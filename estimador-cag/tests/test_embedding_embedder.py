from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.embedding_pipeline.chunker import JSONStructuralChunker
from app.embedding_pipeline.embedder import (
    EMBEDDING_MODEL,
    EMBEDDING_PRICE_USD_PER_1M_TOKENS,
    OpenAIEmbedder,
    count_embedding_tokens,
    estimate_embedding_cost_usd,
)
from app.embedding_pipeline.schemas import Budget


@dataclass
class FakeEmbeddingItem:
    embedding: list[float]


@dataclass
class FakeEmbeddingResponse:
    data: list[FakeEmbeddingItem]


class FakeEmbeddingsResource:
    def __init__(self, embeddings_by_call: list[list[list[float]]]) -> None:
        self.embeddings_by_call = embeddings_by_call
        self.calls: list[dict] = []

    def create(self, *, model: str, input: list[str]) -> FakeEmbeddingResponse:
        self.calls.append({"model": model, "input": input})
        embeddings = self.embeddings_by_call.pop(0)
        return FakeEmbeddingResponse(
            data=[FakeEmbeddingItem(embedding=embedding) for embedding in embeddings]
        )


class FakeOpenAIClient:
    def __init__(self, embeddings_by_call: list[list[list[float]]]) -> None:
        self.embeddings = FakeEmbeddingsResource(embeddings_by_call)


def sample_chunks():
    budget = Budget.model_validate(
        {
            "budget_id": "BUD-2024-014",
            "client_metadata": {
                "name": "FintechCorp",
                "sector": "finance",
                "country": "ES",
            },
            "project_summary": "Mobile banking API with OAuth 2.0 authentication",
            "main_technology": "ruby_on_rails",
            "year": 2024,
            "total_estimated_hours": 200,
            "components": [
                {
                    "component_id": "AUTH-001",
                    "name": "OAuth 2.0 authentication backend",
                    "description": "JWT-based session management for a fintech mobile app.",
                    "tech_stack": ["ruby_on_rails", "postgresql", "redis"],
                    "estimated_hours": 120,
                    "complexity": "high",
                    "dependencies": [],
                },
                {
                    "component_id": "DB-001",
                    "name": "Database migration",
                    "description": "Migration from MySQL to PostgreSQL with rollback plan.",
                    "tech_stack": ["postgresql"],
                    "estimated_hours": 80,
                    "complexity": "medium",
                    "dependencies": ["AUTH-001"],
                },
            ],
        }
    )
    return JSONStructuralChunker().chunk([budget])


def test_embed_texts_uses_openai_embeddings_endpoint_with_expected_model() -> None:
    client = FakeOpenAIClient(embeddings_by_call=[[[0.1, 0.2], [0.3, 0.4]]])
    embedder = OpenAIEmbedder(client=client)

    embeddings = embedder.embed_texts(["alpha", "beta"])

    assert embeddings == [[0.1, 0.2], [0.3, 0.4]]
    assert client.embeddings.calls == [
        {"model": EMBEDDING_MODEL, "input": ["alpha", "beta"]},
    ]


def test_embed_one_reuses_embed_texts() -> None:
    client = FakeOpenAIClient(embeddings_by_call=[[[0.9, 0.8, 0.7]]])
    embedder = OpenAIEmbedder(client=client)

    assert embedder.embed_one("single text") == [0.9, 0.8, 0.7]


def test_embed_many_preserves_chunk_fields_and_adds_embeddings() -> None:
    chunks = sample_chunks()
    client = FakeOpenAIClient(embeddings_by_call=[[[0.1, 0.2], [0.3, 0.4]]])
    embedder = OpenAIEmbedder(client=client)

    embedded = embedder.embed_many(chunks)

    assert [chunk.chunk_id for chunk in embedded] == [
        "BUD-2024-014::AUTH-001",
        "BUD-2024-014::DB-001",
    ]
    assert embedded[0].text == chunks[0].text
    assert embedded[0].metadata == chunks[0].metadata
    assert embedded[0].token_count == chunks[0].token_count
    assert embedded[0].embedding == [0.1, 0.2]
    assert embedded[1].embedding == [0.3, 0.4]


def test_embed_texts_batches_requests_in_groups_of_100() -> None:
    first_batch_embeddings = [[float(index)] for index in range(100)]
    second_batch_embeddings = [[100.0], [101.0]]
    client = FakeOpenAIClient(
        embeddings_by_call=[first_batch_embeddings, second_batch_embeddings]
    )
    embedder = OpenAIEmbedder(client=client, batch_size=100)

    embeddings = embedder.embed_texts([f"text-{index}" for index in range(102)])

    assert len(embeddings) == 102
    assert len(client.embeddings.calls) == 2
    assert len(client.embeddings.calls[0]["input"]) == 100
    assert len(client.embeddings.calls[1]["input"]) == 2


def test_rate_limit_errors_are_retried_with_exponential_backoff(monkeypatch) -> None:
    class FakeRateLimitError(Exception):
        pass

    class FlakyEmbeddingsResource:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, *, model: str, input: list[str]) -> FakeEmbeddingResponse:
            self.calls += 1
            if self.calls < 3:
                raise FakeRateLimitError("slow down, moon captain")
            return FakeEmbeddingResponse(data=[FakeEmbeddingItem(embedding=[1.0])])

    class FlakyClient:
        def __init__(self) -> None:
            self.embeddings = FlakyEmbeddingsResource()

    sleeps: list[int] = []
    monkeypatch.setattr("app.embedding_pipeline.embedder.RateLimitError", FakeRateLimitError)
    monkeypatch.setattr("app.embedding_pipeline.embedder.time.sleep", sleeps.append)

    client = FlakyClient()
    embedder = OpenAIEmbedder(client=client)

    assert embedder.embed_one("retry me") == [1.0]
    assert client.embeddings.calls == 3
    assert sleeps == [1, 2]


def test_non_rate_limit_errors_are_propagated() -> None:
    class BrokenEmbeddingsResource:
        def create(self, *, model: str, input: list[str]) -> FakeEmbeddingResponse:
            raise RuntimeError("boom")

    class BrokenClient:
        embeddings = BrokenEmbeddingsResource()

    embedder = OpenAIEmbedder(client=BrokenClient())

    with pytest.raises(RuntimeError, match="boom"):
        embedder.embed_one("explode")


def test_estimate_embedding_cost_uses_exercise_price_constant() -> None:
    assert EMBEDDING_PRICE_USD_PER_1M_TOKENS == 0.02
    assert estimate_embedding_cost_usd(1_000_000) == 0.02
    assert estimate_embedding_cost_usd(500_000) == 0.01


def test_count_embedding_tokens_uses_embedding_tokenizer_not_character_count() -> None:
    texts = [
        "OAuth 2.0 authentication backend with JWT tokens",
        "Authorization service using JSON Web Tokens",
    ]

    token_count = count_embedding_tokens(texts)

    assert token_count > 0
    assert token_count < sum(len(text) for text in texts)
