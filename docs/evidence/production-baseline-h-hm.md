# Production-path baseline on H and Hm, with the evidence-loss map — plan slice 2.5 (T-65)

The first baseline of the quality campaign taken through the production
retrieval path: hybrid retrieval with parent expansion over the 100
historical cases (H) and the 15 multi-document ones (Hm). The metric, retest
and timing tables come from
[`report.json`](../../reports/baseline/68c5f8d/report.json) and the loss
tables from [`loss-map.json`](../../reports/baseline/68c5f8d/loss-map.json).
The section on the judge also reads the stores and summaries kept beside
them under `judge/`; the sections on the lost Hm pairs and on the two rulers
read the exported contexts, the chunk archive and the family map.
[`tests/test_production_baseline_artifact.py`](../../tests/test_production_baseline_artifact.py)
rebuilds the report from the files of the repository and recounts the tables
and the counts of this capsule from them; what it cannot reach is named in
«What this capsule cannot show». Slice rule (c): published quality numbers
with corpus SHA, code SHA and config (section «Provenance»).

Four things to know before any number is read:

- **One judge.** The relevance grades are those of Claude Opus 5.5 alone
  (`grade_source: single_judge`). They are model labels; inter-annotator
  reproducibility is not established, and the retest below measures the
  stability of one model only. That retest passed, so `provisional_ruler` is
  `false`. Neither a model of another vendor nor a person checked a grade of
  this run; an error Opus makes every time is invisible here.
- **No answers.** The run stops after grading: nothing is generated. It
  measures retrieval, rerank and the sent context, and says nothing about
  answers, citations or actions.
- **Points, not intervals.** Under the registered family map H is 4 clusters,
  one of them 94 of the 100 cases, and Hm is 1. No interval of either subset
  says how well a number is known. The points are read as points, and no
  decision rests on an interval of this run.
- **Two rulers that do not agree.** The judge's grades and the loss map read
  the same contexts and do not rank the cases alike (section «The two rulers
  side by side»). The loss map works on keyword proxies, by one rule for H
  and a stricter one for Hm, and what is said about mechanisms rests on it
  alone.

Words used below:

- **Pool, seeds, sent context.** The pool is what the reranker reads: the 20
  nearest chunks by vector and the 20 best by BM25, merged and deduplicated —
  at most 40. The seeds are the five chunks the reranker keeps. The sent
  context is what is left after parent expansion and the production filter.
- **Grading and the judge.** Grading (stage `grade` of the collector,
  `grading` of the loss map) is the production filter: `qwen2.5:7b` reads the
  documents of a context and drops the irrelevant ones. The judge is another
  model at another time: Claude Opus 5.5 gives each text a relevance grade
  from 0 to 3, which the judged metrics read. The judge filters nothing.
- **The working session** is the Claude Code session that ran the
  collection, the judge passes and the tests on the host, and wrote this
  capsule. A **CLI session** is one isolated request to the judge.
- **The plan** is [`plan_03_10_26.md`](../../archive/docs/specs/plan_03_10_26.md). Its labels
  used here: slices and steps by number — 2.5 this baseline, 1.3d the
  development set with gold spans, 3.1–3.6 the mechanism experiments of
  track 3, 2.8 and 4.1 the checks of answers and the acceptance; H1–H11, the
  mechanism hypotheses; G1, G2, G3 and G12, gaps the plan asks this slice to
  report on — generator dominance, the RU→EN stratum, losses at expansion,
  the semantic invariants of an answer; D6 and D8, decisions of the owner —
  the 0.63 gate is no condition of a decision, and the first campaign runs at
  most two mechanisms and freezes the others.
- **Phase C, P2, GR-3.** Earlier measurements on H and Hm. Phase C is the
  evaluation harness whose archived contexts were unexpanded; P2 graded its
  top five by a consensus of two other models;
  [GR-3](gr3-graph-lane-ab.md) compared the graph branch with the hybrid
  path.

## What was run

- **Population.** H 100 + Hm 15, reported apart; no pooled number. All 115
  cases were collected: the collection excluded none. One H case then leaves
  the three judged metrics and a second leaves `ndcg_at_5` (column
  «Excluded» and its note below).
- **Path.** The production path at the defaults of `config/settings.py`:
  `hybrid` retrieval, graph `off`, model routing off, HyDE and agentic mode
  off, single-turn. The model rewrites the question and the search runs on
  the rewrite — it did in all 115 cases, and the effective queries are in
  the report. Then 20 candidates from each of two lanes, vector and BM25
  (`retrieval_top_k`), merged by RRF with k = 60 and deduplicated into a
  pool of at most 40; rerank to five seeds (`rerank_top_k`); parent
  expansion with window 2 and at most 3 600 characters; then grading. One
  setting is the run's and not a default: the reranker reads the pool in
  batches of 8, where the product leaves the library's batch size.
