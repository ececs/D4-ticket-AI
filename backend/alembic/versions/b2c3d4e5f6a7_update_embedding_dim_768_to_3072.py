"""update_embedding_dim_768_to_3072

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-02 16:00:00.000000+00:00

Switches embedding model from text-embedding-004 (768 dims, unavailable with
current API key) to gemini-embedding-001 (3072 dims).

Changes:
  - tickets.embedding: vector(768) → vector(3072)
  - knowledge_chunks.embedding: vector(768) → vector(3072)
  - Drops and recreates HNSW indices for both tables.

Existing embeddings (if any) are NULLed out since they were generated with
a different model and are not comparable with new 3072-dim vectors.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_DIM = 768
NEW_DIM = 3072


def upgrade() -> None:
    # --- tickets ---
    op.execute("DROP INDEX IF EXISTS tickets_embedding_hnsw")
    op.execute("ALTER TABLE tickets ALTER COLUMN embedding TYPE vector(3072) USING NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS tickets_embedding_hnsw "
        "ON tickets USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # --- knowledge_chunks ---
    op.execute("DROP INDEX IF EXISTS knowledge_chunks_embedding_hnsw")
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(3072) USING NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS tickets_embedding_hnsw")
    op.execute("ALTER TABLE tickets ALTER COLUMN embedding TYPE vector(768) USING NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS tickets_embedding_hnsw "
        "ON tickets USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    op.execute("DROP INDEX IF EXISTS knowledge_chunks_embedding_hnsw")
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(768) USING NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
