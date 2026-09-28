# The 4 steps of the agent: plan what to test, run the benchmark, score it,
# then decide whether to stop or go again.
from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.config import settings
from app.graph.state import AgentState
from app.mcp.registry import get_registry

# Models to try for each industry. Has to match what scripts/seed_snowflake.py
# trained and staged in Snowflake.
MODEL_CANDIDATES = {
    "finance": ["xgboost", "lightgbm", "logistic_regression"],
    "healthcare": ["xgboost", "lightgbm", "logistic_regression"],
}


def plan(state: AgentState) -> dict[str, Any]:
    """Pick which models to benchmark for this industry."""
    industry = state.get("industry", "finance")
    candidates = MODEL_CANDIDATES.get(industry, MODEL_CANDIDATES["finance"])
    dataset_ref = f"{industry.upper()}.BENCHMARK_DATASET"

    return {
        "candidate_models": candidates,
        "dataset_ref": dataset_ref,
        "iteration": state.get("iteration", 0) + 1,
    }


async def run_benchmark(state: AgentState) -> dict[str, Any]:
    """Ask Snowflake (through MCP) to score each candidate model."""
    registry = await get_registry()

    results = []
    tool_calls = []
    for model_name in state["candidate_models"]:
        started = time.perf_counter()
        raw = await registry.call_tool(
            "snowflake.run_industry_eval",
            {
                "industry": state["industry"],
                "model_name": model_name,
                "dataset_ref": state["dataset_ref"],
            },
        )
        latency_ms = (time.perf_counter() - started) * 1000

        text = raw.content[0].text
        parsed = json.loads(text)

        tool_calls.append(
            {
                "tool_name": "run_industry_eval",
                "server_name": "snowflake",
                "arguments": {"model_name": model_name},
                "result": parsed,
                "latency_ms": latency_ms,
            }
        )
        results.append({"model_name": model_name, **parsed})

    return {"benchmark_results": results, "tool_calls": tool_calls}


async def score_with_eval_engine(state: AgentState) -> dict[str, Any]:
    """Send the raw predictions to eval-engine so it can score them."""
    async with httpx.AsyncClient(base_url=settings.eval_engine_url, timeout=60) as client:
        resp = await client.post(
            "/benchmarks/industry/score",
            json={
                "industry": state["industry"],
                "dataset_ref": state["dataset_ref"],
                "results": state["benchmark_results"],
            },
        )
        resp.raise_for_status()
        leaderboard = resp.json()["leaderboard"]

    return {"eval_results": leaderboard}


def should_continue(state: AgentState) -> str:
    """Stop once we've hit max_iterations or a model is already scoring well."""
    if state.get("iteration", 0) >= state.get("max_iterations", 1):
        return "finalize"

    scores = [r.get("impact_score", 0) for r in state.get("eval_results", [])]
    best = max(scores) if scores else 0
    if best >= 0.8:
        return "finalize"

    return "plan"


def finalize(state: AgentState) -> dict[str, Any]:
    """Sort the results best-to-worst and wrap up."""
    leaderboard = sorted(
        state.get("eval_results", []), key=lambda r: r.get("impact_score", 0), reverse=True
    )
    return {"final_leaderboard": leaderboard, "done": True}
