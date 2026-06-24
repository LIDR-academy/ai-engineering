"""
Seed repeatable Session 10 retrieval demo data into PostgreSQL.

This script makes the Streamlit retrieval demo reproducible. It loads the
small course sample from data/budgets_sample.json, converts budget components
into retrieval chunks, and inserts them into the persisted document/chunk store.

The script is idempotent. It uses one source_path per budget:

    data/budgets_sample.json::<budget_id>

If a budget has already been seeded, it is skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text  # noqa: E402

from app.persistence.database import AsyncSessionLocal  # noqa: E402
from app.persistence.repository import ChunkInsert, DocumentRepository  # noqa: E402
from evals.session10_retrieval.run import (  # noqa: E402
    DEFAULT_BUDGETS_PATH,
    HashingVectorizer,
    build_component_chunks,
)

SOURCE_PREFIX = "data/budgets_sample.json::"
DOCUMENT_TYPE = "session10_budget_sample"


@dataclass(frozen=True)
class SeedDocument:
    """One source budget and the component chunks that should be inserted."""

    budget_id: str
    source_path: str
    chunks: tuple[ChunkInsert, ...]
    metadata: dict[str, Any]


def build_seed_plan(budgets_path: Path = DEFAULT_BUDGETS_PATH) -> list[SeedDocument]:
    """Build an idempotent insertion plan from the sample budgets JSON."""
    vectorizer = HashingVectorizer()
    chunks = build_component_chunks(budgets_path=budgets_path, vectorizer=vectorizer)

    grouped: dict[str, list[ChunkInsert]] = defaultdict(list)
    for chunk in chunks:
        budget_id = str(chunk.metadata["budget_id"])
        grouped[budget_id].append(
            ChunkInsert(
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                embedding=chunk.embedding,
                metadata=dict(chunk.metadata),
            )
        )

    plan = []
    for budget_id in sorted(grouped):
        plan.append(
            SeedDocument(
                budget_id=budget_id,
                source_path=f"{SOURCE_PREFIX}{budget_id}",
                chunks=tuple(grouped[budget_id]),
                metadata={
                    "seed": "session10_demo",
                    "budget_id": budget_id,
                    "source": str(budgets_path),
                },
            )
        )

    return plan


def build_dry_run_summary(plan: list[SeedDocument]) -> dict[str, Any]:
    """Return a deterministic summary without opening a database connection."""
    return {
        "mode": "dry_run",
        "documents_planned": len(plan),
        "chunks_planned": sum(len(document.chunks) for document in plan),
        "source_paths": [document.source_path for document in plan],
        "budget_ids": [document.budget_id for document in plan],
    }


async def seed_demo_data(
    *,
    budgets_path: Path = DEFAULT_BUDGETS_PATH,
) -> dict[str, Any]:
    """Seed demo data into PostgreSQL and return an audit summary."""
    plan = build_seed_plan(budgets_path)

    async with AsyncSessionLocal() as session:
        repo = DocumentRepository(session)

        before_documents = (await session.execute(text("select count(*) from documents"))).scalar_one()
        before_chunks = (await session.execute(text("select count(*) from chunks"))).scalar_one()

        inserted_documents = 0
        inserted_chunks = 0
        skipped_documents = 0
        inserted_source_paths = []
        skipped_source_paths = []

        for document in plan:
            existing_id = await repo.find_document_id_by_source_path(document.source_path)

            if existing_id is not None:
                skipped_documents += 1
                skipped_source_paths.append(document.source_path)
                continue

            await repo.add_document_with_chunks(
                source_path=document.source_path,
                document_type=DOCUMENT_TYPE,
                chunks=list(document.chunks),
                metadata=document.metadata,
            )

            inserted_documents += 1
            inserted_chunks += len(document.chunks)
            inserted_source_paths.append(document.source_path)

        await session.commit()

        after_documents = (await session.execute(text("select count(*) from documents"))).scalar_one()
        after_chunks = (await session.execute(text("select count(*) from chunks"))).scalar_one()

    return {
        "mode": "seed",
        "before": {"documents": before_documents, "chunks": before_chunks},
        "inserted": {"documents": inserted_documents, "chunks": inserted_chunks},
        "skipped_documents": skipped_documents,
        "after": {"documents": after_documents, "chunks": after_chunks},
        "inserted_source_paths": inserted_source_paths,
        "skipped_source_paths": skipped_source_paths,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budgets", type=Path, default=DEFAULT_BUDGETS_PATH)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.dry_run:
        payload = build_dry_run_summary(build_seed_plan(args.budgets))
    else:
        payload = asyncio.run(seed_demo_data(budgets_path=args.budgets))

    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
