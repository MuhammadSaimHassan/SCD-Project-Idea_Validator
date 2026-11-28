"""Integration and unit tests for M1 Gateway, M2 Persistence, Migrations, and Cache."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from services.gateway.src.config import GatewaySettings
from services.gateway.src.main import create_app
from services.gateway.src.services import workflow_service as workflow_module

ROOT = Path(__file__).resolve().parents[3]


def _make_client(tmp_path: Path, *, rate_limit: int = 120, agentops_url: str = "") -> TestClient:
    db_file = tmp_path / "test_m2.db"
    cfg = GatewaySettings(
        database_url=f"sqlite:///{db_file.as_posix()}",
        redis_url="",
        jwt_secret="test-secret-key",
        rate_limit_requests=rate_limit,
        rate_limit_window_seconds=60,
        agentops_url=agentops_url,
        config_dir=ROOT / "config",
    )
    return TestClient(create_app(cfg))


def _auth_and_profile(client: TestClient, email: str = "student@nu.edu.pk") -> dict[str, str]:
    reg = client.post("/auth/register", json={"email": email, "password": "secret-password"})
    assert reg.status_code == 201
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    prof = client.put(
        "/profile",
        headers=headers,
        json={
            "skills": ["python", "react"],
            "hours_per_week": 12,
            "weeks_available": 10,
            "team_size": 2,
            "compute": "laptop",
            "goal": "portfolio",
            "interests": ["devtools", "ai"],
        },
    )
    assert prof.status_code == 200
    assert prof.json()["profile_version"] == 1
    return headers


def test_alembic_migration_creates_all_m2_tables(tmp_path: Path, monkeypatch: object) -> None:
    db_path = tmp_path / "migrated.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    alembic_ini = ROOT / "services" / "gateway" / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(ROOT / "services" / "gateway" / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    tables = set(inspect(engine).get_table_names())
    expected = {
        "users",
        "profiles",
        "ideas",
        "idea_versions",
        "verdicts",
        "dimension_scores",
        "approvals",
        "traces_index",
        "conversations",
        "runs",
    }
    assert expected.issubset(tables)


def test_auth_and_profile_versioning(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    unauth = client.get("/profile")
    assert unauth.status_code == 401

    headers = _auth_and_profile(client)
    dup = client.post(
        "/auth/register", json={"email": "student@nu.edu.pk", "password": "secret-password"}
    )
    assert dup.status_code == 409

    login = client.post(
        "/auth/login", json={"email": "student@nu.edu.pk", "password": "secret-password"}
    )
    assert login.status_code == 200

    updated = client.put(
        "/profile",
        headers=headers,
        json={
            "skills": ["python", "docker"],
            "hours_per_week": 15,
            "weeks_available": 10,
            "team_size": 2,
            "compute": "laptop",
            "goal": "startup",
            "interests": ["devtools"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["profile_version"] == 2


def test_versioned_cache_hits_and_invalidation(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    headers = _auth_and_profile(client)
    idea_payload = {
        "title": "CI Log Triage",
        "idea_text": "Cluster noisy GitHub Actions logs for student teams using local embeddings.",
    }

    r1 = client.post("/validate", headers=headers, json=idea_payload)
    assert r1.status_code == 202
    run1 = client.get(f"/runs/{r1.json()['run_id']}", headers=headers).json()
    assert run1["result"]["cache_hit"] is False

    # Second identical request hits cache
    r2 = client.post("/validate", headers=headers, json=idea_payload)
    assert r2.status_code == 202
    run2 = client.get(f"/runs/{r2.json()['run_id']}", headers=headers).json()
    assert run2["result"]["cache_hit"] is True

    metrics_mid = client.get("/metrics").json()
    assert metrics_mid["cache_hits_total"] == 1
    assert metrics_mid["cache_misses_total"] == 1

    # Updating profile bumps profile_version -> cache miss on next validate
    client.put(
        "/profile",
        headers=headers,
        json={
            "skills": ["python"],
            "hours_per_week": 8,
            "weeks_available": 8,
            "team_size": 1,
            "compute": "laptop",
            "goal": "course_project",
            "interests": ["devtools"],
        },
    )
    r3 = client.post("/validate", headers=headers, json=idea_payload)
    run3 = client.get(f"/runs/{r3.json()['run_id']}", headers=headers).json()
    assert run3["result"]["cache_hit"] is False


def test_discover_sse_approval_clarify_challenge_whatif_and_compare(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    headers = _auth_and_profile(client)

    # 1. Discover with budget approval prompt (U4) -> approve -> ranked ideas + SSE (U2, U3)
    disc = client.post(
        "/discover",
        headers=headers,
        json={"niche_wish": "devtools", "max_ideas": 2, "require_deep_search_approval": True},
    )
    assert disc.status_code == 202
    run_id = disc.json()["run_id"]
    run_state = client.get(f"/runs/{run_id}", headers=headers).json()
    assert run_state["status"] == "awaiting_approval"

    approved = client.post(
        f"/runs/{run_id}/approve",
        headers=headers,
        json={"approved": True, "reason": "Proceed within budget"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "completed"
    assert len(approved.json()["result"]["ideas"]) == 2

    sse = client.get(f"/runs/{run_id}/events", headers=headers)
    assert sse.status_code == 200
    assert "text/event-stream" in sse.headers["content-type"]
    assert "event: step" in sse.text

    # 2. Validate with clarifying question (U5)
    val = client.post(
        "/validate",
        headers=headers,
        json={
            "title": "Prompt Diff Tool",
            "idea_text": "Regression testing for local LLM prompts.",
            "needs_clarification": True,
        },
    )
    val_run_id = val.json()["run_id"]
    assert client.get(f"/runs/{val_run_id}", headers=headers).json()["status"] == "awaiting_answer"

    answered = client.post(
        f"/runs/{val_run_id}/answer",
        headers=headers,
        json={"answer": "Targets university ML engineering teams."},
    )
    assert answered.status_code == 200
    assert answered.json()["status"] == "completed"
    idea_id = answered.json()["result"]["verdict"]["idea_id"]

    # 3. Challenge (U8) and What-If (U7) create new versions
    challenged = client.post(
        f"/ideas/{idea_id}/challenge",
        headers=headers,
        json={"dimension": "demand_pain", "claim": "Only 2 complaints are recent"},
    )
    assert challenged.status_code == 200
    assert challenged.json()["version"] == 2

    whatif = client.post(
        f"/ideas/{idea_id}/whatif",
        headers=headers,
        json={"dimension_override": {"competition": 4.5}},
    )
    assert whatif.status_code == 200
    assert whatif.json()["version"] == 3

    versions = client.get(f"/ideas/{idea_id}/versions", headers=headers)
    assert versions.status_code == 200
    assert [v["version"] for v in versions.json()] == [1, 2, 3]

    # 4. Thin evidence -> INSUFFICIENT_EVIDENCE (U10) & Compare (U9)
    thin = client.post(
        "/validate",
        headers=headers,
        json={
            "title": "Niche Idea",
            "idea_text": "Very obscure concept with almost no data.",
            "simulate_thin_evidence": True,
        },
    )
    thin_run = client.get(f"/runs/{thin.json()['run_id']}", headers=headers).json()
    assert thin_run["result"]["verdict"]["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert thin_run["result"]["verdict"]["insufficient_reasons"]

    ideas = client.get("/ideas", headers=headers).json()
    assert len(ideas) >= 2
    comp = client.get(
        f"/compare?left={ideas[0]['idea_id']}&right={ideas[1]['idea_id']}",
        headers=headers,
    )
    assert comp.status_code == 200
    assert len(comp.json()["dimension_deltas"]) == 6


def test_rate_limiting_blocks_excess_requests(tmp_path: Path) -> None:
    client = _make_client(tmp_path, rate_limit=3)
    for _ in range(3):
        resp = client.get("/auth/login")
        assert resp.status_code in (405, 422)
    blocked = client.get("/auth/login")
    assert blocked.status_code == 429
    assert client.get("/metrics").json()["rate_limited_total"] == 1


def test_gateway_emits_workflow_trace_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    emitted: list[tuple[str, object]] = []
    monkeypatch.setattr(
        workflow_module,
        "emit_trace",
        lambda url, record: emitted.append((url, record)),
    )
    client = _make_client(tmp_path, agentops_url="http://agentops")
    headers = _auth_and_profile(client)
    response = client.post(
        "/validate",
        headers=headers,
        json={"title": "Student Planner", "idea_text": "A student study-planning tool."},
    )
    assert response.status_code == 202
    assert len(emitted) == 2
    assert all(url == "http://agentops" for url, _ in emitted)
