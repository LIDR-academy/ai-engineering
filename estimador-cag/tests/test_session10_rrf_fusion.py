import pytest

from app.embedding_pipeline.fusion import reciprocal_rank_fusion


def _ids(items):
    return [item.document_id for item in items]


def test_common_document_in_both_rankings_wins():
    result = reciprocal_rank_fusion(
        {
            "vector": ["budget-a", "budget-b"],
            "lexical": ["budget-b", "budget-c"],
        }
    )

    assert _ids(result) == ["budget-b", "budget-a", "budget-c"]
    assert result[0].ranks == {"vector": 2, "lexical": 1}


def test_empty_rankings_return_empty_result():
    assert reciprocal_rank_fusion({"vector": [], "lexical": []}) == []


def test_duplicate_ids_inside_one_ranking_do_not_double_count():
    result = reciprocal_rank_fusion({"vector": ["budget-a", "budget-a", "budget-b"]})

    assert _ids(result) == ["budget-a", "budget-b"]
    assert result[0].score == pytest.approx(1 / 61)
    assert result[1].score == pytest.approx(1 / 62)


def test_invalid_rrf_k_rejects():
    with pytest.raises(ValueError, match="positive"):
        reciprocal_rank_fusion({"vector": ["budget-a"]}, k=0)


def test_limit_is_applied_after_fusion():
    result = reciprocal_rank_fusion(
        {
            "vector": ["budget-a", "budget-b", "budget-c"],
            "lexical": ["budget-c", "budget-b", "budget-a"],
        },
        limit=2,
    )

    assert len(result) == 2
    assert _ids(result) == ["budget-a", "budget-c"]


def test_tie_breaking_is_deterministic():
    result = reciprocal_rank_fusion(
        {
            "vector": ["budget-b"],
            "lexical": ["budget-a"],
        }
    )

    assert _ids(result) == ["budget-a", "budget-b"]