- **Models.** `qwen2.5:7b` (Ollama 0.33.2) for the rewrite and for grading;
  embedder `BAAI/bge-m3`, 1 024 dimensions, normalised, no prompts; reranker
  `BAAI/bge-reranker-v2-m3`. Everything on the CPU.
- **Index.** The 5 589 chunks of the tracked archive
  `evaluation/gr1b-4436d61-graph-chunks.json.gz`; the embedder manifest
  matched at load for every case (`eligible: exact manifest match`).
- **Contexts.** Five seeds a case. The sent context holds on average 4.77
  documents on H (at least 2) and 4.8 on Hm (at least 3) — 10 787 and 12 861
  characters.
- **Host and time.** `deproject-mac`, the ssh name of the host the report
  calls `iMac-Julia.local` (i5-7500, 4 cores, 8 GiB, macOS 13.7.8), from
  commit `68c5f8d`, started 2026-10-04 10:11 UTC; 67 132 s of stage time,
  61 756 s of it grading.

## Numbers

Relevance is grade ≥ 2 on the 0–3 rubric `p2-0-3-v1`. `precision_at_5` reads
the five reranked seeds before expansion; `sent_precision` reads the
documents left after grading. `ndcg_at_5` reads the same five seeds in their
order, the grade as the gain, against an ideal order the ruler takes from
every graded text of the case — here the seeds and the documents of the sent
context, expanded forms among them (note «nDCG» below). `context_precision`
is the official lexical ruler over the sent context — the question as asked,
the case's `expected.answer_contains` as keywords; `context_precision_seeds`
is the same function over the five seeds.

| Subset | Metric | Point | Cluster bootstrap | t-interval | Read: wider bound | Case bootstrap | n | Clusters | Excluded |
|---|---|---:|---|---|---|---|---:|---:|---:|
| H | `precision_at_5` | 0.5354 | [0.5293, 0.6500] | [0.5157, 0.5550] | [0.5157, 0.6500] | [0.4768, 0.5960] | 99 | 4 | 1 |
| H | `sent_precision` | 0.6247 | [0.6216, 0.7000] | [0.6124, 0.6371] | [0.6124, 0.7000] | [0.5662, 0.6828] | 99 | 4 | 1 |
| H | `ndcg_at_5` | 0.7638 | [0.7154, 0.8184] | [0.7546, 0.7729] | [0.7154, 0.8184] | [0.7419, 0.7849] | 98 | 4 | 2 |
| H | `context_precision` | 0.5436 | [0.5220, 0.5973] | [0.5367, 0.5506] | [0.5220, 0.5973] | [0.5121, 0.5735] | 100 | 4 | 0 |
| H | `context_precision_seeds` | 0.4578 | [0.4545, 0.5249] | [0.4466, 0.4690] | [0.4466, 0.5249] | [0.4259, 0.4882] | 100 | 4 | 0 |
| Hm | `precision_at_5` | 0.6800 | [0.6800, 0.6800] | [0.0000, 1.0000] | [0.0000, 1.0000] | [0.5733, 0.7867] | 15 | 1 | 0 |
| Hm | `sent_precision` | 0.7556 | [0.7556, 0.7556] | [0.0000, 1.0000] | [0.0000, 1.0000] | [0.6489, 0.8533] | 15 | 1 | 0 |
| Hm | `ndcg_at_5` | 0.7990 | [0.7990, 0.7990] | [0.0000, 1.0000] | [0.0000, 1.0000] | [0.7339, 0.8579] | 15 | 1 | 0 |
| Hm | `context_precision` | 0.3077 | [0.3077, 0.3077] | [0.0000, 1.0000] | [0.0000, 1.0000] | [0.2577, 0.3555] | 15 | 1 | 0 |
| Hm | `context_precision_seeds` | 0.2273 | [0.2273, 0.2273] | [0.0000, 1.0000] | [0.0000, 1.0000] | [0.1834, 0.2680] | 15 | 1 | 0 |

How to read the table:

- **Clusters.** A case's families are those of the documents the registered
  family map lists for it — for H the documents of its phase-C top five that
  P2 graded, for Hm its `source_documents`. H joins into 4 clusters — of 94,
  2, 2 and 2 cases — and Hm into 1, of all 15: nearly every case shares a
  topic family with another. Neither the map nor the rule is changed to get
  more clusters; showing that dependence is what the unit is for.
- **Intervals.** 10 000 resamples, seed 20261001, percentile CI95. With fewer
  than 10 clusters the cluster-robust t-interval stands beside the bootstrap
  and the wider bound on each side is the one the ruler reads. With one
  cluster no variance can be estimated: on Hm the bootstrap gives the point
  back and the t-interval is the whole range [0, 1]. On H the columns are no
  better. One cluster holds 94 of the 100 cases (93 and 92 for the judged
  metrics), so a resample of four clusters carries that one once, several
  times or not at all and little else varies,
  and the t-interval comes out 0.014 to 0.039 wide where the case bootstrap
  is 0.043 to 0.119 wide. The case bootstrap — every case its own cluster —
  is the ruler's sensitivity view, said to ignore the dependence the family
  map describes and to be narrower than the truth; on H it is still wider
  than the t-interval in every row, and for `sent_precision` wider than the
  bound read. None of the four columns says how well a point is known.
