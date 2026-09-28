"""Node implementations for the industry-benchmarking LangGraph workflow.

    plan -> run_benchmark -> score -> should_continue -> {plan | finalize}

(see workflow.py for how these are wired into a StateGraph, and state.py for the
AgentState contract every node reads from / writes back into).

Each node is intentionally small and single-purpose so the graph in workflow.py stays
readable. Nodes that call out to MCP tools or the eval-engine are async; LangGraph
handles both sync and async node functions. Verified end to end against a real
Snowflake account and a live Phoenix instance — see docs/architecture.md.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
from opentelemetry import trace

from app.config import settings
from app.graph.state import AgentState
from app.mcp.registry import get_registry

tracer = trace.get_tracer("agent-orchestrator.graph")

#  Restricted to models the in-warehouse scoring proc can actually load: packages on
#  Snowflake's Anaconda channel, staged as a fit-once joblib artifact (see
#  app/snowflake/udf_scoring.py and scripts/seed_snowflake.py). `catboost` and
#  `tabpfn` are deliberately excluded here — see udf_scoring.py's module docstring —
#  and would need eval-engine's external (non-native-app) deployment path instead.
DEFAULT_MODEL_CANDIDATES = {
    "finance": ["xgboost", "lightgbm", "logistic_regression"],
    "healthcare": ["xgboost", "lightgbm", "logistic_regression"],
    "generic": ["xgboost", "logistic_regression"],
}


def plan(state: AgentState) -> dict[str, Any]:
    """Decide which foundational tabular models + Snowflake dataset to benchmark this
    iteration. Adaptive on repeat passes: drops any candidate that scored below a weak
    threshold last time round, so should_continue()'s loop-back actually converges on
    something better instead of re-running the same static list.
    """
    with tracer.start_as_current_span("plan") as span:
        industry = state.get("industry", "generic")
        span.set_attribute("openinference.span.kind", "CHAIN")
        span.set_attribute("industry", industry)

        candidates = DEFAULT_MODEL_CANDIDATES.get(industry, DEFAULT_MODEL_CANDIDATES["generic"])

        prior_results = state.get("eval_results") or []
        if prior_results:
            weak = {r["model_name"] for r in prior_results if r.get("impact_score", 0) < 0.3}
            trimmed = [c for c in candidates if c not in weak]
            candidates = trimmed or candidates  # never plan an empty run

        dataset_ref = f"{industry.upper()}.BENCHMARK_DATASET"
        return {
            "candidate_models": candidates,
            "dataset_ref": dataset_ref,
            "iteration": state.get("iteration", 0) + 1,
        }


async def run_benchmark(state: AgentState) -> dict[str, Any]:
    """Call the Snowflake MCP tool once per candidate model to score it against the
    dataset, and collect both the raw results and a tool-call trace for each. A
    per-model failure is captured and surfaced downstream rather than aborting the
    whole run — one bad model shouldn't block scoring the rest.
    """
    with tracer.start_as_current_span("run_benchmark") as span:
        span.set_attribute("openinference.span.kind", "TOOL")
        registry = await get_registry()

        results: list[dict[str, Any]] = []
        tool_calls: list[dict[str, Any]] = []
        for model_name in state["candidate_models"]:
            arguments = {
                "industry": state["industry"],
                "model_name": model_name,
                "dataset_ref": state["dataset_ref"],
            }
            started = time.perf_counter()
            error: str | None = None
            parsed: dict[str, Any] = {}
            try:
                raw = await registry.call_tool("snowflake.run_industry_eval", arguments)
                # MCP tool results come back as a list of content blocks; the
                # Snowflake tool server returns a single TextContent JSON string
                # (see app/mcp/snowflake_tools.py::call_tool).
                text = raw.content[0].text if hasattr(raw, "content") else raw[0].text
                parsed = json.loads(text)
            except Exception as exc:  # noqa: BLE001 - surfaced per-model, run continues
                error = str(exc)
            latency_ms = (time.perf_counter() - started) * 1000

            tool_calls.append(
                {
                    "tool_name": "run_industry_eval",
                    "server_name": "snowflake",
                    "arguments": {"model_name": model_name},
                    "result": parsed or None,
                    "latency_ms": latency_ms,
                    "error": error,
                }
            )
            results.append({"model_name": model_name, "error": error, **parsed})

        span.set_attribute("models_benchmarked", len(results))
        return {"benchmark_results": results, "tool_calls": tool_calls}


async def score_with_eval_engine(state: AgentState) -> dict[str, Any]:
    """Hand raw benchmark results to eval-engine for industry-specific scoring
    (calibration, fairness, impact score) and get back a ranked leaderboard.
    """
    with tracer.start_as_current_span("score_with_eval_engine") as span:
        span.set_attribute("openinference.span.kind", "CHAIN")
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

        span.set_attribute("leaderboard_size", len(leaderboard))
        return {"eval_results": leaderboard}


def should_continue(state: AgentState) -> str:
    """The agent's stopping decision: loop back to plan() and try a trimmed candidate
    set, or finalize. Stops once max_iterations is hit or the best impact_score this
    run has already cleared a high-confidence bar (0.8) — no point spending another
    round of Snowflake calls once a model is clearly good enough.
    """
    if state.get("iteration", 0) >= state.get("max_iterations", 1):
        return "finalize"
    top = max((r.get("impact_score", 0) for r in state.get("eval_results", [])), default=0)
    if top >= 0.8:
        return "finalize"
    return "plan"


def finalize(state: AgentState) -> dict[str, Any]:
    """Produce the run's final output: the eval_results, ranked best-impact-score-first."""
    with tracer.start_as_current_span("finalize") as span:
        leaderboard = sorted(
            state.get("eval_results", []), key=lambda r: r.get("impact_score", 0), reverse=True
        )
        span.set_attribute("openinference.span.kind", "CHAIN")
        return {"final_leaderboard": leaderboard, "done": True}
