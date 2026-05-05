"""add deletion_requested notification type

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-05 00:00:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'deletion_requested'"
    )


def downgrade() -> None:
    # PostgreSQL enum value removal is intentionally omitted here to keep the
    # migration simple and safe for production data.
    pass
