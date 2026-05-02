"""add_knowledge_chunks

Revision ID: a1b2c3d4e5f6
Revises: 9bc21880aaa1
Create Date: 2026-05-02 12:00:00.000000+00:00

Adds a knowledge base table for RAG (Retrieval-Augmented Generation):
  - knowledge_chunks: stores scraped web page text split into paragraphs,
    each with a 768-dim embedding for semantic retrieval by the AI agent.
  - HNSW index for fast approximate nearest-neighbour cosine search.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9bc21880aaa1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 768


def upgrade() -> None:
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_chunks_url", "knowledge_chunks", ["url"])

    op.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS knowledge_chunks_embedding_hnsw")
    op.drop_index("ix_knowledge_chunks_url", "knowledge_chunks")
    op.drop_table("knowledge_chunks")
