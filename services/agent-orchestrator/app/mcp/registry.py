"""Process-wide MCP tool registry. Connected once at FastAPI startup, reused by every
LangGraph run (see app/main.py lifespan and app/graph/nodes.py).
"""

from __future__ import annotations

from agentevalos_sdk.mcp_client import MCPToolRegistry, load_server_configs

from app.config import settings

_registry: MCPToolRegistry | None = None


async def init_registry() -> MCPToolRegistry:
    global _registry
    configs = load_server_configs(settings.mcp_config_path)
    _registry = MCPToolRegistry(configs)
    await _registry.__aenter__()
    return _registry


async def close_registry() -> None:
    if _registry is not None:
        await _registry.__aexit__(None, None, None)


async def get_registry() -> MCPToolRegistry:
    if _registry is None:
        raise RuntimeError("MCP registry not initialized — call init_registry() at app startup")
    return _registry
