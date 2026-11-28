"""FastAPI entrypoint for M7 Niche & Trend Analyst."""

from fastapi import FastAPI

from .analyzer import GapItem, NicheCluster, analyze_cards, load_cards
from .config import AnalystSettings
from .config import settings as default_settings


def create_app(custom_settings: AnalystSettings | None = None) -> FastAPI:
    cfg = custom_settings or default_settings
    app = FastAPI(title="M7 Niche and Trend Analyst", version="0.1.0")
    cards = load_cards(cfg.snapshot_path)
    clusters, gaps = analyze_cards(cards)

    app.state.settings = cfg
    app.state.clusters = clusters
    app.state.gaps = gaps

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": cfg.service_name}

    @app.get("/ready")
    def ready() -> dict[str, str | int]:
        c: list[NicheCluster] = app.state.clusters
        g: list[GapItem] = app.state.gaps
        return {
            "status": "ready",
            "service": cfg.service_name,
            "niches": len(c),
            "gaps": len(g),
        }

    @app.get("/metrics")
    def metrics() -> dict[str, int | str]:
        c: list[NicheCluster] = app.state.clusters
        g: list[GapItem] = app.state.gaps
        return {"service": cfg.service_name, "niches_total": len(c), "gaps_total": len(g)}

    @app.get("/niches", response_model=list[NicheCluster])
    def list_niches() -> list[NicheCluster]:
        c: list[NicheCluster] = app.state.clusters
        return c

    @app.get("/gaps", response_model=list[GapItem])
    def list_gaps() -> list[GapItem]:
        g: list[GapItem] = app.state.gaps
        return g

    @app.post("/analyze")
    def reanalyze() -> dict[str, int]:
        loaded = load_cards(cfg.snapshot_path)
        new_clusters, new_gaps = analyze_cards(loaded)
        app.state.clusters = new_clusters
        app.state.gaps = new_gaps
        return {"cards_analyzed": len(loaded), "niches": len(new_clusters), "gaps": len(new_gaps)}

    return app


app = create_app()
