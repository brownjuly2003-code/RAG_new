# GR-1a — section coherence as a narrowing arm over the pinned pool

**Slice:** T-13 of stream GR (`plan_06_09_26.md` GR-1a) · **Evidence class:**
`measured` over `agent_labelled` · **Date:** 2026-09-09 · **Rule:** (c) — a
published number with provenance. Production retrieval behaviour did not
change: the arm is post-processing over the same candidate pool T-12 measured,
behind a default-off flag.

## What landed

`scripts/ab_context_precision.py --section-coherence` applies §4 п.3–4 of the
plan to the pinned arm-C pool `.tmp/ab_candidates_phase2_C.json`: candidates are
grouped by **(document, heading path)**, a chunk whose section is already
represented in the top is promoted over an isolated semantic neighbour, and the
isolated neighbour below a named threshold is **dropped rather than re-ranked**.
Selected chunks are then joined to the rest of their section as far as the pool
carries it, instead of a fixed ±1 window.

The structural signal is already in the pool. Every candidate string starts with
the contextual header the production ingest writes — `vectordb.manager.add_contextual_headers`
delegating to the no-LLM fallback in `vectordb._base_manager.add_contextual_headers`:

```
[Контекст: Из документа 07_faq_probation.md, раздел: FAQ по испытательному сроку › Вопросы и ответы › Вопрос 1. …]
```

so the arm needs no model, no corpus and no Mac. The parser is built from the
producer's own separators (`Из документа `, `, раздел: `, ` › `, `, стр. `). The
page marker is removed only when what follows it is a page number, so a heading
that contains the separator itself keeps its full path instead of being cut at
it; no header in this pool carries the marker at all, so that rule moves no
number here. And `tests/test_section_coherence_arm.py` builds its fixtures by
*calling* that producer, so the parser cannot drift into measuring itself.
Over the 1000
candidates the arm reads (100 cases × the deepest neighbourhood in the grid),
**0 headers were unparseable** and 9 candidates come from documents with no
markdown headings — those are sectionless, which is a section of its own and is
counted separately. An unreadable header would be counted, never dropped and
never merged into the sectionless bucket.

The producer also clamps its header at 200 characters, and a clamped header
still parses — the wrapper appends the closing bracket whatever it cut — so the
heading path can be truncated mid-text and two sections of one document that
share a long prefix would group as one. That would be invisible in the section
key, so it is counted rather than assumed away: 4 of the candidates the arm
reads sit exactly on the clamp. They are grouped, promoted and dropped like any
other candidate; the count is what says how far the section key can be trusted.

The machine-readable report is
[`reports/gr/gr1a-section-coherence.json`](../../reports/gr/gr1a-section-coherence.json).

## The base this is measured against, and the base the plan names

The baseline is GR-0.3 ([capsule](gr0-bucket-baseline.md),
[report](../../reports/gr/gr0-bucket-baseline.json)): the same pool, the same
100 cases, top-5, no expansion — context precision **0.5067**, recall
**0.9050**, keyword **87 / 7 / 6**. The arm's report carries that baseline
block verbatim and a test pins it to the committed GR-0.3 artifact.

`plan_06_09_26.md:147` states the GR-1 gate as «context precision @top-5 vs
0.5067 и kw FULL vs 96 %». The precision base matches; **the 96 % does not.**
FULL is 96 in the *D2 arm*, which measures the same pool **with** parent-window
expansion (window 2 / 3600 chars). The phase C contexts this stream publishes
against carry no expansion, and their measured FULL is **87**. This capsule
compares against 87, says so, and does not touch the plan's target — rewriting
a requirement under a result is not a way to meet it. Whoever closes GR-1
should decide which of the two arms the gate meant; the number here is honest
under either reading, because both movements are in every row.

## The whole grid

Threshold = the singleton section's *strength* (its reciprocal-rank score over
the neighbourhood, divided by the strongest section's). `n` is how deep into the
reranked pool "the top" reaches when support is counted; `expand` is the section
expansion. Nothing here is a magic number in the code: every cell is a named
parameter, and every cell is published.

