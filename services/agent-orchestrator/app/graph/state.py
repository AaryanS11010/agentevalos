"""LangGraph state definition for the industry-benchmarking agent.

The graph plans which tabular models + datasets to evaluate for a given industry,
calls the Snowflake MCP tools to run the benchmark, hands results to eval-engine for
scoring, and loops until either a confidence threshold is hit or max_iterations is
reached — that loop is what makes this a durable, stateful agent rather than a single
prompt-response call.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict
from uuid import UUID

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    run_id: UUID
    industry: str
    objective: str
    messages: Annotated[list, add_messages]

    candidate_models: list[str]
    dataset_ref: str | None

    tool_calls: list[dict[str, Any]]
    benchmark_results: list[dict[str, Any]]
    eval_results: list[dict[str, Any]]

    iteration: int
    max_iterations: int
    done: bool
    final_leaderboard: list[dict[str, Any]] | None
