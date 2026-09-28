from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load the .env file at the repo root, no matter which folder you run from.
_REPO_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class SharedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_REPO_ROOT_ENV), extra="ignore")

    database_url: str = "postgresql+psycopg://agentevalos:agentevalos@localhost:5432/agentevalos"

    snowflake_account: str = ""
    snowflake_user: str = ""
    snowflake_password: str = ""
    snowflake_role: str = "AGENTEVALOS_APP_ROLE"
    snowflake_warehouse: str = "AGENTEVALOS_WH"
    snowflake_database: str = "AGENTEVALOS"
    snowflake_schema: str = "EVALS"

    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
