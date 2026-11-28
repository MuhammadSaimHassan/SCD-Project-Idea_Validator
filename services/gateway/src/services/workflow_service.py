"""M1 workflow orchestration adapter, caching, challenge, and what-if logic."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from services.agentops.src.client import emit_trace
from services.gateway.src.repositories.cache import VersionedCache, verdict_cache_key
from services.gateway.src.repositories.idea_repo import IdeaRepository
from services.gateway.src.repositories.run_repo import RunRepository
from services.gateway.src.repositories.user_repo import UserRepository
from services.gateway.src.routes.schemas import (
    ApplyWhatIfRequest,
    ApprovalRequest,
    ChallengeRequest,
    CompareIdeasResponse,
    DiscoverRequest,
    IdeaSummaryResponse,
    IdeaVersionEntry,
    RunStatusResponse,
    ValidateRunRequest,
)
from shared.config import load_thresholds, load_weights
from shared.schemas import (
    DimensionName,
    DimensionScore,
    GatesResult,
    GateStatus,
    SensitivityResult,
    StabilityLabel,
    StudentProfile,
    TraceKind,
    TraceRecord,
    Verdict,
    VerdictLabel,
    VerdictRequest,
    VerdictVersions,
    WhatIfRequest,
    WhatIfSuggestion,
)
from shared.schemas.contracts import GateInputs


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class WorkflowService:
    """Coordinates M2 persistence, versioned cache, and downstream M3/M11 calls."""

    def __init__(
        self,
        *,
        user_repo: UserRepository,
        idea_repo: IdeaRepository,
        run_repo: RunRepository,
        cache: VersionedCache,
        config_dir: Path,
        rubric_version: str,
        verdict_url: str = "",
        orchestrator_url: str = "",
        agentops_url: str = "",
    ) -> None:
        self._users = user_repo
        self._ideas = idea_repo
        self._runs = run_repo
        self._cache = cache
        self._config_dir = config_dir
        self._rubric_version = rubric_version
        self._verdict_url = verdict_url.rstrip("/")
        self._orchestrator_url = orchestrator_url.rstrip("/")
        self._agentops_url = agentops_url.rstrip("/")

    def _emit_trace_events(self, run_id: str, events: list[dict[str, Any]]) -> None:
        for event in events:
            tool = str(event.get("tool", ""))
            kind = (
                TraceKind.DECISION if tool in {"approval", "user_answer"} else TraceKind.TOOL_CALL
            )
            emit_trace(
                self._agentops_url,
                TraceRecord(
                    run_id=run_id,
                    step_id=int(event["step"]),
                    agent=str(event["agent"]),
                    kind=kind,
                    tool=tool or None,
                    input={"message": str(event.get("message", ""))},
                    output=event,
                    cache_hit=bool(event.get("cache_hit", False)),
                    ts=str(event["ts"]),
                ),
            )

    def _require_profile(self, user_id: str) -> StudentProfile:
        profile = self._users.get_profile(user_id)
        if profile is None:
            raise ValueError("Student profile must be saved before running workflows")
        return profile

    def _call_verdict_engine(self, payload: VerdictRequest) -> Verdict:
        if self._verdict_url:
            resp = httpx.post(
                f"{self._verdict_url}/verdict",
                json=payload.model_dump(mode="json"),
                timeout=10.0,
            )
            resp.raise_for_status()
            return Verdict.model_validate(resp.json())

        return self._local_verdict_fallback(payload)

    def _call_whatif_engine(self, payload: WhatIfRequest) -> Verdict:
        if self._verdict_url:
            resp = httpx.post(
                f"{self._verdict_url}/whatif",
                json=payload.model_dump(mode="json"),
                timeout=10.0,
            )
            resp.raise_for_status()
            return Verdict.model_validate(resp.json())

        base = payload.verdict_request
        updated_scores = [
            s.model_copy(
                update={
                    "score": max(
                        0.0, min(5.0, float(payload.dimension_override[s.dimension]))
                    )
                }
            )
            if s.dimension in payload.dimension_override
            else s
            for s in base.scores
        ]
        next_req = base.model_copy(update={"version": base.version + 1, "scores": updated_scores})
        return self._local_verdict_fallback(next_req)

    def _local_verdict_fallback(self, req: VerdictRequest) -> Verdict:
        """Pure-Python deterministic fallback when M11 container URL is unset."""
        w_ver = "w1"
        weights_map = load_weights(self._config_dir)
        thresholds = load_thresholds(self._config_dir)
        weights = weights_map[req.profile.goal]

        adjusted: list[DimensionScore] = []
        for s in req.scores:
            obj_count = req.accepted_objections.get(s.dimension, 0)
            drop = min(1.0, obj_count * 0.5)
            conf_drop = obj_count * 0.1
            adjusted.append(
                s.model_copy(
                    update={
                        "score": max(0.0, s.score - drop),
                        "confidence": max(0.0, s.confidence - conf_drop),
                    }
                )
            )
        by_dim = {s.dimension: s for s in adjusted}

        avail_hours = (
            req.profile.hours_per_week * req.profile.weeks_available * req.profile.team_size
        )
        ev_ok = req.gate_inputs.n_sources >= 3 and req.gate_inputs.n_platforms >= 2
        feas_ok = req.gate_inputs.estimated_build_hours <= avail_hours
        risk_ok = len(req.gate_inputs.risk_blockers) == 0
        dup_ok = (
            req.gate_inputs.duplicate_product_name is None
            or by_dim[DimensionName.DIFFERENTIATION].score >= 3.0
        )
        failures: dict[str, str] = {}
        if not ev_ok:
            failures["evidence"] = (
                f"Need >=3 sources on >=2 platforms (got {req.gate_inputs.n_sources} "
                f"on {req.gate_inputs.n_platforms})"
            )
        if not feas_ok:
            failures["feasibility"] = (
                f"Estimated {req.gate_inputs.estimated_build_hours:.1f}h exceeds "
                f"{avail_hours:.1f}h"
            )
        if not risk_ok:
            failures["risk"] = "; ".join(req.gate_inputs.risk_blockers)
        if not dup_ok:
            failures["duplicate"] = str(req.gate_inputs.duplicate_product_name)

        gates = GatesResult(
            evidence=GateStatus.PASS if ev_ok else GateStatus.FAIL,
            feasibility=GateStatus.PASS if feas_ok else GateStatus.FAIL,
            risk=GateStatus.PASS if risk_ok else GateStatus.FAIL,
            duplicate=GateStatus.PASS if dup_ok else GateStatus.FAIL,
            failure_reasons=failures,
        )

        weighted = round(sum(weights[d] * by_dim[d].score for d in DimensionName) / 5.0, 2)
        mean_conf = sum(by_dim[d].confidence for d in DimensionName) / 6.0
        conf = round(0.7 * mean_conf + 0.3 * min(1.0, req.gate_inputs.n_sources / 5.0), 4)
        insufficient: list[str] = []
        if not ev_ok:
            label = VerdictLabel.INSUFFICIENT_EVIDENCE
            insufficient.append(failures["evidence"])
        elif not (feas_ok and risk_ok and dup_ok):
            label = VerdictLabel.NO_GO
        elif conf < float(thresholds.get("min_confidence", 0.5)) or any(
            not s.evidence_ids or s.abstained for s in adjusted
        ):
            label = VerdictLabel.INSUFFICIENT_EVIDENCE
            insufficient.append("Insufficient evidence ids or confidence below 0.5")
        elif weighted >= float(thresholds["T_go"]) and all(
            by_dim[d].score >= float(thresholds["floor"])
            for d in (
                DimensionName.DEMAND_PAIN,
                DimensionName.COMPETITION,
                DimensionName.DIFFERENTIATION,
                DimensionName.FEASIBILITY,
                DimensionName.RISK,
            )
        ):
            label = VerdictLabel.GO
        elif weighted >= float(thresholds["T_no"]):
            label = VerdictLabel.PIVOT
        else:
            label = VerdictLabel.NO_GO

        weakest = min(DimensionName, key=lambda d: by_dim[d].score)
        what_if: list[WhatIfSuggestion] = []
        if label == VerdictLabel.PIVOT and weakest != DimensionName.LEARNING:
            bumped = min(5.0, round(by_dim[weakest].score + 1.0, 1))
            what_if.append(
                WhatIfSuggestion(
                    change=f"Improve {weakest.value} from {by_dim[weakest].score:.1f} to {bumped}",
                    dimension=weakest,
                    target_score=bumped,
                    new_score=min(100.0, round(weighted + weights[weakest] / 5.0, 2)),
                    new_verdict=VerdictLabel.GO,
                )
            )

        return Verdict(
            idea_id=req.idea_id,
            version=req.version,
            run_id=req.run_id,
            verdict=label,
            stability=StabilityLabel.STABLE,
            score=weighted,
            confidence=conf,
            gates=gates,
            weights=weights,
            thresholds={
                "T_go": float(thresholds["T_go"]),
                "T_no": float(thresholds["T_no"]),
                "floor": float(thresholds["floor"]),
            },
            scores=adjusted,
            weakest_dimension=weakest if label != VerdictLabel.INSUFFICIENT_EVIDENCE else None,
            what_would_make_go=what_if,
            sensitivity=SensitivityResult(runs=0, flipped=0),
            versions=VerdictVersions(
                engine="m11@v1-fallback",
                rubrics=self._rubric_version,
                profile_weights=w_ver,
            ),
            insufficient_reasons=insufficient,
        )

    def _build_draft_scores(
        self, idea_text: str, profile: StudentProfile, *, thin_evidence: bool
    ) -> tuple[list[DimensionScore], GateInputs]:
        avail = profile.hours_per_week * profile.weeks_available * profile.team_size
        est_hours = min(avail * 0.7, 80.0)
        feas_score = 4.0 if est_hours <= avail else 1.5
        base = 3.5 if len(idea_text) > 40 else 3.0
        if thin_evidence:
            scores = [
                DimensionScore(
                    dimension=dim,
                    score=2.0,
                    confidence=0.3,
                    evidence_ids=[],
                    features={"n_sources": 1},
                    reason="Not enough sources found in KB",
                    rubric_version=f"{dim.value}@v1",
                    model="pending-m10",
                    abstained=True,
                )
                for dim in DimensionName
            ]
            return scores, GateInputs(
                n_sources=1, n_platforms=1, estimated_build_hours=est_hours
            )

        values = {
            DimensionName.DEMAND_PAIN: base,
            DimensionName.COMPETITION: 3.0,
            DimensionName.DIFFERENTIATION: 3.5,
            DimensionName.FEASIBILITY: feas_score,
            DimensionName.RISK: 4.5,
            DimensionName.LEARNING: 4.0,
        }
        scores = [
            DimensionScore(
                dimension=dim,
                score=values[dim],
                confidence=0.8,
                evidence_ids=[f"card_seed_{idx}#c0"],
                features={"n_sources": 4},
                reason=f"Initial evidence citation card_seed_{idx}#c0 for {dim.value}",
                rubric_version=f"{dim.value}@v1",
                model="gateway-bootstrap",
            )
            for idx, dim in enumerate(DimensionName, start=1)
        ]
        return scores, GateInputs(n_sources=4, n_platforms=2, estimated_build_hours=est_hours)

    def start_discover(self, user_id: str, payload: DiscoverRequest) -> RunStatusResponse:
        profile = self._require_profile(user_id)
        run_id = f"run_{uuid.uuid4().hex[:10]}"
        self._runs.create_run(
            run_id=run_id,
            user_id=user_id,
            workflow="discover",
            request_payload=payload.model_dump(mode="json"),
        )
        if payload.require_deep_search_approval:
            events = [
                {
                    "step": 1,
                    "agent": "niches_analyst",
                    "tool": "analyze_niches",
                    "spend_usd": 0.01,
                    "message": "Identified matching niches",
                    "ts": _now_iso(),
                },
                {
                    "step": 2,
                    "agent": "budget_guard",
                    "tool": "deep_scout_check",
                    "spend_usd": 0.12,
                    "message": "Deep search exceeds budget cap ($0.10); waiting for approval",
                    "ts": _now_iso(),
                },
            ]
            row = self._runs.update_run(
                run_id,
                status="awaiting_approval",
                events=events,
                pending_approval={
                    "action": "deep_search",
                    "estimated_cost_usd": 0.12,
                    "message": "Deep scout across 30 external pages costs ~$0.12. Approve?",
                },
            )
            self._emit_trace_events(run_id, events)
            return self._to_run_response(row)

        return self._finish_discover_run(run_id, user_id, profile, payload, [])

    def _finish_discover_run(
        self,
        run_id: str,
        user_id: str,
        profile: StudentProfile,
        payload: DiscoverRequest,
        prior_events: list[dict[str, Any]],
    ) -> RunStatusResponse:
        niche = payload.niche_wish.strip() or (
            profile.interests[0] if profile.interests else "devtools"
        )
        candidates = [
            (
                f"{niche.title()} Gap Monitor",
                f"Automated {niche} pain tracker built for small teams.",
            ),
            (
                f"Lightweight {niche.title()} Validator",
                f"CLI and dashboard helping students scope {niche} projects safely.",
            ),
            (
                f"{niche.title()} Evidence Copilot",
                f"Local-first workflow tool targeting missing features in {niche}.",
            ),
        ][: payload.max_ideas]

        ranked_cards: list[dict[str, Any]] = []
        for idx, (title, idea_text) in enumerate(candidates, start=1):
            idea_id = f"idea_{uuid.uuid4().hex[:8]}"
            scores, gate_inputs = self._build_draft_scores(
                idea_text, profile, thin_evidence=False
            )
            if idx == 2:
                scores[1] = scores[1].model_copy(update={"score": 2.0})
            v_req = VerdictRequest(
                idea_id=idea_id,
                version=1,
                run_id=run_id,
                profile=profile,
                scores=scores,
                gate_inputs=gate_inputs,
            )
            verdict = self._call_verdict_engine(v_req)
            self._ideas.create_idea_with_verdict(
                idea_id=idea_id,
                user_id=user_id,
                title=title,
                source="generated",
                idea_text=idea_text,
                verdict=verdict,
            )
            ranked_cards.append({"title": title, "verdict": verdict.model_dump(mode="json")})

        ranked_cards.sort(key=lambda c: float(c["verdict"]["score"]), reverse=True)
        events = list(prior_events) + [
            {
                "step": len(prior_events) + 1,
                "agent": "ideator",
                "tool": "search_kb",
                "spend_usd": 0.02,
                "message": f"Generated {len(ranked_cards)} candidate ideas in {niche}",
                "ts": _now_iso(),
            },
            {
                "step": len(prior_events) + 2,
                "agent": "verdict_engine",
                "tool": "evaluate_verdict",
                "spend_usd": 0.02,
                "message": "Ranked surviving ideas by deterministic score",
                "ts": _now_iso(),
            },
        ]
        self._ideas.upsert_trace_index(run_id, cost_usd=0.02, latency_ms=120, status="completed")
        row = self._runs.update_run(
            run_id,
            status="completed",
            events=events,
            clear_approval=True,
            result={"ideas": ranked_cards},
        )
        self._emit_trace_events(run_id, events[len(prior_events) :])
        return self._to_run_response(row)

    def start_validate(self, user_id: str, payload: ValidateRunRequest) -> RunStatusResponse:
        profile = self._require_profile(user_id)
        run_id = f"run_{uuid.uuid4().hex[:10]}"
        self._runs.create_run(
            run_id=run_id,
            user_id=user_id,
            workflow="validate",
            request_payload=payload.model_dump(mode="json"),
        )
        if payload.needs_clarification:
            row = self._runs.update_run(
                run_id,
                status="awaiting_answer",
                events=[
                    {
                        "step": 1,
                        "agent": "intake",
                        "tool": "clarify_gate",
                        "spend_usd": 0.002,
                        "message": "Target user group affects duplicate gate; asking student",
                        "ts": _now_iso(),
                    }
                ],
                pending_question={
                    "question": "Who is the primary target user and how is this different?",
                    "field": "target_segment",
                },
            )
            self._emit_trace_events(run_id, json.loads(row.events_json))
            return self._to_run_response(row)

        if payload.require_deep_search_approval:
            row = self._runs.update_run(
                run_id,
                status="awaiting_approval",
                events=[
                    {
                        "step": 1,
                        "agent": "budget_guard",
                        "tool": "deep_scout_check",
                        "spend_usd": 0.11,
                        "message": "External deep search requires approval ($0.11 > $0.10 cap)",
                        "ts": _now_iso(),
                    }
                ],
                pending_approval={
                    "action": "deep_search",
                    "estimated_cost_usd": 0.11,
                    "message": "Approve extra external scouting for ~$0.11?",
                },
            )
            self._emit_trace_events(run_id, json.loads(row.events_json))
            return self._to_run_response(row)

        return self._finish_validate_run(run_id, user_id, profile, payload, [])

    def _finish_validate_run(
        self,
        run_id: str,
        user_id: str,
        profile: StudentProfile,
        payload: ValidateRunRequest,
        prior_events: list[dict[str, Any]],
    ) -> RunStatusResponse:
        w_ver = "w1"
        cache_key = verdict_cache_key(
            payload.idea_text,
            profile.profile_version,
            self._rubric_version,
            w_ver,
        )
        cached, cache_hit = self._cache.get_json(cache_key)
        idea_id = f"idea_{uuid.uuid4().hex[:8]}"

        if cached is not None and not payload.simulate_thin_evidence:
            verdict = Verdict.model_validate(cached).model_copy(
                update={"idea_id": idea_id, "run_id": run_id}
            )
        else:
            scores, gate_inputs = self._build_draft_scores(
                payload.idea_text, profile, thin_evidence=payload.simulate_thin_evidence
            )
            gate_inputs = gate_inputs.model_copy(
                update={"estimated_build_hours": payload.estimated_build_hours}
            )
            v_req = VerdictRequest(
                idea_id=idea_id,
                version=1,
                run_id=run_id,
                profile=profile,
                scores=scores,
                gate_inputs=gate_inputs,
            )
            verdict = self._call_verdict_engine(v_req)
            if not payload.simulate_thin_evidence:
                self._cache.set_json(cache_key, verdict.model_dump(mode="json"))

        self._ideas.create_idea_with_verdict(
            idea_id=idea_id,
            user_id=user_id,
            title=payload.title,
            source="own",
            idea_text=payload.idea_text,
            verdict=verdict,
        )
        events = list(prior_events) + [
            {
                "step": len(prior_events) + 1,
                "agent": "scorers",
                "tool": "score_dimensions",
                "spend_usd": 0.0 if cache_hit else 0.015,
                "cache_hit": cache_hit,
                "message": "Cache hit" if cache_hit else "Scored 6 dimensions with evidence",
                "ts": _now_iso(),
            },
            {
                "step": len(prior_events) + 2,
                "agent": "verdict_engine",
                "tool": "evaluate_verdict",
                "spend_usd": 0.0,
                "message": f"Verdict: {verdict.verdict.value} ({verdict.score})",
                "ts": _now_iso(),
            },
        ]
        self._ideas.upsert_trace_index(
            run_id, cost_usd=0.0 if cache_hit else 0.015, latency_ms=45, status="completed"
        )
        row = self._runs.update_run(
            run_id,
            status="completed",
            events=events,
            clear_question=True,
            clear_approval=True,
            result={"verdict": verdict.model_dump(mode="json"), "cache_hit": cache_hit},
        )
        self._emit_trace_events(run_id, events[len(prior_events) :])
        return self._to_run_response(row)

    def get_run(self, user_id: str, run_id: str) -> RunStatusResponse:
        row = self._runs.get_run(run_id)
        if row is None or row.user_id != user_id:
            raise KeyError("Run not found")
        return self._to_run_response(row)

    def answer_run(
        self, user_id: str, run_id: str, payload: dict[str, Any]
    ) -> RunStatusResponse:
        row = self._runs.get_run(run_id)
        if row is None or row.user_id != user_id:
            raise KeyError("Run not found")
        if row.status != "awaiting_answer":
            raise ValueError(f"Run is not awaiting an answer (status={row.status})")
        profile = self._require_profile(user_id)
        req_data = json.loads(row.request_json)
        req_data["idea_text"] = f"{req_data['idea_text']}\nClarification: {payload['answer']}"
        req_data["needs_clarification"] = False
        events = json.loads(row.events_json)
        events.append(
            {
                "step": len(events) + 1,
                "agent": "intake",
                "tool": "user_answer",
                "spend_usd": 0.0,
                "message": "Received clarifying answer from student",
                "ts": _now_iso(),
            }
        )
        self._emit_trace_events(run_id, [events[-1]])
        return self._finish_validate_run(
            run_id, user_id, profile, ValidateRunRequest.model_validate(req_data), events
        )

    def approve_run(
        self, user_id: str, run_id: str, payload: ApprovalRequest
    ) -> RunStatusResponse:
        row = self._runs.get_run(run_id)
        if row is None or row.user_id != user_id:
            raise KeyError("Run not found")
        if row.status != "awaiting_approval":
            raise ValueError(f"Run is not awaiting approval (status={row.status})")
        decision = "approved" if payload.approved else "declined"
        self._ideas.record_approval(run_id, "deep_search", decision)

        events = json.loads(row.events_json)
        events.append(
            {
                "step": len(events) + 1,
                "agent": "budget_guard",
                "tool": "approval",
                "spend_usd": 0.0,
                "message": f"Deep search {decision} by user",
                "ts": _now_iso(),
            }
        )
        self._emit_trace_events(run_id, [events[-1]])
        if not payload.approved:
            updated = self._runs.update_run(
                run_id,
                status="declined",
                events=events,
                clear_approval=True,
                result={"message": "Stopped at user budget boundary without overspending."},
            )
            return self._to_run_response(updated)

        profile = self._require_profile(user_id)
        req_data = json.loads(row.request_json)
        req_data["require_deep_search_approval"] = False
        if row.workflow == "discover":
            return self._finish_discover_run(
                run_id, user_id, profile, DiscoverRequest.model_validate(req_data), events
            )
        return self._finish_validate_run(
            run_id, user_id, profile, ValidateRunRequest.model_validate(req_data), events
        )

    def challenge_idea(
        self, user_id: str, idea_id: str, payload: ChallengeRequest
    ) -> Verdict:
        idea = self._ideas.get_idea(idea_id)
        if idea is None or idea.user_id != user_id:
            raise KeyError("Idea not found")
        latest = self._ideas.get_latest_version_and_verdict(idea_id)
        if latest is None:
            raise KeyError("No verdict found for idea")
        ver_row, prev_verdict = latest
        profile = self._require_profile(user_id)

        run_id = f"run_{uuid.uuid4().hex[:10]}"
        verdict_req = VerdictRequest(
            idea_id=idea_id,
            version=prev_verdict.version + 1,
            run_id=run_id,
            profile=profile,
            scores=prev_verdict.scores,
            gate_inputs=GateInputs(
                n_sources=4,
                n_platforms=2,
                estimated_build_hours=60.0,
            ),
            accepted_objections={payload.dimension: 1},
        )
        new_verdict = self._call_verdict_engine(verdict_req)
        self._ideas.add_version_with_verdict(
            idea_id=idea_id,
            idea_text=f"{ver_row.text}\n[Challenge on {payload.dimension.value}]: {payload.claim}",
            verdict=new_verdict,
        )
        return new_verdict

    def whatif_idea(
        self, user_id: str, idea_id: str, payload: ApplyWhatIfRequest
    ) -> Verdict:
        idea = self._ideas.get_idea(idea_id)
        if idea is None or idea.user_id != user_id:
            raise KeyError("Idea not found")
        latest = self._ideas.get_latest_version_and_verdict(idea_id)
        if latest is None:
            raise KeyError("No verdict found for idea")
        ver_row, prev_verdict = latest
        profile = self._require_profile(user_id)

        run_id = f"run_{uuid.uuid4().hex[:10]}"
        base_req = VerdictRequest(
            idea_id=idea_id,
            version=prev_verdict.version,
            run_id=run_id,
            profile=profile,
            scores=prev_verdict.scores,
            gate_inputs=GateInputs(
                n_sources=4,
                n_platforms=2,
                estimated_build_hours=60.0,
            ),
        )
        new_verdict = self._call_whatif_engine(
            WhatIfRequest(
                verdict_request=base_req,
                dimension_override=payload.dimension_override,
            )
        )
        self._ideas.add_version_with_verdict(
            idea_id=idea_id,
            idea_text=f"{ver_row.text}\n[What-If applied: {payload.dimension_override}]",
            verdict=new_verdict,
        )
        return new_verdict

    def list_ideas(self, user_id: str) -> list[IdeaSummaryResponse]:
        ideas = self._ideas.list_ideas(user_id)
        summaries: list[IdeaSummaryResponse] = []
        for idea in ideas:
            latest = self._ideas.get_latest_version_and_verdict(idea.id)
            summaries.append(
                IdeaSummaryResponse(
                    idea_id=idea.id,
                    title=idea.title,
                    source=idea.source,
                    latest_version=latest[0].version if latest else 1,
                    latest_verdict=latest[1] if latest else None,
                )
            )
        return summaries

    def get_idea_versions(self, user_id: str, idea_id: str) -> list[IdeaVersionEntry]:
        idea = self._ideas.get_idea(idea_id)
        if idea is None or idea.user_id != user_id:
            raise KeyError("Idea not found")
        rows = self._ideas.list_versions_and_verdicts(idea_id)
        return [
            IdeaVersionEntry(version=ver.version, text=ver.text, verdict=verdict)
            for ver, verdict in rows
        ]

    def compare_ideas(
        self, user_id: str, left_id: str, right_id: str
    ) -> CompareIdeasResponse:
        left_idea = self._ideas.get_idea(left_id)
        right_idea = self._ideas.get_idea(right_id)
        if (
            left_idea is None
            or right_idea is None
            or left_idea.user_id != user_id
            or right_idea.user_id != user_id
        ):
            raise KeyError("One or both ideas not found")
        left_latest = self._ideas.get_latest_version_and_verdict(left_id)
        right_latest = self._ideas.get_latest_version_and_verdict(right_id)
        if left_latest is None or right_latest is None:
            raise ValueError("Both ideas must have a verdict before comparison")

        left_map = {s.dimension.value: s.score for s in left_latest[1].scores}
        right_map = {s.dimension.value: s.score for s in right_latest[1].scores}
        deltas = {
            dim.value: round(left_map[dim.value] - right_map[dim.value], 2)
            for dim in DimensionName
        }

        return CompareIdeasResponse(
            left=IdeaSummaryResponse(
                idea_id=left_idea.id,
                title=left_idea.title,
                source=left_idea.source,
                latest_version=left_latest[0].version,
                latest_verdict=left_latest[1],
            ),
            right=IdeaSummaryResponse(
                idea_id=right_idea.id,
                title=right_idea.title,
                source=right_idea.source,
                latest_version=right_latest[0].version,
                latest_verdict=right_latest[1],
            ),
            dimension_deltas=deltas,
        )

    @staticmethod
    def _to_run_response(row: Any) -> RunStatusResponse:
        return RunStatusResponse(
            run_id=row.run_id,
            workflow=row.workflow,
            status=row.status,
            events=json.loads(row.events_json),
            pending_question=(
                json.loads(row.pending_question_json) if row.pending_question_json else None
            ),
            pending_approval=(
                json.loads(row.pending_approval_json) if row.pending_approval_json else None
            ),
            result=json.loads(row.result_json) if row.result_json else None,
        )
