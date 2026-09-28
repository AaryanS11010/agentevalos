"""Snowflake I/O for warehouse-scale eval datasets and the model leaderboard.

Postgres (services/agent-orchestrator/app/db) holds per-run operational metadata;
Snowflake holds the large, append-only, analytics-friendly tables: labeled benchmark
datasets, every eval run's metrics, and the ranked model leaderboard. The reviewer
console and the Snowflake Native App both read the leaderboard table directly.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from agentevalos_sdk.schemas import ModelLeaderboardEntry

from app.config import settings

DDL = """
CREATE WAREHOUSE IF NOT EXISTS {warehouse} WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;

USE WAREHOUSE {warehouse};

CREATE DATABASE IF NOT EXISTS {database};

CREATE SCHEMA IF NOT EXISTS {database}.{schema};

CREATE STAGE IF NOT EXISTS {database}.{schema}.MODEL_STAGE;

CREATE STAGE IF NOT EXISTS {database}.{schema}.UDF_STAGE;

CREATE TABLE IF NOT EXISTS {database}.{schema}.MODEL_LEADERBOARD (
    industry              STRING,
    model_name            STRING,
    dataset_ref           STRING,
    primary_metric_name   STRING,
    primary_metric_value  FLOAT,
    calibration_error     FLOAT,
    fairness_gap          FLOAT,
    latency_ms_p50        FLOAT,
    impact_score          FLOAT,
    evaluated_at           TIMESTAMP_NTZ
);

CREATE TABLE IF NOT EXISTS {database}.{schema}.EVAL_RESULTS (
    run_id      STRING,
    industry    STRING,
    evaluator   STRING,
    model_name  STRING,
    metrics     VARIANT,
    dataset_ref STRING,
    created_at  TIMESTAMP_NTZ
);
"""


def _connection_params() -> dict:
    return {
        "account": settings.snowflake_account,
        "user": settings.snowflake_user,
        "password": settings.snowflake_password,
        "role": settings.snowflake_role,
        "warehouse": settings.snowflake_warehouse,
        "database": settings.snowflake_database,
        "schema": settings.snowflake_schema,
    }


@contextmanager
def get_snowpark_session() -> Iterator[snowflake.snowpark.Session]:  # noqa: F821
    """Snowpark session for registering stored procedures (see
    app/snowflake/udf_scoring.py::register) — distinct from get_connection()'s plain
    connector.Connection, which is enough for the raw-SQL DDL/DML the rest of this
    module does.
    """
    from snowflake.snowpark import Session

    session = Session.builder.configs(_connection_params()).create()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def get_connection() -> Iterator[snowflake.connector.SnowflakeConnection]:  # noqa: F821
    import snowflake.connector

    conn = snowflake.connector.connect(**_connection_params())
    try:
        yield conn
    finally:
        conn.close()


def ensure_schema() -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        formatted = DDL.format(
            warehouse=settings.snowflake_warehouse,
            database=settings.snowflake_database,
            schema=settings.snowflake_schema,
        )
        for stmt in formatted.split(";"):
            if stmt.strip():
                cur.execute(stmt)


def write_leaderboard(entries: list[ModelLeaderboardEntry]) -> None:
    if not entries:
        return
    with get_connection() as conn:
        cur = conn.cursor()
        cur.executemany(
            f"""
            INSERT INTO {settings.snowflake_database}.{settings.snowflake_schema}.MODEL_LEADERBOARD
            (industry, model_name, dataset_ref, primary_metric_name, primary_metric_value,
             calibration_error, fairness_gap, latency_ms_p50, impact_score, evaluated_at)
            VALUES (%(industry)s, %(model_name)s, %(dataset_ref)s, %(primary_metric_name)s,
                    %(primary_metric_value)s, %(calibration_error)s, %(fairness_gap)s,
                    %(latency_ms_p50)s, %(impact_score)s, %(evaluated_at)s)
            """,
            [e.model_dump(mode="json") for e in entries],
        )


def read_leaderboard(industry: str, limit: int = 25) -> list[dict]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT model_name, dataset_ref, primary_metric_name, primary_metric_value,
                   calibration_error, fairness_gap, latency_ms_p50, impact_score, evaluated_at
            FROM {settings.snowflake_database}.{settings.snowflake_schema}.MODEL_LEADERBOARD
            WHERE industry = %(industry)s
            ORDER BY impact_score DESC
            LIMIT %(limit)s
            """,
            {"industry": industry, "limit": limit},
        )
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
