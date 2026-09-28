"""Handler for core.rank_industry_models — returns the top-ranked models for an
industry, backing the Streamlit leaderboard table.
"""

from __future__ import annotations

from snowflake.snowpark import Session
from snowflake.snowpark.functions import col


def handler(session: Session, industry: str):
    return (
        session.table("core.model_leaderboard")
        .filter(col("industry") == industry)
        .sort(col("impact_score").desc())
        .select("model_name", "impact_score", "primary_metric_value")
        .limit(25)
    )
