"""JSON authentication API for the React frontend."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.admin_account import verify_login
from app.web.auth import (
    clear_failed_logins,
    clear_session,
    create_session,
    get_current_user,
    is_locked_out,
    record_failed_login,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthUser(BaseModel):
    id: str
    name: str
    email: str
    role: str


class AuthResponse(BaseModel):
    user: AuthUser


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _user_response(username: str) -> AuthResponse:
    return AuthResponse(
        user=AuthUser(
            id=f"admin:{username}",
            name=username,
            email=username,
            role="Administrador",
        )
    )


def require_api_user(request: Request) -> str:
    username = get_current_user(request)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessao expirada ou usuario nao autenticado",
        )
    return username


@router.post("/login", response_model=AuthResponse)
def login(data: LoginRequest, request: Request, response: Response,
          db: Session = Depends(get_db)):
    client_ip = _client_ip(request)
    if is_locked_out(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas. Aguarde alguns minutos e tente novamente.",
        )

    username = data.username.strip()
    if verify_login(db, username, data.password):
        clear_failed_logins(client_ip)
        create_session(response, username)
        return _user_response(username)

    record_failed_login(client_ip)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Usuario ou senha incorretos",
    )


@router.get("/me", response_model=AuthResponse)
def me(username: str = Depends(require_api_user)):
    return _user_response(username)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    clear_session(response)
    return None
