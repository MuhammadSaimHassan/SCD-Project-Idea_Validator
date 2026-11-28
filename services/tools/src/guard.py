"""Domain allow-list, per-domain rate limiting, and robots.txt enforcement for M5."""

import time
from collections import defaultdict, deque
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx


class DomainNotAllowedError(PermissionError):
    """Raised when target URL domain is outside M5 allow-list."""


class RobotsDisallowedError(PermissionError):
    """Raised when robots.txt disallows fetching the target path."""


class DomainRateLimitError(RuntimeError):
    """Raised when per-domain rate limit is exceeded."""


class DomainRateLimiter:
    """Sliding-window per-domain rate limiter."""

    def __init__(self, max_per_minute: int = 30) -> None:
        self._max = max_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check_and_record(self, domain: str) -> None:
        now = time.monotonic()
        cutoff = now - 60.0
        bucket = self._hits[domain]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self._max:
            raise DomainRateLimitError(f"Rate limit exceeded for domain: {domain}")
        bucket.append(now)


class RobotsCache:
    """Caches parsed robots.txt rules per origin."""

    def __init__(self, user_agent: str) -> None:
        self._ua = user_agent
        self._parsers: dict[str, RobotFileParser] = {}

    def set_rules(self, origin: str, robots_txt: str) -> None:
        parser = RobotFileParser()
        parser.parse(robots_txt.splitlines())
        self._parsers[origin] = parser

    def is_allowed(self, url: str, client: httpx.Client | None = None) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._parsers.get(origin)
        if parser is None:
            parser = RobotFileParser()
            robots_url = f"{origin}/robots.txt"
            try:
                if client is not None:
                    resp = client.get(
                        robots_url,
                        headers={"User-Agent": self._ua},
                        timeout=5.0,
                    )
                    if resp.status_code == 200:
                        parser.parse(resp.text.splitlines())
                    else:
                        parser.parse(["User-agent: *", "Allow: /"])
                else:
                    parser.parse(["User-agent: *", "Allow: /"])
            except httpx.HTTPError:
                parser.parse(["User-agent: *", "Allow: /"])
            self._parsers[origin] = parser
        return bool(parser.can_fetch(self._ua, url))
