"""Niche clustering, monthly time series, trend slope, and gap detection for M7."""

from collections import Counter, defaultdict
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from shared.schemas import IdeaCard

NICHE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ai-agents": ("agent", "agents", "agentic", "llm", "rag", "mcp", "claude", "langchain"),
    "devtools-cli": ("cli", "developer-tools", "devtools", "terminal", "git", "ci", "ide"),
    "fintech": ("fintech", "payments", "invoicing", "billing", "finance", "budget"),
    "healthcare": ("healthcare", "medical", "hipaa", "doctor", "clinical", "health"),
    "education": ("education", "edtech", "classroom", "study", "learning", "student"),
    "productivity": ("productivity", "task", "calendar", "notes", "kanban", "workspace"),
    "security-privacy": ("privacy", "encryption", "auth", "security", "end-to-end"),
    "climate": ("climate", "environmental", "carbon", "energy", "sustainability"),
    "collaboration": ("collaboration", "remote", "messaging", "chat", "team"),
    "b2b-saas": ("b2b", "saas", "analytics", "enterprise", "marketplace"),
}


class MonthlyStat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str
    launches: int
    mentions: int


class NicheCluster(BaseModel):
    model_config = ConfigDict(extra="forbid")

    niche_id: str
    name: str
    size: int
    trend_slope: float
    trend_label: str  # rising | flat | saturated
    monthly_stats: list[MonthlyStat] = Field(default_factory=list)
    sample_card_ids: list[str] = Field(default_factory=list)


class GapItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    niche: str
    gap_summary: str
    evidence_card_ids: list[str]
    demand_signals: int
    competition_count: int
    trend_label: str


def _assign_niche(card: IdeaCard) -> str:
    haystack = " ".join([card.name, card.summary, card.problem, *card.niche_tags]).lower()
    best_niche = "general-indie"
    best_hits = 0
    for niche, keywords in NICHE_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in haystack)
        if hits > best_hits:
            best_hits = hits
            best_niche = niche
    return best_niche


def _linear_slope(values: list[int]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return round(num / den, 4) if den > 0 else 0.0


def analyze_cards(
    cards: list[IdeaCard],
) -> tuple[list[NicheCluster], list[GapItem]]:
    """Cluster cards into named niches, compute monthly trends, and extract gaps."""
    by_niche: dict[str, list[IdeaCard]] = defaultdict(list)
    for card in cards:
        by_niche[_assign_niche(card)].append(card)

    clusters: list[NicheCluster] = []
    gaps: list[GapItem] = []

    for niche_name, group in sorted(by_niche.items(), key=lambda kv: len(kv[1]), reverse=True):
        monthly_mentions: Counter[str] = Counter()
        monthly_launches: Counter[str] = Counter()
        launched_total = 0

        for c in group:
            if c.stage in ("launched", "seed", "active", "public"):
                launched_total += 1
            pub = str(c.published_at) if c.published_at else ""
            month = pub[:7] if len(pub) >= 7 else "undated"
            monthly_mentions[month] += 1
            if c.stage == "launched":
                monthly_launches[month] += 1

        dated_months = sorted(m for m in monthly_mentions if m != "undated")[-12:]
        stats = [
            MonthlyStat(
                month=m,
                launches=monthly_launches[m],
                mentions=monthly_mentions[m],
            )
            for m in dated_months
        ]
        slope = _linear_slope([s.mentions for s in stats])
        launched_ratio = launched_total / max(1, len(group))

        if slope > 0.05:
            trend_label = "rising"
        elif len(group) >= 40 and launched_ratio >= 0.65:
            trend_label = "saturated"
        else:
            trend_label = "flat"

        clusters.append(
            NicheCluster(
                niche_id=f"niche_{niche_name}",
                name=niche_name,
                size=len(group),
                trend_slope=slope,
                trend_label=trend_label,
                monthly_stats=stats,
                sample_card_ids=[c.id for c in group[:5]],
            )
        )

        # Gap detection: cards expressing complaints / Ask HN pain / niche problems
        pain_cards = [
            c
            for c in group
            if any(
                kw in f"{c.name} {c.problem}".lower()
                for kw in ("ask hn", "slow", "missing", "problem", "hard", "pain", "manual", "why")
            )
        ]
        candidate_cards = pain_cards if pain_cards else group[:3]
        if candidate_cards:
            gaps.append(
                GapItem(
                    niche=niche_name,
                    gap_summary=(
                        f"{niche_name}: {len(pain_cards)} complaint/problem signals; "
                        f"sample pain: {candidate_cards[0].summary[:120]}"
                    ),
                    evidence_card_ids=[c.id for c in candidate_cards[:5]],
                    demand_signals=max(len(pain_cards), 1),
                    competition_count=launched_total,
                    trend_label=trend_label,
                )
            )

    gaps.sort(key=lambda g: (g.demand_signals, -g.competition_count), reverse=True)
    return clusters, gaps


def load_cards(snapshot_path: Path) -> list[IdeaCard]:
    if not snapshot_path.exists():
        return []
    cards: list[IdeaCard] = []
    with snapshot_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                cards.append(IdeaCard.model_validate_json(line))
    return cards


def render_niche_chart_svg(clusters: list[NicheCluster]) -> str:
    """Render a clean SVG bar chart of niche sizes and trend labels."""
    top = clusters[:10]
    width = 760
    height = 60 + len(top) * 34
    max_size = max((c.size for c in top), default=1)
    colors = {"rising": "#16a34a", "flat": "#3b82f6", "saturated": "#d97706"}
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#0f1419"/>',
        '<text x="20" y="32" fill="#e8eef5" font-family="sans-serif" font-size="18" '
        'font-weight="bold">Niche Map &amp; Trend Classification (M7)</text>',
    ]
    for idx, c in enumerate(top):
        y = 58 + idx * 34
        bar_w = int((c.size / max_size) * 420)
        color = colors.get(c.trend_label, "#3b82f6")
        lines.append(
            f'<text x="20" y="{y + 16}" fill="#e8eef5" font-family="sans-serif" '
            f'font-size="13">{c.name}</text>'
        )
        lines.append(
            f'<rect x="180" y="{y}" width="{bar_w}" height="22" rx="4" fill="{color}"/>'
        )
        lines.append(
            f'<text x="{190 + bar_w}" y="{y + 16}" fill="#93a4b8" font-family="sans-serif" '
            f'font-size="12">{c.size} cards ({c.trend_label}, slope={c.trend_slope:+.2f})</text>'
        )
    lines.append("</svg>")
    return "\n".join(lines)
