"""FastAPI entrypoint for M9 Parallel Validation Agents."""

from fastapi import FastAPI

from shared.schemas import DimensionScore

from .agents import (
    HttpScoreClient,
    LocalScoreClient,
    ScoreClient,
    ValidateScoresRequest,
    run_four_parallel_scorers,
)
from .config import ValidatorsSettings
from .config import settings as default_settings


def create_app(
    custom_settings: ValidatorsSettings | None = None,
    score_client: ScoreClient | None = None,
) -> FastAPI:
    cfg = custom_settings or default_settings
    app = FastAPI(title="M9 Validation Agents", version="0.1.0")
    client: ScoreClient = score_client or (
        HttpScoreClient(cfg.scorer_url, timeout=cfg.request_timeout_seconds)
        if cfg.scorer_url
        else LocalScoreClient()
    )

    app.state.settings = cfg
    app.state.score_client = client
    app.state.runs_total = 0

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": cfg.service_name}

    @app.get("/ready")
    def ready() -> dict[str, str | int]:
        return {
            "status": "ready",
            "service": cfg.service_name,
            "parallel_scorers": 4,
        }

    @app.get("/metrics")
    def metrics() -> dict[str, int | str]:
        return {
            "service": cfg.service_name,
            "validation_runs_total": int(app.state.runs_total),
        }

    @app.post("/score-all", response_model=list[DimensionScore])
    def score_all(payload: ValidateScoresRequest) -> list[DimensionScore]:
        app.state.runs_total += 1
        sc: ScoreClient = app.state.score_client
        return run_four_parallel_scorers(payload, sc, cfg.rubrics_dir)

    return app


app = create_app()
