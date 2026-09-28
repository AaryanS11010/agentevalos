from __future__ import annotations

from contextlib import asynccontextmanager

from agentevalos_sdk.otel_setup import instrument_fastapi
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_health, routes_runs
from app.config import settings
from app.db.session import init_db
from app.mcp.registry import close_registry, init_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await init_registry()
    yield
    await close_registry()


app = FastAPI(title="AgentEvalOS — Agent Orchestrator", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

instrument_fastapi(app, settings.service_name)

app.include_router(routes_health.router)
app.include_router(routes_runs.router)
