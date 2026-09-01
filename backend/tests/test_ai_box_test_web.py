from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import settings


@pytest.fixture
def logged_in(api_client, monkeypatch):
    monkeypatch.setattr(settings, "admin_user", "admin")
    monkeypatch.setattr(settings, "admin_password", "test-password-123")
    api_client.post("/login", data={"username": "admin", "password": "test-password-123"},
                    follow_redirects=False)
    return api_client


def _fake_pipeline_result(tmp_path):
    art = tmp_path / "art"
    pdf = Path("output/pdf")
    preflight = tmp_path / "preflight"
    art.mkdir()
    pdf.mkdir(parents=True, exist_ok=True)
    preflight.mkdir()
    for path in [
        art / "job_preview.jpg",
        art / "job_ai_preview.jpg",
        art / "job_generated.png",
        art / "job_pipeline.json",
        preflight / "job_overlay.jpg",
        preflight / "job_safety.jpg",
        pdf / "job_arte_cmyk.pdf",
    ]:
        path.write_bytes(b"file")
    return {
        "job_id": "job",
        "model": "gemini-3-pro-image",
        "generated": str(art / "job_generated.png"),
        "generated_preview": str(art / "job_ai_preview.jpg"),
        "metadata": str(art / "job_pipeline.json"),
        "master": {
            "approval_preview": str(art / "job_preview.jpg"),
            "source_px": {"width": 5504, "height": 3072},
            "canvas_px": {"width": 9713, "height": 5154},
        },
        "preflight": str(preflight / "job_overlay.jpg"),
        "safety": str(preflight / "job_safety.jpg"),
        "cmyk": {"tac_after": {"max_tac": 298.0, "over_280_pct": 1.2, "over_300_pct": 0.0}},
        "pdf": {
            "pdf": str(pdf / "job_arte_cmyk.pdf"),
            "color_mode": "CMYK",
            "image_color_spaces": ["/DeviceCMYK"],
            "page_size_mm": {"width": 822.35, "height": 436.35},
            "trim_size_mm": {"width": 816.0, "height": 430.0},
        },
    }


def test_ai_box_test_requires_login(api_client):
    r = api_client.get("/teste/ia-caixa", follow_redirects=False)

    assert r.status_code == 303
    assert "/login" in r.headers["location"]


def test_ai_box_test_page_renders(logged_in, tmp_path, monkeypatch):
    spec = tmp_path / "spec.json"
    die = tmp_path / "faca.pdf"
    spec.write_text(json.dumps({"ok": True}), encoding="utf-8")
    die.write_bytes(b"pdf")
    monkeypatch.setattr(settings, "ai_pilot_spec_path", str(spec))
    monkeypatch.setattr(settings, "ai_pilot_die_pdf_path", str(die))
    monkeypatch.setattr(settings, "gemini_api_key", "g")

    r = logged_in.get("/teste/ia-caixa")

    assert r.status_code == 200
    assert "Teste IA Caixa" in r.text
    assert "Gerar arte de teste" in r.text
    assert "Parar execução" in r.text
    assert "Manter parte de trás vazia" in r.text
    assert 'name="job_id"' in r.text


def test_ai_box_test_post_runs_pipeline_and_shows_links(logged_in, tmp_path, monkeypatch):
    import app.web.views as views

    spec = tmp_path / "spec.json"
    die = tmp_path / "faca.pdf"
    spec.write_text(json.dumps({"ok": True}), encoding="utf-8")
    die.write_bytes(b"pdf")
    monkeypatch.setattr(settings, "ai_pilot_spec_path", str(spec))
    monkeypatch.setattr(settings, "ai_pilot_die_pdf_path", str(die))
    monkeypatch.setattr(settings, "gemini_api_key", "g")

    fake = _fake_pipeline_result(tmp_path)
    calls = {}
    monkeypatch.setattr(settings, "art_masters_dir", tmp_path / "art")
    def fake_run_pipeline(**kwargs):
        calls.update(kwargs)
        return fake

    monkeypatch.setattr(views, "run_ai_art_pipeline", fake_run_pipeline)

    r = logged_in.post(
        "/teste/ia-caixa",
        data={
            "brand": "Pizzaria Teste",
            "phone": "(11) 99999-9999",
            "instagram": "@teste",
            "frase": "Sua pizza chegou!",
            "tema": "premium",
            "product_type": "pizza",
            "empty_back_panel": "1",
        },
        files={"reference": ("ref.png", b"png", "image/png")},
    )

    assert r.status_code == 200
    assert "Resultado job" in r.text
    assert "PDF CMYK" in r.text
    assert "IA bruta" in r.text
    assert "/teste/ia-caixa/arquivo/art/job_preview.jpg" in r.text
    assert "/teste/ia-caixa/arquivo/art/job_ai_preview.jpg" in r.text
    assert "/DeviceCMYK" in r.text
    assert calls["empty_back_panel"] is True
    assert calls["edit_data"]["empty_back_panel"] is True


def test_ai_box_test_artifact_serves_only_known_roots(logged_in, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "art_masters_dir", tmp_path)
    path = tmp_path / "preview.jpg"
    path.write_bytes(b"jpg")

    r = logged_in.get("/teste/ia-caixa/arquivo/art/preview.jpg")

    assert r.status_code == 200
    assert r.content == b"jpg"


def test_ai_box_test_cancel_marks_running_job(logged_in):
    from app.services.ai_job_control import finish_job, register_job

    event = register_job("ai_test_1234567890")
    try:
        r = logged_in.post("/teste/ia-caixa/cancelar", data={"job_id": "ai_test_1234567890"})

        assert r.status_code == 200
        assert r.json()["cancelled"] is True
        assert event.is_set()
    finally:
        finish_job("ai_test_1234567890")
