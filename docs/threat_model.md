# Threat Model

## Protected assets

- Uploaded data and generated results.
- Agent traces, questions, reports, and model credentials.
- Host filesystem and process environment.

## Trust boundary

The default app binds to loopback and assumes a trusted local user. Shared-token mode is only a deployment guard. OIDC mode verifies issuer, audience, signature and required claims, then enforces tenant/user ownership for datasets and Agent task resources.

## Mitigations

- Server-generated upload paths constrained to the upload root.
- Upload byte, row, column, result, concurrency, and duration limits.
- One read-only DuckDB `SELECT`; no arbitrary generated Python execution.
- Explicit rejection of unsupported external, predictive, causal, destructive, and injection requests.
- Trace sample/result redaction by default.
- Optional bearer protection for shared deployments.
- OIDC/JWT verification and resource ownership checks for multi-user deployments.

## Accepted risks

- Excel parsing should run in a resource-limited container for hostile public uploads.
- SQLite is not intended for high-concurrency hostile multi-tenant workloads.
- A shared bearer token is a deployment guard, not user-level authorization.
