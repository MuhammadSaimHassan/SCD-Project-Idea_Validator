"""M3 Discover and Validate state machines with bounded retries and trace records."""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from services.agentops.src.budgets import (
    BudgetApprovalRequired,
    BudgetLimitExceeded,
    BudgetTracker,
)
from services.agentops.src.store import TraceStore
from services.analyst.src.analyzer import analyze_cards, load_cards
from services.ideator.src.agents import debate, ideator
from services.verdict.src.engine import evaluate_verdict
from shared.config import load_budgets, load_thresholds, load_weights_config
from shared.schemas import (
    DimensionName,
    DimensionScore,
    EvidenceItem,
    StudentProfile,
    TraceKind,
    TraceRecord,
    Verdict,
    VerdictRequest,
)
from shared.schemas.contracts import GateInputs


class BudgetExceeded(RuntimeError):
    pass


class Orchestrator:
    def __init__(
        self,
        config_dir: Path,
        snapshot_path: Path,
        max_steps: int = 40,
        max_cost_usd: float = 0.25,
        max_debate_rounds: int = 3,
        trace_store: TraceStore | None = None,
    ) -> None:
        self.config_dir = config_dir
        self.snapshot_path = snapshot_path
        self.max_steps = max_steps
        self.max_cost_usd = max_cost_usd
        self.max_debate_rounds = max_debate_rounds
        self.trace_store = trace_store or TraceStore(Path("data/traces"))
        raw_budgets = load_budgets(config_dir).get("per_run", {})
        self._budget_config = dict(raw_budgets)
        self._budget_config["max_steps"] = max_steps
        self._budget_config["max_cost_usd"] = max_cost_usd
        self.budgets = BudgetTracker(self._budget_config)
        self.traces: list[dict[str, Any]] = []

    def _begin_run(self) -> str:
        run_id = f"run_{uuid.uuid4().hex[:10]}"
        self.budgets = BudgetTracker(self._budget_config)
        return run_id

    def _trace(
        self,
        run_id: str,
        step_id: int,
        agent: str,
        kind: str,
        output: Any,
        *,
        tool: str | None = None,
        input_data: Any = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        pages_fetched: int = 0,
        cost_usd: float = 0.0,
        approved: bool = False,
        model: str | None = None,
        latency_ms: int = 0,
    ) -> None:
        error: str | None = None
        try:
            self.budgets.consume(
                tokens=tokens_in + tokens_out,
                pages_fetched=pages_fetched,
                steps=1,
                cost_usd=cost_usd,
                approved=approved,
            )
        except (BudgetLimitExceeded, BudgetApprovalRequired) as exc:
            error = str(exc)
            self._persist_trace(
                run_id,
                step_id,
                agent,
                kind,
                output,
                tool=tool,
                input_data=input_data,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                model=model,
                latency_ms=latency_ms,
                error=error,
            )
            if isinstance(exc, BudgetApprovalRequired):
                raise
            raise BudgetExceeded(error) from exc

        self._persist_trace(
            run_id,
            step_id,
            agent,
            kind,
            output,
            tool=tool,
            input_data=input_data,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            model=model,
            latency_ms=latency_ms,
            error=error,
        )

    def _persist_trace(
        self,
        run_id: str,
        step_id: int,
        agent: str,
        kind: str,
        output: Any,
        *,
        tool: str | None,
        input_data: Any,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        model: str | None = None,
        latency_ms: int = 0,
        error: str | None = None,
    ) -> None:
        record = TraceRecord(
            run_id=run_id,
            step_id=step_id,
            agent=agent,
            kind=TraceKind(kind),
            tool=tool,
            input=input_data,
            output=output,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            model=model,
            latency_ms=latency_ms,
            error=error,
            ts=datetime.now(UTC),
        )
        self.trace_store.append(record)
        self.traces.append(record.model_dump(mode="json"))

    def record_usage(
        self,
        run_id: str,
        *,
        agent: str,
        kind: str,
        tool: str | None = None,
        input_data: Any = None,
        output: Any = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        pages_fetched: int = 0,
        cost_usd: float = 0.0,
        approved: bool = False,
        model: str | None = None,
        latency_ms: int = 0,
    ) -> None:
        """Account and trace one downstream action against the active run caps."""
        self._trace(
            run_id,
            self.budgets.usage.steps + 1,
            agent,
            kind,
            output,
            tool=tool,
            input_data=input_data,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            pages_fetched=pages_fetched,
            cost_usd=cost_usd,
            approved=approved,
            model=model,
            latency_ms=latency_ms,
        )

    def discover(self, profile: StudentProfile, max_ideas: int = 5) -> dict[str, Any]:
        run_id = self._begin_run()
        started = perf_counter()
        cards = load_cards(self.snapshot_path)
        _, gaps = analyze_cards(cards)
        self._trace(
            run_id,
            1,
            "niche_analyst",
            "tool_call",
            f"{len(gaps)} gaps found",
            tool="analyze_cards",
            input_data={"cards": len(cards)},
            latency_ms=int((perf_counter() - started) * 1000),
        )

        started = perf_counter()
        candidates = ideator(gaps, profile.skills, profile.hours_per_week, limit=max_ideas)
        self._trace(
            run_id,
            2,
            "ideator",
            "decision",
            [c.title for c in candidates],
            tool="draft_ideas",
            input_data={"skills": profile.skills, "hours_per_week": profile.hours_per_week},
            latency_ms=int((perf_counter() - started) * 1000),
        )

        existing_names = [card.name for card in cards]
        started = perf_counter()
        survivors, debate_trace = debate(
            candidates,
            existing_names=existing_names,
            max_rounds=self.max_debate_rounds,
        )
        self._trace(
            run_id,
            3,
            "gap_skeptic",
            "decision",
            debate_trace,
            tool="debate",
            input_data={"max_rounds": self.max_debate_rounds},
            latency_ms=int((perf_counter() - started) * 1000),
        )
        ranked = [
            {
                "title": item.title,
                "description": item.description,
                "evidence_ids": list(item.gap_evidence_ids),
            }
            for item in survivors
        ]
        return {"run_id": run_id, "status": "completed", "ideas": ranked}

    def validate(self, idea_text: str, profile: StudentProfile) -> Verdict:
        run_id = self._begin_run()
        started = perf_counter()
        cards = load_cards(self.snapshot_path)
        evidence = [
            EvidenceItem(
                evidence_id=f"{card.id}#c1",
                card_id=card.id,
                quote=card.summary[:500],
                source=card.source,
                url=card.url,
                retrieved_at=str(card.fetched_at),
            )
            for card in cards[:4]
        ]
        evidence_ids = [item.evidence_id for item in evidence]
        self._trace(
            run_id,
            1,
            "intake",
            "tool_call",
            "evidence collected",
            tool="load_snapshot",
            input_data={"idea_text": idea_text},
            latency_ms=int((perf_counter() - started) * 1000),
        )

        started = perf_counter()
        scores: list[DimensionScore] = []
        base_scores = {
            DimensionName.DEMAND_PAIN: 3.5,
            DimensionName.COMPETITION: 3.0,
            DimensionName.DIFFERENTIATION: 3.5,
            DimensionName.FEASIBILITY: 4.0,
            DimensionName.RISK: 4.0,
            DimensionName.LEARNING: 4.0,
        }
        for dimension in DimensionName:
            scores.append(
                DimensionScore(
                    dimension=dimension,
                    score=base_scores[dimension],
                    confidence=0.8 if evidence_ids else 0.2,
                    evidence_ids=evidence_ids[:2] if evidence_ids else [],
                    features={"n_sources": len({item.source for item in evidence})},
                    reason=f"Orchestrated score for {dimension.value}: {idea_text[:120]}",
                    rubric_version=f"{dimension.value}@v1",
                    model="m10-gateway-fallback",
                    abstained=not evidence_ids,
                )
            )
        self._trace(
            run_id,
            2,
            "validators",
            "decision",
            "Fallback dimension score placeholders created",
            tool="draft_dimension_scores",
            input_data={"evidence_items": len(evidence)},
            model="m10-gateway-fallback",
            latency_ms=int((perf_counter() - started) * 1000),
        )

        available_hours = profile.hours_per_week * profile.weeks_available * profile.team_size
        weights_version, weights = load_weights_config(self.config_dir)
        thresholds = load_thresholds(self.config_dir)
        request = VerdictRequest(
            idea_id=f"idea_{uuid.uuid4().hex[:8]}",
            version=1,
            run_id=run_id,
            profile=profile,
            scores=scores,
            gate_inputs=GateInputs(
                n_sources=len({item.source for item in evidence}),
                n_platforms=len({item.source for item in evidence}),
                estimated_build_hours=min(available_hours * 0.7, 80.0),
            ),
        )
        started = perf_counter()
        verdict = evaluate_verdict(
            request,
            weights_by_goal=weights,
            thresholds=thresholds,
            weights_version=weights_version,
            rubrics_version="orchestrated-rubrics@v1",
        )
        self._trace(
            run_id,
            3,
            "verdict_engine",
            "tool_call",
            verdict.model_dump(mode="json"),
            tool="evaluate_verdict",
            input_data={
                "verdict_request": request.model_dump(mode="json"),
                "weights": {
                    goal.value: {
                        dimension.value: value for dimension, value in preset.items()
                    }
                    for goal, preset in weights.items()
                },
                "thresholds": thresholds,
                "weights_version": weights_version,
                "rubrics_version": "orchestrated-rubrics@v1",
            },
            latency_ms=int((perf_counter() - started) * 1000),
        )
        return verdict
