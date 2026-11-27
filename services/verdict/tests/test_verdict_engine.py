"""Unit and API tests for M11 Verdict Engine and versioned rubrics."""

import ast
from pathlib import Path

from fastapi.testclient import TestClient

from services.verdict.src.engine import apply_whatif, evaluate_verdict
from services.verdict.src.main import app
from shared.config import load_rubrics, load_thresholds, load_weights_config
from shared.schemas import (
    ComputeTier,
    DimensionName,
    DimensionScore,
    GateStatus,
    GoalType,
    StabilityLabel,
    StudentProfile,
    VerdictLabel,
    VerdictRequest,
    WhatIfRequest,
)
from shared.schemas.contracts import GateInputs

ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "config"
RUBRICS_DIR = ROOT / "rubrics"

client = TestClient(app)


def _profile(goal: GoalType = GoalType.PORTFOLIO) -> StudentProfile:
    return StudentProfile(
        user_id="u_test",
        skills=["python", "react"],
        hours_per_week=10,
        weeks_available=12,
        team_size=1,
        compute=ComputeTier.LAPTOP,
        goal=goal,
        interests=["devtools"],
    )


def _make_scores(
    values: dict[DimensionName, float] | None = None,
    confidences: dict[DimensionName, float] | None = None,
    with_evidence: bool = True,
) -> list[DimensionScore]:
    defaults = {
        DimensionName.DEMAND_PAIN: 4.0,
        DimensionName.COMPETITION: 4.0,
        DimensionName.DIFFERENTIATION: 4.0,
        DimensionName.FEASIBILITY: 4.0,
        DimensionName.RISK: 4.0,
        DimensionName.LEARNING: 4.0,
    }
    if values:
        defaults.update(values)
    conf_defaults = {dim: 0.85 for dim in DimensionName}
    if confidences:
        conf_defaults.update(confidences)

    return [
        DimensionScore(
            dimension=dim,
            score=defaults[dim],
            confidence=conf_defaults[dim],
            evidence_ids=[f"card_{idx}#c0"] if with_evidence else [],
            features={"n_sources": 5},
            reason=f"Evidence-backed score for {dim.value}",
            rubric_version=f"{dim.value}@v1",
            model="scorer-lora@v1",
        )
        for idx, dim in enumerate(DimensionName, start=1)
    ]


def _request(
    values: dict[DimensionName, float] | None = None,
    confidences: dict[DimensionName, float] | None = None,
    goal: GoalType = GoalType.PORTFOLIO,
    n_sources: int = 5,
    n_platforms: int = 3,
    estimated_build_hours: float = 80.0,
    risk_blockers: list[str] | None = None,
    duplicate_product_name: str | None = None,
    accepted_objections: dict[DimensionName, int] | None = None,
    with_evidence: bool = True,
) -> VerdictRequest:
    return VerdictRequest(
        idea_id="idea_test",
        version=1,
        run_id="run_test",
        profile=_profile(goal=goal),
        scores=_make_scores(values, confidences, with_evidence=with_evidence),
        gate_inputs=GateInputs(
            n_sources=n_sources,
            n_platforms=n_platforms,
            estimated_build_hours=estimated_build_hours,
            risk_blockers=risk_blockers or [],
            duplicate_product_name=duplicate_product_name,
        ),
        accepted_objections=accepted_objections or {},
    )


def test_rubrics_complete_for_all_dimensions() -> None:
    rubrics = load_rubrics(RUBRICS_DIR)
    assert set(rubrics.keys()) == set(DimensionName)
    for dim, data in rubrics.items():
        assert data["dimension"] == dim.value
        anchors = data["anchors"]
        for level in range(6):
            assert level in anchors
        example_levels = {int(ex["level"]) for ex in data["examples"]}
        assert example_levels == {0, 1, 2, 3, 4, 5}


def test_verdict_service_imports_no_llm_clients() -> None:
    forbidden = {"openai", "anthropic", "google", "litellm", "langchain", "llama_cpp", "torch"}
    for path in (ROOT / "services" / "verdict" / "src").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden


