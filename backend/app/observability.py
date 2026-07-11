from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


class SlidingWindowRateLimiter:
    """Small, dependency-free limiter for one API process.

    Deployments that run multiple replicas should enforce the same policy at the
    reverse proxy or replace this adapter with a shared Redis implementation.
    """

    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> RateLimitDecision:
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - bucket[0])) + 1)
                return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)
            bucket.append(now)
        return RateLimitDecision(allowed=True)


class PrometheusMetrics:
    """Minimal Prometheus exposition without adding an operational dependency."""

    def __init__(self) -> None:
        self._requests: dict[tuple[str, str, int], int] = defaultdict(int)
        self._durations: dict[tuple[str, str], tuple[float, int]] = {}
        self._lock = Lock()

    def record_http(self, *, method: str, route: str, status_code: int, duration_seconds: float) -> None:
        key = (method, route, status_code)
        duration_key = (method, route)
        with self._lock:
            self._requests[key] += 1
            total, count = self._durations.get(duration_key, (0.0, 0))
            self._durations[duration_key] = (total + duration_seconds, count + 1)

    def render(self) -> str:
        def labels(**items: object) -> str:
            rendered = ",".join(f'{name}="{str(value).replace(chr(34), chr(92) + chr(34))}"' for name, value in items.items())
            return "{" + rendered + "}"

        with self._lock:
            request_rows = list(self._requests.items())
            duration_rows = list(self._durations.items())
        lines = [
            "# HELP agent_http_requests_total Number of completed API requests.",
            "# TYPE agent_http_requests_total counter",
        ]
        for (method, route, status_code), count in sorted(request_rows):
            lines.append(f"agent_http_requests_total{labels(method=method, route=route, status=status_code)} {count}")
        lines.extend([
            "# HELP agent_http_request_duration_seconds API request duration in seconds.",
            "# TYPE agent_http_request_duration_seconds summary",
        ])
        for (method, route), (total, count) in sorted(duration_rows):
            label_set = labels(method=method, route=route)
            lines.append(f"agent_http_request_duration_seconds_sum{label_set} {total:.6f}")
            lines.append(f"agent_http_request_duration_seconds_count{label_set} {count}")
        return "\n".join(lines) + "\n"


metrics = PrometheusMetrics()
