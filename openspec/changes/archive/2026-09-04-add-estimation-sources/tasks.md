# Tasks — add-estimation-sources

> Execution plan for the implementing agent. Every actionable item is a checkbox and
> represents one verifiable action.
>
> **Sections 0-2 were completed before the adversarial review** and stay checked; their
> code is in the working tree. Sections 3-5 are the review's findings folded in, and
> section 6 (verification) is **reset** — the earlier run no longer covers the scope.

## 0. Setup

- [x] 0.1 Create branch `feature/add-estimation-sources` and verify the working tree is
      clean
- [x] 0.2 Confirm `business-backend` boots and the RAG wizard's `hours` step renders for
      an existing run; manual check

## 1. Model — the module/task -> neighbors lookup (TDD)

- [x] 1.1 Failing test in `test/models/rag/estimation_run_test.rb` for
      `Rag::EstimationRun#task_hours_neighbors_by_task`
- [x] 1.2 Implement `task_hours_neighbors_by_task` in `app/models/rag/estimation_run.rb`
- [x] 1.3 Run `bin/rails test test/models/rag/estimation_run_test.rb` — green

## 2. View — render the analog block per task (TDD)

- [x] 2.1 Failing `assert_select` assertions in
      `test/controllers/rag/estimation_runs_controller_test.rb`
- [x] 2.2 Render the analog block in `_step_hours.html.erb`
- [x] 2.3 Run `bin/rails test test/controllers/rag/estimation_runs_controller_test.rb` —
      green

## 3. ai-service — carry the recovery agent's analogs (TDD)

- [x] 3.1 Make `TaskNeighbor.source_id` optional (`int | None = None`) in
      `ai-service/app/generation/rag/schemas.py`; add a test that a `TaskNeighbor` with
      no `source_id` validates and serializes
- [x] 3.2 Add a failing test in `ai-service/tests/generation/agentic/` asserting that
      `derive_task_hours` returns the neighbors it was given (not only their count), and
      a test asserting the **observation string is unchanged** — i.e. the value of
      `result["summary"]` is what the loop observes, so the added key never reaches the
      model
- [x] 3.3 Echo the validated neighbors in the dict returned by
      `app/generation/agentic/agent_tools.py::derive_task_hours`
- [x] 3.4 Add `neighbors: list[DeriveTaskHoursNeighbor] = Field(default_factory=list)` to
      `AgentTaskDerivation` (`app/generation/agentic/agent_schemas.py`) and populate it at
      the capture point in `app/generation/agentic/agent_loop.py`
- [x] 3.5 Add a failing test in `ai-service/tests/domain/` for the merge: given a base
      estimate with `has_match=False` and an agent derivation carrying neighbors, the
      merged `TaskHoursEstimate` has `has_match=True` **and** a non-empty `neighbors`
      list; given a derivation the agent could not ground, the task stays unmatched
- [x] 3.6 Carry `neighbors` into the `model_copy(update=...)` in
      `app/domain/agent_estimation.py`, mapping `DeriveTaskHoursNeighbor` ->
      `TaskNeighbor` **in this conductor module** (not in `generation/agentic`, which may
      not import `generation/rag` — see `design.md`)
- [x] 3.7 Run `cd ai-service && uv run pytest tests/generation/agentic tests/domain -v` —
      expect green (154 passed)

## 4. business-backend — label the unavailable-detail state (TDD)

- [x] 4.1 Failing controller-test assertion: a matched task whose stored payload carries
      no `neighbors` renders a distinct "sin detalle de análogos" indication, and it is
      distinguishable from the unmatched "sin análogo histórico" message
- [x] 4.2 Render that indication in `_step_hours.html.erb` (muted, visually distinct from
      the red unmatched message); the unmatched branch keeps priority
- [x] 4.3 Add a regression test for the review's F1: a payload shaped like an
      agent-recovered task (`has_match: true` with neighbors present) renders its analogs
- [x] 4.4 Run `bin/rails test test/controllers/rag/estimation_runs_controller_test.rb` —
      green (20 runs, 117 assertions)

## 5. business-backend — close the F2 assertion gap

- [x] 5.1 Replace the ambiguous `assert_match "80%"` / `assert_match "70%"` in the
      contradicted-consensus scenario with assertions on text unique to an analog row
      (e.g. `assert_select "li", text: /40 h · 80% cercanía/` and `/80 h · 70% cercanía/`).
      Rationale: measured on the real fixture, `90%` occurs once but `80%` and `70%` occur
      twice each — the reliability badges `80% fiab.` (OAuth) and `70% fiab.` (MFA)
      independently satisfy the old assertions, so the scenario was not actually tested
- [x] 5.2 Verify the tightened assertions fail when the analog block is removed, then
      pass with it restored — a test that cannot fail is not a test. Done by temporarily
      neutralizing `task_neighbors` in the view to `[]`, confirming the `40 h · 90%
      cercanía` assertion fails, then restoring the real view and confirming green again

## 6. Verification (MANDATORY — executed by the agent, never the user; RESET)

- [x] 6.1 `cd ai-service && uv run pytest` — expect green, no regression. **715 passed**
      in 543.83s (~9 min, matching the documented pgvector-service-container stall in
      `CLAUDE.md` Session 15 — not a regression). The change's own scope
      (`tests/generation/agentic tests/domain tests/generation/rag/test_schemas.py`) was
      also run in isolation first: 156 passed in 0.78s