def test_worked_example_from_description_section_5_4() -> None:
    """Reproduce exact 70.5 GO -> ~69.9 PIVOT (BORDERLINE) -> 73.5 STABLE GO."""
    w_ver, weights = load_weights_config(CONFIG_DIR)
    thresholds = load_thresholds(CONFIG_DIR)

    req = _request(
        values={
            DimensionName.DEMAND_PAIN: 3.5,
            DimensionName.COMPETITION: 2.0,
            DimensionName.DIFFERENTIATION: 3.0,
            DimensionName.FEASIBILITY: 4.0,
            DimensionName.RISK: 3.5,
            DimensionName.LEARNING: 4.5,
        },
        confidences={
            DimensionName.DEMAND_PAIN: 0.8,
            DimensionName.COMPETITION: 0.7,
            DimensionName.DIFFERENTIATION: 0.75,
            DimensionName.FEASIBILITY: 0.85,
            DimensionName.RISK: 0.8,
            DimensionName.LEARNING: 0.9,
        },
        goal=GoalType.PORTFOLIO,
    )

    verdict_v1 = evaluate_verdict(req, weights, thresholds, weights_version=w_ver)
    assert verdict_v1.score == 70.5
    assert verdict_v1.verdict == VerdictLabel.GO
    assert verdict_v1.stability == StabilityLabel.BORDERLINE
    assert verdict_v1.sensitivity.runs == 14
    assert verdict_v1.sensitivity.flipped >= 1
    assert any(
        "feasibility -20%" in t and "69.9" in t
        for t in verdict_v1.sensitivity.flip_triggers
    )
    assert verdict_v1.what_would_make_go
    comp_suggestions = [
        s for s in verdict_v1.what_would_make_go if s.dimension == DimensionName.COMPETITION
    ]
    assert comp_suggestions and comp_suggestions[0].target_score == 3.0

    verdict_v2 = apply_whatif(
        WhatIfRequest(
            verdict_request=req,
            dimension_override={DimensionName.COMPETITION: 3.0},
        ),
        weights,
        thresholds,
        weights_version=w_ver,
    )
    assert verdict_v2.version == 2
    assert verdict_v2.score == 73.5
    assert verdict_v2.verdict == VerdictLabel.GO
    assert verdict_v2.stability == StabilityLabel.STABLE


def test_deterministic_output() -> None:
    w_ver, weights = load_weights_config(CONFIG_DIR)
    thresholds = load_thresholds(CONFIG_DIR)
    req = _request()
    first = evaluate_verdict(req, weights, thresholds, weights_version=w_ver)
    second = evaluate_verdict(req, weights, thresholds, weights_version=w_ver)
    assert first.model_dump() == second.model_dump()


def test_hard_gates() -> None:
    w_ver, weights = load_weights_config(CONFIG_DIR)
    thresholds = load_thresholds(CONFIG_DIR)

    # 1. Evidence gate fail -> INSUFFICIENT_EVIDENCE
    ev_fail = evaluate_verdict(
        _request(n_sources=2, n_platforms=1), weights, thresholds, weights_version=w_ver
    )
    assert ev_fail.gates.evidence == GateStatus.FAIL
    assert ev_fail.verdict == VerdictLabel.INSUFFICIENT_EVIDENCE
    assert ev_fail.insufficient_reasons

    # 2. Feasibility gate fail -> NO-GO with hours gap
    feas_fail = evaluate_verdict(
        _request(estimated_build_hours=200.0), weights, thresholds, weights_version=w_ver
    )
    assert feas_fail.gates.feasibility == GateStatus.FAIL
    assert feas_fail.verdict == VerdictLabel.NO_GO
    assert "80.0h" in feas_fail.gates.failure_reasons["feasibility"]

    # 3. Risk gate fail -> NO-GO with blocker named
    risk_fail = evaluate_verdict(
        _request(risk_blockers=["Violates platform TOS"]),
        weights,
        thresholds,
        weights_version=w_ver,
    )
    assert risk_fail.gates.risk == GateStatus.FAIL
    assert risk_fail.verdict == VerdictLabel.NO_GO
    assert "Violates platform TOS" in risk_fail.gates.failure_reasons["risk"]

    # 4. Duplicate gate fail when differentiation < 3.0, pass when >= 3.0
    dup_fail = evaluate_verdict(
        _request(
            values={DimensionName.DIFFERENTIATION: 2.5},
            duplicate_product_name="CloneTool",
        ),
        weights,
        thresholds,
        weights_version=w_ver,
    )
    assert dup_fail.gates.duplicate == GateStatus.FAIL
    assert dup_fail.verdict == VerdictLabel.NO_GO
    assert "CloneTool" in dup_fail.gates.failure_reasons["duplicate"]

    dup_pass = evaluate_verdict(
        _request(
            values={DimensionName.DIFFERENTIATION: 3.0},
            duplicate_product_name="CloneTool",
        ),
        weights,
        thresholds,
        weights_version=w_ver,
    )
    assert dup_pass.gates.duplicate == GateStatus.PASS
    assert dup_pass.verdict == VerdictLabel.GO


