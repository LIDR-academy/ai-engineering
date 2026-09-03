---
name: close-requirement
description: Turn a rough task or idea into a decision-closed, senior-reviewable requirement by asking structured questions grounded in the existing codebase. Only draft the final artifact after every key decision is resolved and the user confirms.
author: LIDR.co · AI Engineering
version: 1.0.0
---

# Close Requirement

## Purpose

Transform a vague idea into a **decision-closed, technically clear requirement** that
a senior engineer can review and that can be used as the input for spec generation.

Do not optimize for wording. Optimize for **closed decisions**.

## Context you MUST read first

- `docs/doc-architecture.md`
- `docs/base-standards.md`
- The relevant standards file (`docs/ai-service-standards.md` or
  `docs/business-backend-standards.md`) for the layers this touches

If you cannot read them, stop and say so.

## Behavior

### 1. Understand the request

Identify in two or three lines: what the user wants, what problem it solves, what is
unclear.

### 2. Ask clarifying questions

Ask in the user's language. The goal is **not** to explore. The goal is to **force
decisions**.

- Conversational tone, as many questions as needed, no artificial limit.
- Each question resolves exactly one concrete decision.
- Prefer trade-off questions (A vs B) over open-ended ones.
- Always include a suggested default.

#### Mandatory decision dimensions

Your questions must collectively close all of these:

1. **Solution shape** — new endpoint versus extending existing behaviour.
2. **Layer ownership** — which of the two backends owns each new responsibility.
3. **Expected output** — what is returned, in what shape, to whom.
4. **Behaviour** — normal flow, edge cases, failure paths.
5. **Actor and usage context** — who uses this and why.
6. **Scope boundaries** — explicitly in and explicitly out.
7. **Success criteria** — how we will know it is correctly implemented.

For any change that touches the `/v1/` contract, also close:

8. **Backward compatibility** — do existing clients keep working, unchanged?
9. **Snapshot versus refetch** — is AI output persisted as produced, or recomputed?
10. **Degradation** — what the user sees when the AI service returns 503.

#### Code-grounded suggestions (critical)

Before proposing any default, inspect the codebase: existing routes, current request
and response shapes, existing services, naming conventions, real constraints. Ground
every suggestion in something you actually read, and name the file. A generic
suggestion when code-based evidence exists is a failure of this skill.

### 3. Iterate until closed

Incomplete answer → ask again. Ambiguous answer → ask again. Do not proceed while a
decision is open.

### 4. Confirm before writing

When everything is closed, ask — in the user's language — whether they want you to
draft the final requirement now. Do not write it yet.

### 5. Draft only after explicit confirmation

Use the template in `templates/01-requirement.md`.

## Rules

- Do not write code.
- Do not assume a missing decision.
- Do not draft while a decision is open.
- Reply in the user's language; write the artifact in English.
