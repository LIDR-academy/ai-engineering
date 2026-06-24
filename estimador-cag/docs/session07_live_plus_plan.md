# Session 07 Live Plus Learning Plan

## Purpose

This branch exists to improve the completed Session 07 pre-exercise by learning from the teacher live implementation and translating the useful ideas into the current `estimador-cag` architecture.

This is not the official delivery branch. The official delivered branch stays frozen unless explicitly required.

Official delivery branch:

    session-07/pre-exercise

Working learning branch:

    gg-session-07-live-plus

Main mission:

    Improve our embedding and chunking pipeline enough that the project is ready for the next retrieval/persistence stage, without implementing that later stage yet.

## Scope

In scope:

1. Understand our current embedding pipeline.
2. Understand the teacher live chunking lab.
3. Translate useful teacher ideas into our FastAPI project.
4. Add comparison tooling around chunking strategies.
5. Add a small query corpus and deterministic evaluation scaffolding.
6. Preserve the existing `POST /embeddings/ingest` behavior.
7. Keep tests fake-key safe.

Out of scope for now:

1. pgvector persistence.
2. database migrations.
3. persisted document/chunk tables.
4. semantic search endpoint.
5. Rails UI port.
6. Anthropic Contextual Retrieval implementation.
7. propositional chunking implementation.
8. normal tests that depend on real OpenAI or a real database.

## Current baseline in our repo

| File | Responsibility | Current behavior | Strength | Gap to improve |
| --- | --- | --- | --- | --- |
| `app/embedding_pipeline/schemas.py` | Pydantic contracts. | Defines budget, component, chunk, embedded chunk, ingest request/response, and stats. | Clean minimum contract. | No comparison request/response models yet. |
| `app/embedding_pipeline/chunker.py` | Structural chunker. | One budget component becomes one chunk with parent project context and metadata. | Correct baseline for historical budgets. | Only one strategy. No protocol or registry. |
| `app/embedding_pipeline/embedder.py` | OpenAI embedding adapter. | Uses `text-embedding-3-small`, batching, retry, fake client injection, and tokenizer-based token counting. | Good testability and observability. | No strategy comparison integration yet. |
| `app/embedding_pipeline/router.py` | FastAPI embedding endpoint. | `POST /embeddings/ingest` chunks budgets and returns embedded chunks in memory. | Minimal and working. | No compare endpoint. Direct embedder construction limits dependency override patterns. |
| `scripts/compare.py` | Pairwise similarity CLI. | Embeds two texts and computes cosine similarity manually. | Good sanity tool. | Not enough for corpus-level chunking experiments. |
| `data/budgets_sample.json` | Sample corpus. | Four budgets and eight components. | Valid and deterministic. | Small; needs query corpus for comparisons. |
| `tests/test_embedding_*.py` | Optional test suite. | Covers schemas, chunker, embedder, router, CLI, and sample data. | Stronger than required. | No comparison tests yet. |

## Teacher live implementation inventory

The teacher live package contains two broad areas:

1. Python service code for chunking, embedding, and comparison.
2. Rails web UI code for visualizing the chunking lab.

Only the first area maps directly to our FastAPI service. Rails code should be treated as product/UI inspiration, not copied.

