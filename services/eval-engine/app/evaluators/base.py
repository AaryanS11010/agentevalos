# Base class for a rule-based evaluator that scores model predictions.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from agentevalos_sdk.schemas import EvalMetric, EvalResult, IndustryDomain


class Evaluator(ABC):
    industry: IndustryDomain
    name: str

    @abstractmethod
    def compute_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_score: np.ndarray | None = None,
        sensitive_features: np.ndarray | None = None,
        extra: dict[str, Any] | None = None,
    ) -> list[EvalMetric]:
        raise NotImplementedError

    def evaluate(
        self,
        model_name: str,
        dataset_ref: str,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_score: np.ndarray | None = None,
        sensitive_features: np.ndarray | None = None,
        extra: dict[str, Any] | None = None,
    ) -> EvalResult:
        metrics = self.compute_metrics(y_true, y_pred, y_score, sensitive_features, extra)
        return EvalResult(
            industry=self.industry,
            evaluator=self.name,
            model_name=model_name,
            dataset_ref=dataset_ref,
            metrics=metrics,
        )


def brier_score(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Mean squared error between predicted probability and the actual outcome."""
    return float(np.mean((y_score - y_true) ** 2))


def ks_statistic(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Kolmogorov-Smirnov statistic, common in credit-risk model checks."""
    order = np.argsort(y_score)
    y_true_sorted = y_true[order]
    n_pos = y_true_sorted.sum()
    n_neg = len(y_true_sorted) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.0
    cum_pos = np.cumsum(y_true_sorted) / n_pos
    cum_neg = np.cumsum(1 - y_true_sorted) / n_neg
    return float(np.max(np.abs(cum_pos - cum_neg)))


def demographic_parity_gap(y_pred: np.ndarray, sensitive_features: np.ndarray) -> float:
    """Biggest difference in positive-prediction rate between groups."""
    groups = np.unique(sensitive_features)
    rates = [y_pred[sensitive_features == g].mean() for g in groups]
    return float(max(rates) - min(rates)) if len(rates) > 1 else 0.0
