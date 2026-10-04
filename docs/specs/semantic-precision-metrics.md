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
  independent voice).
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
  references, before any semantic gain is claimed; the plan budgets it but
  has no slice row or outcome rule for it yet (plan G38). A second
  indeterminate κ after the 30-case sample leaves the ruler
  `provisional_ruler`: no semantic gain is claimed on it and the holdout is
  not opened for acceptance 4.1 on it. The judge set is then re-registered
  once, as in branch (1); if that set does not pass either, the campaign
  closes without acceptance 4.1 and the owner decides what follows (until
  2026-10-03 the owner decided right after the second indeterminate κ).
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
  published ten-case grades of step 1.1 predate this protocol and carry none,
  and where later collections add them is still open (plan G38);
  ambiguous and invalid answers counted with their reasons; the rubric is
  not adjusted after a holdout result is seen; κ is stated for its rubric,
  language and context type only. The branching after an indeterminate κ is
  the rule above (10 → 30 cases, then `provisional_ruler`); the sample is not
  grown open-endedly toward a wanted κ.
- No human annotator (G15 as changed by D11): neither a first nor a second
  person grades. The agreement between the reference models — on the
  relevance pairs of the 1.1 sample and on the assertions of the 2.8 sample —
  is published with its CI and the disagreement matrix. It is a reference
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
where containment is ambiguous by the blind judge with the same rubric; the
matcher version is part of the provenance and a changed matcher recomputes
every published `fact_coverage`. A numeric fact is registered as a claim
`{subject, value, unit, polarity, condition}` — polarity from a registered
lexicon (разрешено / запрещено / не более / не менее / только при …) — and is
present only when number + unit match inside a window that also carries the
subject and the same polarity marker: «150 кг разрешено» does not match «150 кг
запрещено» (Astra final-plan audit №18). Critical facts are never resolved by
the matcher alone: each is confirmed by the blind answer check of 4.1 — two
reference models, both must confirm (decision D11; until 2026-10-03 a blind
human check).

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
`model_verified`, with the verifier ids and the rubric version — see «Label
verification»), the seed-selected source section, the
primary class (single-doc / multi-doc / aggregation / needs refusal or
clarification), overlapping flags (RU→EN, numeric facts, trap type among
false premise / out of corpus / outdated rule / conflicting documents /
dangerous goods, safety-critical), `expected_action` (answer / correct the
premise / clarify / refuse / escalate), `as_of`, the authority source of the
rule and the severity of a wrong answer. Quotas live in the plan (1.3d); an
unmet quota narrows the scope of the conclusion instead of being filled.

Label verification (decision D11, added 2026-10-03; rubric
`label-verification/v1`, registered 2026-10-04 in plan step 1.3b before the
first check; it replaces the human approval of decision D3): no person
approves a case. Two verifier models from two vendors, neither of them the
draft author's vendor, check every dev and holdout case independently, each
blind to the other's verdict. The draft author is the registered generator of
the case, recorded per case as `draft_author` with its model and vendor (the
pilot: `gpt-6.1-sol`, OpenAI).

Registered verifiers for drafts by an OpenAI model:

| Verifier | Vendor | Route | Settings |
|---|---|---|---|
| `glm-5.3` | Z.ai | direct `api.z.ai` messages API, streamed | effort `xhigh` |
| `claude-opus-5-5` | Anthropic | Claude Code CLI, first-party provider | effort `max`, no tools |

One request holds one case for one verifier, in a new session with no
conversation state and no tools. A reply counts only when the route reports
the registered model id. The request names neither the draft author nor the
other verifier and carries nothing of an earlier round. The exact prompt is
registered with the rubric: plan step 1.3b records its SHA-256 here in the
commit that adds the verification tool, before any request is sent; a reply
counts only when the prompt SHA-256 stored with it is the recorded one, and
a changed prompt is a new rubric version.

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
4. the primary class, the flags, the trap type and `expected_action` agree
   with the above;
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

