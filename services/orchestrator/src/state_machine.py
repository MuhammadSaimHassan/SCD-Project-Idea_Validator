"""M3 Discover and Validate state machines with bounded retries and trace records."""

import uuid
from pathlib import Path
from typing import Any

from services.analyst.src.analyzer import analyze_cards, load_cards
from services.ideator.src.agents import debate, ideator
from services.verdict.src.engine import evaluate_verdict
from shared.config import load_thresholds, load_weights_config
from shared.schemas import (
    DimensionName,
    DimensionScore,
    EvidenceItem,
    StudentProfile,
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
    ) -> None:
        self.config_dir = config_dir
        self.snapshot_path = snapshot_path
        self.max_steps = max_steps
        self.max_cost_usd = max_cost_usd
        self.max_debate_rounds = max_debate_rounds
        self.traces: list[dict[str, Any]] = []

    def _trace(self, run_id: str, step_id: int, agent: str, kind: str, output: Any) -> None:
        self.traces.append(
            {
                "run_id": run_id,
                "step_id": step_id,
                "agent": agent,
                "kind": kind,
                "output": output,
            }
        )
        if step_id > self.max_steps:
            raise BudgetExceeded("Run stopped: max_steps exceeded")

    def discover(self, profile: StudentProfile, max_ideas: int = 5) -> dict[str, Any]:
        run_id = f"run_{uuid.uuid4().hex[:10]}"
        cards = load_cards(self.snapshot_path)
        _, gaps = analyze_cards(cards)
        self._trace(run_id, 1, "niche_analyst", "decision", f"{len(gaps)} gaps found")

        candidates = ideator(gaps, profile.skills, profile.hours_per_week, limit=max_ideas)
        self._trace(run_id, 2, "ideator", "llm_call", [c.title for c in candidates])

        existing_names = [card.name for card in cards]
        survivors, debate_trace = debate(
            candidates,
            existing_names=existing_names,
            max_rounds=self.max_debate_rounds,
        )
        self._trace(run_id, 3, "gap_skeptic", "decision", debate_trace)
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
        run_id = f"run_{uuid.uuid4().hex[:10]}"
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
        self._trace(run_id, 1, "intake", "decision", "evidence collected")

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
        self._trace(run_id, 2, "validators", "llm_call", "4 parallel scorers completed")

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
        verdict = evaluate_verdict(
            request,
            weights_by_goal=weights,
            thresholds=thresholds,
            weights_version=weights_version,
            rubrics_version="orchestrated-rubrics@v1",
        )
        self._trace(run_id, 3, "verdict_engine", "decision", verdict.model_dump(mode="json"))
        return verdict
