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


def test_cleanup_preview_reports_nothing_when_no_delivered_orders(api_authed_client, db, sample_client, sample_template):
    from app.db import repositories as repo

    repo.order_create(db, sample_client["id"], sample_template["id"], {})

    r = api_authed_client.get("/api/cleanup/preview")
    assert r.status_code == 200
    data = r.json()
    assert data["delivered_orders"] == 0
    assert data["total_files"] == 0


def test_cleanup_preview_counts_files_from_delivered_orders(api_authed_client, db, sample_client, sample_template):
    from app.config import settings
    from app.db import repositories as repo

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


def test_cleanup_execute_deletes_files_and_clears_paths(api_authed_client, db, sample_client, sample_template):
    from app.config import settings
    from app.db import repositories as repo

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
