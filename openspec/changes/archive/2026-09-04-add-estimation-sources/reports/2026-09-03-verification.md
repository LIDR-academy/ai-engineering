# Verification — add-estimation-sources — 2026-09-03

Executed by the implementing agent, per `docs/doc-verification-guide.md`
("I changed business rules, persistence or the UI" → `bin/rails test`; "I changed a
generation-layer conductor" → `uv run pytest`).

> **This report supersedes the pre-review verification** (sections 0-2 of `tasks.md`,
> `business-backend` only). This run covers the full scope after the adversarial-review
> findings were folded in: both `ai-service` and `business-backend`.

## State before this verification pass

- Branch `feature/add-estimation-sources`, sections 0-2 of `tasks.md` already implemented
  and independently re-verified during the adversarial review (`bin/rails test`: 220
  runs, 882 assertions, 0 failures).
- Sections 3-5 (this pass) implemented via TDD: each failing test was run and shown red
  before its implementation, then green after. See `tasks.md` for the task-by-task
  failing→green pairs; this report covers the aggregate verification (task 6).

## Commands and output

### 1. `ai-service` full test suite (task 6.1)

```
$ cd ai-service && uv run pytest
================= 715 passed, 3 warnings in 543.83s (0:09:03) ==================
```

The 543.83s runtime matches a known, documented local-environment characteristic (not a
regression from this change): `CLAUDE.md` — Session 15 notes that without a reachable
pgvector service container, five lifespan-entering test modules each stall on the
connection-pool timeout ("measured: ~9 min without it, ~20 s with"). The 9-minute mark
here is that exact stall, not a hang caused by this change's edits.

The scope this change touches, run in isolation first (before the full run, so a failure
would be attributable without waiting 9 minutes):

```
$ uv run pytest tests/generation/agentic tests/domain tests/generation/rag/test_schemas.py -v
156 passed, 3 warnings in 0.78s
```

Covers: `TaskNeighbor.source_id` optionality (2 tests), `derive_task_hours` echoing its
neighbors + the summary-string safety property (2 tests), the recovery loop capturing
`AgentTaskDerivation.neighbors` (1 assertion added to an existing test), and the
conductor's merge carrying those neighbors onto the response
(`test_hybrid_recovered_task_carries_its_analogs`, 1 new test) — plus the full pre-existing
suites for those three modules, unbroken.

### 2. `ai-service` lint (task 6.2)

```
$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
69 files would be reformatted, 271 files already formatted
```

The 69 files are pre-existing formatting debt unrelated to this change (none of them are
files this change touches — confirmed by re-running `ruff format --check` scoped to just
the 9 files this change edited/added, all 9 already formatted after `ruff format` was run
on them once). Verified no unintended reformatting side effects by re-running the section-3
test scope after formatting — still 156 passed.

### 3. `ai-service` contract check (task 6.3)

```
$ uv run python scripts/check_contract.py
Contract OK -- 34 checks passed (32 consumed routes).
```

Confirms `proposal.md`'s claim: the pinned route contract (`{client, method, path}`) is
unaffected by this change's Pydantic response-field edits (`TaskNeighbor.source_id`
optionality, `AgentTaskDerivation.neighbors`).

### 4. `business-backend` full test suite (task 6.4)

```
$ cd business-backend && bin/rails test
220 runs, 885 assertions, 0 failures, 0 errors, 0 skips
```

Baseline before section 4-5 edits: 220 runs, 882 assertions (matches the pre-review
figure). The +3 assertions come from the tightened/expanded controller test (F2 fix:
`assert_select` in place of two ambiguous `assert_match`s, plus the new agent-recovered
and no-detail-label assertions; net across removed/added assertions in that one test
method is +3). No regression outside the touched files.

### 5. `business-backend` lint (task 6.5)

```
$ bin/rubocop app/models/rag/estimation_run.rb app/controllers/rag/estimation_runs_controller.rb \
    test/models/rag/estimation_run_test.rb test/controllers/rag/estimation_runs_controller_test.rb
4 files inspected, no offenses detected
```

`.erb` excluded from this command as before — no `erb_lint`/RuboCop `.erb` config in this
repo; `bin/rubocop` parses `.erb` as raw Ruby and produces ~160 false `Lint/Syntax`
offenses.

### 6. Spec scenarios exercised

Per `specs/rag/task-hours-explainability/spec.md` (4 requirements, 9 scenarios):

