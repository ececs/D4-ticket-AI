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
from contextlib import asynccontextmanager

import asyncpg
import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.websocket_manager import manager
from app.api.v1 import auth, tickets, comments, attachments, users, notifications, ws
from app.ai import router as ai_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage startup and shutdown tasks.

    Startup:
      - Ensure the MinIO/R2 attachments bucket exists.
      - Start the asyncpg LISTEN loop in the background.

    Shutdown:
      - Cancel the LISTEN task cleanly (avoids asyncpg connection leaks).
    """
    # --- Startup: initialize MinIO bucket ---
    await _init_storage()

    # --- Startup: launch PostgreSQL LISTEN task ---
    listen_task = asyncio.create_task(_pg_listen_loop())

    yield  # Application is running — handle requests

    # --- Shutdown: stop the LISTEN task ---
    listen_task.cancel()
    try:
        await listen_task
    except asyncio.CancelledError:
        pass


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
        except Exception:
            pass  # Never crash the listener loop on a bad payload

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
# In production, replace origins with the actual Vercel URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
    ],
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


@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health endpoint for Docker/Railway health checks."""
    return {"status": "ok", "version": "0.1.1"}
