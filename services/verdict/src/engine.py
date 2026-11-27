"""Deterministic M11 Verdict Engine (no LLM calls)."""

from typing import Any

from shared.schemas import (
    DimensionName,
    DimensionScore,
    GatesResult,
    GateStatus,
    SensitivityResult,
    StabilityLabel,
    Verdict,
    VerdictLabel,
    VerdictRequest,
    VerdictVersions,
    WhatIfRequest,
    WhatIfSuggestion,
)

ENGINE_VERSION = "m11@v1"

FIRST_FIVE_DIMENSIONS: tuple[DimensionName, ...] = (
    DimensionName.DEMAND_PAIN,
    DimensionName.COMPETITION,
    DimensionName.DIFFERENTIATION,
    DimensionName.FEASIBILITY,
    DimensionName.RISK,
)


def _index_scores(scores: list[DimensionScore]) -> dict[DimensionName, DimensionScore]:
    indexed: dict[DimensionName, DimensionScore] = {}
    for item in scores:
        if item.dimension in indexed:
            raise ValueError(f"Duplicate score for dimension: {item.dimension.value}")
        indexed[item.dimension] = item
    missing = [dim.value for dim in DimensionName if dim not in indexed]
    if missing:
        raise ValueError(f"Missing dimension scores: {', '.join(missing)}")
    return indexed


def _apply_challenges(
    scores: dict[DimensionName, DimensionScore],
    accepted_objections: dict[DimensionName, int],
    thresholds: dict[str, Any],
) -> dict[DimensionName, DimensionScore]:
    challenge_cfg = thresholds.get("challenge", {})
    score_step = float(challenge_cfg.get("score_penalty_per_objection", 0.5))
    max_drop = float(challenge_cfg.get("max_score_penalty_per_dimension", 1.0))
    conf_step = float(challenge_cfg.get("confidence_penalty_per_objection", 0.1))

    adjusted: dict[DimensionName, DimensionScore] = {}
    for dim, item in scores.items():
        count = max(0, int(accepted_objections.get(dim, 0)))
        if count == 0:
            adjusted[dim] = item
            continue
        score_drop = min(max_drop, count * score_step)
        conf_drop = count * conf_step
        adjusted[dim] = item.model_copy(
            update={
                "score": round(max(0.0, item.score - score_drop), 4),
                "confidence": round(max(0.0, item.confidence - conf_drop), 4),
            }
        )
    return adjusted


def _evaluate_gates(
    request: VerdictRequest,
    scores: dict[DimensionName, DimensionScore],
    thresholds: dict[str, Any],
) -> GatesResult:
    gate_cfg = thresholds.get("gates", {})
    min_sources = int(gate_cfg.get("min_sources", 3))
    min_platforms = int(gate_cfg.get("min_platforms", 2))
    dup_bypass = float(gate_cfg.get("duplicate_differentiation_bypass", 3.0))

    gi = request.gate_inputs
    profile = request.profile
    available_hours = profile.hours_per_week * profile.weeks_available * profile.team_size
    failures: dict[str, str] = {}

    if gi.n_sources >= min_sources and gi.n_platforms >= min_platforms:
        ev_status = GateStatus.PASS
    else:
        ev_status = GateStatus.FAIL
        failures["evidence"] = (
            f"Need >= {min_sources} sources across >= {min_platforms} platforms "
            f"(got {gi.n_sources} sources on {gi.n_platforms} platforms)"
        )

    if gi.estimated_build_hours <= available_hours:
        feas_status = GateStatus.PASS
    else:
        feas_status = GateStatus.FAIL
        gap = round(gi.estimated_build_hours - available_hours, 1)
        failures["feasibility"] = (
            f"Estimated {gi.estimated_build_hours:.1f}h exceeds available "
            f"{available_hours:.1f}h (gap: {gap:.1f}h)"
        )

    if not gi.risk_blockers:
        risk_status = GateStatus.PASS
    else:
        risk_status = GateStatus.FAIL
        failures["risk"] = f"Legal/safety blocker: {'; '.join(gi.risk_blockers)}"

    diff_score = scores[DimensionName.DIFFERENTIATION].score
    if gi.duplicate_product_name is None or diff_score >= dup_bypass:
        dup_status = GateStatus.PASS
    else:
        dup_status = GateStatus.FAIL
        failures["duplicate"] = (
            f"Matches existing product '{gi.duplicate_product_name}' "
            f"with differentiation {diff_score:.1f} < {dup_bypass:.1f}"
        )

    return GatesResult(
        evidence=ev_status,
        feasibility=feas_status,
        risk=risk_status,
        duplicate=dup_status,
        failure_reasons=failures,
    )


