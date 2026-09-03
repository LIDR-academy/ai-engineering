# AI Service Standards (Python + FastAPI)

Refines `docs/base-standards.md` for `ai-service/`. The dependency rules are stated
normatively in `ai-service/ARCHITECTURE.md`; this file is the day-to-day summary.

## Layering

Five layers, each importing only from the ones above: `foundation/` → `domain/` →
`generation/` → `ingestion/` → `api/`, with `config.py` / `dependencies.py` /
`main.py` as the composition root above them all.

A router does three things and nothing else: validate input with a Pydantic model,
call one service or conductor, map the result and the failures to HTTP. Orchestration
lives in a **conductor** — `app/domain/estimation_service.py` for the fixed pipeline,
`app/domain/graph/` for the LangGraph and supervisor flows. Pure transformations live
in `app/domain/` and perform no I/O. SDK access lives in `app/foundation/` (`llm/`,
`persistence/`).

Two rules that are easy to break and expensive to unbreak:

- **A `generation/` sibling never imports another `generation/` sibling.** `cag/`,
  `rag/` and `agentic/` meet only inside a conductor in `domain/`. (The one sanctioned
  exception: `agentic` may import `conversation`.)
- If you are tempted to put a `try/except` around an LLM call inside a router, the
  code is in the wrong layer.

New cross-layer composition goes in the conductor, never in a router and never via a
sibling import. **Nothing in CI enforces this** — the rules live in
`ai-service/ARCHITECTURE.md` and are upheld by review. Treat a violation found during
a spec review as a blocking finding, not a style note.

## Schemas

- Request and response models are explicit Pydantic classes under
  `app/domain/schemas/` (the contract with Rails) or, for the RAG surface, in
  `app/generation/rag/schemas.py`. No bare `dict`.
- Every field declares its type and whether it is nullable.
- A field that can be absent is modelled with an explicit default, and the technical
  contract states what "absent" means.
- **Lists are never `None`.** An empty result is `[]`.
- Adding a field with a default is backward compatible; the technical contract still
  has to say so explicitly.
- **Field order matters with Instructor.** Declare the parts before the total that
  sums them: the model emits autoregressively, so `phases` before `total_cost_eur` is
  the difference between consistent arithmetic and failures on smaller models.

## Errors

Use typed domain errors, translated to HTTP once, at the router boundary.
The hierarchy lives in `app/generation/rag/errors.py`:

```python
class RagError(Exception): ...
class ReformulationError(RagError): ...
class RetrievalError(RagError): ...
class GenerationError(RagError): ...
class CitationValidationError(RagError): ...
class MalformedEstimateError(RagError): ...
```

plus `InputGuardrailViolation` (`app/foundation/guardrails/input.py`) and
`PrivilegeViolation` (`app/domain/graph/supervisor/privilege.py`).

| Condition                                   | HTTP | Meaning for the business backend        |
| ------------------------------------------- | ---- | --------------------------------------- |
| `InputGuardrailViolation`                   | 400  | Input rejected by policy. Do not retry. |
| Missing/bad `X-Service-Token` or `X-API-Key`| 401  | Configuration problem. Do not retry.    |
| Pydantic validation failure                 | 422  | The request is wrong. Do not retry.     |
| Per-key rate limit                          | 429  | Back off; honour `Retry-After`.         |
| Upstream LLM failure                        | 502  | Retry later.                            |
| `RetrievalError`, embedder or Redis down    | 503  | Degrade gracefully, retry later.        |
| A genuine bug                               | 500  | Fix it.                                 |

**503 means "a dependency is unavailable", not "something went wrong."** Never return
a 200 with an error message inside the payload.

## Guardrails

A guardrail is **code, not a sentence in a prompt**. Prefer deterministic arithmetic
(`app/foundation/guardrails/estimate_bounds.py`) over an instruction to the model: it
runs always, survives a change of provider, and can be tested in CI without spending a
token. Output guardrails **mark, they do not reject** — an implausible result comes
back with `requires_human_review` plus `review_reasons`, and a person decides.

## Prompts

Prompt templates live in versioned Jinja2 files under
`app/foundation/prompts/` — never inline in Python strings. Changing a prompt is a
behaviour change: it needs a spec, an acceptance criterion and an end-to-end
verification, not a single eyeball test.

## Configuration

`Settings` is a cached singleton (`app/config.py::get_settings`, `@lru_cache`), so a
`.env` change needs a container recreate, not a reload. Tunables that must change
mid-session go through the Redis-backed runtime config
(`app/foundation/llm/runtime_config.py` + `PUT /api/v1/config/*`), never through a
`.env` round-trip.

## Observability

Logging is `structlog` (`structlog.get_logger()`), never stdlib `logging`. JSON in
production, console in development. Every request carries an `X-Request-ID`
correlation header set by middleware in `app/main.py`; per-stage timings go through
`log_stage`. Never log a full prompt or user content at info level.

## Testing

- Tests are **network-free**. The LLM and the vector DB are always doubled.
- Run with `uv run pytest`. Layout: flat `tests/test_*.py` plus `tests/api/`,
  `tests/domain/`, `tests/generation/`.
- CI never calls the real model. The only thing that spends tokens is the evaluation
  harness (`eval/`), and it is not in the test suite.
