"""Environment-backed configuration for M11 Verdict Engine."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class VerdictSettings(BaseSettings):
    """Settings read exclusively from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "verdict"
    environment: str = "development"
    log_level: str = "INFO"
    config_dir: Path = Path("./config")


settings = VerdictSettings()
