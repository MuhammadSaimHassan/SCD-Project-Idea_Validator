"""FastAPI entrypoint for M1 API Gateway."""

from fastapi import FastAPI

from shared.schemas import StudentProfile

from .config import settings

app = FastAPI(title="M1 API Gateway", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": settings.service_name}


@app.get("/ready")
def ready() -> dict[str, str]:
    """Readiness probe verifying runtime config and shared schema imports."""
    return {
        "status": "ready",
        "service": settings.service_name,
        "verdict_url": settings.verdict_url,
        "schema": StudentProfile.__name__,
    }


@app.get("/metrics")
def metrics() -> dict[str, int | str]:
    """Basic gateway metrics endpoint."""
    return {"service": settings.service_name, "requests_total": 0}
