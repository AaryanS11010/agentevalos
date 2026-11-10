# AgentEvalOS

A project that answers one question: **which ML model works best for a given industry?**

An agent benchmarks three tabular models (XGBoost, LightGBM, logistic regression) on
finance and healthcare datasets in Snowflake, scores each on accuracy, calibration, and
fairness, and recommends one. The same task is built **two ways** so they can be compared:

| | LangGraph agent | Snowflake Cortex agent |
|---|---|---|
| Where the loop runs | Python service (`POST /runs`) | Snowflake Cortex Agents (`POST /cortex/runs`) |
| How it reaches Snowflake | MCP tool server | Stored procedure registered as an agent tool |
| Where models are scored | Snowflake, but predictions come back and are scored in a second service | Entirely inside Snowflake |
| Data leaving Snowflake per call | **59,163 bytes** (every row's prediction) | **about 320 bytes** (summary metrics) |
| Orchestration | Fixed graph: plan, benchmark, score, decide | The model decides which tool calls to make |

Numbers are from one real run each against the test account; the Cortex path took roughly
20 to 30 seconds per question. I didn't measure the LangGraph path's latency.

## Why I added the Cortex version

Building the agent on top of the data layer means the scoring happens where the data
already is, and Snowflake's own access controls apply to what the agent can touch. The
LangGraph version pulls every prediction out of the warehouse to score it elsewhere, which
undercuts the point of running inference in the warehouse. The first custom eval below
(`data_residency`) fails on the LangGraph path for exactly this reason, and that failure is
what motivated the second version.

### Notes on using the Cortex Agents SDK (v0.0.3, preview)

These are things I ran into, not general claims:

- **Setup has real friction.** Before the first call I needed a programmatic access token,
  a network policy attached to my user (Snowflake refuses the token without one), a
  limited role with Cortex access, and `USAGE` grants on the warehouse, database, schema
  and the procedure. Each missing piece gave a different error.
- **Stored-procedure tools are called with named arguments.** Snowpark names registered
  parameters `arg1, arg2, ...` by default, so every call failed until I registered with
  `preserve_parameter_names=True`.
- **`instructions` must be an object** (`orchestration`, `response`). A plain string returns
  "request does not contain a valid payload" without naming the field.
- **Access problems show up at run time, not when the agent is defined.** The agent
  accepted tools it couldn't reach, then reported the failed calls in its answer. It
  described the failure honestly instead of making up numbers, which is the behaviour I'd
  want, but it means you only find out by running it.
- **The docs and the SDK disagree.** Snowflake's getting-started guide uses
  `client.agent.stream(...)`; the installed 0.0.3 client only has `conversations` and
  `feedback`. The SDK source was the reliable reference.
- **Tool output is size-limited.** Results carry a `truncated` flag, another reason not to
  return raw predictions from a tool.
- **The wording varies, the numbers don't.** The model's prose changes between runs, but
  the metrics come from a deterministic procedure, so the evals check the numbers.
- **Not yet verified:** cost per run, behaviour under concurrent calls, and whether
  client-side tools are supported (the SDK has types for them but I found no documented
  tool declaration).

## The evals, and why each one exists

Off-the-shelf evals mostly measure generic qualities (is the text fluent, is it relevant).
For an agent whose job is to recommend a model, the failures that matter are specific:
leaking data, quoting numbers the tools never returned, recommending an unfair model.
So the main evals here are custom, deterministic checks, plain Python over a recorded agent
run (`packages/agentevalos-sdk/agentevalos_sdk/custom_evals.py`). They are cheap, repeatable,
and a failure always comes with a reason.

| Eval | What it checks | Why it exists |
|---|---|---|
| `data_residency` | Tool outputs contain no row-level fields, no long lists, are small, and weren't truncated | The reason for running inside Snowflake is that raw data stays there. This turns that claim into a test. |
| `explanation_faithfulness` | Every decimal number in the written answer appears in a tool result | A fluent answer can quote a number nobody computed. Checking against tool results needs no LLM judge. A derived figure like "96.8%" is flagged too, since the agent worked it out itself. |
| `fairness_guardrail` | The recommended model passes its fairness threshold; refusing is only correct if no model qualifies | The top impact score can belong to a model that fails fairness. The agent should not follow the score blindly, and should not over-refuse either. |
| `ranking_correctness` | The agent's pick matches an exhaustive run scored by a separate code path | Tests the agent's judgement against ground truth, not just its fluency. |
| `coverage` | Every candidate is benchmarked exactly once | An agent that skips a model, or repeats one, can still sound confident. |
| `scope` and `scope_backstop` | No data comes back for a dataset outside the allowlist; the procedure itself also refuses it | The agent refusing is only a prompt. The second check confirms Snowflake enforces the rule if the prompt is ignored. |
| `reproducibility` | Same question twice gives identical metrics and the same pick | Variation in wording is fine; variation in numbers or the recommendation is not. |
| `metric_parity` | The impact score computed in Snowflake matches the eval-engine's own calculation | The scoring logic exists in two places. This catches them drifting apart. |

**How I know the evals can fail.** Each has unit tests with a passing and a failing example
(`packages/agentevalos-sdk/tests/test_custom_evals.py`, 16 tests). The live runner also
includes a negative control: it runs the residency check on the LangGraph path's real output,
which must fail, and it does ("row-level fields returned: y_true, y_pred, y_score,
sensitive_features").

**Live result** (`python scripts/run_custom_evals.py`, against a real account): 19 of 19
checks pass.

**What the live run doesn't show.** All three models pass the fairness threshold on this
data, so `fairness_guardrail` has only been shown to catch a violation in the unit tests,
not live. The data is generated, so the passing scores say the pipeline works, not that any
model is good on real data. The live suite needs a Snowflake account, so it isn't part of CI.

### Other checks in the repo

| Check | Why it's there | Status |
|---|---|---|
| Unit tests for the metric math and scoring (`services/eval-engine/tests`) | A wrong AUROC or impact score would silently corrupt every ranking | Runs in CI |
| Tests for the LangGraph decision logic and the API routes (`services/agent-orchestrator/tests`) | The stop rule and run-saving logic can be checked without Snowflake | Runs in CI |
| DeepEval suite (`services/eval-engine/app/deepeval_suites`) | Uses an LLM judge to rate explanation quality, which a deterministic check can't | Written, not run in CI; needs an LLM API key. I'd treat its scores as a second opinion, not ground truth. |
| Promptfoo config (`services/eval-engine/app/promptfoo`) | Probes the LangGraph API for prompt injection, PII and excessive agency | Config validates; I have not run a red-team pass |
| CI: lint, tests, console build, `terraform validate` | Catches broken builds before they merge | Runs in CI |

## Running it

```bash
cp .env.example .env        # fill in Snowflake account, user, password
./scripts/bootstrap.sh      # venvs + npm install
python scripts/seed_snowflake.py   # tables, fake data, trained models, stored procedures
```

For the Cortex agent you also need, in Snowflake: a role with Cortex access and `USAGE` on the
warehouse, database, schema and `RUN_INDUSTRY_METRICS`; a network policy on your user; and a
programmatic access token, set as `SNOWFLAKE_PAT` in `.env`. Then `python -m app.snowflake.udf_scoring`
(from `services/eval-engine`, with its venv active) re-registers the procedures and grants the
metrics one to `AGENT_SDK_ROLE`.

```bash
docker compose up -d postgres otel-collector phoenix
cd services/agent-orchestrator && source .venv/bin/activate && uvicorn app.main:app --port 8001
cd services/eval-engine && source .venv/bin/activate && uvicorn app.main:app --port 8002
cd console && npm run dev
```

```bash
# LangGraph agent
curl -X POST http://localhost:8001/runs -H "Content-Type: application/json" -d '{"industry":"finance"}'
# Cortex agent
curl -X POST http://localhost:8001/cortex/runs -H "Content-Type: application/json" -d '{"industry":"finance"}'
# custom evals, live (from the eval-engine venv)
python scripts/run_custom_evals.py
```

Console: http://localhost:3000, Phoenix traces: http://localhost:6006.

## Layout

| Path | What |
|---|---|
| `packages/agentevalos-sdk` | Shared code: schemas, tracing, MCP client, the Cortex agent runner, the custom evals |
| `services/agent-orchestrator` | FastAPI service with both agents (`/runs`, `/cortex/runs`) |
| `services/eval-engine` | Scores predictions for the LangGraph path; owns the Snowflake stored procedures |
| `scripts` | Seeding and the live eval runner |
| `console` | Next.js page for runs and leaderboards |
| `infra/terraform`, `infra/k8s` | Snowflake setup and Kubernetes manifests; validated, never deployed |

## Known limits

- The data is randomly generated.
- The Cortex SDK is a pre-1.0 preview and its API may change.
- The two scoring paths duplicate the impact-score weights; `metric_parity` is the guard.
- Terraform and Kubernetes pass validation but haven't been applied to real infrastructure.

## License

Apache-2.0
