# Creates the Snowflake tables, fills them with fake finance/healthcare data,
# trains a few simple models on that data, and uploads the models to Snowflake
# so the agent has something to test against.
#
# Usage: python scripts/seed_snowflake.py
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from snowflake.connector.pandas_tools import write_pandas

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "eval-engine"))

from app.config import settings
from app.snowflake.client import ensure_schema, get_connection, get_snowpark_session
from app.snowflake.udf_scoring import register as register_scoring_proc

FEATURE_COLUMNS = [f"FEATURE_{i}" for i in range(6)]
# has to match the model names the agent tries in app/graph/nodes.py
MODEL_NAMES = ["logistic_regression", "xgboost", "lightgbm"]


def _fake_dataset(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    features = rng.normal(0, 1, size=(n, len(FEATURE_COLUMNS)))
    signal = features[:, 0] * 1.5 - features[:, 1] * 0.8 + features[:, 2] * 0.5
    label = (signal + rng.normal(0, 1, n) > 0).astype(int)
    sensitive_group = rng.integers(0, 2, n)
    df = pd.DataFrame(features, columns=FEATURE_COLUMNS)
    df["LABEL"] = label
    df["SENSITIVE_GROUP"] = sensitive_group
    return df


def _fit_model(name: str, X: np.ndarray, y: np.ndarray):
    if name == "logistic_regression":
        from sklearn.linear_model import LogisticRegression

        model = LogisticRegression(max_iter=1000)
    elif name == "xgboost":
        from xgboost import XGBClassifier

        model = XGBClassifier(n_estimators=100, max_depth=3, eval_metric="logloss")
    elif name == "lightgbm":
        from lightgbm import LGBMClassifier

        model = LGBMClassifier(n_estimators=100, max_depth=3, verbosity=-1)
    model.fit(X, y)
    return model


def _train_and_upload_models(conn, industry: str, df: pd.DataFrame) -> None:
    import joblib

    X, y = df[FEATURE_COLUMNS].to_numpy(), df["LABEL"].to_numpy()
    stage = f"{settings.snowflake_database}.{settings.snowflake_schema}.MODEL_STAGE"
    cur = conn.cursor()
    with tempfile.TemporaryDirectory() as tmp_dir:
        for model_name in MODEL_NAMES:
            model = _fit_model(model_name, X, y)
            filename = f"{industry.lower()}_{model_name}.joblib"
            local_path = Path(tmp_dir) / filename
            joblib.dump(model, local_path)
            cur.execute(f"PUT file://{local_path} @{stage} AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
            print(f"uploaded {filename}")


def main() -> None:
    print("Setting up Snowflake...")
    ensure_schema()

    feature_ddl = ", ".join(f"{c} FLOAT" for c in FEATURE_COLUMNS)
    with get_connection() as conn:
        cur = conn.cursor()
        for industry in ["FINANCE", "HEALTHCARE"]:
            table = f"{settings.snowflake_database}.{industry}.BENCHMARK_DATASET"
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {settings.snowflake_database}.{industry}")
            cur.execute(f"CREATE OR REPLACE TABLE {table} ({feature_ddl}, LABEL INT, SENSITIVE_GROUP INT)")

            df = _fake_dataset(n=2000, seed=hash(industry) % 1000)
            write_pandas(conn, df, table_name="BENCHMARK_DATASET", database=settings.snowflake_database, schema=industry)
            print(f"loaded {len(df)} rows into {table}")

            _train_and_upload_models(conn, industry, df)

    with get_snowpark_session() as session:
        register_scoring_proc(session)
    print("Done!")


if __name__ == "__main__":
    main()
