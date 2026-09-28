"""Shared data contracts between agent-orchestrator, eval-engine, the console, and the
Snowflake native app. Keeping these in one place means a schema change is a one-line
version bump everyone consumes, instead of three services drifting independently.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class IndustryDomain(str, Enum):
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    GENERIC = "generic"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EVALUATING = "evaluating"


class ToolCallRecord(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    run_id: uuid.UUID
    tool_name: str
    server_name: str
    arguments: dict
    result: dict | str | None = None
    latency_ms: float | None = None
    error: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)


class AgentRun(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    agent_name: str
    industry: IndustryDomain = IndustryDomain.GENERIC
    input: dict
    status: RunStatus = RunStatus.PENDING
    output: dict | None = None
    trace_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EvalMetric(BaseModel):
    name: str
    value: float
    threshold: float | None = None
    passed: bool | None = None
    details: dict | None = None


class EvalResult(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    run_id: uuid.UUID | None = None
    industry: IndustryDomain
    evaluator: str
    model_name: str | None = None
    metrics: list[EvalMetric]
    dataset_ref: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def passed(self) -> bool:
        return all(m.passed for m in self.metrics if m.passed is not None)


class RedTeamFinding(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    run_id: uuid.UUID | None = None
    probe: str
    category: str
    severity: str  # low | medium | high | critical
    prompt: str
    response: str
    flagged: bool
    rationale: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ModelLeaderboardEntry(BaseModel):
    """One row of the tabular-model impact leaderboard, written to Snowflake by
    eval-engine's tabular_model_bench and read by the console + native app."""

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
