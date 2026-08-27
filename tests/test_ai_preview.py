"""AI client-approval preview (Gemini image model) — image generation mocked, no real calls."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.ai.box_designer import build_box_prompt


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 36), (10, 20, 30)).save(buf, "PNG")
    return buf.getvalue()


def test_build_box_prompt_includes_order_data():
    prompt = build_box_prompt(
        client={"name": "Yeti Pizzaria", "phone": "1999", "instagram": "@yeti"},
        template={"product_type": "esfiha"},
        edit_data={"telefone": "(19) 99888-7766", "instagram": "@yetipizzaria",
                   "frase": "Feito com amor", "tema_fundo": "premium"},
    )
    assert "Yeti Pizzaria" in prompt
    assert "esfiha" in prompt
    assert "Produto: esfiha" in prompt
    assert "(19) 99888-7766" in prompt
    assert "@yetipizzaria" in prompt
    assert "Feito com amor" in prompt
    assert "Como nao ha imagem de referencia" in prompt


def test_generate_ai_preview_saves_preview_and_advances_status(db, sample_client, sample_template,
                                                               monkeypatch):
    import app.services.order_service as svc
    from app.db import repositories as repo
    from app.models.commands import OrderStatus

    monkeypatch.setattr(svc, "image_generation", lambda prompt, reference=None: _png_bytes())

    order = repo.order_create(db, sample_client["id"], sample_template["id"],
                              {"telefone": "(19) 90000-0000"}, quantidade=100)

    updated, notes = svc.generate_ai_preview(order["id"], db)

    assert updated["status"] == OrderStatus.preview_sent.value
    assert updated["preview_jpg"] and updated["preview_jpg"].endswith(".jpg")
    from pathlib import Path
    assert Path(updated["preview_jpg"]).exists()
    assert notes and "IA" in notes[0]
    assert repo.revision_count(db, order["id"]) == 1
    assert repo.revision_get_latest(db, order["id"])["preview_source"] == "ai"


def test_ai_preview_cache_ignores_standard_preview(db, sample_client, sample_template,
                                                   monkeypatch, tmp_path):
    import app.services.order_service as svc
    from app.db import repositories as repo
    from app.config import settings

    standard_preview = tmp_path / "standard.jpg"
    standard_preview.write_bytes(_png_bytes())
    monkeypatch.setattr(settings, "preview_dir", tmp_path)

    calls = {"count": 0}

    def fake_image_generation(prompt, reference=None):
        calls["count"] += 1
        return _png_bytes()

    monkeypatch.setattr(svc, "image_generation", fake_image_generation)

    order = repo.order_create(db, sample_client["id"], sample_template["id"],
                              {"telefone": "(19) 90000-0000"}, quantidade=100)
    repo.revision_create(db, order["id"], 1, order["edit_data"], str(standard_preview),
                         preview_source="psd")

    updated, notes = svc.generate_ai_preview(order["id"], db)

    assert calls["count"] == 1
    assert "IA" in notes[0]
    assert updated["preview_jpg"] != str(standard_preview)


def test_ai_preview_rate_limit_counts_only_ai_revisions(db, sample_client, sample_template,
                                                        monkeypatch, tmp_path):
    import app.services.order_service as svc
    from app.db import repositories as repo
    from app.config import settings

    monkeypatch.setattr(settings, "ai_preview_max_per_order", 1)
    monkeypatch.setattr(settings, "ai_preview_cache_enabled", False)
    monkeypatch.setattr(settings, "preview_dir", tmp_path)
    monkeypatch.setattr(svc, "image_generation", lambda prompt, reference=None: _png_bytes())

    order = repo.order_create(db, sample_client["id"], sample_template["id"],
                              {"telefone": "(19) 90000-0000"}, quantidade=100)
    psd_preview = tmp_path / "standard.jpg"
    psd_preview.write_bytes(_png_bytes())
    repo.revision_create(db, order["id"], 1, order["edit_data"], str(psd_preview),
                         preview_source="psd")

    svc.generate_ai_preview(order["id"], db)

    with pytest.raises(Exception) as exc:
        svc.generate_ai_preview(order["id"], db)
    assert "Limite" in str(exc.value)


def test_image_generation_requires_gemini_key(monkeypatch):
    from app.ai.providers import AIUnavailable, image_generation
    from app.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(AIUnavailable):
        image_generation("qualquer prompt")
