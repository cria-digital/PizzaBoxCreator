"""Shared fixtures: every test gets its own SQLite database and storage dirs under tmp_path."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_live_ai(monkeypatch):
    """Keep the whole suite off real LLM providers: deterministic parsing, zero API cost."""
    from app.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "ai_provider", "auto")
    monkeypatch.setattr(settings, "ollama_base_url", "http://localhost:11434")
    monkeypatch.setattr(settings, "ollama_model", "llama3.2:3b")


@pytest.fixture(autouse=True)
def _reset_engine():
    """Reset the SQLAlchemy engine singleton between tests."""
    from app.db.session import reset_engine
    reset_engine()
    yield
    reset_engine()


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    from app.config import settings

    db_file = tmp_path / "test.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_file}")
    monkeypatch.setattr(settings, "db_path", db_file)
    monkeypatch.setattr(settings, "templates_dir", tmp_path / "gabaritos")
    monkeypatch.setattr(settings, "output_dir", tmp_path / "output")
    monkeypatch.setattr(settings, "preview_dir", tmp_path / "preview")
    monkeypatch.setattr(settings, "temp_dir", tmp_path / "temp")
    monkeypatch.setattr(settings, "thumbnails_dir", tmp_path / "thumbnails")
    monkeypatch.setattr(settings, "logos_dir", tmp_path / "logos")
    settings.ensure_dirs()

    from app.db.session import init_db
    init_db()
    return db_file


@pytest.fixture
def db(db_path):
    from app.db.session import _get_session_factory

    SessionLocal = _get_session_factory()
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def api_client(db_path):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_client(db):
    from app.db import repositories as repo

    return repo.client_create(db, "Pizzaria Teste", "11999998888")


@pytest.fixture
def sample_template(db):
    from app.db import repositories as repo

    return repo.template_create(
        db,
        filename="dummy.psd",
        display_name="Caixa Teste",
        description="Modelo de teste",
        size_cm=30,
        product_type="pizza",
        editable_fields=[
            {"name": "telefone", "type": "text", "label": "Telefone", "required": False},
        ],
    )
