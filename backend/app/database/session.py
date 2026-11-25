"""Engine/session management. Tests can point this at a temporary SQLite file."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from app.core.config import get_settings
from app.database.base import Base
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_engine_url: str | None = None


def init_database(url: str | None = None, *, force: bool = False) -> Engine:
    global _engine, _session_factory, _engine_url
    resolved = url or get_settings().database_url
    if _engine is not None and not force and resolved == _engine_url:
        return _engine
    if _engine is not None:
        _engine.dispose()

    connect_args: dict[str, object] = {}
    if resolved.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(resolved, connect_args=connect_args, pool_pre_ping=True, future=True)
    if resolved.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    _engine = engine
    _engine_url = resolved
    _session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine


def get_session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        init_database()
    assert _session_factory is not None
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_schema() -> None:
    from app import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(init_database())


def reset_database_engine() -> None:
    global _engine, _session_factory, _engine_url
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
    _engine_url = None
