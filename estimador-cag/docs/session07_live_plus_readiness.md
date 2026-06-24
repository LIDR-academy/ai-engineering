# Session 07 Live Plus Readiness

This document explains what the `gg-session-07-live-plus` branch prepares and what it deliberately leaves for the next retrieval persistence task.

The branch improves Session 07 by turning the original embedding pipeline into a small chunking comparison lab. It does not implement persistence, semantic search, database migrations, vector indexes, or production retrieval.

## What is ready now

The branch now has a working in memory chunking lab:

1. Structural component chunking.
2. Whole budget baseline chunking.
3. Strategy statistics.
4. Query based top k ranking.
5. Deterministic keyword embedder for fake retrieval shaped tests.
6. Query corpus in `data/test_queries.json`.
7. CLI runner in `scripts/compare_chunkers.py`.
8. Generated comparison report in `docs/session07_chunking_comparison_report.md`.
9. FastAPI endpoint `POST /embeddings/compare`.
10. Dependency providers in the router so tests and later services can override collaborators cleanly.

## Why this matters

The useful lesson is not only that embeddings exist. The useful lesson is that chunking strategy changes what a future retriever can find.

The structural component strategy keeps each budget component isolated while preserving parent project context. The whole budget strategy blends several components into one larger vector. The comparison lab makes that trade off visible through stats and query rankings.

## What the dependency providers prepare

The router now has dependency providers for current collaborators.

This matters because future routes should avoid constructing infrastructure directly inside endpoint functions. The healthier shape is:

    endpoint
    -> dependency providers
    -> service
    -> repository or store
    -> fakeable services in tests

This branch already uses that pattern for the comparison endpoint. That makes the next retrieval persistence work faster and safer because future services can be introduced behind dependency providers instead of hardwired constructors.

## What is intentionally deferred

No persistence is implemented in this branch.

The following items are intentionally deferred:

1. document storage
2. chunk storage
3. pgvector migration
4. database repository
5. duplicate document detection
6. semantic retrieval
7. search endpoint
8. vector index
9. async database sessions
10. production retrieval evaluation

These are not mistakes or missing pieces. They are boundaries.

## Expected future mapping

The next retrieval persistence work will likely need these concepts.

| Future concept | Current preparation | Expected future work |
| --- | --- | --- |
| document storage | budget and query fixtures exist | add a document table or model |
| chunk storage | chunks already have IDs, text, metadata, and token counts | persist chunks and embeddings |
| pgvector | embeddings already use vector shaped data | add vector column and migration later |
| repository layer | dependency providers now exist | introduce fakeable repository boundary |
| semantic retrieval | query ranking shape already exists | embed query and rank persisted chunks |
| endpoint testing | router dependency overrides now exist | override services instead of calling real DB or OpenAI |
| evaluation corpus | `data/test_queries.json` exists | reuse queries for retrieval sanity checks |

## What tests should come first later

Future persistence work should begin with tests before implementation.

Recommended first tests:

1. A store model test proving documents and chunks have the expected metadata shape.
2. A repository test proving duplicate source detection.
3. A service test proving budget input becomes persisted document and chunks.
4. A router test proving persistence errors return safe HTTP responses.
5. A retriever test proving query embedding uses the same embedding model family as stored chunks.
6. A search endpoint test using a fake retriever.

The important principle is simple: normal tests must not require real OpenAI or a live vector database unless the test is explicitly marked as an integration smoke.

## What not to copy blindly

Do not blindly port a larger reference implementation into this branch.

The current project should preserve its existing FastAPI shape and evolve through small tested seams. Rails UI code, vector persistence, indexing, ingestion job orchestration, and semantic search belong to later slices only when the official requirements are clear.

## Final branch boundary

This branch is a strong Session 07 Live Plus branch.

It is ready because it now includes:

1. chunking strategy comparison
2. query ranking mechanics
3. deterministic CLI lab
4. FastAPI comparison endpoint
5. report evidence
6. dependency seams for future services

It stops before persistence.

No persistence is implemented in this branch.