- **nDCG.** An expanded text is nothing the reranker ranks, yet its grade
  enters the ideal order. The ideal is above the best order of the seeds
  themselves in 97 of the 98 H cases and in all 15 of Hm, and 19 of the 20
  cases with `precision_at_5` 1.0 have an nDCG below 1.
  With the ideal taken from the five seeds alone the same grades give 0.9622
  on H and 0.9298 on Hm — a sensitivity figure, not a registered metric. The
  registered number is a diagnostic and never decides; here most of its
  distance from 1 comes from the ideal and not from the order of the seeds,
  and it moves with expansion at the same seeds.
- **Excluded.** One H case, `aircargo-harassment-investigation-timeline`,
  leaves the three judged metrics: its fourth seed is a chunk without an
  address, so that text and its expanded form were not sent to the judge and
  no grade was substituted. The case stays in the lexical metrics. The chunk
  is not a one-off. The collector addresses a chunk by its headings or,
  without a heading, by finding its text in the source file; 62 of the 5 589
  chunks, in 61 of the 201 documents, have no heading and a text the source
  does not hold as written. A case that retrieves one of them leaves the
  judged metrics, and here one did. A second H case,
  `aircargo-cargo-loss-required-fields`, has no relevant graded document, so
  its nDCG is undefined and it leaves `ndcg_at_5` only.
- **The 0.63 gate.** It is the threshold of the official lexical ruler. It is
  printed beside both lexical numbers and applied to neither: under decision
  D6 it is no condition of a decision. `context_precision_seeds` is on the
  kind of context the threshold was set on; the sent-context number is on
  expanded text.
- **Not measured, `N/A` with the reason in the report.**
  `evidence_recall_pool`, `all_evidence_coverage` and `fact_coverage`: H and
  Hm carry no registered gold spans, evidence groups or facts. Every answer
  metric and `critical_errors`: nothing is generated. MDE and achieved power:
  a single arm has no paired difference.
- **Not a comparison.** The [P2 baseline](semantic-ruler-p2-baseline.md)
  differs in the path (the phase-C harness, unexpanded), in the judge (a
  consensus of two other models) and in the graded documents. No difference
  between the two is a result.

## The judge and its stability

`claude-opus-5-5` through the Claude Code CLI 2.1.289 in safe mode — no
instruction file, memory, hook, skill, plugin or MCP server, no tools, an
empty working directory, one turn — at effort `max`, with the system prompt
whose SHA-256 is in «Provenance». Each of the 115 requests carries the 7 to
10 texts of one case in a blind order.

- **Store.** 117 attempts, 115 valid. Two attempts got no reply, each ending
  its pass — `aircargo-claims-forbidden` ran past the 1 200 s limit in the
  second pass, `aircargo-data-retention-legal-hold` ended with the CLI's exit
  in the fourth — and both requests were answered when sent again. An
  attempt without a reply gives no grade, and nothing was put in its place.
  1 102 texts were graded and 2 were not sent (above).
- **Passes** (2026-10-05, UTC). 06:55–07:05, a trial of two requests;
  08:16–09:06, 21 replies, ended by the timeout; 09:14–10:19, 25 replies,
  stopped by the working session between two replies; 14:50–15:23, 24
  replies, ended by the CLI's exit; 15:25–17:28, the last 43. A pass stopped
  from outside writes no row to
  [`runs.jsonl`](../../reports/baseline/68c5f8d/judge/runs.jsonl), so the
  third pass is there only as the 25 valid rows of the store that no pass row
  counts.
- **What left the machine.** At most 117 calls, 1 122 texts and 1 755 804
  characters to the first-party provider — every attempt counted as a whole
  prompt, the two without a reply included. The retest added 20 calls, 192
  texts and 317 932 characters.

**Stability retest.** Ten cases of H and ten of Hm, fixed by the judge plan
before any grade existed, were sent a second time in new CLI sessions and
another blind order (18:15–18:52 UTC). Only the first pass enters a metric.

| Sample | Cases | Units | Quadratic κ | CI95 | Exact agreement | Relevance flips |
|---|---:|---:|---:|---|---:|---:|
| H and Hm | 20 | 192 | 0.9281 | [0.8592, 0.9756] | 174 | 6 |
| H | 10 | 95 | 0.9585 | [0.9130, 0.9918] | 89 | 3 |
| Hm | 10 | 97 | 0.8846 | [0.7349, 0.9810] | 85 | 3 |

The rule reads one interval, that of the whole sub-sample: it lies entirely
at or above 0.7, so the grades are used as a `single_judge` ruler. The κ of a
subset decides nothing. Grades of the first pass in rows, of the second in
columns, over the 192 units:

