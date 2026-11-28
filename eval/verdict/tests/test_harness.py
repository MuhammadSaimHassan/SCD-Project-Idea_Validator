from pathlib import Path
from typing import Literal

import pytest
from eval.verdict.harness import (
    HumanLabel,
    TuningCase,
    VerdictConfig,
    assert_no_finetune_overlap,
    config_to_dict,
    confusion_report,
    load_cases,
    tune_on_training,
)

from shared.config import load_thresholds, load_weights_config
from shared.schemas import (
    DimensionName,
    DimensionScore,
    GoalType,
    StudentProfile,
    VerdictLabel,
    VerdictRequest,
)
from shared.schemas.contracts import GateInputs


def _case(case_id: str, split: Literal["train", "holdout"], verdict: VerdictLabel) -> TuningCase:
    profile = StudentProfile(
        user_id="labelled",
        hours_per_week=10,
        weeks_available=8,
        team_size=1,
        goal=GoalType.COURSE_PROJECT,
    )
    scores = [
        DimensionScore(
            dimension=dimension,
            score=4.0,
            confidence=0.9,
            evidence_ids=["card#c1"],
            reason="Human-labelled evaluation fixture",
            rubric_version=f"{dimension.value}@v1",
            model="test",
        )
        for dimension in DimensionName
    ]
    request = VerdictRequest(
        idea_id=case_id,
        version=1,
        run_id=f"run-{case_id}",
        profile=profile,
        scores=scores,
        gate_inputs=GateInputs(
            n_sources=3,
            n_platforms=2,
            estimated_build_hours=20,
        ),
    )
    return TuningCase(
        case_id=case_id,
        split=split,
        idea_text=f"A distinctive student product idea number {case_id} for evaluation.",
        request=request,
        labels=[
            HumanLabel(reviewer="Member A", verdict=verdict),
            HumanLabel(reviewer="Member B", verdict=verdict),
        ],
        adjudicated_verdict=verdict,
        adjudicator="Both",
    )


def test_tuning_uses_only_training_split(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    weights_version, weights = load_weights_config(root / "config")
    baseline = VerdictConfig(weights_version, weights, load_thresholds(root / "config"))
    cases = [
        _case("train-1", "train", VerdictLabel.GO),
        _case("train-2", "train", VerdictLabel.GO),
        _case("holdout-1", "holdout", VerdictLabel.NO_GO),
    ]
    tuned = tune_on_training(cases, baseline)
    changed_holdout = [
        cases[0],
        cases[1],
        _case("holdout-1", "holdout", VerdictLabel.INSUFFICIENT_EVIDENCE),
    ]
    tuned_without_holdout = tune_on_training(changed_holdout, baseline)
    assert config_to_dict(tuned) == config_to_dict(tuned_without_holdout)


def test_confusion_report_counts_go_for_human_no_go() -> None:
    root = Path(__file__).resolve().parents[3]
    version, weights = load_weights_config(root / "config")
    config = VerdictConfig(version, weights, load_thresholds(root / "config"))
    report = confusion_report([_case("one", "holdout", VerdictLabel.NO_GO)], config)
    assert report["go_when_human_no_go"] == 1
    assert report["confusion_matrix"]["NO-GO"]["GO"] == 1


def test_dataset_rejects_missing_independent_reviewer() -> None:
    case = _case("one", "train", VerdictLabel.GO).model_dump(mode="json")
    case["labels"][1]["reviewer"] = case["labels"][0]["reviewer"]
    with pytest.raises(ValueError, match="different reviewers"):
        TuningCase.model_validate(case)


def test_loader_refuses_missing_human_dataset(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="human-labelled dataset"):
        load_cases(tmp_path / "not-provided.jsonl")


def test_loads_labelled_split_and_rejects_finetuning_overlap(tmp_path: Path) -> None:
    labels = [
        VerdictLabel.GO,
        VerdictLabel.PIVOT,
        VerdictLabel.NO_GO,
        VerdictLabel.INSUFFICIENT_EVIDENCE,
    ]
    cases = [
        _case(
            f"idea-{index}",
            "train" if index < 20 else "holdout",
            labels[index % len(labels)],
        )
        for index in range(25)
    ]
    dataset = tmp_path / "labeled.jsonl"
    dataset.write_text(
        "".join(case.model_dump_json() + "\n" for case in cases),
        encoding="utf-8",
    )
    assert len(load_cases(dataset)) == 25

    finetune = tmp_path / "train.jsonl"
    finetune.write_text('{"idea_id":"idea-0","messages":[]}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="overlap by idea_id"):
        assert_no_finetune_overlap(cases, [finetune])
