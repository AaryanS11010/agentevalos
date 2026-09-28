# Architecture

## Goal

AgentEvalOS answers two related questions for an enterprise running agents over
regulated tabular data:

1. **AgentOps**: is this LangGraph agent behaving correctly — traced, evaluated,
   red-teamed — before and after it ships?
2. **Model impact**: of the foundational tabular models available (XGBoost, CatBoost,
   LightGBM, TabPFN, ...), which one is actually most impactful for a specific
   regulated workload (credit risk, fraud, clinical risk, readmission), once you
   account for discrimination power, calibration, and fairness — not just accuracy?

The second question is answered by a dedicated agent (`tabular_model_bench`, run as a
LangGraph workflow) rather than a one-off notebook, so the benchmark is reproducible,
traced, and re-runnable as new data lands in Snowflake.

## Components

### agent-orchestrator (FastAPI + LangGraph)

Owns the `AgentState` graph defined in
[`app/graph/state.py`](../services/agent-orchestrator/app/graph/state.py):
`plan → run_benchmark → score → (loop | finalize)`. `plan` picks candidate models for
the industry; `run_benchmark` calls the Snowflake MCP tool
([`app/mcp/snowflake_tools.py`](../services/agent-orchestrator/app/mcp/snowflake_tools.py))
to score each model; `score` hands raw results to eval-engine; the loop continues
until a leaderboard entry clears an impact-score threshold or `max_iterations` is hit.

State is checkpointed to Postgres via `langgraph-checkpoint-postgres`
([`app/graph/workflow.py`](../services/agent-orchestrator/app/graph/workflow.py)), so
a run can be resumed after a crash instead of restarting from scratch — this is what
makes it a *durable* stateful workflow rather than a single request/response call.

### eval-engine (FastAPI)

Three kinds of evaluation, all producing the shared `EvalResult`/`EvalMetric` schema
([`packages/agentevalos-sdk/agentevalos_sdk/schemas.py`](../packages/agentevalos-sdk/agentevalos_sdk/schemas.py)):

- **Industry evaluators** ([`app/evaluators/finance`](../services/eval-engine/app/evaluators/finance), [`app/evaluators/healthcare`](../services/eval-engine/app/evaluators/healthcare)) — deterministic, rule-based metrics (AUROC, KS-statistic, expected calibration error, demographic parity gap) appropriate to each regulated domain.
- **LLM-judge evals** ([`app/deepeval_suites`](../services/eval-engine/app/deepeval_suites)) — DeepEval `GEval`/`FaithfulnessMetric` checks on the agent's natural-language output, run as a pytest suite in CI.
- **Red-team** ([`app/evaluators/redteam`](../services/eval-engine/app/evaluators/redteam), [`app/promptfoo`](../services/eval-engine/app/promptfoo)) — Promptfoo-driven adversarial probes (prompt injection, PII leakage, SQL injection attempts against the Snowflake MCP tool) as a CI release gate.

`app/evaluators/tabular_model_bench.py` combines industry-evaluator metrics into a
single `impact_score` per model (see `INDUSTRY_WEIGHTS`), producing the ranked
leaderboard that both the console and the Snowflake Native App read.

### Snowflake Native App

The same scoring logic, packaged as Snowpark stored procedures + a Streamlit UI that
installs directly into a customer's Snowflake account
([`snowflake-native-app/`](../snowflake-native-app)). For customers who won't let
prediction data leave their account, this is the deployment path — no call to
eval-engine required. See [`docs/snowflake_native_app.md`](snowflake_native_app.md).

### Reviewer console (Next.js)

Reads `agent-orchestrator` (`/runs`) and `eval-engine` (`/benchmarks/industry/{industry}/leaderboard`)
directly via server components — see [`console/lib/api.ts`](../console/lib/api.ts).
No BFF layer yet; add one if/when the console needs to aggregate across services or
hide credentials from the browser.

### Tracing

Both FastAPI services call `agentevalos_sdk.otel_setup.instrument_fastapi()` at
startup, exporting OTLP spans tagged with OpenInference semantic conventions
(`openinference.span.kind`) so they render correctly in Arize Phoenix — or in Future
AGI's platform, since it consumes the same OpenInference conventions. This is why
AgentEvalOS doesn't reimplement tracing/eval-metric UI: it interops with that
ecosystem instead of competing with it, and focuses on the Snowflake-native
benchmarking layer neither currently owns.

## Data split: Postgres vs. Snowflake

| | Postgres | Snowflake |
|---|---|---|
| Owns | Run/step/tool-call metadata, LangGraph checkpoints | Labeled benchmark datasets, model leaderboard, eval result history |
| Access pattern | Low-latency, transactional, per-run | Warehouse-scale, analytical, append-heavy |
| Written by | agent-orchestrator | eval-engine (`app/snowflake/client.py`) and the native app's stored procs |

## What's stubbed vs. real

- Graph nodes, evaluator math, API routes, and DB models are real, runnable code.
- Model *inference* (`app/snowflake/udf_scoring.py`,
  `snowflake-native-app/app/python/udfs/run_eval.py`) loads a joblib-staged,
  scikit-learn-API classifier per `{industry}_{model_name}` and scores it against the
  dataset's feature columns in-warehouse. This restricts candidates to models whose
  packages are on Snowflake's Anaconda channel (scikit-learn, xgboost, lightgbm) —
  `catboost`/`tabpfn` aren't supported by this path yet (see `udf_scoring.py`) and
  would need eval-engine's external, non-native-app deployment mode instead.
  `scripts/seed_snowflake.py` trains and stages the demo models.
- `langgraph-checkpoint-postgres` setup falls back to an in-memory checkpointer if the
  package isn't installed, so the service boots during early scaffolding without a
  hard dependency failure.
