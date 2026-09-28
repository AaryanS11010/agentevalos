"""Endpoints backing the agent-orchestrator's LangGraph `score_with_eval_engine` node,
plus read endpoints the reviewer console uses to render the industry leaderboards.
"""

from __future__ import annotations

from typing import Any

from agentevalos_sdk.schemas import IndustryDomain
from fastapi import APIRouter
from pydantic import BaseModel

from app.evaluators.tabular_model_bench import score_benchmark_results
from app.snowflake.client import read_leaderboard, write_leaderboard

router = APIRouter(prefix="/benchmarks/industry", tags=["benchmarks"])


class ScoreRequest(BaseModel):
    industry: IndustryDomain
    dataset_ref: str
    results: list[dict[str, Any]]


@router.post("/score")
def score(req: ScoreRequest) -> dict:
    leaderboard = score_benchmark_results(req.industry, req.dataset_ref, req.results)
    try:
        write_leaderboard(leaderboard)
    except Exception:
        # Snowflake may not be configured yet in local/dev scaffolding — scoring should
        # still succeed so the LangGraph run can complete.
        pass
    return {"leaderboard": [e.model_dump(mode="json") for e in leaderboard]}


@router.get("/{industry}/leaderboard")
def get_leaderboard(industry: str, limit: int = 25) -> dict:
    return {"industry": industry, "entries": read_leaderboard(industry, limit)}
