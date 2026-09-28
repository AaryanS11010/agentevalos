# AgentEvalOS — Snowflake Native App

Runs AgentEvalOS's industry model-benchmarking + scoring logic entirely inside your
Snowflake account. No data, predictions, or model artifacts ever leave your account —
the app is a set of Python stored procedures, tables, and a Streamlit UI installed
into an application-owned schema.

## What it does

- `core.run_industry_eval(industry, model_name, dataset_ref)` — scores a foundational
  tabular model's predictions (already materialized in a table you grant the app
  access to) against industry-appropriate metrics and appends to `core.model_leaderboard`.
- `core.rank_industry_models(industry)` — returns the ranked leaderboard.
- A Streamlit page (`core.leaderboard_ui`) to trigger runs and view results without
  writing SQL.

## Install (dev)

```bash
cd snowflake-native-app
snow app run
```

This creates the application package + application in your configured Snowflake
connection and opens the Streamlit UI.

## Grant the app access to your data

The app cannot see any table until you explicitly grant it:

```sql
GRANT SELECT ON TABLE my_db.my_schema.my_labeled_dataset
  TO APPLICATION agentevalos_app;
```

Then reference it as `my_db.my_schema.my_labeled_dataset` in the "Dataset" field of
the Streamlit UI, or as the `dataset_ref` argument to `core.run_industry_eval`.

## Relationship to the standalone eval-engine service

`app/python/udfs/run_eval.py` in this app mirrors
[`services/eval-engine/app/snowflake/udf_scoring.py`](../services/eval-engine/app/snowflake/udf_scoring.py)
— same scoring math, two deployment targets. Use the native app when a customer wants
zero data egress; use the standalone `eval-engine` service when you're running the
full AgentEvalOS platform (LangGraph orchestration, DeepEval/Promptfoo, the reviewer
console) against your own Snowflake account. See
[`docs/snowflake_native_app.md`](../docs/snowflake_native_app.md) for the plan to
de-duplicate the two.
