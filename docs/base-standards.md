---
description: Core development rules for this repository. Applies to every AI agent (Claude, Cursor, Codex, Gemini) and every human contributor.
alwaysApply: true
---

# Base Standards

Single source of truth. Other standards documents refine this one; none of them
override it.

## 1. Core principles

- **Small tasks, one at a time.** Never run ahead of the approved plan.
- **Decision closure before code.** A requirement that allows two valid
  implementations is not a requirement yet.
- **Test-first where it pays.** New behaviour in the AI service pipeline and in
  business rules starts with a failing test.
- **Typed contracts.** Pydantic models on the AI service side; explicit contract
  POROs (`from_hash` mirroring `model_validate`) on the business backend side.
- **Incremental changes.** Prefer a focused diff over a broad refactor. Refactors
  are their own change, with their own spec.
- **Question assumptions.** State them explicitly and mark them as assumptions.
- **The repository wins.** When a spec, a template or this document disagrees with
  the code, the code is the fact and the document is the bug.

## 2. Language

All technical artifacts are in English: code, variables, functions, comments, error
and log messages, tests, commit messages, API schemas, database names and
configuration. Conversation with the user happens in the user's language.

**One deliberate exception:** the prose documentation under `docs/` is written in
**Spanish**, because students of the programme read it. The five standards documents
in this directory are the exception to the exception — they are read by the agent, so
they stay in English:

- `docs/base-standards.md` (this file)
- `docs/doc-architecture.md`
- `docs/doc-verification-guide.md`
- `docs/ai-service-standards.md`
- `docs/business-backend-standards.md`

## 3. Definition of done

A change is done when all of the following hold:

- The behaviour described in the spec is implemented, and nothing beyond it.
- Tests exist that would fail if the behaviour regressed.
- The verification path from `docs/doc-verification-guide.md` was executed by the
  agent — never delegated to the user — and its result recorded.
- Technical documentation affected by the change was updated in the same change.
- The service contract is still accurate, or was updated deliberately. When the set
  of routes the business backend consumes changes,
  `docs/contract/business-backend-consumed-routes.json` is updated in the same commit
  and `ai-service/scripts/check_contract.py` passes.

## 4. Spec-driven flow

1. `close-requirement` — turn an idea into a decision-closed requirement.
2. Explore the codebase — anchor the requirement in what already exists.
3. Propose — delta specs, technical contract, tasks.
4. Human review and approval of the contract. **Gate.**
5. Apply — implement tasks one at a time, updating checkboxes.
6. Verify — run the verification path, produce evidence.
7. Adversarial review — a different session tries to break it.
8. Archive — the delta spec merges into the capability spec.

Step 4 is the only point where a human blocks the flow. That is deliberate.

## 5. Ambiguity is a defect

These words, when they affect behaviour, make an artifact unmergeable:

*if needed*, *if applicable*, *when available*, *if present*, *optional depending on*,
*or*, *prefer*, *may be*, *as needed*, *handle errors appropriately*.

If you cannot remove the word, you have found an open decision. Ask a blocking
question instead of writing around it.

## 6. Related documents

- `docs/doc-architecture.md` — where a responsibility lives, and which contracts must
  not move by accident.
- `docs/doc-verification-guide.md` — which verification proves which change.
- `docs/ai-service-standards.md` — FastAPI conventions.
- `docs/business-backend-standards.md` — Rails conventions.
