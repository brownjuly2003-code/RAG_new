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
Fifth revision 2026-10-03 under [`plan_03_10_26.md`](plan_03_10_26.md),
decision D11 — the owner's «люди участвовать в процессе не будут» (no person
takes part in the process): wherever a person graded, approved or checked,
reference and verifier models from a vendor other than the checked side's do
it now. Changed: the source of grades, the D2 rule and its scope, the
calibration protocol, the second-annotator item, the confirmation of critical
facts, the case schema with the new «Label verification» paragraph, the
family-map registration, the power fallback, the screening tier, two rows of
the acceptance table, the blind answer check, and the `faithfulness` and
`citation_correctness` definitions. Thresholds, margins, metrics and the three
outcomes are unchanged. A model check is never reported as a human one: the
ruler's status is `model-cross-checked`, a case's is `model_verified`.
Amended the same day after a cold read of the revision: the order of the D2
branches and the CI method, no holdout on a provisional ruler, the draft
author and unavailable vendors in «Label verification», registration of the
answer checkers before the holdout opens. Eight questions it left open are
listed in plan gap G38.
Sixth revision 2026-10-04 in plan step 1.3b, before the first label check:
questions а and б of G38 are closed. «Label verification» gets the rubric
`label-verification/v1` — the two verifiers, a fifth check (currency,
authority, severity, critical facts), the decision rule, the limits of a
repair, and a wide scan of the whole index in place of the control's pool;
the acceptance contract gets the `gold_error` outcome; the family map and the
holdout reserve are registered. The draft of this revision was audited by
GPT-6-Astra before any code was written from it
([audit](../audits/audit_astra_04_10_26_label_verification.md), 22 findings,
all applied). What the tool that runs the protocol must do:
[label-verification.md](label-verification.md).
Seventh revision 2026-10-04 under plan decision D12 — the owner's «ты должен
все делать сам» (do all of it yourself): the agent of the session,
`claude-opus-5-5`, does the plan's work and its checks, and no model of
another vendor is called in any role. «Label verification» becomes rubric
`label-verification/v2`: one verifier in place of two and the status
`single_model_verified`; the repair of a rejected case by the agent in place
of the draft author, with the second check named a consistency check; a
second ground for a declared drop; an unchanged repair refused; and the three
flags the verify script computes no longer sent or judged. No verdict was
counted under v1. The rules of this file that name models of other vendors
for other steps — the judges and references of the ruler, the NLI validation,
the answer checks of acceptance — are re-registered before the step that
uses them starts, and are not run as written here.
Eighth revision 2026-10-05 (UTC) under the same decision, before the first
relevance grade of plan slice 2.5: «Relevance grades» names the judge of new
texts — `claude-opus-5-5` alone — and the status `single_judge` of every
number computed from its grades; says what was measured about this judge on
the P2 sample; puts a stability retest in the place of the reference
sub-sample for expanded contexts and new classes (question г of plan G38);
and says what a `single_judge` ruler may claim. The registered consensus, its
D2 verdict and every published number are unchanged; the answer checks of
2.8 and 4.1 are still to be re-registered.
Ninth revision 2026-10-05 (UTC), also before the first relevance grade of
slice 2.5: the new section «Baseline of plan slice 2.5» fixes what its report
computes each number on, what it prints as `N/A`, the cluster unit of H and Hm
with the number of clusters it leaves — 4 and 1 — the intervals that follow
from so few clusters, why a single arm has no MDE, and the scope of its
timings. No threshold, margin or metric changed.
Tenth revision 2026-10-05 (UTC) under the same decision, before plan step
1.3c registers a size: the five questions of plan G38 that were still open
are closed for one model. «Label verification» gets the replacement of a
dropped case (question в) and rubric `label-verification/v3` for drafts the
checking model wrote itself, with the status `single_model_self_checked`.
«Relevance grades» gets the route of the judge registered again and
contamination controls built from verified gold spans (question д). The new
section «Checks by one model in slices 2.8 and 4.1» registers the route of
every request to the one model — a session that loads nothing, kept with
its record; the reference of the NLI validation — one labeller in two
passes, the status `single_model_referenced`, a bound on unstable labels
(question е); the answer checks of acceptance — four kinds of request, a
third pass on a disagreement, a rehearsal on a development run, and who
decides the action, the abstention, a critical error and faithfulness
(question ж); what happens when the model is unavailable (question з); and
the condition for opening the holdout, which no longer asks for a
`model-cross-checked` ruler. Thresholds, margins, metrics and the three
outcomes are unchanged. The draft of this revision was read cold twice by
new sessions of the same model — the only reader decision D12 leaves. The
first read found, among other things, that a new session is not an empty
one: its own request had come with the owner's instruction file and the
output of hooks. A probe of the arguments by which the earlier requests had
been sent showed the same, and the route was rebuilt before any grade of
slice 2.5 was asked for. The second read, of the whole file by the rebuilt
route, gave 20 findings, three of them blockers: the unit of the 10 % bound
on third passes, a missing verdict that was both left out of a metric and
scored against the answer, and three denominators of
`citation_correctness`. All 20 were applied before anything ran: a verdict
has one rule of existence, a context is checked apart from the answer, a
check runs in ordered stages, a second attempt draws new cases, and the
route registers what the CLI builds in. One closed request by the same
route then set the repaired text against the 20 findings. It found 17
resolved and 3 not — a `gold_error` request that waits for a third pass,
the arm a lost pair is charged to, the draw of a second attempt in later
runs — and named 12 places where a repair contradicted another rule or
could be read two ways, one of them a blocker: which cases a missing
verdict leaves without a result. These 15 were applied as well. Nothing has
read the text since; its next reader is the code written from it.

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
- Source of grades: the registered P2 lower-median consensus of GLM 5.3 and
  Sonnet 5, graded blind through `evaluation.blinded_judge` `build_request`.
  No human grades of the blind sample exist and none are planned (plan
  decision D11, 2026-10-03; until then Julia's blind grades headed this
  list). Two model references check the consensus and never replace it as
  the source: GPT-6-Astra (OpenAI — a vendor outside the consensus) and
  Opus 5.5 (Anthropic, the vendor of the Sonnet judge — a control, not an
  independent voice). This is the source of every grade published up to
  step 1.1; texts graded from slice 2.5 on have the source named in «Judge
  of new texts» below.
- Rule (decision D2 as changed by D11, refined per GLM-1): quadratic-weighted
  κ between the consensus and each of the two model references on the blind
  ten-case sample is published with a bootstrap CI95 clustered by case
  (documents of one case are dependent): 10 000 resamples of cases, a
  percentile interval, seed 20260925 — `BOOTSTRAP_SAMPLES` and `SEED` of
  `evaluation/blinded_judge.py`, fixed before this rule. Both references must
  clear the threshold: only Astra is evidence from an outside vendor, but a
  consensus that fails against Opus fails. The branches are read in this
  order. (1) A CI entirely below 0.7 for either reference: the consensus is
  not used as the ruler — every development result that used consensus grades
  is recomputed on a re-registered judge set (there are no human grades to
  recompute on), and none is reported as a semantic gain until then. The new
  set is named before any of its grades is compared with a reference and is
  checked by this rule once, on a fresh reference sample drawn by a
  registered seed, with at least one reference from a vendor outside the set.
  (2) Otherwise, a CI straddling 0.7 for either reference: the reference
  sample grows to 30 cases — both references grade 20 more H cases drawn by a
  registered seed over the same ruler quintiles — before any semantic-gain
  claim and before acceptance 4.1; engineering runs and screening may
  proceed, their capsules carry `provisional_ruler` (Astra final-plan audit
  №7). The same branches are applied once to the 30-case κ. (3) Otherwise —
  both CIs entirely ≥ 0.7: the ruler is `model-cross-checked` — agreement
  between models of different vendors, which cannot detect an error the
  models share; it is never reported as `human-validated`. The references'
  grades and each judge's κ to them (0.88–0.91) were published before this
  rule was written, so the check is not blind to its likely outcome; the 0.7
  threshold is the one registered on 2026-09-30 for human grades and was not
  adjusted. If human grades ever arrive, the 2026-09-30 wording applies to
  them and `human-validated` becomes reachable again.
- Scope of `model-cross-checked` (A1): the P2 sample's question classes and
  unexpanded top-5 contexts. New question classes and expanded contexts get a
  reference sub-sample of at least 10 cases per class, graded by both
  references, before any semantic gain is claimed (question г of plan G38;
  no such sub-sample was graded — see the end of this item). A second
  indeterminate κ after the 30-case sample leaves the ruler
  `provisional_ruler`: no semantic gain is claimed on it and the holdout is
  not opened for acceptance 4.1 on it. The judge set is then re-registered
  once, as in branch (1); if that set does not pass either, the campaign
  closes without acceptance 4.1 and the owner decides what follows (until
  2026-10-03 the owner decided right after the second indeterminate κ).
  Since the eighth revision no reference sub-sample is graded: one of the two
  references is a model of another vendor, and the stability retest below
  takes its place. This item describes the consensus ruler of step 1.1 and
  binds no grade made after decision D12: what bars the holdout now is
  registered in «Checks by one model in slices 2.8 and 4.1».
- Judge of new texts (decision D12; eighth revision, registered before the
  first grade of slice 2.5; its route registered again in the tenth, also
  before that grade). Every text graded from slice 2.5 on is graded by one
  judge: `claude-opus-5-5` (Anthropic), asked one request at a time, each
  a new session, by the route of «Checks by one model in slices 2.8 and
  4.1» —
  `Claude Code CLI in safe mode, first-party provider`, effort `max`, session
  `safe mode: no instruction file, memory, hook, skill, plugin or MCP
  server; no tools; an empty working directory; nothing stored; one turn` —
  with the system prompt of the P2 Opus reference collection
  (`scripts/p2_opus_reference.py`; system prompt SHA-256
  `2845935202ebc7963c0a6cb9efe7c51a975fae41dadd50cfca7acc7ce25ce76d`) and
  the v2 request of `evaluation.judge_contract`: rubric `p2-0-3-v1`, grading
  instruction SHA-256
  `7877c3845a742013e3c189e260ef506ba07dc65749fa3df8455a181a4dcedc33`, 1 to 10
  documents in the registered blind order. Each reply is stored with the
  record of its session, and no grade is read without the record of a
  session that loaded nothing. The eighth revision also named the arguments
  of that collection; they are not used, because a request sent with them
  carries the owner's instruction file and the output of session hooks
  beside the prompt (found on 2026-10-05). The consensus of GLM 5.3 and
  Sonnet 5 grades no new text: GLM is a model of another vendor, and D12
  leaves the plan one model. A grade of the judge is used as it is. A text
  the judge gave no valid grade is unjudged, never grade 0, and its case
  leaves the judged metrics with the reason; a store that misses more than
  5 % of a run's units makes the run `NOT_EVIDENCE`. A request that got no
  reply — a usage limit, an outage, a session the route refuses — is sent
  again by an explicit rerun and is not an attempt. A reply that does not
  follow the registered form is an attempt: the request is sent again by an
  explicit rerun, three attempts in all, and after the third its texts stay
  unjudged. Every attempt stays in the store, and the first valid reply of
  a request is final.
