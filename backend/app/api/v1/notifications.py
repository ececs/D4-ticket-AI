"""
Notification routes.

Provides endpoints for the authenticated user to:
  - List their notifications (most recent first, with unread count).
  - Mark one or all notifications as read.

Notifications are created automatically by the notification_service when
relevant events occur (ticket assigned, comment added, status changed).
They are delivered in real-time via WebSocket (see ws.py) and persisted
in the DB for users who are offline.
"""

from fastapi import APIRouter
from sqlalchemy import select, update
import uuid

from app.core.dependencies import CurrentUser, DB
from app.models.notification import Notification
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationOut], summary="List my notifications")
async def list_notifications(current_user: CurrentUser, db: DB, limit: int = 50):
    """Return the most recent notifications for the current user (read and unread)."""
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.patch("/{notification_id}/read", summary="Mark a notification as read")
async def mark_read(notification_id: uuid.UUID, current_user: CurrentUser, db: DB):
    """Mark a single notification as read. Only the owner can mark their own notifications."""
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == current_user.id)
        .values(read=True)
    )
    await db.commit()
    return {"ok": True}


@router.patch("/read-all", summary="Mark all notifications as read")
async def mark_all_read(current_user: CurrentUser, db: DB):
    """Mark all unread notifications for the current user as read at once."""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.read == False)
        .values(read=True)
    )
    await db.commit()
    return {"ok": True}
