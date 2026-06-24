"""
LAYER: persistence database
RESPONSIBILITY: Build async SQLAlchemy engine and session factory.
WHY IT EXISTS: Session 08 moves embeddings from in-memory responses to
               PostgreSQL plus pgvector persistence.
"""

import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DEFAULT_DATABASE_URL = "postgresql+asyncpg://estimator:estimator@localhost:5432/estimator"


def get_database_url() -> str:
    """Return the runtime database URL.

    Docker can provide DATABASE_URL for service-to-service networking, while local
    development defaults to localhost.
    """
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def build_async_engine(database_url: str | None = None) -> AsyncEngine:
    """Build an async SQLAlchemy engine without opening a connection."""
    return create_async_engine(
        database_url or get_database_url(),
        pool_pre_ping=True,
    )


engine = build_async_engine()
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Yield one async database session for FastAPI dependencies."""
    async with AsyncSessionLocal() as session:
        yield session
