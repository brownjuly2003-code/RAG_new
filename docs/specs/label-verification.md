# Capability: Label verification of development-set drafts

<!-- Durable spec: it outlives the run. One capability per file; MyFlow injects the requirements a task
     references into the WorkOrder and the review pack. Format is OpenSpec-compatible. -->

Plan step 1.3b replaces the human approval of development-set cases with a
check by a model of a vendor other than the draft author's (decision D11).
Since plan decision D12 the rubric, `label-verification/v2`, registers one
verifier — the model of the agent that runs the plan — where v1 registered
two of two vendors. The protocol — who checks, the five checks, the decision
per case, the repair round, the wide scan — is the section «Label
verification» of [the development ruler](semantic-precision-metrics.md); this
file says what the tool that runs the protocol must do. Where the two differ,
the protocol is right and the difference is a defect of this file. The tool:
`scripts/devset_wide_scan.py` (the wide scan, run where the embedder is),
`evaluation/label_verification.py` (packets, reply form, decision) and
`scripts/devset_label_verify.py` (commands `plan`, `verify`, `decide`,
`apply`, `check`). A model check is not a human approval: nothing here
assigns `real_labelled` or raises the count of real labelled cases.

The rules below are written for any number of registered verifiers: every
verifier must confirm, and any one can reject. The registry names one, and a
scenario that needs two says so. A second verifier would be a registry entry
and a new rubric version, not a change of these rules.

## Requirement: the wide scan covers the whole index with both lanes

For every case of the cases file `scripts/devset_wide_scan.py` SHALL store
the union of the 20 best chunks by the production lexical scorer — BM25 with
the production tokenizer over the same chunk text production indexes, every
chunk of the archive, a chunk with a score of zero or below not taken — and
the 20 nearest chunks by exact cosine similarity between the production
embedder's vector of the question as written and every vector of the
embedding checkpoint. It SHALL apply no query transform, fusion, cap, rerank
or expansion, break ties by position in the archive, and keep a chunk found
by both lanes once, with both ranks. The output SHALL carry, per chunk, its
address, `text_sha256`, and the rank in each lane that found it; per case
the case id and the SHA-256 of the question; and once the SHA-256 of the
chunk archive, of the checkpoint and of the cases file, the embedder
manifest, the lane size and the code SHA. The same inputs SHALL give the
same bytes.

It SHALL refuse, and write nothing, on inputs that break the contract of
`scripts/production_index.py`: an archive whose SHA-256 is not the one in the
index receipt; a checkpoint whose SHA-256 is not the receipt's, or whose
recorded archive SHA-256, ordered text hash or embedder manifest is not the
archive's and the receipt's; a matrix that does not hold one finite
unit-norm row per chunk; a loaded query embedder whose manifest is not the
receipt's.

### Scenario: a passage only the lexical lane finds
- **GIVEN** a chunk in the lexical top 20 and outside the dense top 20
- **WHEN** the scan is made
- **THEN** the chunk is in the union with its lexical rank and no dense rank

### Scenario: another archive of the same size
- **GIVEN** a chunk archive with the receipt's chunk count and another
  SHA-256
- **WHEN** the scan is started
- **THEN** it refuses and writes nothing

## Requirement: a request carries the whole case and names no file

`plan` SHALL build one request per case and round; every registered verifier
receives the same text. The request SHALL carry the question, the span texts,
the required and critical facts with their quotes, the reference answer, the
primary class, the `safety_critical` flag, the trap type, `expected_action`,
the registered reason, `as_of`, the authority documents, the severity, and
the document card of each authority document — the front-matter fields
`title`, `document_type`, `source_type`, `version`, `effective_date`,
`owner_role`, `related_normative_sources` and no other field. It SHALL NOT
carry the flags `numeric`, `ru_to_en` and `adversarial_unanswerable`: the
verify script computes each from the label, and no verdict is asked on them.
For a refusal, clarification or trap case — `expected_action` other than
`answer`, or a trap type set — it SHALL also carry the text of the
seed-selected and partner sections and the texts of the wide scan, in archive
order.

Every source SHALL be named by a pseudonym that is stable inside the request
(`D1`, `D2`, …). The text the model sees SHALL NOT contain a file name, a
`source_id`, a `doc_id` or a path: in every text that goes out, the name of a
corpus file is replaced by the pseudonym of that document and any other
`.md` file name by a neutral token. It SHALL NOT contain the `scope` text of
`authority_source`, the draft author, the repair author, a verifier, the
round or anything of an earlier round. The map from pseudonyms to sources
stays in the plan.

The plan SHALL record, per request, the SHA-256 of the request text, the
case id, the round, the SHA-256 of the case revision it was built from, the
pseudonym map, and the count of characters and of corpus texts; and once the
rubric version, the SHA-256 of the prompt, and each verifier's model id,
vendor, route and settings. The request text is not written to a repository
file: `verify` rebuilds it from the same inputs and refuses a text whose
SHA-256 is not the plan's.

