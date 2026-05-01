"""
Ticket model — the core entity of the system.

A ticket represents an incident, task, or issue. It tracks:
  - Who created it (author) and who is responsible for it (assignee)
  - Its current state in the workflow (status)
  - How urgent it is (priority)
  - Timestamps for creation and last modification

The status and priority fields use Python enums that are stored as PostgreSQL
ENUM types for data integrity (the DB rejects invalid values at the driver level).
"""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class TicketStatus(str, enum.Enum):
    """Workflow states a ticket can be in. Order reflects typical progression."""
    open = "open"
    in_progress = "in_progress"
    in_review = "in_review"
    closed = "closed"


class TicketPriority(str, enum.Enum):
    """Urgency levels, from lowest to highest."""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Ticket(Base):
    """
    Represents a work item in the ticketing system.

    Columns:
      id          - UUID primary key (generated server-side for security)
      title       - Short summary displayed in list and kanban views
      description - Full details, supports multi-line text
      status      - Current workflow state (drives kanban column placement)
      priority    - Urgency level (drives sorting and visual indicators)
      author_id   - User who created the ticket (immutable after creation)
      assignee_id - User currently responsible (nullable — unassigned tickets are valid)
      created_at  - Immutable creation timestamp
      updated_at  - Auto-updated on every PATCH via SQLAlchemy onupdate
    """

    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    status: Mapped[TicketStatus] = mapped_column(
        SAEnum(TicketStatus, name="ticket_status"),
        default=TicketStatus.open,
        nullable=False,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        SAEnum(TicketPriority, name="ticket_priority"),
        default=TicketPriority.medium,
        nullable=False,
    )

    # ForeignKeys reference users.id. author_id is immutable; assignee_id can be changed.
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        # onupdate fires automatically whenever SQLAlchemy executes an UPDATE on this row
        onupdate=lambda: datetime.now(timezone.utc),
    )
