"""Environment-backed configuration for M1 API Gateway."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    """Settings read exclusively from environment variables (never hardcode localhost)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "gateway"
    environment: str = "development"
    log_level: str = "INFO"
    orchestrator_url: str = "http://orchestrator:8000"
    verdict_url: str = "http://verdict:8000"
    agentops_url: str = "http://agentops:8000"


settings = GatewaySettings()
