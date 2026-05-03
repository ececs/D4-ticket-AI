"""
Notification model.

Notifications are created automatically by the system when specific events occur:
  - A ticket is assigned to a user → notify the assignee
  - A comment is added to a ticket → notify the author and current assignee
  - A ticket's status changes → notify author and assignee

They are delivered in real-time via WebSockets (see ws.py) using PostgreSQL
LISTEN/NOTIFY. The `read` flag tracks which notifications the user has seen,
which drives the unread badge count in the frontend.
"""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class NotificationType(str, enum.Enum):
    """The event that triggered this notification."""
    assigned = "assigned"          # A ticket was assigned/reassigned to the user
    commented = "commented"        # A new comment was added to a ticket the user is involved in
    status_changed = "status_changed"  # A ticket's status changed
    ticket_updated = "ticket_updated"  # A ticket was modified (priority, title, etc)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # The user who should receive this notification
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, name="notification_type"), nullable=False
    )

    # CASCADE: when a ticket is deleted, its notifications are also deleted
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )

    # Human-readable message shown in the notifications panel
    message: Mapped[str] = mapped_column(String(500), nullable=False)

    # False = unread (counts toward the badge). True = user has seen it.
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
