from __future__ import annotations

import json
from pathlib import Path

from app.config import Settings


def test_database_url_accepts_railway_postgres_scheme():
    settings = Settings(
        admin_password="strong-password-123",
        secret_key="secret-key-long-enough",
        database_url="postgres://user:pass@host:5432/db",
    )

    assert settings.database_url == "postgresql://user:pass@host:5432/db"


def test_railway_config_uses_healthcheck():
    data = json.loads(Path("railway.json").read_text())

    assert data["build"]["builder"] == "DOCKERFILE"
    assert data["deploy"]["healthcheckPath"] == "/health"
