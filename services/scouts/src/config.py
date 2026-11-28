"""Environment-backed configuration for M4 Scouts."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ScoutSettings(BaseSettings):
    """Settings read exclusively from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "scouts"
    tools_url: str = ""
    request_timeout_seconds: float = 20.0


settings = ScoutSettings()