- Status `single_judge`: every number computed from these grades carries it
  and names the judge. Such a number is not the registered consensus and is
  not `model-cross-checked`, and it is never set against a published
  consensus number as a difference — the P2 baseline of the ruler, the κ of
  step 1.1 and the numbers of 1.4 stay what they are, on their own grades.
  The two arms of any later comparison are graded by this judge under one
  judge version and one rubric version.
- What is known of this judge. On the blind ten-case sample — 50 documents,
  the five-document request of P2 — the same model graded as a reference
  with the same system prompt (CLI 2.1.283): quadratic-weighted κ 0.9604,
  CI95 [0.9087, 1.0000] to the registered consensus, 0.9727
  [0.9257, 1.0000] to GPT-6-Astra, 0.9133 [0.8580, 0.9672] to GLM 5.3 and
  0.8950 [0.8267, 0.9485] to Sonnet 5
  ([capsule](../evidence/p2-model-reference-kappa.md)). Those ten requests
  went out before the route was cleaned, and the events of their sessions
  were not kept; a probe of the same arguments on 2026-10-05 shows such a
  request carrying the owner's instruction file and hook output beside the
  prompt. The numbers describe the model on that route and are a prior for
  the registered one, not a measurement of it. They were published before
  this rule was written, so the choice of the
  judge is not blind to them, and no new comparison with a model of another
  vendor is made (D12). They cover what the sample covers: its question
  classes, unexpanded top-5 contexts and the five-document request. Nothing
  was measured for expanded contexts, for the request of 1 to 10 documents,
  for an Hm case or for the registered route; what speaks for the route is
  the stability retest of each run.
- Stability retest (closes question г of plan G38). Where the scope rule
  asked for a reference sub-sample, the judge grades a sub-sample twice. The
  sub-sample is fixed by the judge plan, before any grade of the run exists:
  per subset, the planned cases that have a request, sorted by the SHA-256 of
  `20260925:retest:<case_id>`, the first 10 (all of them when the subset has
  fewer). Every request of a drawn case is sent a second time, in a new
  session, under the request id `<request id>~retest` — which gives its
  documents another registered blind order — into a store of its own, so no
  reply of the first pass is reused. Published per subset and over the whole
  sub-sample: quadratic-weighted κ between the two passes over the units
  graded in both, its bootstrap CI95 clustered by case (10 000 resamples of
  cases, percentile interval, seed 20260925), the 4 × 4 table of grades and
  the number of units whose relevance (grade ≥ 2) differs between the passes.
  A retest in which either pass misses more than 5 % of the sub-sample's
  units is `NOT_EVIDENCE`, and so is one whose κ over the whole sub-sample
  has no interval — a pass that gave every unit one grade leaves κ
  undefined. A `NOT_EVIDENCE` retest is not a failed one: it asks for no
  re-registration and closes nothing, the ruler of the run stays
  `provisional_ruler`, and the holdout is not opened on that run. Units
  missing for want of a reply are completed by explicit reruns, as any
  unanswered request is, and the retest is read then; units left unjudged
  after three replies of a wrong form stay missing, and an undefined κ is
  final for the run. The rule reads one interval: that of the whole
  sub-sample, every subset and both populations pooled. The κ of a subset is
  printed and decides nothing. Entirely at or above 0.7, the threshold
  registered on 2026-09-30: the grades of the run are used as a
  `single_judge` ruler. An interval that reaches below 0.7 is a failed
  retest: the ruler of the run is `provisional_ruler`, no semantic gain is
  claimed on it, and the judge rule is re-registered before any deciding
  comparison. One re-registration is allowed in a campaign, whichever
  development run asked for it and whatever asked — a failed retest or a
  crossed bound of the contamination controls below. It changes the prompt
  or the shape of the request and nothing else — not the judge, the rubric
  or the threshold. The texts of the run are graded again in full under it,
  and so are the texts of every earlier run that enters a later comparison.
  From then on every retest and every control on development cases — of the
  run that asked, of each regraded earlier run and of each later run — draws
  with `retest2` in place of `retest` in the hash and with `control2` in
  place of `control`, so that the new prompt is not tried on the draw it was
  written after; a regraded run takes its ruler status from its retest and
  controls under the new rule. The two draws can share cases — a subset of
  ten or fewer is drawn whole both times — and the capsule gives the number
  shared. The holdout draws with `retest` and `control`: its cases are in no
  development draw. After the re-registration a failed retest or a crossed
  bound in any development run closes the campaign without acceptance 4.1.
  The holdout run asks for no re-registration and closes no campaign: a
  failed retest or a crossed bound there has only the effect registered in
  «Opening the holdout». In a run on H and Hm a subset is H or Hm;
  in a run on the verified set or on the holdout a subset is a primary
  class. The judge plan of a paired run holds the texts of both arms, so the
  retest of a drawn case covers both arms and both populations — the seeds
  before expansion and the sent context. Only
  the first pass enters a metric; the second is never averaged in and never
  replaces a grade. A retest shows whether one model repeats itself under
  another order in another session. It is not a second voice, and an error
  the model makes both times stays invisible. The 0.7 threshold was
  registered for the agreement of two graders; for one grader with itself it
  is a low bar, kept because no other number was registered — the capsule
  prints κ and the table, and the reader judges the margin.
- What a `single_judge` ruler may claim. With a passed retest: the baseline
  numbers of slice 2.5 as the control's numbers, and for a track-3 experiment
  a result under the unchanged decision rule below, reported as «on a
  `single_judge` ruler (Opus 5.5)». Every such capsule gives the retest κ and
  the P2-sample agreement above and says that neither a model of another
  vendor nor a person checked the grades of the run. It may not claim
  `model-cross-checked` or `human-validated`, a difference to a consensus
  number, or that an error Opus makes systematically would have been seen
  (plan G37). Acceptance 4.1 on such a ruler is registered in «Checks by one
  model in slices 2.8 and 4.1» (tenth revision).
- Contamination controls (closes question д of plan G38; tenth revision,
  registered before any grade of a case that has gold spans). A retest
  cannot show a judge that grades the question or the subject instead of the
  text: such a judge repeats itself. A control is a text whose evidence was
  removed by construction, so the direction its grade should move is known
  without a second grader. Controls accompany every judged run whose cases
  carry verified gold spans — from the first judged run on the verified set
  on (the pilot of plan step 1.3c reads gold spans and is planned without a
  judge). The baseline of slice 2.5 carries none: H and Hm have no gold
  spans, so nothing can be cut or swapped by construction. The control cases
  are fixed by the judge plan, before any grade of the run exists: the
  planned cases in which a document of the control arm's sent context holds
  a gold span of the case, sorted by the SHA-256 of
  `20260925:control:<case_id>`, the first 10 (all of them when there are
  fewer). A span is located in a document by character offsets where the
  address of the document has them — the overlap of the two ranges, so a
  span that lies partly in the document is cut in part and counted as
  partial — and otherwise by its normalised text, case and whitespace
  ignored (the normalisation of gold evidence), whole spans only. A gold
  span of a drawn case that is located in no document of its request is
  listed. Each drawn case gives two requests, sent in new sessions into a
  store of their own; both start from the first request of the control arm's
  sent context, in plan order, that holds a span. `<request id>~span_removed`
  is that request with every located gold span of the case cut out of every
  document: the cut leaves one space and no mark; the documents keep the
  order they have in the request it is built from, so the cut is the only
  change; a document left without a letter or a digit is dropped and
  counted, and a request left without a document is not sent and is counted.
  `<request id>~swapped` is the question of the case with, in place of its
  own documents, the span-bearing documents of a partner case's request, in
  the order of that request; the partner is the next drawn case, cyclically,
  that shares no family with this one and whose gold documents have no
  `cross_ref` link to this case's in the registered family map; a case
  without such a partner gets no swapped request and is counted. The text of
  no request holds a request id or its suffix. Published apart from every κ
  and never entered into a metric: for `span_removed`, over the documents
  with a cut, the 4 × 4 table of the grade before (the first pass) and
  after, and of those relevant before how many fell below grade 2; for
  `swapped`, the grades and the number of documents graded ≥ 2; beside both,
  the retest's share of units whose relevance changed between its passes —
  the noise these counts sit on. Every document that keeps or gets grade ≥ 2
  is listed with its case and address, and is marked *explained* when the
  fact matcher finds a required fact of the question's case in the text as
  sent and *unexplained* when it finds none. The matcher here is the
  deterministic one alone — a fact's `source_quote` by normalised
  containment («Fact presence») — and no request to the judge under test
  stands in for it. Two bounds are read. Both are
  registered here, before any grade, and both are set for a gross failure
  only: the gold spans are the labelled evidence of a case, not all the
  evidence a text may hold, and a text of another family can still answer
  through shared boilerplate, so a finer threshold would measure the labels
  and not the judge. The `span_removed` bound is crossed when, of the
  documents graded 3 before the cut in which the matcher finds no required
  fact after it, fewer than a quarter got a lower grade. The `swapped` bound
  is crossed when, of the swapped documents in which the matcher finds no
  required fact of the question's case, more than half are graded ≥ 2. A
  bound is read only over at least 5 such documents. Which documents a
  bound will be read over is known before any control is graded — from the
  first pass and the matcher. So when the first pass of the run is stored
  and a bound has fewer than 5, a script that prints counts and no grade
  adds control cases in the same hash order, one at a time, until both
  bounds have 5 documents, 30 cases are drawn or the order ends. A crossed
  bound makes the ruler of the run `provisional_ruler`, as a failed retest
  does. A bound still read over fewer than 5 documents bounds nothing: the
  capsule prints «contamination not bounded» beside every verdict of the
  run, and the holdout is not opened on such a run. The controls show
  whether grades follow the evidence when it is
  removed and whether the judge grades by the question alone. They do not
  show that a grade is right, they do not test a text on the same topic that
  lacks the evidence, and they are not a second voice. A capsule of a judged
  run on cases with gold spans that lacks them claims no semantic gain. Of
  the four kinds the calibration protocol lists, `swapped` also serves as
  the text with no evidence; a plausible distractor is not built, because
  nothing fixes its expected grade without a grader. The labeller of slice
  2.8 has a control of its own, registered in «Checks by one model in slices
  2.8 and 4.1».
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
  0–3 rubric for reference and judge; blind, shuffled lists with no judge
  output visible to the reference; a sample drawn before any grade is seen; quadratic-weighted κ with
  a bootstrap CI clustered by case; binarisation ≥ 2 chosen in advance, ≥ 3
  as a sensitivity view, never a second gate; a small pre-selected set of
  contamination controls (no evidence / supporting span removed / swapped
  evidence / plausible distractor) scored separately from the natural κ — the
  published ten-case grades of step 1.1 predate this protocol and carry none;
  which later collections carry them is registered in «Contamination
  controls» above (question д of plan G38);
  ambiguous and invalid answers counted with their reasons; the rubric is
  not adjusted after a holdout result is seen; κ is stated for its rubric,
  language and context type only. The branching after an indeterminate κ is
  the rule above (10 → 30 cases, then `provisional_ruler`); the sample is not
  grown open-endedly toward a wanted κ.