A verifier answers `confirm` or `reject` on checks 2, 3, 4 and 5d, with a
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

A case without a valid reply from both verifiers has no outcome in that round
and keeps `label_check: none`. With two valid replies the case is confirmed
when check 1 passes, both verifiers confirm checks 2, 3, 4 and 5d, neither
rejects 5a or 5b, and on 5c neither verifier's level is two or more steps
from the registered one or on the other side of the `critical` boundary;
otherwise it is rejected. A confirmed case carries `label_check:
model_verified` with the verifier ids, the rubric version and the round. If
either verifier answers `unverifiable` on 5a or 5b, the confirmed case
carries `authority_unverified: true`: it stays in the set and does not count
toward the safety-critical quota; counts of safety-critical cases are
reported with and without such cases. A one-step severity difference that
does not cross the `critical` boundary is published as a disagreement, not a
rejection.

A rejected case is repaired once by the draft author, who sees the reasons of
both verifiers. A repair changes the label, never the question: the case id,
the question text, the draft author, the corpus version, `as_of`, the
seed-selected section and the question style stay as drafted; spans, partner
sections, facts, the reference answer, the class, the flags, the trap type,
`expected_action`, its reason, the authority documents and the severity may
change. A repair cites no document of the holdout reserve. A case that could
be repaired only with one is dropped without a second round: the draft author
declares it and names the reserve document, and that declaration is recorded
as the reason of the drop. The families of a repaired case are recomputed and
published. A new question is a replacement of the
case, which belongs to question в of plan G38, not a repair. The repaired
case passes the per-case rules of the verify script and its source checks;
the rules of the draft set as a whole — quotas, the split of styles, the
SHA-256 of the file — bind the unchanged drafts only. Both verifiers then
check the repaired case in full, in the same form and with no trace of the
first round. A second rejection drops the case, with the rejecting checks
recorded. A relabelled class or action changes the class counts: rejection
shares are reported by the drafted class, the verified set by the class
after repair, with the transitions listed, and the quota rule above applies.
If fewer than two vendors other than the author's are available (a quota, an
outage), verification waits: a second model of one vendor is not a second
voice. The same holds for the repair when the author model is unavailable.
Step 1.3b is closed only when every draft is confirmed or dropped.

The verifiers receive the whole draft case — question, span texts, facts with
their quotes, reference answer, class, flags, trap type, `expected_action`,
the registered reason, `as_of`, the authority documents and the severity —
with every source named by a pseudonym, never by its file name (plan G31); a
file name inside a corpus text is replaced by the pseudonym of that document.
The `scope` text of the pilot's `authority_source` is a template of the draft
phase and is not sent. For check 5 they receive the document card of each
authority document: the front-matter fields `title`, `document_type`,
`source_type`, `version`, `effective_date`, `owner_role` and
`related_normative_sources` of the source file at the registered corpus
version, and nothing else of the front matter. For refusal, clarification and
trap cases they also receive the text of the seed-selected and partner
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
disagreements between the verifiers, the cases flagged `authority_unverified`
and the dropped cases. `label_origin` stays `agent_labelled`: a model check is
not a human approval, `real_labelled` is not assigned and the count of real
labelled cases does not rise. The check bounds label errors, it does not
prove their absence: models can share an error, and on refusal, clarification
and trap cases a passage outside the wide scan can leave an answerable
question registered as unanswerable (plan G37). At acceptance such a case is
resolved by the `gold_error` rule of the contract below. The severity scale
was written after the pilot drafts were labelled; a severity the scale does
not support is a rejection like any other. Still open in plan G38: the
replacement of dropped cases (question в, before step 1.3c registers n).
Screening drafts (below) are checked once by one model of a vendor other than
their author's; rejected drafts are dropped, and more than 10 % rejected
means the generator is rewritten and the check repeated (G32).

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
  dev families only, kept apart from the verified set (`model_verified`; until
  2026-10-03 «the human set»), run retrieval-only with
  the consensus judge and the retrieval stages the mechanism needs. Judge
  grades are cached by the full request hash — `(question_hash, the ordered
  text_sha256 list of the presented set, rubric version, judge version)`:
  documents are graded jointly, neighbours and order can move a grade, so
  only an identical set in the same order is reused (Astra final-plan audit
  №19); the expected number of new requests is published before the run; a run graded by one judge because the other
  hit its limit is `single_judge`, outside the consensus (G24). It ranks
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

