from sqlalchemy import Index

from app.persistence.database import DEFAULT_DATABASE_URL, build_async_engine, get_database_url
from app.persistence.models import Base, Chunk, Document


def test_session08_base_metadata_contains_document_and_chunk_tables() -> None:
    assert "documents" in Base.metadata.tables
    assert "chunks" in Base.metadata.tables


def test_session08_document_model_matches_schema_contract() -> None:
    table = Document.__table__

    assert table.name == "documents"
    assert set(table.columns.keys()) == {
        "id",
        "source_path",
        "document_type",
        "ingested_at",
        "metadata",
    }

    assert table.c.id.primary_key
    assert table.c.id.type.python_type is int
    assert table.c.source_path.nullable is False
    assert table.c.document_type.type.length == 50
    assert table.c.ingested_at.nullable is False
    assert table.c.metadata.nullable is False

    assert hasattr(Document, "document_metadata")


def test_session08_chunk_model_matches_schema_contract() -> None:
    table = Chunk.__table__

    assert table.name == "chunks"
    assert set(table.columns.keys()) == {
        "id",
        "document_id",
        "chunk_type",
        "content",
        "embedding",
        "metadata",
        "created_at",
    }

    assert table.c.id.primary_key
    assert table.c.document_id.nullable is False
    assert table.c.chunk_type.type.length == 50
    assert table.c.content.nullable is False
    assert table.c.embedding.nullable is True
    assert "VECTOR(1536)" in str(table.c.embedding.type).upper()
    assert table.c.metadata.nullable is False
    assert table.c.created_at.nullable is False

    foreign_key = next(iter(table.c.document_id.foreign_keys))
    assert foreign_key.target_fullname == "documents.id"
    assert foreign_key.ondelete == "CASCADE"

    assert hasattr(Chunk, "chunk_metadata")


def test_session08_models_define_required_indexes() -> None:
    document_indexes = {index.name: index for index in Document.__table__.indexes}
    chunk_indexes = {index.name: index for index in Chunk.__table__.indexes}

    assert document_indexes["ix_documents_source_path"].unique is True
    assert _index_columns(document_indexes["ix_documents_source_path"]) == ["source_path"]

    assert _index_columns(chunk_indexes["ix_chunks_document_id"]) == ["document_id"]
    assert _index_columns(chunk_indexes["ix_chunks_chunk_type"]) == ["chunk_type"]

    metadata_index = chunk_indexes["ix_chunks_metadata_gin"]
    assert _index_columns(metadata_index) == ["metadata"]
    assert metadata_index.dialect_options["postgresql"]["using"] == "gin"


def test_session08_database_url_defaults_to_local_postgres(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert get_database_url() == DEFAULT_DATABASE_URL


def test_session08_database_url_can_be_overridden(monkeypatch) -> None:
    expected = "postgresql+asyncpg://user:pass@example.test:5432/custom"
    monkeypatch.setenv("DATABASE_URL", expected)

    assert get_database_url() == expected


def test_session08_build_async_engine_uses_database_url() -> None:
    database_url = "postgresql+asyncpg://estimator:estimator@localhost:5432/estimator"

    engine = build_async_engine(database_url)

    assert engine.url.drivername == "postgresql+asyncpg"
    assert engine.url.username == "estimator"
    assert engine.url.password == "estimator"
    assert engine.url.host == "localhost"
    assert engine.url.port == 5432
    assert engine.url.database == "estimator"


def _index_columns(index: Index) -> list[str]:
    return [column.name for column in index.columns]
