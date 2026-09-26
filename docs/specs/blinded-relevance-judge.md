# Capability: blinded-relevance-judge

An offline evaluator that asks external language models to grade, blind, how well each
retrieved document answers its question. It then compares those grades with the official
context-precision ruler. The pre-registered procedure and decision rule are in the
[P2 plan](p2-blinded-judge-plan.md); this spec states what the runner must do. The runner
changes no retrieval, no gate and no product behaviour.

## Requirement: a judge sees only the question and the document text

For each case, the runner SHALL build one request. It holds the fixed instruction, the
question, and the case's top five documents as the ruler scored them. The documents SHALL
appear in the pre-registered per-case random order, labelled D1 to D5 by position. A
request SHALL NOT contain:
- an expected keyword that is absent from the question and the documents;
- a rank, a reranker score, an arm name, a label, a source path outside the document
  text, or another judge's grade.

Every judge SHALL receive the same bytes for the same case.

### Scenario: keywords stay hidden
- **GIVEN** a case whose expected keywords include a sentinel string that occurs in neither
  its question nor its documents
- **WHEN** the runner builds the case's request
- **THEN** the sentinel does not occur in the request

### Scenario: the order is the pre-registered permutation
- **GIVEN** a case id
- **WHEN** the request is built twice, and on another machine
- **THEN** the documents appear in the order that `random.Random(f"20260925:{case_id}")`
  gives, both times

## Requirement: replies are parsed strictly

The parser SHALL take the first balanced JSON object in a reply, including one inside
prose or a code fence. It SHALL accept the object only if it grades each presented label
exactly once, with an integer from 0 to 3. Any other reply is a parse failure. After a
parse failure the runner SHALL send a new request, at most twice, and then record the case
as `missing` for that judge. A parse failure SHALL never become a grade.

### Scenario: a malformed reply
- **GIVEN** a reply that omits D4, repeats D2, adds D6 or grades a document 4
- **WHEN** it is parsed
- **THEN** it is a parse failure and no grade is stored for the case

## Requirement: an unavailable judge is reported, never graded

An authentication failure, a quota or zero-limit reply, or an unreachable endpoint SHALL
mark the judge `unavailable` for the run, with the reply's code and message. The run SHALL
go on with the other judges. A run in which no judge graded a unit SHALL write no report
and SHALL say `NOT_EVIDENCE`. Transport errors SHALL be retried with backoff. A rate limit
that names its reset time SHALL be waited out.

### Scenario: one judge is blocked
- **GIVEN** two judges, one of which answers HTTP 429 with a zero request limit
- **WHEN** the run starts
- **THEN** that judge is recorded `unavailable` with the code and message
- **AND** the other judge's grades alone form the consensus

## Requirement: replies are stored and reused

Each reply SHALL be stored when it arrives. The record holds the judge, the case, the
request's SHA-256, the raw reply text, the model id the endpoint reported, the timing and
the usage. No credential SHALL be stored. A rerun SHALL skip the cases a judge already
graded with the same request SHA-256. The stored replies of several judges, possibly from
different machines, SHALL merge into one run.

### Scenario: a run resumes after an interruption
- **GIVEN** a judge that graded 40 of 115 cases before the run stopped
- **WHEN** the run is started again with the same inputs
- **THEN** only the other 75 cases are requested from that judge

## Requirement: consensus follows the plan

A unit's consensus SHALL be the lower median of the grades of the judges that graded it.
A judge missing more than 5% of a pool's units SHALL be left out of that pool's consensus
and reported on its own. A unit is relevant when its consensus is at least 2 and
sufficient when it is 3.

### Scenario: two judges disagree
- **GIVEN** grades 3 and 1 for one unit
- **WHEN** the consensus is formed
- **THEN** it is 1

## Requirement: the ruler and the arms are reproduced before use

The runner SHALL recompute, with the official function, the ruler's per-case precision
of `top_k_5` on H. The aggregate SHALL reproduce the published 0.5067; otherwise the run
SHALL stop with `INVALID_CONTROL`. A document's ruler relevance SHALL be the official
function applied to that document alone. The arms SHALL be re-scored from the kept
counts in the published P1 report. Every kept document SHALL be one of the five judged
documents, and no arm SHALL cause a new request.

### Scenario: the control does not reproduce
- **GIVEN** a pool whose recomputed `top_k_5` precision differs from 0.5067
- **WHEN** the run starts
- **THEN** it stops with `INVALID_CONTROL` before any judge is called

## Requirement: the verdict follows the pre-registered rule

The report SHALL carry the verdict that the plan's decision rule gives for H:
`JUDGE_UNRELIABLE`, `RULER_TRACKS`, `RULER_DOES_NOT_TRACK` or `INCONCLUSIVE`. It carries
the `PROVISIONAL_` prefix when judge reliability cannot be checked. The report SHALL pin
the code commit, both pools, the datasets, the label manifest and its approvals sidecar,
the instruction's SHA-256, each judge's route and parameters, and the stored replies.

### Scenario: a single judge without human grades
- **GIVEN** one judge in the consensus and no human grades
- **WHEN** the verdict is computed
- **THEN** it starts with `PROVISIONAL_`

## Requirement: the human sample is drawn by the plan

The runner SHALL draw the human-adjudication sample by the plan's procedure, from the
ruler alone, before any judgment is used. It SHALL write the sample as a local page that
makes no network request and shows no score, rank or grade. It SHALL import the grades
the page exports only when they grade exactly the sampled units with integers from 0 to
3, and only with the grader's name and date.

### Scenario: the sample is fixed
- **GIVEN** the H pool and the official ruler
- **WHEN** the sample is drawn twice
- **THEN** both draws name the same 10 cases, two from each ruler quintile
