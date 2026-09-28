"""Clinical risk-score evaluator (e.g. sepsis risk, mortality risk). Calibration matters
even more here than in finance — a miscalibrated risk score directly changes clinical
decisions — so this evaluator weights calibration and subgroup fairness heavily and
intentionally does NOT report accuracy, which is a poor metric for skewed clinical
outcomes.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from agentevalos_sdk.schemas import EvalMetric, IndustryDomain
from sklearn.calibration import calibration_curve
from sklearn.metrics import roc_auc_score

from app.evaluators.base import Evaluator, brier_score, demographic_parity_gap


def expected_calibration_error(y_true: np.ndarray, y_score: np.ndarray, n_bins: int = 10) -> float:
    prob_true, prob_pred = calibration_curve(y_true, y_score, n_bins=n_bins, strategy="uniform")
    return float(np.mean(np.abs(prob_true - prob_pred)))


class ClinicalRiskEvaluator(Evaluator):
    industry = IndustryDomain.HEALTHCARE
    name = "clinical_risk"

    AUROC_THRESHOLD = 0.75
    ECE_THRESHOLD = 0.05
    FAIRNESS_GAP_THRESHOLD = 0.08

    def compute_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_score: np.ndarray | None = None,
        sensitive_features: np.ndarray | None = None,
        extra: dict[str, Any] | None = None,
    ) -> list[EvalMetric]:
        if y_score is None:
            y_score = y_pred.astype(float)

        auroc = float(roc_auc_score(y_true, y_score))
        ece = expected_calibration_error(y_true, y_score)
        brier = brier_score(y_true, y_score)

        metrics = [
            EvalMetric(name="auroc", value=auroc, threshold=self.AUROC_THRESHOLD, passed=auroc >= self.AUROC_THRESHOLD),
            EvalMetric(name="expected_calibration_error", value=ece, threshold=self.ECE_THRESHOLD, passed=ece <= self.ECE_THRESHOLD),
            EvalMetric(name="brier_score", value=brier),
        ]

        if sensitive_features is not None:
            gap = demographic_parity_gap(y_pred, sensitive_features)
            metrics.append(
                EvalMetric(
                    name="subgroup_fairness_gap",
                    value=gap,
                    threshold=self.FAIRNESS_GAP_THRESHOLD,
                    passed=gap <= self.FAIRNESS_GAP_THRESHOLD,
                )
            )
        return metrics
