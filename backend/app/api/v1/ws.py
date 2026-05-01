"""
WebSocket endpoint for real-time notifications.

Clients connect to /ws after authenticating. The connection stays open
for the duration of the browser session. When a relevant database event
occurs (ticket assigned, comment added, status changed), the WebSocket
manager pushes the notification payload to the client without polling.

Authentication: the JWT token is sent as a query parameter (?token=...)
because browsers don't support custom headers in native WebSocket connections.

Flow:
  1. Frontend connects: ws://localhost:8000/ws?token=<jwt>
  2. Server validates token, registers connection in WebSocketManager.
  3. Server sends pending unread notifications immediately on connect.
  4. Server listens for disconnect; cleans up on close.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.core.websocket_manager import manager
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationOut

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token for authentication"),
):
    """
    Establish a persistent WebSocket connection for the authenticated user.

    On connection:
      - Validates the JWT token.
      - Registers the connection in the WebSocketManager.
      - Sends all unread notifications so the badge count is accurate immediately.

    During connection:
      - Waits for disconnect (no messages expected from client in this version).

    On disconnect:
      - Removes the connection from the manager.
    """
    # Validate the token before accepting the connection
    user_id = decode_access_token(token)
    if not user_id:
        await websocket.close(code=4001)  # Custom code: unauthorized
        return

    # Verify user exists in the database
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            await websocket.close(code=4001)
            return

        # Accept connection and register it with the manager
        await manager.connect(websocket, user.id)

        # Send unread notifications so the badge count is correct immediately on connect
        unread = await db.execute(
            select(Notification)
            .where(Notification.user_id == user.id, Notification.read == False)
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
        notifications = unread.scalars().all()
        for notif in notifications:
            out = NotificationOut.model_validate(notif)
            await websocket.send_text(out.model_dump_json())

    try:
        # Keep the connection alive — wait for client to disconnect
        while True:
            await websocket.receive_text()  # We don't expect messages but this keeps the loop open
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
