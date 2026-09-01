from __future__ import annotations

import io
from pathlib import Path

from PIL import Image


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 40, 20)).save(buf, "PNG")
    return buf.getvalue()


def test_files_api_requires_login(api_client):
    r = api_client.get("/api/files/orders/1")
    assert r.status_code == 401


def test_upload_logo_updates_client_and_order(api_authed_client, db, sample_client, sample_template):
    from app.db import repositories as repo

    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})

    r = api_authed_client.post(
        "/api/files",
        data={"purpose": "logo", "client_id": str(sample_client["id"]), "order_id": str(order["id"])},
        files={"file": ("logo.png", _png_bytes(), "image/png")},
    )

    assert r.status_code == 200
    data = r.json()
    assert data["purpose"] == "logo"
    assert data["asset_path"].endswith(".png")
    assert Path(data["asset_path"]).exists()
    assert repo.client_get(db, sample_client["id"])["logo_path"] == data["asset_path"]
    assert repo.order_get(db, order["id"])["edit_data"]["logo_path"] == data["asset_path"]


def test_list_and_download_order_files(api_authed_client, db, sample_client, sample_template):
    from app.config import settings
    from app.db import repositories as repo

    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})
    preview = settings.preview_dir / "preview.jpg"
    preview.write_bytes(b"fake-preview")
    repo.order_set_paths(db, order["id"], preview_jpg=str(preview))

    r = api_authed_client.get(f"/api/files/orders/{order['id']}")
    assert r.status_code == 200
    assert r.json() == [{
        "kind": "preview",
        "filename": "preview.jpg",
        "download_url": f"/api/files/orders/{order['id']}/preview",
        "exists": True,
    }]

    downloaded = api_authed_client.get(f"/api/files/orders/{order['id']}/preview")
    assert downloaded.status_code == 200
    assert downloaded.content == b"fake-preview"
