"""
Redis cache service — optional caching layer for read-heavy endpoints.

Graceful degradation: if REDIS_URL is not set or Redis is unreachable,
all cache operations are no-ops and callers fall through to the database.

Usage:
    value = await cache_get(key)
    if value is None:
        value = await expensive_query()
        await cache_set(key, value, ttl=60)

    await cache_invalidate_prefix("tickets:")  # on write
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_redis: Any = None


async def init_cache() -> None:
    """Connect to Redis at startup. No-op if REDIS_URL is not set."""
    global _redis
    from app.core.config import settings

    if not settings.REDIS_URL:
        logger.info("Redis cache disabled (REDIS_URL not set)")
        return

    try:
        import redis.asyncio as aioredis

        _redis = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
        )
        await _redis.ping()
        logger.info("Redis cache connected: %s", settings.REDIS_URL)
    except Exception as exc:
        logger.warning("Redis unavailable — cache disabled: %s", exc)
        _redis = None


async def close_cache() -> None:
    """Close the Redis connection at shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def cache_get(key: str) -> Optional[Any]:
    """Return cached value or None if missing / Redis unavailable."""
    if _redis is None:
        return None
    try:
        raw = await _redis.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        logger.debug("Cache GET error for %s: %s", key, exc)
        return None


async def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    """Store value with TTL (seconds). No-op if Redis unavailable."""
    if _redis is None:
        return
    try:
        await _redis.setex(key, ttl, json.dumps(value))
    except Exception as exc:
        logger.debug("Cache SET error for %s: %s", key, exc)


async def cache_invalidate_prefix(prefix: str) -> None:
    """Delete all keys matching `prefix*`. No-op if Redis unavailable."""
    if _redis is None:
        return
    try:
        keys = await _redis.keys(f"{prefix}*")
        if keys:
            await _redis.delete(*keys)
    except Exception as exc:
        logger.debug("Cache INVALIDATE error for prefix %s: %s", prefix, exc)
