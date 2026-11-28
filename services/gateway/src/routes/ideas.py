"""Idea history, versions, challenge, what-if, and comparison routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from services.gateway.src.services.workflow_service import WorkflowService
from shared.schemas import Verdict

from .deps import get_current_user_id, get_workflow_service
from .schemas import (
    ApplyWhatIfRequest,
    ChallengeRequest,
    CompareIdeasResponse,
    IdeaSummaryResponse,
    IdeaVersionEntry,
)

router = APIRouter(tags=["ideas"])


@router.get("/ideas", response_model=list[IdeaSummaryResponse])
def list_ideas(
    user_id: str = Depends(get_current_user_id),
    svc: WorkflowService = Depends(get_workflow_service),
) -> list[IdeaSummaryResponse]:
    return svc.list_ideas(user_id)


@router.get("/ideas/{idea_id}/versions", response_model=list[IdeaVersionEntry])
def list_idea_versions(
    idea_id: str,
    user_id: str = Depends(get_current_user_id),
    svc: WorkflowService = Depends(get_workflow_service),
) -> list[IdeaVersionEntry]:
    try:
        return svc.get_idea_versions(user_id, idea_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/ideas/{idea_id}/challenge", response_model=Verdict)
def challenge_idea(
    idea_id: str,
    payload: ChallengeRequest,
    user_id: str = Depends(get_current_user_id),
    svc: WorkflowService = Depends(get_workflow_service),
) -> Verdict:
    try:
        return svc.challenge_idea(user_id, idea_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/ideas/{idea_id}/whatif", response_model=Verdict)
def whatif_idea(
    idea_id: str,
    payload: ApplyWhatIfRequest,
    user_id: str = Depends(get_current_user_id),
    svc: WorkflowService = Depends(get_workflow_service),
) -> Verdict:
    try:
        return svc.whatif_idea(user_id, idea_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/compare", response_model=CompareIdeasResponse)
def compare_ideas(
    left: str = Query(..., min_length=1),
    right: str = Query(..., min_length=1),
    user_id: str = Depends(get_current_user_id),
    svc: WorkflowService = Depends(get_workflow_service),
) -> CompareIdeasResponse:
    try:
        return svc.compare_ideas(user_id, left, right)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
