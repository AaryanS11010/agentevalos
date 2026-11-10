# Snowflake stored procedures (self-contained; deploy with: python -m app.snowflake.udf_scoring)
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from snowflake.snowpark import Session

RESERVED_COLUMNS = {"LABEL", "SENSITIVE_GROUP"}

# the only datasets the metrics procedure will touch (enforced in the warehouse)
ALLOWED_DATASETS = {"FINANCE.BENCHMARK_DATASET", "HEALTHCARE.BENCHMARK_DATASET"}

# keep in sync with tabular_model_bench.py; the metric_parity eval checks it
IMPACT_WEIGHTS = {
    "finance": {"discrimination": 0.5, "calibration": 0.2, "fairness": 0.3},
    "healthcare": {"discrimination": 0.35, "calibration": 0.35, "fairness": 0.3},
}
FAIRNESS_THRESHOLDS = {"finance": 0.10, "healthcare": 0.08}


def _load_staged_model(session: Session, industry: str, model_name: str):
    import joblib

    filename = f"{industry.lower()}_{model_name}.joblib"
    with tempfile.TemporaryDirectory() as tmp_dir:
        session.file.get(f"@MODEL_STAGE/{filename}", tmp_dir)
        return joblib.load(Path(tmp_dir) / filename)


def _predict(session: Session, industry: str, model_name: str, dataset_ref: str):
    pdf = session.table(dataset_ref).to_pandas()
    feature_cols = [c for c in pdf.columns if c not in RESERVED_COLUMNS]
    model = _load_staged_model(session, industry, model_name)

    X = pdf[feature_cols].to_numpy()
    y_score = model.predict_proba(X)[:, 1] if hasattr(model, "predict_proba") else model.predict(X)
    y_pred = (y_score >= 0.5).astype(int)
    y_true = pdf["LABEL"].to_numpy()
    sensitive = pdf["SENSITIVE_GROUP"].to_numpy() if "SENSITIVE_GROUP" in pdf.columns else None
    return y_true, y_pred, y_score, sensitive


def run_industry_eval_proc(session: Session, industry: str, model_name: str, dataset_ref: str) -> str:
    """AGENTEVALOS.EVALS.RUN_INDUSTRY_EVAL: returns raw predictions as JSON."""
    y_true, y_pred, y_score, sensitive = _predict(session, industry, model_name, dataset_ref)
    return json.dumps(
        {
            "model_name": model_name,
            "y_true": y_true.tolist(),
            "y_pred": y_pred.tolist(),
            "y_score": y_score.tolist(),
            "sensitive_features": sensitive.tolist() if sensitive is not None else None,
        }
    )


def run_industry_metrics_proc(session: Session, industry: str, model_name: str, dataset_ref: str) -> str:
    """AGENTEVALOS.EVALS.RUN_INDUSTRY_METRICS: scores inside Snowflake and returns aggregates only."""
    import numpy as np
    from sklearn.calibration import calibration_curve
    from sklearn.metrics import roc_auc_score

    industry = industry.lower()
    if industry not in IMPACT_WEIGHTS:
        raise ValueError(f"unknown industry: {industry}")
    if dataset_ref.upper() not in ALLOWED_DATASETS or not dataset_ref.upper().startswith(industry.upper() + "."):
        raise ValueError(f"dataset not allowed for {industry}: {dataset_ref}")

    y_true, y_pred, y_score, sensitive = _predict(session, industry, model_name, dataset_ref)

    auroc = float(roc_auc_score(y_true, y_score))
    brier = float(np.mean((y_score - y_true) ** 2))
    prob_true, prob_pred = calibration_curve(y_true, y_score, n_bins=10, strategy="uniform")
    ece = float(np.mean(np.abs(prob_true - prob_pred)))

    order = np.argsort(y_score)
    yt = y_true[order]
    n_pos, n_neg = yt.sum(), len(yt) - yt.sum()
    ks = 0.0
    if n_pos and n_neg:
        ks = float(np.max(np.abs(np.cumsum(yt) / n_pos - np.cumsum(1 - yt) / n_neg)))

    gap = 0.0
    if sensitive is not None:
        rates = [y_pred[sensitive == g].mean() for g in np.unique(sensitive)]
        gap = float(max(rates) - min(rates)) if len(rates) > 1 else 0.0

    # finance is judged on brier score, healthcare on expected calibration error
    calibration_error = brier if industry == "finance" else ece
    weights = IMPACT_WEIGHTS[industry]
    score = (
        weights["discrimination"] * auroc
        + weights["calibration"] * max(0.0, 1 - calibration_error)
        + weights["fairness"] * max(0.0, 1 - gap)
    )
    threshold = FAIRNESS_THRESHOLDS[industry]

    return json.dumps(
        {
            "model_name": model_name,
            "industry": industry,
            "dataset_ref": dataset_ref.upper(),
            "n_rows": len(y_true),
            "auroc": round(auroc, 4),
            "ks_statistic": round(ks, 4),
            "brier_score": round(brier, 4),
            "expected_calibration_error": round(ece, 4),
            "fairness_gap": round(gap, 4),
            "fairness_threshold": threshold,
            "fairness_ok": bool(gap <= threshold),
            "impact_score": round(float(min(max(score, 0.0), 1.0)), 4),
        }
    )


PACKAGES = ["pandas", "pyarrow", "numpy", "scikit-learn", "xgboost", "lightgbm", "joblib"]


def register(session: Session) -> None:
    """Registers both stored procedures in Snowflake."""
    from snowflake.snowpark.types import StringType

    from app.config import settings

    # Snowflake re-imports this module to run the procedures, so upload the app's files
    app_dir = Path(__file__).resolve().parents[1]
    schema = f"{settings.snowflake_database}.{settings.snowflake_schema}"

    for func, name in [
        (run_industry_eval_proc, "RUN_INDUSTRY_EVAL"),
        (run_industry_metrics_proc, "RUN_INDUSTRY_METRICS"),
    ]:
        session.sproc.register(
            func=func,
            name=f"{schema}.{name}",
            return_type=StringType(),
            input_types=None,
            packages=PACKAGES,
            imports=[str(app_dir)],
            is_permanent=True,
            stage_location=f"@{schema}.UDF_STAGE",
            replace=True,
            # Cortex calls tools by argument name; Snowpark would otherwise name them arg1, arg2
            preserve_parameter_names=True,
        )


def grant_to_agent_role(session: Session, role: str = "AGENT_SDK_ROLE") -> None:
    """Lets the Cortex agent's role call the metrics procedure (and only that one)."""
    from app.config import settings

    schema = f"{settings.snowflake_database}.{settings.snowflake_schema}"
    session.sql(
        f"GRANT USAGE ON PROCEDURE {schema}.RUN_INDUSTRY_METRICS(VARCHAR, VARCHAR, VARCHAR) TO ROLE {role}"
    ).collect()


if __name__ == "__main__":
    from app.config import settings
    from app.snowflake.client import get_snowpark_session

    schema = f"{settings.snowflake_database}.{settings.snowflake_schema}"
    with get_snowpark_session() as session:
        # Snowpark can reuse a stale upload, so clear the stage first
        session.sql(f"REMOVE @{schema}.UDF_STAGE").collect()
        register(session)
        grant_to_agent_role(session)
    print(f"Registered {schema}.RUN_INDUSTRY_EVAL and {schema}.RUN_INDUSTRY_METRICS")
