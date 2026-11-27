"""Sliding-window in-memory rate limiter for M1 API Gateway."""

import time
from collections import defaultdict, deque


class RateLimiter:
    """Simple per-client sliding-window rate limiter."""

    def __init__(self, max_requests: int = 120, window_seconds: int = 60) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self.blocked_total = 0

    def allow(self, client_key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window
        bucket = self._buckets[client_key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self._max:
            self.blocked_total += 1
            return False
        bucket.append(now)
        return True
