from __future__ import annotations

from dataclasses import dataclass

from langchain_openai import ChatOpenAI

from app.settings import settings


@dataclass(frozen=True)
class ModelProviderConfig:
    provider: str
    model: str
    api_key: str | None
    base_url: str | None


SUPPORTED_PROVIDERS = {"openai", "openai_compatible", "ollama"}


def current_provider_config() -> ModelProviderConfig:
    provider = settings.llm_provider.lower().strip()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported LLM_PROVIDER={provider!r}. Supported values: {', '.join(sorted(SUPPORTED_PROVIDERS))}."
        )
    if provider == "openai_compatible" and not settings.llm_base_url:
        raise ValueError("LLM_BASE_URL is required for the openai_compatible provider.")
    if provider == "ollama" and not settings.llm_base_url:
        base_url = "http://127.0.0.1:11434/v1"
    else:
        base_url = settings.llm_base_url
    return ModelProviderConfig(
        provider=provider,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=base_url,
    )


def create_chat_model(*, temperature: float = 0) -> ChatOpenAI:
    """Create an OpenAI-protocol chat model for cloud or local providers."""
    config = current_provider_config()
    kwargs: dict[str, object] = {
        "model": config.model,
        "temperature": temperature,
    }
    if config.base_url:
        kwargs["base_url"] = config.base_url
    if config.api_key:
        kwargs["api_key"] = config.api_key
    elif config.provider == "ollama":
        kwargs["api_key"] = "ollama"
    return ChatOpenAI(**kwargs)