| n | threshold | expand | ctx precision | Δ vs base | ctx recall | FULL | PART | MISS |
|---:|---:|:---:|---:|---:|---:|---:|---:|---:|
| 5 | 0.00 | off | 0.5051 | -0.0016 | 0.9050 | 87 | 7 | 6 |
| 5 | 0.00 | on | 0.5053 | -0.0014 | 0.9050 | 87 | 7 | 6 |
| 5 | 0.10 | off | 0.5051 | -0.0016 | 0.9050 | 87 | 7 | 6 |
| 5 | 0.10 | on | 0.5053 | -0.0014 | 0.9050 | 87 | 7 | 6 |
| 5 | 0.25 | off | 0.5216 | +0.0149 | 0.9050 | 87 | 7 | 6 |
| 5 | 0.25 | on | 0.5216 | +0.0149 | 0.9050 | 87 | 7 | 6 |
| 5 | 0.50 | off | 0.5745 | +0.0678 | 0.8600 | 82 | 8 | 10 |
| 5 | 0.50 | on | 0.5745 | +0.0678 | 0.8600 | 82 | 8 | 10 |
| 5 | 0.75 | off | 0.6319 | +0.1252 | 0.7600 | 71 | 10 | 19 |
| 5 | 0.75 | on | 0.6319 | +0.1252 | 0.7600 | 71 | 10 | 19 |
| 10 | 0.00 | off | 0.4884 | -0.0183 | 0.9050 | 87 | 7 | 6 |
| 10 | 0.00 | on | 0.4885 | -0.0182 | 0.9050 | 87 | 7 | 6 |
| 10 | 0.10 | off | 0.4884 | -0.0183 | 0.9050 | 87 | 7 | 6 |
| 10 | 0.10 | on | 0.4885 | -0.0182 | 0.9050 | 87 | 7 | 6 |
| 10 | 0.25 | off | 0.5021 | -0.0046 | 0.9050 | 87 | 7 | 6 |
| 10 | 0.25 | on | 0.5022 | -0.0045 | 0.9050 | 87 | 7 | 6 |
| 10 | 0.50 | off | 0.5442 | +0.0375 | 0.8600 | 82 | 8 | 10 |
| 10 | 0.50 | on | 0.5443 | +0.0376 | 0.8600 | 82 | 8 | 10 |
| 10 | 0.75 | off | 0.5895 | +0.0828 | 0.7600 | 71 | 10 | 19 |
| 10 | 0.75 | on | 0.5896 | +0.0829 | 0.7600 | 71 | 10 | 19 |

The headline row is chosen by a rule stated before the run and applied to the
whole grid: *the cell with the highest aggregate context precision among the
cells that cost no keyword coverage.* That is **n = 5, threshold 0.25, expansion
off** — precision 0.5216 against the baseline's 0.5067, recall 0.9050 and
87 / 7 / 6 unchanged, at 3.94 documents per case instead of 5. Twelve of the
twenty cells qualify; the tie with the same cell at expansion `on` is broken by
publication order, and the two are equal to four decimals.

## The reference that decides what the gain is worth

An arm that ends with 3.94 documents per case must be compared against the
cheapest narrowing there is — keeping the first *k* candidates and dropping the
rest. Same pool, same cases, same metric code path:

| naive top-k | mean docs | ctx precision | ctx recall | FULL | PART | MISS |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.00 | 0.6403 | 0.7200 | 65 | 14 | 21 |
| 2 | 2.00 | 0.5784 | 0.8400 | 79 | 10 | 11 |
| 3 | 3.00 | 0.5432 | 0.8850 | 84 | 9 | 7 |
| 4 | 4.00 | 0.5214 | 0.9050 | 87 | 7 | 6 |
| 5 | 5.00 | 0.5067 | 0.9050 | 87 | 7 | 6 |

**This is the finding.** At the headline cell, section coherence scores 0.5216
and plain top-4 scores 0.5214 with the same 87 / 7 / 6 and the same recall
0.9050. On this corpus the headline gain is *a smaller k*, not section
structure: what the arm mostly does at threshold 0.25 is drop the fifth
candidate, and a fixed top-4 does that for free. Reported as a precision gain
over the baseline alone it would look like a graph result. It is not one.

Where the arm *is* better than fixed truncation is at the aggressive end, and
only on coverage: at threshold 0.50 it holds 82 FULL at 2.13 documents per case
where naive top-2 holds 79, and at threshold 0.75 it holds 71 FULL at 1.24
documents where naive top-1 holds 65. Section coherence there behaves as a
per-case adaptive *k*: it keeps a second and third chunk when they belong to a
section the top already points at, and cuts to one when they do not. That is a
real effect, and it is bought rather than free: at threshold 0.50 the arm's
precision is 0.5745 against naive top-2's 0.5784, and at 0.75 it is 0.6319
against naive top-1's 0.6403. So the trade is 3 to 6 cases of keyword coverage
for under 0.01 of context precision — not coverage at matched precision. It is
also not enough to matter at the conservative end, where the pool's sections are
almost all singletons anyway.

**The GR-1 target of 0.63 is reached only at threshold 0.75**, where precision
is 0.6319 and FULL falls from 87 to 71 with MISS rising from 6 to 19. That is a
precision gain bought by dropping the answer, and it is a NO-SHIP for that cell
under `docs/specs/retrieval-buckets.md`, not a result to tune towards.

## By question class