| Teacher area | Concept | What it teaches | Port directly? | Translate into our repo? | Decision |
| --- | --- | --- | --- | --- | --- |
| `app/generation/rag/chunking/base.py` | Chunker interface. | Strategies should share a contract: name, chunk method, token accounting. | No. | Yes. | Add a lightweight strategy protocol if needed for comparisons. |
| `app/generation/rag/chunking/structural.py` | Structural chunking. | Component-level chunks remain the strongest baseline for budget JSON. | No. | Partially. | Keep our current chunker, adapt only if comparison needs an interface. |
| `chunking/strategies/fixed_size.py` | Mechanical baseline. | Fixed-size chunks are easy to compare and often reveal why structure matters. | No. | Yes. | Good first additional strategy. |
| `chunking/strategies/recursive.py` | Recursive splitting. | More realistic mechanical splitting than naive fixed-size. | No. | Later. | Add after fixed-size baseline if useful. |
| `chunking/strategies/sentence_window.py` | Sentence-window strategy. | Surrounding sentence context can preserve local coherence. | No. | Later. | Defer until deterministic tokenizer/sentence splitting is designed. |
| `chunking/strategies/hierarchical.py` | Parent-child chunking. | Parent context plus child chunks can improve retrieval explainability. | No. | Later. | Valuable but not Slice 1. |
| `chunking/strategies/semantic.py` | Semantic splitting. | Embeddings can guide split points. | No. | Later. | Requires careful fakes and live boundary. |
| `chunking/strategies/contextual_retrieval.py` | Contextual chunk enrichment. | Chunks can be enriched with broader document context. | No. | Documentation first. | Powerful, but too live-model dependent for first slice. |
| `chunking/strategies/propositional.py` | LLM-generated propositions. | Decomposes text into atomic claims. | No. | No for now. | High cost and high variance. Needs evals first. |
| `analysis/comparison.py` | Chunking comparison service. | Compare strategies by chunk count, token distribution, top-k similarity, and query behavior. | No. | Yes. | This is the core idea to translate. |
| `analysis/similarity.py` | Cosine utilities. | Similarity calculation should be reusable beyond pairwise CLI. | No. | Yes. | Reuse or extract from `scripts/compare.py`. |
| `scripts/compare_chunkers.py` | CLI lab. | Run all strategies over a corpus and query set, then report results. | No. | Yes. | Best target for Slice 2. |
| `data/test_queries.json` | Query corpus. | Comparisons need fixed queries, not just random examples. | No. | Yes. | Add our own small query set aligned to our sample budgets. |
| Rails `chunking_comparisons_controller.rb` and views | Product UI. | A chunking lab is useful for humans. | No. | Maybe later as FastAPI/Streamlit. | Do not port Rails. |
| Rails RAG models | Response shape wrappers. | Typed result objects improve UI rendering. | No. | Maybe as Pydantic models. | Translate contracts only if needed. |

## Future-readiness inventory

The prepared future material shows where the architecture is heading, but this branch should only prepare for it conceptually.

| Future concept | What it means | Why it matters later | What we do now |
| --- | --- | --- | --- |
| Document table | One row per ingested source document or budget corpus. | Provides identity, source path, checksum, and metadata. | Document the boundary; do not implement. |
| Chunk table | One row per chunk with metadata and vector. | Makes retrieval possible after ingestion. | Keep our chunk shape compatible in spirit. |
| JSONB metadata | Flexible metadata storage for filters and explainability. | Enables sector, technology, year, complexity, source filtering. | Preserve metadata discipline in current chunks. |
| Duplicate detection | Avoid ingesting the same source repeatedly. | Prevents bloated vector stores and confusing results. | Plan it later; not in this branch. |
| Query embedding | Search embeds the query using the same embedding model. | Model mismatch breaks vector comparison. | Keep embedder reusable and fakeable. |
| Sequential scan baseline | Search without vector index first. | Easier to prove correctness before performance optimization. | Note as future principle only. |
| Vector index | Approximate nearest neighbor search. | Performance optimization after correctness. | Explicitly out of scope. |

## Architecture mapping

| Teacher concept | Our current path | Proposed path in this branch | Action |
| --- | --- | --- | --- |
| Chunker interface | none | `app/embedding_pipeline/comparison.py` can define a local protocol first. | Avoid refactor until needed. |
| Structural chunker | `app/embedding_pipeline/chunker.py` | Keep existing. | Reuse. |
| Fixed-size baseline | none | `app/embedding_pipeline/comparison.py` or `app/embedding_pipeline/chunking_strategies.py`. | Add in Slice 1. |
| Similarity utilities | `scripts/compare.py` | Extract reusable cosine helper only if tests justify it. | Avoid premature movement. |
| Chunking comparison engine | none | `app/embedding_pipeline/comparison.py`. | Slice 1 target. |
| Compare chunkers CLI | none | `scripts/compare_chunkers.py`. | Slice 2 target. |
| Query corpus | none | `data/test_queries.json`. | Slice 2 target. |
| Rails chunking lab | none | Maybe future Streamlit or FastAPI docs. | Do not port now. |
| Future persisted ingest | none | future module, not this branch. | Defer. |
| Future semantic retriever | none | future module, not this branch. | Defer. |

## Recommended mission

