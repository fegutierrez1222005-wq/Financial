"""Engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from finagent_api.settings import get_settings
from finagent_core.logging import get_logger

logger = get_logger(__name__)

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _create_engine(url: str) -> Engine:
    settings = get_settings()
    if url.startswith("sqlite"):
        engine = create_engine(
            url, echo=settings.database_echo, future=True, connect_args={"check_same_thread": False}
        )

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine

    return create_engine(
        url,
        echo=settings.database_echo,
        future=True,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _create_engine(get_settings().database_url)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False
        )
    return _session_factory


def reset_engine() -> None:
    """Drop the cached engine/session factory (tests that swap the database URL)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, rolled back on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Session for background jobs and CLI commands."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_extensions(engine: Engine | None = None) -> None:
    """Create the pgvector extension when running on PostgreSQL."""
    engine = engine or get_engine()
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        try:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception as exc:
            logger.warning("pgvector_extension_unavailable", extra={"detail": str(exc)[:200]})


def create_all() -> None:
    """Create tables directly (tests and first-run bootstrap; Alembic owns production)."""
    from finagent_api.db import models

    engine = get_engine()
    ensure_extensions(engine)
    models.Base.metadata.create_all(bind=engine)


def is_postgres() -> bool:
    return get_engine().dialect.name == "postgresql"
