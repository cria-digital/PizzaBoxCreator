"""Login flow: credential check, session cookie, and the in-memory brute-force throttle."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def reset_login_throttle():
    """_failed_attempts is module-level state shared across requests -- never let one
    test's lockout bleed into the next."""
    from app.web import auth

    auth._failed_attempts.clear()
    yield
    auth._failed_attempts.clear()


@pytest.fixture
def test_credentials(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "admin_user", "admin")
    monkeypatch.setattr(settings, "admin_password", "test-password-123")
    return "admin", "test-password-123"


# ---------------------------------------------------------------------------
# Pure throttle logic
# ---------------------------------------------------------------------------

def test_is_locked_out_false_initially():
    from app.web.auth import is_locked_out

    assert is_locked_out("1.2.3.4") is False


def test_locks_out_after_max_attempts(monkeypatch):
    from app.config import settings
    from app.web.auth import is_locked_out, record_failed_login

    monkeypatch.setattr(settings, "login_max_attempts", 3)

    for _ in range(3):
        record_failed_login("1.2.3.4")

    assert is_locked_out("1.2.3.4") is True


def test_lockout_is_per_ip(monkeypatch):
    from app.config import settings
    from app.web.auth import is_locked_out, record_failed_login

    monkeypatch.setattr(settings, "login_max_attempts", 3)

    for _ in range(3):
        record_failed_login("1.2.3.4")

    assert is_locked_out("5.6.7.8") is False


def test_clear_failed_logins_resets_throttle(monkeypatch):
    from app.config import settings
    from app.web.auth import clear_failed_logins, is_locked_out, record_failed_login

    monkeypatch.setattr(settings, "login_max_attempts", 3)

    for _ in range(3):
        record_failed_login("1.2.3.4")
    clear_failed_logins("1.2.3.4")

    assert is_locked_out("1.2.3.4") is False


def test_old_attempts_expire_outside_lockout_window(monkeypatch):
    from app.config import settings
    from app.web import auth

    monkeypatch.setattr(settings, "login_max_attempts", 3)
    monkeypatch.setattr(settings, "login_lockout_seconds", 60)

    fake_now = [1000.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: fake_now[0])

    for _ in range(3):
        auth.record_failed_login("1.2.3.4")
    assert auth.is_locked_out("1.2.3.4") is True

    fake_now[0] += 61  # past the lockout window
    assert auth.is_locked_out("1.2.3.4") is False


# ---------------------------------------------------------------------------
# HTTP login flow
# ---------------------------------------------------------------------------

def test_login_page_renders(api_client):
    r = api_client.get("/login")
    assert r.status_code == 200


def test_login_with_correct_credentials_sets_session_cookie(api_client, test_credentials):
    user, password = test_credentials
    r = api_client.post("/login", data={"username": user, "password": password}, follow_redirects=False)
    assert r.status_code == 303
    assert "pizzabox_session" in r.cookies


def test_login_with_wrong_password_returns_401(api_client, test_credentials):
    user, _ = test_credentials
    r = api_client.post("/login", data={"username": user, "password": "wrong"})
    assert r.status_code == 401
    assert "pizzabox_session" not in r.cookies


def test_lockout_after_repeated_failed_logins(api_client, test_credentials, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "login_max_attempts", 3)
    user, _ = test_credentials

    for _ in range(3):
        r = api_client.post("/login", data={"username": user, "password": "wrong"})
        assert r.status_code == 401

    r = api_client.post("/login", data={"username": user, "password": "wrong"})
    assert r.status_code == 429


def test_successful_login_clears_throttle(api_client, test_credentials, monkeypatch):
    from app.config import settings
    from app.web import auth

    monkeypatch.setattr(settings, "login_max_attempts", 3)
    user, password = test_credentials

    api_client.post("/login", data={"username": user, "password": "wrong"})
    api_client.post("/login", data={"username": user, "password": password}, follow_redirects=False)

    assert auth.is_locked_out("testclient") is False


def test_dashboard_redirects_to_login_when_unauthenticated(api_client):
    r = api_client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert "/login" in r.headers["location"]


def test_dashboard_accessible_after_login(api_client, test_credentials):
    user, password = test_credentials
    api_client.post("/login", data={"username": user, "password": password}, follow_redirects=False)

    r = api_client.get("/")
    assert r.status_code == 200


def test_logout_clears_session(api_client, test_credentials):
    user, password = test_credentials
    api_client.post("/login", data={"username": user, "password": password}, follow_redirects=False)
    assert api_client.get("/").status_code == 200

    api_client.get("/logout", follow_redirects=False)
    r = api_client.get("/", follow_redirects=False)
    assert r.status_code == 303
