# Builds the LangGraph graph: plan -> run_benchmark -> score -> loop or finish.
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

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

    # Just keeping state in memory for now. Would need a Postgres checkpointer to
    # survive a restart, but that's more than this project needs right now.
    return graph.compile(checkpointer=MemorySaver())
