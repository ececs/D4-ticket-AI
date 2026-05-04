"""
LangGraph PostgreSQL checkpointer — persistent conversation memory.

Why a module-level singleton?
  AsyncPostgresSaver maintains a psycopg connection pool. Creating it per
  request would exhaust PostgreSQL connections under load. A singleton
  initialized once at startup is the correct pattern for connection pools.

  setup() (creates checkpoint_* tables) is called once at init, not per request.

Graceful degradation:
  If PostgreSQL is unreachable at startup (e.g., test environment), the
  checkpointer is set to None and the agent falls back to stateless mode —
  the frontend sends the full conversation history on every request.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_checkpointer = None
_pool = None


async def init_checkpointer() -> None:
    """
    Initialize AsyncPostgresSaver and create checkpoint tables if needed.
    Called once at application startup from the lifespan context.
    Fails gracefully — the agent works without it (stateless fallback).
    """
    global _checkpointer, _pool

    try:
        from psycopg_pool import AsyncConnectionPool
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from app.core.config import settings
        
        # Use a more visible logger for startup
        v_logger = logging.getLogger("uvicorn.error")

        # Ensure we have a standard postgresql:// URL for psycopg (no +asyncpg)
        db_url = settings.DATABASE_URL
        if "+asyncpg" in db_url:
            db_url = db_url.replace("+asyncpg", "")
        
        v_logger.info("Initializing checkpointer with URL: %s", db_url.split("@")[-1])

        _pool = AsyncConnectionPool(
            conninfo=db_url,
            min_size=1,
            max_size=3,
            open=False,
            kwargs={"autocommit": True, "prepare_threshold": 0},
        )
        await _pool.open(wait=True, timeout=10.0)

        # Initialize the checkpointer with the pool
        _checkpointer = AsyncPostgresSaver(_pool)
        
        # CRITICAL: Ensure tables exist
        await _checkpointer.setup()
        
        v_logger.info("✅ LangGraph Checkpointer fully initialized and persistent")
        return _checkpointer

    except Exception as exc:
        logging.getLogger("uvicorn.error").error("❌ Checkpointer FAILED to initialize: %s", exc, exc_info=True)
        _checkpointer = None
        _pool = None


def get_checkpointer():
    """Return the active checkpointer, or None if unavailable."""
    return _checkpointer


async def close_pool() -> None:
    """Close the psycopg connection pool on application shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("LangGraph checkpointer pool closed")
