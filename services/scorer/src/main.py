"""FastAPI entrypoint for M10 Scoring Model Server."""

from fastapi import FastAPI

from shared.schemas import DimensionScore, ScoreRequest

from .config import ScorerSettings
from .config import settings as default_settings
from .model import FeatureRubricBackend, HttpModelBackend, ScorerBackend, ScoringEngine


def create_app(
    custom_settings: ScorerSettings | None = None,
    primary_backend: ScorerBackend | None = None,
    fallback_backend: ScorerBackend | None = None,
) -> FastAPI:
    cfg = custom_settings or default_settings
    app = FastAPI(title="M10 Scoring Model Server", version="0.1.0")

    primary: ScorerBackend = primary_backend or (
        HttpModelBackend(cfg.model_backend_url, cfg.primary_model_name, cfg.request_timeout_seconds)
        if cfg.model_backend_url
        else FeatureRubricBackend()
    )
    fallback: ScorerBackend = fallback_backend or FeatureRubricBackend()
    engine = ScoringEngine(
        primary,
        fallback,
        primary_model_name=cfg.primary_model_name,
        fallback_model_name=cfg.hosted_llm_model,
    )

    app.state.settings = cfg
    app.state.engine = engine

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": cfg.service_name}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        return {
            "status": "ready",
            "service": cfg.service_name,
            "model": cfg.primary_model_name,
        }

    @app.get("/metrics")
    def metrics() -> dict[str, int | str]:
        eng: ScoringEngine = app.state.engine
        return {
            "service": cfg.service_name,
            "scores_total": eng.scores_total,
            "retries_total": eng.retries_total,
            "fallbacks_total": eng.fallbacks_total,
        }

    @app.post("/score", response_model=DimensionScore)
    def score(payload: ScoreRequest) -> DimensionScore:
        eng: ScoringEngine = app.state.engine
        return eng.score(payload)

    return app


app = create_app()
