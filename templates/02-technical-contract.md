# High-Level Technical Contract: <change name>

> The human approval gate. A senior engineer must be able to approve the technical
> direction from this document alone, without reading the task list.
>
> After approval, the task list may expand execution detail but may **not** introduce
> a new behaviour-affecting decision.

## Objective

<One paragraph.>

## Out of scope

- <item>

## Public contract impact

<Which endpoints change and how. State explicitly if none.>

### Request

```python
class <Name>Request(BaseModel):
    ...
```

### Response

```python
class <Name>Response(BaseModel):
    ...
```

### Field contract

Every externally visible field. No exceptions, no "illustrative only" examples.

| Field | Type | Presence | Source of truth | If data is missing | Transformation |
| ----- | ---- | -------- | --------------- | ------------------ | -------------- |
|       |      | required / nullable |        | `null` / `""` / `[]` | pass-through / <named rule> |

No field may be inferred, constructed or derived from another field unless a row
above says so explicitly.

### Error contract

| Condition | HTTP | Business backend behaviour |
| --------- | ---- | -------------------------- |
|           |      |                            |

## Backward compatibility

<Explicit statement. "Existing clients on /v1 keep working without changes because
they ignore unknown fields" — or the breaking change and its migration path.>

## Architectural Delta

Canonical section for ownership, reuse and no-change statements.

- **API** (`app/api/`): <routes and response models to create or modify>
- **Domain** (`app/domain/`): <schemas, conductor methods — or "unchanged">
- **Generation** (`app/generation/{cag,rag,agentic}/`): <exact functions to create,
  modify or reuse. Name the sibling; siblings never import each other>
- **Foundation** (`app/foundation/`): <llm, prompts, guardrails, persistence — or
  "unchanged". Changing foundation affects every session; justify it>
- **Business backend**: <client method, contract PORO, migration, view — or "unchanged">
- **Contract**: <does `docs/contract/business-backend-consumed-routes.json` change?>
- **Tests**: <exact test files expected to change>
- **Ownership**: <new responsibility> lives in <layer>; it must not live in <layer>
- **Reuse**: <existing runtime path> remains the source of truth; <new component>
  only exposes it

## Artifact inventory

Exact files and principal symbols. No behaviour decisions here — they are above.

- `ai-service/app/domain/schemas/<file>.py` or `ai-service/app/generation/rag/schemas.py` — `<Class>`
- `ai-service/app/generation/<arch>/<file>.py` — `<function>`
- `ai-service/app/domain/<conductor>.py` — `<method>` (cross-layer composition only)
- `ai-service/app/api/routers/<file>.py` — `<route>`
- `business-backend/app/services/estimator_ai/<file>_client.rb` — `<method>`
- `business-backend/app/models/rag/<file>_view.rb` — `<Class>`
- `docs/contract/business-backend-consumed-routes.json` — if a consumed route moves

## Validation strategy

By scenario and expected outcome. Exact commands belong in the task list.

| Scenario | Expected outcome | Verification level |
| -------- | ---------------- | ------------------ |
|          |                  | pytest / rails test / check_contract.py / eval harness |

## Risks

- <risk> — <why it does not block, or what mitigates it>

## Approval

- [ ] Approved by <name> on <date>
