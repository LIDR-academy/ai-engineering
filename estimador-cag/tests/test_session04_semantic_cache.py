"""
Tests for Session 04 semantic cache shadow infrastructure.

The semantic cache starts as an observational component only. It must not serve
responses yet, because approximate matching can be dangerous for estimates.
"""

from app.services.semantic_cache import (
    SemanticCacheCandidate,
    build_semantic_bucket,
    cosine_similarity,
    deterministic_text_embedding,
    find_best_semantic_candidate,
)


def test_semantic_bucket_includes_product_and_model_identity():
    """
    The semantic bucket must include fields that materially change an estimate.

    Why this matters:
    Similar descriptions are not interchangeable when prompt version, product
    type, detail level, output format, or model tier changes.
    """

    bucket = build_semantic_bucket(
        prompt_version="v2",
        project_type="web_saas",
        detail_level="medium",
        output_format="phases_table",
        model_identity="flash",
    )

    assert bucket == "v2:web_saas:medium:phases_table:flash"


def test_deterministic_embedding_is_stable_for_same_text():
    """
    Shadow mode tests need deterministic embeddings without external services.

    Why this matters:
    We can validate cache control flow now and later swap in real embeddings
    without changing the semantic cache contract.
    """

    first = deterministic_text_embedding("Build an onboarding SaaS")
    second = deterministic_text_embedding("Build an onboarding SaaS")

    assert first == second
    assert len(first) == 32


def test_cosine_similarity_scores_identical_vectors_as_one():
    """
    Cosine similarity gives us a deterministic similarity score.

    Why this matters:
    Shadow mode records candidate similarity, but must not serve from it yet.
    """

    vector = deterministic_text_embedding("same text")

    assert cosine_similarity(vector, vector) == 1.0


def test_find_best_semantic_candidate_returns_candidate_above_threshold():
    """
    A candidate above threshold should be visible to shadow-mode metrics.

    Why this matters:
    Shadow mode observes whether semantic caching would have found a match
    without using that match as the response.
    """

    query_embedding = deterministic_text_embedding("Build onboarding SaaS")
    candidate = SemanticCacheCandidate(
        key="candidate-1",
        bucket="v2:web_saas:medium:phases_table:flash",
        embedding=query_embedding,
        payload={"summary": "cached estimate"},
    )

    result = find_best_semantic_candidate(
        query_embedding=query_embedding,
        candidates=[candidate],
        threshold=0.85,
    )

    assert result is not None
    assert result.key == "candidate-1"
    assert result.similarity == 1.0


def test_find_best_semantic_candidate_returns_none_below_threshold():
    """
    Candidates below threshold must not be treated as hits.

    Why this matters:
    Semantic cache serving is disabled anyway, but the shadow signal must still
    be conservative and deterministic.
    """

    query_embedding = [1.0, 0.0]
    weak_candidate = SemanticCacheCandidate(
        key="weak",
        bucket="v2:web_saas:medium:phases_table:flash",
        embedding=[0.0, 1.0],
        payload={"summary": "wrong estimate"},
    )

    result = find_best_semantic_candidate(
        query_embedding=query_embedding,
        candidates=[weak_candidate],
        threshold=0.85,
    )

    assert result is None
