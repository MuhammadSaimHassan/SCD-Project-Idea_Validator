"""Environment-backed configuration for M6 Knowledge Base."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class KBSettings(BaseSettings):
    """Settings read exclusively from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "kb"
    environment: str = "development"
    log_level: str = "INFO"

    snapshot_path: Path = Path("data/snapshot/cards.jsonl")
    vector_store_url: str = ""
    default_top_k: int = 5


settings = KBSettings()
