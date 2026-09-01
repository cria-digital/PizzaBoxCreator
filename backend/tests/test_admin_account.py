"""Real admin login: bcrypt-hashed password stored in the DB, with .env as the
first-run fallback until a password is actually set via /configuracoes/conta."""

from __future__ import annotations

import pytest

from app.config import settings
from app.db import repositories as repo
from app.services.admin_account import (
    create_account,
    get_effective_username,
    hash_password,
    save_account,
    verify_login,
    verify_password,
)


@pytest.fixture(autouse=True)
def _env_credentials(monkeypatch):
    monkeypatch.setattr(settings, "admin_user", "admin")
    monkeypatch.setattr(settings, "admin_password", "env-password-123")


@pytest.fixture
def logged_in(api_client):
    api_client.post("/login", data={"username": "admin", "password": "env-password-123"},
                    follow_redirects=False)
    return api_client


# --- hashing ---

def test_hash_and_verify_roundtrip():
    h = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", h) is True
    assert verify_password("wrong", h) is False


def test_verify_password_rejects_malformed_hash():
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False


# --- env fallback vs DB-backed account ---

def test_effective_username_falls_back_to_env_when_unset(db):
    assert get_effective_username(db) == "admin"


def test_effective_username_uses_saved_account_once_set(db):
    save_account(db, "novo_admin", "some-password-1")
    assert get_effective_username(db) == "novo_admin"


def test_verify_login_env_fallback(db):
    assert verify_login(db, "admin", "env-password-123") is True
    assert verify_login(db, "admin", "wrong") is False
    assert verify_login(db, "someone-else", "env-password-123") is False


def test_verify_login_uses_db_account_once_saved(db):
    save_account(db, "admin", "brand-new-password")
    assert verify_login(db, "admin", "brand-new-password") is True
    assert verify_login(db, "admin", "env-password-123") is False  # old env password no longer valid


def test_verify_login_accepts_multiple_saved_accounts(db):
    create_account(db, "admin", "first-password")
    create_account(db, "designer", "second-password")

    assert verify_login(db, "admin", "first-password") is True
    assert verify_login(db, "designer", "second-password") is True
    assert verify_login(db, "designer", "first-password") is False
    assert verify_login(db, "ghost", "env-password-123") is False


def test_save_account_without_new_password_hashes_env_password_on_first_save(db):
    save_account(db, "admin", None)
    row = repo.admin_account_get(db)
    assert verify_password("env-password-123", row["password_hash"])


def test_save_account_without_new_password_keeps_existing_hash(db):
    save_account(db, "admin", "first-password")
    first_hash = repo.admin_account_get(db)["password_hash"]

    save_account(db, "admin_renamed", None)  # change username only
    row = repo.admin_account_get(db)
    assert row["username"] == "admin_renamed"
    assert row["password_hash"] == first_hash
    assert verify_login(db, "admin_renamed", "first-password") is True


# --- web routes ---

def test_account_page_requires_login(api_client):
    r = api_client.get("/configuracoes/conta", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert "/login" in r.headers["location"]


def test_account_page_renders_current_username(logged_in):
    r = logged_in.get("/configuracoes/conta")
    assert r.status_code == 200
    assert "admin" in r.text


def test_change_password_with_wrong_current_password_fails(logged_in, db):
    r = logged_in.post("/configuracoes/conta", data={
        "current_password": "totally-wrong",
        "username": "admin",
        "new_password": "new-password-1",
        "confirm_password": "new-password-1",
    }, follow_redirects=False)
    assert r.status_code == 303
    assert "error=" in r.headers["location"]
    assert repo.admin_account_get(db) is None  # nothing persisted


def test_change_password_mismatched_confirmation_fails(logged_in):
    r = logged_in.post("/configuracoes/conta", data={
        "current_password": "env-password-123",
        "username": "admin",
        "new_password": "new-password-1",
        "confirm_password": "different",
    }, follow_redirects=False)
    assert "error=" in r.headers["location"]


def test_change_password_too_short_fails(logged_in):
    r = logged_in.post("/configuracoes/conta", data={
        "current_password": "env-password-123",
        "username": "admin",
        "new_password": "short",
        "confirm_password": "short",
    }, follow_redirects=False)
    assert "error=" in r.headers["location"]


def test_change_password_success_and_old_password_stops_working(logged_in, api_client):
    r = logged_in.post("/configuracoes/conta", data={
        "current_password": "env-password-123",
        "username": "admin",
        "new_password": "brand-new-password-1",
        "confirm_password": "brand-new-password-1",
    }, follow_redirects=False)
    assert r.status_code == 303
    assert "msg=" in r.headers["location"]

    old = api_client.post("/login", data={"username": "admin", "password": "env-password-123"})
    assert old.status_code == 401

    new = api_client.post("/login", data={"username": "admin", "password": "brand-new-password-1"},
                          follow_redirects=False)
    assert new.status_code == 303
    assert "pizzabox_session" in new.cookies
