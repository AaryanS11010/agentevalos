# Runs the benchmarking agent on Snowflake Cortex Agents; its only tool is RUN_INDUSTRY_METRICS
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from .config import SharedSettings

MODEL_CANDIDATES = {
    "finance": ["xgboost", "lightgbm", "logistic_regression"],
    "healthcare": ["xgboost", "lightgbm", "logistic_regression"],
}


@dataclass
class ToolCall:
    name: str
    input: dict[str, Any]
    output: dict[str, Any] | None = None  # parsed JSON the procedure returned
    error: str | None = None  # set when the tool call failed
    truncated: bool = False  # Snowflake cut the output off because it was too big


@dataclass
class AgentRun:
    question: str
    final_text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def successful_outputs(self) -> list[dict[str, Any]]:
        return [c.output for c in self.tool_calls if c.output and not c.error]

    @property
    def recommended(self) -> str | None:
        """The model named on the 'RECOMMENDED: <model>' line the agent must end with."""
        for line in reversed(self.final_text.strip().splitlines()):
            if line.strip().upper().startswith("RECOMMENDED:"):
                value = line.split(":", 1)[1].strip().strip("*` ").lower()
                return None if value in ("none", "") else value
        return None


def build_agent_spec(industry: str, models: list[str], settings: SharedSettings) -> dict[str, Any]:
    dataset = f"{industry.upper()}.BENCHMARK_DATASET"
    procedure = f"{settings.snowflake_database}.{settings.snowflake_schema}.RUN_INDUSTRY_METRICS"
    return {
        "instructions": {
            "orchestration": (
                f"You benchmark machine learning models for the {industry} industry. "
                f"Call the benchmark_model tool exactly once for each of these models: {', '.join(models)}. "
                f"The only dataset you may use is {dataset}. If the user asks for any other dataset, "
                "do not call the tool for it; say it is out of scope."
            ),
            "response": (
                "Report each model's impact_score, auroc and fairness_gap exactly as the tool returned "
                "them, with no rounding and no numbers you calculated yourself. Rank the models by "
                "impact_score. Never recommend a model whose fairness_ok is false. "
                "End your answer with one final line in exactly this form: RECOMMENDED: <model_name> "
                "(or RECOMMENDED: none if no model qualifies)."
            ),
        },
        "tools": [
            {
                "tool_spec": {
                    "type": "generic",
                    "name": "benchmark_model",
                    "description": (
                        "Scores one model on a labeled dataset inside Snowflake and returns summary "
                        "metrics: auroc, calibration, fairness_gap, fairness_ok and impact_score."
                    ),
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "industry": {"type": "string", "description": "finance or healthcare"},
                            "model_name": {"type": "string"},
                            "dataset_ref": {"type": "string", "description": "e.g. FINANCE.BENCHMARK_DATASET"},
                        },
                        "required": ["industry", "model_name", "dataset_ref"],
                    },
                }
            }
        ],
        "tool_resources": {
            "benchmark_model": {
                "type": "procedure",
                "identifier": procedure,
                "execution_environment": {"type": "warehouse", "warehouse": settings.snowflake_warehouse},
            }
        },
    }


def _collect_tool_calls(events: list[dict[str, Any]]) -> list[ToolCall]:
    calls: dict[str, ToolCall] = {}
    order: list[str] = []
    for e in events:
        kind, tool_id = e.get("event"), e.get("tool_use_id")
        if kind == "response.tool_use" and tool_id:
            calls[tool_id] = ToolCall(name=e.get("name", ""), input=e.get("input") or {})
            order.append(tool_id)
        elif kind == "response.tool_result" and tool_id in calls:
            call = calls[tool_id]
            blocks = e.get("content") or []
            payload = (blocks[0].get("json") if blocks else None) or {}
            call.truncated = bool(payload.get("truncated"))
            result = payload.get("result")
            if e.get("status") != "success":
                call.error = str(result or payload)[:300]
            else:
                try:
                    call.output = json.loads(result) if isinstance(result, str) else result
                except json.JSONDecodeError:
                    call.error = f"tool returned non-JSON output: {str(result)[:120]}"
    return [calls[i] for i in order]


def run_cortex_agent(
    question: str,
    industry: str,
    models: list[str] | None = None,
    settings: SharedSettings | None = None,
) -> AgentRun:
    from cortex_agent_sdk import CortexAgentClient, PatAuth

    settings = settings or SharedSettings()
    if not settings.snowflake_pat:
        raise RuntimeError("SNOWFLAKE_PAT is not set in .env")
    models = models or MODEL_CANDIDATES[industry]

    client = CortexAgentClient(account=settings.snowflake_account.strip(), auth=PatAuth(settings.snowflake_pat.strip()))
    started = time.perf_counter()
    try:
        conversation = client.conversations.create(
            origin_application="agentevalos",
            agent={"type": "inline", "spec": build_agent_spec(industry, models, settings)},
        )
        turn = conversation.send(question)
        final_text = turn.result().text
        events = list(turn.events())
    finally:
        client.close()
    return AgentRun(
        question=question,
        final_text=final_text,
        tool_calls=_collect_tool_calls(events),
        seconds=round(time.perf_counter() - started, 1),
    )
