# Healthcare dataset

`scripts/seed_snowflake.py` creates a fake dataset in `AGENTEVALOS.HEALTHCARE.BENCHMARK_DATASET`
and trains the models against it. A real dataset for this would be something like the
[Diabetes 130-US hospitals dataset](https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008)
(label = readmitted within 30 days).

Expected columns:

| column | notes |
|---|---|
| `LABEL` | 0 or 1, the thing being predicted |
| any other numeric column | treated as a model input |
| `SENSITIVE_GROUP` | optional, used for the fairness metric |

Any real patient data would need to be de-identified before it goes anywhere near
this project.
