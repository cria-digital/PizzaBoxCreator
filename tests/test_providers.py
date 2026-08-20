"""Multi-provider AI routing (Claude / Gemini / Ollama) — no real API calls."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai import providers
from app.ai.providers import AIUnavailable, active_provider, ai_configured, text_completion, vision_completion


@pytest.fixture
def keys(monkeypatch):
    def setter(anthropic="", gemini="", provider="auto", ollama_url="http://localhost:11434",
               ollama_model="llama3.2:3b"):
        monkeypatch.setattr(providers.settings, "anthropic_api_key", anthropic)
        monkeypatch.setattr(providers.settings, "gemini_api_key", gemini)
        monkeypatch.setattr(providers.settings, "ai_provider", provider)
        monkeypatch.setattr(providers.settings, "ollama_base_url", ollama_url)
        monkeypatch.setattr(providers.settings, "ollama_model", ollama_model)
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
    keys(anthropic="", gemini="", provider="ollama")
    assert active_provider() == "ollama"


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


def test_text_completion_routes_to_ollama(keys, monkeypatch):
    keys(provider="ollama", ollama_url="http://ollama.test", ollama_model="llama3.2:3b")

    class FakeResponse:
        text = ""
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "resposta llama"}}

    def fake_post(url, json, timeout):
        assert url == "http://ollama.test/api/chat"
        assert json["model"] == "llama3.2:3b"
        assert json["stream"] is False
        assert json["messages"][0]["role"] == "system"
        assert json["messages"][1]["content"] == "oi"
        assert timeout == 60
        return FakeResponse()

    monkeypatch.setattr(providers.httpx, "post", fake_post)
    assert text_completion("sys", "oi") == "resposta llama"


def test_vision_completion_rejects_ollama_text_only(keys):
    keys(provider="ollama")
    with pytest.raises(AIUnavailable, match="apenas para texto"):
        vision_completion("sys", b"img", "image/jpeg", "prompt")


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
