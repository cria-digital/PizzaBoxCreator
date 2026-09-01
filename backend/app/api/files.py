"""File API: upload client assets and download generated order files."""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import require_api_user
from app.config import settings
from app.db import repositories as repo
from app.db.session import get_db
from app.services.logo_service import prepare_logo
from app.web.auth import get_current_user

router = APIRouter(
    prefix="/files",
    tags=["files"],
    dependencies=[Depends(require_api_user)],
)


class FileUploadResponse(BaseModel):
    purpose: str
    filename: str
    asset_path: str
    download_url: str | None = None
    client_id: int | None = None
    order_id: int | None = None


class OrderFileItem(BaseModel):
    kind: str
    filename: str
    download_url: str
    exists: bool


def _safe_suffix(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp", ".pdf", ".psd", ".zip"} else ".bin"


def _existing_file(kind: str, order: dict) -> Path | None:
    edit_data = order.get("edit_data") or {}
    if kind.startswith("reference:"):
        try:
            index = int(kind.split(":", 1)[1])
        except ValueError:
            return None
        references = edit_data.get("reference_paths") or []
        if not isinstance(references, list) or index < 0 or index >= len(references):
            return None
        raw_path = references[index]
        path = Path(raw_path) if isinstance(raw_path, str) else None
        return path if path and path.exists() else None

    paths = {
        "preview": order.get("preview_jpg"),
        "production": order.get("cmyk_psd"),
        "source": order.get("output_psd"),
        "logo": edit_data.get("logo_path"),
    }

    if kind == "package":
        from app.services.production_package import get_package_path

        return get_package_path(order["id"])

    raw_path = paths.get(kind)
    if not raw_path:
        return None
    path = Path(raw_path)
    return path if path.exists() else None


def _file_items(order: dict) -> list[OrderFileItem]:
    items: list[OrderFileItem] = []
    for kind in ("preview", "production", "package", "source", "logo"):
        path = _existing_file(kind, order)
        if path:
            items.append(
                OrderFileItem(
                    kind=kind,
                    filename=path.name,
                    download_url=f"/api/files/orders/{order['id']}/{kind}",
                    exists=True,
                )
            )
    references = (order.get("edit_data") or {}).get("reference_paths") or []
    if isinstance(references, list):
        for index, raw_path in enumerate(references):
            path = Path(raw_path) if isinstance(raw_path, str) else None
            if path and path.exists():
                items.append(
                    OrderFileItem(
                        kind=f"reference:{index}",
                        filename=path.name,
                        download_url=f"/api/files/orders/{order['id']}/reference:{index}",
                        exists=True,
                    )
                )
    return items


@router.post("", response_model=FileUploadResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    purpose: str = Form("asset"),
    client_id: int | None = Form(None),
    order_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    purpose = purpose.strip().lower() or "asset"
    if purpose not in {"asset", "logo", "reference"}:
        raise HTTPException(400, "purpose deve ser asset, logo ou reference")

    client = repo.client_get(db, client_id) if client_id else None
    if client_id and not client:
        raise HTTPException(404, "Cliente nao encontrado")

    order = repo.order_get(db, order_id) if order_id else None
    if order_id and not order:
        raise HTTPException(404, "Pedido nao encontrado")

    content = await file.read()
    if purpose == "logo":
        owner = client_id or (order["client_id"] if order else "avulso")
        dest = settings.logos_dir / f"client_{owner}_{uuid.uuid4().hex[:8]}.png"
        stored_path = prepare_logo(content, dest)
        if client_id:
            repo.client_update(db, client_id, logo_path=str(stored_path))
        if order_id:
            repo.order_update_edit_data(db, order_id, {"logo_path": str(stored_path)})
    else:
        suffix = _safe_suffix(file.filename)
        dest = settings.temp_dir / f"{purpose}_{uuid.uuid4().hex[:12]}{suffix}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        stored_path = dest
        if purpose == "reference" and order_id:
            edit_data = dict(order.get("edit_data") or {})
            references = edit_data.get("reference_paths") or []
            if not isinstance(references, list):
                references = []
            references.append(str(stored_path))
            repo.order_update_edit_data(db, order_id, {"reference_paths": references})

    if order_id:
        repo.audit_log(
            db,
            get_current_user(request) or "system",
            f"file_uploaded:{purpose}",
            order_id=order_id,
            details={"filename": file.filename, "stored_path": str(stored_path)},
        )

    return FileUploadResponse(
        purpose=purpose,
        filename=stored_path.name,
        asset_path=str(stored_path),
        download_url=f"/api/files/orders/{order_id}/logo" if purpose == "logo" and order_id else None,
        client_id=client_id,
        order_id=order_id,
    )


@router.get("/orders/{order_id}", response_model=list[OrderFileItem])
def list_order_files(order_id: int, db: Session = Depends(get_db)):
    order = repo.order_get(db, order_id)
    if not order:
        raise HTTPException(404, "Pedido nao encontrado")
    return _file_items(order)


@router.get("/orders/{order_id}/{kind}")
def download_order_file(order_id: int, kind: str, db: Session = Depends(get_db)):
    order = repo.order_get(db, order_id)
    if not order:
        raise HTTPException(404, "Pedido nao encontrado")
    if kind not in {"preview", "production", "package", "source", "logo"} and not kind.startswith("reference:"):
        raise HTTPException(404, "Tipo de arquivo nao encontrado")

    path = _existing_file(kind, order)
    if not path:
        raise HTTPException(404, "Arquivo nao disponivel")

    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(str(path), media_type=media_type, filename=path.name)
