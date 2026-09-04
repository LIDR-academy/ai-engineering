## Purpose

Lets the person running the RAG estimation wizard see, for each task on the "hours"
step, which historical tasks its derived hours came from, so the number can be judged
instead of trusted blind. Covers every task whose hours were derived, including the ones
the recovery agent grounded after the deterministic search came up empty.

## Requirements

### Requirement: Matched tasks show their historical analogs
On the `hours` step of the RAG estimation wizard, a task whose hours were derived from
the historical task corpus SHALL display the list of historical task analogs it was
derived from, each with its recorded hours and a closeness score, in the order the
retrieval returned them, without requiring any additional user interaction to reveal
them.

#### Scenario: Task with historical matches
- **WHEN** a reviewed task's derived-hours result reports a historical match and a
  non-empty list of historical analogs
- **THEN** the hours step SHALL show, under that task, each analog's hours and
  closeness score, always visible, in the order received

#### Scenario: Contradicted consensus still shows its evidence
- **WHEN** a reviewed task's derived-hours result reports a historical match and its
  analogs disagree enough to produce an hours range in addition to the point estimate
- **THEN** the hours step SHALL still show the full list of historical analogs for that
  task, unchanged from the non-contradicted case

#### Scenario: Task grounded by the recovery agent
- **WHEN** the deterministic search found no analog for a task, and the recovery agent
  subsequently derived hours for it from historical analogs it searched itself
- **THEN** the hours step SHALL show that task's analogs exactly as it does for a
  deterministically matched task, and SHALL NOT present the task as if it had been
  grounded without evidence

### Requirement: Unmatched tasks state there is no historical analog
On the `hours` step, a task for which no historical analog was found SHALL show an
explicit message stating that no historical analog was found, instead of an analog list.

#### Scenario: Task with no historical match
- **WHEN** a reviewed task's derived-hours result reports no historical match
- **THEN** the hours step SHALL show an explicit "no historical analog" message for
  that task and SHALL NOT show an analog list (empty or otherwise) for it

### Requirement: Derived hours with no analog detail are labelled, never silent
A task that carries derived hours but no analog detail — because the stored result
predates analog data being recorded, or because its analogs could not be matched back to
the reviewed task — SHALL render without error AND SHALL indicate that the supporting
detail is unavailable. It SHALL NOT render as though the hours had supporting detail
that simply was not shown.

#### Scenario: Stored result carries no analog detail
- **WHEN** a reviewed task's stored derived-hours result reports a historical match but
  carries no historical-analog data
- **THEN** the hours step SHALL render that task's row without raising an error, SHALL
  show no analog list for it, and SHALL show an indication that the supporting detail is
  unavailable

#### Scenario: The unavailable-detail indication is distinguishable
- **WHEN** the hours step shows the unavailable-detail indication for one task and the
  "no historical analog" message for another
- **THEN** the two SHALL be distinguishable from each other, so that "we have no
  precedent for this task" is never presented as "we have a precedent we are not
  showing you"

### Requirement: The derived-hours response carries the analogs behind every grounded task
The per-task derived-hours response SHALL include, for every task it reports as
grounded in the historical corpus, the analogs its hours were derived from — each with
the analog's recorded hours and its distance to the task — regardless of whether those
hours came from the deterministic search or from the recovery agent.

#### Scenario: Agent-recovered task in the response
- **WHEN** the recovery agent grounds a task the deterministic search could not, and
  the service returns the merged per-task hours
- **THEN** that task's entry SHALL report a historical match AND carry the analogs the
  agent derived the hours from, not an empty analog list

#### Scenario: Analog with no known source identifier
- **WHEN** an analog backing a grounded task has no known source identifier
- **THEN** the response SHALL still include that analog with its hours and distance,
  rather than omitting the analog or failing to serialize the response

#### Scenario: Agent could not ground the task
- **WHEN** the recovery agent searched for a task and still found no usable analog
- **THEN** that task's entry SHALL continue to report no historical match, and SHALL
  NOT be presented as grounded
