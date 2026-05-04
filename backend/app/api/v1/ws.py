"""
WebSocket endpoint for real-time notifications.
"""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select

from app.core.security import decode_access_token
from app.core.websocket_manager import manager
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.services import notification_service

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """
    Establish a persistent WebSocket connection.
    """
    user_id = decode_access_token(token)
    if not user_id:
        await websocket.close(code=4001)
        return

    async with AsyncSessionLocal() as db:
        # Verify user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            await websocket.close(code=4001)
            return

        await manager.connect(websocket, user.id)

        from app.schemas.websocket import WSMessage, WSMessageType
        
        # Send initial state (unread count)
        unread_count = await notification_service.get_unread_count(db, user.id)
        msg = WSMessage(
            type=WSMessageType.SYSTEM_ALERT,
            data={"unread_count": unread_count},
            message="Estado inicial cargado"
        )
        await websocket.send_text(msg.model_dump_json())

        # Send unread notifications list
        notifications = await notification_service.list_unread_notifications(db, user.id)
        for notif in notifications:
            # We must send it in the same format as the real-time events
            notif_msg = WSMessage(
                type=WSMessageType.NOTIFICATION,
                ticket_id=notif.ticket_id,
                data=notif.model_dump(mode="json")
            )
            await websocket.send_text(notif_msg.model_dump_json())

    try:
        while True:
            try:
                # Keep-alive loop
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
