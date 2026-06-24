import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = REPO_ROOT / "estimador-cag"
VERSIONS_DIR = PROJECT_ROOT / "alembic" / "versions"


def _migration_text() -> str:
    migration = VERSIONS_DIR / "0001_session08_pgvector_documents_chunks.py"
    assert migration.is_file(), "Expected the baseline Session 08 Alembic migration file"
    return migration.read_text(encoding="utf-8")


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def test_session08_migration_creates_vector_extension() -> None:
    migration = _migration_text()

    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration


def test_session08_migration_creates_documents_table_contract() -> None:
    migration = _migration_text()
    compact = _compact(migration)

    assert 'op.create_table("documents",' in compact
    assert 'sa.Column("id",sa.BigInteger()' in compact
    assert 'sa.Column("source_path",sa.Text()' in compact
    assert 'sa.Column("document_type",sa.String(length=50)' in compact
    assert 'sa.Column("ingested_at",sa.DateTime(timezone=True)' in compact
    assert 'sa.Column("metadata",postgresql.JSONB' in compact
    assert 'sa.PrimaryKeyConstraint("id")' in compact
    assert "ix_documents_source_path" in migration
    assert "unique=True" in migration


def test_session08_migration_creates_chunks_table_contract() -> None:
    migration = _migration_text()
    compact = _compact(migration)

    assert 'op.create_table("chunks",' in compact
    assert 'sa.Column("id",sa.BigInteger()' in compact
    assert 'sa.Column("document_id",sa.BigInteger()' in compact
    assert 'sa.Column("chunk_type",sa.String(length=50)' in compact
    assert 'sa.Column("content",sa.Text()' in compact
    assert 'sa.Column("embedding",Vector(1536)' in compact
    assert 'sa.Column("metadata",postgresql.JSONB' in compact
    assert 'sa.Column("created_at",sa.DateTime(timezone=True)' in compact
    assert 'sa.ForeignKeyConstraint(["document_id"],["documents.id"],ondelete="CASCADE")' in compact
    assert 'sa.PrimaryKeyConstraint("id")' in compact


def test_session08_migration_creates_required_non_vector_indexes() -> None:
    migration = _migration_text()

    assert "ix_documents_source_path" in migration
    assert "ix_chunks_document_id" in migration
    assert "ix_chunks_chunk_type" in migration
    assert "ix_chunks_metadata_gin" in migration
    assert 'postgresql_using="gin"' in migration


def test_session08_baseline_migration_deliberately_has_no_vector_index() -> None:
    migration = _migration_text().lower()

    forbidden = [
        "hnsw",
        "ivfflat",
        "vector_cosine_ops",
        "vector_l2_ops",
        "vector_ip_ops",
    ]

    for token in forbidden:
        assert token not in migration


def test_session08_migration_has_downgrade_path() -> None:
    migration = _migration_text()

    assert "def downgrade() -> None:" in migration
    assert 'op.drop_table("chunks")' in migration
    assert 'op.drop_table("documents")' in migration
