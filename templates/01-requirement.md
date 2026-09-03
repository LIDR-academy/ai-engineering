# Requirement: <clear title>

> Output of the `close-requirement` skill. No open decisions may survive into this
> document. Written in English.

## Story

As a <actor>,
I want <capability>,
so that <outcome>.

## Objective

<What this enables. One paragraph.>

## Context

<The problem and why it matters now. Reference the real files or flows involved.>

## Scope

### In scope

- <item>

### Out of scope

- <item>

## Closed decisions

> One line per decision, stated as a fact, not as a preference.

- Solution shape: <extend `POST /v1/estimate` | new endpoint `<path>`>
- Layer ownership: <responsibility> lives in <ai-service | business-backend>
- Persistence: <snapshot as produced | recomputed on read>
- Backward compatibility: <existing clients keep working unchanged | breaking, /v2 required>
- Degradation on 503: <exactly what the user sees>
- Authorization: <who can see this>

## Expected behavior

- Normal: <...>
- Edge case — <name>: <...>
- Failure — <name>: <...>

## Expected output

<What is returned and in what shape. If a payload is involved, every field is listed
with its type, nullability and missing-data behaviour.>

| Field | Type | Nullable | Source of truth | If missing |
| ----- | ---- | -------- | --------------- | ---------- |
|       |      |          |                 |            |

## Success criteria

- <observable condition>
- <validation outcome>

## Open questions

- None. (If this section is not empty, the requirement is not closed.)
