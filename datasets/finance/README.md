# Finance dataset

`scripts/seed_snowflake.py` creates a fake dataset in `AGENTEVALOS.FINANCE.BENCHMARK_DATASET`
and trains the models against it. A real dataset for this would be something like
[Lending Club loan data](https://www.kaggle.com/datasets/wordsforthewise/lending-club)
(label = defaulted on the loan or not).

Expected columns:

| column | notes |
|---|---|
| `LABEL` | 0 or 1, the thing being predicted |
| any other numeric column | treated as a model input |
| `SENSITIVE_GROUP` | optional, used for the fairness metric |