def _compute_weighted_score(
    score_values: dict[DimensionName, float],
    weights: dict[DimensionName, float],
) -> float:
    return round(sum(weights[dim] * score_values[dim] for dim in DimensionName) / 5.0, 4)


def _compute_confidence(
    scores: dict[DimensionName, DimensionScore],
    n_sources: int,
) -> float:
    mean_conf = sum(scores[dim].confidence for dim in DimensionName) / len(DimensionName)
    source_factor = min(1.0, n_sources / 5.0)
    return round(0.7 * mean_conf + 0.3 * source_factor, 4)


def _classify_scored_verdict(
    weighted_score: float,
    score_values: dict[DimensionName, float],
    thresholds: dict[str, Any],
) -> tuple[VerdictLabel, DimensionName]:
    t_go = float(thresholds["T_go"])
    t_no = float(thresholds["T_no"])
    floor = float(thresholds["floor"])

    floor_breaches = [dim for dim in FIRST_FIVE_DIMENSIONS if score_values[dim] < floor]
    if weighted_score >= t_go and not floor_breaches:
        verdict = VerdictLabel.GO
    elif weighted_score >= t_no:
        verdict = VerdictLabel.PIVOT
    else:
        verdict = VerdictLabel.NO_GO

    weak_pool = floor_breaches if floor_breaches else list(DimensionName)
    weakest = min(weak_pool, key=lambda d: score_values[d])
    return verdict, weakest


def _run_sensitivity(
    base_verdict: VerdictLabel,
    score_values: dict[DimensionName, float],
    scores: dict[DimensionName, DimensionScore],
    weights: dict[DimensionName, float],
    thresholds: dict[str, Any],
    duplicate_product_name: str | None,
) -> SensitivityResult:
    sens_cfg = thresholds.get("sensitivity", {})
    weight_delta_pct = float(sens_cfg.get("weight_delta_pct", 20.0))
    score_delta = float(sens_cfg.get("least_confident_score_delta", 1.0))
    dup_bypass = float(
        thresholds.get("gates", {}).get("duplicate_differentiation_bypass", 3.0)
    )

    runs = 0
    flipped = 0
    triggers: list[str] = []

    for dim in DimensionName:
        other_sum = 100.0 - weights[dim]
        for sign in (1.0, -1.0):
            runs += 1
            delta = sign * weights[dim] * (weight_delta_pct / 100.0)
            perturbed_weights = {
                other: (
                    weights[dim] + delta
                    if other == dim
                    else weights[other] - delta * (weights[other] / other_sum)
                )
                for other in DimensionName
            }
            new_score = _compute_weighted_score(score_values, perturbed_weights)
            new_verdict, _ = _classify_scored_verdict(new_score, score_values, thresholds)
            if new_verdict != base_verdict:
                flipped += 1
                pct_label = f"{int(sign * weight_delta_pct):+d}%"
                triggers.append(
                    f"weight({dim.value} {pct_label}): "
                    f"{base_verdict.value}->{new_verdict.value} ({new_score:.1f})"
                )

    least_confident = min(DimensionName, key=lambda d: scores[d].confidence)
    for delta in (score_delta, -score_delta):
        runs += 1
        perturbed_scores = dict(score_values)
        perturbed_scores[least_confident] = max(
            0.0, min(5.0, score_values[least_confident] + delta)
        )
        if (
            duplicate_product_name is not None
            and perturbed_scores[DimensionName.DIFFERENTIATION] < dup_bypass
        ):
            new_verdict = VerdictLabel.NO_GO
            new_score = _compute_weighted_score(perturbed_scores, weights)
        else:
            new_score = _compute_weighted_score(perturbed_scores, weights)
            new_verdict, _ = _classify_scored_verdict(new_score, perturbed_scores, thresholds)
        if new_verdict != base_verdict:
            flipped += 1
            triggers.append(
                f"score({least_confident.value} {delta:+.1f}): "
                f"{base_verdict.value}->{new_verdict.value} ({new_score:.1f})"
            )

    return SensitivityResult(runs=runs, flipped=flipped, flip_triggers=triggers)


