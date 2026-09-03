---
name: spec-review
description: Audit a requirement, technical contract, delta spec or tasks file before implementation starts. Finds open decisions, undefined data behaviour, unverifiable acceptance criteria and missing architectural delta. Use when the user asks to review, audit, challenge or harden a spec.
author: LIDR.co · AI Engineering
version: 1.0.0
---

# Spec Review

## Purpose

Catch the defects that are cheap to fix now and expensive to fix after the agent has
written two thousand lines from them.

You are not the author. Act as an independent reviewer whose job is to find the
places where **two competent engineers would implement this differently**.

## Inputs

The change folder under `openspec/changes/<change-name>/`, or the specific files the
user names. Read the codebase to check claims — a spec that contradicts the code is a
finding, not a style opinion.

## Checks

Run all six passes. Report findings; do not silently fix.

### 1. Decision closure

Scan for behaviour-affecting ambiguity: *if needed*, *if applicable*, *when
available*, *if present*, *optional depending on*, *or*, *prefer*, *may be*, *as
needed*, *handle errors appropriately*.

For each hit: quote it, say which decision is open, and propose the two candidate
resolutions with a recommendation.

### 2. Data contract closure

For every field in every externally visible payload, verify the spec states:

- **Presence** — required or nullable
- **Source of truth** — the exact origin of the value
- **Missing-data behaviour** — `null`, `""` or `[]`, chosen explicitly
- **Transformation** — passed through as-is, or transformed by a named rule
- **No synthesis** — no field is inferred or derived unless explicitly approved

Failure condition: two valid implementations could produce different values for the
same field given the same input.

### 3. Architectural delta

The contract must name, or explicitly state as unchanged:

- routes and schemas created or modified
- services created, modified or reused
- domain modules, mappers and normalizers
- repositories and integrations
- the business backend client and its specs, when the `/v1/` contract moves
- test areas expected to change
- ownership boundaries: where each responsibility lives, and where it must not

A senior engineer must be able to approve the direction without reading the tasks.

### 4. Acceptance criteria are observable

Every scenario must be checkable by someone who did not write it. Reject
"the estimation is accurate", "performance is acceptable", "errors are handled".
Demand a `WHEN`/`THEN` pair with a concrete input and a concrete observable outcome.

### 5. Verification is real

The spec names an executable verification path from
`docs/doc-verification-guide.md`, matched to the risk of the change. Retrieval and
prompt changes verified only with unit tests is a finding. "Tests will be added" with
no named suite is a finding.

### 6. Scope and traceability

- In-scope and out-of-scope are both explicit.
- Every task maps to a requirement; every requirement maps to at least one task.
- Tasks are checkboxes with stable ids (`T<phase>.<index>`), one verifiable action
  each.
- There is an execution report template at the end of the tasks file.

## Output

```markdown
# Spec Review — <change-name>

## Verdict
READY | NEEDS WORK | NOT REVIEWABLE

## Blocking findings
### F1 · <short title> · <file>:<section>
- Quote: "<exact text>"
- Why it blocks: <the two implementations it allows>
- Proposed resolution: <closed wording, ready to paste>

## Non-blocking findings
- <same shape, shorter>

## Questions for the human
- <only decisions the reviewer cannot make>
```

## Rules

- Quote exact text. A finding without a quote is an opinion.
- Propose ready-to-paste wording for every blocking finding.
- Do not review code style. This is a spec review.
- Never mark READY while a blocking finding is open.
