from pathlib import Path

from services.agentops.src.budgets import BudgetApprovalRequired
from services.agentops.src.store import TraceStore, replay_recorded_results
from services.orchestrator.src.state_machine import BudgetExceeded, Orchestrator
from shared.schemas import GoalType, StudentProfile


def _profile(tmp_path: Path) -> StudentProfile:
    profile = StudentProfile(
        user_id="u1",
        skills=["python", "fastapi"],
        hours_per_week=15,
        weeks_available=8,
        team_size=2,
        goal=GoalType.COURSE_PROJECT,
        interests=["education"],
    )
    path = tmp_path / "profile.json"
    path.write_text(profile.model_dump_json(), encoding="utf-8")
    return StudentProfile.model_validate_json(path.read_text(encoding="utf-8"))


def test_validate_and_discover_record_traces(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    root = Path(__file__).resolve().parents[3]
    orchestrator = Orchestrator(
        config_dir=root / "config",
        snapshot_path=root / "data/snapshot/cards.jsonl",
        trace_store=TraceStore(tmp_path / "traces"),
    )
    verdict = orchestrator.validate("Student study planning assistant", profile)
    assert verdict.run_id
    assert len(verdict.scores) == 6
    assert orchestrator.traces
    records = TraceStore(tmp_path / "traces").list_run(verdict.run_id)
    replay = replay_recorded_results(records)
    assert replay[-1]["reran_deterministic_verdict"] is True
    assert replay[-1]["matches_recorded_output"] is True

    discovered = orchestrator.discover(profile, max_ideas=3)
    assert discovered["run_id"]
    assert "ideas" in discovered


def test_budget_stop_is_bounded(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    root = Path(__file__).resolve().parents[3]
    orchestrator = Orchestrator(
        config_dir=root / "config",
        snapshot_path=root / "data/snapshot/cards.jsonl",
        max_steps=1,
        trace_store=TraceStore(tmp_path / "traces"),
    )
    try:
        orchestrator.validate("A small student app", profile)
    except BudgetExceeded:
        pass
    else:
        raise AssertionError("BudgetExceeded was not raised")
    assert any(record.error is not None for record in TraceStore(tmp_path / "traces").list_all())


def test_orchestrator_stops_and_records_approval_boundary(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    orchestrator = Orchestrator(
        config_dir=root / "config",
        snapshot_path=root / "data/snapshot/cards.jsonl",
        trace_store=TraceStore(tmp_path / "traces"),
    )
    run_id = orchestrator._begin_run()
    try:
        orchestrator._trace(
            run_id,
            1,
            "model",
            "llm_call",
            {"status": "pending"},
            cost_usd=0.11,
        )
    except BudgetApprovalRequired:
        pass
    else:
        raise AssertionError("Approval threshold did not stop the run")
    trace = TraceStore(tmp_path / "traces").list_run(run_id)
    assert trace[0].error is not None
