"""Starter health and readiness tests for M1 API Gateway."""

from fastapi.testclient import TestClient

from services.gateway.src.main import app

client = TestClient(app)


def test_gateway_health_and_ready() -> None:
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json() == {"status": "ok", "service": "gateway"}

    ready_resp = client.get("/ready")
    assert ready_resp.status_code == 200
    body = ready_resp.json()
    assert body["status"] == "ready"
    assert body["schema"] == "StudentProfile"