| First \ second | 0 | 1 | 2 | 3 |
|---|---:|---:|---:|---:|
| 0 | 2 | 0 | 0 | 0 |
| 1 | 0 | 64 | 3 | 0 |
| 2 | 0 | 3 | 62 | 9 |
| 3 | 0 | 0 | 3 | 46 |

What the retest is and is not:

- It shows that one model repeats itself under another order in another
  session. It is not a second voice. The 0.7 threshold was registered for the
  agreement of two graders; for one grader with itself it is a low bar.
- The κ 0.9604 (CI95 [0.9087, 1.0000]) of the
  [P2 sample](p2-model-reference-kappa.md) is the agreement of the same model
  with the consensus of two other models on ten unexpanded cases, over the
  route as it was before it was cleaned: a probe with the same arguments
  shows such a request carrying the owner's instruction file and hook output
  beside the prompt. It is a prior for the registered route, not a
  measurement of it.
- No contamination control: H and Hm have no gold spans to cut or swap, so a
  judge that grades the subject instead of the text would not be seen.

## Timings and the host

One run on one host: `latency_evidence` is `false`, and nothing here is
speed evidence. Failed attempts are included.

| Stage | n | p50, ms | p95, ms |
|---|---:|---:|---:|
| `transform` | 115 | 8341.7 | 32166.7 |
| `embed` | 115 | 175.7 | 311.5 |
| `pools` | 115 | 132.7 | 274.6 |
| `rerank` | 115 | 30506.4 | 49942.6 |
| `total` | 115 | 30584.3 | 50181.2 |
| `expansion` | 115 | 0.1 | 0.3 |
| `retrieve` | 115 | 30596.6 | 50194.3 |
| `grade` | 115 | 507000.2 | 881887.2 |

- `pools`, `rerank` and `total` are the retrieval path's own timers.
  `retrieve` is the collector's time for that stage of one case, expansion
  included; `grade` is the production grading of the documents by
  `qwen2.5:7b`.
- The p95 of `retrieve` is this run's number without an interval. It is not
  the control of the ≤ 200 ms check, whose protocol — interleaved arms, three
  repeats a case, warm-up excluded — this run does not follow.
- **Pauses.** Two, both at a case boundary, for test runs of the working
  session on the same host: in `retrieve` after 70 cases, asked for at
  11:14:33 and in effect from 11:15:02 to 11:32:01 UTC, and in `grade` after
  3 cases, asked for at 12:23:29 and in effect from 12:25:10 to 12:34:17 UTC,
  with the model unloaded. `retrieve` and `grade` each took two attempts.
- **Foreign load.** The supervisor of the run marks a sample foreign-loaded
  when a process other than the collector, Ollama and the supervisor itself
  takes 25 % of a CPU or more. Such samples: 1 of 1 in `prepare`, 20 of 47 in
  `transform`, 0 of 5 in `embed`, 42 of 128 in `retrieve`, 578 of 2 041 in
  `grade`. They were the browser test runs of another project and Python
  processes, the test runs of the working session on the same host among
  them.
- **Peaks**, all in `grade`: 7 696 MB of memory used, 13 404 MB of swap, a
  one-minute load of 62.35, and 5 543 924 kB of resident memory for the
  collector and Ollama together.

## The evidence-loss map

`python -m scripts.evidence_loss_map --baseline-run <run directory> --chunks
evaluation/gr1b-4436d61-graph-chunks.json.gz --out
reports/baseline/68c5f8d/loss-map.json` reads the per-case records of the
run and says, for every gold term, the first stage that no longer holds it.

**The gold is a proxy, and not the same one for H and Hm.** Neither subset
has gold spans. H gold is the 200 keyword terms of
`expected.answer_contains`, looked for in every text of a stage. 122 of them
are a single word, and a single word can be held by a chunk that is not the
evidence: «held» is the most this rule can say, and the 91 of 100 below is
an upper bound on what arrived. Hm gold is the 32 pairs (term, document) of
`answer_sources`, looked for only in texts of that document; 29 of the 32
terms are written in Latin letters alone, 28 of them phrases of two or three
words. The Hm rule is the stricter one, so a row of H and a row of Hm are
not one scale. A term the sent context holds is
`no_observed_loss` whatever the earlier stages show. A wrong label or a cut
span can still be missed.

| Subset | First loss | Cases | Terms |
|---|---|---:|---:|
| H | `index` | 0 of 100 | 0 of 200 |
| H | `index_to_pool_unknown` | 3 of 100 | 4 of 200 |
| H | `caps_dedup` | 0 of 100 | 0 of 200 |
| H | `rerank` | 6 of 100 | 10 of 200 |
| H | `expansion` | 0 of 100 | 0 of 200 |
| H | `packing` | 0 of 100 | 0 of 200 |
| H | `grading` | 0 of 100 | 0 of 200 |
| H | `no_observed_loss` | 91 of 100 | 186 of 200 |
| Hm | `index` | 0 of 15 | 0 of 32 |
| Hm | `index_to_pool_unknown` | 11 of 15 | 15 of 32 |
| Hm | `caps_dedup` | 0 of 15 | 0 of 32 |
| Hm | `rerank` | 2 of 15 | 5 of 32 |
| Hm | `expansion` | 0 of 15 | 0 of 32 |
| Hm | `packing` | 0 of 15 | 0 of 32 |
| Hm | `grading` | 0 of 15 | 0 of 32 |
| Hm | `no_observed_loss` | 2 of 15 | 12 of 32 |

