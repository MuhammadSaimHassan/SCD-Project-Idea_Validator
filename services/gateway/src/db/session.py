"""Database engine and session helpers for M2."""

from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def build_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine supporting Postgres and SQLite."""
    connect_args: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a configured sessionmaker bound to engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_schema(engine: Engine) -> None:
    """Create tables if not already migrated (convenient for local/test runs)."""
    Base.metadata.create_all(bind=engine)


def check_db_ready(engine: Engine) -> bool:
    """Verify DB connectivity for /ready probe."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True


def session_scope(
    session_factory: sessionmaker[Session],
) -> Generator[Session, None, None]:
    """Yield a session and close it deterministically."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
