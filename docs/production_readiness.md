# Production Readiness

## Supported deployment boundary

The Compose stack is suitable for demos and a single trusted deployment. For a
shared deployment, terminate TLS at a reverse proxy, set `APP_ENV=production`,
use `AUTH_MODE=oidc` (or a rotated shared token for short-lived demos), and set
explicit `CORS_ORIGINS` and `TRUSTED_HOSTS` values.

The application refuses to start in production with local authentication,
wildcard CORS, incomplete OIDC configuration, or token mode without an access
token.

## Runtime controls

- `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS` protect one API process
  with an in-memory sliding window. Apply a shared Redis or gateway limit when
  running multiple replicas.
- Each API response includes `X-Request-ID`; structured request-completion logs
  and authenticated Prometheus-format metrics are available at
  `GET /api/ops/metrics`.
- `POST /api/analysis/tasks/{task_id}/retry` reruns a failed or cancelled task
  with the same ID after clearing previous trace and token accounting. Restarted
  in-flight tasks are automatically rerun and marked with `task_resumed`.
- `GET /api/ops/model-status` is safe to call because it never returns a key.
  `POST /api/ops/model-smoke-test` is an explicit, low-cost live connectivity
  check and requires `USE_LLM=true`.

## Required next infrastructure step

SQLite and restart-from-beginning recovery are intentionally retained for the
local-first release. A multi-replica production deployment requires a PostgreSQL
storage adapter, object storage for uploads, a shared queue/rate limiter, and
LangGraph checkpoint persistence before horizontal scaling is claimed.