What each stage holds, loses and brings back:

| Subset | Stage | Terms held | Terms lost here | Terms gained here | Cases with every term | Cases losing a term here |
|---|---|---:|---:|---:|---:|---:|
| H | `index` | 200 of 200 | — | — | 100 of 100 | — |
| H | `initial_pool` | 190 of 200 | 10 | 0 | 94 of 100 | 6 |
| H | `caps_dedup` | 190 of 200 | 0 | 0 | 94 of 100 | 0 |
| H | `rerank` | 170 of 200 | 20 | 0 | 80 of 100 | 16 |
| H | `expansion` | 186 of 200 | 0 | 16 | 91 of 100 | 0 |
| H | `packing` | 186 of 200 | 0 | 0 | 91 of 100 | 0 |
| H | `grading` | 186 of 200 | 0 | 0 | 91 of 100 | 0 |
| Hm | `index` | 32 of 32 | — | — | 15 of 15 | — |
| Hm | `initial_pool` | 15 of 32 | 17 | 0 | 3 of 15 | 12 |
| Hm | `caps_dedup` | 15 of 32 | 0 | 0 | 3 of 15 | 0 |
| Hm | `rerank` | 9 of 32 | 6 | 0 | 1 of 15 | 6 |
| Hm | `expansion` | 12 of 32 | 0 | 3 | 2 of 15 | 0 |
| Hm | `packing` | 12 of 32 | 0 | 0 | 2 of 15 | 0 |
| Hm | `grading` | 12 of 32 | 0 | 0 | 2 of 15 | 0 |

- **No index loss.** Every term is held by a chunk of the index, so no
  ingestion fix precedes the baseline. For H this is the weakest row of the
  map: a term is looked for in all 5 589 chunks.
- **Expansion (G3).** Parent expansion loses nothing and brings terms back:
  16 terms in 11 cases of H, 3 pairs in 3 cases of Hm. Packing and grading
  lose nothing.
- **`index_to_pool_unknown`** — «before the pool» below. Neither the 20
  vector candidates nor the pool holds the term. The collector records no
  BM25 candidate ids, so the artifacts cannot tell a term no lane retrieved
  from a term the caps and the deduplication removed. The cause of these
  losses is unknown by construction.
- **The query rewrite.** The map has no stage for it. That no loss is
  attributed to the rewrite is the rule of the map and no finding: the
  search ran on the rewritten query in all 115 cases, and a term first lost
  before the pool may have been lost there.
- **Not observable.** The caps and the coherence filter of the graph lane
  (the run is graph `off`) and the answer (nothing is generated).

**The RU→EN stratum (G2)** under the registered rule
`cyrillic-query-missing-latin-fact-token-v1` — a Cyrillic question and a
Latin token of a gold term that the question does not contain:

| Subset | Stratum | Cases | `index_to_pool_unknown` | `rerank` | `no_observed_loss` |
|---|---|---:|---:|---:|---:|
| H | inside | 52 | 2 | 5 | 45 |
| H | outside | 48 | 1 | 1 | 46 |
| Hm | inside | 14 | 10 | 2 | 2 |
| Hm | outside | 1 | 1 | 0 | 0 |

On H 7 of the 9 cases with a loss are inside the stratum: 7 of its 52 cases
against 2 of the 48 outside, and by terms 11 of 104 lost inside against 3 of
96 outside. Of the 14 lost H terms 11 are written in Latin letters alone —
11 of the 93 such terms against 3 of the 107 others. On Hm the stratum is 14
of the 15 cases and shows nothing apart; with 29 of the 32 terms in Latin
letters, «a question over several documents» and «a Russian question for a
Latin term» cannot be told apart there. These are counts over 9 and 13 cases
with a loss, and no interval stands behind them. Under the proxy of the
[preliminary map](evidence-loss-map-prelim.md) the H stratum is 55 cases with
the same 7 losses. The preliminary map read archived phase-C contexts, not
this path: its 13 H cases with a loss and the 9 here are not a paired
comparison.

## Where the lost Hm pairs are

Read from the loss map, the exported contexts, the chunk archive and the
family map. A «seed document» is a source document of one of the five seeds.

| Lost pair | Its document | Pairs | Of them: pairs whose document one explicit `cross_ref` link from a seed document reaches |
|---|---|---:|---:|
| first lost before the pool | among the seeds, through another chunk | 3 | 0 |
| first lost before the pool | in the pool, not among the seeds | 6 | 1 |
| first lost before the pool | not in the pool | 6 | 2 |
| first lost at the rerank cut | in the pool, not among the seeds | 5 | 0 |

