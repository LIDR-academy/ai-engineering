"""Session 10 full text search support for hybrid retrieval.

Adds a generated stored tsvector column to chunks plus a GIN index. This creates
the lexical branch used later by hybrid vector plus full text retrieval.

Text search configuration: english.

Reason: the current repository sample budget corpus is written in English, and
the teacher Session 10 reference corpus is also English. The later lexical query
must use the same configuration through plainto_tsquery('english', query).
"""

from __future__ import annotations

from alembic import op

revision = "0003_session10_full_text_search"
down_revision = "0002_session08_hnsw_vector_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE chunks "
        "ADD COLUMN content_tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', content)) STORED"
    )
    op.execute(
        "CREATE INDEX ix_chunks_content_tsv "
        "ON chunks "
        "USING gin (content_tsv)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_content_tsv")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS content_tsv")
