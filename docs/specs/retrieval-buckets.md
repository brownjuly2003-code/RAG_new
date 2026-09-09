# Capability: Retrieval quality by question class

<!-- Durable spec: it outlives the run. One capability per file; MyFlow injects the requirements a task
     references into the WorkOrder and the review pack. Format is OpenSpec-compatible. -->

Phase C measures one aggregate context precision (0.5067 at recall 0.9050) over
all 100 curated cases. One number cannot say whether the top-5 is noisy on
questions answerable from a single section or on questions that need several
documents chained, and stream GR of `plan_06_09_26.md` is a bet about exactly
that difference. Every GR claim is therefore reported per question class, over a
candidate pool that is pinned by digest so that arms are compared against each
other and not against a re-ranking that quietly moved underneath them.

## Requirement: every curated case carries a question class, without touching the dataset

Each of the 100 curated air-cargo cases SHALL carry a `question_class` of
`single_hop`, `multi_hop`, `aggregation` or `global`, stored alongside the
existing journey labels rather than inside `evaluation/curated_cases_aircargo.jsonl`,
so that the dataset file stays byte-identical and the phase C baseline
(`dataset_sha256 = 3737d694…`) remains reproducible from HEAD.

### Scenario: the labelled dataset is still the measured dataset

- **GIVEN** question classes recorded for all 100 cases
- **WHEN** the SHA-256 of `evaluation/curated_cases_aircargo.jsonl` is taken
- **THEN** it is still
  `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720`

### Scenario: a class is a claim about the question, and it says who made it

- **GIVEN** a case labelled with a question class
- **WHEN** its label is read
- **THEN** the label names the labeller and carries a one-line reason, and its
  evidence class is `agent_labelled` until a human approves it, exactly as
  ADR 0008 requires of the journey labels

## Requirement: a retrieval number is reported per class over a pinned pool

A retrieval report SHALL group its metrics by question class, SHALL state the
number of cases in each class, and SHALL carry the SHA-256 of the candidate
pool it post-processed together with the corpus digest, the code commit and the
configuration, so a later arm can be compared against it.

### Scenario: the baseline is reproducible and comparable

- **GIVEN** the pinned candidate pool and the question-class labels
- **WHEN** the bucket report is produced twice from the same inputs
- **THEN** both reports carry the same per-class numbers and the same pool
  digest

### Scenario: an aggregate that hides a class is not accepted

- **GIVEN** a report over classes with different case counts
- **WHEN** the report is read
- **THEN** the per-class case counts are printed next to the per-class metrics,
  and the aggregate is reported as well, so a class of three cases cannot be
  mistaken for a measured result

## Requirement: a narrowing arm is measured against the arm it replaces

An arm that re-orders or filters candidates SHALL be reported against the
baseline arm on the same pool and the same cases, with keyword coverage
(FULL / PART / MISS) reported next to context precision and recall, so that a
precision gain bought by dropping the answer is visible rather than hidden.

### Scenario: precision went up and coverage went down

- **GIVEN** an arm that raises context precision but turns a FULL case into a
  PART case
- **WHEN** the comparison is reported
- **THEN** both movements appear in the same table, and the report does not
  present the arm as an improvement on precision alone

### Scenario: the arm ends with fewer documents than the baseline

- **GIVEN** an arm whose mean document count per case is below the baseline's
  top-k
- **WHEN** its context precision is reported
- **THEN** fixed truncation of the same pool at each k up to the baseline's is
  reported beside it, so a gain that "keep the first four" already produces is
  not published as a retrieval result

### Scenario: the arm is swept, not tuned

- **GIVEN** an arm with a threshold or any other continuous parameter
- **WHEN** its result is published
- **THEN** the whole stated grid is published, the headline row is chosen by a
  rule fixed before the run rather than by inspection, and the grid contains a
  control cell in which the arm provably drops nothing and adds nothing, whose
  keyword coverage equals the baseline's