Counted by document and not by term, the 15 cases name 32 gold documents: the
pool holds 26 of them, the five seeds 15, and the sent context the same 15 —
expansion brings no new document. The 32 are pairs of a case and a document
over 13 files, and three of the files —
`05_tlog_contract_carrier_liability.md`, `05_tlog_contract_transport_road.md`
and `05_tlog_contract_transport_air.md` — carry 9 of the 20 lost pairs.

| Gold documents of a case | In the pool | Among the seeds | In the sent context | Cases |
|---:|---:|---:|---:|---:|
| 2 | 1 | 0 | 0 | 4 |
| 2 | 1 | 1 | 1 | 2 |
| 2 | 2 | 1 | 1 | 4 |
| 2 | 2 | 2 | 2 | 3 |
| 3 | 3 | 1 | 1 | 1 |
| 3 | 3 | 2 | 2 | 1 |

- The pool lacks a gold document in 6 of the 15 cases; in the other 9 it has
  them all, and the five seeds keep them all in 3. In 4 cases no gold
  document reaches the sent context.
- 14 of the 20 lost pairs lie in a document the pool already holds. The
  document was found; the passage with the term was not retrieved, or its
  document was cut at rerank. For 3 of them the document reached the sent
  context and the passage with the term did not.
- The five seeds come from few documents: from one document in 2 cases, two
  in 4, three in 6, four in 2 and five in 1.

## The two rulers side by side

The judged metrics and the loss map read the same contexts and ask different
questions: the judge, how much of what was sent is relevant; the map,
whether a named term arrived. They do not rank the cases alike.

| Subset | Cases | Judged cases | `precision_at_5` | `sent_precision` |
|---|---|---:|---:|---:|
| H | the map shows a loss | 9 | 0.5111 | 0.7333 |
| H | no observed loss | 90 | 0.5378 | 0.6139 |
| Hm | no gold document in the sent context | 4 | 0.7500 | 0.8000 |
| Hm | a gold document in the sent context | 11 | 0.6545 | 0.7394 |

- By the judge Hm stands above H on all three judged metrics; by the map Hm
  is where the losses are.
- A context can be relevant throughout and hold no gold pair:
  `aircargo-gr-road-air-handover` keeps 0 of its 2 pairs, and both its
  precisions are 1.0. The four Hm cases without a gold document in the sent
  context score above the eleven with one on both precisions, and the nine H
  cases with a loss have the higher `sent_precision`. The groups are 9 and 4
  cases: this is a description, not an estimate.
- Two readings fit, both may hold, and this run cannot tell. Either the
  proxy gold is narrower than the evidence — a pair is one phrase of one
  document, and another passage may answer the question — or the judge
  gives grade 2 to a text on the subject that lacks the fact. In both,
  precision is no measure of completeness.
- What follows about mechanisms rests on the map alone. The judged metrics
  do not confirm it, and gold spans (step 1.3d) may change it.

## Mechanisms for the first campaign

The plan (decision D8) lets the map choose at most two mechanisms of
track 3, «by the losses that can be removed and by cost». The default is
step 3.1 (H1) with step 3.2 (H5) as the budget setting of its branch; steps
3.3–3.5 replace them only where the map points at entity ranking,
cross-references or the category.

**Outcome: the plan's default stands — H1 inside the graph branch
(step 3.1), with the candidate budget of 40 (H5, step 3.2) as its setting.
The map did not choose it; it gives no ground to replace it.**

What the map measured, on the hybrid path alone:

- On H 91 of 100 cases reach the sent context with every term; on Hm 2 of 15
  do, and 20 of 32 pairs are lost. The two rows are not one scale: the H rule
  is the looser one, and Hm is a single cluster of 15 cases, 14 of them
  RU→EN. That Hm loses more is what the proxies show. That the cause is the
  number of documents a question needs is not shown.
- Where a term is lost, it is first lost before the pool more often than at
  the cut. The first loss is before the pool for 19 of the 34 lost terms (14
  of the 22 cases with a loss) and at the rerank cut for 15 (8 cases): on Hm
  15 of the 20 lost pairs go before the pool, on H 10 of the 14 lost terms at
  the cut. What loses a term before the pool is unknown (above).
- Most lost Hm pairs sit in documents the pool already holds (14 of 20): the
  document was found and the passage with the term was not, or its document
  was cut at rerank.

What that says about the default:

- **H1 (step 3.1)** changes the coherence filter of the graph branch — a
  soft preference where a lone chunk is now dropped — and the run is graph
  `off`: the candidates, the caps and the filter of that branch are not
  observed. The loss H1 was written against, full coverage on Hm falling
  from 4 cases to 1 when the branch was switched on in GR-3, is a loss of
  that branch and not one this map contains. The branch adds lanes to the
  pool, and a loss before the pool is where added candidates could act;
  whether they do is what the two registered comparisons of step 3.1
  measure. H1 is the plan's default left standing, not a measured gain.
