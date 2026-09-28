# Healthcare benchmark datasets

`scripts/seed_snowflake.py` loads a small synthetic dataset into
`AGENTEVALOS.HEALTHCARE.BENCHMARK_DATASET` (feature columns, `LABEL`,
`SENSITIVE_GROUP`) and trains + stages baseline models so the clinical-risk/
readmission evaluators have something to run against out of the box. For a real
benchmark, replace it with:

- **Readmission risk**: [Diabetes 130-US hospitals dataset](https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008) — the canonical tabular benchmark for this task, label = readmitted within 30 days.
- **Clinical risk (mortality/sepsis)**: [MIMIC-IV](https://physionet.org/content/mimiciv/) (requires credentialed access + a data use agreement — do not commit any MIMIC data to this repo).

All data must be de-identified per HIPAA Safe Harbor (or equivalent) before it is
loaded into any AgentEvalOS dataset table — this scaffold assumes datasets are already
compliant by the time they reach Snowflake; it does not perform de-identification.

Expected schema (see
[`services/eval-engine/app/evaluators/healthcare`](../../services/eval-engine/app/evaluators/healthcare)):

| column | type | notes |
|---|---|---|
| `LABEL` | int (0/1) | ground truth outcome |
| any other numeric column | float/int | treated as a model input feature |
| `SENSITIVE_GROUP` | int/categorical | optional, excluded from features, drives the subgroup-fairness-gap metric |

`PRED_SCORE` is no longer part of the dataset contract — the scoring proc loads the
candidate model (a joblib-staged, scikit-learn-API classifier at
`@AGENTEVALOS.EVALS.MODEL_STAGE/healthcare_{model_name}.joblib`) and scores the
feature columns itself. See `scripts/seed_snowflake.py` for how the demo models are
trained and staged.
