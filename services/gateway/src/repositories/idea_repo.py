"""Idea, IdeaVersion, Verdict, DimensionScore, and Approval repository for M2."""

import json
import uuid

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from services.gateway.src.db.models import (
    ApprovalRow,
    DimensionScoreRow,
    IdeaRow,
    IdeaVersionRow,
    TracesIndexRow,
    VerdictRow,
)
from shared.schemas import Verdict


class IdeaRepository:
    """Persistence operations for ideas, versions, verdicts, and approvals."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_idea_with_verdict(
        self,
        idea_id: str,
        user_id: str,
        title: str,
        source: str,
        idea_text: str,
        verdict: Verdict,
    ) -> VerdictRow:
        idea = IdeaRow(id=idea_id, user_id=user_id, title=title, source=source)
        self._session.add(idea)
        version_row = IdeaVersionRow(
            id=f"{idea_id}_v{verdict.version}",
            idea_id=idea_id,
            version=verdict.version,
            text=idea_text,
        )
        self._session.add(version_row)
        verdict_row = self._persist_verdict_row(version_row.id, verdict)
        self._session.commit()
        return verdict_row

    def add_version_with_verdict(
        self,
        idea_id: str,
        idea_text: str,
        verdict: Verdict,
    ) -> VerdictRow:
        version_row = IdeaVersionRow(
            id=f"{idea_id}_v{verdict.version}_{uuid.uuid4().hex[:6]}",
            idea_id=idea_id,
            version=verdict.version,
            text=idea_text,
        )
        self._session.add(version_row)
        verdict_row = self._persist_verdict_row(version_row.id, verdict)
        self._session.commit()
        return verdict_row

    def _persist_verdict_row(self, version_id: str, verdict: Verdict) -> VerdictRow:
        verdict_id = f"verd_{uuid.uuid4().hex[:12]}"
        verdict_row = VerdictRow(
            id=verdict_id,
            version_id=version_id,
            run_id=verdict.run_id,
            verdict=verdict.verdict.value,
            score=verdict.score,
            confidence=verdict.confidence,
            payload_json=verdict.model_dump_json(),
        )
        self._session.add(verdict_row)
        for dim_score in verdict.scores:
            self._session.add(
                DimensionScoreRow(
                    id=f"ds_{uuid.uuid4().hex[:12]}",
                    verdict_id=verdict_id,
                    dimension=dim_score.dimension.value,
                    score=dim_score.score,
                    confidence=dim_score.confidence,
                    evidence_json=json.dumps(dim_score.evidence_ids),
                )
            )
        return verdict_row

    def get_idea(self, idea_id: str) -> IdeaRow | None:
        return self._session.get(IdeaRow, idea_id)

    def list_ideas(self, user_id: str) -> list[IdeaRow]:
        stmt = (
            select(IdeaRow)
            .where(IdeaRow.user_id == user_id)
            .order_by(desc(IdeaRow.created_at))
        )
        return list(self._session.scalars(stmt))

    def list_versions_and_verdicts(
        self, idea_id: str
    ) -> list[tuple[IdeaVersionRow, Verdict | None]]:
        stmt = (
            select(IdeaVersionRow)
            .where(IdeaVersionRow.idea_id == idea_id)
            .order_by(IdeaVersionRow.version.asc())
        )
        versions = list(self._session.scalars(stmt))
        results: list[tuple[IdeaVersionRow, Verdict | None]] = []
        for ver in versions:
            v_stmt = (
                select(VerdictRow)
                .where(VerdictRow.version_id == ver.id)
                .order_by(desc(VerdictRow.created_at))
            )
            v_row = self._session.scalar(v_stmt)
            parsed = Verdict.model_validate_json(v_row.payload_json) if v_row else None
            results.append((ver, parsed))
        return results

    def get_latest_version_and_verdict(
        self, idea_id: str
    ) -> tuple[IdeaVersionRow, Verdict] | None:
        items = self.list_versions_and_verdicts(idea_id)
        for ver, verdict in reversed(items):
            if verdict is not None:
                return ver, verdict
        return None

    def record_approval(self, run_id: str, action: str, decision: str) -> None:
        self._session.add(
            ApprovalRow(
                id=f"app_{uuid.uuid4().hex[:12]}",
                run_id=run_id,
                action=action,
                decision=decision,
            )
        )
        self._session.commit()

    def upsert_trace_index(
        self, run_id: str, cost_usd: float, latency_ms: int, status: str
    ) -> None:
        existing = self._session.get(TracesIndexRow, run_id)
        if existing is None:
            self._session.add(
                TracesIndexRow(
                    run_id=run_id,
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    status=status,
                )
            )
        else:
            existing.cost_usd = cost_usd
            existing.latency_ms = latency_ms
            existing.status = status
        self._session.commit()
