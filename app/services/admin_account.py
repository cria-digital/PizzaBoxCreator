"""Admin login backed by bcrypt hashes stored in the database.

.env stays as the first-run bootstrap credential. Once at least one admin_account row
exists, saved database accounts are authoritative and .env is no longer accepted.
"""

from __future__ import annotations

import hmac
import sqlite3

import bcrypt

from app.config import settings
from app.db import repositories as repo


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False  # malformed hash -- never let a broken row pass as valid


def get_effective_username(db: sqlite3.Connection) -> str:
    """Default username shown before a session-specific user is known."""
    account = repo.admin_account_get(db)
    return account["username"] if account else settings.admin_user


def verify_login(db: sqlite3.Connection, username: str, password: str) -> bool:
    account = repo.admin_account_get(db, username)
    if account:
        return verify_password(password, account["password_hash"])

    if repo.admin_account_any(db):
        return False

    # No saved account yet: fall back to the .env bootstrap credential.
    valid_user = hmac.compare_digest(username, settings.admin_user)
    valid_pass = hmac.compare_digest(password, settings.admin_password)
    return valid_user and valid_pass


def save_account(db: sqlite3.Connection, username: str, new_password: str | None,
                 current_username: str | None = None) -> dict:
    """Persist the account. If new_password is None, keep the current hash (or, on the
    very first save, hash the .env password so the row becomes self-sufficient)."""
    existing = repo.admin_account_get(db, current_username) if current_username else repo.admin_account_get(db)
    if new_password:
        password_hash = hash_password(new_password)
    else:
        password_hash = existing["password_hash"] if existing else hash_password(settings.admin_password)
    account_id = existing["id"] if existing else None
    return repo.admin_account_set(db, username, password_hash, account_id=account_id)


def create_account(db: sqlite3.Connection, username: str, password: str) -> dict:
    """Create or replace an admin account by username."""
    return repo.admin_account_set(db, username, hash_password(password))
