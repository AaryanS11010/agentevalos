from agentevalos_sdk.config import SharedSettings


class Settings(SharedSettings):
    service_name: str = "eval-engine"
    port: int = 8002
    redteam_promptfoo_config: str = "./app/promptfoo/promptfooconfig.yaml"


settings = Settings()
