"""Client API: manage client registry."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import repositories as repo
from app.models.commands import ClientCreate, ClientResponse, ClientUpdate
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


@router.get("/clients/{client_id:int}", response_model=ClientResponse)
def get_client(client_id: int, db: Session = Depends(get_db)):
    client = repo.client_get(db, client_id)
    if not client:
        raise HTTPException(404, "Cliente nao encontrado")
    return ClientResponse(**client)


@router.get("/clients/by-phone/{phone}", response_model=ClientResponse)
def get_client_by_phone_explicit(phone: str, db: Session = Depends(get_db)):
    return get_client_by_phone(phone, db)


@router.get("/clients/{phone}", response_model=ClientResponse)
def get_client_by_phone(phone: str, db: Session = Depends(get_db)):
    client = repo.client_get_by_phone(db, phone)
    if not client:
        raise HTTPException(404, "Cliente nao encontrado")
    return ClientResponse(**client)


@router.patch("/clients/{client_id:int}", response_model=ClientResponse)
def update_client(client_id: int, data: ClientUpdate, db: Session = Depends(get_db)):
    client = repo.client_get(db, client_id)
    if not client:
        raise HTTPException(404, "Cliente nao encontrado")

    fields = data.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(400, "Informe ao menos um campo para atualizar")

    if "phone" in fields and fields["phone"] != client["phone"]:
        existing = repo.client_get_by_phone(db, fields["phone"])
        if existing and existing["id"] != client_id:
            raise HTTPException(409, "Ja existe cliente com esse telefone")

    try:
        updated = repo.client_update(db, client_id, **fields)
    except IntegrityError:
        raise HTTPException(409, "Ja existe cliente com esse telefone")
    return ClientResponse(**updated)


@router.delete("/clients/{client_id:int}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id: int, db: Session = Depends(get_db)):
    client = repo.client_get(db, client_id)
    if not client:
        raise HTTPException(404, "Cliente nao encontrado")

    if repo.client_order_count(db, client_id) > 0:
        raise HTTPException(409, "Cliente possui pedidos e nao pode ser excluido")

    repo.client_delete(db, client_id)
    return None
