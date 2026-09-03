# Verification Guide

Pick the **cheapest verification that can detect the risk this change introduces**.
Do not default to end-to-end for everything, and do not stop at unit tests when the
real success criterion is retrieval or prompt behaviour.

The agent executes these itself. Verification is never delegated to the user.

## Order of preference

1. Unit tests — pure logic, parsing, mapping, business rules.
2. Integration tests — service wiring, routers, API response shape.
3. Contract check — the routes the business backend consumes, against the live schema.
4. End-to-end — real vector DB, real LLM, real routing.
5. Manual smoke with `curl` or the browser — only to inspect live payloads.

## Where the tests live

- `ai-service/tests/` — flat `test_*.py` at the root, plus `tests/api/` (routers),
  `tests/domain/` (conductors, graph, supervisor) and `tests/generation/` (cag, rag,
  agentic). There is **no** `tests/unit`, `tests/integration` or `tests/e2e` split;
  pick the file that already covers the module you touched.
- `business-backend/test/` — **Minitest**: `controllers/`, `integration/`, `models/`,
  `services/`, `system/`.

Both suites are network-free and never call a real model.

## Quick map

### I changed pure logic, parsing or mapping in the AI service

```bash
cd ai-service && uv run pytest -q tests/test_<the_module>.py
```

### I changed a router, a schema or a repository in the AI service

```bash
cd ai-service && uv run pytest -q tests/api tests/domain
```

Then confirm the OpenAPI schema still matches expectations:

```bash
curl -s localhost:8000/openapi.json | jq '.paths."/v1/estimate/tasks/hours"'
```

### I changed the contract between layers

Run the AI service suite **and** the contract checker **and** the Rails client tests:

```bash
cd ai-service && uv run pytest -q
cd ai-service && uv run python scripts/check_contract.py
cd business-backend && bin/rails test test/services
```

`check_contract.py` validates `docs/contract/business-backend-consumed-routes.json`
against the OpenAPI schema FastAPI generates from the live Pydantic models, and also
asserts that `/health` and `/health/ready` stay token-exempt. It runs in CI. **A
contract change that only passes on one side is not verified.**

### I changed prompt behaviour, retrieval or ranking

Unit tests cannot prove retrieval quality. Use the evaluation harness against a
running service:

```bash
cd ai-service && uv run python eval/run_eval.py --base-url http://localhost:8000
cd ai-service && uv run python eval/compare_against_baseline.py
```

This spends real tokens (6 cases, ~10–20 min). The regression gate has **zero
tolerance on `safety_compliance_rate`**. For retrieval specifically there is also
`ai-service/scripts/eval_retrieval_s10.py` over the golden set.

### I changed business rules, persistence or the UI

```bash
cd business-backend && bin/rails test
```

Add `bin/rails test:system` when the change is visible in a screen.

### I changed a spec

```bash
openspec validate <change-name> --strict
openspec change show <change-name> --diff
```

`--strict` turns warnings into failures, which is what makes "a requirement must say
SHALL or MUST" an error instead of a note. `--diff` shows each MODIFIED block against the
living spec, requirement by requirement — the fastest way to catch a header that differs
only in case, or a scenario the block forgot to repeat. Both run offline and cost nothing.

### I changed a guardrail

```bash
cd ai-service && uv run pytest -q tests/generation/rag/test_guardrails_s16.py \
  tests/test_guardrails_input.py tests/test_guardrails_output.py
```

Guardrails are deterministic arithmetic on purpose: they must be provable without
spending a token.

### I changed something that runs at startup or in Docker

```bash
docker compose up --build
curl -s localhost:8000/health        # liveness, never calls the LLM
curl -s localhost:8000/health/ready  # readiness: SELECT 1 + Redis PING
```

## Linting

```bash
cd ai-service && uv run ruff check . && uv run ruff format --check .
cd business-backend && bin/rubocop && bin/brakeman
```

## Evidence

Every verification produces a record. Write it to:

```
openspec/changes/<change-name>/reports/YYYY-MM-DD-<step>-verification.md
```

with the exact commands, their output, and the state before and after. "It works" is
not evidence. A pasted command with its result is.
