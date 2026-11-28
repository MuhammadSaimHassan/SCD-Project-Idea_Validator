"""Tests for M10t dataset splitting (>=300 examples, >=60 checked, split by idea)."""

import json
from pathlib import Path

from jobs.finetune.src.build_dataset import build_dataset
from jobs.finetune.src.evaluate_models import run_benchmark

ROOT = Path(__file__).resolve().parents[3]


def test_build_dataset_splits_by_idea_and_meets_minimums(tmp_path: Path) -> None:
    cards_path = ROOT / "data" / "snapshot" / "cards.jsonl"
    if not cards_path.exists():
        pytest_cards = ROOT / "eval" / "retrieval" / "eval_cards.jsonl"
        cards_path = pytest_cards

    summary = build_dataset(cards_path, tmp_path, num_ideas=65, eval_ratio=0.2)
    assert summary["total_examples"] >= 300
    assert summary["eval_checked_examples"] >= 60

    train_rows = [
        json.loads(line)
        for line in (tmp_path / "train.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    eval_rows = [
        json.loads(line)
        for line in (tmp_path / "eval_checked.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    train_ideas = {r["idea_id"] for r in train_rows}
    eval_ideas = {r["idea_id"] for r in eval_rows}
    assert train_ideas.isdisjoint(eval_ideas)
    assert all(r["checked_by_human"] is True for r in eval_rows)

    # Check exact chat messages format
    sample = eval_rows[0]
    assert [m["role"] for m in sample["messages"]] == ["system", "user", "assistant"]
    parsed_out = json.loads(sample["messages"][2]["content"])
    assert "score" in parsed_out and "evidence_ids" in parsed_out

    report = run_benchmark(
        tmp_path / "eval_checked.jsonl", tmp_path / "comparison.json"
    )
    assert len(report["comparison"]) == 3
    assert report["failure_case"] is not None
