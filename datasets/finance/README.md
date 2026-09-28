# Finance benchmark datasets

`scripts/seed_snowflake.py` loads a small synthetic dataset into
`AGENTEVALOS.FINANCE.BENCHMARK_DATASET` (feature columns, `LABEL`, `SENSITIVE_GROUP`)
and trains + stages baseline models so the credit-risk evaluator has something to run
against out of the box. For a real benchmark, replace it with:

- **Credit risk**: [Lending Club loan data](https://www.kaggle.com/datasets/wordsforthewise/lending-club) or [Give Me Some Credit](https://www.kaggle.com/c/GiveMeSomeCredit) (label = default within N months).
- **Fraud detection**: [IEEE-CIS Fraud Detection](https://www.kaggle.com/c/ieee-fraud-detection) or [Kaggle Credit Card Fraud](https://www.kaggle.com/mlg-ulb/creditcardfraud) (heavily imbalanced — use with `FraudDetectionEvaluator`, not `CreditRiskEvaluator`).

Expected schema for anything fed into `CreditRiskEvaluator`/`FraudDetectionEvaluator`
via `app/snowflake/udf_scoring.py`
(see [`services/eval-engine/app/evaluators/finance`](../../services/eval-engine/app/evaluators/finance)):

| column | type | notes |
|---|---|---|
| `LABEL` | int (0/1) | ground truth |
| any other numeric column | float/int | treated as a model input feature |
| `SENSITIVE_GROUP` | int/categorical | optional, excluded from features, drives the fairness-gap metric |

`PRED_SCORE` is no longer part of the dataset contract — the scoring proc now loads
the candidate model (a joblib-staged, scikit-learn-API classifier at
`@AGENTEVALOS.EVALS.MODEL_STAGE/finance_{model_name}.joblib`) and scores the feature
columns itself. To add a new candidate model, train it against this schema and stage
it under that naming convention (see `scripts/seed_snowflake.py` for an example).
