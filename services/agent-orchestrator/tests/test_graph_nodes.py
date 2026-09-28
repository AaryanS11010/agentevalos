"""Spec for the graph nodes you implement in app/graph/nodes.py — see that file's
module docstring for the full contract each function must satisfy. plan() and
should_continue() are pure/sync so they're covered here; run_benchmark() and
score_with_eval_engine() do real I/O (MCP calls, an HTTP POST) so they're easiest to
verify by actually running the stack — see docs/architecture.md.
"""

from app.graph.nodes import DEFAULT_MODEL_CANDIDATES, plan, should_continue


def test_plan_selects_finance_candidates():
    state = {"industry": "finance", "iteration": 0}
    result = plan(state)
    assert result["candidate_models"] == DEFAULT_MODEL_CANDIDATES["finance"]
    assert result["dataset_ref"] == "FINANCE.BENCHMARK_DATASET"
    assert result["iteration"] == 1


def test_plan_defaults_to_generic_for_unknown_industry():
    state = {"industry": "retail", "iteration": 2}
    result = plan(state)
    assert result["candidate_models"] == DEFAULT_MODEL_CANDIDATES["generic"]


def test_should_continue_finalizes_at_max_iterations():
    state = {"iteration": 3, "max_iterations": 3, "eval_results": [{"impact_score": 0.2}]}
    assert should_continue(state) == "finalize"


def test_should_continue_finalizes_on_high_impact_score():
    state = {"iteration": 1, "max_iterations": 5, "eval_results": [{"impact_score": 0.85}]}
    assert should_continue(state) == "finalize"


def test_should_continue_loops_when_below_threshold_and_under_max_iterations():
    state = {"iteration": 1, "max_iterations": 5, "eval_results": [{"impact_score": 0.4}]}
    assert should_continue(state) == "plan"
