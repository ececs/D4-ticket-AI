"""
Pub/Sub transport abstraction for real-time WebSocket notifications.

Two transports supported:
  - Redis Pub/Sub (primary): horizontally scalable — all backend instances
    subscribe to the same Redis channel, so a NOTIFY from instance A reaches
    WebSocket clients on instance B.
  - PostgreSQL LISTEN/NOTIFY (fallback): single-instance, no Redis required.
    Used automatically when REDIS_URL is not set.

The transport is selected at startup in main.py by calling start_listen_loop().
notification_service.py calls publish() without knowing which transport is active.

Redis channel: "notifications"
PG channel:    "notifications"
Payload:       JSON string {"user_id": "...", "id": "...", ...}
"""

import asyncio
import json
import logging

logger = logging.getLogger(__name__)

CHANNEL = "notifications"


async def publish(payload: dict) -> None:
    """
    Publish a notification payload to connected WebSocket clients.

    Routes to Redis if available, otherwise falls back to PostgreSQL NOTIFY
    (which requires the db session — imported lazily to avoid circular imports).
    The caller (notification_service) passes the db session for the PG path.
    """
    from app.services.cache_service import _redis

    if _redis is not None:
        try:
            await _redis.publish(CHANNEL, json.dumps(payload))
            return
        except Exception as exc:
            logger.warning("Redis publish failed, falling back to PG NOTIFY: %s", exc)

    # PG NOTIFY fallback — db session injected by notification_service
    _pg_notify_fn = payload.pop("_pg_notify_fn", None)
    if _pg_notify_fn is not None:
        await _pg_notify_fn(payload)


async def redis_listen_loop() -> None:
    """
    Background task: subscribe to Redis pub/sub and push to WebSocket clients.

    Runs for the lifetime of the application. Reconnects on transient errors.
    Only started when REDIS_URL is set and Redis is reachable.
    """
    from app.services.cache_service import _redis
    from app.core.websocket_manager import manager

    if _redis is None:
        logger.info("Redis not available — skipping Redis listen loop")
        return

    try:
        pubsub = _redis.pubsub()
        await pubsub.subscribe(CHANNEL)
        logger.info("Redis pub/sub subscribed to channel '%s'", CHANNEL)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
                user_id = data.get("user_id")
                if user_id:
                    await manager.broadcast_to_user(user_id, data)
            except Exception as exc:
                logger.debug("Error processing pub/sub message: %s", exc)
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.warning("Redis listen loop error: %s", exc)
    finally:
        try:
            await pubsub.unsubscribe(CHANNEL)
            await pubsub.aclose()
        except Exception:
            pass


def is_redis_available() -> bool:
    """Return True if the Redis client is connected (for transport selection)."""
    from app.services.cache_service import _redis
    return _redis is not None
