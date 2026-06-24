# Session 08 Search Quality Evaluation

This is an offline evaluator for the Session 08 live-inspired hardening branch.

It exists to measure current `/search` behavior before changing retrieval rules.

Scope:

- No LLM judge.
- No live provider call.
- No PostgreSQL or FastAPI call.
- Evaluates captured `/search` response payloads only.
- This is not a Task 09 implementation claim.
- This does not claim benchmark superiority.

Dataset:

- `auth_jwt_finance` expects `AUTH-001`.
- `auth_token_banking` expects `AUTH-001`.
- `restaurant_negative_control` expects no true match.
- `external_integration` expects `INT-001`.
- `kubernetes_migration` expects `MIG-001`.

Metrics:

- answerable top-k hit rate
- mean best expected rank
- negative controls returning results

Interpretation:

The negative-control case intentionally records the current nearest-neighbor behavior.

A later slice may add confidence labeling or a maximum-distance threshold, but this evaluator only measures the current behavior.
