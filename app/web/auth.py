"""Simple cookie-based authentication for the dashboard."""

from __future__ import annotations

import time

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.config import settings

COOKIE_NAME = "pizzabox_session"
MAX_AGE = 60 * 60 * 12  # 12 hours

# In-memory login throttle, keyed by client IP. Resets on process restart;
# good enough for a single-instance dashboard, not meant to survive a cluster.
_failed_attempts: dict[str, list[float]] = {}


def is_locked_out(client_ip: str) -> bool:
    cutoff = time.monotonic() - settings.login_lockout_seconds
    attempts = [t for t in _failed_attempts.get(client_ip, []) if t > cutoff]
    _failed_attempts[client_ip] = attempts
    return len(attempts) >= settings.login_max_attempts


def record_failed_login(client_ip: str):
    _failed_attempts.setdefault(client_ip, []).append(time.monotonic())


def clear_failed_logins(client_ip: str):
    _failed_attempts.pop(client_ip, None)


def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key)


def create_session(response: Response, username: str):
    token = _get_serializer().dumps({"user": username})
    response.set_cookie(
        COOKIE_NAME, token, max_age=MAX_AGE, httponly=True, samesite="lax",
        secure=settings.secure_cookies,
    )


def get_current_user(request: Request) -> str | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        data = _get_serializer().loads(token, max_age=MAX_AGE)
        return data.get("user")
    except (BadSignature, SignatureExpired):
        return None


def clear_session(response: Response):
    response.delete_cookie(COOKIE_NAME)


def require_login(request: Request) -> RedirectResponse | None:
    """Returns a redirect to /login if not authenticated, else None."""
    if get_current_user(request):
        return None
    return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
