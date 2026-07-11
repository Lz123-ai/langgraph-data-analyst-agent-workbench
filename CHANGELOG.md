# Changelog

## 0.4.0 - 2026-07-11

### Added

- Production startup guardrails for authentication, CORS, trusted hosts, request IDs, security headers, and rate limiting.
- Authenticated Prometheus-format API metrics and safe model runtime status / explicit live-provider smoke test endpoints.
- Tenant-scoped user improvement logs, read-only system logs, and same-ID retry for failed or cancelled analysis tasks.
- LLM verification script, production-readiness guide, Dependabot configuration, and code-of-conduct policy.

### Changed

- CI now runs both the batch and enterprise Agent evaluation suites.

## 0.3.0 - 2026-07-10

### Added

- Schema-grounded answerability and generic categorical filtering.
- SQLite task/event persistence, SSE replay, cancellation, timeout, concurrency limit, and restart auto-rerun.
- Provider LLM usage separated from deterministic payload metrics.
- Trace redaction, dataset limits/deletion/retention, optional bearer protection, and business template registry.
- Layered evaluation, threat model, contributing guide, and CI foundation.

### Fixed

- Windows shutdown terminates reload child processes.
- `.env` loads consistently in local Python startup modes.

### Extended

- OpenAI-compatible and Ollama model provider configuration.
- OIDC/JWT validation with dataset and Agent task ownership enforcement.
- Interrupted SQLite tasks automatically rerun with the same task ID after restart.
- Planner, insight, review, report, and label responsibilities split into dedicated graph modules.
- Windows Docker prerequisite and Compose smoke-test scripts.
