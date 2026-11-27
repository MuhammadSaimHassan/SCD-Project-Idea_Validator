"""Profile routes: GET /profile, PUT /profile."""

from fastapi import APIRouter, Depends, HTTPException, status

from services.gateway.src.repositories.user_repo import UserRepository
from shared.schemas import StudentProfile

from .deps import get_current_user_id, get_user_repo
from .schemas import ProfileUpdateRequest

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=StudentProfile)
def read_profile(
    user_id: str = Depends(get_current_user_id),
    repo: UserRepository = Depends(get_user_repo),
) -> StudentProfile:
    profile = repo.get_profile(user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    return profile


@router.put("/profile", response_model=StudentProfile)
def upsert_profile(
    payload: ProfileUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    repo: UserRepository = Depends(get_user_repo),
) -> StudentProfile:
    profile = StudentProfile(
        user_id=user_id,
        skills=payload.skills,
        hours_per_week=payload.hours_per_week,
        weeks_available=payload.weeks_available,
        team_size=payload.team_size,
        compute=payload.compute,
        goal=payload.goal,
        interests=payload.interests,
    )
    return repo.upsert_profile(profile)
