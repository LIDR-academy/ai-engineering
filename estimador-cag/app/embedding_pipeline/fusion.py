"""Rank fusion helpers for Session 10 hybrid retrieval.

The vector branch ranks chunks by cosine distance, while the lexical branch ranks
chunks by PostgreSQL full text relevance. Those raw scores are not comparable.
Reciprocal Rank Fusion combines only the rank positions, which keeps the
hybrid search deterministic and avoids brittle score normalization.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass, field

DEFAULT_RRF_K = 60


@dataclass(frozen=True)
class FusedRankingItem:
    """One document or chunk after Reciprocal Rank Fusion."""

    document_id: Hashable
    score: float
    ranks: dict[str, int] = field(default_factory=dict)


def reciprocal_rank_fusion(
    rankings: Mapping[str, Iterable[Hashable]],
    *,
    k: int = DEFAULT_RRF_K,
    limit: int | None = None,
) -> list[FusedRankingItem]:
    """Fuse ranked document identifiers using Reciprocal Rank Fusion.

    Args:
        rankings: Mapping from ranking name, such as ``vector`` or ``lexical``,
            to document identifiers ordered best first.
        k: Positive smoothing constant. The common teaching/default value is 60.
        limit: Optional maximum number of fused results to return.

    Returns:
        Fused results ordered by descending RRF score and deterministic ID
        tie-break.

    Raises:
        ValueError: If ``k`` is not positive or ``limit`` is negative.
    """

    if k <= 0:
        raise ValueError("RRF smoothing constant k must be positive")
    if limit is not None and limit < 0:
        raise ValueError("RRF result limit must be non negative")

    scores: defaultdict[Hashable, float] = defaultdict(float)
    ranks_by_document: defaultdict[Hashable, dict[str, int]] = defaultdict(dict)

    for ranking_name, ordered_ids in rankings.items():
        seen_in_branch: set[Hashable] = set()
        unique_rank = 0

        for document_id in ordered_ids:
            if document_id in seen_in_branch:
                continue

            seen_in_branch.add(document_id)
            unique_rank += 1

            scores[document_id] += 1 / (k + unique_rank)
            ranks_by_document[document_id][ranking_name] = unique_rank

    ordered_documents = sorted(
        scores,
        key=lambda document_id: (
            -scores[document_id],
            _stable_document_key(document_id),
        ),
    )

    if limit is not None:
        ordered_documents = ordered_documents[:limit]

    return [
        FusedRankingItem(
            document_id=document_id,
            score=scores[document_id],
            ranks=dict(ranks_by_document[document_id]),
        )
        for document_id in ordered_documents
    ]


def _stable_document_key(document_id: Hashable) -> tuple[str, str]:
    """Return a deterministic tie-break key for mixed identifier types."""

    return (type(document_id).__name__, repr(document_id))
