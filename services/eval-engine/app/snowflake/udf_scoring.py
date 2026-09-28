# This is registered as a stored procedure that runs INSIDE Snowflake: it loads
# a saved model file from a stage, scores the dataset, and returns the predictions.
# It has to be self-contained (no imports from the rest of this app) because
# Snowflake runs it in its own sandbox and only has stdlib + a few packages.
#
# Deploy/redeploy it with: python -m app.snowflake.udf_scoring
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from snowflake.snowpark import Session

RESERVED_COLUMNS = {"LABEL", "SENSITIVE_GROUP"}


def _load_staged_model(session: Session, industry: str, model_name: str):
    import joblib

    filename = f"{industry.lower()}_{model_name}.joblib"
    with tempfile.TemporaryDirectory() as tmp_dir:
        session.file.get(f"@MODEL_STAGE/{filename}", tmp_dir)
        return joblib.load(Path(tmp_dir) / filename)


def run_industry_eval_proc(session: Session, industry: str, model_name: str, dataset_ref: str) -> str:
    """Runs in Snowflake as AGENTEVALOS.EVALS.RUN_INDUSTRY_EVAL. Loads the dataset,
    scores it with the staged model, and returns raw predictions as JSON.
    """
    pdf = session.table(dataset_ref).to_pandas()

    feature_cols = [c for c in pdf.columns if c not in RESERVED_COLUMNS]
    model = _load_staged_model(session, industry, model_name)

    y_true = pdf["LABEL"].to_numpy()
    X = pdf[feature_cols].to_numpy()
    y_score = (
        model.predict_proba(X)[:, 1] if hasattr(model, "predict_proba") else model.predict(X)
    )
    y_pred = (y_score >= 0.5).astype(int)
    sensitive = pdf["SENSITIVE_GROUP"].to_numpy() if "SENSITIVE_GROUP" in pdf.columns else None

    return json.dumps(
        {
            "model_name": model_name,
            "y_true": y_true.tolist(),
            "y_pred": y_pred.tolist(),
            "y_score": y_score.tolist(),
            "sensitive_features": sensitive.tolist() if sensitive is not None else None,
        }
    )


def register(session: Session) -> None:
    """Registers run_industry_eval_proc as a stored procedure in Snowflake."""
    from snowflake.snowpark.types import StringType

    from app.config import settings

    # Snowflake needs this app's source files uploaded so it can find the
    # function when it re-imports this module to run the procedure.
    app_dir = Path(__file__).resolve().parents[1]

    session.sproc.register(
        func=run_industry_eval_proc,
        name=f"{settings.snowflake_database}.{settings.snowflake_schema}.RUN_INDUSTRY_EVAL",
        return_type=StringType(),
        input_types=None,
        packages=["pandas", "pyarrow", "numpy", "scikit-learn", "xgboost", "lightgbm", "joblib"],
        imports=[str(app_dir)],
        is_permanent=True,
        stage_location=f"@{settings.snowflake_database}.{settings.snowflake_schema}.UDF_STAGE",
        replace=True,
    )


if __name__ == "__main__":
    from app.config import settings
    from app.snowflake.client import get_snowpark_session

    with get_snowpark_session() as session:
        register(session)
    print(f"Registered {settings.snowflake_database}.{settings.snowflake_schema}.RUN_INDUSTRY_EVAL")