| Scenario | Exercised by |
| --- | --- |
| Task with historical matches | `RagEstimationRunsControllerTest` — OAuth (`assert_select "li", text: /40 h · 90% cercanía/`) |
| Contradicted consensus still shows its evidence | Same test — SSO, both analogs asserted individually (F2 fix: no longer a substring collision with reliability badges) |
| **Task grounded by the recovery agent** | Same test — "SSO Recovered" fixture, `has_match: true` + non-empty `neighbors` (the exact shape the `ai-service` fix now produces), asserts its analog renders |
| Task with no historical match | Same test — RBAC, `assert_match "sin análogo histórico"` |
| **Stored result carries no analog detail** | Same test — MFA (`has_match: true`, no `neighbors` key), `assert_match "sin detalle de análogos"` |
| **The unavailable-detail indication is distinguishable** | Same test — asserts the two message strings are not equal; visually distinct CSS classes (`text-danger/70` red vs `text-white/30 italic` muted) |
| **Agent-recovered task in the response** | `ai-service`: `tests/domain/test_agent_estimation.py::test_hybrid_recovered_task_carries_its_analogs` |
| **Analog with no known source identifier** | `ai-service`: same test, second neighbor has `source_id=None`; also `tests/generation/rag/test_schemas.py::test_task_neighbor_source_id_is_optional` |
| **Agent could not ground the task** | `ai-service`: pre-existing `test_hybrid_keeps_deterministic_when_agent_finds_nothing`, unaffected by this change's edits — still green |

Bold rows are new or materially changed by the adversarial-review findings.

### 7. F2 fix verified to actually discriminate (task 5.2)

The tightened controller-test assertions were confirmed to fail when the analog block is
neutralized (`task_neighbors` forced to `[]` in a throwaway edit), then confirmed to pass
again with the real view restored:

```
# with task_neighbors forced to []
Failure: Expected: /40 h · 90% cercanía/  Actual: "1Reformulación →". Expected 0 to be >= 1.

# with the real view restored
20 runs, 117 assertions, 0 failures, 0 errors, 0 skips
```

This closes the gap the review found: the old `assert_match "80%"` / `"70%"` would have
passed in the neutralized case too, because those substrings also come from unrelated
reliability badges (`80% fiab.`, `70% fiab.`) elsewhere on the same page.

### 8. Safety property: the agent's observation is unchanged (design.md risk mitigation)

```
$ uv run pytest tests/generation/agentic/test_agent_tools.py::test_derive_task_hours_summary_unaffected_by_the_echoed_neighbors -v
PASSED
```

Confirms `result["summary"]` — the only thing the agent loop observes
(`agent_loop.py:292`, `result.get("summary") or result.get("error") or ...`) — is
unchanged by adding the `neighbors` key to `derive_task_hours`'s return value. No context
growth, no token cost, no behavioural drift in a live agent path.

## State after

```
$ git status --short
 M business-backend/app/models/rag/estimation_run.rb
 M business-backend/app/views/rag/estimation_runs/_step_hours.html.erb
 M business-backend/test/controllers/rag/estimation_runs_controller_test.rb
 M business-backend/test/models/rag/estimation_run_test.rb
 M ai-service/app/domain/agent_estimation.py
 M ai-service/app/generation/agentic/agent_loop.py
 M ai-service/app/generation/agentic/agent_schemas.py
 M ai-service/app/generation/agentic/agent_tools.py
 M ai-service/app/generation/rag/schemas.py
 M ai-service/tests/domain/test_agent_estimation.py
 M ai-service/tests/generation/agentic/test_agent_loop.py
 M ai-service/tests/generation/agentic/test_agent_tools.py
?? ai-service/tests/generation/rag/test_schemas.py
?? openspec/changes/add-estimation-sources/
```

Matches `tasks.md` — "Files changed" (pre-review four Rails files, plus the five
`ai-service` files and one new `ai-service` test file from sections 3-5), plus this
change's own planning folder.

## Deviations from `tasks.md` as originally written

Carried over from the pre-review report (still applicable):

1. **Task 0.1 - branch base.** Branched from `lab/00-start` instead of `main`, to keep the
   Session 17 SDD kit on the working branch. No product-code risk.
2. **Task 3.2 (original numbering) - rubocop file list.** `.erb` dropped from the rubocop
   command — no `erb_lint`/RuboCop `.erb` config in this repo.

New in this pass:

3. **Task 6.1 runtime.** The full `ai-service` suite took ~9 minutes locally due to the
   documented pgvector-service-container stall (`CLAUDE.md`, Session 15). Not a regression;
   confirmed by running the change's own scope (156 tests) in isolation first, in 0.78s.
