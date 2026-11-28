from services.analyst.src.analyzer import GapItem
from services.ideator.src.agents import debate, ideator


def test_ideator_debate_caps_rounds_and_drops_unsupported_clone() -> None:
    gaps = [
        GapItem(
            niche="education",
            gap_summary="Students need automated study review",
            evidence_card_ids=["card_1#c1", "card_2#c1"],
            demand_signals=8,
            competition_count=2,
            trend_label="rising",
        )
    ]
    candidates = ideator(gaps, ["python", "fastapi"], 12)
    assert len(candidates) == 1
    assert candidates[0].gap_evidence_ids

    clone = candidates[0]
    survivors, trace = debate([clone], existing_names=[clone.title], max_rounds=3)
    assert survivors == []
    assert len(trace) == 1
    assert trace[0]["objections"]
