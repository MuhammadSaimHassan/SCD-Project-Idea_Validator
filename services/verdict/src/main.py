"""FastAPI entrypoint for M11 Verdict Engine."""

from fastapi import FastAPI, HTTPException

from shared.config import load_rubrics, load_thresholds, load_weights_config
from shared.schemas import Verdict, VerdictRequest, WhatIfRequest

from .config import settings
from .engine import apply_whatif, evaluate_verdict

app = FastAPI(title="M11 Verdict Engine", version="0.1.0")

_verdicts_computed = 0


def _rubric_version_tag() -> str:
    try:
        rubrics = load_rubrics(settings.config_dir.parent / "rubrics")
        versions = sorted(str(r.get("rubric_version", dim.value)) for dim, r in rubrics.items())
        return ",".join(versions)
    except FileNotFoundError:
        return "r1"


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": settings.service_name}


@app.get("/ready")
def ready() -> dict[str, str | int | float]:
    """Readiness probe verifying config files and schema imports."""
    _, weights = load_weights_config(settings.config_dir)
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
    return {"service": settings.service_name, "verdicts_computed": _verdicts_computed}


@app.post("/verdict", response_model=Verdict)
def compute_verdict(payload: VerdictRequest) -> Verdict:
    """Evaluate hard gates, weighted score, sensitivity, and what-if suggestions."""
    global _verdicts_computed
    weights_version, weights = load_weights_config(settings.config_dir)
    thresholds = load_thresholds(settings.config_dir)
    try:
        result = evaluate_verdict(
            payload,
            weights_by_goal=weights,
            thresholds=thresholds,
            weights_version=weights_version,
            rubrics_version=_rubric_version_tag(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _verdicts_computed += 1
    return result


@app.post("/whatif", response_model=Verdict)
def compute_whatif(payload: WhatIfRequest) -> Verdict:
    """Apply dimension overrides and produce a new Verdict version."""
    global _verdicts_computed
    weights_version, weights = load_weights_config(settings.config_dir)
    thresholds = load_thresholds(settings.config_dir)
    try:
        result = apply_whatif(
            payload,
            weights_by_goal=weights,
            thresholds=thresholds,
            weights_version=weights_version,
            rubrics_version=_rubric_version_tag(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _verdicts_computed += 1
    return result