In round 2 a case rejected in round 1 comes to `plan` in one of two forms: a
repaired revision, or a drop declared by the repair author — the case id and
a ground: `repair_needs_reserve` with the document or documents of the
holdout reserve that a repair would have to cite, or `repair_not_possible`
with the reason in one sentence. A declared drop gets no request; the plan
SHALL record it with its ground and what that ground needs, and nothing else
of the declaration. A rejected case given in neither form stays
`repair_pending`.

`plan` SHALL refuse, and write nothing, when the SHA-256 of the prompt is not
the registered one; when no verifier is given, a verifier's vendor is the
draft author's or two verifiers share a vendor; when the corpus is not the
registered version; in round 1, when the drafts fail the unchanged verify
script of the pilot; in round 2, when a case was not rejected in round 1 or
is given both as a repair and as a declared drop; when a repaired case
changes a field a repair must keep — the case id, the question text, the
draft author, the corpus version, `as_of`, the seed-selected section, the
question style — cites a document of the holdout reserve, leaves the label as
drafted, or fails the per-case rules of the verify script or its source
checks; when a declared drop has a ground other than the two registered ones,
under `repair_needs_reserve` names no document or a document outside the
registered holdout reserve, or under `repair_not_possible` gives no reason;
when a refusal, clarification or trap case has no wide scan made for its
question; and when a text of the scan does not match its `text_sha256` in the
chunk archive.

### Scenario: a file name would leave the machine
- **GIVEN** a case whose spans come from two source files, one of which
  lists the other's file name under «Связанные документы»
- **WHEN** its request is built
- **THEN** the request names them `D1` and `D2`, the same pseudonym on spans,
  cards and scan texts of one document, and no corpus file name appears
  anywhere in the request text

### Scenario: a repair that changes the question
- **GIVEN** a case rejected in round 1 and a repaired version with another
  question text
- **WHEN** round 2 is planned
- **THEN** `plan` refuses and writes nothing

### Scenario: a repair that reaches into the reserve
- **GIVEN** a repaired case with a span from a document of the holdout
  reserve
- **WHEN** round 2 is planned
- **THEN** `plan` refuses and writes nothing

### Scenario: a repair that changes nothing
- **GIVEN** a case rejected in round 1 and, given as its repair, the label
  as drafted
- **WHEN** round 2 is planned
- **THEN** `plan` refuses and writes nothing: a second request on the same
  label would be a second draw of the same check

### Scenario: a case that only a reserve document could repair
- **GIVEN** a case rejected in round 1 and a declared drop that names one
  document of the holdout reserve
- **WHEN** round 2 is planned, decided and applied
- **THEN** the case gets no request, its state is `dropped` with the declared
  ground and that document in the register, and it does not keep `complete`
  false

### Scenario: a case no repair can answer
- **GIVEN** a case rejected in round 1 and a drop declared on the ground
  `repair_not_possible` with its reason
- **WHEN** round 2 is planned, decided and applied
- **THEN** the case gets no request, its state is `dropped` with the ground
  and the reason in the register, and it does not keep `complete` false

### Scenario: a declared drop that names no reserve document
- **GIVEN** a declared drop on the ground `repair_needs_reserve` whose only
  document is outside the holdout reserve
- **WHEN** round 2 is planned
- **THEN** `plan` refuses and writes nothing

## Requirement: a verdict is stored as the verifier gave it, and only a valid one counts

`verify` SHALL send the planned requests of one verifier through that
verifier's registered route — a new process of the Claude Code CLI for every
request, with no conversation state, no stored session and no tools — and
keep every reply in a store that a rerun resumes by request. The tool SHALL
hold a route for a registered verifier only and SHALL NOT build a client for
any other model. A reply SHALL count only when the route reports the
registered model id and the reply follows the form of the protocol: `confirm`
or `reject` with a reason on checks 2, 3, 4 and 5d, and the element concerned
on a rejection; `confirm`, `reject` or `unverifiable` with a reason on 5a and
5b; a level of the registered scale on 5c. A reply in another form SHALL be
stored as invalid and the request sent again, three attempts in all. When the
verifier is unavailable — a quota, an outage, another model id — `verify`
SHALL stop with a non-zero exit code and record no verdict for the requests
it did not complete. The store SHALL keep the request SHA-256, the prompt
SHA-256, the rubric version, the reported model id, the attempt, the raw
reply and the usage; it SHALL NOT keep or print an endpoint, a key or a
settings path.

### Scenario: the verifier is out of quota
- **GIVEN** a plan of thirty requests and a verifier that refuses the tenth
  with a quota error
- **WHEN** `verify` runs and is run again after the reset
- **THEN** the first run stops with a non-zero exit code and nine verdicts,
  and the second run sends only the remaining twenty-one

### Scenario: a rejection without a reason
- **GIVEN** a reply that rejects check 2 and gives no reason
- **WHEN** it is parsed
- **THEN** it is stored as invalid and the request is sent again

### Scenario: a model that is not a registered verifier
- **GIVEN** the id of a model of another vendor, or of the draft author
- **WHEN** a client is asked for it
- **THEN** the tool refuses: no route exists for it

## Requirement: the decision is the registered rule, recomputed from the stores

