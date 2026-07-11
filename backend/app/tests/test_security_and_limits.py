from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import security
from app.analysis.service import _payload_summary
from app.main import app
from app.settings import settings


def test_optional_api_token_protects_non_health_routes(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_access_token", "test-secret")
    monkeypatch.setattr(settings, "auth_mode", "token")
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/ops/summary").status_code == 401
    assert client.get("/api/ops/summary?access_token=test-secret").status_code == 401
    assert client.get("/api/ops/summary", headers={"Authorization": "Bearer test-secret"}).status_code == 200


def test_oidc_identity_isolates_dataset_resources(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "oidc")
    monkeypatch.setattr(
        security,
        "_validate_oidc_token",
        lambda token: {"sub": f"user-{token}", "tenant_id": f"tenant-{token}"},
    )
    client = TestClient(app)
    owner_headers = {"Authorization": "Bearer owner"}
    other_headers = {"Authorization": "Bearer other"}

    uploaded = client.post(
        "/api/datasets/upload",
        headers=owner_headers,
        files={"file": ("owned.csv", b"category,sales\nA,1\n", "text/csv")},
    )
    assert uploaded.status_code == 200
    dataset_id = uploaded.json()["dataset"]["dataset_id"]
    assert client.get(f"/api/datasets/{dataset_id}", headers=owner_headers).status_code == 200
    assert client.get(f"/api/datasets/{dataset_id}", headers=other_headers).status_code == 404
    assert client.post(
        "/api/analysis/tasks",
        headers=other_headers,
        json={"dataset_id": dataset_id, "question": "Average sales by category"},
    ).status_code == 404
    assert client.delete(f"/api/datasets/{dataset_id}", headers=owner_headers).status_code == 204


def test_oidc_identity_isolates_user_improvement_logs(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "oidc")
    monkeypatch.setattr(
        security,
        "_validate_oidc_token",
        lambda token: {"sub": f"user-{token}", "tenant_id": f"tenant-{token}"},
    )
    client = TestClient(app)
    owner_headers = {"Authorization": "Bearer owner"}
    other_headers = {"Authorization": "Bearer other"}
    created = client.post(
        "/api/improvements",
        headers=owner_headers,
        json={"issue": "owner-only issue", "resolution": "owner-only resolution", "status": "open"},
    )
    assert created.status_code == 201
    log_id = created.json()["log_id"]
    assert client.get(f"/api/improvements/{log_id}", headers=other_headers).status_code == 404
    other_logs = client.get("/api/improvements", headers=other_headers).json()["logs"]
    assert all(log["log_id"] != log_id for log in other_logs)
    assert client.delete(f"/api/improvements/{log_id}", headers=owner_headers).status_code == 204


def test_oidc_validator_checks_real_signature_issuer_and_audience(monkeypatch) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "user-1",
            "tenant_id": "tenant-1",
            "iss": "https://issuer.test/",
            "aud": "data-agent",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )

    monkeypatch.setattr(settings, "oidc_issuer", "https://issuer.test/")
    monkeypatch.setattr(settings, "oidc_audience", "data-agent")
    monkeypatch.setattr(settings, "oidc_jwks_url", "https://issuer.test/jwks.json")
    monkeypatch.setattr(settings, "oidc_algorithms", ["RS256"])
    monkeypatch.setattr(
        security,
        "_jwks_client",
        lambda _: SimpleNamespace(get_signing_key_from_jwt=lambda __: SimpleNamespace(key=private_key.public_key())),
    )

    claims = security._validate_oidc_token(token)
    assert claims["sub"] == "user-1"
    assert claims["tenant_id"] == "tenant-1"


def test_upload_row_limit_and_dataset_delete(monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_dataset_rows", 2)
    client = TestClient(app)
    too_large = client.post(
        "/api/datasets/upload",
        files={"file": ("too-large.csv", b"category,sales\nA,1\nB,2\nC,3\n", "text/csv")},
    )
    assert too_large.status_code == 413

    monkeypatch.setattr(settings, "max_dataset_rows", 10)
    uploaded = client.post(
        "/api/datasets/upload",
        files={"file": ("deletable.csv", b"category,sales\nA,1\n", "text/csv")},
    )
    assert uploaded.status_code == 200
    dataset_id = uploaded.json()["dataset"]["dataset_id"]
    assert client.delete(f"/api/datasets/{dataset_id}").status_code == 204
    assert client.get(f"/api/datasets/{dataset_id}").status_code == 404


def test_trace_summary_redacts_sample_and_result_rows(monkeypatch) -> None:
    monkeypatch.setattr(settings, "trace_include_sample_data", False)
    summary = _payload_summary(
        {
            "dataset_preview": [{"customer": "sensitive-name"}],
            "execution_result": {
                "kind": "group_aggregate",
                "source": "duckdb",
                "tables": [{"name": "result", "rows": [{"customer": "sensitive-name"}]}],
            },
        }
    )
    assert "sensitive-name" not in summary
    assert '"redacted":true' in summary
