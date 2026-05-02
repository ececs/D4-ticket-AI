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
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.notification import Notification, NotificationType
from app.models.ticket import Ticket
from app.models.user import User


async def _pg_notify(db: AsyncSession, user_id: str, payload: dict) -> None:
    """
    Send a PostgreSQL NOTIFY on the 'notifications' channel.

    asyncpg's LISTEN in main.py receives this and immediately broadcasts
    the payload to the user's open WebSocket connections.

    Args:
        db: The current database session (used to run the NOTIFY statement).
        user_id: Target user UUID string (included in payload for routing).
        payload: Dict that will be JSON-serialized and sent as the NOTIFY payload.
    """
    payload["user_id"] = user_id
    payload_str = json.dumps(payload)
    # Use text() to safely pass the payload as a parameter — no SQL injection risk
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

    # Notify connected WebSocket clients immediately
    await _pg_notify(db, str(user_id), {
        "id": str(notification.id),
        "type": notification_type.value,
        "ticket_id": str(ticket_id),
        "message": message,
        "read": False,
        "created_at": notification.created_at.isoformat(),
    })

    return notification


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
    status_label = new_status.replace("_", " ").title()
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
