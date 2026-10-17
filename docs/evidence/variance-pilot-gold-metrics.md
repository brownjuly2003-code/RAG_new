# Variance pilot of the gold metrics on the production path — plan step 1.3c

Three runs of the production retrieval path over the 24 verified pilot cases
that carry gold evidence: the registered control and two perturbations of
it. The pilot exists to show how far a paired difference of a gold metric
spreads between two arms — the interval of the decision rule is made of such
differences — and what a case costs in seconds. The estimates and the
registered MDE come from
[`measure.json`](../../reports/variance-pilot/768a195/measure.json); the
evidence of each arm lies beside it in
[`control/`](../../reports/variance-pilot/768a195/control),
[`pool30/`](../../reports/variance-pilot/768a195/pool30) and
[`sent3/`](../../reports/variance-pilot/768a195/sent3), each with a file
`model-requests.json` that lists what the arm asked the model.
[`tests/test_variance_pilot_artifact.py`](../../tests/test_variance_pilot_artifact.py)
rebuilds the measure from these files and recounts the tables and the counts
of this capsule; what it cannot reach is named in «What this capsule cannot
show». Slice rule (c): published numbers with corpus SHA, code SHA and
config (section «Provenance»).

Seven things to know before any number is read:

- **No verdict.** `pool30` and `sent3` are not mechanism candidates. Nothing
  is chosen from them, and no level of a metric in an arm is a result. The
  pilot gives the spread of paired differences and the seconds of a case.
- **The registered MDE did not move.** Every variance the pilot gives is
  below the grid value 0.10, so all 22 registered rows stay at the grid:
  0.171 to 0.303 in development, 0.224 to 0.287 in the holdout. The campaign
  is registered as checking effects of at least that size.
- **Two pairs.** On each metric of the sent context each perturbation moved
  2 of the 24 pairs, one up and one down. A variance and a correlation drawn
  from two pairs are rough, which is why the rule lets the pilot raise the
  registered variance and never lower it.
- **The filter is a draw.** The production filter gave another verdict on the
  same question and the same document in 5 of 109 documents between `control`
  and `pool30`, and in 4 of 59 between `control` and `sent3`. Three of the
  four pairs that differ on `all_evidence_coverage` come from a document both
  arms had and only one sent, not from what the perturbation changed.
- **Half of the grading time bought nothing.** In every case of the three
  arms, and in all 115 cases of the baseline of slice 2.5, the product asked
  for the grades of the whole batch twice, got one grade for the batch both
  times, and then asked document by document. The two batch requests took
  52.2 % of the grading seconds of the control.
- **One run on one host.** The seconds are those of one run on one machine,
  part of it under other load. They size a budget; they are not evidence of
  speed.
- **Labels checked by one model.** The gold spans and facts of the 24 cases
  are `single_model_verified`: drafted by the agent and checked by Claude
  Opus 5.5 under the rubric `label-verification/v2`. No model of another
  vendor and no person checked them.

Words used below:

- **Pool, seeds, sent context.** The pool is what the reranker reads: the
  nearest chunks by vector and the best by BM25, merged and deduplicated. The
  seeds are the chunks the reranker keeps. Each seed is widened by parent
  expansion into a document; the sent context is the documents left after the
  production filter.
- **The filter, or grading.** Stage `grade` of the collector: `qwen2.5:7b`
  reads the documents of a context and drops those it calls irrelevant. A
  *batch request* asks about all documents of a context at once; a *document
  request* asks about one. A request goes *with a schema* — the model is told
  to return JSON of a given shape — or *as text*.
- **Arm, perturbation, pair.** An arm is one run over the 24 cases.
  `control` is the registered control: 20 candidates from each of the two
  searches, 5 seeds. `pool30` takes 30 candidates in place of 20; `sent3`
  keeps 3 seeds in place of 5. A pair is one case in the control and in a
  perturbation; a paired difference is the arm's metric less the control's.
- **Cluster.** Cases that share a document family of the development split
  move together and count as one cluster. The 24 cases form 15: two of 4,
  three of 2 and ten of 1.
