"""Environment-backed configuration for M1 API Gateway & M2 Persistence."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    """Settings read exclusively from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "gateway"
    environment: str = "development"
    log_level: str = "INFO"

    # Persistence & cache (M2)
    database_url: str = "sqlite:///./gateway_dev.db"
    redis_url: str = ""
    cache_ttl_seconds: int = 3600

    # Auth & rate limiting (M1)
    jwt_secret: str = "dev-insecure-secret-change-in-prod"
    jwt_ttl_seconds: int = 86400
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    # Downstream services (DNS names, never hardcode localhost)
    orchestrator_url: str = ""
    verdict_url: str = ""
    critic_url: str = ""
    agentops_url: str = ""
    config_dir: Path = Path("./config")
    rubric_version: str = "r1"


settings = GatewaySettings()
