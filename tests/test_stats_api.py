from __future__ import annotations

import os
from collections import namedtuple


def test_stats_requires_login(api_client):
    r = api_client.get("/api/stats")
    assert r.status_code == 401


def test_stats_counts_clients_orders_templates(api_authed_client, db, sample_client, sample_template):
    from app.db import repositories as repo

    repo.order_create(db, sample_client["id"], sample_template["id"], {})

    r = api_authed_client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_clients"] == 1
    assert data["total_templates"] == 1
    assert data["orders_by_status"]["draft"] == 1
    assert len(data["recent_orders"]) == 1


def test_stats_with_empty_db(api_authed_client):
    r = api_authed_client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_clients"] == 0
    assert data["total_orders"] == 0
    assert data["orders_by_status"] == {}


def test_storage_requires_login(api_client):
    r = api_client.get("/api/storage")
    assert r.status_code == 401


def test_storage_snapshot_reports_warning_alert_once(api_authed_client, db, monkeypatch):
    from sqlalchemy import func, select

    from app.config import settings
    from app.db.models import AuditLog
    from app.services import storage_service

    DiskUsage = namedtuple("DiskUsage", "total used free")
    monkeypatch.setattr(storage_service.shutil, "disk_usage", lambda _: DiskUsage(100, 85, 15))
    monkeypatch.setattr(settings, "storage_warning_threshold_percent", 80)
    monkeypatch.setattr(settings, "storage_critical_threshold_percent", 90)

    r = api_authed_client.get("/api/storage")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "warning"
    assert data["alert"]["emitted"] is True
    assert data["alert"]["action"] == "storage_alert_warning"

    r = api_authed_client.get("/api/storage")
    assert r.status_code == 200
    assert r.json()["alert"]["reason"] == "cooldown"

    count = db.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "storage_alert_warning")
    )
    assert count == 1


def test_storage_snapshot_reports_critical_alert(api_authed_client, db, monkeypatch):
    from sqlalchemy import func, select

    from app.config import settings
    from app.db.models import AuditLog
    from app.services import storage_service

    DiskUsage = namedtuple("DiskUsage", "total used free")
    monkeypatch.setattr(storage_service.shutil, "disk_usage", lambda _: DiskUsage(100, 95, 5))
    monkeypatch.setattr(settings, "storage_warning_threshold_percent", 80)
    monkeypatch.setattr(settings, "storage_critical_threshold_percent", 90)

    r = api_authed_client.get("/api/storage")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "critical"
    assert data["alert"]["emitted"] is True
    assert data["alert"]["action"] == "storage_alert_critical"

    count = db.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "storage_alert_critical")
    )
    assert count == 1


def test_cleanup_preview_reports_nothing_when_no_delivered_orders(api_authed_client, db, sample_client, sample_template):
    from app.db import repositories as repo

    repo.order_create(db, sample_client["id"], sample_template["id"], {})

    r = api_authed_client.get("/api/cleanup/preview")
    assert r.status_code == 200
    data = r.json()
    assert data["delivered_orders"] == 0
    assert data["total_files"] == 0


def test_cleanup_preview_counts_files_from_delivered_orders(
    api_authed_client,
    db,
    sample_client,
    sample_template,
    monkeypatch,
):
    from app.config import settings
    from app.db import repositories as repo

    monkeypatch.setattr(settings, "storage_retention_delivered_days", 0)
    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})

    preview_path = settings.preview_dir / "fake_preview.jpg"
    preview_path.write_bytes(b"0" * 200_000)  # big enough to round to a visible MB value
    repo.order_set_paths(db, order["id"], preview_jpg=str(preview_path))
    repo.order_update_status(db, order["id"], "delivered")

    r = api_authed_client.get("/api/cleanup/preview")
    assert r.status_code == 200
    data = r.json()
    assert data["delivered_orders"] == 1
    assert data["files_from_delivered"] == 1
    assert data["total_mb"] > 0


def test_cleanup_execute_deletes_files_and_clears_paths(
    api_authed_client,
    db,
    sample_client,
    sample_template,
    monkeypatch,
):
    from app.config import settings
    from app.db import repositories as repo

    monkeypatch.setattr(settings, "storage_retention_delivered_days", 0)
    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})

    preview_path = settings.preview_dir / "fake_preview.jpg"
    preview_path.write_bytes(b"fake-jpeg-bytes")
    repo.order_set_paths(db, order["id"], preview_jpg=str(preview_path))
    repo.order_update_status(db, order["id"], "delivered")

    r = api_authed_client.post("/api/cleanup/execute")
    assert r.status_code == 200
    data = r.json()
    assert data["deleted_files"] == 1
    assert not preview_path.exists()

    updated = repo.order_get(db, order["id"])
    assert updated["preview_jpg"] is None


def test_cleanup_execute_preserves_recent_delivered_order_by_default(
    api_authed_client,
    db,
    sample_client,
    sample_template,
):
    from app.config import settings
    from app.db import repositories as repo

    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})
    preview_path = settings.preview_dir / "recent_delivered.jpg"
    preview_path.write_bytes(b"fake-jpeg-bytes")
    repo.order_set_paths(db, order["id"], preview_jpg=str(preview_path))
    repo.order_update_status(db, order["id"], "delivered")

    r = api_authed_client.post("/api/storage/cleanup/execute")
    assert r.status_code == 200
    data = r.json()
    assert data["deleted_files"] == 0
    assert preview_path.exists()
    assert repo.order_get(db, order["id"])["preview_jpg"] == str(preview_path)


def test_cleanup_execute_deletes_eligible_temp_and_backup_files(api_authed_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "storage_retention_temp_hours", 0)
    monkeypatch.setattr(settings, "storage_backup_max_files", 1)

    temp_file = settings.temp_dir / "old-upload.bin"
    temp_file.write_bytes(b"temp")
    old_backup = settings.backups_dir / "pizzabox_20260101_000000.db.gz"
    old_backup.write_bytes(b"old")
    newest_backup = settings.backups_dir / "pizzabox_20260102_000000.db.gz"
    newest_backup.write_bytes(b"new")
    os.utime(old_backup, (1, 1))
    os.utime(newest_backup, (2, 2))

    r = api_authed_client.post("/api/storage/cleanup/execute")
    assert r.status_code == 200
    data = r.json()
    assert data["deleted_files"] == 2
    assert not temp_file.exists()
    assert not old_backup.exists()
    assert newest_backup.exists()