- **Grid, registered MDE.** The grid is the three variances registered
  before the pilot, 0.05 / 0.10 / 0.20. The MDE is the smallest true effect a
  comparison detects with power 0.8. The registered MDE of a metric takes the
  cases of a cluster as moving together (correlation 1) and the larger of the
  grid value 0.10 and the variances the pilot gives.
- **The three gold metrics.** `evidence_recall_pool` — the share of a case's
  gold spans that the pool holds. `all_evidence_coverage` — 1 when the sent
  context holds a span of every required evidence group of the case, else 0.
  `fact_coverage` — the share of the case's required facts that the sent
  context holds. A *critical fact* is a required fact whose loss blocks a
  mechanism.
- **The plan** is [`plan_03_10_26.md`](../../archive/docs/specs/plan_03_10_26.md); the rules
  of this pilot are in
  [the development ruler](../specs/semantic-precision-metrics.md), sections
  «The pilot» to «What the sizes cannot show».

## What was run

- **Cases.** The 24 verified pilot cases with gold evidence — 10 single-doc,
  10 multi-doc, 4 aggregation — with 38 gold spans in 38 evidence groups and
  66 required facts, 17 of them critical. The run reads ids and questions
  only; the labels stay out of it. The six refusal or clarification cases of
  the pilot carry no gold evidence and are not run.
- **Arms.** `control`, `pool30` and `sent3`, from one commit on one index.
  Apart from the one count each perturbation moves, the three manifests name
  the same code, cases, index, models and settings; the measuring tool
  refuses arms that do not.
- **Path.** The collector of slice 2.5 with its stages — query rewrite,
  embedding, retrieval with the reranker, parent expansion with window 2 and
  at most 3 600 characters, grading. Graph off. No generator and no judge.
- **Models.** `qwen2.5:7b` (Ollama 0.33.2) for the rewrite and the filter,
  `BAAI/bge-reranker-v2-m3` for the reranker.
- **Collection.** On the Mac (macOS 13.7.8, i5-7500, 4 cores, 8 GiB), from
  2026-10-05 16:44:53 to 2026-10-06 03:33:51 UTC, one arm after another:
  `control`, `pool30`, `sent3`. Every stage of every arm ran once, with no
  pause. No arm excluded a case: 24 of 24 in each.
- **Measure.** [`scripts/variance_pilot.py`](../../scripts/variance_pilot.py)
  at the commit of the runs. The test rebuilds the document with the code of
  the repository as it is now and gets the same numbers.

## The gold rule and the bound of the index

A gold span is found in a text when the text comes from the span's document
and contains the span's text whole (rule `verified-gold/text-containment-v1`).
Of the 38 spans, 37 are held whole by exactly one chunk of the index. None is
held by several chunks, so the rule never has to choose between two places.
One span, `T64-16-E2`, is held whole by no chunk: no pool can reach it, and
case T64-16 cannot reach `all_evidence_coverage` 1 in any arm. This is a
property of the labels and the chunking, the same for every arm.

## Numbers

The control, as a level: its pool held 0.8542 of the gold spans by case mean,
its sent context held every required evidence group in 12 of the 24 cases
(0.5000) and 0.6597 of the required facts. These are points on 24 cases in
15 clusters, with labels checked by one model; they are not a baseline of the
campaign.

Both perturbations are usable: all 24 pairs were measured in each, a chunk of
the index holds a gold span, and the pool of the control holds one.

`pool30` against `control`:

| Metric | Control | Arm | Mean difference | Variance | Pairs that differ | Up / down | Clusters with a non-zero sum | Correlation as it comes out |
|---|---|---|---|---|---|---|---|---|
| `evidence_recall_pool` | 0.8542 | 0.8750 | +0.0208 | 0.0104 | 1 | 1 / 0 | 1 | -1.1220 |
| `all_evidence_coverage` | 0.5000 | 0.5000 | 0.0000 | 0.0870 | 2 | 1 / 1 | 2 | -0.6540 |
| `fact_coverage` | 0.6597 | 0.6493 | -0.0104 | 0.0352 | 2 | 1 / 1 | 2 | -0.5210 |

