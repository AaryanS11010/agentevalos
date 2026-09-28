"""Streamlit-in-Snowflake UI for the AgentEvalOS Native App. Lets a consumer, entirely
within their own Snowflake account, pick an industry + dataset + candidate models,
trigger a benchmark run, and see the resulting impact-score leaderboard — no data or
predictions ever leave the account.
"""

import pandas as pd
import streamlit as st
from snowflake.snowpark.context import get_active_session

session = get_active_session()

st.set_page_config(page_title="AgentEvalOS — Industry Model Leaderboard", layout="wide")
st.title("AgentEvalOS — Which model is most impactful for your industry?")

industry = st.selectbox("Industry", ["finance", "healthcare"])
dataset_ref = st.text_input("Dataset (fully-qualified table)", value=f"{industry.upper()}.BENCHMARK_DATASET")
candidate_models = st.multiselect(
    "Candidate foundational tabular models",
    ["xgboost", "catboost", "lightgbm", "tabpfn", "logistic_regression"],
    default=["xgboost", "catboost"],
)

if st.button("Run benchmark", type="primary"):
    progress = st.progress(0.0)
    for i, model_name in enumerate(candidate_models):
        session.call("core.run_industry_eval", industry, model_name, dataset_ref)
        progress.progress((i + 1) / len(candidate_models))
    st.success(f"Benchmarked {len(candidate_models)} model(s) against {dataset_ref}")

st.subheader(f"Leaderboard — {industry}")
rows = session.call("core.rank_industry_models", industry).collect()
if rows:
    df = pd.DataFrame([r.as_dict() for r in rows])
    st.dataframe(df, use_container_width=True)
    st.bar_chart(df.set_index("MODEL_NAME")["IMPACT_SCORE"])
else:
    st.info("No benchmark runs yet for this industry — run one above.")
