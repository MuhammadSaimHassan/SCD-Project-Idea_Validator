"""Snapshot and verdict-distribution drift summaries."""

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from services.analyst.src.analyzer import analyze_cards
from shared.schemas import IdeaCard, VerdictLabel


def build_drift_report(
    previous_cards: list[IdeaCard],
    current_cards: list[IdeaCard],
    previous_verdicts: list[VerdictLabel] | None = None,
    current_verdicts: list[VerdictLabel] | None = None,
) -> dict[str, Any]:
    previous_sources = Counter(card.source for card in previous_cards)
    current_sources = Counter(card.source for card in current_cards)

    def freshness(cards: list[IdeaCard]) -> dict[str, str]:
        dates: dict[str, str] = {}
        for card in cards:
            fetched_at = str(card.fetched_at)
            dates[card.source] = max(dates.get(card.source, ""), fetched_at)
        return dict(sorted(dates.items()))

    previous_niches, _ = analyze_cards(previous_cards)
    current_niches, _ = analyze_cards(current_cards)
    previous_niche_counts = {item.name: item.size for item in previous_niches}
    current_niche_counts = {item.name: item.size for item in current_niches}

    def distribution(values: list[VerdictLabel] | None) -> dict[str, int]:
        return dict(sorted(Counter(item.value for item in values or []).items()))

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "cards": {
            "previous": len(previous_cards),
            "current": len(current_cards),
            "delta": len(current_cards) - len(previous_cards),
        },
        "sources": {
            "previous": dict(sorted(previous_sources.items())),
            "current": dict(sorted(current_sources.items())),
        },
        "freshness": {
            "previous_latest_fetched_at": freshness(previous_cards),
            "current_latest_fetched_at": freshness(current_cards),
        },
        "niche_coverage": {
            "previous": dict(sorted(previous_niche_counts.items())),
            "current": dict(sorted(current_niche_counts.items())),
        },
        "verdict_distribution": {
            "available": previous_verdicts is not None and current_verdicts is not None,
            "previous": distribution(previous_verdicts),
            "current": distribution(current_verdicts),
        },
    }