`sent3` against `control`:

| Metric | Control | Arm | Mean difference | Variance | Pairs that differ | Up / down | Clusters with a non-zero sum | Correlation as it comes out |
|---|---|---|---|---|---|---|---|---|
| `evidence_recall_pool` | 0.8542 | 0.8542 | 0.0000 | 0.0000 | 0 | 0 / 0 | 0 | none |
| `all_evidence_coverage` | 0.5000 | 0.5000 | 0.0000 | 0.0870 | 2 | 1 / 1 | 2 | 0.3741 |
| `fact_coverage` | 0.6597 | 0.6701 | +0.0104 | 0.0678 | 2 | 1 / 1 | 2 | 0.5531 |

- **Correlation.** The intra-cluster correlation is the one-way
  analysis-of-variance estimate over the 15 clusters. Kept inside [0, 1], the
  three negative estimates of `pool30` read as 0. With two differing pairs an
  estimate says where those two pairs happened to fall, and little else. The
  largest, 0.5531, is the one the descriptive column of the next section
  uses.
- **Pool and context.** `pool30` has another pool in 24 cases and another
  sent context in 8. `sent3` has another pool in 0 cases and another sent
  context in 23. `sent3` cannot change the pool, so the 0 is the run-to-run
  noise of the stages before the reranker: none was seen.
- **Critical facts.** Each perturbation lost 3 critical facts that the
  control's context held, all in one case, T64-13.

## The registered MDE

Every variance above is below the grid value 0.10, so the registered variance
of every deciding metric stays 0.10 and all 22 rows of the registered table —
11 deciding metrics in two splits — keep `grid` as their source. The rows
differ by population only:

| Split | Population | n | Clusters | Registered MDE | Whole rule at a true +0.05 | Non-inferiority at a true zero | Gain at which it passes | MDE of independent cases | MDE at correlation 0.5531 |
|---|---|---|---|---|---|---|---|---|---|
| development | all cases | 60 | 37 | 0.171 | 0.117 | 0.045 | 0.151 | 0.114 | 0.146 |
| development | cases with gold evidence | 48 | 32 | 0.184 | 0.104 | 0.042 | 0.164 | 0.128 | 0.158 |
| development | unresolvable cases | 12 | 11 | 0.303 | 0.043 | 0.021 | 0.283 | 0.256 | 0.267 |
| holdout | all cases | 64 | 18 | 0.224 | 0.073 | 0.032 | 0.204 | 0.111 | 0.175 |
| holdout | cases with gold evidence | 51 | 18 | 0.229 | 0.071 | 0.032 | 0.209 | 0.124 | 0.182 |
| holdout | unresolvable cases | 13 | 12 | 0.287 | 0.047 | 0.023 | 0.267 | 0.246 | 0.256 |

- **Populations.** `precision_at_5`, `faithfulness`, `citation_presence` and
  `action_correct` are registered on all cases; `sent_precision`,
  `all_evidence_coverage`, `evidence_recall_pool`, `fact_coverage`,
  `answer_fact_coverage` and `citation_correctness` on the cases with gold
  evidence; `abstention_correct` on the unresolvable cases.
- **Columns.** «Whole rule at a true +0.05» is the probability that the
  primary rule passes when the true gain is the minimally useful +0.05.
  «Non-inferiority at a true zero» is the probability that a check with the
  margin −0.02 passes for a mechanism that changes nothing; «Gain at which it
  passes» is the true gain at which that check passes with power 0.8. The
  last two columns are description, not a claim of sensitivity: the MDE if
  the cases of a cluster were independent, and at the largest correlation the
  pilot gives.
- **What the sizes cannot show.** The registered MDE is three to six times
  the minimally useful +0.05. No non-inferiority check reaches power 0.8 at a
  true zero: on these rows the power is 0.02 to 0.05. A mechanism that is
  neutral on such a row is expected to end `INCONCLUSIVE`, row by row, unless
  the metric is registered before the run as structurally invariant under the
  mechanism. The interval-validity rule needs ten clusters with a non-zero
  difference; the perturbations moved 2 of 24 pairs on a metric of the sent
  context and 1 or 0 on the pool, which is the low end the ruler names. The
  margin −0.02 is not widened (decision D9).
