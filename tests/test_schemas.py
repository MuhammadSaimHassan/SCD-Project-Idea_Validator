"""Tests for shared schemas, JSON Schema exports, and YAML config files."""

import json
from pathlib import Path

from shared.config import load_budgets, load_thresholds, load_weights
from shared.schemas import (
    ComputeTier,
    DimensionName,
    DimensionScore,
    EvidenceItem,
    GoalType,
    IdeaCard,
    StudentProfile,
    TraceKind,
    TraceRecord,
)
from shared.schemas.export import SCHEMA_MODELS

ROOT = Path(__file__).resolve().parents[1]


def test_exported_json_schemas_match_models() -> None:
    schemas_dir = ROOT / "schemas"
    for name, model in SCHEMA_MODELS.items():
        path = schemas_dir / f"{name}.schema.json"
        assert path.exists(), f"Missing exported schema: {path}"
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded == model.model_json_schema()


def test_core_domain_models_validate() -> None:
    card = IdeaCard(
        id="card_8f21",
        name="ExampleApp",
        summary="One line on what it does",
        problem="Export is slow",
        customer="Data analysts",
        niche_tags=["devtools"],
        stage="launched",
        funding_usd=1500000,
        source="hackernews",
        url="https://news.ycombinator.com/item?id=1",
        published_at="2026-03-02",
        fetched_at="2026-11-10",
        text="Cleaned text used for embeddings",
    )
    assert card.id == "card_8f21"

    profile = StudentProfile(
        user_id="u_12",
        skills=["python", "react"],
        hours_per_week=10,
        weeks_available=12,
        team_size=2,
        compute=ComputeTier.LAPTOP,
        goal=GoalType.PORTFOLIO,
        interests=["education"],
    )
    assert profile.goal == GoalType.PORTFOLIO

    evidence = EvidenceItem(
        evidence_id="card_8f21#c2",
        card_id="card_8f21",
        quote="Export is slow",
        source="hackernews",
        url="https://news.ycombinator.com/item?id=1",
        retrieved_at="2026-11-10T00:00:00Z",
    )
    score = DimensionScore(
        dimension=DimensionName.DEMAND_PAIN,
        score=3.5,
        confidence=0.7,
        evidence_ids=[evidence.evidence_id],
        features={"n_sources": 4, "trend_growth": 0.31},
        reason="Recurring problem cited in card_8f21#c2",
        rubric_version="demand_pain@v1",
        model="scorer-lora@v1",
    )
    assert score.score == 3.5

    trace = TraceRecord(
        run_id="run_90",
        step_id=1,
        parent_step=None,
        agent="competition_scorer",
        kind=TraceKind.TOOL_CALL,
        tool="search_kb",
        tokens_in=812,
        tokens_out=140,
        cost_usd=0.0004,
        latency_ms=930,
        ts="2026-11-28T00:00:00Z",
    )
    assert trace.run_id == "run_90"


def test_configs_load_and_validate() -> None:
    config_dir = ROOT / "config"
    weights = load_weights(config_dir)
    assert set(weights.keys()) == {GoalType.STARTUP, GoalType.PORTFOLIO, GoalType.COURSE_PROJECT}
    thresholds = load_thresholds(config_dir)
    assert thresholds["T_go"] == 70.0
    assert thresholds["T_no"] == 50.0
    assert thresholds["floor"] == 1.5
    budgets = load_budgets(config_dir)
    assert budgets["per_run"]["max_debate_rounds"] == 3
