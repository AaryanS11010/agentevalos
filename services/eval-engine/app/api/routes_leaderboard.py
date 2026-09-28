# POST /score scores raw predictions. GET /leaderboard reads results back from Snowflake.
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
        # don't fail the whole request just because the Snowflake write failed
        pass
    return {"leaderboard": [e.model_dump(mode="json") for e in leaderboard]}


@router.get("/{industry}/leaderboard")
def get_leaderboard(industry: str, limit: int = 25) -> dict:
    return {"industry": industry, "entries": read_leaderboard(industry, limit)}
