from __future__ import annotations


def test_final_files_requires_login(api_client):
    r = api_client.post("/api/final-files/orders/1/export")
    assert r.status_code == 401


def test_export_final_file_builds_package(api_authed_client, db, sample_client, sample_template):
    from app.config import settings
    from app.db import repositories as repo

    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})
    preview = settings.preview_dir / "approved.jpg"
    preview.write_bytes(b"approved-preview")
    repo.order_set_paths(db, order["id"], preview_jpg=str(preview))
    repo.order_update_status(db, order["id"], "preview_sent")

    r = api_authed_client.post(f"/api/final-files/orders/{order['id']}/export")

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "production"
    assert data["package_url"] == f"/api/orders/{order['id']}/package"

    downloaded = api_authed_client.get(f"/api/final-files/orders/{order['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/zip"


def test_export_final_file_rejects_draft_order(api_authed_client, db, sample_client, sample_template):
    from app.db import repositories as repo

    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})

    r = api_authed_client.post(f"/api/final-files/orders/{order['id']}/export")

    assert r.status_code == 409
