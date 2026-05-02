"""
Notification routes.
"""

import uuid
from typing import List
from fastapi import APIRouter, HTTPException
from app.core.dependencies import CurrentUser, DB
from app.schemas.notification import NotificationOut
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationOut], summary="List my notifications")
async def list_notifications(current_user: CurrentUser, db: DB, limit: int = 50):
    """Return the most recent notifications for the current user."""
    return await notification_service.list_notifications(
        db, user_id=current_user.id, limit=limit
    )


@router.patch("/{notification_id}/read", summary="Mark a notification as read")
async def mark_read(notification_id: uuid.UUID, current_user: CurrentUser, db: DB):
    """Mark a single notification as read."""
    success = await notification_service.mark_read(
        db, notification_id=notification_id, user_id=current_user.id
    )
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}


@router.patch("/read-all", summary="Mark all notifications as read")
async def mark_all_read(current_user: CurrentUser, db: DB):
    """Mark all unread notifications for the current user as read at once."""
    count = await notification_service.mark_all_read(db, user_id=current_user.id)
    return {"ok": True, "count": count}