99 of the 100 cases are `single_hop`, so this table cannot discriminate between
classes — the finding GR-0.3 published, unchanged. It is here because the spec
requires the classes to be reported and because the one `multi_hop` case moved,
in the wrong direction.

| question class | cases | ctx precision | ctx recall | FULL | PART | MISS |
|---|---:|---:|---:|---:|---:|---:|
| single_hop (baseline) | 99 | 0.5063 | 0.9091 | 87 | 6 | 6 |
| single_hop (headline) | 99 | 0.5226 | 0.9091 | 87 | 6 | 6 |
| multi_hop (baseline) | 1 | 0.5401 | 0.5000 | 0 | 1 | 0 |
| multi_hop (headline) | 1 | 0.4267 | 0.5000 | 0 | 1 | 0 |
| aggregation | 0 | — | — | 0 | 0 | 0 |
| global | 0 | — | — | 0 | 0 | 0 |
| all cases (baseline) | 100 | 0.5067 | 0.9050 | 87 | 7 | 6 |
| all cases (headline) | 100 | 0.5216 | 0.9050 | 87 | 7 | 6 |

The single `multi_hop` case (`aircargo-subject-rights-third-party-masking`) drops
from 0.5401 to 0.4267 with its recall unchanged: the arm demoted its top chunk
below a supported section. One case is an anecdote with four decimal places, and
it is reported for the same reason a zero-case class reports `null` and never
`0.0000` — a number nobody can generalise from must still be visible.

## Every case whose keyword status regressed

No case regresses at the headline cell. These are the cases the two aggressive
cells lose, named in full, because a list of eighteen is short enough to read
and is the only way to see what a precision number costs.

| case | at threshold 0.50 | at threshold 0.75 |
|---|---|---|
| `aircargo-templates-checklist` | FULL → PART | FULL → MISS |
| `aircargo-contract-termination-open-awb` | FULL → MISS | FULL → MISS |
| `aircargo-customs-special-cargo-manual-check` | PART → MISS | PART → MISS |
| `aircargo-sick-leave-required-fields` | FULL → MISS | FULL → MISS |
| `aircargo-late-delivery-reply-no-admission` | FULL → PART | FULL → PART |
| `aircargo-fuel-supply-evidence` | FULL → MISS | FULL → MISS |
| `aircargo-business-trip-advance-report` | — | FULL → PART |
| `aircargo-road-contract-aircargo-fields` | — | FULL → MISS |
| `aircargo-dangerous-goods-fields` | — | FULL → MISS |
| `aircargo-access-control-review` | — | FULL → MISS |
| `aircargo-employment-contract-essential-terms` | — | PART → MISS |
| `aircargo-employment-contract-special-form` | — | FULL → MISS |
| `aircargo-driver-job-documents` | — | FULL → PART |
| `aircargo-warehouse-3pl-escalation` | — | FULL → PART |
| `aircargo-data-retention-required-fields` | — | FULL → MISS |
| `aircargo-cargo-insurance-evidence` | — | FULL → PART |
| `aircargo-cargo-insurance-operational-limits` | — | FULL → MISS |
| `aircargo-gps-monitoring-required-fields` | — | FULL → MISS |

## Where expansion to the section boundary was not possible

Almost everywhere. The arm reads only what the pool carries for a case, down to
the deepest neighbourhood in the grid — 10 candidates — so "the section
boundary" is reachable exactly when a sibling chunk of the same (document,
section) was itself retrieved *and* was not already selected. At the headline
parameters with expansion on, 11 of the 394 selected chunks had such a sibling;
the other 383 had none and were left alone. That is why the
`expand` column moves the fourth decimal and nothing else, and it is a property
of the pool, not of the arm: structural chunking gives most sections exactly one
chunk, and in the top-10 of 71 of the 100 cases every candidate sits in a
section of its own. Reading the corpus to find the real section boundary is
GR-1b's job, on a new pool, on the Mac. This arm does not read the corpus and
does not pretend the ±1 window is the boundary.

## The control that proves the arm rejects nothing valid

The grid carries one cell — `n` equal to the top-k, threshold 0.00, expansion
off — in which the arm may re-order but may not remove a candidate the reranker
admitted or add a character the baseline did not carry. Its recall and its
FULL / PART / MISS are asserted equal to the baseline's, and its regression list
is asserted empty, so a change that starts rejecting valid candidates fails a
test instead of shipping as a precision gain.

That equality of coverage is not free from ordering: the context budget is one
shared character allowance spent in candidate order, so on a pool where a case
reached it, re-ordering alone could move FULL / PART / MISS without a single
candidate being rejected. Every cell of the grid therefore reports how many
cases reach that budget — zero, on this pool, in every cell — which is what
makes the control cell's equality a property of the arm rather than an accident
of truncation. A future pool where a case does reach it fails that test instead
of quietly voiding the reasoning.