- **H5 (step 3.2)** is the budget of that branch and no mechanism of its
  own: it caps the candidates of the graph branch at 40, the size the hybrid
  pool already has at most.
- **Removable loss and cost.** The plan's criterion needs both, and this run
  measured neither for any mechanism. The map shows where a term
  disappears, not what a mechanism brings back, and no mechanism was run.
  The one bound it gives is the reach of H2 below.

**Second slot: not taken.**

- **H2, one hop over explicit `cross_ref` (step 3.4).** A hop from the seed
  documents reaches the document of 3 of the 20 lost pairs — 2 of the 6 whose
  document the pool lacks. Reaching the document is an upper bound: the
  passage with the term still has to be the one brought. The step also needs
  labelled chains in the development set — the plan makes them a dependency
  of step 3.4 through step 1.3e — and that set is not built yet.
- **H3, entity ranking (step 3.3).** The plan defines it as the ranking of
  the entity candidates of the graph branch — RU/EN aliases, a penalty for
  common nodes, exact lookup of rare entities — and it replaces 3.1. The map
  observes no entity candidate. It does show the pattern the aliases are
  about: on H a loss in 7 of the 52 cases inside the RU→EN stratum against
  2 of the 48 outside, and 11 of the 14 lost terms in Latin letters. Over 9
  cases with a loss that is a reason to keep the stratum in the map of step
  1.3d, not a ground to replace the default. The plan ties the stratum to
  the embedder in use (G2), and the mechanism that changes the embedder, H9,
  is frozen with H7.
- **H4, the category as a prior (step 3.5).** It needs the routing audit of
  step 2.6, which is conditional and has not run. The map has no stage at
  which the category acts.
- **The rerank cut.** It is the largest first loss on H — 6 of the 9 cases
  with a loss, 10 of the 14 lost terms — and the first loss of 5 of the 20
  lost Hm pairs. Counted by document, 11 of the 26 gold documents the Hm
  pool holds are not among the seeds: for 5 the passage with the term was in
  the pool and was cut, for the other 6 the pool held only other passages of
  the document. The map records the stage and nothing more — no rank and no
  score of a cut passage — so it does not say whether another selection rule
  would have kept it, and in 3 of the 6 H cases the judge finds every sent
  document relevant. The mechanism aimed at the cut, H7 — a selection rule
  over the scores of the reranker in use — is frozen in the first campaign
  (decision D8, step 3.6). The plan returns it only if steps 3.1–3.5 do not
  close the goal, with a budget of its own and a measured reason from the
  loss map. This map is an observation towards that reason and no more; the
  freeze stands.
- **Generator dominance (G1)**, which would close the retrieval campaign,
  cannot be seen: nothing was generated. For the same reason the semantic
  invariants of a real answer — fact, citation, action (G12) — which the
  plan's row of this slice lists, are not observed here; the ruler's section
  «Baseline of plan slice 2.5» leaves them with steps 2.8 and 4.1.

**What would settle the open causes.** Two things this map could not tell
are within reach of the collector and not of a mechanism: a record of the
BM25 candidates would tell a term no lane retrieved from one the
deduplication removed, and a search on the question as asked would show what
the rewrite costs. Gold spans (step 1.3d) replace the keyword proxy and give
neither.

The outcome is read again when the map is rebuilt after step 1.3d, on cases
that carry gold spans.

## What this capsule cannot show

- **The `collection` block of the report** — stage seconds, pauses, host
  peaks — comes from the supervisor's state and the host samples. The samples
  name other processes of the host, so neither file is committed: their
  SHA-256 are in «Provenance», and the test rebuilds every other part of the
  report.
- **The loss map** pins 1 785 files by SHA-256: the tracked chunk archive
  and the 1 784 files of the run directory, which the repository does not
  hold. Built again from that directory at the commit of the report, it gave
  the same bytes. The test checks that its summaries follow from its
  per-case rows, and recounts from tracked files the sections «Where the
  lost Hm pairs are» and «The two rulers side by side» and the counts of
  «Mechanisms for the first campaign».
- **Numbers the test does not hold.** The 25 % of the foreign-load rule is
  the supervisor's, and the supervisor is not committed; what the foreign
  processes were is read from the host samples. The 62 chunks without an
  address were counted with the collector's address rule over the chunk
  archive and the 201 source files, each at its registered SHA-256; the
  repository does not hold the corpus.
- **A cold read is not a second voice.** An isolated session of the same
  model read the first version of this capsule against the two files, the
  rules and the plan on 2026-10-05. It found every table cell in agreement
  with the files and fourteen faults of reading — conclusions the numbers
  did not carry and numbers whose meaning was not said — which this version
  answers. It is one model reading its own work.
