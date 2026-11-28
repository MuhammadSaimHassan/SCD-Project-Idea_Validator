"""Unit and API tests for M7 Niche & Trend Analyst."""

from pathlib import Path

from fastapi.testclient import TestClient

from services.analyst.src.analyzer import analyze_cards, load_cards, render_niche_chart_svg
from services.analyst.src.config import AnalystSettings
from services.analyst.src.main import create_app

ROOT = Path(__file__).resolve().parents[3]


def test_analyst_clusters_trends_and_gaps() -> None:
    eval_path = ROOT / "eval" / "retrieval" / "eval_cards.jsonl"
    cards = load_cards(eval_path)
    clusters, gaps = analyze_cards(cards)
    assert len(clusters) >= 3
    assert len(gaps) >= 3
    assert all(c.trend_label in {"rising", "flat", "saturated"} for c in clusters)
    assert all(len(g.evidence_card_ids) >= 1 for g in gaps)

    svg = render_niche_chart_svg(clusters)
    assert "<svg" in svg

    client = TestClient(create_app(AnalystSettings(snapshot_path=eval_path)))
    assert client.get("/health").status_code == 200
    assert client.get("/ready").json()["status"] == "ready"
    assert len(client.get("/niches").json()) >= 3
    assert len(client.get("/gaps").json()) >= 3
