import os
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.skipif(
    os.environ.get("SESSION08_DB_INTEGRATION") != "1",
    reason="Session 08 vector index integration tests require local Postgres and explicit opt-in.",
)


@pytest.fixture
def db_session_factory() -> Iterator[async_sessionmaker[AsyncSession]]:
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://estimator:estimator@localhost:5432/estimator",
    )
    engine = create_async_engine(database_url, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        yield factory
    finally:
        import asyncio

        asyncio.run(engine.dispose())


def test_session08_db_has_hnsw_cosine_vector_index(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def check_index() -> None:
        async with db_session_factory() as session:
            result = await session.execute(
                sa.text(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'chunks'
                      AND indexname = 'ix_chunks_embedding_hnsw_cosine'
                    """
                )
            )

        rows = result.mappings().all()

        assert len(rows) == 1
        indexdef = rows[0]["indexdef"].lower()
        assert "using hnsw" in indexdef
        assert "vector_cosine_ops" in indexdef
        assert "embedding is not null" in indexdef

    import asyncio

    asyncio.run(check_index())