- No human annotator (G15 as changed by D11): neither a first nor a second
  person grades. The agreement between the reference models on the relevance
  pairs of the 1.1 sample is published with its CI and the disagreement
  matrix; for the assertions of the 2.8 sample the agreement of the one
  labeller's two passes takes its place (tenth revision). It is a reference
  for agreement, not a mathematical ceiling: the judge's κ is not divided by
  it and thresholds are not lowered by it. Every capsule states that the
  reference labels are model labels, that inter-annotator reproducibility is
  not established and that a retest measures one model's stability only.

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
where the matcher's outcome is ambiguous — defined below — by the blind
check registered for the comparison; the
matcher version is part of the provenance and a changed matcher recomputes
every published `fact_coverage`. A numeric fact is registered as a claim
`{subject, value, unit, polarity, condition}` — polarity from a registered
lexicon (разрешено / запрещено / не более / не менее / только при …) — and is
present only when number + unit match inside a window that also carries the
subject and the same polarity marker: «150 кг разрешено» does not match «150 кг
запрещено» (Astra final-plan audit №18).

On the verified set the matcher follows the rule the facts were labelled
under (`pilot-claim-quote-v2`, `evaluation/devset.py`). In a context a fact
is present when its `source_quote` — a verbatim excerpt of a gold span — is
contained in the text of a sent document; a derived fact, an aggregation
result that no span states and that has no quote, is present when every
required evidence group of its case is satisfied there. In an answer the
matcher reads the fact's `text`. *Ambiguous* is an outcome of the matcher,
not a judgement about it. In a context nothing is ambiguous — a quote is
contained or it is not — and `fact_coverage` is the matcher's number. In an
answer the matcher's finding stands only where it finds the fact; a fact it
does not find, or whose polarity it cannot settle (`needs_blind_judgment`),
is ambiguous — an answer may state it in other words — and takes the
verdict of the Facts request of 4.1.

A critical fact is not left to the matcher where the matcher may be wrong
(decisions D11 and D12, tenth revision; two reference models in the fifth
revision, a blind human check until 2026-10-03). In an answer the verdict
of Facts decides for it whatever the matcher found. In a context a quote
the matcher finds is present — it is verbatim — and a critical fact the
matcher does not find takes the verdict of the Context request, in every
comparison, a retrieval-only development one included. Until the tenth
revision this paragraph said that each critical fact «is confirmed by the
blind answer check of 4.1», which a comparison without answers could not
do. Both requests are registered in «Checks by one model in slices 2.8 and
4.1».

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
(`agent_labelled` / `real_labelled`), `label_check` (`none` /
`single_model_self_checked` / `single_model_verified` / `model_verified`,
with the verifier ids, the rubric version, the round and, after a repair,
the repair author — see «Label verification»), the seed-selected source
section, the
primary class (single-doc / multi-doc / aggregation / needs refusal or
clarification), overlapping flags (RU→EN, numeric facts, trap type among
false premise / out of corpus / outdated rule / conflicting documents /
dangerous goods, safety-critical), `expected_action` (answer / correct the
premise / clarify / refuse / escalate), `as_of`, the authority source of the
rule and the severity of a wrong answer. Quotas live in the plan (1.3d); an
unmet quota narrows the scope of the conclusion instead of being filled.

Label verification (decision D11, added 2026-10-03; rubric
`label-verification/v2`, registered 2026-10-04 in plan step 1.3b before the
first counted check; it replaces the human approval of decision D3): no
person approves a case. One verifier model checks every dev and holdout case
under the rubric in force for the step: under v2 a model of a vendor other
than the draft author's, under v3 (below) also the model that wrote the
draft. Rubric v1 named two verifiers of
two vendors; plan decision D12 leaves the plan one model, the agent of the
session, so v2 names that model alone and says below what a check by one
model does not show. Under v1 no verdict was counted: one request to each
verifier was sent as a trial of the routes before D12 was recorded, and
neither reply is evidence. The draft author is the registered generator of
the case, recorded per case as `draft_author` with its model and vendor (the
pilot: `gpt-6.1-sol`, OpenAI).

Registered verifier for drafts by an OpenAI model:

| Verifier | Vendor | Route | Settings |
|---|---|---|---|
| `claude-opus-5-5` | Anthropic | Claude Code CLI, first-party provider | effort `max`, no tools |

The route of this table is the one the 35 requests of step 1.3b were sent
by. A probe of it on 2026-10-05 showed that such a request is a new session
but not an empty one: beside the registered prompt it carries the owner's
instruction file for coding sessions and the output of two session hooks.
In the probe request none of that text was about a case, a label or a
verdict; one of the hooks picks its text by the words of the request, so
what it added to each of the 35 is not known. The 35 replies were stored
without the events of their sessions, so all of this is known from the
probe, not read from them. The verdicts of step 1.3b stay as published, with this said
in their capsule; rubric v3 names the route that replaces it.

One request holds one case, in a new session with no conversation state and
no tools. The verifier is the model of the agent that runs the plan: the new
session is what keeps the agent's own knowledge — the draft author, the
round, the reasons of an earlier check — out of the verdict. A reply counts
only when the route reports the registered model id. The request names
neither the draft author nor the verifier and carries nothing of an earlier
round. The exact prompt is registered with the rubric: its SHA-256 is
recorded here in the commit that moves the verification tool to v2, before
any request of v2 is sent; a reply counts only when the prompt SHA-256 stored
with it is the recorded one, and a changed prompt is a new rubric version.

Prompt SHA-256 (rubric label-verification/v2): `3f7c114428028f6518aca3f21a03f5352d0497d99d0356f2c804b9389df756ad`

The checks:

1. every evidence span is present verbatim in the named source at the
   registered corpus version — a deterministic check by the verify script,
   not a model verdict;
2. every required and critical fact follows from the spans alone, and the
   minimal reference answer states nothing the spans do not. A case without
   spans has no facts: its reference answer states only the action and its
   reason, and the reason rests on the supplied sections and scan;
3. the question is answerable from the spans as written, and the reference
   answer answers it: an answer that states the required facts and nothing
   else is correct and leaves out nothing the question asks for. For
   refusal, clarification and trap cases — `expected_action` other than
   `answer`, or a trap type set — instead, the registered reason holds
   against the wide scan of the corpus (below). On a case registered as
   unresolvable (`expected_action` refuse, clarify or escalate) no passage
   of the scan that applies to the question — its subject, the people or
   cargo it concerns, its conditions and `as_of` — answers the question as
   written. On a trap case with spans the spans correct the premise as
   registered and no applicable passage of the scan makes the premise true.
   Where passages conflict or one is outdated, the verifier judges by the
   passage that applies on `as_of` and names it;
4. the primary class, the `safety_critical` flag, the trap type and
   `expected_action` agree with the above. The flags `numeric`, `ru_to_en`
   and `adversarial_unanswerable` are not judged: the verify script computes
   each from the label by its registered rule and refuses a case whose stored
   flag differs. Rubric v1 sent them and described `ru_to_en` more loosely
   than its rule, and the trial request was rejected on that description
   alone;
5. (plan G38, question б) authority and weight of the case. Checks 5a and 5b
   concern the organisation's own documents as supplied: whether an external
   norm a document cites says the same is not checked, and a citation of an
   external norm does not take authority from the internal document.
   - 5a, currency: every authority document of the case is in force on
     `as_of` — its card gives an effective date not later than `as_of`, and
     nothing supplied says the rule is replaced or expired;
   - 5b, authority: the card and the supplied text show the named document
     to be the organisation's controlled source of the rule the case relies
     on — on a case without spans, of the rule that justifies the action;
   - 5c, severity: the verifier names the severity of the most harmful wrong
     answer the question invites, on the registered scale `low` < `moderate`
     < `high` < `critical`, taking the highest level that applies.
     `critical`: harm to people, a breach of an occupational-safety,
     aviation-security or dangerous-goods rule, or disclosure or
     unauthorised transfer of credentials or personal data. `high`: a
     material financial loss, a breach of another legal or regulatory duty,
     a wrongly decided personnel case. `moderate`: rework, delay or a wrong
     internal step the process corrects. `low`: no operational consequence;
   - 5d, critical facts: a fact is critical when an answer that omits or
     misstates it would lead the user to an unsafe, unlawful or materially
     costly action — a prohibition, a mandatory safety, security,
     dangerous-goods, legal or financial-control step, a limit or a deadline
     whose breach is a violation. Every listed critical fact meets this, and
     no fact that a correct answer needs and that meets it is absent from
     the critical facts. A case without spans has no facts, and 5d is
     confirmed.

The verifier answers `confirm` or `reject` on checks 2, 3, 4 and 5d, with a
one-sentence reason and, on a rejection, the element concerned (a fact, a
span, a passage of the scan). On 5a and 5b it answers `confirm`, `reject` or
`unverifiable`: `reject` needs positive evidence in the supplied material —
an effective date later than `as_of`, a text saying the rule is replaced or
expired, a card or text showing that the document is not the organisation's
controlled source of the rule; `unverifiable` means the supplied material
lacks what the check needs — no effective date or version, no owner or source
type. On 5c it names a level. A statement inside the case that an owner must
confirm something is the draft author's note from before decision D11, not
evidence for 5a or 5b. A reply that does not follow this form is requested
again, three attempts in all.

A case without a valid reply from the verifier has no outcome in that round
and keeps `label_check: none`. With a valid reply the case is confirmed when
check 1 passes, the verifier confirms checks 2, 3, 4 and 5d, does not reject
5a or 5b, and on 5c its level is neither two or more steps from the
registered one nor on the other side of the `critical` boundary; otherwise it
is rejected. A confirmed case carries `label_check: single_model_verified`
with the verifier id, the rubric version and the round. `model_verified` is
the word of a check by verifiers of two vendors, and no case of this rubric
gets it. If the verifier answers `unverifiable` on 5a or 5b, the confirmed
case carries `authority_unverified: true`: it stays in the set and does not
count toward the safety-critical quota; counts of safety-critical cases are
reported with and without such cases. A one-step severity difference that
does not cross the `critical` boundary is published as a difference, not a
rejection.

