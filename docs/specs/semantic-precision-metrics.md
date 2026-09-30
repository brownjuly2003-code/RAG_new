# Semantic precision metrics — pre-registered development ruler

Registered 2026-09-30 under [`plan_final_30_09_26.md`](plan_final_30_09_26.md)
step 1.2, on the owner's delegation (decision D2). Applies to the
first-campaign experiments of track 3 (at most two mechanisms chosen by the
evidence-loss map of slice 2.5; 3.6 and the combination 3.7 are frozen,
decision D8) and to acceptance 4.1. It is a **development ruler**: it selects between
retrieval mechanisms on a development set. It is not a product gate. The
official phase-C gate (lexical `context_precision` ≥ 0.63 over cached
contexts, [`evaluation/ragas_eval.py`](../../evaluation/ragas_eval.py))
stays defined on its own ruler and is reported beside every number below.
Revised 2026-09-30 after the [GLM 5.3 audit](../audits/audit_glm_30_09_26_plan.md)
(GLM-1..4): κ confidence rule, primary metric per mechanism, power from the
pilot, recall pool defined after caps; and again after the
[Astra audit](../audits/audit_astra_30_09_26_plan.md) (A1–A6, A10): unit of
grading, judge protocol, evidence operationalisation, applicability, numeric
fact coverage, clustering, acceptance contract; and a third time on
2026-09-30 after the [Astra gap consultation](../audits/astra_gaps_30_09_26.md)
(G7, G8, G13, G15–G20 and the Sol/GLM proposals decided in its §5), applied
on the owner's delegation: calibration protocol, chunk address and label
migration, three outcomes with MDE, screening tier, one-shot holdout and
ledger, action and critical-error checks, generator fingerprint,
single-turn scope. Fourth revision the same night after the two audits of
the final plan ([GLM](../audits/audit_glm_final_30_09_26.md),
[Astra](../audits/audit_astra_final_30_09_26.md)): third verdict, corpus
snapshot, interval validity, closed table of deciding metrics, scenario
power, common pair mask, joint-grading cache, claim-level facts and citations.

## Why a second ruler

[P2](../evidence/p2-blinded-relevance-judgment.md) measured the official ruler
against blinded LLM relevance grades: Krippendorff α 0.8566 between judges,
per-case Kendall τ_b 0.1561 (CI95 [0.0197, 0.2880]) against the ruler —
`RULER_DOES_NOT_TRACK`. Optimising the lexical ruler further can raise it by
adding matching text or by dropping documents that carry required facts
([audit](../audits/audit_asta_30_09_26.md) §3.1).

## Relevance grades

- Scale: P2's, unchanged — 3 fully answers, 2 partly answers, 1 on topic but
  unhelpful, 0 unrelated. A document is *relevant* at grade ≥ 2.
- Source of grades, in this order of authority: (1) Julia's blind human
  grades where they exist; (2) the registered P2 lower-median consensus of
  GLM 5.3 and Sonnet 5, graded blind through `evaluation.blinded_judge`
  `build_request`; (3) the Opus 5.5 reference grades as a control only.
- Rule (decision D2, refined per GLM-1): when human grades arrive,
  quadratic-weighted κ between them and the consensus is published with a
  bootstrap CI95 clustered by case (documents of one case are dependent).
  CI entirely ≥ 0.7: the ruler is human-validated. CI straddling 0.7: the
  human sample grows to 30 cases before any semantic-gain claim and before
  acceptance 4.1; engineering runs and screening may proceed, their capsules
  carry `provisional_ruler` (Astra final-plan audit №7). CI entirely below
  0.7: every development result that used consensus grades is recomputed
  and none is reported as a semantic gain until then.
- Scope of `human-validated` (A1): the P2 sample's question classes and
  unexpanded top-5 contexts. New question classes and expanded contexts get a
  human sub-sample of at least 10 cases per class before any semantic gain is
  claimed. A second indeterminate κ after the 30-case sample leaves the ruler
  `provisional_ruler`; the owner decides what follows.
