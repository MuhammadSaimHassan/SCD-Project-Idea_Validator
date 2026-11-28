"""M8 deterministic ideator, gap analyst, skeptic, and three-round debate."""

from collections.abc import Iterable
from dataclasses import dataclass

from services.analyst.src.analyzer import GapItem


@dataclass(frozen=True)
class CandidateIdea:
    title: str
    description: str
    gap_evidence_ids: tuple[str, ...]
    niche: str


def ideator(
    gaps: Iterable[GapItem], skills: list[str], hours_per_week: float, limit: int = 5
) -> list[CandidateIdea]:
    candidates: list[CandidateIdea] = []
    skill_text = ", ".join(skills[:3]) or "general software"
    for gap in gaps:
        title = f"{gap.niche.title()} Gap Monitor"
        description = (
            f"A scoped tool for {gap.niche} that addresses '{gap.gap_summary}' "
            f"using {skill_text}, designed for a {int(hours_per_week)}h/week student team."
        )
        candidates.append(
            CandidateIdea(
                title=title,
                description=description,
                gap_evidence_ids=tuple(gap.evidence_card_ids),
                niche=gap.niche,
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def gap_analyst(gap: GapItem) -> str:
    return (
        f"Demand signals: {gap.demand_signals}; competition: {gap.competition_count}; "
        f"trend: {gap.trend_label}. Gap: {gap.gap_summary}"
    )


def skeptic(candidate: CandidateIdea, existing_names: Iterable[str] = ()) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    known = {name.lower() for name in existing_names}
    if candidate.title.lower() in known:
        reasons.append("This is a renamed clone of an existing product")
    if not candidate.gap_evidence_ids:
        reasons.append("No gap evidence supports this idea")
    if len(candidate.description) < 40:
        reasons.append("The idea is too thin to validate")
    return not reasons, reasons


def debate(
    candidates: Iterable[CandidateIdea],
    existing_names: Iterable[str] = (),
    max_rounds: int = 3,
) -> tuple[list[CandidateIdea], list[dict[str, object]]]:
    survivors: list[CandidateIdea] = list(candidates)
    trace: list[dict[str, object]] = []
    for round_number in range(1, max_rounds + 1):
        next_survivors: list[CandidateIdea] = []
        for candidate in survivors:
            survives, reasons = skeptic(candidate, existing_names)
            trace.append(
                {
                    "round": round_number,
                    "title": candidate.title,
                    "survives": survives,
                    "objections": reasons,
                }
            )
            if survives:
                next_survivors.append(candidate)
        survivors = next_survivors
        if not survivors:
            break
    return survivors, trace
