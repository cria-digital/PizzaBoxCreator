"""Catalog API: browse available templates."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.db import repositories as repo
from app.models.commands import CatalogItem, CatalogDetail, EditableFieldInfo, LayerInfo
from app.psd.inspector import inspect_template
from app.api.auth import require_api_user

router = APIRouter(tags=["catalog"], dependencies=[Depends(require_api_user)])


@router.get("/catalog", response_model=list[CatalogItem])
def list_catalog(db: Session = Depends(get_db)):
    templates = repo.template_list_active(db)
    return [
        CatalogItem(
            id=t["id"],
            display_name=t["display_name"],
            description=t.get("description"),
            size_cm=t.get("size_cm"),
            product_type=t["product_type"],
            thumbnail_url=f"/api/catalog/{t['id']}/thumbnail",
            editable_fields=[EditableFieldInfo(**f) for f in t["editable_fields"]],
        )
        for t in templates
    ]


@router.get("/catalog/{template_id}", response_model=CatalogDetail)
def get_catalog_detail(template_id: int, db: Session = Depends(get_db)):
    t = repo.template_get(db, template_id)
    if not t:
        raise HTTPException(404, "Template nao encontrado")

    psd_path = settings.templates_dir / t["filename"]
    layers: list[LayerInfo] = []
    if psd_path.exists():
        info = inspect_template(psd_path)
        layers = info.layers

    return CatalogDetail(
        id=t["id"],
        display_name=t["display_name"],
        description=t.get("description"),
        size_cm=t.get("size_cm"),
        product_type=t["product_type"],
        filename=t["filename"],
        thumbnail_url=f"/api/catalog/{t['id']}/thumbnail",
        editable_fields=[EditableFieldInfo(**f) for f in t["editable_fields"]],
        layers=layers,
    )


@router.get("/catalog/{template_id}/thumbnail")
def get_thumbnail(template_id: int, db: Session = Depends(get_db)):
    t = repo.template_get(db, template_id)
    if not t or not t.get("thumbnail"):
        raise HTTPException(404, "Thumbnail nao disponivel")

    path = settings.thumbnails_dir / t["thumbnail"]
    if not path.exists():
        raise HTTPException(404, "Thumbnail nao encontrado no disco")

    return FileResponse(str(path), media_type="image/jpeg")