Recommended mission: Session 07 Live Plus.

This means:

1. Improve the completed Session 07 pipeline.
2. Add an in-memory chunking comparison lab.
3. Add deterministic tests and query corpus.
4. Keep the existing ingest endpoint working.
5. Avoid persistence and search until the actual task arrives.

This mission is strong because it teaches the real lesson of the live class: chunking strategy matters, and it must be measured on your own corpus instead of chosen by vibes.

## Slice plan

| Slice | Learning objective | Files touched | Tests first | Expected red | Green patch | Gates | Stop condition | Commit message |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Slice 0: Live plus map | Understand what to port, translate, ignore, and defer. | `docs/session07_live_plus_plan.md` | No code tests needed. | File missing. | Create this document. | Ruff, py_compile, pytest, diff checks. | Stop after doc. | `Map Session 07 live plus learning plan` |
| Slice 1: In-memory comparison core | Compare structural chunking against a simple baseline. | `app/embedding_pipeline/comparison.py`, tests. | Test stats and fake ranking. | Missing comparator. | Add comparator with structural and fixed-size/budget-level baseline. | Ruff, py_compile, pytest. | Stop before CLI. | `Add in-memory chunking comparison core` |
| Slice 2: Query corpus and CLI | Learn corpus/query evaluation. | `data/test_queries.json`, `scripts/compare_chunkers.py`, tests. | CLI help/import test red. | Missing CLI/query file. | Add deterministic CLI and report output. | Ruff, py_compile, pytest. | Stop before API endpoint. | `Add chunking comparison CLI and query corpus` |
| Slice 3: Comparison endpoint | Expose lab through FastAPI. | `router.py`, schemas/tests. | `/embeddings/compare` missing. | Add endpoint with fakeable service. | Ruff, py_compile, pytest, `/docs`. | Stop before UI. | `Expose chunking comparison endpoint` |
| Slice 4: Optional learning report | Summarize observed results from our corpus. | `docs/session07_chunking_comparison_report.md`. | Not needed. | Run deterministic and optional live comparison, record results honestly. | Ruff, py_compile, pytest. | Stop before persistence. | `Document Session 07 chunking comparison results` |

## Non-goals

1. Do not replace the existing pre-exercise endpoint.
2. Do not move everything into a new architecture just because the teacher code does.
3. Do not port Rails.
4. Do not add DB persistence.
5. Do not add vector indexes.
6. Do not make normal tests use real OpenAI.
7. Do not implement live-model chunking strategies before deterministic comparison exists.

## What I should learn

After this branch, I should be able to explain:

1. Why one component per chunk is a strong structural baseline.
2. Why fixed-size or whole-budget chunks are useful as comparison baselines but weak defaults.
3. Why query choice changes the apparent quality of a chunking strategy.
4. Why top-k comparison is more useful than only chunk count and token count.
5. Why metadata should travel separately from embedded text.
6. Why persistence and retrieval should wait until the comparison baseline is clear.

## Validation checklist

Run in Codespaces before considering Slice 0 complete locally:

    cd /workspaces/ai-engineering/estimador-cag
    uv run ruff check --fix app evals tests scripts
    uv run ruff check app evals tests scripts
    uv run python -m py_compile $(find app tests evals scripts -name '*.py' -type f 2>/dev/null) streamlit_app.py
    OPENAI_API_KEY=test DEEPSEEK_API_KEY=test KIMI_API_KEY=test uv run pytest -q

Then:

    cd /workspaces/ai-engineering
    git diff --check
    git diff --stat
    git status --short

Before commit in a local repo:

    git add estimador-cag/docs/session07_live_plus_plan.md
    git diff --cached --check
    git diff --cached --stat
    git diff --cached --name-only
    git diff --cached | grep -E "sk-[A-Za-z0-9_-]{20,}|OPENAI_API_KEY=.+|KIMI_API_KEY=.+|DEEPSEEK_API_KEY=.+|Bearer [A-Za-z0-9._-]{20,}|BEGIN (RSA|OPENSSH|PRIVATE) KEY" && echo "POSSIBLE SECRET FOUND" || echo "No obvious secret value found"

## Stop condition

Stop after Slice 0.

Recommended next action:

    Start Slice 1: in-memory chunking comparison core.