Two acceptances (A3, A12). The holdout is opened only when the ruler is
`model-cross-checked` («Relevance grades», the scope item).
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
| `faithfulness` | higher | answered cases | NI −0.02; the blind answer check by two reference models decides while `provisional_judge` (D11) | cluster bootstrap |
| `answer_fact_coverage` | higher | answered cases with facts | NI −0.02 | cluster bootstrap |
| `citation_correctness` | higher | citations made; cases with none counted separately | NI −0.02, resolved by the blind answer check by two reference models (claim↔source; D11) | cluster bootstrap |
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
- wrong gold on an unresolvable case (`gold_error`, plan G38, question а):
  when an arm answers a case registered as unresolvable and cites a passage,
  the two answer-check models decide, blind to the arm, whether that passage
  — a passage of the registered corpus, in force on `as_of` and applicable
  to the question — makes an answer the right action instead of the
  registered one. If both confirm, the case's outcome is `gold_error`: the
  label was wrong. The decision is stored apart from the holdout, which is
  not edited after it is opened, and applies to every arm alike: the case
  leaves `abstention_correct` and `action_correct`, and an answer on it is
  not counted as the critical error «confident answer where refusal or
  escalation was required». Nothing else is forgiven: the faithfulness and
  citation checks of each answer stay scored, and a critical error that does
  not rest on the registered action — a wrong answer on a safety-critical or
  dangerous-goods case, an outdated rule presented as current — stays
  counted for the arm that made it. The case's eligibility for every other
  metric stays as registered; the capsule lists the case with the passage
  address and publishes the denominators with and without it; the stratum
  loses the case for the action metrics and its conclusion narrows as for an
  unmet quota. If only one model confirms, the registered label stands and
  the answer is charged as registered;
- answer checks are done by two reference models from two vendors, neither of
  them the answer generator's, registered with their versions, prompt and
  rubric before the holdout is opened; the checks are blind to the arm:
  answers of both arms
  are presented shuffled without an arm label, and the label is joined after
  the verdicts are stored (G34). A critical fact, a faithfulness verdict and
  a claim↔source link count only when both models confirm them; a split
  verdict counts against the answer and is listed. No person checks answers
  (decision D11), and the capsule says so. Who decides `action_correct`,
  `abstention_correct` and a disputed critical error is not registered yet;
  it must be before the holdout is opened (plan G38);
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
| `faithfulness` | the phase-C judge (LLM judge with the NLI second judge) on the answer against the sent context; the phase-C condition (≥ 0.90 target) is reported as its own gate. The NLI model and threshold used here are the ones registered by plan slice 2.8 (validation against LLM-judge verdicts and a model reference — the majority label of three models from three vendors; no human labels since decision D11); until 2.8 closes, the pinned `mDeBERTa-v3-base-mnli-xnli` at 0.5 is `provisional_judge` |
| `answer_fact_coverage` | required facts present in the answer divided by the case's facts |
| `citation_correctness` | cited sources that are in the sent context and support the cited claim, divided by citations made; the API today emits one citation per sent document (`agent/graph.py` ~1943), not per claim, so until a claim-linked citation exists the metric is resolved by the blind answer check of 4.1 (two reference models, both must confirm; decision D11) — for each required fact in the answer, whether a listed source contains it (Astra final-plan audit №18) |
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
4.1 is the blind answer check by two reference models already in the contract; the NLI number
and the phase-C ≥ 0.90 gate are printed with the `provisional_judge` caveat
(№18).

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
