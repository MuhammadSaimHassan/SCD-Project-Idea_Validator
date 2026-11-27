"""FastAPI entrypoint for M1 API Gateway + M2 Persistence & Cache."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.gateway.src.db.session import (
    build_engine,
    build_session_factory,
    check_db_ready,
    init_schema,
)
from services.gateway.src.repositories.cache import VersionedCache
from services.gateway.src.routes import auth, ideas, profile, runs
from services.gateway.src.services.rate_limit import RateLimiter
from shared.schemas import StudentProfile

from .config import GatewaySettings
from .config import settings as default_settings


def create_app(custom_settings: GatewaySettings | None = None) -> FastAPI:
    """Create configured M1 Gateway FastAPI app (supports isolated test settings)."""
    cfg = custom_settings or default_settings
    app = FastAPI(title="M1 API Gateway", version="0.2.0")

    engine = build_engine(cfg.database_url)
    init_schema(engine)

    app.state.settings = cfg
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    app.state.cache = VersionedCache(
        redis_url=cfg.redis_url,
        default_ttl_seconds=cfg.cache_ttl_seconds,
    )
    app.state.rate_limiter = RateLimiter(
        max_requests=cfg.rate_limit_requests,
        window_seconds=cfg.rate_limit_window_seconds,
    )
    app.state.requests_total = 0

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def rate_limit_and_count(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        app.state.requests_total += 1
        if request.url.path not in ("/health", "/ready", "/metrics"):
            client_ip = request.client.host if request.client else "unknown"
            if not app.state.rate_limiter.allow(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                )
        return await call_next(request)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": cfg.service_name}

    @app.get("/ready")
    def ready() -> dict[str, str | bool]:
        db_ok = check_db_ready(app.state.engine)
        cache_ok = app.state.cache.ping()
        return {
            "status": "ready" if (db_ok and cache_ok) else "degraded",
            "service": cfg.service_name,
            "db_ready": db_ok,
            "cache_ready": cache_ok,
            "schema": StudentProfile.__name__,
        }

    @app.get("/metrics")
    def metrics() -> dict[str, int | float | str]:
        cache: VersionedCache = app.state.cache
        total_lookups = cache.hits + cache.misses
        hit_rate = round(cache.hits / total_lookups, 4) if total_lookups else 0.0
        return {
            "service": cfg.service_name,
            "requests_total": int(app.state.requests_total),
            "rate_limited_total": int(app.state.rate_limiter.blocked_total),
            "cache_hits_total": cache.hits,
            "cache_misses_total": cache.misses,
            "cache_hit_rate": hit_rate,
        }

    app.include_router(auth.router)
    app.include_router(profile.router)
    app.include_router(runs.router)
    app.include_router(ideas.router)

    return app


app = create_app()
