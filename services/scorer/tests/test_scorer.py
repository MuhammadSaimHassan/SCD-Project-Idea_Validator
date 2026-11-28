"""Unit and API tests for M10 Scoring Model Server (validation, retry, fallback)."""

import json

from fastapi.testclient import TestClient

from services.scorer.src.config import ScorerSettings
from services.scorer.src.main import create_app
from shared.schemas import DimensionName, EvidenceItem, ScoreRequest


class FlakyOnceBackend:
    """Returns invalid JSON once, then valid JSON on retry."""

    def __init__(self) -> None:
        self.calls = 0

    def generate_score_json(self, req: ScoreRequest) -> str:
        self.calls += 1
        if self.calls == 1:
            return "NOT VALID JSON {{"
        return json.dumps(
            {
                "score": 4.0,
                "confidence": 0.85,
                "evidence_ids": [req.evidence[0].evidence_id],
                "reason": "Recovered on retry",
            }
        )


class AlwaysBrokenBackend:
    """Always outputs invalid schema / hallucinated evidence_ids."""

    def generate_score_json(self, req: ScoreRequest) -> str:
        return json.dumps(
            {
                "score": 5.0,
                "confidence": 0.9,
                "evidence_ids": ["card_fake#c99"],
                "reason": "Hallucinated id",
            }
        )


def _sample_req(with_evidence: bool = True) -> ScoreRequest:
    ev = (
        [
            EvidenceItem(
                evidence_id="card_1#c0",
                card_id="card_1",
                quote="Users complain about manual CSV exports",
                source="hackernews",
                url="https://news.ycombinator.com/item?id=1",
                retrieved_at="2026-11-28T00:00:00Z",
            )
        ]
        if with_evidence
        else []
    )
    return ScoreRequest(
        dimension=DimensionName.DEMAND_PAIN,
        rubric_version="demand_pain@v1",
        rubric_text="0..5 scale",
        idea_text="Automated CSV exporter",
        evidence=ev,
        features={"n_sources": 4, "trend_growth": 0.2},
    )


def test_scorer_retries_once_and_succeeds() -> None:
    flaky = FlakyOnceBackend()
    client = TestClient(create_app(ScorerSettings(), primary_backend=flaky))
    resp = client.post("/score", json=_sample_req().model_dump(mode="json"))
    assert resp.status_code == 200
    assert resp.json()["score"] == 4.0
    assert flaky.calls == 2
    assert client.get("/metrics").json()["retries_total"] == 1
    assert client.get("/metrics").json()["fallbacks_total"] == 0


def test_scorer_falls_back_to_hosted_after_retry_fails() -> None:
    client = TestClient(
        create_app(
            ScorerSettings(hosted_llm_model="gemini-2.0-flash"),
            primary_backend=AlwaysBrokenBackend(),
        )
    )
    resp = client.post("/score", json=_sample_req().model_dump(mode="json"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "gemini-2.0-flash"
    assert body["evidence_ids"] == ["card_1#c0"]
    metrics = client.get("/metrics").json()
    assert metrics["retries_total"] == 1
    assert metrics["fallbacks_total"] == 1


def test_scorer_abstains_without_evidence() -> None:
    client = TestClient(create_app(ScorerSettings()))
    resp = client.post("/score", json=_sample_req(with_evidence=False).model_dump(mode="json"))
    assert resp.status_code == 200
    assert resp.json()["abstained"] is True
    assert resp.json()["confidence"] == 0.0
