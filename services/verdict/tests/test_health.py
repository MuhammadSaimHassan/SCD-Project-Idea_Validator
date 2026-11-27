"""Starter health and readiness tests for M11 Verdict Engine."""

from fastapi.testclient import TestClient

from services.verdict.src.main import app

client = TestClient(app)


def test_verdict_health_and_ready() -> None:
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json() == {"status": "ok", "service": "verdict"}

    ready_resp = client.get("/ready")
    assert ready_resp.status_code == 200
    body = ready_resp.json()
    assert body["status"] == "ready"
    assert body["goal_presets"] == 3
    assert body["t_go"] == 70.0
    assert body["schema"] == "Verdict"
