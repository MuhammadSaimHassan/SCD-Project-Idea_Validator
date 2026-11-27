"""Run state repository for Discover and Validate workflows."""

import json
from typing import Any

from sqlalchemy.orm import Session

from services.gateway.src.db.models import RunRow


class RunRepository:
    """Persistence for workflow runs, progress events, and pending prompts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_run(
        self,
        run_id: str,
        user_id: str,
        workflow: str,
        request_payload: dict[str, Any],
        status: str = "running",
    ) -> RunRow:
        row = RunRow(
            run_id=run_id,
            user_id=user_id,
            workflow=workflow,
            status=status,
            request_json=json.dumps(request_payload),
            events_json="[]",
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row

    def get_run(self, run_id: str) -> RunRow | None:
        return self._session.get(RunRow, run_id)

    def update_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        events: list[dict[str, Any]] | None = None,
        pending_question: dict[str, Any] | None = None,
        clear_question: bool = False,
        pending_approval: dict[str, Any] | None = None,
        clear_approval: bool = False,
        result: dict[str, Any] | None = None,
    ) -> RunRow:
        row = self._session.get(RunRow, run_id)
        if row is None:
            raise KeyError(f"Run not found: {run_id}")
        if status is not None:
            row.status = status
        if events is not None:
            row.events_json = json.dumps(events)
        if clear_question:
            row.pending_question_json = None
        elif pending_question is not None:
            row.pending_question_json = json.dumps(pending_question)
        if clear_approval:
            row.pending_approval_json = None
        elif pending_approval is not None:
            row.pending_approval_json = json.dumps(pending_approval)
        if result is not None:
            row.result_json = json.dumps(result)
        self._session.commit()
        self._session.refresh(row)
        return row