A rejected case is repaired once by the agent of the session
(`claude-opus-5-5`, recorded as `repair_author`), who sees the verifier's
reasons; the draft author is not called (D12). A repair changes the label,
never the question: the case id, the question text, the draft author, the
corpus version, `as_of`, the seed-selected section and the question style
stay as drafted; spans, partner sections, facts, the reference answer, the
class, the flags, the trap type, `expected_action`, its reason, the authority
documents and the severity may change. A repair that leaves the label as
drafted is refused: a second request on an unchanged label would be a second
draw of the same check, not a repair. A repair cites no document of the
holdout reserve. A rejected case that is not repaired is dropped without a
second round by a declaration of the repair author, on one of two grounds:
`repair_needs_reserve` — only a document of the holdout reserve could repair
it, and the declaration names the document; `repair_not_possible` — no change
of the label within the bounds above answers the rejection, because the
question itself is at fault or because the agent finds the rejection wrong
and so has no repair to make — with the reason in one sentence. The
declaration is recorded as the reason of the drop. The families of a repaired
case are recomputed and published. A new question is a replacement of the
case (below), not a repair. The repaired
case passes the per-case rules of the verify script and its source checks;
the rules of the draft set as a whole — quotas, the split of styles, the
SHA-256 of the file — bind the unchanged drafts only. The verifier then
checks the repaired case in full, in the same form, in a new session and with
no trace of the first round. This second check is made by the model that
wrote the repair: it is a consistency check — it can catch a repair that its
own spans do not support — and not a check by another party. A case confirmed
in round 2 carries `repair_author` in its `label_check` and is counted apart.
A second rejection drops the case, with the rejecting checks recorded. A
relabelled class or action changes the class counts: rejection shares are
reported by the drafted class, the verified set by the class after repair,
with the transitions listed, and the quota rule above applies. If the
verifier is unavailable (a quota, an outage), verification waits. Step 1.3b
is closed only when every draft is confirmed or dropped.

Replacement of a dropped case (plan G38, question в; tenth revision,
registered before step 1.3c names a size). The sizes step 1.3c registers are
targets for the verified set. A case dropped during verification is replaced
once. Replacements are made when the first verification of the split is
complete — every draft of it confirmed or dropped — and in ascending id of
the dropped cases. The draw order of a split is a seeded order of its
eligible sections, registered with its seed in step 1.3c, before any draft
of step 1.3d exists, together with the eligibility test of each primary
class — a rule a script applies to a section, not a judgement of the
generator. The replacement of a dropped case is drafted from the first
section of that order that is the seed section of no draft of the split,
dropped drafts included, and passes the test of the dropped case's class as
drafted. The generator passes over nothing: a section is skipped by the
script or not at all. The new draft keeps the class as drafted, the question
style, the trap type and `expected_action` of the dropped case, and is
written in a stateless request that holds the section — with the partner
sections its class needs by the registered rule — and these four fields;
nothing of the dropped case and nothing of its rejection reaches it. A
request that gives no valid draft in three attempts, or an order with no
section left, leaves the place empty. The new draft is verified like any
other, a repair included. A replacement that is dropped as well leaves its
place empty: no third draft is written, because drawing until the verifier
accepts selects the cases one model finds easy to confirm. After the holdout
is locked (step 1.3e) nothing is replaced. A label made `needs_review` by a
changed source falls under the corpus-snapshot rule of the decision rule;
a `gold_error` at acceptance takes the case out of `action_correct` and
`abstention_correct` only, as the contract says. Step 1.3d publishes
the verified n and the clusters of each split and stratum, and the MDE and
the powers of step 1.3c are recomputed on them; the margin is not widened,
and a quota the drops leave unmet narrows the conclusion as any unmet quota
does. The capsule gives the drops and the replacements per class and split
and says that the set is conditional on confirmation by one model: a case
this model rejects twice is absent from it. The pilot had no drop and so no
replacement.

The verifier receives the whole draft case — question, span texts, facts with
their quotes, reference answer, class, the `safety_critical` flag, trap type,
`expected_action`, the registered reason, `as_of`, the authority documents
and the severity; the three flags the verify script computes are not sent —
with every source named by a pseudonym, never by its file name (plan G31); a
file name inside a corpus text is replaced by the pseudonym of that document.
The `scope` text of the pilot's `authority_source` is a template of the draft
phase and is not sent. For check 5 the verifier receives the document card of
each authority document: the front-matter fields `title`, `document_type`,
`source_type`, `version`, `effective_date`, `owner_role` and
`related_normative_sources` of the source file at the registered corpus
version, and nothing else of the front matter. For refusal, clarification and
trap cases it also receives the text of the seed-selected and partner
sections and the texts of the wide scan.

Wide scan (plan G38, question а; it replaces the control's pre-rerank pool in
check 3): for the question as written, the union of the 20 best chunks by the
production lexical scorer — BM25 with the production tokenizer over every
chunk of the index; a chunk with a score of zero or below is not taken, so
the lane may hold fewer — and the 20 nearest chunks by exact cosine
similarity between the production embedder's query vector and every chunk
vector of the index's embedding checkpoint. No query transform, fusion, cap,
rerank or expansion; ties are broken by position in the chunk archive; a
chunk found by both lanes is kept once with both ranks; the texts are passed
in archive order. The scan is stored for every case before the first check,
with chunk addresses, `text_sha256`, lanes and ranks, the SHA-256 of the
chunk archive and of the checkpoint, and the code SHA. It runs on the index
of the slice 2.5 baseline. The lane size of 20 is a budget chosen in advance,
not a measured recall: at most 40 of the 5589 chunks of that index reach a
verifier, and the chance that the scan misses an answering passage has not
been estimated.

The capsule publishes, per class, the share rejected at the first check, the
cases confirmed only after a repair, the severity differences, the cases
flagged `authority_unverified` and the dropped cases with their grounds.
`label_origin` stays `agent_labelled`: a model check is not a human approval,
`real_labelled` is not assigned and the count of real labelled cases does not
rise. The check bounds label errors, it does not prove their absence. What a
check by one model does not show: an error this model makes systematically —
in reading a rule, in judging a severity — passes unseen, and there is no
second verifier whose disagreement would point at it. On an unrepaired case
the author of the label and its verifier are models of two vendors; on a
repaired case they are one model. On refusal, clarification and trap cases a
passage outside the wide scan can leave an answerable question registered as
unanswerable (plan G37). At acceptance such a case is resolved by the
`gold_error` rule of the contract below. The severity scale was written after
the pilot drafts were labelled; a severity the scale does not support is a
rejection like any other. The replacement of a dropped case is registered
above (question в of plan G38). Screening drafts (below) are checked once
under the rubric in force for the step; rejected drafts are dropped, and
more than 10 % rejected means the generator prompt is rewritten once and
the check repeated on drafts written anew under it (G32). More than 10 %
rejected a second time, and the tier is not built, which the capsule says:
the rule had no limit, and where one model writes and checks, repeating
until the check passes selects what that model accepts.

Rubric `label-verification/v3` (tenth revision; registered before step 1.3c
names a size). Under decision D12 the drafts of step 1.3d and the screening
drafts are written by the agent of the session, `claude-opus-5-5`, so their
author and their verifier are one model and the vendor rule of v2 cannot be
met. v3 is v2 with four changes, and nothing else about the request, the
checks, the decision rule, the limits of a repair or the grounds of a drop
is different.

1. The route. Every request of v3 goes by the route of «Checks by one model
   in slices 2.8 and 4.1» — a session that loads nothing, kept with its
   record. A verdict counts only with the record of such a session.
2. The verifier of a label written by an Anthropic model is
   `claude-opus-5-5` itself. That is a draft of step 1.3d, a screening
   draft, and any label after a repair, whoever drafted the case: the
   repair makes the checking model the author of the label. A confirmed
   case then carries `label_check: single_model_self_checked` with the
   verifier id, the rubric version and the round. Only an unrepaired draft
   by a model of another vendor keeps `single_model_verified`.
3. A draft is written in a stateless request of its own, by the same route,
   from a generator prompt registered with its SHA-256 in step 1.3d. So the
   check is made neither in the session that wrote the draft nor with
   anything that session knew: the verifier's request holds the case and the
   supplied corpus texts.
4. A repair is written the same way, and not by the session that plans the
   work: one stateless request by the same route, from a repair prompt
   registered with its SHA-256 before the first repair of v3. It holds the
   case as the verifier received it and the verifier's reply, and returns
   the repaired label or the declaration of a drop with its ground. The
   script applies the limits of a repair — the fields that stay as drafted,
   a label that must change, no document of the holdout reserve — and
   checks that a `repair_needs_reserve` declaration names a supplied
   document of the reserve. A reply that breaks these is asked for again,
   three attempts in all; a case left without a valid repair is dropped as
   `repair_not_possible`. `repair_author` is the model of that request.

What a self-check can show: a fact its span does not state, a reference
answer that does not follow from the facts, a class or an action that
disagrees with the label, a refusal the wide scan contradicts. What it
cannot show is wider than under v2, where the draft came from a model of
another vendor: an error this model makes both when it writes and when it
reads — a rule misread, a severity misjudged, a question taken for
answerable that is not — passes unseen. Every capsule of step 1.3d says that
draft, check, repair and replacement are by one model. The prompt of v3 is
that of v2 under the new rubric name; its SHA-256 is recorded here in the
commit that moves the verification tool to v3, before any request of v3 is
sent. The 30 pilot cases — drafted by `gpt-6.1-sol` and verified under v2 by
the earlier route — are checked again under v3 in step 1.3d: the 25
confirmed as drafted as drafts of their author, the 5 confirmed after a
repair as labels of the checking model (change 2). The capsule sets the two
sets of verdicts side by side, and a pilot case rejected there is repaired
or dropped like any other.

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
  weights. The split between dev and holdout never separates documents of
  one family. Resampling cases does not remove judge bias — plan step 1.1
  checks for it against model references; a bias the models share stays
  undetected (plan G37).

  A **document family** (G22) is a registered group of source documents. The
  registered map is `evaluation/document_families.json` at SHA-256
  `54bdb736180e00325bff20f49e2b9d985dd62278fe9f9cdb6161a0da719e3584`,
  registered by this paragraph in plan step 1.3b on 2026-10-04; since decision
  D11 no owner confirmation is awaited. The file is pinned by the pilot
  manifest and is not rewritten, so its own `status` fields keep the draft
  wording of step 1.3a. The map groups documents by topic: 84 families over the
  201 documents, 57 of them with one document. This departs from the earlier
  definition — documents that share a source folder or topic or are linked by
  `cross_ref` — because its literal closure joins all 201 documents into one
  family, and topic families merged transitively by `cross_ref` leave 24
  families with 171 documents in one. Folder and `cross_ref` closure stay as
  sensitivity views, not cluster units.

  The holdout reserve is registered with the map: the 35 families (36
  documents) that no development use has touched — H, Hm, P1b/P2, the loss map
  of step 2.5 and the pilot. Topic families do not remove cross-reference
  dependence: 25 of the 35 reserve families link directly to a development
  family (105 links). No independent sources are added — only the owner can
  add documents — so the holdout is independent at the level of topics, with
  this leakage stated in every capsule that uses it. The reserve is skewed: 24
  of its 36 documents are legal (contract templates and powers of attorney),
  10 are HR and 2 are transport-logistics contracts; it holds no compliance,
  FAQ or external document and no claims, customs or dangerous-goods family.
  The conclusion of step 4.1 therefore covers only the topics and strata the
  holdout has cases for, and its capsule lists the strata it does not cover.
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
  widened**: if the size is unreachable the study states that it detects only
  larger effects (MDE above MUE); adding independent families needs new
  source documents, which only the owner can supply (decision D11). Power does not transfer between tiers — screening, sent context
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
  dev families only, kept apart from the verified set (`single_model_verified`
  since the seventh revision and, for a label the checking model wrote,
  `single_model_self_checked` since the tenth; `model_verified` in the
  fifth; until 2026-10-03 «the human set»), run retrieval-only with
  the registered judge (the consensus until the eighth revision, the judge
  of new texts since) and the retrieval stages the mechanism needs. Judge
  grades are cached by the full request hash — `(question_hash, the ordered
  text_sha256 list of the presented set, rubric version, judge version)`:
  documents are graded jointly, neighbours and order can move a grade, so
  only an identical set in the same order is reused (Astra final-plan audit
  №19); the expected number of new requests is published before the run; a run graded by one judge because the other
  hit its limit is `single_judge`, outside the consensus (G24) — since the
  eighth revision every new run is graded by one judge and is `single_judge`
  («Relevance grades»). The tier ranks
  candidates and nothing else: it cannot pass a non-inferiority check, prove
  answer safety or produce a semantic gain, and families — not questions —
  are its unit of independence. Cross-reference, added 2026-10-03 with no new
  criterion and no change to the measurement contract — see the requirements
  this spec already states: candidate and token budgets are equal between
  arms, and `sent_precision` is taken on the exact expanded documents the arm
  sends (the closing paragraph of «Metrics per case, then averaged over
  cases»); the registered control is hybrid retrieval with production
  expansion (the first item of this list); each mechanism names its primary
  metric before the run — `sent_precision` for selection mechanisms,
  `all_evidence_coverage` for coverage mechanisms (the second item). Why the
  pointer: a comparison on the reranked seeds and the same comparison on the
  expanded context can diverge. In the exploratory lexical-lane study (gap G36
  of the [quality plan](plan_03_10_26.md); its files stay outside this
  repository) Snowball-stemmed
  BM25 against the study's control had all answer keywords present in 92 vs
  87 of 100 cases on the five reranked seeds and in 96 vs 97 after production
  expansion; the difference between the two states was not tested. That is a
  lexical proxy; it does not transfer to judged labels.
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

