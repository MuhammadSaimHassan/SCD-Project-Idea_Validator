"""FastAPI entrypoint for M6 Knowledge Base."""

from fastapi import FastAPI

from shared.schemas import SearchRequest, SearchResponse

from .config import KBSettings
from .config import settings as default_settings
from .retriever import HybridKnowledgeBase


def create_app(
    custom_settings: KBSettings | None = None,
    kb: HybridKnowledgeBase | None = None,
) -> FastAPI:
    cfg = custom_settings or default_settings
    app = FastAPI(title="M6 Knowledge Base", version="0.1.0")
    index = kb or HybridKnowledgeBase.from_snapshot(cfg.snapshot_path)

    app.state.settings = cfg
    app.state.kb = index
    app.state.searches_total = 0

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": cfg.service_name}

    @app.get("/ready")
    def ready() -> dict[str, str | int]:
        store: HybridKnowledgeBase = app.state.kb
        return {
            "status": "ready",
            "service": cfg.service_name,
            "cards_indexed": store.card_count,
            "chunks_indexed": store.chunk_count,
        }

    @app.get("/metrics")
    def metrics() -> dict[str, int | str]:
        store: HybridKnowledgeBase = app.state.kb
        return {
            "service": cfg.service_name,
            "searches_total": int(app.state.searches_total),
            "cards_indexed": store.card_count,
            "chunks_indexed": store.chunk_count,
        }

    @app.get("/stats")
    def stats() -> dict[str, object]:
        store: HybridKnowledgeBase = app.state.kb
        return store.stats()

    @app.post("/search", response_model=SearchResponse)
    def search(payload: SearchRequest) -> SearchResponse:
        app.state.searches_total += 1
        store: HybridKnowledgeBase = app.state.kb
        return store.search(payload, mode="hybrid")

    return app


app = create_app()
