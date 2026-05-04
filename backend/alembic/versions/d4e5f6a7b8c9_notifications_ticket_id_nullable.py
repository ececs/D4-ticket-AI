"""notifications: ticket_id nullable + SET NULL + ticket_deleted type

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-04

Why:
  Notifications for deleted tickets must survive after the ticket row is gone.
  Previously ticket_id was NOT NULL / CASCADE, which made it impossible to
  create a "ticket_deleted" notification (the FK insert would fail because the
  ticket is deleted before the notification is written, or the notification
  itself would cascade-delete along with the ticket).

  Changes:
  - notifications.ticket_id: NOT NULL → nullable, ON DELETE CASCADE → SET NULL
  - notification_type enum: add 'ticket_deleted' value (PostgreSQL only; SQLite
    stores enums as VARCHAR so no DDL needed there)
"""

from typing import Union
import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 1. Add 'ticket_deleted' to the PostgreSQL enum type (no-op on SQLite)
    if dialect == "postgresql":
        op.execute(
            "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'ticket_deleted'"
        )

    # 2. Drop the old FK constraint and alter the column to nullable + SET NULL
    #    Use batch mode for SQLite compatibility (tests run on SQLite).
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.alter_column(
            "ticket_id",
            existing_type=sa.UUID(),
            nullable=True,
        )
        batch_op.drop_constraint("notifications_ticket_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "notifications_ticket_id_fkey",
            "tickets",
            ["ticket_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    # Restore NOT NULL / CASCADE — will fail if any ticket_id is already NULL
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.drop_constraint("notifications_ticket_id_fkey", type_="foreignkey")
        batch_op.create_foreign_key(
            "notifications_ticket_id_fkey",
            "tickets",
            ["ticket_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.alter_column(
            "ticket_id",
            existing_type=sa.UUID(),
            nullable=False,
        )