Two acceptances (A3, A12). The holdout is opened only under the condition
registered in «Checks by one model in slices 2.8 and 4.1» — a passed
stability retest of the one judge, contamination controls read and not
crossed, and a passed rehearsal of the answer checks. Until the tenth
revision the condition was a `model-cross-checked`
ruler, which no grade made after decision D12 can carry.
**Research acceptance (4.1)** runs the locked
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
| `faithfulness` | higher | answered cases | NI −0.02; decided by the blind answer check — the Grounding request of one model (D11, D12; since the tenth revision whatever the status of the NLI judge) | cluster bootstrap |
| `answer_fact_coverage` | higher | answered cases with facts | NI −0.02 | cluster bootstrap |
| `citation_correctness` | higher | answered cases with facts and, in each arm, at least one citation and at least one fact the answer states; the rest counted by reason and by arm | NI −0.02, resolved by the blind answer check — the Facts and Context requests of one model (stated fact ↔ cited document; D11, D12) | cluster bootstrap |
| `citation_presence` | higher | answered non-refusal cases | NI −0.02 | cluster bootstrap |
| `action_correct` | higher | all cases; per action class reported | NI −0.02 over the set | cluster bootstrap |
| `critical_errors` | fewer | all cases | any **new** critical error blocks SHIP — a rule, no interval | — |
| lexical `context_precision` on H | higher | H | NI −0.02 (D6) | cluster bootstrap |
| retrieve p95 | lower | all cases, protocol below | delta ≤ 200 ms against the CI95 upper bound | bootstrap over cases |

- the interval-validity rule above applies to every row: a degenerate
  interval does not pass a check;
- «answered cases» in the table are the cases whose answer is of the class
  answered in both arms; a case answered in one arm only is a lost pair
  under the pair mask below («Checks by one model in slices 2.8 and 4.1»);
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
  harm-weighted sum may be reported as description only. A type can be
  observed only on the cases that carry what it is derived from, and the
  capsule gives their number per type beside the count of errors;
- wrong gold on an unresolvable case (`gold_error`, plan G38, question а):
  when the answer of at least one arm on a case registered as unresolvable
  is of the class answered, the answer checker decides in a request of its
  own, in two passes and blind to the arm (two answer-check models until
  the tenth revision), whether a document of a sent context — a passage of
  the registered corpus, in force on `as_of` and applicable to the question
  — makes an answer the right action instead of the registered one. The
  request is sent for the sent context of each arm, of an arm that
  abstained as well, so that the arm that answers more does not alone get
  the chance. If in the request of either context both passes name the same
  document, the case's outcome is `gold_error`: the label was wrong. The
  decision is stored apart from the holdout, which is
  not edited after it is opened, and applies to every arm alike: the case
  leaves `abstention_correct` and `action_correct`, and an answer on it is
  not counted as the critical error «confident answer where refusal or
  escalation was required». Nothing else is forgiven: the faithfulness and
  citation checks of each answer stay scored, and a critical error that does
  not rest on the registered action — a wrong answer on a safety-critical or
  dangerous-goods case, an outdated rule presented as current — stays
  counted for the arm that made it. The case's eligibility for every other
  metric stays as registered; the capsule lists the case with the passage
  address and publishes the denominators, and the verdict of every row the
  removal touches, with and without it — the registered reading is the one
  with the removal; the stratum
  loses the case for the action metrics and its conclusion narrows as for an
  unmet quota. If in neither request the two passes name the same document,
  the registered label stands and the answer is charged as registered —
  unless a pass of one of these requests is invalid. Then the case has no
  `gold_error` result, and nothing is charged for an invalid pass: the case
  is a lost pair for `action_correct` and `abstention_correct` and is
  without a result for that critical error. A label that is wrong where both
  arms abstain is not looked for: it credits both arms alike;
- answer checks are done by one model, registered with its route, prompts
  and rubric before the rehearsal that precedes the holdout: who it is, what
  each of the four kinds of request holds, when a verdict exists, how a
  disagreement between two passes is settled and what decides
  `faithfulness`, `action_correct`, `abstention_correct` and a critical
  error are registered in «Checks by one model in slices 2.8 and 4.1»
  (tenth revision, question ж of plan G38). The fifth revision named two
  reference models of two vendors, which decision D12 took out of the plan.
  The checks are blind to the arm (G34): a request holds one answer or one
  context and names no arm, and the arm is joined after the verdicts are
  stored. A field on which the first two passes do not agree is settled by
  a third pass, by the same rule in both arms — the `gold_error` request
  excepted, which is never sent a third time. A metric fed by a field that
  is not one value in two valid first passes in more than 10 % of an arm's
  requests of that kind that carry the field is `INCONCLUSIVE`. No person
  checks answers (decision D11), and
  no model of another vendor decides anything about them (D12): the one
  such model whose number is printed is the NLI classifier of the phase-C
  judge, and the capsule says so;
