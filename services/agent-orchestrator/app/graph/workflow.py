"""Builds the durable, stateful LangGraph workflow for industry tabular-model
benchmarking. Uses a Postgres checkpointer so runs survive process restarts and can be
resumed/replayed — required for anything you'd call "production-quality AgentOps".
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.config import settings
from app.graph.nodes import (
    finalize,
    plan,
    run_benchmark,
    score_with_eval_engine,
    should_continue,
)
from app.graph.state import AgentState


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("plan", plan)
    graph.add_node("run_benchmark", run_benchmark)
    graph.add_node("score", score_with_eval_engine)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "run_benchmark")
    graph.add_edge("run_benchmark", "score")
    graph.add_conditional_edges("score", should_continue, {"plan": "plan", "finalize": "finalize"})
    graph.add_edge("finalize", END)

    checkpointer = _build_checkpointer()
    return graph.compile(checkpointer=checkpointer)


def _build_checkpointer():
    """Postgres-backed checkpointer so LangGraph state is durable across restarts.

    Falls back to an in-memory checkpointer if langgraph-checkpoint-postgres isn't
    installed yet, so `uvicorn app.main:app` still boots during early scaffolding.
    """
    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        saver_cm = PostgresSaver.from_conn_string(settings.database_url)
        saver = saver_cm.__enter__()
        saver.setup()
        return saver
    except Exception:
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()
