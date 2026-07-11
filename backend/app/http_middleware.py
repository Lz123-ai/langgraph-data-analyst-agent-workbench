from __future__ import annotations

import json
import logging
from time import monotonic
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.observability import SlidingWindowRateLimiter, metrics
from app.settings import settings

logger = logging.getLogger("app.http")


class RequestProtectionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.rate_limiter = SlidingWindowRateLimiter(
            limit=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID", "").strip()[:128] or uuid4().hex
        request.state.request_id = request_id
        path = request.url.path
        if path not in {"/api/health", "/docs", "/openapi.json", "/redoc"}:
            client_ip = request.client.host if request.client else "unknown"
            decision = self.rate_limiter.check(client_ip)
            if not decision.allowed:
                response = Response(
                    content=json.dumps({"detail": "Rate limit exceeded.", "request_id": request_id}),
                    status_code=429,
                    media_type="application/json",
                )
                response.headers["Retry-After"] = str(decision.retry_after_seconds)
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["X-Frame-Options"] = "DENY"
                response.headers["Referrer-Policy"] = "no-referrer"
                response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                return response

        started = monotonic()
        try:
            response = await call_next(request)
        except Exception:
            duration = monotonic() - started
            metrics.record_http(method=request.method, route=_route_label(request), status_code=500, duration_seconds=duration)
            raise
        duration = monotonic() - started
        route = _route_label(request)
        metrics.record_http(method=request.method, route=route, status_code=response.status_code, duration_seconds=duration)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        logger.info(
            json.dumps(
                {
                    "event": "http_request_completed",
                    "request_id": request_id,
                    "method": request.method,
                    "route": route,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
                ensure_ascii=False,
            )
        )
        return response


def _route_label(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return str(path or request.url.path)