- **Zero losses.** Counting losses instead of reading an interval does not
  help either: zero losses bound a loss rate by 0.02 only from 149 cases on.

## What moved the sent context

By the seeds and the sent documents (`addresses.json` of each arm):

- **`sent3`.** Its three seeds are the control's first three in 24 of 24
  cases, and its pool is the control's, in the same order, in 24 of 24. Of
  the documents built on those three seeds the control sent 3 that `sent3`
  did not — on seed 1781 in T64-02, 425 in T64-03 and 5151 in T64-13 — and
  `sent3` sent 1 that the control did not, on seed 454 in T64-06.
- **`pool30`.** Its pool contains the control's in 24 of 24 cases. The
  reranker kept the control's five seeds in 18 cases. In 3 of those 18 the
  sent context still differs: the arm did not send 4 documents the control
  sent, on seed 747 in T64-01, 1781 and 1799 in T64-02, and 5151 in T64-13.
  In the other 6 cases the arms share 3 or 4 seeds of 5, and 5 of them have
  another context.
- **The four pairs of `all_evidence_coverage`.** `pool30`: T64-13 fell from
  1 to 0, on a seed both arms had; T64-20 rose from 0 to 1, on seed 2706,
  which only the wider pool gave. `sent3`: T64-13 fell from 1 to 0 and T64-06
  rose from 0 to 1, each on a seed both arms had. The same four pairs are the
  ones that differ on `fact_coverage`. Three of the four come from a document
  both arms could send and one did; one comes from what a perturbation
  changed.

By the requests to the model (`model-requests.json`; one row a request, the
prompt and the reply as SHA-256). The product grades a context in steps: the
whole batch with a schema; the same batch as text when the reply does not
carry a grade for every document; then every document on its own, with a
schema, and as text when that reply is no verdict.

| Run | Cases | Batch requests | With a grade for every document | Documents in them | Document requests | With a structured verdict | Asked again as text | Kept | Dropped |
|---|---|---|---|---|---|---|---|---|---|
| `control` | 24 | 24 | 0 | 120 | 120 | 105 | 15 | 103 | 17 |
| `pool30` | 24 | 24 | 0 | 120 | 120 | 104 | 16 | 100 | 20 |
| `sent3` | 24 | 24 | 0 | 72 | 72 | 64 | 8 | 63 | 9 |
| baseline of slice 2.5 | 115 | 115 | 0 | 575 | 575 | 519 | 56 | 549 | 26 |

- **The batch step never gave grades.** In 187 of 187 contexts the first
  batch request and its repeat as text were both made, and neither reply
  carried a grade for every document: 186 of the 187 replies with a schema
  and 184 of the 187 as text held one grade, the other 4 held no list. Every
  document was then asked on its own — the document requests equal the
  documents of the batches in every run. The batch prompt ends with an
  example of the reply that holds one grade
  (`DOC_GRADE_BATCH_PROMPT_V1`, [`agent/prompts.py`](../../agent/prompts.py));
  that this is the cause was not tested.
- **A document request with a schema is asked two things.** The schema tells
  the model to return JSON; the document prompt ends by asking for one word,
  YES or NO. In 95 of the 887 document requests the reply with a schema was
  not JSON — the bare word in 89 of them — and the document was asked again
  as text.
- **Options.** Every request as text carries `temperature` 0.0 and
  `max_tokens` 256, the options of its role. No request with a schema carries
  an option: the role's temperature does not reach it.
- **Replies that repeat.** A prompt that two arms share has the same SHA-256
  in both. `pool30` shares 18 batch prompts with the control, as many as the
  cases in which it kept the control's seeds: there the filter read the same
  question and the same five documents in both arms. As text, every shared
  prompt got the same reply: 52 of 52 between `control` and `pool30` (18
  batch, 10 document, 24 rewrites), 28 of 28 between `control` and `sent3`.
  With a schema, 7 of 18 batch prompts and 10 of 109 document prompts got the
  same reply in `pool30`, and 5 of 59 document prompts in `sent3`.
