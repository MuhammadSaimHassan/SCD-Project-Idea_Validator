from pathlib import Path

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
    )
    verdict = orchestrator.validate("Student study planning assistant", profile)
    assert verdict.run_id
    assert len(verdict.scores) == 6
    assert orchestrator.traces

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
    )
    try:
        orchestrator.validate("A small student app", profile)
    except BudgetExceeded:
        pass
    else:
        raise AssertionError("BudgetExceeded was not raised")
