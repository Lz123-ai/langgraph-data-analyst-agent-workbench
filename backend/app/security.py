from __future__ import annotations

import hmac
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Header, HTTPException, Query, Request, status
from jwt import PyJWKClient

from app.ops.models import IdentityContext
from app.settings import settings


def require_api_access(
    request: Request,
    authorization: str | None = Header(default=None),
    access_token: str | None = Query(default=None),
    x_tenant_id: str = Header(default="local"),
    x_user_id: str = Header(default="local-user"),
) -> None:
    """Authenticate the request and attach a trusted identity to request.state."""
    mode = settings.auth_mode
    if mode == "local":
        request.state.identity = IdentityContext(tenant_id="local", user_id="local-user")
        return

    scheme, _, supplied = (authorization or "").partition(" ")
    query_candidate = (access_token or "") if request.url.path.endswith("/events") else ""
    token = supplied if scheme.lower() == "bearer" else query_candidate
    if not token:
        _unauthorized("A bearer token is required.")

    if mode == "token":
        expected = settings.api_access_token or ""
        if not expected or not hmac.compare_digest(token, expected):
            _unauthorized("A valid bearer token is required.")
        request.state.identity = IdentityContext(tenant_id=x_tenant_id, user_id=x_user_id)
        return

    if mode == "oidc":
        claims = _validate_oidc_token(token)
        subject = str(claims.get("sub") or "")
        if not subject:
            _unauthorized("OIDC token is missing the sub claim.")
        tenant = str(claims.get(settings.oidc_tenant_claim) or claims.get("org_id") or subject)
        request.state.identity = IdentityContext(tenant_id=tenant[:64], user_id=subject[:64])
        return

    raise HTTPException(status_code=500, detail=f"Unsupported AUTH_MODE={mode!r}.")


def identity_from_request(request: Request) -> IdentityContext:
    identity = getattr(request.state, "identity", None)
    if not isinstance(identity, IdentityContext):
        raise HTTPException(status_code=500, detail="Authenticated identity is unavailable.")
    return identity


def _validate_oidc_token(token: str) -> dict[str, Any]:
    if not settings.oidc_issuer or not settings.oidc_audience or not settings.oidc_jwks_url:
        raise HTTPException(
            status_code=500,
            detail="OIDC_ISSUER, OIDC_AUDIENCE, and OIDC_JWKS_URL are required in OIDC mode.",
        )
    try:
        signing_key = _jwks_client(settings.oidc_jwks_url).get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=settings.oidc_algorithms,
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        _unauthorized(f"OIDC token validation failed: {exc}")


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, lifespan=300)


def _unauthorized(detail: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
