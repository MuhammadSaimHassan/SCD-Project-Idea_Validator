"""FastAPI dependency wiring for M1 routes."""

from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from services.gateway.src.repositories.cache import VersionedCache
from services.gateway.src.repositories.idea_repo import IdeaRepository
from services.gateway.src.repositories.run_repo import RunRepository
from services.gateway.src.repositories.user_repo import UserRepository
from services.gateway.src.services.auth import AuthService
from services.gateway.src.services.workflow_service import WorkflowService


def get_db_session(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_cache(request: Request) -> VersionedCache:
    cache: VersionedCache = request.app.state.cache
    return cache


def get_auth_service(
    request: Request, session: Session = Depends(get_db_session)
) -> AuthService:
    settings = request.app.state.settings
    return AuthService(
        UserRepository(session),
        jwt_secret=settings.jwt_secret,
        jwt_ttl_seconds=settings.jwt_ttl_seconds,
    )


def get_current_user_id(
    authorization: str | None = Header(default=None),
    auth: AuthService = Depends(get_auth_service),
) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )
    token = authorization.split(" ", maxsplit=1)[1]
    try:
        return auth.authenticate_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


def get_user_repo(session: Session = Depends(get_db_session)) -> UserRepository:
    return UserRepository(session)


def get_workflow_service(
    request: Request,
    session: Session = Depends(get_db_session),
    cache: VersionedCache = Depends(get_cache),
) -> WorkflowService:
    settings = request.app.state.settings
    return WorkflowService(
        user_repo=UserRepository(session),
        idea_repo=IdeaRepository(session),
        run_repo=RunRepository(session),
        cache=cache,
        config_dir=settings.config_dir,
        rubric_version=settings.rubric_version,
        verdict_url=settings.verdict_url,
        orchestrator_url=settings.orchestrator_url,
    )
