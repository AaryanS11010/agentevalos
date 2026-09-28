-- AgentEvalOS Native App setup script.
-- Runs once when the consumer installs/upgrades the app in their account.
-- Creates an app-owned schema, the industry benchmark tables, the scoring stored
-- procedure (mirrors services/eval-engine/app/snowflake/udf_scoring.py), and the
-- Streamlit-in-Snowflake leaderboard UI. All data stays in the consumer's account —
-- nothing here calls out to an external service.

CREATE APPLICATION ROLE IF NOT EXISTS app_admin;
CREATE APPLICATION ROLE IF NOT EXISTS app_viewer;

CREATE OR ALTER VERSIONED SCHEMA core;
GRANT USAGE ON SCHEMA core TO APPLICATION ROLE app_admin;
GRANT USAGE ON SCHEMA core TO APPLICATION ROLE app_viewer;

-- Leaderboard + eval history tables. Mirrors AGENTEVALOS.EVALS.* in the standalone
-- eval-engine deployment so the same reporting queries work in either mode.
CREATE TABLE IF NOT EXISTS core.model_leaderboard (
    industry              STRING,
    model_name            STRING,
    dataset_ref           STRING,
    primary_metric_name   STRING,
    primary_metric_value  FLOAT,
    calibration_error     FLOAT,
    fairness_gap          FLOAT,
    latency_ms_p50        FLOAT,
    impact_score          FLOAT,
    evaluated_at           TIMESTAMP_NTZ
);
GRANT SELECT ON TABLE core.model_leaderboard TO APPLICATION ROLE app_viewer;
GRANT SELECT, INSERT ON TABLE core.model_leaderboard TO APPLICATION ROLE app_admin;

CREATE TABLE IF NOT EXISTS core.eval_results (
    run_id      STRING,
    industry    STRING,
    evaluator   STRING,
    model_name  STRING,
    metrics     VARIANT,
    dataset_ref STRING,
    created_at  TIMESTAMP_NTZ
);
GRANT SELECT ON TABLE core.eval_results TO APPLICATION ROLE app_viewer;
GRANT SELECT, INSERT ON TABLE core.eval_results TO APPLICATION ROLE app_admin;

-- Internal stage the consumer uploads joblib-serialized candidate models to, named
-- `{industry}_{model_name}.joblib` (e.g. finance_xgboost.joblib) — see README.md.
CREATE STAGE IF NOT EXISTS core.model_stage;
GRANT READ ON STAGE core.model_stage TO APPLICATION ROLE app_admin;
GRANT WRITE ON STAGE core.model_stage TO APPLICATION ROLE app_admin;

-- Python stored procedure that scores a labeled dataset already present in the
-- consumer's account (referenced by the consumer at grant time — see README.md)
-- against a foundational tabular model staged in core.model_stage and appends to
-- the leaderboard.
CREATE OR REPLACE PROCEDURE core.run_industry_eval(
    industry STRING,
    model_name STRING,
    dataset_ref STRING
)
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python', 'pandas', 'numpy', 'scikit-learn', 'xgboost', 'lightgbm', 'joblib')
IMPORTS = ('/python/udfs/run_eval.py')
HANDLER = 'run_eval.handler'
;
GRANT USAGE ON PROCEDURE core.run_industry_eval(STRING, STRING, STRING) TO APPLICATION ROLE app_admin;

-- Aggregation proc backing the Streamlit leaderboard view.
CREATE OR REPLACE PROCEDURE core.rank_industry_models(industry STRING)
RETURNS TABLE (model_name STRING, impact_score FLOAT, primary_metric_value FLOAT)
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
IMPORTS = ('/python/udfs/industry_benchmark.py')
HANDLER = 'industry_benchmark.handler'
;
GRANT USAGE ON PROCEDURE core.rank_industry_models(STRING) TO APPLICATION ROLE app_viewer;

CREATE STREAMLIT IF NOT EXISTS core.leaderboard_ui
    FROM '/'
    MAIN_FILE = 'streamlit_app.py';
GRANT USAGE ON STREAMLIT core.leaderboard_ui TO APPLICATION ROLE app_viewer;
