# Keeps one MCP connection open for the whole app, set up when FastAPI starts.
from __future__ import annotations

from pathlib import Path

from agentevalos_sdk.mcp_client import MCPToolRegistry, load_server_configs

from app.config import settings

_registry: MCPToolRegistry | None = None
_SERVICE_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _SERVICE_DIR.parents[1]


def _config_path() -> str:
    # the path in .env is relative to the repo root, so try a few bases
    path = Path(settings.mcp_config_path)
    for base in (Path.cwd(), _REPO_ROOT, _SERVICE_DIR):
        if (base / path).exists():
            return str(base / path)
    return str(path)


async def init_registry() -> MCPToolRegistry:
    global _registry
    configs = load_server_configs(_config_path())
    _registry = MCPToolRegistry(configs)
    await _registry.__aenter__()
    return _registry


async def close_registry() -> None:
    if _registry is not None:
        await _registry.__aexit__(None, None, None)


async def get_registry() -> MCPToolRegistry:
    if _registry is None:
        raise RuntimeError("call init_registry() first")
    return _registry
