"""Controlled HTTP fetcher for M5 Tool Layer."""

import time
from datetime import UTC, datetime
from urllib.parse import urlencode, urlparse

import httpx

from shared.schemas import FetchRequest, FetchResponse

from .config import ToolsSettings
from .guard import (
    DomainNotAllowedError,
    DomainRateLimiter,
    RobotsCache,
    RobotsDisallowedError,
)
from .sanitiser import sanitise_text


class ToolFetcher:
    """Single controlled internet egress implementing allow-list, robots, rate limit, cache."""

    def __init__(
        self,
        settings: ToolsSettings,
        *,
        http_client: httpx.Client | None = None,
        robots_cache: RobotsCache | None = None,
    ) -> None:
        self._settings = settings
        self._allowed = {d.lower() for d in settings.allowed_domains}
        self._limiter = DomainRateLimiter(max_per_minute=settings.per_domain_rpm)
        self._robots = robots_cache or RobotsCache(settings.user_agent)
        self._client = http_client or httpx.Client(timeout=settings.request_timeout_seconds)
        self._cache: dict[str, tuple[float, FetchResponse]] = {}
        self.fetch_count = 0
        self.cache_hits = 0
        self.blocked_domains = 0
        self.blocked_robots = 0
        self.sanitized_total = 0

    def _canonical_url(self, req: FetchRequest) -> str:
        if not req.params:
            return req.url
        sep = "&" if "?" in req.url else "?"
        return f"{req.url}{sep}{urlencode(req.params)}"

    def fetch(self, req: FetchRequest) -> FetchResponse:
        parsed = urlparse(req.url)
        domain = parsed.netloc.lower()
        if parsed.scheme not in ("http", "https") or domain not in self._allowed:
            self.blocked_domains += 1
            raise DomainNotAllowedError(f"Domain '{domain}' is not on M5 allow-list")

        full_url = self._canonical_url(req)
        cached = self._cache.get(full_url)
        if cached is not None:
            expires_at, response = cached
            if time.monotonic() < expires_at:
                self.cache_hits += 1
                return response.model_copy(update={"cache_hit": True})
            del self._cache[full_url]

        if self._settings.respect_robots_txt and not self._robots.is_allowed(
            full_url, self._client
        ):
            self.blocked_robots += 1
            raise RobotsDisallowedError(f"Blocked by robots.txt: {full_url}")

        self._limiter.check_and_record(domain)

        headers = {"User-Agent": self._settings.user_agent}
        if domain == "api.github.com" and self._settings.github_token:
            headers["Authorization"] = f"Bearer {self._settings.github_token}"

        last_exc: Exception | None = None
        resp: httpx.Response | None = None
        for attempt in range(self._settings.max_retries + 1):
            try:
                resp = self._client.get(full_url, headers=headers)
                if (
                    resp.status_code in (429, 500, 502, 503, 504)
                    and attempt < self._settings.max_retries
                ):
                    time.sleep(0.2 * (2**attempt))
                    continue
                break
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < self._settings.max_retries:
                    time.sleep(0.2 * (2**attempt))
                    continue
                raise

        if resp is None:
            raise RuntimeError(f"Failed to fetch {full_url}: {last_exc}")

        cleaned, injected_count = sanitise_text(resp.text)
        self.fetch_count += 1
        self.sanitized_total += injected_count

        result = FetchResponse(
            url=full_url,
            source=req.source,
            status_code=resp.status_code,
            content=cleaned,
            cache_hit=False,
            sanitized_injections=injected_count,
            fetched_at=datetime.now(UTC).isoformat(),
        )
        if 200 <= resp.status_code < 300:
            self._cache[full_url] = (
                time.monotonic() + self._settings.cache_ttl_seconds,
                result,
            )
        return result
