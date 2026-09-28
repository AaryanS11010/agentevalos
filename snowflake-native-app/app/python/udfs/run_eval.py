"""Snowpark stored-procedure handler for core.run_industry_eval, registered by
setup_script.sql. This is the in-warehouse twin of
services/eval-engine/app/snowflake/udf_scoring.py — kept dependency-light (no
agentevalos-sdk import) since native app code runs inside Snowflake's Python sandbox
without access to the rest of this repo. Scoring math is duplicated intentionally at
this scaffolding stage; see docs/snowflake_native_app.md for the plan to share it via
a vendored package instead.

Model inference mirrors udf_scoring.py: `model_name` is a joblib-serialized,
scikit-learn-API classifier the consumer stages at
`@core.model_stage/{industry}_{model_name}.joblib` (see README.md). Only models whose
packages are on the Snowflake Anaconda channel work here — scikit-learn, xgboost,
lightgbm — consistent with the PACKAGES list on core.run_industry_eval in
setup_script.sql.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from snowflake.snowpark import Session

RESERVED_COLUMNS = {"LABEL", "SENSITIVE_GROUP"}


def _ks_statistic(y_true: np.ndarray, y_score: np.ndarray) -> float:
    order = np.argsort(y_score)
    y_true_sorted = y_true[order]
    n_pos, n_neg = y_true_sorted.sum(), len(y_true_sorted) - y_true_sorted.sum()
    if n_pos == 0 or n_neg == 0:
        return 0.0
    cum_pos = np.cumsum(y_true_sorted) / n_pos
    cum_neg = np.cumsum(1 - y_true_sorted) / n_neg
    return float(np.max(np.abs(cum_pos - cum_neg)))


def _load_staged_model(session: Session, industry: str, model_name: str):
    import joblib

    filename = f"{industry.lower()}_{model_name}.joblib"
    with tempfile.TemporaryDirectory() as tmp_dir:
        session.file.get(f"@core.model_stage/{filename}", tmp_dir)
        return joblib.load(Path(tmp_dir) / filename)


def handler(session: Session, industry: str, model_name: str, dataset_ref: str) -> str:
    from sklearn.metrics import roc_auc_score

    df: pd.DataFrame = session.table(dataset_ref).to_pandas()

    feature_cols = [c for c in df.columns if c not in RESERVED_COLUMNS]
    model = _load_staged_model(session, industry, model_name)

    y_true = df["LABEL"].to_numpy()
    X = df[feature_cols].to_numpy()
    y_score = (
        model.predict_proba(X)[:, 1] if hasattr(model, "predict_proba") else model.predict(X)
    )

    auroc = float(roc_auc_score(y_true, y_score))
    ks = _ks_statistic(y_true, y_score)
    brier = float(np.mean((y_score - y_true) ** 2))
    impact_score = round(float(np.clip(0.6 * auroc + 0.4 * (1 - brier), 0, 1)), 4)

    session.sql(
        """
        INSERT INTO core.model_leaderboard
        (industry, model_name, dataset_ref, primary_metric_name, primary_metric_value,
         calibration_error, fairness_gap, latency_ms_p50, impact_score, evaluated_at)
        SELECT ?, ?, ?, 'auroc', ?, NULL, NULL, NULL, ?, CURRENT_TIMESTAMP()
        """,
        params=[industry, model_name, dataset_ref, auroc, impact_score],
    ).collect()

    return json.dumps(
        {"model_name": model_name, "auroc": auroc, "ks_statistic": ks, "impact_score": impact_score}
    )
