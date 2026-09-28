"""Fraud-detection evaluator. Fraud datasets are heavily imbalanced, so AUROC alone is
misleading — precision@k and recall at a fixed low false-positive budget matter more
operationally (analysts can only review so many flagged transactions per day).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from agentevalos_sdk.schemas import EvalMetric, IndustryDomain

from app.evaluators.base import Evaluator


def precision_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int) -> float:
    top_k_idx = np.argsort(y_score)[-k:]
    return float(y_true[top_k_idx].sum() / k) if k > 0 else 0.0


def recall_at_fpr_budget(y_true: np.ndarray, y_score: np.ndarray, fpr_budget: float = 0.01) -> float:
    negatives = y_true == 0
    n_neg = negatives.sum()
    if n_neg == 0:
        return 0.0
    threshold_idx = int(n_neg * (1 - fpr_budget))
    neg_scores_sorted = np.sort(y_score[negatives])
    threshold = neg_scores_sorted[min(threshold_idx, n_neg - 1)]
    predicted_positive = y_score >= threshold
    positives = y_true == 1
    return float((predicted_positive & positives).sum() / max(positives.sum(), 1))


class FraudDetectionEvaluator(Evaluator):
    industry = IndustryDomain.FINANCE
    name = "fraud_detection"

    PRECISION_AT_100_THRESHOLD = 0.5
    RECALL_AT_1PCT_FPR_THRESHOLD = 0.6

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
        k = min(100, len(y_true))

        p_at_k = precision_at_k(y_true, y_score, k)
        recall_budget = recall_at_fpr_budget(y_true, y_score, fpr_budget=0.01)

        return [
            EvalMetric(
                name=f"precision_at_{k}",
                value=p_at_k,
                threshold=self.PRECISION_AT_100_THRESHOLD,
                passed=p_at_k >= self.PRECISION_AT_100_THRESHOLD,
            ),
            EvalMetric(
                name="recall_at_1pct_fpr",
                value=recall_budget,
                threshold=self.RECALL_AT_1PCT_FPR_THRESHOLD,
                passed=recall_budget >= self.RECALL_AT_1PCT_FPR_THRESHOLD,
            ),
        ]
