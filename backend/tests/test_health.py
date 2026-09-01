"""Health probe endpoint."""

from __future__ import annotations


def test_health_reports_ok_and_database_reachable(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200

    data = r.json()
    assert data["status"] == "ok"
    assert data["database"] is True
    assert "whatsapp_enabled" in data