`decide` SHALL give every planned case one outcome of the round, in this
order: `none` — a verifier gave no valid verdict; `confirmed` — the
deterministic check passes, every verifier confirms checks 2, 3, 4 and 5d,
none rejects 5a or 5b, and none names a severity two or more steps from the
registered one on the scale `low` < `moderate` < `high` < `critical` or on
the other side of the `critical` boundary; `rejected` — any other set of
valid verdicts. A confirmed case SHALL carry `authority_unverified` when a
verifier answered `unverifiable` on 5a or 5b. For every rejected case
`decide` SHALL list the rejecting checks with the reasons of every verifier —
the input of the repair. Over the rounds a case is `verified` (confirmed in
round 1 or 2), `dropped` (rejected in round 2, or rejected in round 1 with a
declared drop in the plan of round 2), `repair_pending` (rejected in round 1,
with neither a declared drop nor an outcome in round 2 yet) or `unverified`
(no outcome). `decide` SHALL refuse a store whose request, prompt or rubric
version is not the plan's.

### Scenario: one verifier decides alone
- **GIVEN** the one registered verifier rejecting check 3
- **WHEN** the round is decided
- **THEN** the case is rejected with that reason, and no disagreement is
  listed

### Scenario: the verifiers disagree
- **GIVEN** two registered verifiers, one confirming every check and the
  other rejecting check 3
- **WHEN** the round is decided
- **THEN** the case is rejected, and the disagreement and the reason are
  listed

### Scenario: currency cannot be read from the corpus
- **GIVEN** a verdict with every check confirmed except 5a, where the
  verifier answers `unverifiable`
- **WHEN** the round is decided
- **THEN** the case is confirmed and carries `authority_unverified: true`

### Scenario: severity differs by one step
- **GIVEN** a case registered `moderate` that a verifier calls `high`
- **WHEN** the round is decided
- **THEN** the difference is listed and does not reject the case

### Scenario: severity crosses the critical boundary
- **GIVEN** a case registered `high` that a verifier calls `critical`
- **WHEN** the round is decided
- **THEN** the case is rejected on check 5c

## Requirement: the verified set and its register follow from the decisions

`apply` SHALL write the verified set: every verified case, in the revision
its verdicts were given on, with `draft_author`, `label_check` — the status,
the verifier ids, the rubric version, the round and, on a case confirmed in
round 2, `repair_author` — and `authority_unverified`; every `unverified` or
`repair_pending` case as its draft with `label_check: none`; no dropped case.
The status SHALL be `single_model_verified` when one verifier is registered,
and `model_verified` only when more than one is: a check by one model is
never given the word of a check by two vendors. It SHALL write a register
with, per case, its state, the outcome of each round, each verifier's verdict
on each check with its reason, the SHA-256 of the case before and after a
repair, its documents and families after a repair, and the reason of a drop:
the rejecting checks of round 2, or the declared ground with the reserve
documents or the reason it gives.
The register SHALL publish: per drafted class the share rejected at the first
check; the class of every repaired case before and after, the cases verified
after a repair, and the counts of the verified set by class after repair; the
disagreements between the verifiers and the severity differences; the flagged
and the dropped cases; the count of safety-critical cases with and without
the `authority_unverified` ones; the repair author; per verifier the count of
requests, characters and corpus texts sent; the SHA-256 of the drafts, the
plans, the stores and the scan; and `complete`, true only when every case is
verified or dropped. `label_origin` SHALL stay `agent_labelled`. The same
inputs SHALL give the same bytes. The drafts file, its manifest and the
family register SHALL NOT be changed.

`check` SHALL recompute the decisions from the stores and refuse a verified
set that differs: a verified case whose valid verdicts do not satisfy the
confirmation rule of the protocol; a case whose status is not the one the
registered verifiers give; a verified case whose content is not the revision
the verdicts' requests were built from; an unrepaired case that differs from
its draft; a repaired case that changes a field a repair must keep, cites a
document of the holdout reserve, leaves the label as drafted or fails the
per-case rules of the verify script; a dropped case still present; a declared
drop for a case round 1 did not reject, or one without what its ground needs.
Set-level rules of the drafts — quotas, trap and flag counts, the split of
styles, the SHA-256 of the drafts file — do not apply to the verified set;
its counts are reported.

### Scenario: a set checked by one model
- **GIVEN** the one registered verifier confirming a case in round 1 and
  another, repaired, in round 2
- **WHEN** the set is applied
- **THEN** both carry `single_model_verified`, the second with
  `repair_author`, the register lists it among the cases verified after a
  repair, and `check` refuses a row relabelled `model_verified` by hand

### Scenario: a case one verifier has not answered
- **GIVEN** two registered verifiers and a case with a valid verdict of one
  only
- **WHEN** the set is applied
- **THEN** the case is written with `label_check: none`, its state is
  `unverified`, and `complete` is false

### Scenario: a case waiting for its repair
- **GIVEN** a case rejected in round 1 and no round 2 yet
- **WHEN** the set is applied
- **THEN** the case is written as its draft with `label_check: none`, its
  state is `repair_pending`, and `complete` is false
