from agentevalos_sdk.config import SharedSettings


class Settings(SharedSettings):
    service_name: str = "agent-orchestrator"
    port: int = 8001
    eval_engine_url: str = "http://localhost:8002"
    mcp_config_path: str = "./mcp_servers.yaml"


settings = Settings()
