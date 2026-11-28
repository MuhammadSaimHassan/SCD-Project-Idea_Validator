"""Environment-backed configuration for M5 Tool Layer."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ToolsSettings(BaseSettings):
    """Settings read exclusively from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "tools"
    environment: str = "development"
    log_level: str = "INFO"

    user_agent: str = "CS4032-IdeaValidator-Bot/1.0 (+educational-project)"
    allowed_domains: list[str] = [
        "hn.algolia.com",
        "hacker-news.firebaseio.com",
        "api.github.com",
        "yc-oss.github.io",
        "www.reddit.com",
        "oauth.reddit.com",
        "api.producthunt.com",
        "www.ycombinator.com",
    ]
    per_domain_rpm: int = 30
    cache_ttl_seconds: int = 3600
    request_timeout_seconds: float = 15.0
    max_retries: int = 2
    max_pages_per_run: int = 25
    agentops_url: str = ""
    github_token: str = ""
    respect_robots_txt: bool = True


settings = ToolsSettings()
