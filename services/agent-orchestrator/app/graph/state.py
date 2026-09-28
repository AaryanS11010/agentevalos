# The state that gets passed between nodes in the graph.
from __future__ import annotations

from typing import Any, TypedDict
from uuid import UUID


class AgentState(TypedDict, total=False):
    run_id: UUID
    industry: str
    objective: str

    candidate_models: list[str]
    dataset_ref: str | None

    tool_calls: list[dict[str, Any]]
    benchmark_results: list[dict[str, Any]]
    eval_results: list[dict[str, Any]]

    iteration: int
    max_iterations: int
    done: bool
    final_leaderboard: list[dict[str, Any]] | None