- **Absolute paths.** `manifest.json`, `collector-report.json` and
  `report.json` keep absolute paths of the collection host — the snapshot
  `/Users/julia/RAG_new_t65_baseline_7d2535f8876f`, and in the manifest also
  the index directory and the interpreter — and the last two its host name.
  They identify the files of that run; they are not locations in this
  repository.
- **The judge plan** is kept packed, as `judge/plan.json.gz`; unpacked it has
  the SHA-256 the stores and the report name.

## Provenance

| What | Value |
|---|---|
| Run identity: SHA-256 of the canonical JSON of `manifest.json` | `6b30fbbc25bb5e08c7b5ff0ebcfe4dcec3f3e92bda69fdf105127593d2581550` |
| Code of the collection | `68c5f8d16354771a9648c9486efdc89669011e1d` |
| Corpus SHA-256 | `c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343` |
| Chunk archive, the ingestion snapshot | `2a9da515a4c69b46453a59ed6d0bb772b0aad6fed23c87ee465851b43dbdef12` |
| H dataset, 100 cases | `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720` |
| Hm dataset, 15 cases | `0949d7563983b96500074e61f10274b28cb9341612206e02733a59b5c7968f5f` |
| Config of the run, registered as its entry `T-68/2.5a` | `843772da5793c8762ec1e0b14933740717059bd228d5787825dbab9fd8aa28e0` |
| `qwen2.5:7b`, digest | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` |
| `BAAI/bge-m3`, revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| `BAAI/bge-reranker-v2-m3`, revision | `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` |
| Judge system prompt | `2845935202ebc7963c0a6cb9efe7c51a975fae41dadd50cfca7acc7ce25ce76d` |
| Judge plan, unpacked | `727ca9386ac61e86960a960c5bdc80634821853d3ca447f4088dc17d309a2aca` |
| Store of the first pass, `judge/opus.jsonl` | `3cf525c2213f107d188a4dc6c20fa01eb9b5fd753fa441ac3a2a453c95615f17` |
| Store of the retest, `judge/opus-retest.jsonl` | `4601060c0efbd8aaa976bd1d92e2a4a1a5287cd378002c9875b75273913d87a3` |
| `judge/ruler-input.json` | `9b70a2a8b10f631746652bcda17b566fd654e08ab492c658552076670a4883f7` |
| `judge/opus-retest.json` | `ba239696658b216f92d4740ff6ce2d12dccb0a4542942a3acf4da6c1b47029c9` |
| Content of `contexts.json.gz`: SHA-256 of its canonical JSON | `5a10491c9b6ee5f4f032e90536d6505cd0276dd96e5c00d76751baa72f851adc` |
| `collector-report.json` | `3db5ad1624dbda2096f111ddb2002f2470be6f91d457e1d3d2d7e86e7a7879e4` |
| Family map, `evaluation/document_families.json` | `54bdb736180e00325bff20f49e2b9d985dd62278fe9f9cdb6161a0da719e3584` |
| Supervisor state, not committed | `197ed4152ac75aebdddd90bfdd535906f3cf8728cebf4f45abf22b095649d743` |
| Host samples, not committed | `916bea55913451e0f76722728ae9406bd993800547732708929984f9f039e0e3` |
| `report.json` | `eae9748a9f178e452c8b104c4e062cdb9a3c25247d2377a033daf5687f8f3967` |
| `loss-map.json` | `d600072bd3b6a734fe52d9d151f63f1be3f8dceac9075a9fad45f65fc50bcb25` |
| Code of the report, tracked tree clean | `5d8621327c68572c01697581334f8c67ca39208d` |

- **Seeds.** 20261001 for the metric intervals, 20260925 for the retest κ.
- **Corpus and archive.** «Corpus SHA-256» is the `corpus_sha256` of
  `evaluation/aircargo_corpus.manifest.json`: the SHA-256 over the lines
  «name, SHA-256» of the 201 source files, sorted by name. The chunk archive
  is the chunked form of that corpus, and its SHA-256 is what the index
  receipt and the ingestion snapshot name.
- **Not applicable, printed as `N/A` in the report.** Graph digest and
  `entity_graph_status` (graph off), generator fingerprint (no generation),
  label-migration report (the registered corpus is unchanged).
- **Residency.** Separate stage processes; the model unloaded after
  `transform` and `grade`; embedding and rerank on the CPU. Peak resident
  memory of the collector alone: 2 837 811 200 bytes.
- **Ledger.** The collector registered the configuration as the run's entry
  `T-68/2.5a` before its first case. Entry 2 of the
  [development ledger](../../evaluation/dev_ledger.jsonl) records the run as
  a use of the H and Hm families, with the SHA-256 of the report.
- **Rules.** [The development ruler](../specs/semantic-precision-metrics.md),
  sections «Relevance grades» and «Baseline of plan slice 2.5»;
  [the loss map](../specs/evidence-loss-map.md); the collection and the
  judging are told in [the handoff](../../archive/docs/operations/t65-baseline-handoff.md).
