# Scores a model on credit risk (predicting default): how well it separates
# good vs. bad borrowers, how calibrated it is, and whether it's fair across groups.
from __future__ import annotations

from typing import Any

import numpy as np
from agentevalos_sdk.schemas import EvalMetric, IndustryDomain
from sklearn.metrics import roc_auc_score

from app.evaluators.base import (
    Evaluator,
    brier_score,
    demographic_parity_gap,
    ks_statistic,
)


class CreditRiskEvaluator(Evaluator):
    industry = IndustryDomain.FINANCE
    name = "credit_risk"

    AUROC_THRESHOLD = 0.70
    KS_THRESHOLD = 0.30
    FAIRNESS_GAP_THRESHOLD = 0.10

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
        ks = ks_statistic(y_true, y_score)
        brier = brier_score(y_true, y_score)

        metrics = [
            EvalMetric(name="auroc", value=auroc, threshold=self.AUROC_THRESHOLD, passed=auroc >= self.AUROC_THRESHOLD),
            EvalMetric(name="ks_statistic", value=ks, threshold=self.KS_THRESHOLD, passed=ks >= self.KS_THRESHOLD),
            EvalMetric(name="brier_score", value=brier, threshold=0.25, passed=brier <= 0.25),
        ]

        if sensitive_features is not None:
            gap = demographic_parity_gap(y_pred, sensitive_features)
            metrics.append(
                EvalMetric(
                    name="demographic_parity_gap",
                    value=gap,
                    threshold=self.FAIRNESS_GAP_THRESHOLD,
                    passed=gap <= self.FAIRNESS_GAP_THRESHOLD,
                )
            )
        return metrics
