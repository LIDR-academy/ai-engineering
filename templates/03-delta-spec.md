# Delta Spec — <capability name>

> Lives in `openspec/changes/<change-name>/specs/<capability-path>/spec.md`.
> The file MUST be named `spec.md` and MUST sit under a capability directory — a file
> at `specs/spec.md` is ignored by the merge.
>
> **A delta spec is not a spec. It is a diff.** It describes only what this change adds,
> modifies, removes or renames, and it is applied against the living spec of the
> capability at `openspec/specs/<capability-path>/spec.md`. After the merge the living
> spec carries no delta headers: everything is flattened into one `## Requirements`
> section.
>
> Four operations exist, applied in this order:
> `RENAMED` → `REMOVED` → `MODIFIED` → `ADDED`. Plain Markdown, no special syntax.

## ADDED Requirements

### Requirement: <name>

The system SHALL <requirement statement, single sentence, testable>.

#### Scenario: <what the actor does>

- **WHEN** <concrete precondition and input>
- **THEN** <concrete observable outcome>

#### Scenario: <edge case>

- **WHEN** <concrete precondition and input>
- **THEN** <concrete observable outcome>

#### Scenario: <failure path>

- **WHEN** <the dependency that fails>
- **THEN** <the exact status code and the exact user-visible behaviour>

## MODIFIED Requirements

> **A MODIFIED block REPLACES the whole requirement — it does not patch it.**
> Copy the header **verbatim** from the living spec (matching is case-sensitive) and
> repeat **every** scenario the requirement already has, including the ones you are not
> changing. Drop one and the archive **aborts** with
> `current spec contains scenario(s) not present in the modified block`. It does not
> lose it silently, but it does not merge either.

### Requirement: <existing name, copied verbatim from the living spec>

The system SHALL <new statement>.

> Previous behaviour: <one line>. Reason for the change: <one line>.

#### Scenario: <the one you are changing>

- **WHEN** <...>
- **THEN** <...>

#### Scenario: <every other scenario the living spec already had, repeated verbatim>

- **WHEN** <...>
- **THEN** <...>

## REMOVED Requirements

> Names only — no body and no scenarios are required. The reason and the migration are a
> convention this project keeps, not something the tool checks.

### Requirement: <name>

Removed because <reason>. Clients relying on it must <migration>.

## RENAMED Requirements

> Exact syntax. `FROM:` and `TO:` are case-sensitive; the backticks are optional.
> Use this instead of a REMOVED + ADDED pair, which would lose the requirement's history.

- FROM: `### Requirement: <old name>`
- TO: `### Requirement: <new name>`

---

## Writing rules

- One requirement, one behaviour. If a requirement needs an "and" in the middle,
  it is two requirements.
- Every requirement has at least one failure scenario. A capability with only happy
  paths has not been specified.
- `WHEN` states a concrete input, not a category. "WHEN the user submits an empty
  description" beats "WHEN the input is invalid".
- `THEN` states something observable from outside: a status code, a stored row, a
  rendered message. Not "the service handles it correctly".
- No forbidden words: *if needed*, *if applicable*, *when available*, *if present*,
  *or*, *prefer*, *may be*, *as needed*.

## What the tool checks, and what it does not

Know the difference, so you do not mistake a green validation for a good spec.

**Checked** (`openspec validate <change>`): at least one delta exists; every ADDED and
MODIFIED requirement has at least one scenario; no duplicate names within a section; no
requirement in two sections at once; RENAMED pairs well formed. With `--strict`, a
requirement text missing `SHALL`/`MUST` fails too.

**Not checked**: the `- **WHEN**` / `- **THEN**` shape. For OpenSpec a scenario is *any*
`####` header and its body is opaque text. WHEN/THEN is a convention this project
enforces by review, not by tooling — which is exactly why the review matters.
