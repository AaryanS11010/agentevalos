import numpy as np
from agentevalos_sdk.schemas import IndustryDomain
from app.evaluators.finance.credit_risk import CreditRiskEvaluator
from app.evaluators.tabular_model_bench import (
    compute_impact_score,
    score_benchmark_results,
)


def _synthetic_result(model_name: str, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    n = 500
    y_true = rng.integers(0, 2, n)
    y_score = np.clip(y_true * 0.6 + rng.normal(0.3, 0.2, n), 0, 1)
    y_pred = (y_score >= 0.5).astype(int)
    sensitive = rng.integers(0, 2, n)
    return {
        "model_name": model_name,
        "y_true": y_true.tolist(),
        "y_pred": y_pred.tolist(),
        "y_score": y_score.tolist(),
        "sensitive_features": sensitive.tolist(),
        "latency_ms": 12.3,
    }


def test_credit_risk_evaluator_returns_expected_metrics():
    evaluator = CreditRiskEvaluator()
    result = _synthetic_result("xgboost", seed=1)
    eval_result = evaluator.evaluate(
        model_name="xgboost",
        dataset_ref="FINANCE.BENCHMARK_DATASET",
        y_true=np.array(result["y_true"]),
        y_pred=np.array(result["y_pred"]),
        y_score=np.array(result["y_score"]),
        sensitive_features=np.array(result["sensitive_features"]),
    )
    metric_names = {m.name for m in eval_result.metrics}
    assert {"auroc", "ks_statistic", "brier_score", "demographic_parity_gap"} <= metric_names


def test_leaderboard_is_ranked_descending_by_impact_score():
    results = [_synthetic_result(f"model_{i}", seed=i) for i in range(3)]
    leaderboard = score_benchmark_results(
        IndustryDomain.FINANCE, "FINANCE.BENCHMARK_DATASET", results
    )
    scores = [e.impact_score for e in leaderboard]
    assert scores == sorted(scores, reverse=True)


def test_compute_impact_score_is_bounded():
    from agentevalos_sdk.schemas import EvalMetric

    metrics = [
        EvalMetric(name="auroc", value=0.9),
        EvalMetric(name="expected_calibration_error", value=0.02),
        EvalMetric(name="demographic_parity_gap", value=0.01),
    ]
    score = compute_impact_score(IndustryDomain.FINANCE, metrics)
    assert 0.0 <= score <= 1.0