- [x] 6.2 `cd ai-service && uv run ruff check . && uv run ruff format --check .` — clean
      on this change's 9 touched/added files (`ruff check`: all pass repo-wide; `ruff
      format`: 69 pre-existing files elsewhere have unrelated formatting debt, none of
      them touched by this change)
- [x] 6.3 `cd ai-service && uv run python scripts/check_contract.py` — **pass**, 34
      checks / 32 consumed routes; the pinned route contract is unaffected
- [x] 6.4 `cd business-backend && bin/rails test` — **220 runs, 885 assertions, 0
      failures**. Baseline before section 4-5: 220 runs, 882 assertions
- [x] 6.5 `cd business-backend && bin/rubocop app/models/rag/estimation_run.rb app/controllers/rag/estimation_runs_controller.rb test/models/rag/estimation_run_test.rb test/controllers/rag/estimation_runs_controller_test.rb`
      — **4 files inspected, no offenses detected** (`.erb` excluded: no `erb_lint`/
      RuboCop `.erb` config in this repo)
- [x] 6.6 Wrote `openspec/changes/add-estimation-sources/reports/2026-09-03-verification.md`
      with the exact commands, their output, and a scenario-by-scenario mapping of all 9
      spec scenarios to the tests that exercise them — including the agent-recovered and
      no-detail cases
- [x] 6.7 Updated `guides/session-17-live-guide.md` (~line 433, "Hallazgos"): noted the
      discard happens **twice** and the second one is in `ai-service`, so the "exponer,
      no calcular" framing holds but the "dos horas" sizing does not. Local edit only —
      `guides/` is git-ignored, never committed

## Risks

- The `[module_name, task_name]` string-key join can miss if a task was renamed between
  the `review` and `hours` steps — an existing, accepted risk shared with
  `seed_breakdown_with_hours`. It now degrades into the **labelled** no-detail state
  rather than into silence.
- Section 3 edits a live agent path. The mitigation is task 3.2: the observation string
  the model sees must be provably unchanged.

## Rollback

Revert the `business-backend` and `ai-service` commits. No data migration, no schema
migration to undo. The two layers are independently deployable in either order (see
`design.md` - Migration Plan).

---

## Execution Report (completed by the implementing agent)

### Summary

- Total execution tasks: 27
- Completed: 27
- Blocked: 0
- Skipped: 0
- Remaining: 0

### Task status

- [x] 0.1 · [x] 0.2
- [x] 1.1 · [x] 1.2 · [x] 1.3
- [x] 2.1 · [x] 2.2 · [x] 2.3
- [x] 3.1 · [x] 3.2 · [x] 3.3 · [x] 3.4 · [x] 3.5 · [x] 3.6 · [x] 3.7
- [x] 4.1 · [x] 4.2 · [x] 4.3 · [x] 4.4
- [x] 5.1 · [x] 5.2
- [x] 6.1 · [x] 6.2 · [x] 6.3 · [x] 6.4 · [x] 6.5 · [x] 6.6 · [x] 6.7

### Validation executed

- [x] Pre-review: `bin/rails test` → 220 runs, 882 assertions, 0 failures
- [x] Post-review: `cd ai-service && uv run pytest` → 715 passed, 0 failures (543.83s;
      the runtime is a documented local-environment characteristic, see `tasks.md` 6.1)
- [x] Post-review: `cd ai-service && uv run ruff check .` → all checks passed
- [x] Post-review: `cd ai-service && uv run python scripts/check_contract.py` → 34
      checks passed, 32 consumed routes
- [x] Post-review: `cd business-backend && bin/rails test` → 220 runs, 885 assertions,
      0 failures
- [x] Post-review: `cd business-backend && bin/rubocop <4 files>` → no offenses
- [x] F2 fix verified to discriminate: tightened assertions shown to fail against a
      neutralized view, then pass against the real one (see the verification report,
      "7. F2 fix verified to actually discriminate")
- [x] Safety property verified: the agent's observed `summary` string is unchanged by
      the new `neighbors` key (see the verification report, section 8)

### Blockers

- None

### Files changed

`business-backend` (sections 1-2, pre-review; section 4-5, post-review):

- `business-backend/app/models/rag/estimation_run.rb`
- `business-backend/app/views/rag/estimation_runs/_step_hours.html.erb`
- `business-backend/test/models/rag/estimation_run_test.rb`
- `business-backend/test/controllers/rag/estimation_runs_controller_test.rb`

`ai-service` (section 3, post-review):

- `ai-service/app/generation/rag/schemas.py`
- `ai-service/app/generation/agentic/agent_tools.py`
- `ai-service/app/generation/agentic/agent_schemas.py`
- `ai-service/app/generation/agentic/agent_loop.py`
- `ai-service/app/domain/agent_estimation.py`
- `ai-service/tests/generation/agentic/test_agent_tools.py`
- `ai-service/tests/generation/agentic/test_agent_loop.py`
- `ai-service/tests/domain/test_agent_estimation.py`
- `ai-service/tests/generation/rag/test_schemas.py` (new)

Local-only, not committed (`guides/` is git-ignored):

- `guides/session-17-live-guide.md`

### Final statement

- [x] All non-blocked tasks completed
- [x] All required validations executed by the agent
- [x] Optional validations executed or explicitly marked `[SKIPPED]` with the reason —
      none skipped
- [x] No behaviour beyond the approved technical contract was introduced — scope matched
      `requirement.md`, `design.md` and the two review findings (F1, F2) exactly; no
      LLM-facing tool-schema change, no new endpoint, no `docs/contract/...` change
