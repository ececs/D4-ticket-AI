"""
FastAPI application entry point.

This module creates and configures the FastAPI app. Key responsibilities:
  1. CORS: allow the Next.js frontend to call the API from a different origin.
  2. Lifespan: on startup, create the MinIO bucket if it doesn't exist, then start
     the PostgreSQL LISTEN loop that pushes notifications to WebSocket clients.
  3. Router registration: mount all v1 API routers under /api/v1.

The lifespan pattern (instead of deprecated @app.on_event) ensures cleanup code
(graceful shutdown) runs even when the server receives a SIGTERM.
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

import asyncpg
import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.websocket_manager import manager
from app.api.v1 import auth, tickets, comments, attachments, users, notifications, ws, knowledge
from app.ai import router as ai_router
from app.ai.checkpoint import init_checkpointer, close_pool
from app.services.cache_service import init_cache, close_cache
from app.services import pubsub_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup diagnostics
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("Checking environment variables...")
    if settings.GOOGLE_API_KEY:
        logger.info(f"✅ GOOGLE_API_KEY loaded (starts with {settings.GOOGLE_API_KEY[:4]}...)")
    else:
        logger.warning("❌ GOOGLE_API_KEY is MISSING!")
        
    if settings.OPENAI_API_KEY:
        logger.info(f"✅ OPENAI_API_KEY loaded (starts with {settings.OPENAI_API_KEY[:7]}...)")
    else:
        logger.warning("❌ OPENAI_API_KEY is MISSING!")
    
    # Initialize background notification listener (PostgreSQL)
    _init_langsmith()
    await _init_storage()
    await init_checkpointer()
    await init_cache()
    # Redis Pub/Sub when available; PG LISTEN/NOTIFY as fallback
    if pubsub_service.is_redis_available():
        logger.info("Real-time transport: Redis Pub/Sub")
        listen_task = asyncio.create_task(pubsub_service.redis_listen_loop())
    else:
        logger.info("Real-time transport: PostgreSQL LISTEN/NOTIFY")
        listen_task = asyncio.create_task(_pg_listen_loop())

    yield

    # --- Shutdown ---
    listen_task.cancel()
    try:
        await listen_task
    except asyncio.CancelledError:
        pass
    await close_pool()
    await close_cache()


def _init_langsmith() -> None:
    """
    Configure LangSmith tracing by propagating settings to the env vars that
    LangChain reads automatically. This way the .env file works in dev and
    Railway env vars work in production — both paths go through pydantic-settings.
    """
    if not settings.LANGSMITH_TRACING or not settings.LANGSMITH_API_KEY:
        logger.info("LangSmith tracing disabled")
        return

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    logger.info("LangSmith tracing enabled — project: %s", settings.LANGSMITH_PROJECT)


async def _init_storage() -> None:
    """
    Create the attachments bucket in MinIO/Cloudflare R2 if it doesn't exist.

    We use the synchronous boto3 client here because this only runs once at startup
    (not in a hot path). The bucket check is idempotent — safe to run on every restart.
    """
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.STORAGE_ENDPOINT,
        aws_access_key_id=settings.STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.STORAGE_SECRET_KEY,
        region_name=settings.STORAGE_REGION,
    )
    try:
        s3.head_bucket(Bucket=settings.STORAGE_BUCKET)
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "404":
            s3.create_bucket(Bucket=settings.STORAGE_BUCKET)
        # Other errors (auth, network) will propagate and crash startup — intentional


async def _pg_listen_loop() -> None:
    """
    Permanent background task that listens for PostgreSQL NOTIFY events.

    How it works:
      1. A direct asyncpg connection (not from SQLAlchemy pool) subscribes to
         the 'notifications' channel.
      2. When any DB operation triggers NOTIFY 'notifications', '<json_payload>',
         this callback fires and pushes the payload to the target user's WebSocket(s).
      3. The loop runs until the application shuts down (CancelledError).

    Why asyncpg directly instead of SQLAlchemy?
      SQLAlchemy's async session is designed for request-response queries.
      asyncpg's LISTEN requires a persistent long-lived connection with a callback,
      which maps perfectly to a background task.
    """
    # Build a raw asyncpg connection URL (asyncpg uses its own URL format)
    raw_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    conn: asyncpg.Connection = await asyncpg.connect(raw_url)

    async def on_notification(connection, pid, channel, payload):
        """Callback invoked by asyncpg when a NOTIFY arrives."""
        try:
            data = json.loads(payload)
            user_id = data.get("user_id")
            if user_id:
                await manager.broadcast_to_user(user_id, data)
        except Exception as e:
            logger.error(f"WebSocket Listener: Failed to process notification: {str(e)}")

    await conn.add_listener("notifications", on_notification)

    try:
        # Wait forever (until CancelledError on shutdown)
        await asyncio.Future()
    finally:
        await conn.remove_listener("notifications", on_notification)
        await conn.close()


# --- Application factory ---

app = FastAPI(
    title="D4-Ticket AI",
    description="Collaborative ticketing system with AI assistant powered by LangGraph.",
    version="1.0.0",
    docs_url="/docs",      # Swagger UI
    redoc_url="/redoc",    # ReDoc
    lifespan=lifespan,
)

# CORS: allow the frontend origin to make cross-origin requests.
# We combine the configured CORS_ORIGINS with FRONTEND_URL to ensure consistency.
allowed_origins = list(set(settings.CORS_ORIGINS + [settings.FRONTEND_URL]))
print(f"🔓 Allowed Origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,  # Required for cookie-based auth
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all API routers under /api/v1
# Each router file is responsible for its own prefix and tags
app.include_router(auth.router, prefix="/api/v1")
app.include_router(tickets.router, prefix="/api/v1")
app.include_router(comments.router, prefix="/api/v1")
app.include_router(attachments.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(ws.router)  # WebSocket doesn't follow the /api/v1 pattern
app.include_router(ai_router.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health endpoint for Docker/Railway health checks."""
    return {"status": "ok", "version": "0.1.1"}
