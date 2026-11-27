"""Versioned Redis cache with in-memory TTL fallback and hit/miss visibility."""

import hashlib
import json
import logging
import time
from typing import Any

import redis

logger = logging.getLogger("gateway.cache")


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()[:16]


def verdict_cache_key(
    idea_text: str,
    profile_version: int,
    rubric_version: str,
    weights_version: str,
) -> str:
    """Build verdict cache key including profile, rubric, and weight versions."""
    return (
        f"verdict:{_short_hash(idea_text)}:p{profile_version}"
        f":r{rubric_version}:w{weights_version}"
    )


def retrieval_cache_key(query: str, rubric_version: str) -> str:
    """Build retrieval cache key including rubric version."""
    return f"retrieval:{_short_hash(query)}:r{rubric_version}"


class VersionedCache:
    """Cache wrapper supporting Redis or an in-memory TTL store with visible metrics."""

    def __init__(self, redis_url: str = "", default_ttl_seconds: int = 3600) -> None:
        self._ttl = default_ttl_seconds
        self._memory: dict[str, tuple[float, str]] = {}
        self._client: redis.Redis | None = None
        if redis_url:
            self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        self.hits = 0
        self.misses = 0

    def is_redis_enabled(self) -> bool:
        return self._client is not None

    def ping(self) -> bool:
        if self._client is None:
            return True
        return bool(self._client.ping())

    def get_json(self, key: str) -> tuple[dict[str, Any] | None, bool]:
        """Retrieve cached JSON payload and record visible hit/miss state."""
        raw: str | None = None
        if self._client is not None:
            val = self._client.get(key)
            raw = val if isinstance(val, str) else None
        else:
            entry = self._memory.get(key)
            if entry is not None:
                expires_at, payload = entry
                if time.monotonic() < expires_at:
                    raw = payload
                else:
                    del self._memory[key]

        if raw is None:
            self.misses += 1
            logger.info("cache_miss key=%s", key)
            return None, False

        self.hits += 1
        logger.info("cache_hit key=%s", key)
        parsed = json.loads(raw)
        return (parsed if isinstance(parsed, dict) else None), True

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int | None = None) -> None:
        """Store JSON payload with TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl
        serialized = json.dumps(value)
        if self._client is not None:
            self._client.setex(key, ttl, serialized)
        else:
            self._memory[key] = (time.monotonic() + ttl, serialized)