- semantic invariants (G12): that the required fact, the citation and the
  action are present in an answer is what the rows `answer_fact_coverage`,
  `citation_presence` and `action_correct` decide on the holdout. Until the
  tenth revision this item read «on the dev cases already checked in 2.5»,
  and no such cases exist — slice 2.5 generates no answer. On development
  cases the three are printed from the verdicts of the rehearsal and decide
  nothing. No exact-string comparison of whole answers. The 10 fake-LLM
  contract cases of slice 2.1 test the API contract and are not evidence of
  model quality.

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
| `faithfulness` | the phase-C judge (LLM judge with the NLI second judge) on the answer against the sent context; the phase-C condition (≥ 0.90 target) is reported as its own gate. The NLI model and threshold used here are the ones registered by plan slice 2.8 (validation against a model reference — since the tenth revision the labels of one model on which its two passes agree, in place of the majority label of three models from three vendors; no human labels since decision D11); until 2.8 closes, the pinned `mDeBERTa-v3-base-mnli-xnli` at 0.5 is `provisional_judge`. At acceptance 4.1 the deciding value is not this judge's: it is the blind answer check — 1 when the Grounding request finds every factual statement of the answer supported by the sent context, else 0. Beside it the number of the NLI classifier is printed; the LLM part of the phase-C judge is not run at acceptance and its number is `N/A`, because that part asks whatever model the evaluation is given and no model but `claude-opus-5-5` is asked to judge (D12; tenth revision) |
| `answer_fact_coverage` | required facts present in the answer divided by the case's facts |
| `citation_correctness` | as first registered: cited sources that are in the sent context and support the cited claim, divided by citations made. The API today emits one citation per sent document (`agent/graph.py` ~1943), not per claim, so until a claim-linked citation exists the metric is resolved by the blind answer check of 4.1 (decisions D11 and D12; Astra final-plan audit №18) and has one denominator. Per case: of the required facts the answer states (the matcher, and the Facts request where the matcher does not decide), the share that stand in at least one cited document (the matcher's verbatim quote, and the Context request where the matcher finds none; a derived fact counts when the cited documents satisfy every evidence group of its case). Averaged over the cases answered in both arms that have facts and, in each arm, at least one citation and at least one stated fact. The number says whether what the answer states of the label stands in a document it cites; it is not claim-level citation correctness, and the capsule says so |
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
with no facts, or with no citation or no fact its answer states in either
arm, is excluded from `citation_correctness` in both arms and counted by
reason and by arm (№13); it is not a lost pair.
`citation_presence` and `answer_fact_coverage` are deciding metrics, so the
exclusions cannot hide missing citations or missing facts (№17). The
deciding faithfulness
check of 4.1 is the blind answer check of the contract, whatever slice 2.8
concluded (tenth revision; until then only while the NLI judge stayed
`provisional_judge`). The number of the NLI classifier is printed beside it
with the status slice 2.8 left the judge — the `provisional_judge` caveat,
if that is the status (№18) — and the 0.90 of phase C as a line that is not
applied.

Sometimes the baseline collection cannot finish a case. This rule was added
on 2026-10-02 for T-68.
- **Model failure on one case.** Examples: a pipeline error, a grader
  error, a reranker fallback.
  - The case becomes a recorded exclusion and is never scored 0.
  - The exclusion leaves the numerator and the denominator of every metric.
  - The report lists it with its stage, reason and error type, and
    publishes the denominators per subset.
  - If more than 10 % of a subset's cases are excluded, that subset's
    baseline numbers are `NOT_EVIDENCE`, as with invalid judge answers (№13).
- **Integrity or environment failure.** Examples: a mismatch in an input
  SHA, a model digest, the replay cache, index eligibility or the embedder
  manifest; a failed vector query; an unreachable model service.
  - The run stops; the failure never becomes an exclusion.
  - Three consecutive exclusions with the same error type at one stage
    count as an environment failure, and the run stops.
  - The stop is recorded, including a failed check of the registered
    inputs before the stage starts.
  - A refusal to start is not a stop and leaves no record. There are three
    refusals: the stage order is wrong, `--resume` is missing, or an
    earlier stage's stop is still open.
  - Later stages and the report refuse to run until the stopped stage is
    resumed after a fix. On resume, the cases of the
    three-exclusion streak run again; they are not kept as exclusions. The
    report lists every resolved stop.

**Product acceptance (4.2)** repeats the latency and behaviour checks on the
deployment target against the absolute SLO the owner names (D5). Without a
named target and SLO there is no product SHIP. The per-tenant flag (4.3)
follows product acceptance only.

## Checks by one model in slices 2.8 and 4.1

Registered in the tenth revision, 2026-10-05 (UTC), before slice 2.8 draws
its sample and before a holdout exists. It closes questions е, ж and з of
plan G38. The fifth revision gave these checks to models of two and three
vendors; plan decision D12 leaves the plan one model, so the rules below
replace those and are the ones that run. Where this file, the NLI research
or a row of the plan still names two or three models, a model of another
vendor or a `model-cross-checked` ruler for work done after 2026-10-04, this
section and the rubric in force for the step govern.

**The model and the route.** `claude-opus-5-5` (Anthropic). Every request to
it that this file registers — a relevance grade, a label check, a draft, a
reference label, an answer check — is one new process started by
`evaluation/isolated_request.py`:

- route `Claude Code CLI in safe mode, first-party provider`, effort `max`;
- session `safe mode: no instruction file, memory, hook, skill, plugin or
  MCP server; no tools; an empty working directory; nothing stored; one
  turn`;
- the registered system prompt of the check on the command line and the
  request text on standard input, and nothing of the session that planned
  the check.

The reply is read from the event stream of the CLI, every text block in
order. Beside it the route keeps the *session record*: the CLI version, the
model id, the number of turns, the number of context tokens, and the names
of what the session loaded, in seven lists — tools, MCP servers, slash
commands, skills, memory, plugins that are not built in, hook events. A
reply counts only when the session, every message and the usage record name
the registered model, alone and from the first-party provider; when each of
the seven lists is empty, literally; and when the reply came in one turn
that the model ended itself. What the CLI builds in is kept in a part of
its own and is not among the seven lists: its own plugins — those it marks
`builtin` — and its agent types. Their names are registered from the probe
of the route, in `evaluation/isolated_request.py` (CLI 2.1.289: three
plugins, four agent types). A session that names a built-in outside the
registered ones, or an output style other than the default, gives no
counted reply: the route is probed and registered again first. The
registered system prompt is passed by `--system-prompt`, which replaces the
CLI's own. A script that computes a number reads no verdict without such a
record.

Two blocks the CLI puts into every request cannot be switched off under a
subscription login, and they belong to the route: a description of the
account and a description of the environment — working directory, platform,
shell, OS version, model name and id, knowledge cutoff, today's date. As far
as the probe of 2026-10-05 showed (CLI 2.1.289), a request holds these two
blocks beside the registered prompt and its own text, nothing of the
built-in plugins or agent types — with no tools there is nothing that
describes them to the model — and no case, arm or task. That is what a
probe saw, not a check of each reply: per reply the record holds names and
the number of context tokens, not the text the CLI added. The date makes
requests of two days differ by a line. The route reports the model id and
no finer revision. The CLI version
is stored with every reply and published; replies under two CLI versions
are joined, replies under two model ids never.

What went before: until 2026-10-05 the requests to this model were sent
without safe mode — the 35 requests of the pilot label check (step 1.3b)
and the 10 of the P2 Opus reference collection — and the events of their
sessions were not kept. A probe of the same arguments, on the machine and
under the CLI version of the 35, shows what such a request carries beside
the registered prompt: the owner's instruction file for coding sessions,
the output of two session hooks — a pointer to installed skills and a list
of skill names picked by the words of the request — and the two blocks
above. In the probe request none of that text named a case, a label or a
verdict; what the second hook picked for each of the 35 is not known.
Whether it moved a verdict was not measured; that it can shape a reply is
plain — the
file asks for answers in Russian. For the ten requests of the P2
collection, sent under an earlier CLI version, what exactly was attached is
not known. Those verdicts and numbers stay published with this caveat, the
pilot cases are checked again under this route in step 1.3d, and no reply
sent before the route is joined in a number with a reply sent under it.

The exact prompt and rubric of each check are registered with their SHA-256
before its first request — for 2.8 before the sample is labelled, for 4.1
before the rehearsal below. A changed prompt is a new version, and replies
of two versions are not joined. The text of no request holds a request id, a
pass suffix, an arm or the name of a mechanism; a test of each tool asserts
it.

**Passes and attempts.** Every unit — an assertion of the 2.8 sample, a
request of an answer check — is sent in two passes, each a new session,
each into a store of its own; the second has the request id
`<request id>~pass2`. Passes of one model are not voices: an error the model
makes every time counts as confirmed, and no status in this section says
otherwise. Agreement of the passes shows neither that a rubric is
unambiguous nor that a label is right, and each capsule says so. A request
that gets no reply — a usage limit, an outage, a session the route refuses —
stays in the store as unavailable and is not counted among the attempts:
the check waits, and an explicit rerun sends the request again. A reply
that does not follow the registered form is asked for again, three attempts
in all; a pass left without a valid reply after them is invalid. The first
valid reply of a unit and pass is final, and no later reply replaces it.
What an invalid pass does to a label or a verdict is said with each check
below; it is never scored as a wrong answer.

A check runs in stages. A script moves it from one stage to the next and
prints request ids and counts, never a verdict.

1. The requests of the first two passes — in a comparison those of both
   arms — are sent in one order, by the SHA-256 of
   `20260925:order:<request id with its pass suffix>`: neither an arm nor a
   pass goes first, and a change of date or of CLI version falls on both
   alike.
2. When they are stored, the script lists what the registered rules send
   next — third passes, a top-up, added control cases. To do so it
   compares fields; it shows none.
3. Those are sent and stored. The script then lists the requests that
   wait for a class verdict as it stands after the third passes — the
   `gold_error` requests and the answer control of the rehearsal — and
   prints their ids only; both passes of these are sent in the same hashed
   order and stored. There is no further round.
4. The verdicts are derived, and only then joined to an arm or to the
   output of a judge.

Before stage 4 no verdict is printed or read outside the script.

**Model unavailable (question з).** While the model gives no reply the check
waits. No other model is substituted: not a model of another vendor (D12),
and not another model of the same vendor, whose label would be another
labeller's. Decision D12 names this model. If the provider withdraws it,
the work that needs it stops until the owner names a model in a decision of
the same level; nothing is chosen in her place. Under the newly named model
a check starts again from its registration: every unit of a comparison is
checked anew, the stability retest and the rehearsal are repeated before
the holdout is opened, and replies of two models are never joined in one
number. If the model is withdrawn after the holdout is opened and before
the checks of acceptance are complete, acceptance closes `INCONCLUSIVE`: the
checker of a one-shot holdout is not chosen after its answers exist.

**Reference of the NLI validation (slice 2.8; question е).** The reference
label of an assertion is the label of this one model under the four-label
rubric of the [NLI research](research-nli-judges.md) (§3.3). A request holds
what the research shows a labeller — the question, the whole answer with the
unit marked, the five contexts numbered and cut as the judge cuts them — and
no score, no source and no output of a judge. The second pass presents the
five contexts and the four label definitions in a second order, seeded by
the request id. Each pass's label is reduced to supported (SUPPORTED), not
supported (PARTIAL or UNSUPPORTED) or not a claim (NOT_CLAIM). An assertion
is *stable* when the two passes give the same reduced label, and that label
is its reference label. Otherwise it is `unstable`: it takes the place of
«no majority» of the fifth revision and of the AMBIGUOUS flag of the
research — outside every deciding number, counted and listed. An assertion
with an invalid pass has no reference label either; it is listed apart and
counts with the unstable ones in the bound below.

The labeller has a control. Units of strata b3 and a4 — the units the
current judge scores highest — are drawn before any label, in the order of
the SHA-256 of `20260925:nli_control:<claim_id>`: the first 20. Each is
sent in both passes with, in place of its own five contexts, the five
contexts of the next drawn unit, cyclically, whose contexts come from no
document family of this unit's contexts — by the registered family map,
where the stored contexts name their source documents. Where they do not,
the partner is a unit of another case that shares no context text with it,
and the capsule says the control was built without the family rule. A unit
without such a partner gets no control request and is counted. Nothing in
those contexts was retrieved for the unit, so the expected reduced label is
not supported or not a claim. The control labels are stored apart and enter
no κ. The control is read over the drawn units whose label in their own
contexts is stable and supported: a unit that is no claim, or is not
supported where it was retrieved, would pass the control for nothing. When
fewer than 10 of the first 20 are such, further units are drawn in the same
order until 10 are or the two strata end. Over fewer than 10 the control
bounds nothing, and a judge accepted on such a reference carries «labeller
control not read» in its status line.

The stability bound is computed and published before the output of any
judge is joined to a label, after the top-up below and over the whole
sample. The rubric is taken as ambiguous when more than 10 % of the
sample's assertions are unstable; or when the CI95 lower bound of Cohen's κ
between the two passes on the reduced label is under 0.6, the retest bar of
the research — cluster bootstrap by `case_id`, 2 000 resamples, percentile
interval, seed 20260925; or when more than one tenth of the units the
control is read over are labelled supported in both control passes. The
rubric is then clarified once. The clarification is written in a stateless
request that holds the rubric, the unstable units with the labels of their
two passes, the control units labelled supported in both passes with the
contexts they were shown, and nothing else. Only the text of the rubric
changes, and it may quote no unit of the sample: a script refuses a rubric
that holds eight consecutive words of a unit, an answer or a context. The
new version is registered with its SHA-256 and its diff before its first
request, and the whole sample is labelled again in two passes, with a
control drawn anew under `nli_control2`. The second bound is read on the
sample the clarification was written from: it is in-sample, and the capsule
says so. No κ of a
judge to labels of the first version is computed. A second failure closes
the slice without an accepted judge: the reference is not used, and every
judge stays `provisional_judge` and is printed with that caveat whatever
its κ.

The registered criteria — out-of-fold κ ≥ 0.6, CI95 lower bound ≥ 0.4,
recall of «not supported» ≥ 0.7, system |Δ| ≤ 0.05 on C.1a and on C.1b —
are computed on the stable units whose reference label is supported or not
supported. The weight of a stratum is its pool size divided by its stable
units, for the judge and for the reference alike. Beside each criterion the
capsule prints the same number with every unstable unit counted against the
judge — given the label opposite to the judge's, and for the system |Δ| the
range between all of them supported and none; these numbers decide nothing.
The top-up rule of the research — fewer than 40 not-supported units, 50 more
from a2, a3 and b2 — counts stable not-supported units and is applied once
for a rubric version, before the output of any judge is joined.

A judge accepted by these criteria carries the status
`single_model_referenced`, written with the labeller's id and the count
«on <stable> of <sample> units». The criteria were written for a human
reference and then for a majority of three models; their numbers are
unchanged, and the status says what they were met against. It is not
`human-validated` and not validated against labels of several vendors. What
it does not cover: a support judgement this model gets wrong the same way
in both passes, and the question the research left to human labels —
whether 1.0 on C.1b is real — beyond what one model's labels say. The
sample, the strata and the choice rule stay those of the research, with
these parts not applied. No LLM judge L is run (its row of §3.4, item 7 of
§3.5, the third bullet of §3.7 (3)): under D12 it would be this same model
scored against its own labels — a third pass, not a validation. The
sentences of the plan row on a majority of three models are void. The
labelling by a person and the seven-day retest interval fall away, and the
retest of 40 assertions is contained in the second pass. If no configuration
passes, the tiers of §3.7 (4) and the word `NLI_NOT_VALIDATED` are not used:
every judge stays `provisional_judge`. Compared are M0–M3 and the optional
A3 and B2. An accepted judge decides nothing at acceptance (below): its
number is printed.

**Answer checks of acceptance (slice 4.1; question ж).** An answer is
checked by four kinds of request, each sent in passes and stages as above.
None names an arm, a mechanism or another answer; the arm is joined after
the verdicts are stored (G34). The checked answer is that of the first
measured repeat of its case and arm.

- *Grounding* holds the question, the context exactly as sent and the
  answer with its citations, and no part of the label. It returns the
  factual statements of the answer that the sent context does not support —
  none, when every statement is supported.
- *Action* holds the question and the answer, without the context and
  without the label. It returns which of the five actions the answer
  performs. The script compares it with `expected_action`.
- *Facts* holds the question, the answer and the required facts of the
  case — the critical ones among them, unmarked — and no context. For each
  fact it returns whether the answer states it, misstates it or leaves it
  out. On a case whose trap type is outdated rule it also holds `as_of` and
  the registered reason of the case, and returns whether the answer
  presents the superseded rule as in force.
- *Context* holds the question, the context exactly as sent with its
  documents numbered, and the required facts of the case that are not
  derived; no answer. For each fact it returns the numbers of the documents
  that contain it — none, when no document does. A derived fact is never
  sent: its presence in a context is the evidence-group rule of «Fact
  presence».

Facts and Context are the two kinds that show a part of the label: the
facts and, in Facts on an outdated-rule case, `as_of` and the registered
reason. A context is judged without the answer in view, and an answer
without the context. Grounding and Action are sent for every answer; Facts
for every case that has facts and for every case whose trap type is
outdated rule; Context for every case with a fact that is not derived. Two
arms whose requests of one kind are identical — equal SHA-256 of the
canonical request — share that check, so identical outputs cannot differ by
the noise of the checker: two arms with one answer share Action and Facts,
two arms with one sent context share Context. The passes of a request are
byte-identical, because the numbers of the documents refer to the order of
the sent context. Whether two replies to one request differ on this route
has not been observed. The rehearsal publishes, per kind, the share of
requests whose first two replies are identical byte for byte; where the
passes repeat each other exactly their agreement measures nothing and the
10 % bound below cannot fail, and the capsule says so in these words.

In a retrieval-only comparison of track 3 there is no answer, and Context
is the only kind sent. It is sent, in both arms, for every case with a
critical fact that the matcher does not find in the sent context of at
least one arm («Fact presence»), in passes and stages as above, and its
verdict decides the critical-fact rule there.

A *field* is what the script reads from a reply. What a reply holds beyond
the fields — the wording of an unsupported statement — is stored and is not
compared.

| Request | Field | Feeds |
|---|---|---|
| Grounding | `supported` — the reply lists no unsupported statement | `faithfulness` |
| Action | `action` — one of the five | `action_correct` |
| Action | `class` — *answered* (answer, correct the premise) or *abstained* (refuse, escalate, clarify), read from the action of each pass | `abstention_correct`; which cases are answered, and so the pairs of every metric over answered cases; critical errors of types 1 and 2; the `gold_error` request |
| Facts | per fact, `treatment` — states, misstates or leaves out | `answer_fact_coverage`; `citation_correctness`; critical error of type 1 |
| Facts | `outdated` — the answer presents the superseded rule as in force | critical error of type 3 |
| Context | per fact, `contained` — the reply names at least one document — and `cited` — it names at least one document the answer of the arm cites; both read from each pass | the critical-fact rule; `citation_correctness` |

A field has a verdict when two valid passes, of at most three, give it one
value. When the first two passes are both valid and equal on every field
of a request, those values are its verdicts. Otherwise the request is sent
a third time, `<request id>~pass3`, in stage 3, and each field takes the
value two valid passes share. A field on which no two valid passes agree
has no verdict. Nothing is scored against an answer for that. A missing
verdict counts only where a derivation below reads the field on that case
and the verdicts the case does have leave the outcome open. It is not read
and does not count: the `treatment` of a fact that is not critical and that
the matcher finds in the answer; the `contained` or `cited` of a fact whose
quote the matcher finds; a field of Facts, for a critical error, on an
answer whose class is abstained. Where it counts for a metric the case is
invalid for that metric: it leaves numerator and denominator, is listed,
and is a lost pair under the pair mask of the contract; a per-fact field
does this for its case. For the two rows that are rules without an interval
— `critical_errors` and the critical-fact rule — a case is then without a
result. For the critical-fact rule: the `contained` of a critical fact has
no verdict in an arm, and the fact is neither known to be absent from the
control's context nor known to be present in the candidate's. For
`critical_errors`: as said with the types below. A row with such a case is
`INCONCLUSIVE` unless a case that has a result fails it. The rule
is the same for both arms. A reading in which every disagreement counts
against the candidate arm was considered and is not the deciding one: once
the share of disagreements exceeds the margin it fails whatever the arms
do. It is printed as a sensitivity view, with its mirror image.

What the script derives from the verdicts, and nothing else decides:

- pairs. A metric over answered cases is computed on the cases whose class
  is answered in both arms. A case answered in one arm only, or without a
  class in an arm, is a lost pair. It is charged to each arm in which its
  class is not answered — abstained or missing — and so to both when
  neither arm has an answered class. The base of the shares is the cases
  that are answered in at least one arm or lack a class in at least one
  arm. The pair mask of the contract is read on it: more than 10 % of the
  base lost, or shares charged to the two arms that differ by more than 5
  points, and the metric is `INCONCLUSIVE`. In the worst-case view of the
  contract an arm takes the metric's worst value on every pair charged to
  it, and the other arm keeps its own value where it has one. Without this
  an arm that abstains on its hard cases would take them out of its own
  denominator;
- `faithfulness`: 1 for an answered case whose answer Grounding finds
  wholly supported, else 0 — a share of supported statements is not
  computed, since the passes would have to cut an answer into the same
  statements. This check decides the metric whatever slice 2.8 concluded: a
  judge accepted there is accepted as an approximation of this model's
  labels, and at acceptance the model itself is asked. Beside it the
  capsule prints the number of the NLI classifier with the status slice 2.8
  left it, and the 0.90 of phase C as a line that is not applied; neither
  decides. The LLM part of the phase-C judge is not run and its number is
  `N/A`: no model but `claude-opus-5-5` is asked to judge (D12). The capsule
  names every model other than `claude-opus-5-5` that produced a number in
  it;
- `abstention_correct` on a case registered as unresolvable is 1 when the
  class is abstained;
- `action_correct` is 1 when the verdict of `action` is the registered
  action;
- facts follow «Fact presence» (G23). `fact_coverage` is the matcher's
  number. An answer *states* a fact when the matcher finds it in the answer
  or, where the matcher does not find it or cannot settle it, when its
  `treatment` is states; a critical fact is stated only by its `treatment`,
  whatever the matcher found. `answer_fact_coverage` is the share of the
  case's facts the answer states. In a sent context a critical fact the
  matcher does not find takes `contained`. The findings of matcher and
  model are printed side by side;
- `citation_correctness`, per case: of the required facts the answer
  states, the share that stand in a cited document. A fact whose quote the
  matcher finds in a cited document does; any other fact does when its
  `cited` is true; a derived fact does when the cited documents satisfy
  every evidence group of the case. This holds for critical and other
  facts alike. The case counts when it is answered in both arms, has facts
  and has, in each arm, at least one citation and at least one stated
  fact. A case that meets this in one arm only is excluded from both,
  counted by reason and by arm, and is not a lost pair; the others are
  counted by reason. Every sent document is cited today, so the number
  says whether what the answer states of the label stands in a document it
  cites, and the capsule says that it is not claim-level citation
  correctness;
- critical errors are derived, never asked for. Type 1, a wrong answer on a
  safety-critical or dangerous-goods case: the case carries the
  `safety_critical` flag or the dangerous-goods trap type, the class is
  answered, and the `treatment` of a critical fact is misstates or leaves
  out; a wrong statement beside correctly stated critical facts is charged
  to `faithfulness` and is not this error. Type 2, a confident answer where
  refusal or escalation was required: `expected_action` is refuse or
  escalate and the class is answered, on a case not found `gold_error`.
  Type 3, an outdated rule presented as current: the trap type is outdated
  rule and `outdated` is true. On a case an arm's error of a type is
  *established* by these conditions and *excluded* when a verdict rules
  them out: type 1 when the class is abstained or every critical fact is
  stated, type 2 when the class is abstained or the case is `gold_error`,
  type 3 when `outdated` is false. It is neither when a verdict it needs is
  missing or, for type 2, when the case has no `gold_error` result. A case
  is without a result for the row when it leaves open whether the candidate
  makes a new error on it: a type is neither established nor excluded there
  for the candidate — unless the control makes that error on the case and
  the type is on the list below — or a type on the list is established for
  the candidate and is neither for the control. A type can be observed
  only where its inputs
  exist — type 1 on cases with critical facts, type 2 on cases registered
  refuse or escalate, type 3 on outdated-rule cases — and the capsule gives
  the number of such cases per type beside the count of errors: «all cases»
  of the contract row are the cases examined, not cases on which every type
  could show. An error is **new** as the contract says, by either clause.
  The first: the control does not make it on the same case. Two arms with
  one answer share Action and Facts and so make the same errors, none of
  them new by this clause. The second: its type is not on the list of types
  observed in the project before. No capsule published before this revision
  names a critical error of these types, so the list starts empty; it takes
  the types the rehearsal below finds for the control arm and is frozen in
  the capsule that opens the holdout. An error of a type outside the list
  is new even when both arms make it. That is the contract as registered
  (№12) and it is kept: it can block a mechanism for an error the control
  makes too, and the capsule says which clause made each error new;
- `gold_error` has a request of its own. When the class verdict of at least
  one arm's answer is answered on a case registered as unresolvable, it is
  sent for the sent context of each arm — once, where the two contexts are
  identical — in the second round of stage 3. It holds the question, the
  registered action with its reason,
  `as_of` and every document of that context with its document card, as
  the label verifier receives it — no answer and no arm. It checks the
  label, not an answer, and so it shows the registered action. It returns
  the one document that, being in force on `as_of` and applicable to the
  question, makes answering the right action, or none. It is sent in two
  passes and never a third: the case is `gold_error` when, in the request
  of either context, both passes are valid and name the same document.
  Where no context gives that and a pass of a request of the case is
  invalid, the case has no `gold_error` result, and nothing is charged to
  an answer for an invalid pass: the case is a lost pair for
  `action_correct` and `abstention_correct`, and type 2 is neither
  established nor excluded on it. A context without a document gives no
  request.

For each field and arm the capsule publishes the disagreement of the first
two passes: the share, among the arm's requests of that kind that carry the
field, of those on which the field — for a per-fact field, the field of any
fact — is not one value in two valid first passes, and κ. The requests that
carry a field: for `supported`, `action` and `class` every request of the
kind; for `treatment` the Facts requests with at least one fact; for
`outdated` the Facts requests of outdated-rule cases; for `contained` every
Context request; for `cited` the Context requests of the cases whose answer
in that arm has a citation. A request two arms share counts in each. A
metric fed
by a field whose share exceeds 10 % in either arm is `INCONCLUSIVE`, as a
metric that loses more than 10 % of its pairs is: a majority over that much
disagreement is not a measurement. For `critical_errors` and the
critical-fact rule the same share leaves the row `INCONCLUSIVE` unless it
has failed.

**Rehearsal on a development run.** One mechanism is named in the ledger
before the first request of the rehearsal, by the rule of the decision
rule. The answer checks then run in full — four kinds of request, passes,
stages — on both arms of the development run in which that mechanism
reached `SHIP_TO_HOLDOUT`, with answers generated under the generator
fingerprint of acceptance. It sends its own Context requests, for every
case with a fact that is not derived, and reuses no reply of the track-3
comparison, whose verdict stays as derived from its own replies. The
rehearsal gives the paired variance of each
answer metric — the refinement on development data that plan step 1.3c asks
for before the holdout is opened — the disagreement shares, the share of
identical replies, and the answer control. What it shows of the arms — the
answer metrics, the critical errors — is printed and decides nothing about
the mechanism: the named mechanism is not exchanged for another after it.
Two things are taken from it and no more: the list of critical-error types
found for the control arm, read from the verdicts of the last registered
version of each prompt, and the critical-fact rule when Context is
registered again (below).

The answer control. The development cases whose `expected_action` is answer
or correct the premise are put in the order of the SHA-256 of
`20260925:answer_control:<case_id>`. The control is read over the first 10
of them whose control-arm answer has the class verdict answered — an answer
that abstains states nothing that could lack support — so its requests are
listed in the second round of stage 3, when those verdicts exist. Each such
case gives a Grounding request with the control arm's answer and, in place
of its own context, the control-arm context of a partner case: the next
case of that order, cyclically, that shares no family with it. A case
without such a partner gets no control request and is counted, and the next
answered case of the order takes its place. Nothing in that context was
retrieved for the answer, so the expected verdict is not supported. A
control request is sent in two passes and never a third; one with an
invalid pass leaves the control and is counted. The control is crossed when
more than one tenth of its requests are found wholly supported in both
passes. Read over fewer than 5 requests it bounds nothing.

The rehearsal is passed when the control is read and not crossed and no
field's disagreement share exceeds 10 % in either arm. A crossed control is
a failure of Grounding, and a share above 10 % a failure of the kind of its
field. A control that bounds nothing is a failure of no kind: no prompt is
registered again for it, and the holdout is not opened. The prompt of each
kind that failed is registered again, and that kind alone is sent again in
full on the same run. Its disagreement share is then read on the cases the
new prompt was written after: it is in-sample, and the capsule says so.
When Grounding is the kind registered again, and only then, the control is
drawn anew under `answer_control2`. When Context is, the critical-fact rule
of the named run is derived again from the new replies; a loss it then
shows makes that run `NO_SHIP`, and the holdout is not opened. A kind is
registered again once in a campaign, and a kind that fails after that
closes the campaign without acceptance 4.1. After a passed rehearsal the
prompts are frozen: the holdout is checked with the versions the rehearsal
ran.

**Opening the holdout.** Until the tenth revision the holdout opened only on
a `model-cross-checked` ruler. That status belongs to the consensus on the
sample of step 1.1 and stays there; every grade made since decision D12 is
`single_judge`. The holdout is now opened when all of this holds for the
development run in which the named mechanism reached `SHIP_TO_HOLDOUT`: the
stability retest of the judge of new texts passed on it — by the one
interval of its whole sub-sample, which pools the primary classes of the
verified set and, for both arms, the seeds before expansion and the
expanded sent contexts; both bounds of its contamination controls were read
and neither was crossed; and the rehearsal of the answer checks was passed.
On a `provisional_ruler` the holdout is not opened, nor on a run whose
contamination is not bounded. The acceptance run repeats the retest and the
controls on the holdout's own grades, with no second attempt: a retest that
fails there or stays `NOT_EVIDENCE`, or a control bound crossed there, makes
every metric computed from grades `INCONCLUSIVE`, and a bound that could
not be read there is printed as «contamination not bounded» beside the
verdict. The verdict words are unchanged. A capsule of acceptance under
these rules reports its verdict as reached on a `single_judge` ruler with
answers checked by one model; gives the retest κ, the controls, the
disagreement of the passes and what the route puts into a request; and
says that no person took part (D11) and that no model of another vendor
decided a grade, a label or a verdict (D12), naming the NLI classifier
whose number it prints.

## Baseline of plan slice 2.5

Registered in the ninth revision, 2026-10-05 (UTC): the collection of the
baseline was still running and no relevance grade of it existed. The report
is built by `scripts/baseline_report.py`; these rules were written before the
script.

- **Population.** H 100 + Hm 15 in the configuration of the collection:
  hybrid retrieval with production expansion, graph `off`, model routing off,
  single-turn; retrieval, rerank and grading, no generation. H and Hm are
  reported apart and no pooled number is formed. A case the collection
  excluded leaves every metric and is listed.
- **What each number is computed on.** `precision_at_5` and `ndcg_at_5`: the
  first five reranked seeds, their texts before expansion. `sent_precision`:
  the documents left after grading — the sent context. Lexical
  `context_precision`: the question as asked, not its rewrite; the texts of
  the sent context in their order; the case's `expected.answer_contains` as
  keywords. Printed beside it as a diagnostic, `context_precision_seeds`: the
  same function over the first five seeds before expansion — the kind of
  context the 0.63 threshold was set on. The sent-context number is on
  expanded texts; 0.63 is printed beside it and is not applied to it. A case
  with an unjudged text among its five seeds or its sent documents leaves the
  three judged metrics with the reason and stays in the lexical ones.
- **Not measured, printed as `N/A` with the reason.** `evidence_recall_pool`,
  `all_evidence_coverage` and `fact_coverage`: H and Hm carry no registered
  gold spans, evidence groups or facts; the loss map of the same slice reads
  their keyword terms instead. Every answer metric and `critical_errors`:
  nothing is generated in this mode, so the semantic invariants of a real
  answer (fact, citation, action — plan G12) are not observed here and stay
  with steps 2.8 and 4.1.
- **Cluster unit.** The registered family map. A case's families are those of
  the documents the map lists for it under
  `development_used.<subset>.case_documents`: for H the documents of its
  phase-C top five that P2 graded, for Hm its `source_documents`. Under this
  rule H has **4 clusters — of 94, 2, 2 and 2 cases — and Hm has 1**, of all
  15. Neither the map nor the rule is changed to get more: nearly every H
  case shares a topic family with another through the documents of its top
  five, the Hm cases share theirs through their sources, and showing that
  dependence is what the unit is for.
- **Intervals.** 10 000 resamples, seed 20261001, percentile CI95 — the
  constants of `evaluation/semantic_ruler.py`. Both subsets have fewer than 10
  clusters, so the interval-validity rule of the decision rule applies to this
  single arm as it does to a paired difference: the cluster-robust t-interval
  is printed beside the bootstrap, and the capsule reads the wider bound on
  each side. With one cluster no variance can be estimated: the t-interval is
  the whole range of the metric, [0, 1]. Printed beside as a sensitivity view
  and named so — a bootstrap over cases, each case its own cluster; it ignores
  the dependence the family map describes and is narrower than the truth.
  Neither interval is a statement of how well the baseline is known that a
  decision may rest on. The points are read as points.
- **MDE and power.** A single arm has no paired difference. For every deciding
  metric the report prints `n` and the clusters, and `N/A` with this reason
  for the MDE and the achieved power. The cluster counts are an input of plan
  step 1.3c: a development set whose cases join into a few components cannot
  reach the registered power whatever its size, so 1.3c checks the
  development set for the same collapse before it registers a size.
- **Timings.** p50 and p95 per stage from the collector's trace: one run on
  one host, its pauses and the foreign load on the host listed;
  `latency_evidence` is false. `retrieve_p95` is that run's number without an
  interval. It is not the control of the ≤ 200 ms check, whose protocol —
  interleaved arms, three repeats a case, warm-up excluded — this run does not
  follow.
- **Status.** `single_judge`, as «Relevance grades» registers it, and
  `provisional_ruler` until the stability retest of the same run passes — and
  afterwards if it does not. The baseline carries no contamination control
  (tenth revision): H and Hm have no gold spans to cut or swap, and its
  capsule says so.

## Provenance every report carries

Corpus SHA-256, code SHA, full config including `RAG_RERANK_BATCH`, model and
reranker digests, graph digest and `entity_graph_status` from the retrieval
path, cached contexts, raw judge replies with request hashes, bootstrap seed,
host. Added 2026-09-30 (Astra): ingestion snapshot id and `chunker_version`
(G3), effective query with transformation type and hash (G4), routing mode
(G9), generator fingerprint (G19), embedder id / HF revision / dimension /
query and document prompts / normalisation as stamped in the index manifest
(G25 — a matching dimension alone is not a matching model), fact-matcher
version (G23), judge model / revision / rubric version (G16; for the one
judge of decision D12 the revision is what its route can give — the model
id, the route and, per reply, the CLI version with the session record), the
label-migration report of the corpus version (G16), residency mode
and peak host RSS (G5), the ledger entry of the configuration (G7), and for
every deciding metric `n`, clusters, MDE and achieved power (D9). A run
missing any of these is `NOT_EVIDENCE`; a field that does not apply to an arm
(graph digest and `entity_graph_status` for a graph-off arm) is printed as
`N/A`, never omitted (Astra final-plan audit №4). The embedder manifest and
its load-time check are mandatory for every arm, hybrid included (plan 2.3,
mandatory part).