- **Verdicts that change.** Of the 109 documents both `control` and `pool30`
  asked about, 104 got the same verdict and 5 were kept by the control only.
  Of the 59 that `control` and `sent3` share, 55 got the same verdict, 3 were
  kept by the control only and 1 by `sent3` only. In 5 of these 9 changes one
  of the two verdicts came from the repeat as text.
- **Rewrites.** The 24 rewritten questions are the same in the three arms:
  the rewrite goes as text, and its replies repeat.

What this says and what it does not. The verdict of the filter on a document
is in part a draw: asked twice, it differs in about one document of twenty.
Any metric read after the filter carries that draw in its paired differences,
between two arms that sent the filter the same documents as well. A metric
read before it — `evidence_recall_pool` — does not. The pilot cannot say how
much of a variance above is the draw and how much the perturbation: its
variances rest on two pairs. It does say that a comparison of two mechanisms
after the filter inherits the draw, and that the baseline of slice 2.5 is one
draw of it. What the model server does with a request that names no
temperature was not read into a file here; the replies show that it samples.

## Timings and the host

Seconds of the stages, from the supervisor's state:

| Arm | Start, UTC | prepare | transform | embed | retrieve | grade | Whole arm |
|---|---|---|---|---|---|---|---|
| `control` | 10-05 16:44:53 | 2.0 | 478.4 | 95.5 | 838.0 | 13637.7 | 15051.6 |
| `pool30` | 10-05 20:55:45 | 5.1 | 288.7 | 103.6 | 972.1 | 12422.1 | 13791.6 |
| `sent3` | 10-06 00:45:36 | 16.1 | 386.0 | 98.7 | 718.4 | 8866.0 | 10085.2 |

The three arms took 38 928 s, 10.8 hours, against an estimate of 11.

Seconds a case, median and 95th percentile, from the collector's reports:

| Stage | `control` p50 | p95 | `pool30` p50 | p95 | `sent3` p50 | p95 |
|---|---|---|---|---|---|---|
| `transform` | 19.5 | 38.7 | 8.6 | 15.9 | 9.5 | 29.5 |
| `embed` | 0.3 | 0.6 | 0.3 | 0.6 | 0.3 | 0.5 |
| `rerank` | 31.8 | 41.0 | 36.4 | 53.7 | 26.2 | 39.7 |
| `retrieve` | 32.0 | 41.1 | 36.6 | 53.9 | 26.4 | 39.9 |
| `grade` | 561.1 | 848.3 | 504.5 | 687.7 | 376.4 | 457.7 |

Seconds the model took, by what was asked (`latency_ms` of the requests):

| Run | Cases | Both batch requests | Document requests | Rewrites | Batch share of the grading |
|---|---|---|---|---|---|
| `control` | 24 | 7111.2 | 6504.2 | 473.7 | 52.2 % |
| `pool30` | 24 | 6420.4 | 5981.2 | 283.8 | 51.8 % |
| `sent3` | 24 | 5531.1 | 3325.8 | 375.6 | 62.4 % |
| baseline of slice 2.5 | 115 | 29588.5 | 32016.8 | 1411.2 | 48.0 % |

- **The batch requests.** No reply to them was used in any of the four runs.
  In the control they took 296 s of a case's 568 s of grading.
- **Scope.** `timing_scope` of every report: one run on one host, not
  evidence of speed. The median `transform` of the control is twice that of
  the other arms; it ran first, with 6 of its 16 samples under other load.
- **Other load.** The supervisor marks a sample foreign-loaded when a process
  outside the run takes 25 % of a CPU or more. Such samples in `grade`: 197
  of 452 for `control`, 81 of 411 for `pool30`, 29 of 294 for `sent3`. Among
  the processes were the gate runs of this session on the same host.
- **Peaks**, all in `grade`: memory 7 354 MB, swap 12 626 MB and load 28.4
  for `control`; 7 284 MB, 11 688.5 MB and 20.5 for `pool30`; 6 557 MB,
  11 722.5 MB and 9.5 for `sent3`.

## The budget of the campaign at the registered sizes

