"""update_embedding_dim_768_to_1536

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-02 16:00:00.000000+00:00

Switches embedding model from text-embedding-004 (768 dims, unavailable with
current API key) to gemini-embedding-001 (1536 dims).

Drop-and-recreate strategy is used instead of ALTER COLUMN TYPE because
pgvector does not support casting between vector sizes. All existing embeddings
are discarded (they were 768-dim and incompatible with the new model anyway).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- tickets ---
    op.execute("DROP INDEX IF EXISTS tickets_embedding_hnsw")
    op.drop_column("tickets", "embedding")
    op.add_column("tickets", sa.Column("embedding", Vector(1536), nullable=True))
    op.execute(
        "CREATE INDEX IF NOT EXISTS tickets_embedding_hnsw "
        "ON tickets USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # --- knowledge_chunks ---
    op.execute("DROP INDEX IF EXISTS knowledge_chunks_embedding_hnsw")
    op.drop_column("knowledge_chunks", "embedding")
    op.add_column("knowledge_chunks", sa.Column("embedding", Vector(1536), nullable=True))
    op.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS tickets_embedding_hnsw")
    op.drop_column("tickets", "embedding")
    op.add_column("tickets", sa.Column("embedding", Vector(768), nullable=True))
    op.execute(
        "CREATE INDEX IF NOT EXISTS tickets_embedding_hnsw "
        "ON tickets USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    op.execute("DROP INDEX IF EXISTS knowledge_chunks_embedding_hnsw")
    op.drop_column("knowledge_chunks", "embedding")
    op.add_column("knowledge_chunks", sa.Column("embedding", Vector(768), nullable=True))
    op.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
