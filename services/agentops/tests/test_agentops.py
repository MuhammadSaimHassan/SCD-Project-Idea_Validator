from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.agentops.src import main as agentops_main
from services.agentops.src.budgets import (
    BudgetApprovalRequired,
    BudgetLimitExceeded,
    BudgetTracker,
)
from services.agentops.src.drift import build_drift_report
from services.agentops.src.registry import registry_snapshot
from services.agentops.src.store import TraceStore, metrics_snapshot, replay_recorded_results
from shared.schemas import IdeaCard, TraceKind, TraceRecord, VerdictLabel


def _record(run_id: str = "run_1", step_id: int = 1) -> TraceRecord:
    return TraceRecord(
        run_id=run_id,
        step_id=step_id,
        agent="fetcher",
        kind=TraceKind.TOOL_CALL,
        tool="search",
        input={"query": "test"},
        output={"results": ["stored"]},
        tokens_in=3,
        tokens_out=2,
        cost_usd=0.01,
        latency_ms=20,
        ts=datetime.now(UTC),
    )


def _card(card_id: str, source: str, niche: str) -> IdeaCard:
    return IdeaCard(
        id=card_id,
        name=f"{niche} tool",
        summary=f"A {niche} product",
        problem=f"Manual {niche} workflows",
        customer="small teams",
        niche_tags=[niche],
        source=source,
        url=f"https://example.com/{card_id}",
        fetched_at="2026-01-01",
        text=f"{niche} workflow product",
    )


def test_jsonl_trace_replay_and_metrics(tmp_path: Path) -> None:
    store = TraceStore(tmp_path)
    store.append(_record())

    records = store.list_run("run_1")
    replay = replay_recorded_results(records)
    metrics = metrics_snapshot(records)

    assert replay[0]["output"] == {"results": ["stored"]}
    assert replay[0]["used_recorded_result"] is True
    assert metrics["tokens_total"] == 5
    assert metrics["cost_usd_total"] == 0.01
    assert metrics["latency_by_agent"]["fetcher"]["latency_ms_average"] == 20
    with pytest.raises(ValueError):
        store.list_run("../outside")


def test_budget_approval_and_hard_caps() -> None:
    tracker = BudgetTracker(
        {
            "max_tokens": 10,
            "max_pages_fetched": 2,
            "max_steps": 3,
            "max_cost_usd": 0.25,
            "require_approval_over_usd": 0.10,
        }
    )
    tracker.consume(tokens=4, steps=1, cost_usd=0.08)
    with pytest.raises(BudgetApprovalRequired):
        tracker.consume(tokens=2, steps=1, cost_usd=0.04)
    assert tracker.usage.tokens == 4
    tracker.consume(tokens=2, steps=1, cost_usd=0.04, approved=True)
    with pytest.raises(BudgetLimitExceeded):
        tracker.consume(pages_fetched=3)


def test_drift_report_and_registry() -> None:
    before = [_card("a", "hn", "education")]
    after = before + [_card("b", "github", "fintech")]
    report = build_drift_report(
        before,
        after,
        [VerdictLabel.GO],
        [VerdictLabel.NO_GO, VerdictLabel.GO],
    )
    assert report["cards"]["delta"] == 1
    assert report["verdict_distribution"]["current"] == {"GO": 1, "NO-GO": 1}
    assert report["verdict_distribution"]["available"] is True
    assert report["freshness"]["current_latest_fetched_at"]["hn"] == "2026-01-01"

    root = Path(__file__).resolve().parents[3]
    registry = registry_snapshot(root)
    assert len(registry["prompts"]) == 4
    assert len(registry["rubrics"]) == 6


def test_agentops_http_trace_replay_and_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(agentops_main, "trace_store", TraceStore(tmp_path))
    client = TestClient(agentops_main.app)
    record = _record()

    written = client.post("/trace", json=record.model_dump(mode="json"))
    assert written.status_code == 200
    replay = client.post("/runs/run_1/replay")
    assert replay.status_code == 200
    assert replay.json()["steps"][0]["used_recorded_result"] is True
    assert "agentops_trace_records_total 1" in client.get("/metrics").text
    assert "AgenticOps dashboard" in client.get("/dashboard").text
    assert client.get("/dashboard/data").json()["runs_total"] == 1
    assert client.get("/registry").status_code == 200
