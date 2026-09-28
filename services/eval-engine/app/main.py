from __future__ import annotations

from agentevalos_sdk.otel_setup import instrument_fastapi
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_health, routes_leaderboard, routes_redteam
from app.config import settings

app = FastAPI(title="AgentEvalOS - Eval Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

instrument_fastapi(app, settings.service_name)

app.include_router(routes_health.router)
app.include_router(routes_leaderboard.router)
app.include_router(routes_redteam.router)
