# Shared data models used by both services.
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class IndustryDomain(str, Enum):
    FINANCE = "finance"
    HEALTHCARE = "healthcare"


class EvalMetric(BaseModel):
    name: str
    value: float
    threshold: float | None = None
    passed: bool | None = None


class EvalResult(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    industry: IndustryDomain
    evaluator: str
    model_name: str | None = None
    metrics: list[EvalMetric]
    dataset_ref: str | None = None


class RedTeamFinding(BaseModel):
    probe: str
    category: str
    severity: str
    prompt: str
    response: str
    flagged: bool
    rationale: str | None = None


class ModelLeaderboardEntry(BaseModel):
    """One row of the model leaderboard, written to and read from Snowflake."""

    industry: IndustryDomain
    model_name: str
    dataset_ref: str
    primary_metric_name: str
    primary_metric_value: float
    calibration_error: float | None = None
    fairness_gap: float | None = None
    latency_ms_p50: float | None = None
    impact_score: float
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
