"""MCP server exposing Snowflake-backed tools to the LangGraph agent:

  - run_industry_eval(industry, model_name, dataset_ref) -> benchmark a single
    foundational tabular model against a labeled Snowflake dataset and return raw
    predictions/metrics for eval-engine to score.
  - fetch_dataset_schema(dataset_ref) -> column metadata, used during planning.

Run standalone for local testing: `python -m app.mcp.snowflake_tools`
Spawned automatically by agent-orchestrator per mcp_servers.yaml.
"""

from __future__ import annotations

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from app.config import settings

server = Server("snowflake")


def _get_snowflake_connection():
    """Lazy import + connect so this module can be introspected without snowflake-connector
    installed in dev environments that only touch the FastAPI side."""
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
            description=(
                "Benchmark a foundational tabular model (xgboost, catboost, lightgbm, "
                "tabpfn, logistic_regression) against a labeled Snowflake dataset for a "
                "given industry (finance | healthcare | generic). Returns predictions and "
                "raw metrics for downstream scoring."
            ),
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
        types.Tool(
            name="fetch_dataset_schema",
            description="Return column names/types/label column for a Snowflake dataset ref.",
            inputSchema={
                "type": "object",
                "properties": {"dataset_ref": {"type": "string"}},
                "required": ["dataset_ref"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "run_industry_eval":
        result = _run_industry_eval(**arguments)
    elif name == "fetch_dataset_schema":
        result = _fetch_dataset_schema(**arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")
    import json

    return [types.TextContent(type="text", text=json.dumps(result))]


def _run_industry_eval(industry: str, model_name: str, dataset_ref: str) -> dict:
    """Calls the Snowpark stored procedure that mirrors the native app's in-warehouse
    scoring logic (see snowflake-native-app/app/python/udfs/run_eval.py) so the same
    scoring code path is exercised whether you're running from this orchestrator or
    from inside a customer's Snowflake account via the native app.
    """
    import json

    conn = _get_snowflake_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "CALL AGENTEVALOS.EVALS.RUN_INDUSTRY_EVAL(%s, %s, %s)",
            (industry, model_name, dataset_ref),
        )
        row = cur.fetchone()
        if not row:
            return {}
        # CALL returns a single column holding the JSON string
        # run_industry_eval_proc produced (model_name/y_true/y_pred/y_score/...) —
        # parse it so callers get those keys directly instead of a
        # {"RUN_INDUSTRY_EVAL": "<json>"} wrapper.
        return json.loads(row[0])
    finally:
        conn.close()


def _fetch_dataset_schema(dataset_ref: str) -> dict:
    conn = _get_snowflake_connection()
    try:
        table = dataset_ref.split(".")[-1]
        cur = conn.cursor()
        cur.execute(f"DESCRIBE TABLE {dataset_ref}")
        rows = cur.fetchall()
        return {"table": table, "columns": [{"name": r[0], "type": r[1]} for r in rows]}
    finally:
        conn.close()


async def main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
