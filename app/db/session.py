"""Database session management with FastAPI dependency injection."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(
            settings.database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        if settings.database_url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _set_sqlite_pragma(dbapi_conn, _):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=DELETE")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
    return _engine


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a SQLAlchemy Session and ensures cleanup."""
    SessionLocal = _get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables (used at startup)."""
    from app.db.base import Base
    import app.db.models  # noqa: F401 — ensure models are registered

    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        _ensure_sqlite_columns(engine)


def _ensure_sqlite_columns(engine) -> None:
    """Apply small additive migrations for existing local SQLite databases."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "orders" in tables:
            order_cols = {c["name"] for c in inspector.get_columns("orders")}
            if "created_by" not in order_cols:
                conn.execute(text("ALTER TABLE orders ADD COLUMN created_by VARCHAR"))

        if "order_revisions" in tables:
            rev_cols = {c["name"] for c in inspector.get_columns("order_revisions")}
            if "preview_source" not in rev_cols:
                conn.execute(text(
                    "ALTER TABLE order_revisions "
                    "ADD COLUMN preview_source VARCHAR NOT NULL DEFAULT 'psd'"
                ))

        if "admin_account" in tables:
            ddl = conn.execute(text(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='admin_account'"
            )).scalar() or ""
            if "CHECK (id = 1)" in ddl or "CHECK(id = 1)" in ddl:
                conn.execute(text("ALTER TABLE admin_account RENAME TO admin_account_old"))
                conn.execute(text(
                    "CREATE TABLE admin_account ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "username VARCHAR NOT NULL UNIQUE, "
                    "password_hash VARCHAR NOT NULL, "
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)"
                ))
                conn.execute(text(
                    "INSERT INTO admin_account (username, password_hash, updated_at) "
                    "SELECT username, password_hash, updated_at FROM admin_account_old"
                ))
                conn.execute(text("DROP TABLE admin_account_old"))


def reset_engine():
    """Reset the global engine (used in tests)."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None
