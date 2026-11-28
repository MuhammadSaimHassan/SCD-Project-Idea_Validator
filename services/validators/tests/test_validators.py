"""Unit and API tests for M9 four parallel validation scorers."""

from pathlib import Path

from fastapi.testclient import TestClient

from services.validators.src.config import ValidatorsSettings
from services.validators.src.main import create_app
from shared.schemas import ComputeTier, DimensionName, GoalType

ROOT = Path(__file__).resolve().parents[3]


def test_validators_score_all_six_dimensions_in_parallel() -> None:
    client = TestClient(create_app(ValidatorsSettings(rubrics_dir=ROOT / "rubrics")))
    assert client.get("/health").status_code == 200
    assert client.get("/ready").json()["parallel_scorers"] == 4

    payload = {
        "idea_text": "Python and React automated CI log triage tool for devtools teams",
        "profile": {
            "user_id": "u_1",
            "skills": ["python", "react"],
            "hours_per_week": 12,
            "weeks_available": 10,
            "team_size": 2,
            "compute": ComputeTier.LAPTOP.value,
            "goal": GoalType.PORTFOLIO.value,
            "interests": ["devtools"],
        },
        "evidence": [
            {
                "evidence_id": "card_10#c0",
                "card_id": "card_10",
                "quote": "CI logs take forever to parse",
                "source": "hackernews",
                "url": "https://news.ycombinator.com/item?id=10",
                "retrieved_at": "2026-11-28T00:00:00Z",
            },
            {
                "evidence_id": "card_20#c0",
                "card_id": "card_20",
                "quote": "Open source CI failure clustering",
                "source": "github",
                "url": "https://github.com/acme/ci",
                "retrieved_at": "2026-11-28T00:00:00Z",
            },
        ],
        "estimated_build_hours": 80.0,
        "trend_growth": 0.25,
        "direct_competitor_count": 2,
        "gap_count": 3,
    }
    resp = client.post("/score-all", json=payload)
    assert resp.status_code == 200
    scores = resp.json()
    assert len(scores) == 6
    assert {s["dimension"] for s in scores} == {d.value for d in DimensionName}
    assert all(not s["abstained"] and len(s["evidence_ids"]) >= 1 for s in scores)


def test_validators_abstain_when_evidence_is_empty() -> None:
    client = TestClient(create_app(ValidatorsSettings(rubrics_dir=ROOT / "rubrics")))
    payload = {
        "idea_text": "Unsupported idea",
        "profile": {
            "user_id": "u_1",
            "skills": ["python"],
            "hours_per_week": 10,
            "weeks_available": 8,
            "team_size": 1,
            "compute": "laptop",
            "goal": "portfolio",
            "interests": [],
        },
        "evidence": [],
    }
    resp = client.post("/score-all", json=payload)
    assert resp.status_code == 200
    scores = resp.json()
    assert all(s["abstained"] is True and s["confidence"] == 0.0 for s in scores)
