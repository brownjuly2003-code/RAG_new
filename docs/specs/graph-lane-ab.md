# Capability: GR-3 graph-lane A/B and the retrieval default decision

<!-- Durable spec: it outlives the run. One capability per file; MyFlow injects the requirements a task
     references into the WorkOrder and the review pack. Format is OpenSpec-compatible. -->

GR-3 closes stream GR's measurement half (`plan_06_09_26.md` §GR-3): hybrid
against the structural lane (`G1`) against the structural plus entity lane
(`G2`) on the same cases, one generation run over graph-lane contexts under the
C.1a contract, and a decision about the `RAG_GRAPH_RETRIEVAL` default taken by
a rule written down before the numbers exist. GR-1b and GR-2 already published
`G1` and `G2` over both datasets
([capsule](../evidence/gr2-entity-graph-lane.md)); what is missing is hybrid on
the multi-document bucket, retrieval time for the hybrid arm, and any answer
quality number over graph contexts.

## Requirement: a generation run over graph contexts differs from C.1a only by its contexts

`scripts/generator_benchmark.py` SHALL run the graph-lane contexts under the
C.1a contract: model `qwen2.5:7b` at weights digest `845dbda0…`, prompt version
`aircargo-context-only-ru-v1`, 3 runs from seed 42, temperature 0, `num_ctx`
4096, `num_predict` 384, a 6000-character context cap, NLI
`MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` at `8adb042d…`, and the contexts
digest in the report. Graph pools end with fewer contexts than `rerank_k`
(section coherence keeps 2–5 of 5 on phase C). Such a pool SHALL be accepted
only under an explicit option that the report records, and every case result
SHALL record how many contexts the generator received. Nothing is padded.

### Scenario: a short pool without the option is refused
- **GIVEN** a contexts pool where one case has 3 contexts and `rerank_k` 5
- **WHEN** the benchmark loads it without `--allow-short-contexts`
- **THEN** it fails closed and the error names that case

### Scenario: with the option the report says so
- **GIVEN** the same pool
- **WHEN** it is loaded with `--allow-short-contexts`
- **THEN** that case is generated from its 3 contexts, the report config records
  `allow_short_contexts: true`, and the case result records `context_count: 3`

### Scenario: a full pool is unchanged by the option
- **GIVEN** a pool where every case has at least `rerank_k` contexts
- **WHEN** it is loaded with and without the option
- **THEN** the selected contexts are identical and only the recorded flag differs

## Requirement: every A/B arm records its retrieval time

The pools stage of `scripts/ab_remote_contextual.py` SHALL record per-case
`timing_ms` for every arm — `vector` and `bm25` for the hybrid arms, plus
`entity` for the graph arms (0 when the lane did not run) — without changing any
candidate, source or metadata it writes. The rerank stage already records
`rerank_s`, which for the graph arms includes section coherence and expansion.

### Scenario: the hybrid arm carries timings
- **GIVEN** a synthetic corpus and one case
- **WHEN** arm `C` builds its pool
- **THEN** the row has `timing_ms` with non-negative `vector` and `bm25`, and its
  `cands` and `cand_sources` equal those built without timing

## Requirement: the retrieval A/B compares hybrid, G1 and G2 on the same cases

The GR-3 report SHALL publish, per labelled class and over all cases, for both
the 100 phase-C cases and the 15-case multi-document bucket: precision, recall
and FULL/PART/MISS for each arm, the paired deltas `G1 − hybrid`,
`G2 − hybrid` and `G2 − G1`, keyword transitions with the case ids of every
loss, the mean number of contexts and characters each arm hands on, and latency
per arm — pools-stage p50/p95, rerank p50/p95 and their per-case sum. Arms over
different case sets or different queries are refused. The hybrid arm on the
bucket SHALL come from the same code and run as a phase-C hybrid re-run, and
that re-run SHALL be compared case by case with the published pool `91ce1745…`
(the pool C.1a generated from): identical, or the divergent cases are named.

### Scenario: an arm that hands on fewer contexts shows it
- **GIVEN** a hybrid arm with 5 contexts per case and a graph arm with 3
- **WHEN** the report is built
- **THEN** the mean contexts and characters per arm are published next to the
  precision they produce

### Scenario: a hybrid re-run that drifted is named, not hidden
- **GIVEN** a hybrid re-run whose reranked top-5 differs from the published pool
  in two cases
- **WHEN** the report is built
- **THEN** the parity section lists exactly those two case ids and the report
  still builds

### Scenario: the report reproduces from archived inputs
- **GIVEN** the archived pools, datasets and label sidecars
- **WHEN** a test rebuilds the report
- **THEN** every number equals the published JSON, with no model, network or
  corpus read

## Requirement: the default decision follows a rule fixed before the numbers

`RAG_GRAPH_RETRIEVAL` SHALL become `auto` by default only if, on the phase-C
cases against the hybrid pool C.1a generated from, all four hold: context
precision rose; keyword FULL did not fall; LLM faithfulness and NLI
faithfulness did not fall significantly, meaning the upper bound of the paired
case-level 95% bootstrap interval of `graph − hybrid` is not below zero; and
retrieve p95, counted as pools stage plus rerank, rose by at most 200 ms.
Otherwise the default stays unchanged and the capsule records NO-SHIP-to-default
with the criteria that failed. Both outcomes are results.

### Scenario: identical seeds do not stand in for variance
- **GIVEN** C.1a's run-level interval for LLM faithfulness is
  `[0.8295, 0.8295]` because temperature 0 makes the three runs identical
- **WHEN** the graph run is compared with it
- **THEN** the comparison uses the paired case-level bootstrap interval
  (fixed seed, published resample count), not the run-level interval

### Scenario: a latency gate that times only entity search is refused
- **GIVEN** entity search at p95 9.39 ms and reranking of the lane pool at about a
  minute per lane case on the measurement host
- **WHEN** the retrieve criterion is evaluated
- **THEN** it is evaluated on pools stage plus rerank per case, and the capsule
  names the host it was measured on
