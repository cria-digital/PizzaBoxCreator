"""Multi-provider AI routing (Claude / Gemini) — SDKs mocked, no real calls."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai import providers
from app.ai.providers import AIUnavailable, active_provider, ai_configured, text_completion, vision_completion


@pytest.fixture
def keys(monkeypatch):
    def setter(anthropic="", gemini="", provider="auto"):
        monkeypatch.setattr(providers.settings, "anthropic_api_key", anthropic)
        monkeypatch.setattr(providers.settings, "gemini_api_key", gemini)
        monkeypatch.setattr(providers.settings, "ai_provider", provider)
    return setter


def test_auto_prefers_anthropic_then_gemini(keys):
    keys(anthropic="a", gemini="g")
    assert active_provider() == "anthropic"
    keys(anthropic="", gemini="g")
    assert active_provider() == "gemini"


def test_explicit_provider_requires_its_key(keys):
    keys(anthropic="", gemini="g", provider="anthropic")
    assert not ai_configured()  # forced anthropic but no anthropic key
    keys(anthropic="", gemini="g", provider="gemini")
    assert active_provider() == "gemini"


def test_raises_when_no_key(keys):
    keys(anthropic="", gemini="")
    assert not ai_configured()
    with pytest.raises(AIUnavailable):
        active_provider()


def test_text_completion_routes_to_gemini(keys, monkeypatch):
    keys(gemini="g", provider="gemini")

    class FakeModels:
        def generate_content(self, model, contents, config):
            return SimpleNamespace(text="resposta gemini")

    fake_client = SimpleNamespace(models=FakeModels())
    fake_types = SimpleNamespace(
        GenerateContentConfig=lambda **kw: kw,
        ThinkingConfig=lambda **kw: kw,
    )
    monkeypatch.setattr(providers, "_gemini", lambda: (fake_client, fake_types))
    assert text_completion("sys", "oi") == "resposta gemini"


def test_vision_completion_routes_to_anthropic(keys, monkeypatch):
    keys(anthropic="a", provider="anthropic")

    class FakeMessages:
        def create(self, **kwargs):
            # confirm the image block was built
            assert kwargs["messages"][0]["content"][0]["type"] == "image"
            return SimpleNamespace(content=[SimpleNamespace(text="ok claude")])

    monkeypatch.setattr(providers, "_anthropic_client",
                        lambda: SimpleNamespace(messages=FakeMessages()))
    assert vision_completion("sys", b"img", "image/jpeg", "prompt") == "ok claude"
