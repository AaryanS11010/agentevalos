# POST /cortex/runs runs the same benchmark as POST /runs, but on Snowflake Cortex
# Agents instead of LangGraph. Runs are saved in the same Postgres tables.
from __future__ import annotations

import logging
import uuid
from typing import Any, Literal

from agentevalos_sdk.cortex_agent import run_cortex_agent
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AgentRunRow, ToolCallRow
from app.db.session import get_db

router = APIRouter(prefix="/cortex", tags=["cortex"])
logger = logging.getLogger(__name__)


class CortexRunRequest(BaseModel):
    industry: Literal["finance", "healthcare"] = "finance"
    question: str | None = None


class CortexRunResponse(BaseModel):
    id: uuid.UUID
    status: str
    industry: str
    output: dict[str, Any] | None = None


@router.post("/runs", response_model=CortexRunResponse)
def create_cortex_run(req: CortexRunRequest, db: Session = Depends(get_db)) -> CortexRunResponse:
    question = req.question or f"Which model is best for {req.industry}? Benchmark each candidate."
    run_row = AgentRunRow(
        agent_name="cortex-agent", industry=req.industry, status="running", input=req.model_dump()
    )
    db.add(run_row)
    db.commit()
    db.refresh(run_row)

    try:
        run = run_cortex_agent(question, req.industry, settings=settings)
        run_row.status = "succeeded"
        run_row.output = {
            "answer": run.final_text,
            "recommended": run.recommended,
            "metrics": run.successful_outputs,
            "seconds": run.seconds,
        }
        for call in run.tool_calls:
            db.add(
                ToolCallRow(
                    run_id=run_row.id,
                    tool_name=call.name,
                    server_name="snowflake-cortex",
                    arguments=call.input,
                    result=call.output if call.output else {"error": call.error},
                )
            )
    except Exception as exc:  # the run is saved as failed instead of returning a 500
        logger.exception("cortex run failed")
        run_row.status = "failed"
        run_row.output = {"error": str(exc)}

    db.commit()
    db.refresh(run_row)
    return CortexRunResponse(
        id=run_row.id, status=run_row.status, industry=run_row.industry, output=run_row.output
    )
