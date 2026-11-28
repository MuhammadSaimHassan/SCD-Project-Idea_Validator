"""Environment-backed configuration for M9 Validation Agents."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ValidatorsSettings(BaseSettings):
    """Settings read exclusively from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "validators"
    environment: str = "development"
    log_level: str = "INFO"
    scorer_url: str = ""
    rubrics_dir: Path = Path("./rubrics")
    request_timeout_seconds: float = 15.0


settings = ValidatorsSettings()
