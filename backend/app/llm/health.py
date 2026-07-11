from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from langchain_core.messages import HumanMessage

from app.llm.provider import create_chat_model, current_provider_config
from app.settings import settings


def model_runtime_status() -> dict[str, str | bool | None]:
    """Return configuration state without ever exposing an API key."""
    try:
        config = current_provider_config()
        configuration_error = None
    except ValueError as exc:
        config = None
        configuration_error = str(exc)
    return {
        "enabled": settings.use_llm,
        "provider": config.provider if config else settings.llm_provider,
        "model": config.model if config else settings.llm_model,
        "base_url_configured": bool(config and config.base_url),
        "api_key_configured": bool(config and config.api_key),
        "configuration_error": configuration_error,
    }


def run_model_smoke_test() -> dict[str, str | bool]:
    """Perform an explicit, low-cost provider connectivity check.

    This endpoint is intentionally opt-in: normal application traffic remains
    rule-first and cannot incur a model call unless USE_LLM=true.
    """
    if not settings.use_llm:
        raise HTTPException(status_code=409, detail="Set USE_LLM=true and configure a provider before running a model smoke test.")
    try:
        response = create_chat_model(temperature=0).invoke(
            [
                HumanMessage(
                    content='Return exactly this JSON and nothing else: {"status":"ok"}.',
                )
            ]
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Configured model provider did not complete the smoke test.") from exc

    content = _content_to_text(response.content)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Model smoke test returned invalid JSON.") from exc
    if parsed != {"status": "ok"}:
        raise HTTPException(status_code=502, detail="Model smoke test returned an unexpected response.")
    config = current_provider_config()
    return {"ok": True, "provider": config.provider, "model": config.model}


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in content).strip()
    return str(content).strip()
