"""CRM API: contacts, funnel metrics and assisted reengagement."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import require_api_user
from app.db import repositories as repo
from app.db.session import get_db
from app.services import crm_service, reengagement_service


router = APIRouter(tags=["crm"], dependencies=[Depends(require_api_user)])


class SkipTaskBody(BaseModel):
    note: str = "Ignorado pelo operador"


@router.get("/crm/contacts")
def list_contacts(
    db: Session = Depends(get_db),
    classification: str | None = None,
    stage: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    crm_service.backfill_crm(db)
    return repo.crm_contacts_list(
        db,
        classification=classification,
        stage=stage,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/crm/contacts/{client_id}")
def get_contact(client_id: int, db: Session = Depends(get_db)):
    detail = crm_service.contact_detail(db, client_id)
    if not detail:
        raise HTTPException(404, "Contato CRM nao encontrado")
    return detail


@router.get("/crm/metrics")
def get_metrics(
    db: Session = Depends(get_db),
    start: datetime | None = None,
    end: datetime | None = None,
):
    return crm_service.crm_metrics(db, start=start, end=end)


@router.post("/crm/reclassify")
def reclassify(db: Session = Depends(get_db)):
    backfill = crm_service.backfill_crm(db)
    result = crm_service.reclassify_all(db)
    return {"backfill": backfill, **result}


@router.get("/crm/reengagement")
def list_reengagement(
    db: Session = Depends(get_db),
    status: str | None = None,
    client_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
):
    return repo.crm_reengagement_list(
        db,
        status=status,
        client_id=client_id,
        limit=limit,
        offset=offset,
    )


@router.post("/crm/reengagement/{task_id}/send")
def mark_reengagement_sent(task_id: int, db: Session = Depends(get_db)):
    task = reengagement_service.mark_task_sent(db, task_id)
    if not task:
        raise HTTPException(404, "Tarefa de reengajamento nao encontrada")
    return task


@router.post("/crm/reengagement/{task_id}/skip")
def skip_reengagement(task_id: int, body: SkipTaskBody, db: Session = Depends(get_db)):
    task = reengagement_service.skip_task(db, task_id, note=body.note)
    if not task:
        raise HTTPException(404, "Tarefa de reengajamento nao encontrada")
    return task
