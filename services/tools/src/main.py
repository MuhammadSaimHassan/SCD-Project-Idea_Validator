"""FastAPI entrypoint for M5 Tool Layer."""

from fastapi import FastAPI, HTTPException, status

from shared.schemas import FetchRequest, FetchResponse

from .config import ToolsSettings
from .config import settings as default_settings
from .fetcher import ToolFetcher
from .guard import DomainNotAllowedError, DomainRateLimitError, RobotsDisallowedError


def create_app(custom_settings: ToolsSettings | None = None) -> FastAPI:
    cfg = custom_settings or default_settings
    app = FastAPI(title="M5 Tool Layer", version="0.1.0")
    fetcher = ToolFetcher(cfg)
    app.state.settings = cfg
    app.state.fetcher = fetcher

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": cfg.service_name}

    @app.get("/ready")
    def ready() -> dict[str, str | int]:
        return {
            "status": "ready",
            "service": cfg.service_name,
            "allowed_domains": len(cfg.allowed_domains),
        }

    @app.get("/metrics")
    def metrics() -> dict[str, int | str]:
        f: ToolFetcher = app.state.fetcher
        return {
            "service": cfg.service_name,
            "fetches_total": f.fetch_count,
            "cache_hits_total": f.cache_hits,
            "blocked_domains_total": f.blocked_domains,
            "blocked_robots_total": f.blocked_robots,
            "sanitized_injections_total": f.sanitized_total,
        }

    @app.post("/fetch", response_model=FetchResponse)
    def fetch(payload: FetchRequest) -> FetchResponse:
        f: ToolFetcher = app.state.fetcher
        try:
            return f.fetch(payload)
        except (DomainNotAllowedError, RobotsDisallowedError) as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except DomainRateLimitError as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
            ) from exc

    return app


app = create_app()
