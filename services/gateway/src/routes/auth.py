"""Auth routes: POST /auth/register, POST /auth/login."""

from fastapi import APIRouter, Depends, HTTPException, status

from services.gateway.src.services.auth import AuthService

from .deps import get_auth_service
from .schemas import AuthResponse, LoginRequest, RegisterRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    auth: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    try:
        user_id, email, token = auth.register(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return AuthResponse(user_id=user_id, email=email, access_token=token)


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    auth: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    try:
        user_id, email, token = auth.login(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return AuthResponse(user_id=user_id, email=email, access_token=token)