The plan left this recount to the pilot. It is arithmetic on the control of
one run on one host; a night is 8 hours, 28 800 s.

| Unit | Seconds a case | Cases a night |
|---|---|---|
| Up to the reranked list (prepare, transform, embed, retrieve) | 59 | 489 |
| Through grading | 627 | 46 |
| Through grading, were the two batch requests not made | 331 | 87 |

| Work | Plan, 2026-10-03 | Recounted |
|---|---|---|
| One arm through grading, no generator: development 60 cases, holdout 64 | not a row | 1.3 and 1.4 nights |
| Screening: 300 to 500 questions, three arms up to the reranked list | 3–5 | 1.8–3.1 |
| Paired comparison on development with the generator, 60 cases, two arms | 1–1.5 | 3.3 |
| Acceptance 4.1 with the generator, 64 holdout cases, two arms; with the plan's 0.7 for the H and Hm regression | 3.7, at 100 cases | 3.6; 4.3 |

- **The generator.** No answer was generated here. The two rows with the
  generator add the plan's own 176 s a case to the 627 s measured through
  grading.
- **What the table says.** Retrieval up to the reranked list is cheaper than
  the plan assumed, and anything through grading is dearer: a comparison of
  two arms through grading on development takes 2.6 nights before a word is
  generated. The third line of the first table is not a promise — it is what
  the seconds of the batch requests come to.
- **The external bases** are not recounted here: their seconds come from the
  pilot of slice 1.6.

## What this leaves open

Three things the product does on this path were seen here and are changed by
nothing in this slice: the batch step of the filter that never gives grades
and takes half of its time; the requests with a schema that carry no
temperature; the document request that asks for JSON and for one word at
once. A change of any of them changes the control: the baseline of slice 2.5
and this pilot describe the filter as it is. Whether the filter is changed
before the campaign, and the baseline taken again, is a decision of the plan
and is not taken here.

## What this capsule cannot show

- **The size of an effect.** Neither perturbation is a mechanism. A mean
  difference above is not a gain or a loss of anything.
- **How well a variance is known.** Each rests on at most two differing pairs
  of 24. The rule guards against that in one direction only: the registered
  variance cannot fall below the grid.
- **The judged metrics and the metrics of the answer.** Nothing was judged or
  generated. For `sent_precision`, `precision_at_5`, `faithfulness` and the
  other rows the grid is the only reading.
- **The unresolvable cases.** They were not run: without a generator nothing
  of them can be measured.
- **The place of a span.** The gold rule finds a span's text in a text of its
  document and cannot tell the labelled place from another place with the
  same text. No span of this set stands in two chunks, so no number here
  depends on it.
- **Labels by another hand.** One model drafted the labels and one model of
  the same vendor checked them. An error both make is invisible here.
- **Why the batch replies hold one grade, and how the server samples.** The
  first was not tested; the second was read from the replies, not from the
  server's settings.
- **Which document a changed verdict belongs to.** The request rows carry
  digests, not cases. The counts by seeds and the counts by requests agree —
  4 changed documents between `control` and `sent3` in both — and the rows
  themselves are not tied to seeds.
- **What the test cannot reach.** The seconds of the stages, the pauses, the
  other load and the peaks come from the supervisor's state and the host
  samples. They are not committed, since they name the other processes of
  the host; their SHA-256 are in «Provenance». The request files were
  extracted on the host from the runs' caches, which stay there.

## Provenance