- Unit of grading (A4, G16): a grade belongs to a text and carries two keys
  — the **chunk address** `{source_id, source_revision, section_path or
  char offsets, chunker_version}` (which source the text came from; the same
  boilerplate under two sources is two addresses, not one) and the exact
  **`text_sha256`** (identity of the graded bytes) — plus `case_id` /
  `question_hash`, rubric version and judge version. P2 grades transfer only
  where the text hash matches; expanded or changed text is regraded.
  `chunk_ordinal` and normalised text are not keys: the first is unstable
  under rechunking, the second is not the graded bytes. The current
  `build_request` takes exactly five documents; slice 2.7 adds a v2 request
  for 1–10 documents with the same rubric and blinding, the text hashes
  included in the request hash.
- Label migration (G16): gold stays on the source document and its spans.
  Unchanged source + new chunking → span coverage is recomputed from the
  spans; a relevance grade is never derived for a new text, it is regraded.
  Changed or deleted source → every dependent label becomes `needs_review`;
  an ambiguous match is not a migration. Each corpus version ships a short
  migration report: labels kept, regraded, `needs_review`, dropped. No
  separate annotation database or ontology.
- Documents a mechanism newly surfaces are graded the same blind way before
  the comparison. An ungraded document counts as grade 0 only in a flagged
  pessimistic view; the deciding comparison uses fully graded arms. On
  external human-annotated sets (ConditionalQA) an element the annotators did
  not select is `unjudged`, never grade 0: selecting evidence is not an
  exhaustive relevance judgement of every chunk (Astra §5, Sol).
- Calibration protocol (G8), registered here before plan step 1.1 and reused
  by 2.7 and any later external calibration: the same exact texts and the
  0–3 rubric for human and judge; blind, shuffled lists with no judge output
  visible; a sample drawn before any grade is seen; quadratic-weighted κ with
  a bootstrap CI clustered by case; binarisation ≥ 2 chosen in advance, ≥ 3
  as a sensitivity view, never a second gate; a small pre-selected set of
  contamination controls (no evidence / supporting span removed / swapped
  evidence / plausible distractor) scored separately from the natural κ;
  ambiguous and invalid answers counted with their reasons; the rubric is
  not adjusted after a holdout result is seen; κ is stated for its rubric,
  language and context type only. The branching after an indeterminate κ is
  the rule above (10 → 30 cases, then `provisional_ruler`); the sample is not
  grown open-endedly toward a wanted κ.
- Second annotator (G15): a second trained person grades 50 relevance pairs
  from the 1.1 sample and 50 assertions from the 2.8 sample, independently
  and blind, before any discussion. Human–human κ with CI, the disagreement
  matrix and the adjudication log are published. It is a reference for
  agreement, not a mathematical ceiling: the judge's κ is not divided by it
  and thresholds are not lowered by it. Without a second person every capsule
  states that reference labels reflect one expert and that the retest
  measures self-consistency only.

## Metrics per case, then averaged over cases