def test_confidence_and_abstention_give_insufficient_evidence() -> None:
    w_ver, weights = load_weights_config(CONFIG_DIR)
    thresholds = load_thresholds(CONFIG_DIR)

    low_conf = evaluate_verdict(
        _request(
            confidences={dim: 0.2 for dim in DimensionName},
            n_sources=3,
        ),
        weights,
        thresholds,
        weights_version=w_ver,
    )
    assert low_conf.confidence < 0.5
    assert low_conf.verdict == VerdictLabel.INSUFFICIENT_EVIDENCE

    abstained = evaluate_verdict(
        _request(with_evidence=False),
        weights,
        thresholds,
        weights_version=w_ver,
    )
    assert abstained.verdict == VerdictLabel.INSUFFICIENT_EVIDENCE


def test_thresholds_floor_and_challenge_penalties() -> None:
    w_ver, weights = load_weights_config(CONFIG_DIR)
    thresholds = load_thresholds(CONFIG_DIR)

    # High score but floor breach on one of the first 5 dimensions -> PIVOT
    floor_breach = evaluate_verdict(
        _request(
            values={
                DimensionName.DEMAND_PAIN: 1.4,
                DimensionName.COMPETITION: 5.0,
                DimensionName.DIFFERENTIATION: 5.0,
                DimensionName.FEASIBILITY: 5.0,
                DimensionName.RISK: 5.0,
                DimensionName.LEARNING: 5.0,
            }
        ),
        weights,
        thresholds,
        weights_version=w_ver,
    )
    assert floor_breach.score > 70.0
    assert floor_breach.verdict == VerdictLabel.PIVOT
    assert floor_breach.weakest_dimension == DimensionName.DEMAND_PAIN

    # Learning below 1.5 does NOT breach floor (floor applies to first 5 dimensions)
    learning_low = evaluate_verdict(
        _request(
            values={
                DimensionName.DEMAND_PAIN: 5.0,
                DimensionName.COMPETITION: 5.0,
                DimensionName.DIFFERENTIATION: 5.0,
                DimensionName.FEASIBILITY: 5.0,
                DimensionName.RISK: 5.0,
                DimensionName.LEARNING: 1.0,
            }
        ),
        weights,
        thresholds,
        weights_version=w_ver,
    )
    assert learning_low.verdict == VerdictLabel.GO

    # Score below T_no (50) -> NO-GO
    low_score = evaluate_verdict(
        _request(values={dim: 2.0 for dim in DimensionName}),
        weights,
        thresholds,
        weights_version=w_ver,
    )
    assert low_score.score == 40.0
    assert low_score.verdict == VerdictLabel.NO_GO

    # Challenge: 3 accepted objections -> capped at -1.0 score and -0.3 confidence
    challenged = evaluate_verdict(
        _request(accepted_objections={DimensionName.DEMAND_PAIN: 3}),
        weights,
        thresholds,
        weights_version=w_ver,
    )
    demand_score = next(
        s for s in challenged.scores if s.dimension == DimensionName.DEMAND_PAIN
    )
    assert demand_score.score == 3.0
    assert demand_score.confidence == 0.55


def test_verdict_and_whatif_http_endpoints() -> None:
    req = _request(values={DimensionName.COMPETITION: 2.0})
    resp = client.post("/verdict", json=req.model_dump(mode="json"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "GO"
    assert body["versions"]["engine"] == "m11@v1"

    whatif_payload = WhatIfRequest(
        verdict_request=req,
        dimension_override={DimensionName.COMPETITION: 4.0},
    )
    whatif_resp = client.post("/whatif", json=whatif_payload.model_dump(mode="json"))
    assert whatif_resp.status_code == 200
    assert whatif_resp.json()["version"] == 2
    assert whatif_resp.json()["score"] > body["score"]
