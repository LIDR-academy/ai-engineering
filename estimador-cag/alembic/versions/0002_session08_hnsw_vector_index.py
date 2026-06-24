"""Add HNSW cosine vector index for Session 08 extra-mile search.

Revision ID: 0002_session08_hnsw_vector_index
Revises: 0001_session08_pgvector
Create Date: 2026-06-07

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_session08_hnsw_vector_index"
down_revision: str | None = "0001_session08_pgvector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add measured HNSW cosine index for chunk embeddings."""
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw_cosine
        ON chunks
        USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    """Drop the Session 08 extra-mile HNSW index."""
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw_cosine")
