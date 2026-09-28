"""Thin async wrapper around the MCP python SDK for connecting agent-orchestrator's
LangGraph nodes to MCP tool servers (Snowflake data access, industry benchmark tools,
and any third-party MCP servers an enterprise wants to plug in).

Server definitions live in a YAML file (see services/agent-orchestrator/mcp_servers.yaml)
so new tool servers can be added without a code change.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str]
    env: dict[str, str] | None = None


def load_server_configs(path: str) -> list[MCPServerConfig]:
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return [MCPServerConfig(name=k, **v) for k, v in raw.get("servers", {}).items()]


class MCPToolRegistry:
    """Connects to every configured MCP server and exposes a flat call_tool() API.

    Usage:
        registry = MCPToolRegistry(load_server_configs(MCP_CONFIG_PATH))
        async with registry:
            tools = await registry.list_tools()
            result = await registry.call_tool("snowflake.run_industry_eval", {...})
    """

    def __init__(self, configs: list[MCPServerConfig]):
        self._configs = {c.name: c for c in configs}
        self._sessions: dict[str, ClientSession] = {}
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> "MCPToolRegistry":
        for cfg in self._configs.values():
            params = StdioServerParameters(command=cfg.command, args=cfg.args, env=cfg.env)
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self._sessions[cfg.name] = session
        return self

    async def __aexit__(self, *exc):
        await self._stack.aclose()

    async def list_tools(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for name, session in self._sessions.items():
            resp = await session.list_tools()
            out[name] = [t.name for t in resp.tools]
        return out

    async def call_tool(self, qualified_name: str, arguments: dict[str, Any]) -> Any:
        """qualified_name is "<server_name>.<tool_name>", e.g. "snowflake.run_industry_eval"."""
        server_name, tool_name = qualified_name.split(".", 1)
        session = self._sessions[server_name]
        return await session.call_tool(tool_name, arguments)
