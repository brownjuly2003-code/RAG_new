# A.6 — Journey admission scored, and why the corpus cannot measure resolution

**Slice:** T-05 of phase A.6 · **Evidence class:** `measured` over
`agent_labelled` · **Date:** 2026-08-27 · **Rule:** (c) — a published
number with provenance. `/api/ask` did not change.

## What landed

Three commits, read in this order. They are local; they have not been
pushed and have not been through remote CI.

- `6651964` **T-01** — the shipment-status journey decides whether a
  request is its own before asking for an id. Three rules, and nothing
  else: a valid shipment reference admits; a truncated one (`SHP-` /
  `AC-` with no id after it) admits, because someone half-typing a
  reference is asking about a shipment; otherwise a shipment-domain noun
  AND a status cue must both be present. A request that fails all three
  ends CANCELLED / NOT_IN_JOURNEY, and `build_shipment_status_observer`
  returns None, so the shadow records nothing and the legacy answer is
  untouched. CLARIFICATION_REQUIRED stopped being the kernel's default
  and became a decision: you asked about a shipment and did not name one.
- `36d4269` **T-02** — `evaluation/journey_admission.py` +
  `scripts/journey_admission_report.py` score that decision against
  `label.journey` on all 100 labelled cases. First consumer B.1's labels
  have had. The number is published as it stands.
- `bd82297` **T-08** — the vocabulary gained a Russian half, built as a
  translation of the English one so it could not be fitted to the corpus
  it is scored against. Every Russian entry names the English term it
  translates; a term with no English counterpart is not added. Matching
  is a stem plus a finite named set of endings, not an unbounded prefix
  and not a hand-written word list.

The shadow behind `/api/ask` is still read-only. Both existing flags
(`RESOLUTION_SHADOW_JOURNEYS`, `SESSION_DURABLE_TURNS`) still default
off. No new flag exists. The legacy answer is still what the user gets.

## The finding this capsule exists for

The corpus cannot measure resolution, for three independent reasons, and
the third was only findable because the vocabulary was not tuned to the
corpus. On these 100 agent-authored-over-real-documents cases, still
`agent_labelled` and 0 approved:

1. **No case names a shipment** (B.1, already on the record). 66 of 100
   belong to no kernel journey; the other 34 are blocked by
   `no_shipment_binding` before they start.
2. **The corpus is Russian and the gate's vocabulary was English.**
   T-02 printed `contains_both_domain_noun_and_status_cue: 0`, so the
   gate could not have admitted anything and over the 100
   agent-authored-over-real-documents cases, still `agent_labelled` and
   0 approved, `recall 0.0000` said nothing about the predicate. 67 of
   the 100 cases contain no Latin character at all; the Latin in the
   other 33 is terms (`MAWB`, `GPS`, `cut-off`), not sentences.
