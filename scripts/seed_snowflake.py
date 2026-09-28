"""Creates the AgentEvalOS Snowflake schema/tables, loads small synthetic
finance/healthcare benchmark datasets, and trains + stages a couple of baseline
"foundational tabular model" candidates so the in-warehouse scoring proc
(app/snowflake/udf_scoring.py) has something real to load and run end to end. Not for
production data or models — see datasets/*/README.md for where real labeled datasets
should come from, and swap the trained models below for whatever candidates you
actually want benchmarked.

Usage: python scripts/seed_snowflake.py
Requires SNOWFLAKE_* env vars (see .env.example) to be set.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "eval-engine"))

from app.config import settings
from app.snowflake.client import ensure_schema, get_connection, get_snowpark_session
from app.snowflake.udf_scoring import register as register_scoring_proc

FEATURE_COLUMNS = [f"FEATURE_{i}" for i in range(6)]
# Must match the in-warehouse-servable candidates in
# services/agent-orchestrator/app/graph/nodes.py::DEFAULT_MODEL_CANDIDATES.
BASELINE_MODELS = ["logistic_regression", "xgboost", "lightgbm"]


def _synthetic_dataset(n: int, seed: int) -> pd.DataFrame:
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
    else:
        raise ValueError(f"No training recipe for baseline model {name!r}")
    model.fit(X, y)
    return model


def _stage_models(conn, industry: str, df: pd.DataFrame) -> None:
    import joblib

    X, y = df[FEATURE_COLUMNS].to_numpy(), df["LABEL"].to_numpy()
    stage = f"{settings.snowflake_database}.{settings.snowflake_schema}.MODEL_STAGE"
    cur = conn.cursor()
    with tempfile.TemporaryDirectory() as tmp_dir:
        for model_name in BASELINE_MODELS:
            model = _fit_model(model_name, X, y)
            filename = f"{industry.lower()}_{model_name}.joblib"
            local_path = Path(tmp_dir) / filename
            joblib.dump(model, local_path)
            cur.execute(f"PUT file://{local_path} @{stage} AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
            print(f"Staged {filename} -> @{stage}")


def main() -> None:
    print(f"Seeding Snowflake database={settings.snowflake_database} schema={settings.snowflake_schema}")
    ensure_schema()

    feature_ddl = ", ".join(f"{c} FLOAT" for c in FEATURE_COLUMNS)
    with get_connection() as conn:
        cur = conn.cursor()
        for industry, table in [("FINANCE", "BENCHMARK_DATASET"), ("HEALTHCARE", "BENCHMARK_DATASET")]:
            fq_table = f"{settings.snowflake_database}.{industry}.{table}"
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {settings.snowflake_database}.{industry}")
            cur.execute(
                f"""
                CREATE OR REPLACE TABLE {fq_table} (
                    {feature_ddl}, LABEL INT, SENSITIVE_GROUP INT
                )
                """
            )
            df = _synthetic_dataset(n=2000, seed=hash(industry) % 1000)
            write_pandas_available = True
            try:
                from snowflake.connector.pandas_tools import write_pandas

                write_pandas(conn, df, table_name=table, database=settings.snowflake_database, schema=industry)
            except ImportError:
                write_pandas_available = False
            if not write_pandas_available:
                cols = ", ".join(df.columns)
                placeholders = ", ".join(["%s"] * len(df.columns))
                cur.executemany(
                    f"INSERT INTO {fq_table} ({cols}) VALUES ({placeholders})",
                    df.values.tolist(),
                )
            print(f"Seeded {len(df)} rows into {fq_table}")

            _stage_models(conn, industry, df)

    with get_snowpark_session() as session:
        register_scoring_proc(session)
    print(f"Registered {settings.snowflake_database}.{settings.snowflake_schema}.RUN_INDUSTRY_EVAL")

    print("Done.")


if __name__ == "__main__":
    main()
