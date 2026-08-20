"""Database initialization — delegates to session.py for SQLAlchemy engine management."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import settings


def get_db():
    """Legacy compat: returns a raw sqlite3.Connection for code not yet migrated."""
    conn = sqlite3.connect(str(settings.db_path), timeout=settings.sqlite_busy_timeout / 1000)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA journal_mode={settings.sqlite_journal_mode}")
    conn.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout}")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables via SQLAlchemy ORM + Alembic-style create_all."""
    from app.db.session import init_db as _sa_init
    _sa_init()
