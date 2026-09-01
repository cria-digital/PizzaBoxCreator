"""Settings helpers: CORS origin parsing."""

from __future__ import annotations

from app.config import settings


def test_cors_origin_list_wildcard(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "*")
    assert settings.cors_origin_list == ["*"]


def test_cors_origin_list_splits_and_strips(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "https://a.com, https://b.com ")
    assert settings.cors_origin_list == ["https://a.com", "https://b.com"]


def test_cors_origin_list_empty_falls_back_to_wildcard(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "")
    assert settings.cors_origin_list == ["*"]
