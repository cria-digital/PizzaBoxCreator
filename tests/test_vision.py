"""AI vision analysis of a box photo (Claude mocked — no real API calls)."""

from __future__ import annotations

import pytest

from app.ai import vision
from app.ai.vision import analyze_box_photo, VisionUnavailable, _coerce, _parse_json

TEMPLATES = [{"id": 1, "display_name": "Caixa A"}, {"id": 2, "display_name": "Caixa B"}]


def _patch_ai(monkeypatch, text):
    """Stub the provider layer so no real AI SDK/key is needed."""
    monkeypatch.setattr(vision, "vision_completion",
                        lambda system, image_bytes, media_type, prompt: text)


def test_raises_when_no_provider(monkeypatch):
    from app.ai.providers import AIUnavailable

    def unavailable(*a, **k):
        raise AIUnavailable("nenhuma IA")

    monkeypatch.setattr(vision, "vision_completion", unavailable)
    with pytest.raises(VisionUnavailable):
        analyze_box_photo(b"img", TEMPLATES)


def test_analyzes_photo_and_returns_match_and_data(monkeypatch):
    _patch_ai(monkeypatch,
                  '{"template_id": 2, "confianca": "alta", "telefone": "(11) 98888-7777", '
                  '"instagram": "@pizza", "frase": "A melhor!"}')
    result = analyze_box_photo(b"fake-jpeg", TEMPLATES)
    assert result["template_id"] == 2
    assert result["confianca"] == "alta"
    assert result["telefone"] == "(11) 98888-7777"
    assert result["instagram"] == "@pizza"


def test_strips_json_code_fences(monkeypatch):
    _patch_ai(monkeypatch, '```json\n{"template_id": 1}\n```')
    assert analyze_box_photo(b"x", TEMPLATES)["template_id"] == 1


def test_coerce_drops_unknown_template_and_blank_fields():
    out = _coerce({"template_id": 99, "telefone": "  ", "instagram": "@x", "frase": None,
                   "confianca": "invalida"}, TEMPLATES)
    assert out["template_id"] is None       # 99 not in catalog
    assert out["telefone"] is None          # blank
    assert out["instagram"] == "@x"
    assert out["confianca"] is None         # not one of alta/media/baixa


def test_parse_json_rejects_non_object(monkeypatch):
    with pytest.raises(VisionUnavailable):
        _parse_json("[1, 2, 3]")


def test_invalid_json_raises_vision_unavailable():
    with pytest.raises(VisionUnavailable):
        _parse_json("not json at all")