That cell is also a result in itself: **section coherence used purely as a
re-ordering loses precision**, 0.5051 against 0.5067. The reranker's own order
is better than the structural prior at equal recall; the arm only pays when it
is allowed to drop.

## Provenance

| | |
|---|---|
| Pool | `.tmp/ab_candidates_phase2_C.json` (gitignored), 7,692,098 bytes |
| Pool sha256 | `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10` |
| Corpus | `data/uploads/aircargo`, 201 files ([manifest](../../evaluation/aircargo_corpus.manifest.json), T-10) |
| Corpus sha256 | `c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343` |
| Dataset sha256 | `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720` |
| Label sidecar sha256 | `cc6356b9faa46d4b952a955e1d47e9a8b15003284c42f48e7e5236471f8ff17c` |
| Label manifest sha256 | `e2010fc94ee283c29308e6fa53e522c70b57d767aacf00113628858a061f7b10` |
| Code commit | `bcb83de7a1fa0001f4caf112df959db2192c625f` |
| Baseline | [`reports/gr/gr0-bucket-baseline.json`](../../reports/gr/gr0-bucket-baseline.json) (GR-0.3) |
| Config | top_k 5 · context_chars 6000 · neighbourhoods 5 and 10 · thresholds 0.00 / 0.10 / 0.25 / 0.50 / 0.75 · expansion off and section-boundary · grouping `(document, heading path)` from the production contextual header · metrics `evaluation.ragas_eval` · statuses `ab_remote_contextual._kw_status` · per-case rounding to 4 decimals, then the mean |

Same pool digest, same dataset digest and same corpus digest as GR-0.3 — that is
what makes the two tables comparable at all. As in T-12, the report records
`tree_clean: false` and a per-file SHA-256 of the five files that decide the
number, because the code that produced it is the working tree of this slice,
committed immediately after; the file digests are what pin the code, not the
commit.

Every number here is over 100 questions **agent-authored over real documents**,
still `agent_labelled` with **0 approved**, whose question classes are
agent-assigned and likewise unapproved.

## Reproducing it

```
python scripts/ab_context_precision.py --section-coherence
```

Minutes, no model, no network. The report body carries no timestamp and no run
id, so a second run over the same inputs reproduces it byte for byte, with the
same two provenance exemptions T-12 documented (`provenance.code.commit` and
`provenance.code.tree_clean` track HEAD by design). Only the control cell and
the headline cell keep a per-case table; every other cell keeps its full
regression list and is reproducible from the same command.

`tests/test_section_coherence_arm.py` asserts the parser against the producer,
the grouping, the purity of the arm, the singleton-answer regression, the
control cell, the naive top-k reference reproducing the baseline at k = 5, and
that every number in this capsule that is a claim about this measurement — table
cells, decimals and **integers** in running prose alike — is a number the
committed JSON carries. Every table here is checked against its own section of
that JSON: the grid cells, the naive reference, the per-class buckets and the
from→to pairs of the regression list, each guard proven by mutating one of its
cells and watching it fail. Tables are found by their heading, not by their
width, because the first form of this guard read only the widest table and left
the other three unpinned while this paragraph already claimed otherwise. The counts this narrative quotes are report fields for
that reason, not arithmetic done in the prose. The few integers here that are
claims about something else — the target `plan_06_09_26.md` states, the D2 arm
measured in another report, GR-0.2's precondition, a date, a section number —
are listed — once, for both capsules — in `tests/capsule_prose.py`
(`NON_REPORT_PHRASES`), each with its reason, and each as the exact phrase it
appears in: change a digit and the exemption stops matching, so it cannot cover
a wrong number.

## What this is not

- **Not a shipped retrieval change.** Nothing in `HybridRetriever` moved. The
  arm is an offline post-processor behind `--section-coherence`, off by default.
- **Not the GR-1 gate.** 0.63 is reached only by dropping the answer in 18
  cases. Under `docs/specs/retrieval-buckets.md` that is not an improvement.
- **Not a verdict on section coherence in general.** It is a verdict on section
  coherence *over this pool*, where structural chunking leaves most sections
  with one chunk and the pool cannot see past what retrieval already returned.
  GR-1b builds a pool with the structure available at retrieval time; that is
  where the idea gets its real test.
- **Not a bucketed comparison.** 99 of the 100 cases are `single_hop`. GR-0.2's
  ≥ 15 new multi-hop / aggregation questions remain the precondition, exactly as
  GR-0.3 said.
- **Not real labelled data**, and not a human relevance judgement: the metrics
  are the keyword definitions in `evaluation/ragas_eval.py`, reused so that this
  table and phase C are the same ruler.
