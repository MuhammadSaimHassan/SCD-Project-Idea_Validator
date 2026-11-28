"""CLI runner for M6i Ingestion job (scouts -> dedupe -> chunk -> embed -> snapshot)."""

import argparse
import json
import sys
from pathlib import Path

from services.agentops.src.drift import build_drift_report
from services.analyst.src.analyzer import load_cards
from services.scouts.src.config import settings as scout_settings
from services.scouts.src.connectors import HttpToolsClient, ToolsClient, run_scouts
from services.tools.src.config import ToolsSettings
from services.tools.src.fetcher import ToolFetcher

from .pipeline import IngestionStore


def _build_tools() -> ToolsClient:
    if scout_settings.tools_url:
        return HttpToolsClient(
            scout_settings.tools_url, timeout=scout_settings.request_timeout_seconds
        )
    return ToolFetcher(ToolsSettings())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run M6i Ingestion job")
    parser.add_argument(
        "--sources",
        default="hn,github,yc",
        help="Comma-separated scout sources (e.g., hn,github,yc,reddit)",
    )
    parser.add_argument("--per-source", type=int, default=550, help="Target cards per source")
    parser.add_argument("--db", default="data/kb/knowledge.db", help="SQLite store path")
    parser.add_argument(
        "--snapshot", default="data/snapshot/cards.jsonl", help="JSONL snapshot output"
    )
    parser.add_argument(
        "--from-snapshot",
        default="",
        help="Load existing snapshot JSONL instead of calling scouts",
    )
    parser.add_argument(
        "--drift-report",
        default="eval/results/drift_report.json",
        help="Output path for the post-ingestion drift report",
    )
    args = parser.parse_args(argv)

    snapshot_path = Path(args.snapshot)
    previous_cards = load_cards(snapshot_path) if snapshot_path.exists() else []
    store = IngestionStore(Path(args.db), snapshot_path)
    try:
        if args.from_snapshot:
            stats = store.load_snapshot(Path(args.from_snapshot))
            errors: dict[str, str] = {}
        else:
            sources = [s.strip() for s in args.sources.split(",") if s.strip()]
            tools = _build_tools()
            items, errors = run_scouts(sources, tools, per_source_limit=args.per_source)
            stats = store.ingest_items(items, run_source=",".join(sources))
    finally:
        store.close()

    current_cards = load_cards(snapshot_path)
    drift_report = build_drift_report(previous_cards, current_cards)
    drift_path = Path(args.drift_report)
    drift_path.parent.mkdir(parents=True, exist_ok=True)
    drift_path.write_text(json.dumps(drift_report, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "run_id": stats.run_id,
                "added": stats.added,
                "dropped_duplicates": stats.dropped,
                "total_cards": stats.total_cards,
                "counts_by_source": stats.counts_by_source,
                "scout_errors": errors,
                "snapshot": args.snapshot,
                "drift_report": args.drift_report,
            },
            indent=2,
        )
    )
    return 0 if stats.total_cards > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
