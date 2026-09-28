# Turns raw model predictions into a ranked leaderboard.
#
# For each model: run it through the industry evaluator to get metrics (AUROC,
# calibration, fairness), then combine those into one "impact_score" so models
# can be ranked against each other.
from __future__ import annotations

from typing import Any

import numpy as np
from agentevalos_sdk.schemas import IndustryDomain, ModelLeaderboardEntry

from app.evaluators.finance.credit_risk import CreditRiskEvaluator
from app.evaluators.healthcare.clinical_risk import ClinicalRiskEvaluator

EVALUATORS_BY_INDUSTRY = {
    IndustryDomain.FINANCE: CreditRiskEvaluator(),
    IndustryDomain.HEALTHCARE: ClinicalRiskEvaluator(),
}

# How much each factor counts toward the final impact_score, per industry.
INDUSTRY_WEIGHTS = {
    IndustryDomain.FINANCE: {"discrimination": 0.5, "calibration": 0.2, "fairness": 0.3},
    IndustryDomain.HEALTHCARE: {"discrimination": 0.35, "calibration": 0.35, "fairness": 0.3},
}


def _metric_value(metrics: list, name: str, default: float = 0.0) -> float:
    for m in metrics:
        if m.name == name:
            return m.value
    return default


def compute_impact_score(industry: IndustryDomain, metrics: list) -> float:
    weights = INDUSTRY_WEIGHTS[industry]

    discrimination = _metric_value(metrics, "auroc", default=0.5)

    calibration_metric = _metric_value(metrics, "expected_calibration_error", default=None)
    if calibration_metric is None:
        calibration_metric = _metric_value(metrics, "brier_score", default=0.25)
    calibration = max(0.0, 1 - calibration_metric)

    fairness_gap = _metric_value(
        metrics, "demographic_parity_gap", default=None
    ) or _metric_value(metrics, "subgroup_fairness_gap", default=0.0)
    fairness = max(0.0, 1 - fairness_gap)

    score = (
        weights["discrimination"] * discrimination
        + weights["calibration"] * calibration
        + weights["fairness"] * fairness
    )
    return round(float(np.clip(score, 0.0, 1.0)), 4)


def score_benchmark_results(
    industry: IndustryDomain, dataset_ref: str, results: list[dict[str, Any]]
) -> list[ModelLeaderboardEntry]:
    """`results` is a list of {"model_name", "y_true", "y_pred", "y_score", ...}
    dicts, one per model, as returned by the Snowflake tool call.
    """
    evaluator = EVALUATORS_BY_INDUSTRY[industry]

    leaderboard: list[ModelLeaderboardEntry] = []
    for r in results:
        y_true = np.array(r["y_true"])
        y_pred = np.array(r["y_pred"])
        y_score = np.array(r["y_score"]) if r.get("y_score") is not None else None
        sensitive = np.array(r["sensitive_features"]) if r.get("sensitive_features") else None

        eval_result = evaluator.evaluate(
            model_name=r["model_name"],
            dataset_ref=dataset_ref,
            y_true=y_true,
            y_pred=y_pred,
            y_score=y_score,
            sensitive_features=sensitive,
        )
        impact = compute_impact_score(industry, eval_result.metrics)

        leaderboard.append(
            ModelLeaderboardEntry(
                industry=industry,
                model_name=r["model_name"],
                dataset_ref=dataset_ref,
                primary_metric_name="auroc",
                primary_metric_value=_metric_value(eval_result.metrics, "auroc"),
                calibration_error=_metric_value(
                    eval_result.metrics, "expected_calibration_error", default=None
                ),
                fairness_gap=_metric_value(
                    eval_result.metrics, "demographic_parity_gap", default=None
                )
                or _metric_value(eval_result.metrics, "subgroup_fairness_gap", default=None),
                latency_ms_p50=r.get("latency_ms"),
                impact_score=impact,
            )
        )

    leaderboard.sort(key=lambda e: e.impact_score, reverse=True)
    return leaderboard
