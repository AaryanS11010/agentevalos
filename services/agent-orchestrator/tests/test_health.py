from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_health import router


def test_healthz_returns_ok():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "agent-orchestrator"}