| Metric | Definition | Role |
|---|---|---|
| `precision_at_5` | relevant documents among the first five reranked seeds, before parent expansion, divided by 5 (fewer than five positions count as misses) | primary ordering metric |
| `sent_precision` | relevant documents among the documents actually sent to the generator, divided by the number sent; an empty context is 0 | primary selection metric |
| `ndcg_at_5` | graded nDCG@5 on the reranked seeds before expansion (the `precision_at_5` population): gain = grade (0–3), discount log2(rank + 1) with rank from 1, ideal ordering from all graded documents of the case (not the pair's union), seeds deduplicated by id; a case with zero IDCG is excluded from nDCG and counted | order quality — diagnostic, never deciding (Astra final-plan audit №6, №22) |
| `evidence_recall_pool` | gold evidence spans found anywhere in the final pre-rerank pool — after candidate caps and deduplication, exactly the pool the reranker receives — divided by the case's gold spans; bounded by the known gold and labelled as such | candidate coverage |
| `all_evidence_coverage` | 1 if every required evidence group of the case is satisfied by at least one of its listed alternatives in the sent context, else 0; a group is a required piece of evidence, not an inferred relation — two documents co-occurring does not prove the link | completeness of multi-hop |
| `fact_coverage` | numeric on every set: required atomic facts present in the sent context divided by the case's facts; on H/Hm the existing FULL/PART/MISS labels stay beside it as the regression view. Each case also lists its critical facts; a critical fact present in the control and absent in the arm blocks the mechanism, PART cases included | completeness of facts |
| `abstention_rate` | share of cases where the answer declines or asks to clarify | reported, not optimised |
| `abstention_correct` | on cases registered as unresolvable or ambiguous: 1 if the answer declines or asks to clarify, else 0 | correctness of refusals |

Fact presence (G23): whether a required fact is present in the sent context
or in the answer is decided by a registered matcher per fact type — numeric
facts by normalised number plus unit with a registered tolerance (dates,
weights, counts, money), textual facts by normalised-text containment, and
where containment is ambiguous by the blind judge with the same rubric; the
matcher version is part of the provenance and a changed matcher recomputes
every published `fact_coverage`. A numeric fact is registered as a claim
`{subject, value, unit, polarity, condition}` — polarity from a registered
lexicon (разрешено / запрещено / не более / не менее / только при …) — and is
present only when number + unit match inside a window that also carries the
subject and the same polarity marker: «150 кг разрешено» does not match «150 кг
запрещено» (Astra final-plan audit №18). Critical facts are never resolved by
the matcher alone: each is confirmed by the blind human check of 4.1.

Gold evidence (A5): a gold span is `{source_id, corpus_version, char_start,
char_end, normalized_text}`; it matches a chunk of the same corpus version by
offsets, or by normalized-text containment when offsets are unavailable.
Required evidence groups list their alternatives explicitly. Applicability:
every case carries its subset flags; `evidence_recall_pool`,
`all_evidence_coverage` and `fact_coverage` apply only to cases with gold
evidence, unresolvable cases are scored by `abstention_correct` and excluded
from the precision averages, and every report prints the case count behind
each metric.

Case schema (G6, G17, G18; slices 1.3a/1.3d): besides question, evidence
spans and required / critical facts, every case carries `question_origin`
(agent style A / agent style B / real ticket) and `label_origin`
(`agent_labelled` / `real_labelled`), the seed-selected source section, the
primary class (single-doc / multi-doc / aggregation / needs refusal or
clarification), overlapping flags (RU→EN, numeric facts, trap type among
false premise / out of corpus / outdated rule / conflicting documents /
dangerous goods, safety-critical), `expected_action` (answer / correct the
premise / clarify / refuse / escalate), `as_of`, the authority source of the
rule and the severity of a wrong answer. Quotas live in the plan (1.3d); an
unmet quota narrows the scope of the conclusion instead of being filled.

Candidate and token budgets are equal between arms. `precision_at_5` and
`ndcg_at_5` are computed on the reranked seeds before expansion;
`sent_precision` on the exact expanded documents the arm sends, identified by
text hash — one population per metric (№6).

## Decision rule for a development experiment

- Paired comparison against the registered control — in the first campaign
  the slice 2.5 baseline configuration: hybrid retrieval with production
  expansion, graph `off`, model routing off, the same candidate and token
  budgets, the same generator fingerprint (G33): on the frozen pool for
  post-filters (H1, H7); at the same corpus, queries and budgets for
  mechanisms that change retrieval (H2, H3, H4, H5) (A6). For a mechanism that lives only in the graph lane
  (H1: `_apply_graph_coherence` is called by `get_graph_documents_with_path`
  alone) two comparisons are registered — the ablation on the frozen
  graph-lane pool, which isolates the mechanism, and the graph lane with the
  mechanism against this hybrid control at an equal candidate budget of 40
  (H5 is that budget setting, not a mechanism), which decides SHIP (Astra
  final-plan audit №3). 10 000 bootstrap
  resamples, percentile CI, seed recorded. Cluster unit: connected components
  of the case–family graph (a multi-hop case joins every family it touches),
  registered before results together with the number of clusters; equal case
  weights. A **document family** (G22) is a registered group of source
  documents that share a source folder or topic or are linked by
  `cross_ref`; the family map of the corpus is built before 1.3a and
  confirmed by the owner with the first approved batch; the split between
  dev and holdout never separates documents of one family. Resampling cases does not remove judge bias — that is what plan
  step 1.1 is for.
- **Primary metric per mechanism** (GLM-2): each experiment's
  pre-registration names one primary metric before the run —
  `sent_precision` for selection mechanisms (H5, H3, H4, H7),
  `all_evidence_coverage` for coverage mechanisms (H1, H2); the other
  metric then enters the non-inferiority set with the same −0.02 margin.
- **Minimally useful effect:** +0.05 absolute in the primary metric with the
  CI95 lower bound of the paired difference above 0.
- **Power** (GLM-3, revised per G13 / decision D9): the development-set size
  comes from the pilot's variance of paired differences (plan 1.3c) so that a
  true +0.05 is detected and a neutral mechanism passes non-inferiority, each
  with power 0.8; the pilot gives a scenario range, the chosen mechanism's
  paired variance is refined on dev before the holdout opens, and holdout
  size, maximum budget and deciding criteria are fixed before its results.
  For every deciding metric the report publishes `n`, the number of
  clusters, the MDE at power 0.8, the CI and the achieved power, separately
  for the +0.05 check and for each −0.02 check. **The margin is not
  widened**: if the size is unreachable the owner adds independent families
  or accepts that the study detects only larger effects (MDE above MUE,
  stated). Power does not transfer between tiers — screening, sent context
  and answer measure different quantities. Illustration, not a measurement:
  with independent pairs and paired-difference variance `v`, `MDE ≈ (1.96 +
  0.84)·sqrt(v/n)`; at n = 100 and v = 0.10–0.20 that is 0.089–0.125.
  Three scenario powers are published per deciding metric before the run:
  (a) CI95 lower bound > 0 at a true effect equal to the MDE; (b)
  non-inferiority at a true zero; (c) the whole rule — point ≥ +0.05 and CI
  lower bound > 0 — at true effects +0.05 and MDE (at exactly +0.05 the point
  condition holds about half the time by construction: the study is powered
  for effects ≥ MDE, not for the composite at the MUE). Post-hoc power from
  the observed effect is printed as description, never as evidence of
  adequacy (Astra final-plan audit №12).
- **Screening tier** (G13): 300–500 `agent_labelled` questions drawn from the
  dev families only, kept apart from the human set, run retrieval-only with
  the consensus judge and the retrieval stages the mechanism needs. Judge
  grades are cached by the full request hash — `(question_hash, the ordered
  text_sha256 list of the presented set, rubric version, judge version)`:
  documents are graded jointly, neighbours and order can move a grade, so
  only an identical set in the same order is reused (Astra final-plan audit
  №19); the expected number of new requests is published before the run; a run graded by one judge because the other
  hit its limit is `single_judge`, outside the consensus (G24). It ranks
  candidates and nothing else: it cannot pass a non-inferiority check, prove
  answer safety or produce a semantic gain, and families — not questions —
  are its unit of independence.
- The thresholds +0.05 and −0.02 are chosen utility criteria, not measured
  properties; P1b's lexical deltas do not show they are reachable. The rule is
  read literally: point gain ≥ +0.05, CI95 lower bound > 0, non-inferiority
  bounds ≥ −0.02. Power is computed per check; the probability of passing the
  whole composite rule is not equated to it.
- **Non-inferiority:** `evidence_recall_pool` and `fact_coverage` may not fall
  by more than 0.02 at the CI95 lower bound; the `all_evidence_coverage`
  point estimate over the set may not fall at all (per-case losses are
  caught by the FULL→PART/MISS rule below). Any critical-fact loss on a regression case blocks the
  mechanism regardless of the averages, PART→MISS and losses inside PART cases
  included; the FULL→PART/MISS labels are reported beside it.
- **Interval validity** (Astra final-plan audit №11): the percentile cluster
  bootstrap decides only when the paired differences are non-degenerate — at
  least 10 clusters carry a non-zero difference and at least 5 % of pairs
  differ. Otherwise the interval is not evidence of non-inferiority: the
  report prints the one-sided 95 % Clopper–Pearson upper bound of the
  per-case loss rate (≈ 3/n at zero observed losses) and the metric bound it
  implies, and the metric's verdict is `INCONCLUSIVE` unless the metric was
  registered before the run as structurally invariant under the mechanism
  (for example `evidence_recall_pool` for a post-filter evaluated on the
  frozen pool), the invariance being listed in the capsule. With fewer than
  10 clusters a cluster-robust t-interval is printed beside the bootstrap and
  the more conservative bound decides.
- **Latency:** retrieve p95 delta ≤ 200 ms against the control at equal
  candidate budget (the existing graph gate), with per-stage timings
  (`pools`, `rerank`, `coherence_expand`) from the retrieval path reported.
- Absence of significance is reported as inconclusive, never as equivalence.
- Verdicts (three outcomes, D9): `SHIP_TO_HOLDOUT` (every check passed; the
  mechanism may be confirmed once on the locked holdout), `NO_SHIP` (a
  mandatory check failed with the CI outside its bound, or a critical-fact
  loss) or `INCONCLUSIVE` (a mandatory check neither passed nor failed at
  the achieved power). `INCONCLUSIVE` ends the registered study and does
  not permit enablement. No verdict changes a runtime default.
- Ledger and one-shot holdout (G7): the development set is exploratory —
  every configuration run on it, failures included, is logged with its
  config hash; the ledger starts with the first data-driven choice (the
  preliminary loss map of slice 2.5), and a register of families already
  used — H/Hm, P1b/P2, the loss-map families — is development by
  definition, the holdout drawing only from families outside it (Astra
  final-plan audit №13); one final mechanism is named before the holdout is opened;
  the holdout is read exactly once (plan 4.1). Changing the mechanism after
  seeing that result requires a new independent confirmation, and a rerun on
  the seen holdout is a regression check, never a new confirmation. A
  combination of dev winners is not confirmed by its parts (3.7 frozen). If
  two mechanisms both reach `SHIP_TO_HOLDOUT`, the one with the larger CI95
  lower bound of its primary-metric gain goes to the holdout; on a tie, the
  smaller retrieve p95 (№15) — registered here, not chosen after the fact.
- Corpus snapshot (№17): the campaign runs on one registered ingestion
  snapshot (corpus SHA, chunker version, index manifest). Live corpus updates
  do not enter it. If the snapshot must change after 1.3e, dependent labels
  become `needs_review` and the measurement contract restarts as a new
  campaign with a new holdout; results across snapshots are not compared.

## Acceptance contract (plan track 4)

Two acceptances (A3, A12). **Research acceptance (4.1)** runs the locked
holdout through the real `/api/ask` on `deproject-mac` and passes only if all
of the following hold; the verdict is `SHIP_RESEARCH`, `NO_SHIP` (a
condition failed with its CI outside the bound, or a critical error) or
`INCONCLUSIVE` (a condition neither passed nor failed at the achieved power —
not proven, not refuted: the default does not change and the campaign closes
per plan G26/D9; GLM final-plan audit №10):

- the deciding metrics are the closed table below and nothing else (Astra
  final-plan audit №5); diagnostic metrics — `ndcg_at_5`, `abstention_rate`,
  the Simulated stratum of WixQA, per-stage timings — are printed and never
  decide:

| Metric | Direction | Applies to (denominator) | Check | Interval |
|---|---|---|---|---|
| registered primary (`sent_precision` or `all_evidence_coverage`) | higher | cases with gold evidence | point gain ≥ +0.05 and CI95 lower bound > 0 | cluster bootstrap |
| the other of the two | higher | same | NI: CI95 lower bound ≥ −0.02 (coverage: point not below, FULL→PART/MISS rule) | cluster bootstrap |
| `precision_at_5` | higher | all judged cases | NI −0.02 | cluster bootstrap |
| `evidence_recall_pool` | higher | cases with gold spans | NI −0.02 | cluster bootstrap |
| `fact_coverage` | higher | cases with facts | NI −0.02 plus the critical-fact rule | cluster bootstrap |
| `abstention_correct` | higher | registered unresolvable cases | NI −0.02 | cluster bootstrap |
| `faithfulness` | higher | answered cases | NI −0.02; the blind human check decides while `provisional_judge` | cluster bootstrap |
| `answer_fact_coverage` | higher | answered cases with facts | NI −0.02 | cluster bootstrap |
| `citation_correctness` | higher | citations made; cases with none counted separately | NI −0.02, resolved by the blind human check (claim↔source) | cluster bootstrap |
| `citation_presence` | higher | answered non-refusal cases | NI −0.02 | cluster bootstrap |
| `action_correct` | higher | all cases; per action class reported | NI −0.02 over the set | cluster bootstrap |
| `critical_errors` | fewer | all cases | any **new** critical error blocks SHIP — a rule, no interval | — |
| lexical `context_precision` on H | higher | H | NI −0.02 (D6) | cluster bootstrap |
| retrieve p95 | lower | all cases, protocol below | delta ≤ 200 ms against the CI95 upper bound | bootstrap over cases |

- the interval-validity rule above applies to every row: a degenerate
  interval does not pass a check;
- no critical-fact loss on any regression case, PART cases included;
- retrieve p95 delta ≤ 200 ms at equal candidate budget — protocol (Astra
  final-plan audit №21): warm-up requests excluded, arms interleaved, at
  least 3 repeats per case, p95 with a bootstrap CI over cases, the threshold
  compared with the CI95 upper bound of the delta; absolute p50/p95
  published;
- lexical `context_precision` on H not more than 0.02 below the control; the
  0.63 threshold is printed beside it and is not a pass condition (decision D6,
  owner may reverse);
- tenant isolation and streaming parity tests green on the same build;
- both arms answer on one **generator fingerprint** (G19): generator id,
  provider and revision or digest, prompt hash, sampling parameters, token
  limits, context-assembly settings and routing mode; a changed fingerprint
  repeats the answer checks, only the unchanged retrieval part carries over —
  such a repeat is a regression check, not a second confirmation (№13);
- single-turn scope (G20): every request runs with an empty history; the
  capsule and any product claim are limited to that mode;
- actions and critical errors (G17): results are reported per
  `expected_action` and as the count and type of critical errors (wrong
  answer on a safety-critical or dangerous-goods case, confident answer
  where refusal or escalation was required, outdated rule presented as
  current); a critical error is **new** when the control does not make it on
  the same case, or when its type has not been observed in the project before
  (№12); **a new critical error blocks SHIP** regardless of the averages; a
  harm-weighted sum may be reported as description only;
- human answer checks are blind to the arm: answers of both arms are
  presented shuffled without an arm label, the label is revealed after the
  scores are entered (G34);
- semantic invariants (G12) on the dev cases already checked in 2.5: the
  required fact, the citation and the action are present; no exact-string
  comparison of whole answers. The 10 fake-LLM contract cases of slice 2.1
  test the API contract and are not evidence of model quality.

The external control (plan 1.5 + 1.5c, decision D7) is a separate
**transferability** line in the capsule, not a SHIP condition: confirmation
(point effect ≥ 0 and CI95 lower bound ≥ −0.02), convincing contradiction
(CI95 upper bound < −0.02) or inconclusive. A contradiction forbids the
transferability claim and makes the step to 4.2/4.3 an explicit owner
decision; tuning on the external result spends the control. Each base has its
own primary metric, cluster unit (ConditionalQA: document; WixQA: gold
article set), denominator (ConditionalQA: the 395 answerable questions;
WixQA: the ExpertWritten stratum decides, Simulated is diagnostic) and power
scenario from the registered pilot outside the deciding slice (№14).

Answer metrics, computed on the generated answer, not on the context:

| Metric | Definition |
|---|---|
| `faithfulness` | the phase-C judge (LLM judge with the NLI second judge) on the answer against the sent context; the phase-C condition (≥ 0.90 target) is reported as its own gate. The NLI model and threshold used here are the ones registered by plan slice 2.8 (validation against human and LLM-judge verdicts); until 2.8 closes, the pinned `mDeBERTa-v3-base-mnli-xnli` at 0.5 is `provisional_judge` |
| `answer_fact_coverage` | required facts present in the answer divided by the case's facts |
| `citation_correctness` | cited sources that are in the sent context and support the cited claim, divided by citations made; the API today emits one citation per sent document (`agent/graph.py` ~1943), not per claim, so until a claim-linked citation exists the metric is resolved by the blind human check — for each required fact in the answer, whether a listed source contains it (Astra final-plan audit №18) |
| `citation_presence` | answered non-refusal cases with at least one citation, divided by answered non-refusal cases (№17) |
| `abstention_correct` | on unresolvable cases, as above |
| `action_correct` | 1 if the answer performs the case's `expected_action` (answer / correct the premise / clarify / refuse / escalate), else 0; reported per action class |
| `critical_errors` | count and type of critical errors over the set; any new one blocks SHIP (see contract) |

Judge answers that fail the strict parser (slice 2.7) are `invalid`: excluded
from numerator and denominator, counted and listed, never scored 0. If more
than 10 % of a run's judge answers are `invalid`, that run's answer metrics
are `NOT_EVIDENCE` (№13). Before any deciding comparison the common pair mask
is registered: a case enters the paired analysis only when both arms hold
valid judge answers for it; the number and share of cases dropped per arm and
per stratum are published with a worst-case sensitivity (dropped cases scored
against the arm); a deciding metric that loses more than 10 % of its pairs, or
whose loss differs between arms by more than 5 points, is `INCONCLUSIVE` — no
SHIP without sufficient decisive data (Astra final-plan audit №17). A case
with no citations is excluded from the `citation_correctness` denominator and
counted separately (№13); `citation_presence` is a deciding metric so the
exclusion cannot hide missing citations (№17). If slice 2.8
leaves the NLI judge `provisional_judge`, the deciding faithfulness check of
4.1 is the blind human answer check already in the contract; the NLI number
and the phase-C ≥ 0.90 gate are printed with the `provisional_judge` caveat
(№18).

**Product acceptance (4.2)** repeats the latency and behaviour checks on the
deployment target against the absolute SLO the owner names (D5). Without a
named target and SLO there is no product SHIP. The per-tenant flag (4.3)
follows product acceptance only.

## Provenance every report carries

Corpus SHA-256, code SHA, full config including `RAG_RERANK_BATCH`, model and
reranker digests, graph digest and `entity_graph_status` from the retrieval
path, cached contexts, raw judge replies with request hashes, bootstrap seed,
host. Added 2026-09-30 (Astra): ingestion snapshot id and `chunker_version`
(G3), effective query with transformation type and hash (G4), routing mode
(G9), generator fingerprint (G19), embedder id / HF revision / dimension /
query and document prompts / normalisation as stamped in the index manifest
(G25 — a matching dimension alone is not a matching model), fact-matcher
version (G23), judge model / revision / rubric version (G16), the label-migration report of the corpus version (G16), residency mode
and peak host RSS (G5), the ledger entry of the configuration (G7), and for
every deciding metric `n`, clusters, MDE and achieved power (D9). A run
missing any of these is `NOT_EVIDENCE`; a field that does not apply to an arm
(graph digest and `entity_graph_status` for a graph-off arm) is printed as
`N/A`, never omitted (Astra final-plan audit №4). The embedder manifest and
its load-time check are mandatory for every arm, hybrid included (plan 2.3,
mandatory part).
