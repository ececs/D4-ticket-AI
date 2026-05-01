"""
WebSocket connection manager.

This module manages the lifecycle of all active WebSocket connections.
It is the bridge between server-side events (PostgreSQL NOTIFY messages)
and connected browser clients.

Architecture:
  - Each authenticated user can have multiple browser tabs/windows open,
    each with its own WebSocket connection.
  - Connections are stored in a dict keyed by user_id (UUID).
  - The value is a list of WebSocket objects (one per open tab).

When a notification must be delivered to user X:
  1. PostgreSQL triggers a NOTIFY with the user's UUID as the channel.
  2. The asyncpg listener (in main.py lifespan) calls manager.broadcast_to_user().
  3. The manager sends the JSON payload to all active connections for that user.
  4. If a connection is broken (client disconnected), it is removed gracefully.
"""

import json
import uuid
from fastapi import WebSocket


class WebSocketManager:
    """Thread-safe (within async event loop) manager for WebSocket connections."""

    def __init__(self) -> None:
        # Dict mapping user UUID -> list of active WebSocket connections for that user
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: uuid.UUID) -> None:
        """
        Accept a new WebSocket connection and register it for the given user.

        Args:
            websocket: The FastAPI WebSocket object.
            user_id: The authenticated user's UUID (used as the channel key).
        """
        await websocket.accept()
        key = str(user_id)
        if key not in self.connections:
            self.connections[key] = []
        self.connections[key].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: uuid.UUID) -> None:
        """
        Remove a WebSocket connection when the client disconnects.

        Args:
            websocket: The WebSocket to remove.
            user_id: The user whose connection list to update.
        """
        key = str(user_id)
        if key in self.connections:
            self.connections[key] = [
                ws for ws in self.connections[key] if ws is not websocket
            ]
            # Clean up empty lists to avoid memory leaks
            if not self.connections[key]:
                del self.connections[key]

    async def broadcast_to_user(self, user_id: str, data: dict) -> None:
        """
        Send a JSON payload to all active connections for a specific user.

        Broken connections (client closed browser) are cleaned up automatically.

        Args:
            user_id: UUID string of the target user.
            data: Dict to serialize as JSON and send.
        """
        if user_id not in self.connections:
            return  # User has no active connections — notification saved to DB, will load on next login

        message = json.dumps(data)
        dead_connections: list[WebSocket] = []

        for websocket in self.connections[user_id]:
            try:
                await websocket.send_text(message)
            except Exception:
                # Connection is broken (client disconnected without clean close)
                dead_connections.append(websocket)

        # Remove broken connections
        for ws in dead_connections:
            self.connections[user_id] = [c for c in self.connections[user_id] if c is not ws]


# Singleton instance — imported in main.py and ws.py
manager = WebSocketManager()
