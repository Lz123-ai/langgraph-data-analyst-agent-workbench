from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.observability import SlidingWindowRateLimiter
from app.settings import settings


def test_health_response_has_request_id_and_security_headers() -> None:
    response = TestClient(app).get("/api/health", headers={"X-Request-ID": "trace-test"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "trace-test"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_sliding_window_limiter_returns_retry_after() -> None:
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)
    assert limiter.check("client").allowed is True
    assert limiter.check("client").allowed is True
    denied = limiter.check("client")
    assert denied.allowed is False
    assert denied.retry_after_seconds >= 1


def test_production_configuration_rejects_local_auth(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "auth_mode", "local")
    with pytest.raises(RuntimeError, match="AUTH_MODE=local"):
        settings.validate_deployment()


def test_metrics_and_model_status_are_authenticated_api_surfaces(monkeypatch) -> None:
    monkeypatch.setattr(settings, "use_llm", False)
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200
    metrics = client.get("/api/ops/metrics")
    assert metrics.status_code == 200
    assert "agent_http_requests_total" in metrics.text
    model_status = client.get("/api/ops/model-status")
    assert model_status.status_code == 200
    assert isinstance(model_status.json()["api_key_configured"], bool)
    assert client.post("/api/ops/model-smoke-test").status_code == 409
