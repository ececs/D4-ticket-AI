"""
Comment model.

Comments are threaded discussion attached to a ticket.
They are displayed chronologically in the ticket detail view.

Each comment has an author relationship for eager loading in the API response,
so the frontend can display the commenter's name and avatar without extra requests.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # CASCADE: deleting the ticket removes all its comments
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Eager-loadable relationship for response serialization
    author: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User",
        foreign_keys=[author_id],
        lazy="noload",
    )
