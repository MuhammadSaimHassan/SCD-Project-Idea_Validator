"""FastAPI entrypoint for M11 Verdict Engine."""

from fastapi import FastAPI

from shared.config import load_thresholds, load_weights
from shared.schemas import Verdict

from .config import settings

app = FastAPI(title="M11 Verdict Engine", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": settings.service_name}


@app.get("/ready")
def ready() -> dict[str, str | int | float]:
    """Readiness probe verifying config files and schema imports."""
    weights = load_weights(settings.config_dir)
    thresholds = load_thresholds(settings.config_dir)
    return {
        "status": "ready",
        "service": settings.service_name,
        "goal_presets": len(weights),
        "t_go": float(thresholds["T_go"]),
        "schema": Verdict.__name__,
    }


@app.get("/metrics")
def metrics() -> dict[str, int | str]:
    """Basic service metrics endpoint."""
    return {"service": settings.service_name, "verdicts_computed": 0}
