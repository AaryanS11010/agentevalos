# Eval methodology

## Why not just accuracy

Regulated tabular workloads are judged by model-risk-management (finance) and
clinical-governance (healthcare) reviewers on three axes, not one:

1. **Discrimination** — can the model separate positive/negative cases at all
   (AUROC, KS-statistic, AUPRC for imbalanced fraud data)?
2. **Calibration** — do predicted probabilities mean what they say (Brier score,
   expected calibration error)? Critical for clinical risk scores that drive
   real decisions, and for credit models under SR 11-7 style review.
3. **Fairness** — does the model treat protected groups comparably (demographic
   parity gap, subgroup fairness gap)? A model with great AUROC and a large fairness
   gap is not "impactful," it's a liability.

`impact_score` in
[`app/evaluators/tabular_model_bench.py`](../services/eval-engine/app/evaluators/tabular_model_bench.py)
is a transparent, per-industry weighted blend of these three axes
(`INDUSTRY_WEIGHTS`) — not a black-box score. Finance weights fairness slightly
higher than healthcare weights calibration; tune both per your own risk policy.

## Industry evaluators

| Evaluator | Industry | Use case | Key metrics |
|---|---|---|---|
| [`CreditRiskEvaluator`](../services/eval-engine/app/evaluators/finance/credit_risk.py) | Finance | Default prediction | AUROC, KS-statistic, Brier, demographic parity gap |
| [`FraudDetectionEvaluator`](../services/eval-engine/app/evaluators/finance/fraud_detection.py) | Finance | Transaction fraud (imbalanced) | precision@k, recall at fixed FPR budget |
| [`ClinicalRiskEvaluator`](../services/eval-engine/app/evaluators/healthcare/clinical_risk.py) | Healthcare | Sepsis/mortality risk scores | AUROC, expected calibration error, subgroup fairness gap |
| [`ReadmissionEvaluator`](../services/eval-engine/app/evaluators/healthcare/readmission.py) | Healthcare | 30-day readmission | AUROC, AUPRC, calibration |

Add a new industry evaluator by subclassing
[`Evaluator`](../services/eval-engine/app/evaluators/base.py) and registering it in
`EVALUATORS_BY_INDUSTRY` in `tabular_model_bench.py`.

## LLM-judge evals (DeepEval)

`app/deepeval_suites/agent_regression_suite.py` checks the agent's *natural-language
explanations* of leaderboard results — not the models themselves — for faithfulness
to the actual metric values it was given (`FaithfulnessMetric`) and domain relevance
(`GEval`). Run as a normal pytest suite; wire into CI as a blocking gate once you have
enough test cases to trust the signal.

## Red-teaming (Promptfoo)

[`app/promptfoo/promptfooconfig.yaml`](../services/eval-engine/app/promptfoo/promptfooconfig.yaml)
defines the agent's threat model (must not exfiltrate PII, run arbitrary SQL outside
its scoped MCP tools, or reveal other tenants' data) and the plugins/strategies
(`pii`, `sql-injection`, `excessive-agency`, `jailbreak`, `prompt-injection`) used to
probe it. `.github/workflows/ci.yml`'s `redteam-gate` job runs this on every PR against
a staging `agent-orchestrator` deployment.

## Roadmap

- [ ] Fairlearn integration for richer fairness metrics (equalized odds, calibration
      within groups) beyond the current demographic-parity-gap approximation.
- [ ] Confidence intervals on leaderboard entries (bootstrap over the eval dataset).
- [ ] Promptfoo `redteam` (not just `eval`) wired into CI against a real staging
      target, gating merges on `flagged` count.
- [ ] Read endpoint for eval history (`GET /evals`) to back the console's Evals page.
