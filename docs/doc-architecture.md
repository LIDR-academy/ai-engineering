# Architecture Guide

Canonical reference for deciding **where a new file belongs**, **who owns a
responsibility**, and **which contracts must not change by accident**.

This document is the **decision index**. It is deliberately short. When you need the
full contract of a layer, follow the link — do not re-derive it here:

| For the detail of… | Read |
| ------------------ | ---- |
| The AI service layer cake and its MUST/MUST NOT dependency rules | `ai-service/ARCHITECTURE.md` |
| The business backend contexts and its client boundary | `business-backend/ARCHITECTURE.md` |
| The public/private boundary, the two auth layers, error codes | `docs/architecture.md` (Spanish) |
| Which routes the business backend actually consumes | `docs/contract/business-backend-consumed-routes.json` |

## Deployed topology

```
[ User ]
    |  HTTPS (public)
    v
+---------------------------------+
|  Frontend + business backend    |   Ruby on Rails 8
+---------------------------------+
    |                       |  HTTP, private network, X-Service-Token
    v                       v
+---------------+   +---------------------------------+
| postgres      |   |  ai-service (CAG/RAG + agents)   |   Python + FastAPI
| (relational)  |   +---------------------------------+
+---------------+                   |
                                    v
                        +---------------------------+
                        |  vector-db (pgvector)     |
                        +---------------------------+
```

Only `business-backend` publishes ports. The AI service and both datastores live on
the private compose network. There are **two** PostgreSQL instances on purpose:
`vector-db` (pgvector, owned by the AI service) and `postgres` (owned by Rails).
Neither reads the other's data.

## Ownership boundaries

| Concern                                    | Owner              |
| ------------------------------------------ | ------------------ |
| Users, sessions, authorization, tiers      | business backend   |
| Persistence of estimates and their history | business backend   |
| UI and presentation                        | business backend   |
| Prompt construction and rendering          | AI service         |
| Retrieval, ranking, reranking              | AI service         |
| LLM invocation, retries, fallback          | AI service         |
| Vector DB access                           | AI service         |
| Interpreting a domain result for a user    | business backend   |

The business backend never talks to the vector DB or to an LLM provider directly.
**The AI service never reads the relational DB and knows nothing about users** — it
has no notion of user, project or tenant anywhere in its code or in its corpus.
Anything that depends on *who is asking* is the business backend's responsibility, or
must be passed in explicitly and enforced inside the retrieval query.

## AI service layout (`ai-service/`)

Five layers. Each may import only from the layers above it. Full table of rules in
`ai-service/ARCHITECTURE.md` §3.

- `app/foundation/` — plumbing with no AI-architecture opinion: `llm/` (LLMWrapper over
  LiteLLM + Instructor), `prompts/` (versioned Jinja2), `guardrails/` (input/output),
  `attachments/`, `persistence/`. Imports only `config`.
- `app/domain/` — the contract and the conductors: `schemas/` (the Pydantic contract
  with Rails), `estimation_service.py` (the fixed pipeline), `graph/` (the LangGraph
  and supervisor flows).
- `app/generation/` — the three AI architectures: `cag/`, `rag/`, `agentic/`, plus
  `conversation/`. **A generation sibling never imports another generation sibling**;
  they meet only inside a conductor in `domain/`.
- `app/ingestion/` — the offline batch pipeline that feeds RAG.
- `app/api/` — transport only: thin routers, error mapping. No business logic.
- `app/config.py`, `app/dependencies.py`, `app/main.py` — composition root, above the
  layers; `dependencies.py` may import anything.
- `tests/` — flat `test_*.py` at the root plus `tests/api/`, `tests/domain/`,
  `tests/generation/`. Run with `uv run pytest`.

Business logic never lives in a route. A route validates input with a Pydantic model,
calls one service or conductor, and maps failures to HTTP statuses.

## Business backend layout (`business-backend/`)

Organized by contexts mirroring the programme's modules — `estimation`, `conversation`,
`rag`, `agents`. Contexts never import each other.

- `app/models/` — ActiveRecord roots plus **contract POROs** that mirror the Pydantic
  schemas 1:1 (`from_hash` ↔ `model_validate`), e.g. `app/models/rag/`.
- `app/services/estimator_ai/` — **the only layer that speaks HTTP to the AI service.**
  `base_client.rb` owns the connections, the default headers (including
  `X-Service-Token`) and the response → typed-error mapping; one client per context
  inherits from it (`estimations_client.rb`, `rag_estimate_client.rb`,
  `sessions_client.rb`, `embeddings_client.rb`, `eval_client.rb`, …). Nothing else in
  the app may call the AI service directly.
- `app/services/rag/` — use cases that coordinate models and the AI clients.
- `app/controllers/`, `app/views/` — transport and presentation only.
- `test/` — **Minitest**, run with `bin/rails test`.

## The contract between layers

Every route the business backend consumes is listed in
`docs/contract/business-backend-consumed-routes.json` (32 routes) and validated in CI
by `ai-service/scripts/check_contract.py` against the OpenAPI schema FastAPI generates
from the live Pydantic models. **A contract change that does not update that file
fails the pipeline.**

Two URL prefixes coexist, and this is not an accident to be tidied away:
`/api/v1/*` (the Session 4 CAG estimate, sessions, ingestion, config) and `/v1/*`
(the Session 9+ RAG and graph routes, each protected by its own `X-API-Key`).

Example — per-task hours, the route that grounds each task in historical analogs:

```python
# ai-service/app/generation/rag/schemas.py (extract)
class TaskNeighbor(BaseModel):
    """One historical task that matched the query task, for transparency."""

    source_id: int
    budget_id: str | None = None
    estimated_hours: int
    distance: float          # cosine distance; lower = closer


class TaskHoursResult(BaseModel):
    tasks: list[TaskHoursEstimate] = Field(default_factory=list)
    requires_human_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
```

```ruby
# business-backend/app/services/estimator_ai/rag_estimate_client.rb (extract)
def estimate_task_hours(modules:)
  handle_response(json_conn.post("/v1/estimate/tasks/hours", { modules: modules }))
end
```

`BaseClient#handle_response` maps status to the shared taxonomy in
`EstimatorAi`: `400` → `GuardrailViolation` / `InvalidRequest`, `401` →
`Unauthorized`, `404` → `SessionNotFound`, `409` → `Conflict`, `415`/`422` →
`InvalidRequest`, `429` → `RateLimited` (carrying `Retry-After`), `503` →
`ServiceUnavailable`, `500`/`502` and anything unexpected → `ServerError`.

Contract rules:

- **Version stays where it is.** Breaking changes create a new prefix and coexist;
  they never mutate an existing one in place.
- **Error codes are contract**, not an implementation detail: `400` input rejected by
  a guardrail, `401` bad service token or API key, `422` payload fails Pydantic
  validation, `429` per-key rate limit, `502` the LLM failed, `503` a dependency
  (vector DB, Redis, embedder) is unavailable. A genuine bug stays `500`.
- Adding a field to a response is backward compatible **because** the Rails contract
  POROs parse with explicit keys (`.slice(...)` over named keys) and ignore unknown
  ones. State this explicitly in the technical contract anyway — it is a property to
  be verified, not assumed.
- Any change to a consumed route requires updating
  `docs/contract/business-backend-consumed-routes.json` in the same change.
