"""Database layer: models, portable types and session management."""

from finagent_api.db.base import Base, utcnow
from finagent_api.db.session import (
    create_all,
    ensure_extensions,
    get_db,
    get_engine,
    get_session_factory,
    is_postgres,
    reset_engine,
    session_scope,
)
from finagent_api.db.types import GUID, JSONB, UTCDateTime, Vector, new_uuid

__all__ = [
    "GUID",
    "JSONB",
    "Base",
    "UTCDateTime",
    "Vector",
    "create_all",
    "ensure_extensions",
    "get_db",
    "get_engine",
    "get_session_factory",
    "is_postgres",
    "new_uuid",
    "reset_engine",
    "session_scope",
    "utcnow",
]