def _find_what_would_make_go(
    base_verdict: VerdictLabel,
    base_stability: StabilityLabel,
    gates: GatesResult,
    score_values: dict[DimensionName, float],
    scores: dict[DimensionName, DimensionScore],
    weights: dict[DimensionName, float],
    thresholds: dict[str, Any],
    duplicate_product_name: str | None,
) -> list[WhatIfSuggestion]:
    if base_verdict == VerdictLabel.GO and base_stability == StabilityLabel.STABLE:
        return []
    if (
        gates.evidence == GateStatus.FAIL
        or gates.risk == GateStatus.FAIL
        or gates.feasibility == GateStatus.FAIL
        or base_verdict == VerdictLabel.INSUFFICIENT_EVIDENCE
    ):
        return []

    dup_bypass = float(
        thresholds.get("gates", {}).get("duplicate_differentiation_bypass", 3.0)
    )
    candidates: list[tuple[int, float, float, WhatIfSuggestion]] = []

    for dim in DimensionName:
        current = score_values[dim]
        if current >= 5.0:
            continue
        best_for_dim: tuple[int, float, float, WhatIfSuggestion] | None = None
        step = 0.5
        while round(current + step, 4) <= 5.0:
            target = round(current + step, 4)
            trial_scores = dict(score_values)
            trial_scores[dim] = target

            if (
                duplicate_product_name is not None
                and trial_scores[DimensionName.DIFFERENTIATION] < dup_bypass
            ):
                step += 0.5
                continue

            trial_weighted = _compute_weighted_score(trial_scores, weights)
            trial_verdict, _ = _classify_scored_verdict(trial_weighted, trial_scores, thresholds)
            if trial_verdict == VerdictLabel.GO:
                sens = _run_sensitivity(
                    trial_verdict,
                    trial_scores,
                    scores,
                    weights,
                    thresholds,
                    duplicate_product_name,
                )
                is_stable = sens.flipped == 0
                priority = 0 if is_stable else 1
                label = (
                    f"Raise {dim.value} from {current:.1f} to {target:.1f}"
                    + (" (stable GO)" if is_stable else " (borderline GO)")
                )
                suggestion = WhatIfSuggestion(
                    change=label,
                    dimension=dim,
                    target_score=target,
                    new_score=round(trial_weighted, 2),
                    new_verdict=VerdictLabel.GO,
                )
                candidate = (priority, step, -trial_weighted, suggestion)
                if best_for_dim is None or candidate[:3] < best_for_dim[:3]:
                    best_for_dim = candidate
                if is_stable:
                    break
            step += 0.5

        if best_for_dim is not None:
            candidates.append(best_for_dim)

    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in candidates[:3]]


