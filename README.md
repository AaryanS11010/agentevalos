# AgentEvalOS

A small project I built to answer one question: **which ML model works best for a given
industry?**

It's an agent (built with LangGraph) that tries a few tabular models (XGBoost,
LightGBM, logistic regression) against finance and healthcare datasets stored in
Snowflake, scores each one on accuracy, calibration, and fairness, and ranks them.

## How it works

1. **Plan** — pick which models to try for the industry.
2. **Benchmark** — call Snowflake (through MCP) to run each model and get predictions.
3. **Score** — send predictions to a second service that scores them on AUROC,
   calibration error, and a fairness gap, and combines those into one impact score.
4. **Decide** — stop once a model scores well enough, otherwise try again.

Everything is traced with OpenTelemetry and shows up in Arize Phoenix. There's also a
small Next.js page for browsing runs and leaderboards, a DeepEval suite that checks
the agent's explanations make sense, and a Promptfoo config for basic red-teaming.

## Project layout

| Path | What |
|---|---|
| `packages/agentevalos-sdk` | Shared code (schemas, tracing setup, MCP client) used by both services |
| `services/agent-orchestrator` | The agent (FastAPI + LangGraph) |
| `services/eval-engine` | Scores model predictions and talks to Snowflake |
| `console` | Next.js page for viewing runs and leaderboards |
| `infra/terraform` | Sets up the Snowflake warehouse/database/role |
| `infra/k8s` | Kubernetes manifests |
| `datasets` | Notes on what real data would replace the fake seeded data |

## Running it locally

```bash
cp .env.example .env        # fill in your Snowflake account + an LLM API key
./scripts/bootstrap.sh      # sets up venvs + npm install
python scripts/seed_snowflake.py   # creates tables, trains + uploads the models
docker compose up -d postgres otel-collector phoenix
```

Then in separate terminals:
```bash
cd services/agent-orchestrator && source .venv/bin/activate && uvicorn app.main:app --reload --port 8001
cd services/eval-engine && source .venv/bin/activate && uvicorn app.main:app --reload --port 8002
cd console && npm run dev
```

Try it:
```bash
curl -X POST http://localhost:8001/runs -H "Content-Type: application/json" -d '{"industry":"finance"}'
```

- Console: http://localhost:3000
- Phoenix traces: http://localhost:6006
- API docs: http://localhost:8001/docs and http://localhost:8002/docs

## Notes

- The data is randomly, so this shows the pipeline works, not that
  any of these models are actually good for real finance/healthcare data.
- `infra/terraform` and `infra/k8s` are written and pass validation, but I haven't
  deployed to a real cloud yet.

## License

Apache-2.0