| What | Value |
|---|---|
| Code of the collection and of the measure | `768a195900a9c2543c161fa1e933a65108582e3a` |
| Corpus SHA-256 | `c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343` |
| Chunk archive, the ingestion snapshot | `2a9da515a4c69b46453a59ed6d0bb772b0aad6fed23c87ee465851b43dbdef12` |
| Index receipt | `52f733a08d84fe238cbbc1f9ea6080db58c4f8d758a31a257c350278d47fa51c` |
| Questions of the 24 cases | `c5017d2f81f47b4751183a090d7ff505afded013335bb7f01bf3045c5edffccf` |
| Verified cases with their labels | `05ebf00743e2ae3b6a8117f735a3d9a34b451f8bf066a4dd1dfcaadf8e708df4` |
| Family map | `54bdb736180e00325bff20f49e2b9d985dd62278fe9f9cdb6161a0da719e3584` |
| Registered split | `20d69e9bb30043f7012823e3b39ca2692badc58bf9e04a737691abbcab2c44a8` |
| `qwen2.5:7b`, digest | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` |
| `BAAI/bge-reranker-v2-m3`, revision | `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` |
| Config of `control`, ledger entry 3 | `843772da5793c8762ec1e0b14933740717059bd228d5787825dbab9fd8aa28e0` |
| Config of `pool30`, ledger entry 4 | `30854f84d0db3a0ce5b3eaeb0d2bea067f267e343b5db9dec77118184699340d` |
| Config of `sent3`, ledger entry 5 | `acd57f3c28011016e0dcb634cdf2b7aa0cb5025ac06a828c27fdebd87b93c260` |
| Run identity of `control` | `0f6b8dafa7860cb40454f6cefd738d37cb99678955361f6e4b695bf425a1adfb` |
| Run identity of `pool30` | `ceb8ea1c49f4c3e1d74ea3b2f870d382948124bd497afdcf3c7638e90063ba9a` |
| Run identity of `sent3` | `32effb08da1aebb7c62b564a92087d8a6d493fdd9beddcae03f7d11148cd14b9` |
| `control/collector-report.json` | `1f8d26bcd76af57f7f13d384924a7ae1011b94ec38b027ee0583ea69934a1885` |
| `pool30/collector-report.json` | `fcbcb53a289f99b09d7b1bc42d794a1722ed36ce8e90f39767c9ad3a25fdd6f3` |
| `sent3/collector-report.json` | `6acfdb8aeb79888b917c77c1212cbb619028b3af4b50535aa09df3aa98b74da9` |
| `control/model-requests.json` | `4010cd4dd2223a20e0cd853d74a06505a692c23369f8ebe64b3a4827c2ac32c3` |
| `pool30/model-requests.json` | `197f99c9762855e05a25ae9a3db56caa03eaf3c40ba69e6bb9080f1f121d7dd5` |
| `sent3/model-requests.json` | `44f252b88ffc101a4fe1f418be10be2340a2b3eea32c5d6d2ee1c27f2c442fdb` |
| Requests of the baseline, `reports/baseline/68c5f8d/model-requests.json` | `7d0cf4afedafce67dc89e0cd8e7a523ddfaf641316d449e5b262f6f413c85176` |
| `measure.json` | `62f0802a02b353fe7284dbb1dae00276a1fc70b6714b2d360c1e77592b3b0538` |
| Supervisor state, not committed | `221edbc9ed6247b54bbe9f1a633623678eecb6b9b4b55ca00ca5ad28b2e29b07` |
| Host samples, not committed | `5311cd4b427ea4be6bb583036115208f123530aaafdf2c5172a7b33277e04eaf` |

- **Config.** `retrieval_top_k` 20, `rerank_top_k` 5, parent expansion on
  with window 2 and at most 3 600 characters, reranker batch 8, RRF constant
  60, graph off, HyDE off. `pool30` sets `retrieval_top_k` 30 and `sent3`
  sets `rerank_top_k` 3; nothing else differs.
- **Rules.** Gold match `verified-gold/text-containment-v1`, fact labels
  `pilot-claim-quote-v2`, fact matcher `semantic-ruler/claim-window-v3`.
- **Measuring code.** `measure.json` names the SHA-256 of the five files
  that built it at the commit of the runs. The test rebuilds the document
  with the code of the repository as it stands and holds it equal in every
  other key.
- **Request files.** Written by
  [`scripts/model_requests.py`](../../scripts/model_requests.py) from the
  replay cache of each run on the host. Each names the SHA-256 of the run's
  `manifest.json`, which is the manifest committed beside it.
- **Ledger.** Entries 3 to 5 of the
  [development ledger](../../evaluation/dev_ledger.jsonl) record the three
  runs with their config hashes, as development runs without a verdict.
- **Dates** are UTC.
