"""Unit and API tests for M6 Knowledge Base search, filters, and stats."""

from pathlib import Path

from fastapi.testclient import TestClient

from services.kb.src.config import KBSettings
from services.kb.src.main import create_app

ROOT = Path(__file__).resolve().parents[3]


def test_kb_search_filters_and_stats() -> None:
    cfg = KBSettings(snapshot_path=ROOT / "eval" / "retrieval" / "eval_cards.jsonl")
    client = TestClient(create_app(cfg))

    assert client.get("/health").status_code == 200
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["cards_indexed"] >= 150

    stats = client.get("/stats")
    assert stats.status_code == 200
    assert "counts_by_source" in stats.json()

    resp = client.post(
        "/search",
        json={
            "query": "HIPAA messaging doctors",
            "top_k": 5,
            "source_filter": ["yc"],
        },
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert all(item["source"] == "yc" for item in items)
    assert all("#c" in item["evidence_id"] for item in items)
