from app.graph.nodes import MODEL_CANDIDATES, plan, should_continue


def test_plan_picks_finance_models():
    state = {"industry": "finance", "iteration": 0}
    result = plan(state)
    assert result["candidate_models"] == MODEL_CANDIDATES["finance"]
    assert result["dataset_ref"] == "FINANCE.BENCHMARK_DATASET"
    assert result["iteration"] == 1


def test_should_continue_stops_at_max_iterations():
    state = {"iteration": 3, "max_iterations": 3, "eval_results": [{"impact_score": 0.2}]}
    assert should_continue(state) == "finalize"


def test_should_continue_stops_when_score_is_high():
    state = {"iteration": 1, "max_iterations": 5, "eval_results": [{"impact_score": 0.85}]}
    assert should_continue(state) == "finalize"


def test_should_continue_keeps_going_when_score_is_low():
    state = {"iteration": 1, "max_iterations": 5, "eval_results": [{"impact_score": 0.4}]}
    assert should_continue(state) == "plan"
