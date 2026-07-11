from __future__ import annotations

import pytest

from app.llm import health, provider
from app.settings import settings


def test_openai_compatible_provider_passes_model_key_and_base_url(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeChatModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(provider, "ChatOpenAI", FakeChatModel)
    monkeypatch.setattr(settings, "llm_provider", "openai_compatible")
    monkeypatch.setattr(settings, "llm_model", "deepseek-chat")
    monkeypatch.setattr(settings, "llm_api_key", "provider-key")
    monkeypatch.setattr(settings, "llm_base_url", "https://example.test/v1")

    provider.create_chat_model()
    assert captured["model"] == "deepseek-chat"
    assert captured["api_key"] == "provider-key"
    assert captured["base_url"] == "https://example.test/v1"


def test_openai_compatible_provider_requires_base_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "openai_compatible")
    monkeypatch.setattr(settings, "llm_base_url", None)
    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        provider.current_provider_config()


def test_ollama_uses_local_default_and_placeholder_key(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeChatModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(provider, "ChatOpenAI", FakeChatModel)
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "llm_model", "qwen3:8b")
    monkeypatch.setattr(settings, "llm_api_key", None)
    monkeypatch.setattr(settings, "llm_base_url", None)

    provider.create_chat_model()
    assert captured["base_url"] == "http://127.0.0.1:11434/v1"
    assert captured["api_key"] == "ollama"


def test_model_smoke_test_requires_explicit_enablement(monkeypatch) -> None:
    monkeypatch.setattr(settings, "use_llm", False)
    with pytest.raises(Exception, match="USE_LLM=true"):
        health.run_model_smoke_test()


def test_model_smoke_test_uses_fixed_json_probe(monkeypatch) -> None:
    class FakeModel:
        def invoke(self, messages):
            assert "Return exactly" in messages[0].content
            return type("Response", (), {"content": '{"status":"ok"}'})()

    monkeypatch.setattr(settings, "use_llm", True)
    monkeypatch.setattr(settings, "llm_provider", "openai_compatible")
    monkeypatch.setattr(settings, "llm_model", "deepseek-chat")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_base_url", "https://example.test/v1")
    monkeypatch.setattr(health, "create_chat_model", lambda temperature: FakeModel())

    assert health.run_model_smoke_test() == {"ok": True, "provider": "openai_compatible", "model": "deepseek-chat"}
