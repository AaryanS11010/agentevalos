# AgentEvalOS

Which ML model works best for a given industry? An agent benchmarks XGBoost, LightGBM and
logistic regression on finance and healthcare data in Snowflake, scores each on accuracy,
calibration and fairness, and recommends one.

The same task is built two ways so they can be compared:

| | LangGraph agent | Snowflake Cortex agent |
|---|---|---|
| Endpoint | `POST /runs` | `POST /cortex/runs` |
| Loop runs in | A Python service | Snowflake Cortex Agents |
| Reaches Snowflake via | MCP tool server | Stored procedure registered as the agent's tool |
| Models scored | Predictions come back, a second service scores them | Entirely inside Snowflake |
| Data leaving Snowflake per call | 59,163 bytes (every row's prediction) | about 320 bytes (summary metrics) |

Measured on one real run each. The Cortex path took roughly 20 to 30 seconds per question;
the LangGraph path wasn't timed.

## Quick start

You need a Snowflake account (Enterprise edition for Cortex), Python 3.11+ and Node 20+.
Docker is optional.

**1. Set up**

```bash
cp .env.example .env     # fill in SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD
./scripts/bootstrap.sh   # creates a .venv per package and runs npm install
source services/eval-engine/.venv/bin/activate
python scripts/seed_snowflake.py   # tables, generated data, trained models, stored procedures
```

**2. Check it works: the evals** (the fastest way to see everything run; needs the Cortex setup below)

```bash
python scripts/run_custom_evals.py   # expect: 19/19 checks passed
```

**3. Run the services**

```bash
# terminal 1: eval-engine
cd services/eval-engine && source .venv/bin/activate && uvicorn app.main:app --port 8002

# terminal 2: orchestrator (SQLite means no Docker needed; use Postgres via docker compose if you prefer)
cd services/agent-orchestrator && source .venv/bin/activate
DATABASE_URL=sqlite:///./agentevalos.db uvicorn app.main:app --port 8001

# terminal 3: console
cd console && npm run dev
```

```bash
curl -X POST localhost:8001/runs        -H "Content-Type: application/json" -d '{"industry":"finance"}'
curl -X POST localhost:8001/cortex/runs -H "Content-Type: application/json" -d '{"industry":"finance"}'
```

Console: http://localhost:3000 (leaderboards and LangGraph runs). API docs: http://localhost:8001/docs.
Traces: `docker compose up -d phoenix otel-collector`, then http://localhost:6006.

### Cortex setup (only for `/cortex/runs` and the live evals)

Run once in a Snowsight worksheet as ACCOUNTADMIN, using your own username:

```sql
create role if not exists AGENT_SDK_ROLE;
grant database role snowflake.cortex_user to role AGENT_SDK_ROLE;
grant role AGENT_SDK_ROLE to user YOUR_USERNAME;
grant usage on warehouse AGENTEVALOS_WH to role AGENT_SDK_ROLE;
grant usage on database AGENTEVALOS to role AGENT_SDK_ROLE;
grant usage on schema AGENTEVALOS.EVALS to role AGENT_SDK_ROLE;
create network policy AGENTEVALOS_POLICY allowed_ip_list = ('YOUR_PUBLIC_IP');
alter user YOUR_USERNAME set network_policy = AGENTEVALOS_POLICY;
```

Then generate a token (Snowsight: your name, Settings, Authentication, Programmatic access
tokens, restricted to `AGENT_SDK_ROLE`), put it in `.env` as `SNOWFLAKE_PAT=...`, and grant
the metrics procedure to the role:

```bash
cd services/eval-engine && python -m app.snowflake.udf_scoring
```

## Custom evals

Generic evals measure generic qualities, like whether text is fluent. For an agent that
recommends a model, the failures that matter are specific: leaking data, quoting numbers no
tool returned, recommending an unfair model. So the main evals are deterministic checks over
a recorded agent run (`packages/agentevalos-sdk/agentevalos_sdk/custom_evals.py`). They are
cheap, repeatable, and every failure comes with a reason.

| Eval | Checks | Why it exists |
|---|---|---|
| `data_residency` | Tool outputs have no row-level fields, no long lists, are small, and weren't truncated | Running inside Snowflake is only worth it if raw data stays there. This makes the claim testable. |
| `explanation_faithfulness` | Every decimal in the written answer appears in a tool result | A fluent answer can quote a number nobody computed. A derived figure like "96.8%" is flagged too. No LLM judge needed. |
| `fairness_guardrail` | The recommended model passes its fairness threshold | The top impact score can belong to a model that fails fairness, and the agent shouldn't follow the score blindly. Refusing is only correct if no model qualifies. |
| `ranking_correctness` | The pick matches an exhaustive run scored by a separate code path | Tests the agent's judgement against ground truth, not its fluency. |
| `coverage` | Every candidate is benchmarked exactly once | An agent that skips or repeats a model can still sound confident. |
| `scope`, `scope_backstop` | No data returns for a dataset outside the allowlist, and the procedure itself refuses it | The agent refusing is only a prompt. The second check confirms Snowflake enforces the rule if the prompt is ignored. |
| `reproducibility` | The same question twice gives identical metrics and the same pick | Wording may vary. Numbers and the recommendation must not. |
| `metric_parity` | The impact score computed in Snowflake matches the eval-engine's own calculation | The scoring logic exists in two places. This catches drift. |

**Can they fail?** Each has unit tests with a passing and a failing example (16 tests). The
live runner also has a negative control: the residency check run on the LangGraph path's real
output must fail, and it does.

**Live result:** 19 of 19 checks pass against a real account. All three models pass the
fairness threshold on this data, so `fairness_guardrail` has only been shown to catch a
violation in unit tests. The data is generated, so the scores show the pipeline works, not that
any model is good on real data. The live suite needs a Snowflake account, so it isn't in CI.

### Other checks

| Check | Why | Status |
|---|---|---|
| Metric and scoring unit tests (`services/eval-engine/tests`) | A wrong AUROC or impact score would silently corrupt every ranking | In CI |
| Decision-logic and route tests (`services/agent-orchestrator/tests`) | The stop rule and run saving can be checked without Snowflake | In CI |
| DeepEval suite (`services/eval-engine/app/deepeval_suites`) | An LLM judge rates explanation quality, which a deterministic check can't | Not in CI; needs an LLM key. A second opinion, not ground truth. |
| Promptfoo config (`services/eval-engine/app/promptfoo`) | Probes the LangGraph API for prompt injection and excessive agency | Config validates; no red-team pass run |
| Lint, tests, console build, `terraform validate` | Catches broken builds | In CI |

## Notes on the Cortex Agents SDK (v0.0.3, preview)

Observed while building this, not general claims:

- **Setup has real friction.** A token, a network policy (Snowflake refuses the token without
  one), a role with Cortex access, and grants on the warehouse, schema and procedure. Each
  missing piece gave a different error.
- **Tools are called with named arguments.** Snowpark names parameters `arg1, arg2` by default,
  so calls failed until the procedures were registered with `preserve_parameter_names=True`.
- **`instructions` must be an object** (`orchestration`, `response`). A string gives "invalid
  payload" without naming the field.
- **Access errors appear at run time.** The agent accepted tools it couldn't reach, then
  reported the failed calls in its answer. It said so honestly instead of inventing numbers.
- **The docs and the SDK disagree.** The getting-started guide uses `client.agent.stream`, but
  0.0.3 only has `conversations` and `feedback`. The SDK source was the reliable reference.
- **Tool output is size-limited** (a `truncated` flag), another reason not to return raw rows.
- **Wording varies, numbers don't**, because the metrics come from a deterministic procedure.
- **Not verified:** cost per run, concurrency, and client-side tools.

## Layout

| Path | What |
|---|---|
| `packages/agentevalos-sdk` | Shared code: schemas, tracing, MCP client, Cortex agent runner, custom evals |
| `services/agent-orchestrator` | FastAPI service with both agents |
| `services/eval-engine` | Scores predictions for the LangGraph path; owns the stored procedures |
| `scripts` | Seeding and the live eval runner |
| `console` | Next.js page for runs and leaderboards |
| `infra` | Terraform (Snowflake objects) and Kubernetes manifests; validated, never deployed |

## Known limits

- The data is randomly generated.
- The Cortex SDK is pre-1.0 and its API may change.
- The impact-score weights exist in two places; `metric_parity` guards against drift.
- Terraform and Kubernetes pass validation but haven't been applied to real infrastructure.

## License

Apache-2.0
