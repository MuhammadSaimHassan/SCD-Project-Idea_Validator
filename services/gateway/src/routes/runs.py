"""Workflow run routes: /discover, /validate, /runs/{id}, /events, /answer, /approve."""

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from services.gateway.src.services.workflow_service import WorkflowService

from .deps import get_current_user_id, get_workflow_service
from .schemas import (
    AnswerRequest,
    ApprovalRequest,
    DiscoverRequest,
    RunAcceptedResponse,
    RunStatusResponse,
    ValidateRunRequest,
)

router = APIRouter(tags=["runs"])


@router.post("/discover", response_model=RunAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def start_discover(
    payload: DiscoverRequest,
    user_id: str = Depends(get_current_user_id),
    svc: WorkflowService = Depends(get_workflow_service),
) -> RunAcceptedResponse:
    try:
        run = svc.start_discover(user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RunAcceptedResponse(run_id=run.run_id, status=run.status, workflow=run.workflow)


@router.post("/validate", response_model=RunAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def start_validate(
    payload: ValidateRunRequest,
    user_id: str = Depends(get_current_user_id),
    svc: WorkflowService = Depends(get_workflow_service),
) -> RunAcceptedResponse:
    try:
        run = svc.start_validate(user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RunAcceptedResponse(run_id=run.run_id, status=run.status, workflow=run.workflow)


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
def get_run(
    run_id: str,
    user_id: str = Depends(get_current_user_id),
    svc: WorkflowService = Depends(get_workflow_service),
) -> RunStatusResponse:
    try:
        return svc.get_run(user_id, run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/runs/{run_id}/events")
def stream_run_events(
    run_id: str,
    user_id: str = Depends(get_current_user_id),
    svc: WorkflowService = Depends(get_workflow_service),
) -> StreamingResponse:
    try:
        run = svc.get_run(user_id, run_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    def _event_stream() -> Iterator[str]:
        for event in run.events:
            yield f"event: step\ndata: {json.dumps(event)}\n\n"
        done_payload = {"run_id": run.run_id, "status": run.status}
        yield f"event: status\ndata: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


@router.post("/runs/{run_id}/answer", response_model=RunStatusResponse)
def answer_run(
    run_id: str,
    payload: AnswerRequest,
    user_id: str = Depends(get_current_user_id),
    svc: WorkflowService = Depends(get_workflow_service),
) -> RunStatusResponse:
    try:
        return svc.answer_run(user_id, run_id, payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/runs/{run_id}/approve", response_model=RunStatusResponse)
def approve_run(
    run_id: str,
    payload: ApprovalRequest,
    user_id: str = Depends(get_current_user_id),
    svc: WorkflowService = Depends(get_workflow_service),
) -> RunStatusResponse:
    try:
        return svc.approve_run(user_id, run_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
