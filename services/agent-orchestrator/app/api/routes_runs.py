"""Endpoints for triggering and inspecting agent runs. POST /runs kicks off the
LangGraph industry-benchmarking workflow; GET endpoints read run/tool-call history
back from Postgres for the reviewer console.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import AgentRunRow, ToolCallRow
from app.db.session import get_db
from app.graph import build_graph

router = APIRouter(prefix="/runs", tags=["runs"])

_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


class CreateRunRequest(BaseModel):
    agent_name: str = "tabular-model-benchmark"
    industry: str = "finance"
    objective: str = "Rank foundational tabular models by industry impact"
    max_iterations: int = 3


class RunResponse(BaseModel):
    id: uuid.UUID
    status: str
    industry: str
    output: dict[str, Any] | None = None


@router.post("", response_model=RunResponse)
async def create_run(req: CreateRunRequest, db: Session = Depends(get_db)) -> RunResponse:
    run_row = AgentRunRow(
        agent_name=req.agent_name,
        industry=req.industry,
        status="running",
        input=req.model_dump(),
    )
    db.add(run_row)
    db.commit()
    db.refresh(run_row)

    graph = _get_graph()
    try:
        result = await graph.ainvoke(
            {
                "run_id": run_row.id,
                "industry": req.industry,
                "objective": req.objective,
                "iteration": 0,
                "max_iterations": req.max_iterations,
            },
            config={"configurable": {"thread_id": str(run_row.id)}},
        )
        run_row.status = "succeeded"
        run_row.output = {"final_leaderboard": result.get("final_leaderboard", [])}

        for call in result.get("tool_calls", []):
            db.add(ToolCallRow(run_id=run_row.id, **call))

    except Exception as exc:  # noqa: BLE001 - surfaced to caller, run marked failed
        run_row.status = "failed"
        run_row.output = {"error": str(exc)}

    db.commit()
    db.refresh(run_row)

    return RunResponse(
        id=run_row.id, status=run_row.status, industry=run_row.industry, output=run_row.output
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> RunResponse:
    run_row = db.get(AgentRunRow, run_id)
    if run_row is None:
        raise HTTPException(status_code=404, detail="run not found")
    return RunResponse(
        id=run_row.id, status=run_row.status, industry=run_row.industry, output=run_row.output
    )


@router.get("", response_model=list[RunResponse])
def list_runs(db: Session = Depends(get_db)) -> list[RunResponse]:
    rows = db.query(AgentRunRow).order_by(AgentRunRow.created_at.desc()).limit(100).all()
    return [
        RunResponse(id=r.id, status=r.status, industry=r.industry, output=r.output) for r in rows
    ]
