"""add_client_context_and_metadata
 
Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-03 01:00:00.000000+00:00
 
Adds client context fields to tickets and metadata to knowledge chunks.
"""
 
from typing import Sequence, Union
 
from alembic import op
import sqlalchemy as sa
 
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
 
 
def upgrade() -> None:
    # Add client context to tickets
    op.add_column("tickets", sa.Column("client_url", sa.String(512), nullable=True))
    op.add_column("tickets", sa.Column("client_summary", sa.Text(), nullable=True))
    
    # Add chunk_metadata to knowledge_chunks
    op.add_column("knowledge_chunks", sa.Column("chunk_metadata", sa.JSON(), nullable=True))
 
 
def downgrade() -> None:
    op.drop_column("knowledge_chunks", "chunk_metadata")
    op.drop_column("tickets", "client_summary")
    op.drop_column("tickets", "client_url")
