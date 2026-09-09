# GR-0.3 — the phase C retrieval baseline, split by question class

**Slice:** T-12 of stream GR (`plan_06_09_26.md` GR-0.3) · **Evidence class:**
`measured` over `agent_labelled` · **Date:** 2026-09-09 · **Rule:** (c) — a
published number with provenance. Retrieval behaviour did not change; this is
measurement of a pool that already existed.

## What landed

`scripts/ab_context_precision.py --buckets` post-processes the pinned arm-C
candidate pool `.tmp/ab_candidates_phase2_C.json` (7,692,098 bytes, 100 cases,
BGE-M3 + bge-reranker-v2-m3, production chunking — produced once on the Mac by
`scripts/ab_remote_contextual.py --stage pools/rerank --arm C`) and reports
context precision, context recall and the FULL / PART / MISS keyword status at
top-5 **per question class**. The classes come from the T-11 sidecar
`evaluation/curated_cases_question_class.jsonl`, joined by `case_id` through
`evaluation.question_class_labels.load_classified_cases`, which refuses to
start if the sidecar's pinned dataset digest has moved away from
`evaluation/curated_cases_aircargo.jsonl`.

No model, no network, no LLM: the contexts are built by the phase C code path
itself (`scripts.generator_benchmark.load_benchmark_cases` — the pool sliced at
each row's `rerank_k` = 5, the joined context capped at 6000 characters, no
parent expansion), and the two metrics are
`evaluation.ragas_eval.context_precision` / `context_recall`, the same keyword
definitions phase C published. The machine-readable report is
[`reports/gr/gr0-bucket-baseline.json`](../../reports/gr/gr0-bucket-baseline.json).

## The numbers, and the case counts that qualify them

Every number below is over 100 questions that were **agent-authored over real
documents**, still `agent_labelled` with **0 approved**, whose question classes
are **agent-assigned and likewise unapproved**. The classes are a proposal, not
a human-verified partition, and the metrics are keyword proxies, not human
relevance judgements.

| question class | cases | ctx precision | ctx recall | FULL | PART | MISS |
|---|---:|---:|---:|---:|---:|---:|
| single_hop | 99 | 0.5063 | 0.9091 | 87 | 6 | 6 |
| multi_hop | 1 | 0.5401 | 0.5000 | 0 | 1 | 0 |
| aggregation | 0 | — | — | 0 | 0 | 0 |
| global | 0 | — | — | 0 | 0 | 0 |
| all cases | 100 | 0.5067 | 0.9050 | 87 | 7 | 6 |

A class with no cases reports `null`, never `0.0000`: a bucket nobody measured
must not read as a bucket that scored zero. The case count sits next to every
row for the same reason — `multi_hop` here is one case, and one case is an
anecdote with four decimal places.

**And that is the finding of GR-0.3.** 99 of the 100 curated cases fall in a
single bucket, so this table cannot yet answer the question stream GR exists to
ask — whether the top-5 is noisy on questions answerable from one section or on
questions that need several documents. `single_hop` at 0.5063 and the aggregate
at 0.5067 are the same measurement read twice; `multi_hop` at 0.5401 over one
case (`aircargo-subject-rights-third-party-masking`, recall 0.5000, PART)
compares with nothing. The bucketed baseline is a ruler, not a comparison, and
the ruler is what this slice publishes.

The reason is on the record in T-11 and is not a labelling failure: the curated
100 were authored as single-section lookups over a templated document set where
every file carries "Обязательные поля" and "Доказательства и источники", and
the labeller correctly refused to call a list-inside-one-section question
`aggregation`. It follows that GR-0.2's **≥ 15 new multi-hop / aggregation
questions over real documents are a precondition, not optional follow-up
work** — for any bucketed comparison at all, including the GR-1 arm that will
be measured against this baseline. They need a new candidate pool, which is Mac
work; they are not built here.

## Reconciliation with the published phase C number

