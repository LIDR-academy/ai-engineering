from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_DIR = REPO_ROOT / "estimador-cag" / "alembic" / "versions"
MIGRATION = VERSIONS_DIR / "0002_session08_hnsw_vector_index.py"


def _migration_text() -> str:
    assert MIGRATION.is_file()
    return MIGRATION.read_text(encoding="utf-8")


def test_session08_hnsw_migration_declares_revision_chain() -> None:
    migration = _migration_text()

    assert 'revision: str = "0002_session08_hnsw_vector_index"' in migration
    assert 'down_revision: str | None = "0001_session08_pgvector"' in migration


def test_session08_hnsw_migration_creates_cosine_vector_index() -> None:
    migration = _migration_text()

    assert "ix_chunks_embedding_hnsw_cosine" in migration
    assert "USING hnsw" in migration
    assert "embedding vector_cosine_ops" in migration
    assert "WHERE embedding IS NOT NULL" in migration
    assert "CREATE INDEX IF NOT EXISTS" in migration


def test_session08_hnsw_migration_has_downgrade_path() -> None:
    migration = _migration_text()

    assert "def downgrade() -> None:" in migration
    assert "DROP INDEX IF EXISTS ix_chunks_embedding_hnsw_cosine" in migration
