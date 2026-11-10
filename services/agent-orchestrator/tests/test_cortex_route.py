from agentevalos_sdk.cortex_agent import AgentRun, ToolCall
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes_cortex
from app.db.models import AgentRunRow, Base, ToolCallRow
from app.db.session import get_db

OUTPUT = {"model_name": "xgboost", "impact_score": 0.9677, "fairness_ok": True}


def _client(monkeypatch, run_fn):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(routes_cortex.router)
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(routes_cortex, "run_cortex_agent", run_fn)
    return TestClient(app), Session


def test_cortex_run_is_saved_with_its_tool_calls(monkeypatch):
    def fake_run(question, industry, settings=None):
        call = ToolCall("benchmark_model", {"model_name": "xgboost"}, output=OUTPUT)
        return AgentRun(question, "Best is xgboost.\nRECOMMENDED: xgboost", [call], seconds=1.5)

    client, Session = _client(monkeypatch, fake_run)
    body = client.post("/cortex/runs", json={"industry": "finance"}).json()

    assert body["status"] == "succeeded"
    assert body["output"]["recommended"] == "xgboost"
    with Session() as db:
        assert db.query(AgentRunRow).one().agent_name == "cortex-agent"
        assert db.query(ToolCallRow).one().server_name == "snowflake-cortex"


def test_cortex_run_failure_is_saved_not_raised(monkeypatch):
    def broken_run(question, industry, settings=None):
        raise RuntimeError("SNOWFLAKE_PAT is not set in .env")

    client, _ = _client(monkeypatch, broken_run)
    body = client.post("/cortex/runs", json={"industry": "healthcare"}).json()

    assert body["status"] == "failed"
    assert "SNOWFLAKE_PAT" in body["output"]["error"]


def test_unknown_industry_is_rejected(monkeypatch):
    client, _ = _client(monkeypatch, lambda *a, **k: None)
    assert client.post("/cortex/runs", json={"industry": "retail"}).status_code == 422
