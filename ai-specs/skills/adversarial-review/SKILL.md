---
name: adversarial-review
description: Independent red-team pass over an implemented change, before archiving. Use when the user asks for an adversarial review, red-team check, devil's advocate pass or independent verification of a finished change.
author: LIDR.co · AI Engineering
version: 1.0.0
---

# Adversarial Review

Run this in a **different session from the one that implemented the change**. An
agent reviewing its own work confirms its own assumptions.

Assume gaps exist until you have argued against them with evidence.

## Workflow

### Step 1 — Load the specification side first

Read the change artifacts (proposal, technical contract, delta specs, tasks) and
extract the acceptance criteria and the explicit non-goals. Write down what must be
true for "done". Note anything underspecified.

Read the specs **before** the diff. Reading the diff first anchors you to what was
built instead of what was asked.

### Step 2 — Load the implementation side

Use the pull request if there is one, otherwise `git diff` against the merge base.
Map each changed file to a spec section or a task. Anything changed that maps to
nothing is a finding.

### Step 3 — Try to break it

For each acceptance criterion, state how the implementation could still fail while
the author believed it passed. Work through, at minimum:

- empty and oversized inputs
- the vector DB returning zero results
- the LLM provider timing out mid-request
- a second identical request arriving before the first finishes
- a user from a different project or tier reading the result
- a field the spec said is never null arriving as null from the model
- the business backend client on the old contract version

For each: is there a test that would catch it, or only a hope?

### Step 4 — Spec versus code

Every mismatch between what the spec says and what the code does is a first-class
finding, regardless of which one you think is right.

### Step 5 — Verify the verification

Re-run the verification path yourself. Do not trust the report. If the report claims
a command was run, run it. A verification you did not observe did not happen.

## Output

```markdown
# Adversarial Review — <change-name>

## Verdict
SHIP | SHIP WITH FOLLOW-UPS | DO NOT SHIP

## Findings
### F1 · <severity: blocker | major | minor> · <file>:<line>
- What breaks: <concrete scenario, concrete input>
- Evidence: <test output, code path, missing test>
- Fix: <smallest change that closes it>

## Verification re-run
- <command> → <result>

## Spec drift
- <spec says X, code does Y>
```

## Rules

- A finding needs a concrete failing scenario. "This could be risky" is not a finding.
- Do not rewrite the code. Report and let the implementer fix.
- Calibrate depth to risk: auth, data mutation, cross-project access and cost get
  stricter scrutiny than copy changes.
