"""
User model.

Users are created automatically on first Google OAuth login — there is no
manual registration flow. The data (email, name, avatar) comes directly
from the Google profile returned by the OAuth callback.

The email field has a unique constraint because it is used as the stable
identity across Google re-logins (a user's Google account email doesn't change).
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Email is unique — used to match returning OAuth users to their existing account
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Google profile picture URL — can be None if the user has no avatar
    avatar_url: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    @property
    def display_name(self) -> str:
        """Returns name if available, otherwise email."""
        return self.name or self.email or "Unknown User"
