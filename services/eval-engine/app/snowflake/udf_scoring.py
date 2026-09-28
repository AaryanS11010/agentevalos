"""Snowpark Python UDF/stored-procedure definitions for in-warehouse scoring.

This is the source of truth for the in-warehouse *inference* logic; it is registered
as a Snowflake stored procedure both by this service (for local/dev deployments where
eval-engine manages the Snowflake objects) and mirrored by the Snowflake Native App's
setup_script.sql (for customers who install the app and never let raw data leave
their account).

Deliberately self-contained (only stdlib + the Anaconda-channel `packages` listed in
register() below) rather than importing app.evaluators/agentevalos_sdk directly: this
function is pickled by reference and executed inside Snowflake's remote Python
sandbox, which only has the Anaconda-channel packages available — not this repo's own
source, and not agentevalos_sdk's OTEL/FastAPI-instrumentation imports, which have no
business running there anyway. It returns raw predictions; the industry-specific
scoring (calibration, fairness, impact score) happens back in eval-engine — see
app/api/routes_leaderboard.py — which is the same reasoning
snowflake-native-app/app/python/udfs/run_eval.py already uses for the native app path.

Model inference: `model_name` is loaded from a joblib-serialized, scikit-learn-API
classifier (`.predict_proba`) staged at `@MODEL_STAGE/{industry}_{model_name}.joblib`
(relative to the calling session's current database/schema — see
app/mcp/snowflake_tools.py, which always connects with database/schema set to
AGENTEVALOS.EVALS). This restricts in-warehouse candidates to models whose
training/inference packages are available on Snowflake's Anaconda channel — today
that's scikit-learn, xgboost, and lightgbm (see `register()` PACKAGES below).
`catboost` and `tabpfn` are deliberately not supported by this path: catboost isn't
reliably on the Anaconda channel and tabpfn is an in-context learner that needs the
training set at inference time, not a fit-once artifact — both would need the
external (non-native-app) `eval-engine`-connects-out deployment mode instead.
`scripts/seed_snowflake.py` trains and stages the demo models this scaffold ships
with, and also calls register() to create the stored procedure.

Deploy/redeploy the stored procedure standalone with:
    python -m app.snowflake.udf_scoring
"""

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
    """Snowpark stored procedure body: pulls labeled rows for `dataset_ref`, scores
    them with the staged `model_name` classifier, and returns raw predictions as a
    JSON string for eval-engine to evaluate downstream. Registered as
    AGENTEVALOS.EVALS.RUN_INDUSTRY_EVAL in Snowflake.
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
    """Registers run_industry_eval_proc as a Snowflake stored procedure. Called from
    scripts/seed_snowflake.py during local setup; mirrored in setup_script.sql for the
    native app deployment path.

    Snowpark pickles the function *by reference* (module + qualified name), not by
    value — the remote sandbox re-imports `app.snowflake.udf_scoring` to resolve it,
    so that module (and its package, `app/`) must physically exist there even though
    its own top-level code has no external imports. `imports` ships just the `app`
    directory to make that import path resolvable; app/__init__.py and
    app/snowflake/__init__.py are both empty, so this doesn't drag in anything else
    (importing a submodule doesn't execute unrelated sibling modules).
    """
    from pathlib import Path

    from snowflake.snowpark.types import StringType

    from app.config import settings

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
