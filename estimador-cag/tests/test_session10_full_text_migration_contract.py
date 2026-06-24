import re
from pathlib import Path


def test_session10_full_text_migration_exists_after_hnsw_revision():
    migration = Path("alembic/versions/0003_session10_full_text_search.py")

    assert migration.exists(), "Session 10 must add a full text search migration"

    text = migration.read_text(encoding="utf-8")

    assert "down_revision" in text
    assert "0002" in text, "Session 10 migration should come after the Session 08 HNSW revision"
    assert "content_tsv" in text
    assert "tsvector" in text
    assert "GENERATED ALWAYS AS" in text
    assert "to_tsvector(" in text
    assert "using gin" in text.lower() or "postgresql_using=\"gin\"" in text
    assert "ix_chunks_content_tsv" in text


def test_session10_full_text_migration_uses_one_consistent_text_search_config():
    migration = Path("alembic/versions/0003_session10_full_text_search.py")
    text = migration.read_text(encoding="utf-8")

    configs = set(re.findall(r"to_tsvector\('([^']+)'", text))

    assert len(configs) == 1
    assert configs <= {"english", "spanish"}
