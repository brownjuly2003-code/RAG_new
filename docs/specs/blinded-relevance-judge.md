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

## Requirement: v2 requests bind blind grades to exact addressed chunks

The v2 contract in `evaluation/judge_contract.py` SHALL accept 1–10 documents and
retain the v1 0–3 rubric. The v1 builder and parser remain available for the pinned
P2 artifacts. A v2 request SHALL record `request_version: 2`, `rubric_version` and
the caller's `judge_version` (model id and route parameters).

Each document SHALL carry its exact text, its UTF-8 `text_sha256` and an address:
`source_id`, `source_revision`, `chunker_version`, and either `section_path` or
`char_start`/`char_end`. Addresses, hashes and retrieval metadata SHALL stay outside
the prompt. Empty sets, more than ten documents, duplicate text hashes and a
supplied hash that differs from the exact text SHALL be refused. The builder SHALL
sort by text hash, then shuffle with `random.Random(f"20260925:v2:{case_id}")`,
and label the presented documents D1 through Dn.

`question_hash` SHALL hash the exact UTF-8 question. `request_key` SHALL hash the
canonical JSON (sorted keys, compact separators, UTF-8) of `request_version`,
`question_hash`, the ordered `text_sha256` list, `rubric_version` and
`judge_version`. `request_sha256` SHALL separately hash the exact prompt bytes.
Stored grades SHALL be reused only for an identical `request_key`.

The v2 parser SHALL accept the first balanced JSON object, including one inside
prose or a code fence, only when each presented label occurs exactly once with an
integer 0–3. Its outcome SHALL be `valid`, `invalid` or `absent`. Invalid reason
codes SHALL be `no_json`, `missing_label`, `duplicate_label`, `extra_label`,
`out_of_range` or `non_integer`; an empty or missing reply SHALL be `absent`.
Neither invalid nor absent outcomes SHALL produce grade records.

The JSON-lines grade store SHALL validate every record on write and read. Each
record SHALL contain `case_id`, `question_hash`, `address`, `text_sha256`, `grade`,
`rubric_version`, `judge_version`, `request_key` and `request_sha256`. Missing
fields, malformed SHA-256 hashes, invalid addresses and grades outside the
integer 0–3 range SHALL be refused.

### Scenario: retrieval order and metadata stay hidden
- **GIVEN** the same addressed text set in two different retrieval orders
- **WHEN** both v2 requests are built for the same case and versions
- **THEN** their prompt bytes and request keys are identical
- **AND** neither prompt contains metadata-only addresses, hashes, ranks or keywords

### Scenario: the cache binds exact text and versions
- **GIVEN** stored grades for a v2 request
- **WHEN** one text, the question, the rubric version or the judge version changes
- **THEN** the request key changes and the previous grades are not reused

### Scenario: a fenced valid reply differs from a missing grade
- **GIVEN** a fenced JSON object grading all presented labels once with integers 0–3
- **WHEN** it is parsed
- **THEN** the outcome is valid and its addressed grades can be stored
- **AND** a reply missing a label is invalid, while no reply is absent; neither is graded

## Requirement: the v2 runner persists exact replies and resumes explicitly

`python -m scripts.relevance_judge_v2 --judge glm --cases cases.jsonl --store replies.jsonl`
SHALL consume JSONL cases with `case_id`, `question` and 1–10 `documents`. Each
document contains `text` and `address` as specified above; an optional
`text_sha256` must match. The entire input SHALL be validated before any request.
`--judge` also accepts `sonnet` and `mistral`; Mistral requires
`--mistral-key-file`. Credentials SHALL NOT enter the reply store.

Each attempt SHALL append its status, reason, raw reply, request hashes and
versions, plus validated `records` for a valid reply. Successful responses also
retain the reported model, usage and elapsed time. The CLI's judge version SHALL
bind the judge, route and parameters; Sonnet also binds the SHA-256 of the
configured endpoint. Stored grade records SHALL be validated on read, and cached
raw replies SHALL be parsed again before reuse. Reuse requires both the exact
`request_key` and `request_sha256`. An unchanged text set with new addresses
SHALL reuse the reply and append records bound to the current addresses.

This explicit v2 runner SHALL make at most one request per uncached case per
invocation; the archived v1 runner retains its registered retry procedure.
Invalid/absent outcomes SHALL produce no grades and SHALL remain eligible for
a later explicit invocation. Transport failures SHALL be recorded as absent.
Quota, authentication and rate-limit failures SHALL be persisted and end the
run without retries or waiting; a supplied reset time SHALL be retained.
`--limit N` SHALL cap new requests, while cached cases can still be reused.
The summary SHALL report valid, invalid, absent, reused and pending case counts;
any invalid, absent or pending case SHALL cause exit status 1. These are runner
counts, not quality metrics or an acceptance verdict.

### Scenario: a resumed v2 run keeps failed attempts separate
- **GIVEN** a store with valid, invalid and absent replies
- **WHEN** the runner resumes with the same inputs and judge configuration
- **THEN** only exact valid replies are reused, while failures receive new attempts
- **AND** no invalid or absent reply becomes grade 0

### Scenario: the judge endpoint changes
- **GIVEN** a valid cached Sonnet reply
- **WHEN** the runner uses a different `--gk-base` endpoint
- **THEN** it sends a new request instead of reusing the previous endpoint's grade

### Scenario: a run reaches a quota or rate limit
- **GIVEN** a judge that returns an unavailable or rate-limit outcome
- **WHEN** the runner receives it
- **THEN** it stores an absent attempt and any reset time, leaves remaining cases
  pending, and exits with status 1

