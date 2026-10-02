# Capability: Real-model production parity runner

<!-- Durable spec: it outlives the run. One capability per file; MyFlow injects the requirements a task
     references into the WorkOrder and the review pack. Format is OpenSpec-compatible. -->

Plan 2.4 (Astra audit of the final plan, №21) requires a bounded real-model
comparison before the holdout opens: on 30 H cases, the API's Chroma search and
the harness's exact-cosine search are compared on id and order of the pool and
the reranked list, the effective query and the post-grading context hash.
`scripts/production_parity.py` calls every model once, records the call, and
replays the records through `ConversationSession`, so both arms and the session
replay see identical model outputs.

## Requirement: an incomplete model call refuses evidence

A model, embedding or reranker call that does not complete SHALL NOT be cached,
SHALL be counted as a failure and SHALL make its stage refuse the result.
Incomplete calls include a timeout, a connection error, a digest mismatch, a
cache miss, a corrupt record and an unknown recorded outcome, as well as any
exception other than the recorded outcome below. The refusal SHALL carry the
first failure's exception as its cause.

### Scenario: model timeout during grading
- **GIVEN** the live model raises `TimeoutError("model timeout")`
- **WHEN** the stage checks its state
- **THEN** no cache record exists for the call, the stage raises a
  `RuntimeError` that names the failed call, and its `__cause__` is that
  `TimeoutError`

### Scenario: unknown or tampered recorded outcome
- **GIVEN** a cached `llm` record whose outcome is unknown, or whose value no
  longer matches its hash
- **WHEN** the record is replayed
- **THEN** the call counts as a failure and the stage refuses its result

## Requirement: a completed reply that fails schema validation is a recorded outcome

When the model completes a reply and the production provider's
`generate_with_schema` raises `StructuredOutputValidationError` on it, the
runner SHALL record that outcome as a cache record. The record holds the error
type, the message and the raw reply, under the same integrity check as a
response. The runner SHALL raise the same `StructuredOutputValidationError` to
the caller in both live and replay modes, and SHALL NOT count it as a failure.
Production's own fallback then runs identically in both arms and in the
session replay. Production code is not changed for this.

### Scenario: the model answers YES instead of JSON
The full 30-case run on `c3d2909` stopped this way at call `64aa36e2…`.

- **GIVEN** the raw reply to a schema grade call is the text `YES`
- **WHEN** the grade stage runs live and the verify stage replays it
- **THEN** the cache holds one outcome record with the raw text `YES`;
  both modes raise `StructuredOutputValidationError("structured output is not
  valid JSON")`; production falls back to its text grade; the stages complete;
  and the session replay matches
