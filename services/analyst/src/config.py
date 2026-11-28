"""Environment-backed configuration for M7 Niche & Trend Analyst."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalystSettings(BaseSettings):
    """Settings read exclusively from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "analyst"
    environment: str = "development"
    log_level: str = "INFO"
    snapshot_path: Path = Path("data/snapshot/cards.jsonl")


settings = AnalystSettings()