The aggregate had to land on the phase C.1a numbers or the harness would not be
measuring what phase C measured. It lands on them exactly: context precision
**0.5067** and context recall **0.9050**, identical to the published C.1a
baseline in `CURRENT_STATE.md` and in
[`evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json`](../../evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json),
over the same 100 cases, the same pool digest and the same top-5 / 6000-char
context contract. `tests/test_gr_bucket_baseline.py` pins that reconciliation
against literals of the published numbers, so a future edit that changes the
contexts silently will fail rather than republish a different ruler under the
same name.

The keyword FULL / PART / MISS counts (87 / 7 / 6) are **not** the D2 arm's
96 / 3 / 1: D2 measures the same pool *with* parent-window expansion
(window 2 / 3600 chars), which pulls neighbouring sections in and finds more
keywords. This report deliberately reproduces the phase C contexts, which have
no expansion. Both are the same pool; they are different configurations, and
the config block below says which one this is.

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
| Code commit | `69a5140461c52e41aaaa9085e3d2997b517a619c` |
| Config | top_k 5 · context_chars 6000 · parent_expansion off · grade_docs off · metrics `evaluation.ragas_eval` · statuses `ab_remote_contextual._kw_status` · per-case rounding to 4 decimals, then the mean |

The pool is gitignored, so its digest is the only thing that ties this table to
the bytes it was computed from; it is the same digest phase C.1a recorded as
`contexts_sha256`. The code commit is HEAD at the time of the run, and the
report records `tree_clean: false` because the code that produced it is the
working tree of this slice, committed immediately after. That is why the report
also carries a sha256 of each of the five files that decide the number
(`scripts/ab_context_precision.py`, `scripts/generator_benchmark.py`,
`scripts/ab_remote_contextual.py`, `evaluation/ragas_eval.py`,
`evaluation/question_class_labels.py`) — those digests are verifiable from the
commit this capsule lands in, whatever HEAD was one second earlier.

## Reproducing it

```
python scripts/ab_context_precision.py --buckets
```

The report body carries no timestamp and no run id, so a second run over the
same inputs reproduces the *measured* body byte for byte — the per-class rows,
the aggregate, the per-case table, every digest and the whole config block. A
diff in any of those means an input moved. Two fields are deliberately exempt:
`provenance.code.commit` and `provenance.code.tree_clean` are provenance, not
measurement. They record which HEAD and which working tree produced the file,
so they change whenever HEAD changes — including at the very commit that
publishes this report. A report that froze them would be lying about which code
ran.

That is also what `tree_clean: false` in the committed report means: it was
produced from the working tree of this slice, before the commit that publishes
it existed. So the field to check is not `commit` — it is the five per-file
SHA-256 digests in `provenance.code.files`, which pin the code that actually
computed these numbers exactly, clean tree or not.

`tests/test_gr_bucket_baseline.py` asserts that determinism, the per-class rows
over a synthetic pool (including a class with zero cases), the refusal when the
sidecar's pinned dataset digest disagrees with the dataset, and that the numbers
in this capsule are the numbers in the committed JSON.

## What this is not

- **Not a retrieval result.** Nothing was re-ordered, filtered or narrowed. The
  arm that will do that is GR-1, and this table is what it must be compared
  against — on the same pool, the same cases, with FULL / PART / MISS beside
  precision, so that a precision rise bought by dropping the answer is visible
  rather than hidden (`docs/specs/retrieval-buckets.md`).
- **Not a discriminating comparison between classes.** See above: 99 of 100 in
  one bucket.
- **Not real labelled data.** The questions are agent-authored over real
  documents, the journey labels are `agent_labelled` with 0 approved, and the
  question classes are agent-assigned with 0 approved. Q2(a) — approving label
  batches — is still Julia's, and nothing here approves anything.
- **Not a human relevance judgement.** Context precision and recall here are
  keyword coverage over the retrieved text, as defined in
  `evaluation/ragas_eval.py`. They are the phase C definitions, reused so the
  two numbers are the same ruler; they are not RAGAS-with-an-LLM.
