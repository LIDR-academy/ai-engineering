# Estimador CAG

Current branch:

```text
gg-session-10/pre-work
```

Current focus:

```text
Session 10 — advanced retrieval compass, hybrid retrieval, reranking, and A/B/C/D evaluation
```

## Current retrieval stack

The project now contains a layered retrieval implementation:

| Layer | Files |
| --- | --- |
| Persistence | `app/persistence/models.py`, `app/persistence/repository.py` |
| Vector retrieval | `app/embedding_pipeline/search_service.py` |
| Lexical retrieval | `DocumentRepository.search_chunks_by_text` |
| Fusion | `app/embedding_pipeline/fusion.py` |
| Reranking | `app/embedding_pipeline/reranker.py` |
| API | `app/routers/search.py` |
| Evaluation | `evals/session10_retrieval/` |

## Public search API

`POST /search` supports:

| Field | Meaning |
| --- | --- |
| `query` | Search query |
| `k` | Final result count |
| `search_mode` | `vector` or `hybrid` |
| `recall_k` | Wider internal candidate pool used by hybrid and reranking experiments |
| metadata filters | sector, country, technology, complexity, year, budget, component, stack, scope |

The router intentionally exposes vector and hybrid search. The deterministic reranker is currently measured at service level and is not exposed publicly through the API.

## A/B/C/D evaluation

The committed Session 10 measurement runner compares:

| Config | Search | Reranking |
| --- | --- | --- |
| A | Vector | No |
| B | Hybrid | No |
| C | Vector | Yes |
| D | Hybrid | Yes |

Run:

```bash
cd /workspaces/ai-engineering/estimador-cag

uv run python -m evals.session10_retrieval.run \
  --output evals/session10_retrieval/results.json \
  --report evals/session10_retrieval/REPORT.md \
  --k 5 \
  --recall-k 8
```

Outputs:

```text
evals/session10_retrieval/results.json
evals/session10_retrieval/REPORT.md
```

## Current measured result

All variants currently solve the small deterministic golden set:

| Config | result budget precision@5 | unique budget precision@5 | budget hit@5 | component hit@5 | top1 budget | top1 component |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 0.4000 | 0.2000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| B | 0.4000 | 0.2000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| C | 0.4000 | 0.2000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| D | 0.4000 | 0.2000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

Interpretation:

This confirms that all retrieval branches are wired and measurable. It does not prove hybrid retrieval or reranking superiority because the corpus has only four budgets, eight component chunks, and seven clean queries plus five challenge queries.

## Metric interpretation

| Metric | Interpretation |
| --- | --- |
| result budget precision@5 | Counts every result row whose budget is relevant, including duplicate chunks from the same budget |
| unique budget precision@5 | Counts each retrieved budget once |
| budget hit@5 | Correct budget appears anywhere in top 5 |
| component hit@5 | Correct component appears anywhere in top 5 |
| top1 budget | Correct budget is rank 1 |
| top1 component | Correct component is rank 1 |

## Deterministic gates

```bash
cd /workspaces/ai-engineering/estimador-cag

uv run ruff check --fix app evals tests scripts query_examples.py streamlit_app.py
uv run ruff check app evals tests scripts query_examples.py streamlit_app.py
uv run python -m py_compile $(find app tests evals scripts -name '*.py' -type f 2>/dev/null) streamlit_app.py query_examples.py
OPENAI_API_KEY=test DEEPSEEK_API_KEY=test KIMI_API_KEY=test uv run pytest -q
```

## Streamlit retrieval UI

The Streamlit app includes a Session 10 retrieval search panel backed by `/search`.

The panel exposes:

    search_mode: Vector only or Hybrid RRF
    k: final result count
    recall_k: internal candidate pool
    client_sector, client_country, tech_stack, and scope filters

The Streamlit retrieval panel refreshes `/search/metrics` automatically after each successful search and renders the latest in-memory search metrics, including recorded searches, successes, failures, last result count, last search, and recent history.

The UI is a human review path for vector and hybrid retrieval. A/B/C/D evaluation remains runner based because reranking is intentionally measured at service level and is not exposed as a public API flag.

## Optional persisted API smoke

```bash
cd /workspaces/ai-engineering
docker compose up -d postgres redis ai_service
docker compose exec -T ai_service uv run alembic upgrade head
```

Then use `/docs` or `POST /search`.

## Real provider policy

The deterministic retrieval runner does not call providers.

For future live provider checks, prefer DeepSeek first. Use Kimi only as fallback or comparison. Do not put real provider checks in normal CI.

## Historical notes

Older Session 06, Session 07, and Session 08 material has been moved out of the front-door README and summarized in:

```text
docs/HISTORICAL_SESSIONS.md
```

The old artifacts are still intentionally preserved:

```text
evals/stress/
evals/session08_search_quality/
query_examples.py
output_examples.txt
docs/session07_*
```

## Security notes

Never commit `.env`, real API keys, screenshots with secrets, copied terminal output containing secrets, or generated cache files.

## Optional DeepSeek live comparison

The optional DeepSeek comparison is intentionally outside normal CI.

It compares:

    DeepSeek baseline prompt without retrieved context
    DeepSeek retrieval-grounded prompt using Session 10 hybrid plus reranking context

Dry-run mode is safe and makes no network calls:

    uv run python -m evals.session10_retrieval.deepseek_live_comparison --max-cases 3

Live mode requires an explicit key and flag:

    DEEPSEEK_API_KEY=... DEEPSEEK_MODEL=deepseek-v4-flash uv run python -m evals.session10_retrieval.deepseek_live_comparison --live --max-cases 3

This keeps normal CI deterministic while still providing a real provider comparison path for manual evidence.

## Reproducible Session 10 UI demo seed

The retrieval UI reads from the persisted PostgreSQL chunk store. From a clean Codespace, seed the Session 10 sample budgets before opening Streamlit:

    docker compose up -d postgres redis ai_service
    docker compose exec -T ai_service uv run alembic upgrade head
    docker compose exec -T ai_service uv run python scripts/seed_session10_demo_data.py

Dry-run mode verifies the planned sample corpus without touching the database:

    uv run python scripts/seed_session10_demo_data.py --dry-run

The script inserts one document per budget from data/budgets_sample.json and is idempotent. Re-running it skips already seeded source paths.

Browser smoke query:

    JWT authentication financial backend

Use Hybrid RRF, k=5, recall_k=8, client_country=ES, client_sector=finance, and leave tech_stack and scope empty. The expected results are BUD-2024-014 with AUTH-001 and AUDIT-001.
