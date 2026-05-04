"""
Notification service.

Centralizes all notification creation logic. When a ticket is assigned,
a comment is added, or a status changes, this service:
  1. Creates a Notification row in the database for each affected user.
  2. Sends a PostgreSQL NOTIFY so the background listener pushes the
     notification to any connected WebSocket clients in real time.

Why separate this into a service?
  - The same notification logic is needed from multiple routers
    (tickets, comments). A service avoids code duplication.
  - It makes the routers thin (HTTP concerns only) and the business
    logic testable in isolation.

PostgreSQL NOTIFY channel: "notifications"
  Payload: JSON string with user_id, notification data, and type.
  The asyncpg listener in main.py receives this and calls
  websocket_manager.broadcast_to_user().
"""

import json
import logging
from typing import List, Optional, Any, Dict
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func

from app.models.notification import Notification, NotificationType
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.notification import NotificationOut
from app.services import pubsub_service
from app.schemas.websocket import WSMessage, WSMessageType

logger = logging.getLogger(__name__)


async def _pg_notify(db: AsyncSession, user_id: str, payload: dict) -> None:
    """Send a raw PostgreSQL NOTIFY — used as fallback when Redis is unavailable."""
    payload["user_id"] = user_id
    payload_str = json.dumps(payload, default=str)
    await db.execute(
        text("SELECT pg_notify('notifications', :payload)"),
        {"payload": payload_str},
    )


async def _create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    notification_type: NotificationType,
    ticket_id: uuid.UUID,
    message: str,
) -> Notification:
    """
    Persist a Notification to the database and push it via WebSocket.

    Args:
        db: Database session (caller is responsible for commit).
        user_id: The user who should receive this notification.
        notification_type: The kind of event that triggered it.
        ticket_id: The related ticket (for click-through in the UI).
        message: Human-readable description shown in the notifications panel.

    Returns:
        The created Notification object (before commit).
    """
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        ticket_id=ticket_id,
        message=message,
    )
    db.add(notification)
    # Flush so the notification gets an id before we send NOTIFY
    await db.flush()

    # Get updated unread count for this user
    unread_count = await get_unread_count(db, user_id)

    # Publish to connected WebSocket clients (Redis Pub/Sub or PG NOTIFY fallback)
    # Prepare the payload for real-time delivery
    from app.schemas.websocket import WSMessage, WSMessageType
    
    ws_msg = WSMessage(
        type=WSMessageType.NOTIFICATION,
        ticket_id=ticket_id,
        data={
            "id": str(notification.id),
            "user_id": str(user_id),
            "type": notification_type.value,
            "ticket_id": str(ticket_id),
            "message": message,
            "read": notification.read,
            "created_at": notification.created_at.isoformat(),
            "unread_count": unread_count,
        }
    )
    
    event = ws_msg.model_dump(mode="json")
    # Add user_id for the listener to know where to broadcast
    event["user_id"] = str(user_id)
    
    logger.info(f"🔔 Notification created: type={notification_type.value}, user={user_id}, msg={message[:30]}...")
    
    if pubsub_service.is_redis_available():
        await pubsub_service.publish(event)
        logger.debug(f"Broadcasted notification to user {user_id} via Redis")
    else:
        await _pg_notify(db, str(user_id), event)
        logger.debug(f"Broadcasted notification to user {user_id} via PG Notify")

    return notification


async def notify_ticket_created(
    db: AsyncSession,
    ticket: Ticket,
    actor: User,
) -> None:
    """
    Notify the author and the assignee when a new ticket is created.
    """
    users_to_notify = {ticket.author_id}
    if ticket.assignee_id:
        users_to_notify.add(ticket.assignee_id)

    for user_id in users_to_notify:
        await _create_notification(
            db,
            user_id=user_id,
            notification_type=NotificationType.status_changed,
            ticket_id=ticket.id,
            message=f'New ticket created: "{ticket.title}" by {actor.name}',
        )


async def notify_ticket_deleted(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    ticket_title: str,
    actor: User,
) -> None:
    """
    Notify the actor that the ticket has been deleted.
    Provides a persistent notification record in the history.
    """
    await _create_notification(
        db,
        user_id=actor.id,
        notification_type=NotificationType.ticket_deleted,
        ticket_id=None,
        message=f'Ticket "{ticket_title}" eliminado por {actor.name}.',
    )


async def notify_ticket_assigned(
    db: AsyncSession,
    ticket: Ticket,
    assignee: User,
    actor: User,
) -> None:
    await _create_notification(
        db,
        user_id=assignee.id,
        notification_type=NotificationType.assigned,
        ticket_id=ticket.id,
        message=f'{actor.name} assigned ticket "{ticket.title}" to you',
    )