## Requirement: baseline contexts are regraded by a fixed plan

`python -m scripts.baseline_judge plan --run <run> --out <dir>` SHALL read one
finished production-baseline run: its manifest, its report and every grade row,
each bound to the run's identity, with no open abort record. It SHALL write
`plan.json` once; an equal plan already in the directory is accepted, a different
one SHALL be refused. For each collected case the plan SHALL take the first five
reranked seeds and the sent documents, deduplicated by `text_sha256`. A text
without a chunk address SHALL NOT be sent; the plan records it as unaddressed with
its address reason. Cases excluded in collection SHALL be listed and not judged.

The addressed texts of a case SHALL be sorted by `text_sha256` and cut into
`ceil(n / 10)` consecutive parts whose sizes differ by at most one, larger parts
first. A single part keeps the case id; the parts of a split case are
`<case_id>#<k>` with `k` from 1. The plan SHALL record each request's
`request_sha256` and prompt length, and SHALL be refused on read when either no
longer rebuilds from the stored question and documents.

`judge --out <dir> --judge glm|sonnet` SHALL send the planned requests through the
v2 runner into `<dir>/<judge>.jsonl`, under the judge version the runner's own CLI
gives the same judge, route, parameters and endpoint. One store SHALL hold the
attempts of one judge version: before any request `judge` SHALL refuse a store
that holds an attempt of another version. The Sonnet endpoint SHALL come from
`RAG_JUDGE_GK_BASE`; without it the command SHALL be refused before any request.
Neither the endpoint nor a credential SHALL be printed. The summary SHALL report
what left the machine as an upper bound: the calls, texts and prompt characters of
every attempt that was not a reuse.

`consensus --out <dir>` SHALL count a grade only when its request id and
`request_sha256` are in the plan. It SHALL refuse a store whose attempts, whatever
their outcome, carry more than one judge version, and a store that holds a sent
attempt whose request id and `request_sha256` are not a planned pair. The unit is
`(baseline case, text_sha256)` and its consensus follows the rule above. A unit
without a grade of an included judge is unjudged with a reason, never grade 0. A
case whose deciding population, the first five seeds and the sent documents, holds
an unjudged or unaddressed text SHALL be left out of the ruler input and counted,
never scored. A text sent more than once is one document of the ruler input, kept
at its first position, and the repeats SHALL be counted; seeds are passed as
ranked. With no consensus grade at all the status SHALL be `NOT_EVIDENCE`,
`ruler-input.json` SHALL NOT be written and the exit status SHALL be 1; the counts
of kept and excluded cases SHALL be reported for both statuses. The command
computes no quality number.

### Scenario: a case with more than ten texts is split
- **GIVEN** a case whose seeds and sent documents hold 21 distinct addressed texts
- **WHEN** the plan is built
- **THEN** it holds three requests of 7 texts each in `text_sha256` order, named
  `<case_id>#1` to `<case_id>#3`
- **AND** the same texts in another retrieval order give the same requests

### Scenario: an unaddressed text leaves its case out
- **GIVEN** a sent document whose chunk address could not be resolved
- **WHEN** the plan and the consensus are built
- **THEN** the text is in no request
- **AND** its case is left out of the ruler input with the address reason

### Scenario: a judge directory is reused for another run
- **GIVEN** a judge directory that holds the plan of one baseline run
- **WHEN** `plan` is called there for a run that gives a different plan
- **THEN** the command is refused and `plan.json` is unchanged

### Scenario: the judge configuration changes in a used directory
- **GIVEN** a store that holds attempts of one judge version
- **WHEN** `judge` runs there with another endpoint or other judge parameters
- **THEN** it is refused before any request and the store is unchanged

### Scenario: one text is sent twice
- **GIVEN** a sent context that holds one text under two addresses and one other text
- **WHEN** the ruler input is built
- **THEN** the case's sent documents are the two distinct texts and one repeat is counted

## Requirement: the generation judge's deciding κ sample is explicit

The deciding κ of the generation judge (`scripts/generator_benchmark.py`) SHALL
use only pairs of records that share the exact judge request (`request_sha256`)
and are both eligible: status `valid`, neither the context nor the answer
truncated. Unit-interval scores SHALL be binned for quadratic κ as
`min(3, floor(score × 4))`; a score outside [0, 1] SHALL be refused. Every
excluded pair and every unmatched record SHALL be counted once, under
`unpaired`, `absent`, `invalid` or `truncated` in that order of precedence. A
run summary SHALL print, per metric, the κ-sample size and the exclusions. A
request repeated within one source, or a stored `kappa_eligible` that
contradicts the status and truncation, SHALL be refused.

### Scenario: a truncated pair stays outside κ
- **GIVEN** two sources that agree on a set of eligible pairs
- **WHEN** a pair whose request was truncated is added to both
- **THEN** κ and the pair count are unchanged and only `truncated` grows

## Requirement: set labels live next to the set and bind to its cases

Grade records of a labelled set SHALL be stored in `<set>.grades.jsonl` next to
the set file, written and read only through the validating grade store. Each
record SHALL bind to a case of the set: its `case_id` exists in the set and its
`question_hash` equals the hash of that case's exact question. Otherwise a
write SHALL store nothing and a read SHALL be refused. The chunk address need
not point at a gold document: the judge also grades retrieved chunks.

### Scenario: a record of a foreign case is refused
- **GIVEN** a set and a record whose `case_id` is not in it
- **WHEN** the records are written
- **THEN** the write is refused and the grades file is not created
