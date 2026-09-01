"""Client API: manage client registry."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import repositories as repo
from app.models.commands import ClientCreate, ClientResponse
from app.api.auth import require_api_user

router = APIRouter(tags=["clients"], dependencies=[Depends(require_api_user)])


@router.post("/clients", response_model=ClientResponse)
def create_or_update_client(data: ClientCreate, db: Session = Depends(get_db)):
    client = repo.client_upsert(db, data.name, data.phone, data.instagram, data.logo_path)
    return ClientResponse(**client)


@router.get("/clients", response_model=list[ClientResponse])
def list_clients(db: Session = Depends(get_db), search: str | None = None):
    clients = repo.client_list(db, search)
    return [ClientResponse(**c) for c in clients]


@router.get("/clients/{phone}", response_model=ClientResponse)
def get_client_by_phone(phone: str, db: Session = Depends(get_db)):
    client = repo.client_get_by_phone(db, phone)
    if not client:
        raise HTTPException(404, "Cliente nao encontrado")
    return ClientResponse(**client)
