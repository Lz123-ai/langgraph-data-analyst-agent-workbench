# Authentication and Resource Ownership

## Local mode

```env
AUTH_MODE=local
```

This is the default loopback-only development mode. All resources use the `local/local-user` identity.

## Shared token mode

```env
AUTH_MODE=token
API_ACCESS_TOKEN=long-random-secret
```

This protects a shared deployment but is not user-level authorization. Tenant/user headers remain operational labels in this mode.

## OIDC mode

```env
AUTH_MODE=oidc
OIDC_ISSUER=https://identity.example.com/
OIDC_AUDIENCE=data-agent
OIDC_JWKS_URL=https://identity.example.com/.well-known/jwks.json
OIDC_TENANT_CLAIM=tenant_id
OIDC_ALGORITHMS=RS256
```

OIDC mode verifies the JWT signature, issuer, audience, expiry, issued-at time and subject. Dataset and analysis/AgentOps resources are scoped to the trusted tenant and subject claims. A missing tenant claim falls back to the subject, preserving per-user isolation.

The browser login gate stores the access token in `sessionStorage`, never local storage. Production deployments should use short-lived access tokens and an identity provider authorization-code flow at the reverse proxy or a dedicated backend-for-frontend.