3. **With the language removed, over the 100
   agent-authored-over-real-documents cases, still `agent_labelled` and
   0 approved, admission recall is still 0.0000.** Reachability
   moved from `both 0` to `both 1`. The one case that came through is a
   false positive on `aircargo-trade-compliance-hold`, labelled
   `exception_escalation` ("Когда нельзя снимать compliance hold по
   авиагрузовой отправке?"). None of the six cases labelled
   `shipment_status` was admitted. The corpus contains no case this
   journey should admit.

B.2, B.3 and B.5 therefore stay blocked on data, now for three reasons
rather than one. That is the brief's own NO-GO check (§15) firing a
third time, by an independent route.

## Before / after

Over the 100 agent-authored-over-real-documents cases, still
`agent_labelled` and 0 approved, admission recall is **0.0000** in both
columns (precision undefined, then 0.0000). Both columns were produced
by `python scripts/journey_admission_report.py`: the left at the T-02
tree `36d4269`, the right at HEAD `bd82297` (the fenced pair in the
next section is the right-hand column, quoted as it prints).

| | English only (`36d4269` T-02) | + Russian (`bd82297` T-08) |
|---|---|---|
| Corpus sha256 | `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720` | same |
| HEAD sha | `36d42693564653aa4b3a01986c7bd3ac878ea791` | `bd8229775939e14c35438dbee8fcfeba9f69aff1` |
| Code digest (sha256) | `9e82a8975e2fe282e0493a69dc876f72259199ba1e6be8f04547de4e03b0802d` | `62efcdaf233fd232ff197f3d55f1e98ab04a4aff37ab4d2e13bad0e4f2880874` |
| Reproducible from HEAD | true | true |
| `contains_domain_noun` | 12 | 22 |
| `contains_status_cue` | 3 | 6 |
| `contains_both_domain_noun_and_status_cue` | **0** | **1** |
| true_positive | 0 | 0 |
| false_positive | 0 | 1 |
| false_negative | 6 | 6 |
| true_negative | 94 | 93 |
| Admission precision | undefined | 0.0000 |
| Admission recall | **0.0000** | **0.0000** |
| `no_shipment_reference` | 100 | 99 |
| `no_domain_noun` | 88 | 78 |
| `no_status_cue` | 97 | 94 |
| `neither_domain_noun_nor_status_cue` | 85 | 73 |
| `contains_latin` / `contains_no_latin` | 33 / 67 | 33 / 67 |

The language barrier was real and it was not the binding constraint.
Had the vocabulary been fitted to the corpus, the move from `both 0` to
`both 1` would have read as an improvement instead of as a false
positive on a case this journey should not own.

Code digest framing (both runs): for each listed path in order: 8-byte
big-endian UTF-8 path length, path bytes, 8-byte big-endian content
length, content bytes. Paths in order:
`evaluation/aircargo_labels.py`, `evaluation/journey_admission.py`,
`scripts/journey_admission_report.py`,
`resolution/application/shipment_status.py`.

## The report as it prints from the clean tree

```
python scripts/journey_admission_report.py
```

```
Journey admission report
Corpus: D:\RAG_new\evaluation\curated_cases_aircargo.jsonl
Corpus sha256: 3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720
HEAD sha: bd8229775939e14c35438dbee8fcfeba9f69aff1
Code digest (sha256): 62efcdaf233fd232ff197f3d55f1e98ab04a4aff37ab4d2e13bad0e4f2880874
Code digest framing: for each listed path in order: 8-byte big-endian UTF-8 path length, path bytes, 8-byte big-endian content length, content bytes
Code digest paths (in order):
  evaluation/aircargo_labels.py
  evaluation/journey_admission.py
  scripts/journey_admission_report.py
  resolution/application/shipment_status.py
Reproducible from HEAD: true
Kernel function: resolution.application.shipment_status.ShipmentStatusShadowLoop._is_admitted
Cases: 100
Counts per journey:
  shipment_status: 6
  customs_docs: 11
  exception_escalation: 17
  out_of_scope: 66
Confusion matrix (positive = shipment_status admitted):
  true_positive: 0
  false_positive: 1
  false_negative: 6
  true_negative: 93
  total: 100
Decline reasons (declined cases only):
  no_shipment_reference: 99
  no_domain_noun: 78
  no_status_cue: 94
  neither_domain_noun_nor_status_cue: 73
Script composition:
  contains_latin: 33
  contains_no_latin: 67
Vocabulary reachability:
  contains_domain_noun: 22
  contains_status_cue: 6
  contains_both_domain_noun_and_status_cue: 1
Admission precision: 0.0000
Admission recall: 0.0000
Note: shipment_status is the only admitted journey. out_of_scope is declined; customs_docs and exception_escalation are also declined because no kernel loop exists for them. Those declines are not routing opinions.
```

Over the 100 agent-authored-over-real-documents cases, still
`agent_labelled` and 0 approved, the printed admission precision is
0.0000 and admission recall is 0.0000.

`label.journey` records a topic, not a gold label for admission: the six
`shipment_status` cases are questions *about* the work ("Клиент путает
MAWB и HAWB — какие факты нужны для ответа?"), not requests inside it.
That is B.1's own conclusion arriving a second time.

## Why the numbers are trustworthy

The first version of the scorer labelled its result with
`git rev-parse HEAD` while the scorer did not exist in that commit.
Review findings fixed four earlier provenance defects, and each one
would have left a number that looked like evidence:

1. a SHA that named a commit without the scorer in it;
2. a digest that omitted the module that loads the questions
   (`evaluation/aircargo_labels.py`);
3. the corpus read once for the digest and again for the parse, so the
   bytes scored were not the bytes hashed;
4. a bare concatenation digest, so different file splits collided.

The report now prints one resolved commit SHA, a length-framed digest over the
four code files that decide the result, the framing rule itself, and an
explicit `Reproducible from HEAD` line. T-07 moves that output to report schema
v1.3: corpus and manifest are each read once, and the exact snapshots used for
validation and scoring join the code inputs in the report-level reproducibility
decision. Every Git batch query names the same immutable resolved SHA rather
than symbolic `HEAD:path`; inputs outside the repository fail closed. The two
regressions were RED before the repair. The isolated Mac verification passed
11 focused tests, strict Mypy 1.19.1 and Ruff 0.15.11.

## Accepted limitation (T-08)

The Russian half is deliberately tuned to under-admit. A missed form
costs a legacy answer, which is the status quo; a false friend costs a
real user a wrong question. From here a missing form is a published
limitation; a word admitted that should not be stays a defect at any
severity. An entry is a stem plus a finite named set of endings — not
`startswith`, and not a hand-typed word list — because a list of Russian
surface forms cannot be finished and an unbounded stem prefix admits
derived words that are not inflections (`грузин`, `грузчик`, `холдинг`).

English matching is untouched: exact token or regular plural, as
committed in `6651964`.

## What is still not measured

- **Resolution.** No verified-resolution number, VRY or `pass^k` can
  come from this corpus, however good the kernel gets. That is the
  finding, not a delay.
- **`/api/ask` acting on the clarification terminal.** T-03 closed this
  after A.6: an independent default-off allowlist lets the contract's
  shipment-id clarification own the response. Without both allowlists,
  the user still gets the legacy RAG answer.
- **An empty Evidence bundle is no longer ambiguous.** T-04 records a
  minimal outcome for a declined journey or producer failure. The API
  and tab distinguish both from a disabled shadow; declines still call
  neither source nor policy and never enter resolution persistence.
- **The other two journeys.** `customs_docs` and `exception_escalation`
  have no kernel loop. A decline of those labels is not a routing
  opinion; the report says so.
- **Any terminal other than admission.** `expected_terminal` is
  `verified` for 100 out of 100, so the corpus exercises no
  clarification, escalation, disclosure or refusal path.
- **T-06 correction:** a multi-word admission noun can no longer be assembled
  across a message boundary; a complete noun and its status cue may still
  occur in different messages. Public `/api/ask` supplies one message, so this
  correction is not a new slice under rule (a).
- **T-09 correction:** the validator now compares the original stem with its
  single-space reconstruction before token generation. The exact double-space
  regression was RED; 174 adjacent tests plus strict Mypy and Ruff are green.

Nothing here approves a batch. Q2 stays Julia's.
