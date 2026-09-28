"""30-day readmission risk evaluator. This is the canonical "foundational tabular model
benchmark" dataset (mirrors the UCI Diabetes 130-US hospitals readmission task) used to
compare gradient-boosted trees against newer foundation models like TabPFN.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from agentevalos_sdk.schemas import EvalMetric, IndustryDomain
from sklearn.metrics import average_precision_score, roc_auc_score

from app.evaluators.base import Evaluator, brier_score
from app.evaluators.healthcare.clinical_risk import expected_calibration_error


class ReadmissionEvaluator(Evaluator):
    industry = IndustryDomain.HEALTHCARE
    name = "readmission_risk"

    AUROC_THRESHOLD = 0.68
    AUPRC_THRESHOLD = 0.35

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
        auprc = float(average_precision_score(y_true, y_score))
        ece = expected_calibration_error(y_true, y_score)
        brier = brier_score(y_true, y_score)

        return [
            EvalMetric(name="auroc", value=auroc, threshold=self.AUROC_THRESHOLD, passed=auroc >= self.AUROC_THRESHOLD),
            EvalMetric(name="auprc", value=auprc, threshold=self.AUPRC_THRESHOLD, passed=auprc >= self.AUPRC_THRESHOLD),
            EvalMetric(name="expected_calibration_error", value=ece),
            EvalMetric(name="brier_score", value=brier),
        ]
