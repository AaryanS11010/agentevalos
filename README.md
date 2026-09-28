# AgentEvalOS

**AgentEvalOS** is an open-source AgentOps and evaluation framework for enterprises running AI agents on regulated,
high-stakes tabular data (finance, healthcare). It standardizes how you **instrument** (LangGraph + MCP + OpenTelemetry),
**benchmark** (DeepEval + Promptfoo + industry-specific evaluators), **red-team**, and **release** agents — with
warehouse-scale analytics in Snowflake and a reviewer console for humans in the loop.

It is built to interoperate with the [Future AGI](https://github.com/future-agi/future-agi) ecosystem
(`traceAI` OTel instrumentation, `ai-evaluation` metrics, Arize Phoenix) rather than reinvent it — AgentEvalOS focuses
on the piece those platforms don't own out of the box: a **Snowflake-native evaluation and benchmarking layer** that
tells you which foundational tabular models (XGBoost, CatBoost, TabPFN, LightGBM, in-house nets, ...) actually move
the needle for a given regulated industry workload, plus the agent that runs those benchmarks continuously.

## What it does

1. **Instrument** — Every agent run (LangGraph graph execution, MCP tool calls) is traced with OpenTelemetry /
   OpenInference semantic conventions and exported to Phoenix (or any OTLP backend).
2. **Evaluate** — `eval-engine` runs LLM-judge evals (DeepEval), deterministic rule-based evals, and
   **industry-specific evaluators** for finance (credit risk, fraud) and healthcare (clinical risk, readmission)
   against foundational tabular models.
3. **Benchmark** — The `tabular_model_bench` agent pulls labeled datasets from Snowflake, runs a pluggable set of
   foundational tabular models, scores them with industry-appropriate metrics (AUROC, KS-statistic, calibration,
   subgroup fairness), and writes a ranked leaderboard back to Snowflake — answering "which model is most impactful
   for this industry, right now."
4. **Red-team** — Promptfoo-driven adversarial suites (prompt injection, PII leakage, jailbreaks) run in CI as a
   release gate.
5. **Release** — Results, traces, and red-team findings surface in a Next.js reviewer console; a Snowflake Native
   App ships the same benchmarking/scoring logic to run entirely inside a customer's Snowflake account.

## Architecture

```
                        ┌─────────────────────────┐
                        │   Reviewer Console       │  React / Next.js
                        │   (runs, evals, industry │
                        │    leaderboards)         │
                        └────────────┬─────────────┘
                                     │ REST
        ┌────────────────────────────┼─────────────────────────────┐
        │                             │                             │
┌───────▼────────┐           ┌────────▼─────────┐          ┌────────▼────────┐
│ agent-          │  MCP      │  eval-engine      │ writes   │  Postgres        │
│ orchestrator    │◄─────────►│  (DeepEval,       │ metadata │  (runs, steps,   │
│ (FastAPI +      │  tools    │   Promptfoo,      │─────────►│   tool calls,    │
│  LangGraph)     │           │   industry evals) │          │   eval results)  │
└───────┬─────────┘           └─────────┬─────────┘          └──────────────────┘
        │ OpenTelemetry / OpenInference            │ reads/writes (Snowpark)
        ▼                                          ▼
┌────────────────────┐                    ┌──────────────────────────┐
│  OTel Collector →   │                    │   Snowflake               │
│  Arize Phoenix       │                   │   - eval datasets         │
└────────────────────┘                    │   - model leaderboard     │
                                            │   - Snowflake Native App  │
                                            │     (in-warehouse scoring)│
                                            └──────────────────────────┘
```

## Repo layout

| Path | What |
|---|---|
| [`packages/agentevalos-sdk`](packages/agentevalos-sdk) | Shared schemas, OTel setup, MCP client — imported by both services |
| [`services/agent-orchestrator`](services/agent-orchestrator) | FastAPI + LangGraph service that runs agent workflows and calls MCP tools |
| [`services/eval-engine`](services/eval-engine) | FastAPI service: DeepEval/Promptfoo evals, industry evaluators, tabular model benchmarking, Snowflake I/O |
| [`snowflake-native-app`](snowflake-native-app) | Snowflake Native Application — ships benchmarking/scoring as UDFs + Streamlit-in-Snowflake, runs inside the customer's account |
| [`console`](console) | Next.js reviewer console (runs, evals, industry leaderboards) |
| [`infra/terraform`](infra/terraform) | Terraform: Snowflake objects, Postgres, Kubernetes cluster |
| [`infra/k8s`](infra/k8s) | Kustomize manifests for the two services + console + Postgres + OTel collector |
| [`.github/workflows`](.github/workflows) | CI: lint/test, docker build, terraform plan, red-team gate |
| [`datasets`](datasets) | Synthetic finance/healthcare dataset specs used for local dev + seeding Snowflake |
| [`docs`](docs) | Architecture, eval methodology, Snowflake Native App packaging notes |

## Quickstart (local dev)

```bash
cp .env.example .env
./scripts/bootstrap.sh          # creates venvs, installs deps for both services + sdk
docker compose up -d postgres otel-collector phoenix
docker compose up agent-orchestrator eval-engine
cd console && npm install && npm run dev
```

Orchestrator: http://localhost:8001/docs · Eval engine: http://localhost:8002/docs · Console: http://localhost:3000 ·
Phoenix: http://localhost:6006

## Status

Scaffolding stage — services boot, endpoints and evaluators are stubbed with clear extension points. See
[`docs/architecture.md`](docs/architecture.md) and [`docs/evals.md`](docs/evals.md) for what's implemented vs. TODO.

## License

Apache-2.0
