# Tasks — <change name>

> Execution plan for the implementing agent. Every actionable item is a checkbox with
> a stable id `T<phase>.<index>` and represents **one verifiable action**.
> Objectives, risks and rollback notes never get checkboxes.

## 0. Setup (first, always)

- [ ] T0.1 Create branch `feature/<change-name>` from `main`
- [ ] T0.2 Confirm the working tree is clean and both services start

## 1. AI service — contract (TDD)

- [ ] T1.1 Add failing test for the `<Class>` field contract in `ai-service/tests/<file>.py`
- [ ] T1.2 Add `<Class>` to `ai-service/app/domain/schemas/<file>.py` (or `app/generation/rag/schemas.py`)
- [ ] T1.3 Run `cd ai-service && uv run pytest -q tests/<file>.py` — expect green

## 2. AI service — behaviour (TDD)

- [ ] T2.1 Add failing test for the empty-retrieval path
- [ ] T2.2 Add failing test for the vector-store-unavailable path (503, not 500)
- [ ] T2.3 Implement `<function>` in `app/generation/<arch>/<file>.py`
- [ ] T2.4 Run `cd ai-service && uv run pytest -q tests/generation` — expect green

## 3. AI service — route

- [ ] T3.1 Wire the route in `app/api/routers/<file>.py`, transport only
- [ ] T3.2 Run `cd ai-service && uv run pytest -q tests/api` — expect green
- [ ] T3.3 Update `docs/contract/business-backend-consumed-routes.json` if a consumed route moved
- [ ] T3.4 Run `cd ai-service && uv run python scripts/check_contract.py` — expect green

## 4. Business backend — client and product behaviour

- [ ] T4.1 Update `app/services/estimator_ai/<file>_client.rb` and the contract PORO
- [ ] T4.2 Implement the 503 degradation exactly as specified
- [ ] T4.3 Run `cd business-backend && bin/rails test` — expect green

## 5. Verification (MANDATORY — the agent executes these, never the user)

- [ ] T5.1 Capture pre-test state for affected records
- [ ] T5.2 Run the verification path named in the technical contract
- [ ] T5.3 Execute the manual `curl` check and restore state afterwards
- [ ] T5.4 Verify post-test state matches pre-test state
- [ ] T5.5 Write `openspec/changes/<change-name>/reports/YYYY-MM-DD-verification.md`

## 6. Documentation

- [ ] T6.1 Update `docs/doc-architecture.md` if the contract moved
- [ ] T6.2 Update the API examples if request or response shape changed
- [ ] T6.3 Run `cd ai-service && uv run ruff check .` and `cd business-backend && bin/rubocop`

## Risks

- <risk and mitigation>

## Rollback

<One sentence.>

---

## Execution Report (completed by the implementing agent)

### Summary

- Total execution tasks: <n>
- Completed: <n>
- Blocked: <n>
- Skipped: <n>

### Task status

- [ ] T0.1
- [ ] T1.1

### Validation executed

- [ ] `<exact command>` → <result>

### Blockers

- None

### Files changed

- `<file>`

### Final statement

- [ ] All non-blocked tasks completed
- [ ] All required validations executed by the agent
- [ ] Optional validations executed or explicitly marked `[SKIPPED]` with the reason
- [ ] No behaviour beyond the approved technical contract was introduced
