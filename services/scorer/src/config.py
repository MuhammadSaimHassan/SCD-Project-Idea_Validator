"""Environment-backed configuration for M10 Scoring Model server."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ScorerSettings(BaseSettings):
    """Settings read exclusively from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "scorer"
    environment: str = "development"
    log_level: str = "INFO"

    primary_model_name: str = "scorer-lora@v1"
    model_backend_url: str = ""  # Optional llama.cpp / Ollama URL
    hosted_llm_api_key: str = ""
    hosted_llm_model: str = "gemini-2.0-flash"
    request_timeout_seconds: float = 15.0


settings = ScorerSettings()
