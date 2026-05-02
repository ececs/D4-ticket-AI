"""add_pgvector_and_ticket_embeddings

Revision ID: 9bc21880aaa1
Revises: 0001
Create Date: 2026-05-02 04:39:09.336810+00:00

Adds semantic search capability to tickets:
  1. Enables the pgvector PostgreSQL extension.
  2. Adds an `embedding` column (vector(768)) to tickets.
  3. Creates an HNSW index for fast approximate nearest-neighbour search.

Why HNSW over IVFFlat?
  HNSW (Hierarchical Navigable Small World) gives better recall at query time
  and does not require a training phase (IVFFlat needs a populated table to
  build the inverted-file index). For a growing dataset starting from zero,
  HNSW is the correct default.

Embedding model: Google text-embedding-004 (768 dimensions).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = '9bc21880aaa1'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 768


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        "tickets",
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
    )

    # HNSW index for cosine similarity — m=16 and ef_construction=64 are
    # good defaults for datasets up to ~1M rows.
    op.execute(
        "CREATE INDEX IF NOT EXISTS tickets_embedding_hnsw "
        "ON tickets USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS tickets_embedding_hnsw")
    op.drop_column("tickets", "embedding")
