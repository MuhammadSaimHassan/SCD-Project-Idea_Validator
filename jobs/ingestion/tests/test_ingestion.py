"""Unit tests for M6i repeatable ingestion, deduplication, chunk card_ids, and snapshot."""

from pathlib import Path

from jobs.ingestion.src.pipeline import IngestionStore

from services.scouts.src.connectors import RawScoutItem


def _sample_items() -> list[RawScoutItem]:
    return [
        RawScoutItem(
            source="hackernews",
            name="CI Log Analyzer",
            url="https://news.ycombinator.com/item?id=1001",
            summary="Analyze CI logs",
            problem="Logs are huge and noisy to grep manually. " * 20,
            customer="developers",
            niche_tags=["devtools", "ci"],
            stage="launched",
            funding_usd=None,
            published_at="2026-10-15",
            text="CI Log Analyzer helps teams find root causes fast. " * 15,
        ),
        RawScoutItem(
            source="github",
            name="acme/doc-lint",
            url="https://github.com/acme/doc-lint",
            summary="Lint markdown docs",
            problem="Broken links in docs",
            customer="maintainers",
            niche_tags=["docs", "python"],
            stage="launched",
            funding_usd=None,
            published_at="2026-09-20",
            text="acme/doc-lint catches stale links in pull requests.",
        ),
        # Near-duplicate of item 2 with different URL
        RawScoutItem(
            source="yc",
            name="DocLint Mirror",
            url="https://www.ycombinator.com/companies/doclint",
            summary="Lint markdown docs",
            problem="Broken links in docs",
            customer="maintainers",
            niche_tags=["docs"],
            stage="seed",
            funding_usd=None,
            published_at=None,
            text="acme/doc-lint catches stale links in pull requests.",
        ),
    ]


def test_ingestion_is_repeatable_and_preserves_card_ids(tmp_path: Path) -> None:
    db_path = tmp_path / "kb.db"
    snap_path = tmp_path / "cards.jsonl"
    store = IngestionStore(db_path, snap_path)
    try:
        first = store.ingest_items(_sample_items(), run_source="test")
        assert first.added == 2
        assert first.dropped == 1
        assert first.total_cards == 2
        assert snap_path.exists()

        # Running again with identical batch adds 0 duplicates
        second = store.ingest_items(_sample_items(), run_source="test")
        assert second.added == 0
        assert second.dropped == 3
        assert second.total_cards == 2

        # Every chunk retains card_id prefix
        rows = store._conn.execute("SELECT chunk_id, card_id FROM chunks").fetchall()
        assert len(rows) >= 2
        for chunk_id, card_id in rows:
            assert chunk_id.startswith(f"{card_id}#c")
    finally:
        store.close()

    # Snapshot reload works offline into a fresh DB
    db_reloaded = tmp_path / "kb_reloaded.db"
    store2 = IngestionStore(db_reloaded)
    try:
        loaded = store2.load_snapshot(snap_path)
        assert loaded.added == 2
        assert loaded.total_cards == 2
    finally:
        store2.close()