def evaluate_verdict(
    request: VerdictRequest,
    weights_by_goal: dict[Any, dict[DimensionName, float]],
    thresholds: dict[str, Any],
    weights_version: str = "w1",
    rubrics_version: str = "r1",
) -> Verdict:
    """Compute a deterministic Verdict from six DimensionScores and a StudentProfile."""
    raw_scores = _index_scores(request.scores)
    adjusted_scores = _apply_challenges(raw_scores, request.accepted_objections, thresholds)
    score_values = {dim: adjusted_scores[dim].score for dim in DimensionName}
    weights = weights_by_goal[request.profile.goal]

    gates = _evaluate_gates(request, adjusted_scores, thresholds)
    weighted_score = _compute_weighted_score(score_values, weights)
    overall_confidence = _compute_confidence(adjusted_scores, request.gate_inputs.n_sources)

    insufficient_reasons: list[str] = []
    min_confidence = float(thresholds.get("min_confidence", 0.5))

    abstained_dims = [
        dim.value
        for dim in DimensionName
        if adjusted_scores[dim].abstained or not adjusted_scores[dim].evidence_ids
    ]

    if gates.evidence == GateStatus.FAIL:
        verdict = VerdictLabel.INSUFFICIENT_EVIDENCE
        insufficient_reasons.append(gates.failure_reasons["evidence"])
        weakest: DimensionName | None = None
        sensitivity = SensitivityResult(runs=0, flipped=0)
        stability = StabilityLabel.STABLE
    elif (
        gates.feasibility == GateStatus.FAIL
        or gates.risk == GateStatus.FAIL
        or gates.duplicate == GateStatus.FAIL
    ):
        verdict = VerdictLabel.NO_GO
        weakest = min(DimensionName, key=lambda d: score_values[d])
        sensitivity = SensitivityResult(runs=0, flipped=0)
        stability = StabilityLabel.STABLE
    elif abstained_dims or overall_confidence < min_confidence:
        verdict = VerdictLabel.INSUFFICIENT_EVIDENCE
        if abstained_dims:
            insufficient_reasons.append(
                f"Missing evidence_ids / abstained scorers: {', '.join(abstained_dims)}"
            )
        if overall_confidence < min_confidence:
            insufficient_reasons.append(
                f"Overall confidence {overall_confidence:.2f} < {min_confidence:.2f}"
            )
        weakest = None
        sensitivity = SensitivityResult(runs=0, flipped=0)
        stability = StabilityLabel.STABLE
    else:
        verdict, weakest = _classify_scored_verdict(weighted_score, score_values, thresholds)
        sensitivity = _run_sensitivity(
            verdict,
            score_values,
            adjusted_scores,
            weights,
            thresholds,
            request.gate_inputs.duplicate_product_name,
        )
        stability = (
            StabilityLabel.BORDERLINE if sensitivity.flipped > 0 else StabilityLabel.STABLE
        )

    what_if = _find_what_would_make_go(
        verdict,
        stability,
        gates,
        score_values,
        adjusted_scores,
        weights,
        thresholds,
        request.gate_inputs.duplicate_product_name,
    )

    threshold_snapshot = {
        "T_go": float(thresholds["T_go"]),
        "T_no": float(thresholds["T_no"]),
        "floor": float(thresholds["floor"]),
    }

    return Verdict(
        idea_id=request.idea_id,
        version=request.version,
        run_id=request.run_id,
        verdict=verdict,
        stability=stability,
        score=round(weighted_score, 2),
        confidence=round(overall_confidence, 4),
        gates=gates,
        weights=weights,
        thresholds=threshold_snapshot,
        scores=[adjusted_scores[dim] for dim in DimensionName],
        weakest_dimension=weakest,
        what_would_make_go=what_if,
        sensitivity=sensitivity,
        versions=VerdictVersions(
            engine=ENGINE_VERSION,
            rubrics=rubrics_version,
            profile_weights=weights_version,
        ),
        insufficient_reasons=insufficient_reasons,
    )


def apply_whatif(
    request: WhatIfRequest,
    weights_by_goal: dict[Any, dict[DimensionName, float]],
    thresholds: dict[str, Any],
    weights_version: str = "w1",
    rubrics_version: str = "r1",
) -> Verdict:
    """Apply dimension score overrides and return a new versioned Verdict."""
    base = request.verdict_request
    updated_scores: list[DimensionScore] = []
    for item in base.scores:
        if item.dimension in request.dimension_override:
            new_val = max(0.0, min(5.0, float(request.dimension_override[item.dimension])))
            updated_scores.append(item.model_copy(update={"score": new_val}))
        else:
            updated_scores.append(item)

    new_request = base.model_copy(
        update={
            "version": base.version + 1,
            "scores": updated_scores,
        }
    )
    return evaluate_verdict(
        new_request,
        weights_by_goal=weights_by_goal,
        thresholds=thresholds,
        weights_version=weights_version,
        rubrics_version=rubrics_version,
    )