async def notify_comment_added(
    db: AsyncSession,
    ticket: Ticket,
    commenter: User,
) -> None:
    users_to_notify: set[uuid.UUID] = set()

    users_to_notify.add(ticket.author_id)

    if ticket.assignee_id:
        users_to_notify.add(ticket.assignee_id)

    for user_id in users_to_notify:
        await _create_notification(
            db,
            user_id=user_id,
            notification_type=NotificationType.commented,
            ticket_id=ticket.id,
            message=f'{commenter.name} commented on "{ticket.title}"',
        )


async def notify_status_changed(
    db: AsyncSession,
    ticket: Ticket,
    actor: User,
    new_status: str,
) -> None:
    """
    Notify the ticket author and assignee when the ticket status changes.

    Args:
        db: Database session.
        ticket: The ticket whose status changed.
        actor: The user who made the change.
        new_status: The new status value (for display in the message).
    """
    status_str = new_status.value if hasattr(new_status, "value") else new_status
    status_label = status_str.replace("_", " ").title()
    message = f'{actor.name} changed "{ticket.title}" to {status_label}'

    users_to_notify: set[uuid.UUID] = set()

    users_to_notify.add(ticket.author_id)

    if ticket.assignee_id:
        users_to_notify.add(ticket.assignee_id)

    for user_id in users_to_notify:
        await _create_notification(
            db,
            user_id=user_id,
            notification_type=NotificationType.status_changed,
            ticket_id=ticket.id,
            message=message,
        )


async def broadcast_global_event(
    type: WSMessageType,
    data: Optional[Dict[str, Any]] = None,
    db: Optional[AsyncSession] = None
) -> None:
    """
    Push a real-time event to ALL connected users via the WebSocket manager.
    Used for board-wide events (ticket created, deleted) so every user's UI stays in sync.
    """
    from app.schemas.websocket import WSMessage
    from app.core.websocket_manager import manager

    ws_msg = WSMessage(type=type, data=data)
    logger.info("Global broadcast: type=%s", type.value)
    await manager.broadcast_to_all(ws_msg)


async def broadcast_live_update(
    user_id: uuid.UUID,
    ticket_id: uuid.UUID,
    type: WSMessageType = WSMessageType.TICKET_UPDATED,
    message: Optional[str] = None,
    db: Optional[AsyncSession] = None
) -> None:
    """
    Push a real-time event to a user via Pub/Sub.
    Used for UI synchronization (e.g. "Someone is editing this ticket").
    """
    from app.schemas.websocket import WSMessage
    
    ws_msg = WSMessage(
        type=type,
        ticket_id=ticket_id,
        message=message
    )
    
    # We must use Pub/Sub here too, so that it works across multiple workers!
    event = ws_msg.model_dump(mode="json")
    event["user_id"] = str(user_id)
    
    logger.info(f"🔄 Live update broadcast: type={type.value}, user={user_id}, ticket={ticket_id}")
    
    from app.services import pubsub_service
    if pubsub_service.is_redis_available():
        await pubsub_service.publish(event)
    elif db is not None:
        await _pg_notify(db, str(user_id), event)
    else:
        logger.warning(f"Live update skipped for user {user_id}: No Redis and no DB session provided for PG Notify.")


async def notify_ticket_updated(
    db: AsyncSession,
    ticket: Ticket,
    actor: User,
) -> None:
    """
    Broadcast a global real-time update event.
    This ensures all connected users see the change in their UI (Kanban/List).
    """
    await broadcast_global_event(
        type=WSMessageType.TICKET_UPDATED,
        data={
            "id": str(ticket.id), 
            "title": ticket.title,
            "status": ticket.status.value,
            "priority": ticket.priority.value
        },
        db=db
    )


async def list_notifications(
    db: AsyncSession, 
    user_id: uuid.UUID, 
    limit: int = 50
) -> list[NotificationOut]:
    """
    Retrieves the most recent notifications for a specific user.
    """
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    notifications = result.scalars().all()
    return [NotificationOut.model_validate(n) for n in notifications]


async def mark_read(
    db: AsyncSession, 
    notification_id: uuid.UUID, 
    user_id: uuid.UUID
) -> bool:
    """
    Marks a single notification as read if it belongs to the user.
    """
    from sqlalchemy import update
    result = await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(read=True)
    )
    await db.commit()
    return result.rowcount > 0


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> int:
    """
    Marks all unread notifications for a user as read.
    """
    from sqlalchemy import update
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read == False)
        .values(read=True)
    )
    await db.commit()
    return result.rowcount


async def get_unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    """
    Returns the number of unread notifications for a user.
    """
    result = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == user_id, Notification.read == False)
    )
    return result.scalar() or 0


async def list_unread_notifications(
    db: AsyncSession, 
    user_id: uuid.UUID, 
    limit: int = 50
) -> list[NotificationOut]:
    """
    Retrieves only the unread notifications for a specific user.
    """
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id, Notification.read == False)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    notifications = result.scalars().all()
    return [NotificationOut.model_validate(n) for n in notifications]
