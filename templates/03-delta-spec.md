# Delta Spec — <capability name>

> Lives in `openspec/changes/<change-name>/specs/<capability>/spec.md`.
> A delta spec describes only what this change **adds**, **modifies** or **removes**
> from the capability. Plain Markdown, no special syntax.

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

### Requirement: <existing name, copied verbatim from the capability spec>

The system SHALL <new statement>.

> Previous behaviour: <one line>. Reason for the change: <one line>.

#### Scenario: <...>

- **WHEN** <...>
- **THEN** <...>

## REMOVED Requirements

### Requirement: <name>

Removed because <reason>. Clients relying on it must <migration>.

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
