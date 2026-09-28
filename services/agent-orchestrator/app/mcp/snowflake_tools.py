# A small MCP server that gives the agent one tool: run a model against a
# Snowflake dataset and get the predictions back.
# Run by itself for testing: python -m app.mcp.snowflake_tools
from __future__ import annotations

import json

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from app.config import settings

server = Server("snowflake")


def _get_connection():
    import snowflake.connector

    return snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        password=settings.snowflake_password,
        role=settings.snowflake_role,
        warehouse=settings.snowflake_warehouse,
        database=settings.snowflake_database,
        schema=settings.snowflake_schema,
    )


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="run_industry_eval",
            description="Run a tabular model against a Snowflake dataset and return predictions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "industry": {"type": "string"},
                    "model_name": {"type": "string"},
                    "dataset_ref": {"type": "string"},
                },
                "required": ["industry", "model_name", "dataset_ref"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name != "run_industry_eval":
        raise ValueError(f"unknown tool: {name}")

    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "CALL AGENTEVALOS.EVALS.RUN_INDUSTRY_EVAL(%s, %s, %s)",
            (arguments["industry"], arguments["model_name"], arguments["dataset_ref"]),
        )
        row = cur.fetchone()
        # the CALL result is one column holding a JSON string
        result = json.loads(row[0]) if row else {}
    finally:
        conn.close()

    return [types.TextContent(type="text", text=json.dumps(result))]


async def main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
