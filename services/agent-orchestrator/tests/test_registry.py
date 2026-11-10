from pathlib import Path

from app.config import settings
from app.mcp import registry


def test_config_path_from_env_resolves_from_any_folder(monkeypatch, tmp_path):
    # .env uses a repo-root-relative path; the service is usually started from elsewhere
    monkeypatch.setattr(settings, "mcp_config_path", "./services/agent-orchestrator/mcp_servers.yaml")
    monkeypatch.chdir(tmp_path)
    assert Path(registry._config_path()).is_file()
