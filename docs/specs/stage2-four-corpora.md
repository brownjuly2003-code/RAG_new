# Stage 2: the four corpora measured on the fixed chat path

Status 2026-10-19: **registered before the stage's first request** — parts 1, 2, 4 and 5;
part 3, the graph lane, amended on 2026-10-19 before any request of its own: GR-3's archives
counted, the live lane moved to stage 7 ([below](#part-3-the-graph-lane--amended-2026-10-19)).
[`PLAN.md`](../../PLAN.md) §5, stage 2, is the authority. This spec writes down everything
that must not be chosen after seeing an answer: the stand, the questions and their order, the
forecasts and stop rules, what each number is and how it is read, the judge, what is
`NOT_EVIDENCE`, and what each record holds. Parts 1–4 are preparation; part 5's record, its
test and its evidence row are rule (c) — the first quality numbers on the customer's path, the
four corpora side by side. A cold read of the draft by a fresh agent on the session's model
found 28 problems; this text answers them (listed [at the end](#what-the-cold-read-corrected)).

## What is measured, on what

- **The path.** The web chat, `/api/ask/stream`, each question sent as a visitor's first (a
  fresh session, no history), at the code defaults: the 3,600-s ceiling, the reranker on the
  CPU (`RAG_DEVICE=cpu`), Qwen3-4B-Instruct-2507 (`qwen3:4b-instruct-2507-q4_K_M`) on Ollama,
  on `deproject-mac`, production's machine. Retrieval: BM25 and BGE-M3, 20 candidates each,
  fused by RRF; the bge-reranker-v2-m3 scores every fused candidate and keeps 5; parent
  expansion; `_fit_stream_prompt` fits the documents to the model's window; prompts V3
  (`agent/prompts.py`).
- **The stand.** The archive (`git archive`) of the commit that registers this spec and the
  stage's tools, at `/Users/julia/RAG_new_chat_<commit>`, raised by the command of the
  [stage-1 handoff](../operations/session-handoff-2026-10-18-stage1-closed.md) («Next actions»
  2). Its product code is that of `4ca5ddd`, the stage-1 rerun's: outside docs, reports, tests
  and the root `.md` files the diff from `4ca5ddd` adds only `scripts/context_judge.py`, which
  no product module imports. Every request of parts 1, 2 and 4 runs on this one stand. A
  change of product code or prompts is a new stand, and everything run before it runs again;
  so is a change of a tool that sends the requests or drives them — `live_supervisor.py`,
  `live_runner.py`, `live_retrieval.py`, `live_api.py`, `stage2.sh`. A fix of a summary or of
  the judge's export reruns offline on the kept runs, its record naming the tool's new
  SHA-256.
- **The indexes.** The second generation, `/Users/julia/RAG_new_external_s1/<base>/index/chroma`
  (built at `e5e135a`, 2026-10-18). Each run reads a byte-identical copy made just before it
  and removed after it — the API writes into the database it opens, and the generation stays
  as its receipt describes it. Every record carries the SHA-256 of the generation's
  `corpus.manifest.json`, `chunks-report.json` and `index/index-receipt.json`; a retrieval
  record also that of the chunk archive `chunks.json.gz`, refused unless the receipt names
  it.
- **Tenants:** `aircargo`; `ext_conditionalqa`, `ext_wixqa`, `ext_multihoprag`.

## The questions, in order

| Key | Questions | Count | What they hold |
|---|---|---|---|
| `aircargo` | `evaluation/curated_cases_aircargo.jsonl`, file order | 100 | Russian; two keywords each (`expected.answer_contains`, M2) |
| `aircargo-gr` | `evaluation/curated_cases_aircargo_gr_multihop.jsonl`, file order | 15 | GR's questions that need several documents; part 2 only (part 3's baseline before its amendment) |
| `conditionalqa` | selection `stage2`, then `stage2_not_answerable` | 80 + 20 | 40 documents × 2 primary questions, 26 of them conditional; then 20 not answerable — no gold, no reference answer |
| `wixqa` | selection `stage2` | 100 | the first 100 tuning questions (77 clusters, all of the `simulated` stratum); 1–3 gold articles and one reference answer each |
| `multihoprag` | selection `stage2` | 100 | the first 100 advisory questions (15 clusters): 70 `inference_query` with 2–4 gold documents, 30 `null_query` with none; one reference answer each |

The selections are those of `evaluation/external_parts.json`, registered at `e5e135a`, before
stage 2's first request. `reports/stage2/tools/stage2_cases.py KEY CASES_FILE` prints a key's ids in this
order — through `evaluation.external_parts.read`, which refuses a locked part — and refuses an
id its questions file lacks (an external base's is `<base>/cases.jsonl` of the generation,
every question of the base) or an id that repeats. Answers go in batches of ten in this
order: batch *b* holds questions 10*b* − 9 to 10*b*.

## Parts, forecasts, stop rules

| Part | Work | Forecast | Stops at |
|---|---|---|---|
| 1 | aircargo, 100 answers: 10 batches of 10, each one supervisor run — a fresh API and database, the model loaded (timed apart) and unloaded after | a batch 4,060 s: 120 s the API's start and the model's load, 340 s the first question, 400 s each other; 11.3 h | a question past 1,020 s (a batch's first) or 1,200 s (the others); the part past 3 × 10 × 4,060 s (33.8 h) |
| 2 | retrieval without the answer model, 415 questions: one run per key — aircargo 100, aircargo-gr 15, each external base 100 | a run of *M* questions 140 + 40*M* s (60 s to build the retriever, 120 s the first question, 40 s each other): 4,140 s for 100, 740 s for 15; 4.8 h | a question past 360 s (the first) or 120 s (the others); a run past 3 × (140 + 40*M*) s |
| 3 | the graph lane on aircargo — amended 2026-10-19: GR-3's archives counted by a test | none of the Mac's or the judge's time (registered: ≈ 1–1.5 h) | none: no request |
| 4 | 300 answers on the external bases: 10 batches of 10 per base, as part 1 | as part 1: 11.3 h a base, 33.8 h the three | as part 1, per base: a base's part past 33.8 h |
| judge | 115 requests (part 1), 130 (part 2), 345 (part 4), on the laptop | an answer 80 s and $0.15, a context 40 s and $0.10: 11.7 h, ≈ $82 | a plan's run past 3× its forecast |

The answers' forecasts are PLAN's; stage 1's V3 answers, each a fresh API's first question,
took 399 s (aircargo), 285, 336 and 335 s (ConditionalQA, WixQA, MultiHop-RAG). Retrieval's
first question is the cpu placement's of [`reports/chat-live/33d4b42/`](../../reports/chat-live/33d4b42/)
(120.35 s with the models' load); a later one, 27.6 s there, is 40 s from the smoke below:
24.0 to 44.1 s on the four bases, the reranker scoring pools of 32–38 candidates. The
retriever built in 8–21 s there; 60 s holds it with the process's start. The judge's are the
smoke's: an answer 77.7 s and $0.145, a context 35.9 s and $0.094.
The stop rule is Julia's (2026-10-15): 3× a question's named forecast. `live_runner.py` ends a
batch at its first question past its cap; `live_retrieval.py` ends a run the same way, and the
supervisor's timeout bounds the run; `stage2.sh` checks the part's cap and the stop file
before each batch. The part's cap belongs to one invocation of `stage2.sh` — 3× the forecast
of the batches it is given — and is read between batches, a batch itself being bounded by its
questions' caps; a rerun is an invocation with a cap of its own, and the record sets the
part's measured hours against its forecast.

**One, five, the rest** (Julia's rule). An answers part, part 4's each base too, runs its
batch 1 alone. Its first answer is read when it lands, then its first five: the time against
the forecast, the route, the answer's script against the question's, the prompt's labels
`[N | source=…]`, and the path (below). Batches 2–10 start after batch 1 completes and those
five read clean — no path break, no question at its cap, the labels in every prompt; the
time, the route and the script are reported, not gates (stage 1's aircargo answer took 399 s
against the forecast's 340). A retrieval run's first question is read the same way as it
lands; part 2's runs go one after another.

**The path breaks** — stage 1's definition — when the record of an answer or a retrieval shows
an empty lane (no vector or no BM25 candidate), a rerank status other than `ok`, fewer than 5
documents returned, no `Restored N chunks` line for the run's tenant or a `Chunk restore
failed` or `WITHOUT BM25` line for it, an HTTP status other than 200, or no answer (no result
event or no streamed token). The API's start also loads the tenant `default`, which logged
`WITHOUT BM25` on the smoke stand: not the measured path. The test runs three times over:
`live_retrieval.py` ends a run at the first question whose path breaks (exit 6); the driver
runs it on every batch and every retrieval run as it ends (`answers_summary.py check`,
`retrieval_summary.py check`), and a break stops the part; both summaries list what they find
under `path_breaks`, per question and per run (an answers run's restore line is in its
`api.log`, a retrieval run's in its `progress.log`), and part 5's test asserts that no counted
question has one. An answer that never came — the runner's exit 4 — is a path break too, not
a failed batch to rerun. The work stops and Julia is told first: a fix is a new stand, and
everything run before it runs again. A lane with fewer than 20 candidates (BM25 keeps only
positive scores), an answer in the other script, a low self-score or the route `human` is
measured, not a stop.

## What each number is

- **M1, the answer's verdict** (parts 1 and 4): the shares of good, partial_ok and bad answers
  (`classify` of the answer judge: good — complete against what the documents offer and
  fully supported, or a right decline; partial_ok — faithful but partial; both only where the
  documents hold the answer, [as amended](#the-judge) before the first grade); of the `[N]`
  marks that name a listed document, those whose statement the document supports; marks that
  name none, counted without the judge; the defects. An empty answer is bad without a request.
- **M2, against the gold.** aircargo: the case's keywords in the answer by the repository's
  rule (`scripts/ab_remote_contextual._kw_status`: FULL, PART, MISS) — a weak gold, printed as
  it is. External bases, a question with an answer: the judge's `reference` — agrees, partial,
  disagrees, declined. A question without one (ConditionalQA `not_answerable`, MultiHop-RAG
  `null_query`): right when the judge's `answers_question` is `declined`, wrong otherwise.
  The two are printed apart, never pooled. The judge's private references file holds the
  answers of the questions with one only — ConditionalQA's answerable, WixQA's, MultiHop-RAG's
  `inference_query` (a `null_query`'s answer in the dataset is not a reference) — so a
  question without one reaches the judge with none. ConditionalQA's 26 conditional
  questions are printed apart too: their references are the bare answers without the
  conditions, so `agrees` there can hide a missing condition.
- **M3, the context.** The registered point is «sent», the documents of the prompt the model
  reads.
  - aircargo: primary, part 2's context judge at «sent» — `full` and `partial` hold the
    answer; part 1's `context_has_answer` of the answer judge is printed beside it, with the
    two's agreement on the questions both read.
  - External bases, part 2: the gold's coverage by `evaluation/external_gold.py` (rule
    `external-gold/range-coverage-v1`) through `scripts/external_pilot.read_gold`. Primary:
    ConditionalQA and MultiHop-RAG `all_evidence_coverage` — every evidence group of the
    question covered by a chunk present — with `evidence_recall`, the share of groups covered;
    WixQA `gold_article` — a gold article present — with `gold_articles`, the share. Read at
    each point of the path — each lane's 20, the fused pool, the reranked five, the expanded
    five, «sent» — so a loss is placed. A document the fitting cut counts the paragraphs of its
    excerpt found in place; WixQA counts the article when the excerpt shows text of it.
    Questions without gold (20 + 30) stay out; `gold_in_index` says whether the generation's
    index holds the gold at all, the ceiling. A point that cannot be read — a chunk without a
    place in its document — ends the reading of the question there, and the record counts it
    (`unresolved`). Each point prints its n; two points are compared only on the questions
    read at both.
- **The K curve** (part 2, external bases; stage 4's input). For K = 1 … 20 the pool is the
  union of the first K of each lane, and the kept five are its top five by part 2's
  cross-encoder scores (kept whole, so a tie is a true one), ties in fused order; the coverage
  of the kept five per K. At K = 20 it must give the run's ranked five as a set
  (`k20_is_ranked`); a question where it does not is left out of the curve and counted, and an
  order that differs within the five is counted apart (`k20_order_differs`). The first K of a
  lane stand for what a search of K would return: exact for BM25, an approximation for the
  vector lane, whose HNSW search goes deeper for a larger K. The curve ends at the reranked
  five: expansion and the fitting are not replayed. aircargo has no deterministic gold: its
  scores are kept for stage 4, which judges the contexts it needs.
- **Parity.** The SHA-256 of a question's retrieval prompt against that of its answer's stream
  prompt (parts 1 and 4). Equal: part 2's M3 is the M3 of the context the answer was written
  from. Unequal: counted, and for that question part 2's M3 describes retrieval alone.
- **M4, the route:** `auto` or `human` per answer, with the self-score and its source. The
  signals S1–S8 are stage 3's ([handover plan](handover-signal.md)).
- **M5, time and memory:** per question the first token, the result, retrieval, rerank and
  the stream; per batch the model's load; swap, the least free memory, the largest resident
  size by process kind. Incidental to quality runs, so no basis for a speed decision
  (PLAN §4.3); a batch's first question is read apart.

**How the numbers are read** (PLAN §4.4). Each share is printed with its n and its Wilson 95 %
interval: at n = 100 the half-width is at most 10 points, at the 80 and 70 questions with gold
of ConditionalQA and MultiHop-RAG 11, at their 20 and 30 without gold 20 and 17, at
aircargo-gr's 15 23. An external base's questions are not independent — MultiHop-RAG's 70
with gold form 15 clusters, one of 49; ConditionalQA asks two questions of each of 40
documents; WixQA's 100 form 77 — so its shares also print the cluster count and a
cluster-bootstrap 95 % interval (`evaluation.semantic_ruler.cluster_summary` over the clusters
of `evaluation/external_parts.py`: ConditionalQA the questions of one document, WixQA and
MultiHop-RAG the questions joined by a shared gold document; a question without gold is a
cluster of its own), and the wider of the two intervals is the one read. Two corpora are
independent samples: at 80 % power and α = 0.05 two-sided a difference below about 20 points
(16 near a share of 0.8; 23 between the 80 and the 70 questions with gold) cannot be detected
— written «not detected», never «no difference». Two points of one question set — M3 at
«ranked» and at «sent», two values of K (part 3's pairing withdrawn by its amendment) — are
paired: McNemar's test on the discordant questions, detecting about 2.8·√(d/n): 9 points when
a tenth of the questions disagree, 13 when a fifth do. A stage-2 number decides nothing alone;
stages 3, 4 and 7 read it under their own registrations.
Numbers far from phase C's (the 4B: 67 good, 21 partial, 12 bad) are a finding, not a stop:
phase C judged fixed contexts, not the chat's retrieval.

## The judge

- **One judge**, `claude-opus-5-5` at effort `max` (`evaluation/isolated_request.py`, `MODEL`
  and `EFFORT`): stateless requests by the registered route, on the laptop. A verdict counts
  only with the record of a clean session and the hash of its planned request.
- **Answers, parts 1 and 4:** `scripts/chat_answer_judge.py` as committed (salt
  `chat-answer-judge-2026-10-18`, frame `QA_PROMPT_V3`), one English prompt for every corpus,
  the answer due in the question's language. Per answer: the material claims and how many the
  documents support, whether the documents hold the answer, whether the answer gives it, the
  supported marks, a defect and, given the case's reference answers, M2. One plan per part and
  base, each with 15 retests: part 1 its ten counted batch runs (115 requests); part 4 each
  base's ten, `--references` the reference answers of its questions that have one (3 × 115).
  Part 1's plan is the [handover-signal plan](handover-signal.md)'s 1.2: before its first
  grade `judge_export.py reading` writes into its `plan.json` the key `reading` — that plan's
  reading, «frozen in stage 1's `plan.json`, before its first verdict», copied from the
  committed text with the commit it is copied from — and 1.4 applies it as frozen.
- **Contexts without an answer, part 2:** `scripts/context_judge.py`, new with this spec
  (salt `context-judge-2026-10-19`): whether the documents of the prompt the chat would send
  hold the answer — `full`, `partial`, `none` — and which documents hold a part; a context
  without documents is `none` without a request. One plan for the aircargo and aircargo-gr
  runs: 115 contexts and 15 retests.
- **Stability.** A plan's numbers count when its retest pairs — the valid ones, at least 12
  of the 15 — pass either way, over the plan's ordered scale (the three classes of `classify`,
  or the three levels):
  - the quadratic kappa is at least 0.6, the value of the repository's precedent
    (`PASS_KAPPA`, `evaluation/nli_validation.py`); or
  - at least 13 in 15 of the pairs agree (13 of 15 or 14, 12 of 13, 11 of 12) and none is two
    steps apart (good and bad, full and none).

  The second way exists because on 15 pairs the kappa follows the classes' shares: 14 pairs
  of good and one of good and partial give a kappa of 0.0 at 93 % agreement. A kappa that
  cannot be computed leaves the decision to the agreement. The precedent holds the lower end
  of a bootstrap 95 % interval to 0.6, over a far larger sample; on 15 pairs that interval is
  too wide to decide anything, so it is printed, not gated. Fewer than 12 valid pairs, or
  neither way passed: that plan's numbers are `NOT_EVIDENCE` and Julia is told; the prompt is
  not tuned on the same answers — a changed prompt is a new registration with its own
  retests. The record prints the pairs, the agreement, the kappa and its interval (the scheme
  of `scripts/p2_reference_kappa.py`), and the agreement of the verdicts' other fields on the
  pairs (M2's `reference`, `answers_question`, `context_has_answer`, the documents that hold
  a part), not gated apart.
- **Re-asks and the cap.** The adapter asks a request up to three times while the reply is not
  of the registered form; one more `run` of the plan asks again those still without a valid
  verdict, and no further one counts: the export takes a verdict only from a request's first
  six replies, and a request without one is missing, never guessed. A plan's run past 3× its
  forecast pauses, and Julia gets the measured pace and a new forecast before it goes on.
- **What it reads stays off the repository.** The judge reads copies of the run folders —
  `launch.json`, `cases/` and `prompts/*-stream.txt` of an answers run, `launch.json` and
  `retrieval/` of a retrieval run — and the reference answers, in
  `D:/RAG_new_stage2_private/` on the laptop: outside `D:/RAG_new`, so `sync.py` never ships
  it and no commit takes it. Its plans, verdicts and summaries stay there. A request carries
  the question, the documents and the reference to the judge's provider; the rule bars a
  commit or a publication of them, and a request is neither.
- **What leaves it:** `reports/stage2/tools/judge_export.py`, committed with a test before
  the judge's first grade, writes each plan's record from its plan and verdicts — per
  question its ids, class or level, the enum and integer fields, M2 by the split above, no
  note — and the plan's numbers: the counts per run, the stability rule's figures and
  verdict, the field agreement, the cluster intervals; `stage2_common.without_text` guards
  it like the summaries.
- **When.** A plan freezes every request before the first grade: part 1's after its tenth
  batch, part 2's after both aircargo runs, each base's of part 4 after its tenth batch. A
  failing route (a CLI update, a plugin that refuses it) or a spent usage window pauses the
  judge; the Mac's parts go on.
- **Amended 2026-10-19, before the first grade,** on a second opinion in two rounds: Codex
  `gpt-6-astra`, effort xhigh, read-only, on frozen packages of the judges, the export, their
  tests and this spec — session `01a1566e-2af8-7da1-8f0b-43bff2b2040b` at `d006d7b`, then
  session `01a15697-40e7-71e0-b7d1-4a648fc3de86` on the fixes. Each point was checked in the
  code; taken:
  - a plan counts only when it is its judge's and whole — the code's salt, rules and route,
    each request the text its hash names, each id once, at most one retest of a request and
    that one its copy — checked before a request is sent and again when a verdict is counted.
    The hashes inside a plan cannot show an edit of the whole, so each plan's SHA-256, its
    reading written, is committed before its first grade, and its record names it;
  - a verdict counts only from the plan's model, and the six replies bind the sending too: a
    resumed run asks a request no further than its sixth reply and refuses a row of a request
    the plan does not hold; the export reads the whole journal, the rows past the sixth
    included, by the same checks;
  - each string of a record's question row is an identifier or a registered value (letters,
    digits and `_.:~-`), so no text of a question, a document or an answer rides in a row;
  - `classify` takes `full` and `partial` only where the judge finds the answer in the
    documents (`context_has_answer`), since both weigh the answer against what the documents
    offer; otherwise the answer is bad, and `answer_without_context` counts how often;
  - a kappa that cannot be computed is none, as the rule above reads it — the code gave 1;
  - part 4's plans name the SHA-256 of their references file, which holds a question once, and
    the export takes no other file; an empty answer to a question without a reference is M2's
    wrong, as above — the export had a value of its own for it;
  - the context judge's documents stand smallest first; M2's `reference` agreement is read on
    the pairs of a question with a reference only;
  - a record whose retests fail the rule says `NOT_EVIDENCE` in its status, and the export
    exits 3.

  Deferred, each to before what it bears on: whether part 4 reads M1 in a request without
  the reference, so that the reference cannot sway it (before part 4's first grade); the
  record's full schema, the pairs' ids and each verdict's basis of admission (before part 4's
  records); the denominators and intervals of M1's other parts (part 5's record). The plans,
  journals and run copies stay in the private folder, so each deferred count can be made
  later from what was graded.
- **Amended 2026-10-23, before part 4's first grade:** part 4 reads M1 in a request without
  the reference — the first deferred point, decided by the session under Julia's word of
  2026-10-19 («Прими решения сам из цели - лучший продукт в финале»). The ruler is one: part
  1's aircargo requests carry no reference, so an external M1 read beside one would be another
  measurement, and whether a reference sways the judge is not known. Each base gets two plans
  of its ten counted batch runs — the same answers, item ids and 15 retests:
  - `p4-<base>-m1`, `plan --references FILE --withhold-references`: the file named by its
    SHA-256 for the strata and clusters only, every request with «none» for the reference; its
    M1 is part 4's M1, and its record holds no M2;
  - `p4-<base>-m2`, as registered above: its `reference` and declines give M2.

  The m2 plan's M1 fields are printed beside the m1 plan's on the same answers — the
  reference's sway — and gate nothing. 6 × 115 = 690 requests; forecast ≈ 45 s and ≈ $0.11 a
  request, ≈ 8.6 h and ≈ $76; a plan's run past 3× its forecast pauses. Each plan's SHA-256
  is committed before its first grade. The tools: `chat_answer_judge.py plan
  --withhold-references` and `judge_export.py`'s reading of such a plan, with their tests.
- **Settled 2026-10-23, before part 4's records:** the record's schema, the pairs' ids and
  each verdict's basis of admission. A judge record holds `plan`, `status`, `judge`, `base`;
  `provenance` — the SHA-256 of the plan, the journal, the references file, the rules, the
  adapter and the tool, `references_withheld`, the salt, prompt id, route, runs, the replies
  counted per request and the reading; `replies` — rows, statuses, past the limit, models,
  cost, and for every counted verdict, retests included, the reply that admitted it
  (`admitted_at_reply`) and the CLI it ran under (`admitted_cli`); `questions`,
  `requests_valid`, `missing`, `per_run`, `shares`; `retest` with `pairs_ids`, the first
  request of each pair in the order of `pairs_list`; for answers whose requests carried
  references `m2`, and on ConditionalQA the conditional split; for contexts
  `holds_the_answer`. A question row: the plan's ids and counts, `grade`, `missing`, the
  verdict's fields but the note, `admitted_reply` and `admitted_cli`; on an external base
  `stratum`, `cluster`, `conditional` and, where references were carried, `m2`. Part 1's and
  part 2's records, exported before this, lack the admission fields and `pairs_ids`; their
  private journals give them.
- **Settled 2026-10-23, before part 4's first record — part 5's reading,** the third deferred
  point, under the same word of Julia's:
  - **M1's other parts.** The supported marks: of the marks naming a listed document
    (`marks_listed`) in the answers with a verdict, those the judge finds supported
    (`citations_supported`); the claims likewise (`claims_supported` of `claims_total`). Each
    is a share of marks or claims, not of answers, so beside its Wilson interval it prints a
    cluster-bootstrap interval — the answer is the cluster on aircargo, the question's cluster
    on an external base — and the wider is read. The marks naming no listed document: their
    count and the answers with one. The defects: the share of graded answers whose defect is
    not `none`, and each defect's count; `answer_without_context`, a count. On ConditionalQA
    and MultiHop-RAG, M1 is also printed by stratum: without an answer, good is a right decline.
  - **Two corpora**, aircargo against an external base, per class of M1: the difference of
    the shares with Newcombe's hybrid score interval, each side taken from its share's read
    interval — Wilson on aircargo, the wider of Wilson and the cluster bootstrap on an
    external base. «Detected» when the interval excludes zero, «not detected» otherwise, never
    «no difference». Three comparisons per class, printed as found, none corrected for the
    others; the external bases are not compared with each other.
  - **The reference's sway**, per base: the m1 and m2 plans' classes on the answers both
    graded — the 3 × 3 counts, the agreement, the pairs two steps apart, the quadratic kappa;
    printed, not gated.
  - **aircargo's M3:** the context judge's record split by run, aircargo's 100 and
    aircargo-gr's 15 apart; its `full` or `partial` against part 1's `context_has_answer` on
    the questions both read.
  - The tool, `reports/stage2/tools/stage2_record.py`, is committed with its test before part
    4's first record. It reads committed records only and writes
    `reports/stage2/5e308fe/stage2-record.json`; part 5's test derives that record again.

## What is `NOT_EVIDENCE`

- A batch that did not complete — all of it, the answers before a question past its cap
  included: a batch counts whole or not at all. A retrieval run that did not complete — all
  of it: its summary refuses it.
- A batch run its rerun replaced (kept and listed, not counted).
- Any run on another stand, the smoke stand of the next section included.
- A judge plan's numbers when its retests fail the stability rule; a verdict without its clean
  session record, or past a request's first six replies. A missing verdict is counted as
  missing, never guessed.
- A question's K curve when K = 20 does not give its ranked five.
- M5's numbers as the basis of a speed decision.

## Outcomes, and what Julia is told

- **A question stops at its cap, or a batch fails.** Read the batch's `supervisor.log` and
  `api.log`, then rerun the whole batch once (`SUFFIX=-r2`) on an idle Mac; the record keeps
  both runs and counts the rerun. A second stop in the part — the rerun or another batch —
  means the pace changed: the part stops, and Julia gets the measured times; nothing more of
  it runs, a further rerun included, without her word. If the part ends there, its
  denominator is the questions counted, and the rest are listed as not measured. A retrieval
  run is rerun whole, never from the question it stopped at; its `missing` is counted against
  the registration.
- **The path breaks**, an answer that never came included: above — stop, Julia first; a fix
  costs Mac hours.
- **The Mac is busy at a batch start:** the driver waits 180 s for free ports and an empty
  Ollama, then stops. Find what holds the Mac; never stop another project's process; tell
  Julia if it is hers.
- **A part passes its cap:** it stops, its unsent questions are `NOT_EVIDENCE`, and Julia gets
  the measured pace and a new forecast.
- **The judge:** a plan that fails the stability rule, a run past its cap, or a failing route
  — above.
- **At each part's launch** Julia gets its forecast and its end in her time; one word from her
  stops it. **At the end:** the first quality numbers on the customer's path, the four corpora
  side by side with their limits and provenance; the push is asked; stage 3 follows on the
  same 100 aircargo answers.

## Running it

On the stand, `S=/Users/julia/RAG_new_chat_<commit>`, the tools in `$S/chatlive/`; the idle
check of the handoff first (no `llama-server`, supervisor or pytest; the 5-minute load below
2; Ollama holding no model). Each part runs detached, and ssh returns at once:

    ssh deproject-mac "mkdir -p $S/chatlive/runs; nohup sh $S/chatlive/stage2.sh MODE PART KEY /Users/julia/RAG_new_external_s1 [FROM [TO]] > $S/chatlive/runs/PART-KEY.out 2>&1 </dev/null &"

(`;`, never `&&`, before `nohup`: the shell would background the whole list, which holds the
ssh channel until the part ends), with `MODE` `answers` (`FROM`, `TO` batches) or `retrieval`
(questions); `PART` `p1`, `p2`, `p4`. The driver's log is `runs/PART-KEY.log`; each run's folder `runs/<label>/`, its labels
`PART-KEY-bNN` (answers) or `PART-KEY` (retrieval), a rerun adding `SUFFIX`. To stop before
the next batch: `touch $S/chatlive/runs/PART-KEY.stop`. To stop at once:
`pkill -f "stage2.sh MODE PART KEY"`, then `pkill -f "$S/chatlive/live_runner.py"` (answers)
or `pkill -f "$S/chatlive/live_retrieval.py"` (retrieval); the supervisor then stops the API
and the database and unloads the model. While a part runs, its label, log and stop command
stand in [`CURRENT_STATE.md`](../../CURRENT_STATE.md). No `sync.py` or `remote.py` during a
run, and one measurement on the Mac at a time.

## The records

Under `reports/stage2/<stand commit>/`, written on the Mac by the stand's summaries and copied
back; every file passes `stage2_common.without_text`, which refuses a record when a string of
it is the name of a document of the base or holds a question (`evaluation/external_bases.json`,
"redistribution": counts, digests and the ids of questions leave the hosts, never a question,
evidence string, document, chunk or embedding).

- `p1-aircargo.json`, `p4-<base>.json` (`answers_summary.py PART-KEY ROOT OUT`): provenance —
  code, model and digest, the settings and their SHA-256, the overrides, the generation's
  files, the questions file, each tool's SHA-256 —, every run of the part with what counted,
  the driver's log lines, the aggregates; `.cases.jsonl` beside it, one counted question a
  line: times, HTTP status, route, self-score, sources, the letters of the question and the
  answer by script, the answer's marks, the stream prompt's labels and SHA-256, the
  retrieval's path, each fused candidate as [vector rank, BM25 rank, cross-encoder score], the
  model calls, memory, `path_breaks`; aircargo's M2.
- `p2-<key>.json` (`retrieval_summary.py RUN ROOT OUT [ANSWERS_CASES]`): provenance as above
  plus the measuring code's SHA-256 and the registrations'; per question (`.cases.jsonl`) the
  walls, the rerank status, the lanes' sizes, the pool as ranks and scores, the kept scores,
  the expanded and sent documents' counts and sizes, whether the fitting cut one, the prompt's
  SHA-256 and size, parity, `path_breaks`; on the external bases the stratum, gold, `gold_in_index`, the
  coverage at each point and the K curve. An external base's file is written again after
  part 4, with its answers' cases for parity.
- The judge's, per plan, by `judge_export.py` on the laptop: the plan's numbers — counts per
  run, the retest's pairs, agreement, kappa and interval, the stability verdict, the field
  agreement — and per question its class or level and its verdict's fields but the note, the
  judge's own sentence.
- Part 5: a test that derives every published number from these files, one row in
  [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md), the numbers in `CURRENT_STATE.md`.

## Part 3, the graph lane — amended 2026-10-19

**As registered:** the chat path has no graph runner: GR-3's `scripts/gr3_graph_lane_ab.py` and
`scripts/extract_graph_entities.py` read phase C's contexts and the first generation's chunks.
An amendment was to register, before part 3's first request, the graph (GR-3's, or rebuilt on
the second generation), the lane's runner on this stand, the same 115 questions, M3 by
`context_judge.py` paired against part 2's contexts, the forecast and the stop rule. Stage 2
was not to close without part 3 unless Julia said so.

**The amendment, before any request of part 3.** Julia delegated the choice on 2026-10-19:
«Прими решения сам из цели — лучший продукт в финале».

- **The forecast's premise failed.** PLAN's 1–1.5 h assumed GR-3's graph. Stage 1 changed the
  chunk texts, so GR-2's entity cache is refused and its graph would load as `mismatch`
  (`vectordb/manager.py` 1040–1064: the persisted graph's structural part must equal the one
  rebuilt from the restored chunks, content hashes included). The live entity lane needs the
  entities of the second generation's 5,589 aircargo chunks extracted again (GR-2's benchmark:
  11.4 s a chunk with qwen2.5:7b, ≈ 17.7 h of the Mac — an extrapolation from eight chunks); a
  step persisting the entity graph, which does not exist; a runner; Postgres and model routing
  in retrieval mode, so a new stand. In all ≈ 25–30 h of the Mac and 1–2 days of work, with
  part 4 waiting for the Mac. The structural route alone needs no extraction, but the same
  runner, routing and stand.
- **GR-3's committed archives already show what the graph route did with these questions.**
  `evaluation/gr3-32de532-{phase-c,bucket}-{Hm,G1m,G2m}-candidates.json.gz` hold the same
  100 + 15 questions; their SHA-256 are in the [GR-3 record](../evidence/gr3-graph-lane-ab.md).
  `Hm` is the hybrid, `G1m` the structural route, `G2m` structural + entity.
  - G2m hands on the same candidates as G1m on 98 of 100 phase-C questions and on 15 of 15
    bucket questions. GR-3 builds every arm's context through one function with one top-k and
    one cap (`scripts/gr3_graph_lane_ab.py`, `_score_arm`), so the entity lane changed the
    context on at most 2 of 115 questions. Entities matched on 5 of 100 and on 11 of 15.
  - Those 2 are the only questions where a graph arm hands on a source that none of the
    hybrid's five candidates comes from.
  - Otherwise the graph route trims the hybrid's context: ≈ 3 documents against 5 (305 on 100
    questions, 45 on 15); on 57 of 100 questions (59 for G1m) and on 5 of 15 every document is
    one of the hybrid's five texts verbatim. A subset adds no evidence, and a share of useful
    documents can rise from the smaller denominator alone.
  - `tests/test_stage2_part3_archives.py` pins the archives and every count.
- **So part 3 is this archive diagnostic: no request, no time of the Mac or the judge.** It
  replaces the registered comparison and the close condition: stage 2 closes with part 3 as
  this finding, under Julia's delegation above — it stands for the word
  [item 26](#what-the-cold-read-corrected) asks for.
  - **Not done:** the judge on GR-3's arms (≈ 245 context requests). The arms ran on the first
    generation's chunking in GR-3's harness, not on the chat's path: the result would decide
    nothing now, and stage 7 measures on the final path anyway.
  - **To stage 7:** the live measurement, the structural route (G1) first. Universality asks
    more than a new extractor: the section, quote and order cross-references are Russian
    patterns (`ingestion/structure_graph.py` 28–43), the entity prompt is Russian, the
    normalisation uses hand-made aliases, and the web stream calls the hybrid retriever, not
    the graph route. M3 at «sent» by `context_judge.py`, paired with the hybrid on the same
    questions, hybrid → structural and structural → entity apart: the whole context's
    completeness and the evidence each arm loses, exact McNemar on «full» and on «full or
    partial», the retest drawn from both arms.
  - **Part 5's record** carries the counts and states what they cannot show — answer quality,
    latency on the current path, the second generation's effect, whether a graph helps on the
    final path.
- **A second opinion:** Codex `gpt-6-astra`, effort xhigh, read-only, session
  `01a15640-3635-7312-97fc-f13e40635ec5`, on a frozen package of this repository's files at
  `d006d7b`; it saw no archive. It agreed, with amendments, all taken above: call the result a
  diagnostic and change the close condition in writing; separate the entity lane's effect from
  the structural route's; read a subset as another selection, not a better one; count the
  context GR-3 handed on, not raw candidates (GR-3's table counts 3.04 and 2.93 a question,
  the raw archives 3.05 and 3.00); universality asks more than a new extractor. Not taken: the
  judge on the 2 changed questions' four contexts — two questions decide nothing, and the
  extractor that made them is to be replaced.

## The tools

Copied to the stand's `chatlive/` in this order, the second set replacing the first's
`live_api.py`:

- `reports/stage1/tools/`, unchanged: `live_supervisor.py` (one run: the database, the API and
  the model, or retrieval alone; `TENANT`, `CHROMA`, `CASES_FILE`), `live_runner.py` (the
  client), `launch.py`, `audit.sh`, `audit_summary.py`, `s1_supervisor.py`.
- `reports/stage2/tools/`: `live_api.py` — stage 1's, plus two rows per retrieval, the lanes
  and every fused candidate's cross-encoder score: the wrapper asks the rerank for every score
  and hands the product's first five back, the same objects in the same order (the product
  scores every candidate anyway, then cuts; the runner asks one question at a time, so the
  wrapper's temporary change of the retriever's `rerank_k` meets no other request);
  `live_retrieval.py` — retrieval alone for any tenant: the API's retriever, the chat's
  `_fit_stream_prompt` with the provider's window, one record per question, the retriever's
  restore lines in the run's `progress.log`; `stage2.sh`, the
  driver; `stage2_cases.py`; `stage2_common.py`; `answers_summary.py`; `retrieval_summary.py`.
- `scripts/context_judge.py` with `tests/test_context_judge.py`; `scripts/chat_answer_judge.py`
  unchanged.
- Later, committed with its test before the judge's first grade:
  `reports/stage2/tools/judge_export.py` — on the Mac, a base's private references file
  (every registered question: `case_id`, its cluster, and `reference_answers` for a question
  with an answer only), copied to the private folder; on the laptop, part 1's `reading` and
  each plan's committed record, by the rules of «The judge» above.

## Tried before the commit

Not evidence: a smoke stand of `172620f` with these tools copied in
(`/Users/julia/RAG_new_s2smoke_172620f`), 2026-10-19, on a Mac another project's idle process
shared. Its runs changed the forecasts, the path test and the launch command above.

- `stage2_cases.py` for the five keys: 100, 15, 100, 100 and 100 ids, none repeated; a wrong
  questions file refused.
- `tests/test_context_judge.py` and `tests/test_chat_answer_judge.py` on the Mac: 8 passed.
- **Retrieval**, the first two questions of each base and aircargo-gr's first, one
  `live_supervisor.py` run each in mode retrieval: every run complete; every lane 20 and 20,
  pools 32–38, the rerank `ok`, five documents back, three to five sent. The first question
  122.0 s in the first run (models and caches cold), 27.3–49.0 s in the later runs; a later
  question 24.0–44.1 s; the builds 8–21 s. The K curve at K = 20 gave the ranked five on all
  five questions with gold.
- **One aircargo answer**, `aircargo-probation-data`, through the supervisor as a batch of one:
  290.6 s against the forecast's 340 (the first token at 182 s, retrieval 123.5 s, the model's
  load 22.1 s apart), route `auto`, self-score 100, keywords FULL, a Cyrillic answer, three
  labels `[N | source=…]` and marks naming only them, the restore line for `aircargo`; swap
  458 → 1,080 MB. Its retrieval prompt equals the retrieval run's for the same question
  (parity). The API's log also held the tenant `default`'s warnings and one `db.audit` write
  that timed out during retrieval — neither the path.
- **The summaries** on these runs: `without_text` passed every record. They then gained the
  path test (`path_breaks`), `live_retrieval.py` the restore lines in `progress.log`, and the
  caps 360/120 s; rerun on the answer and on one WixQA question through `stage2.sh retrieval`
  (the run's cap 540 s, `Restored 37571 chunks for tenant ext_wixqa`): no break found.
- **After the cold read** (below) the tools changed again — the path test in
  `live_retrieval.py`, the driver's check after each batch and run, whole scores, the K curve
  by set, the summaries' refusals — and ran again on the same stand. The four receipts name
  their chunk archives. `answers_summary.py check` passes the answer and stops (exit 6) on a
  copy with its restore line cut; `retrieval_summary.py check` stops on a copy with one BM25
  lane emptied and the restore line cut. Through `stage2.sh retrieval`, two questions each of
  WixQA and ConditionalQA (the first 96.1 s and 43.5 s); through `stage2.sh answers`, a batch
  of two aircargo answers, the questions file cut to two and restored after: 271.3 s and
  309.9 s, the first token at 161.9 s and 186.5 s, route `auto`, keywords FULL, Cyrillic,
  three and four labels, swap up to 1,454 MB. Every run was checked clean and summarised.
- **The judge's route**, one request each on that answer and on its retrieval context: valid
  at the first attempt, the session clean (no tools, MCP servers, skills, memory, plugins or
  hooks loaded). The answer 77.7 s and $0.145 — four claims, three supported, so `bad` by
  `classify`; the context 35.9 s and $0.094, `full`.

## What the cold read corrected

The draft (2026-10-19, uncommitted) was read cold by a fresh agent on the session's model. It
found, and this text and the tools fix:

1. A path break after batch 1 went unnoticed: the driver stopped only on a failed run, no tool
   judged the restore line or the rerank's status, and a retrieval run logged no restore line.
   The test now runs in `live_retrieval.py`, after every batch and run, and in both
   summaries; part 5's test asserts it.
2. A question with outer spaces, or repeated in a batch, would stop the answer judge for a
   whole base. None of the 300 external questions or aircargo's has either (counted on the
   Mac); `live_retrieval.py` strips the question as the API does, so parity holds anyway.
3. The K curve averaged in the questions it said it left out; now only those where K = 20
   gives the ranked five.
4. Rounded scores made false ties: the pool's scores are kept whole, and a set and an order
   that differ are counted apart.
5. M2 had no rule for the questions without an answer: the references file holds only those
   with one, and the two M2s are computed apart.
6. ConditionalQA's references lack the conditions: the 26 conditional questions are printed
   apart.
7. The judge's committed record had no tool and contradicted the private folder:
   `judge_export.py`, committed before the first grade.
8. On 15 pairs the kappa follows the classes' shares: an agreement rule beside it, a floor of
   12 valid pairs, the interval printed.
9. The external bases' questions come in clusters: cluster counts and cluster-bootstrap
   intervals; the detectable difference between the 80 and the 70 questions.
10. aircargo's M3 had two instruments and no primary: the context judge at «sent».
11. The denominators moved between points: n per point, comparisons on the questions common
    to both.
12. Reruns: an answer that never came is a path break; a batch counts whole; nothing runs after
    a second stop without Julia; a retrieval run reruns whole, `missing` against the
    registration.
13. A retrieval run that did not complete was counted: its summary refuses it.
14. «Read clean» was undefined: defined; the time, the route and the script are reported.
15. Most tools had never run: both modes of `stage2.sh` and both summaries ran on the smoke
    stand (above); a tool's change mid-stage is a new stand, a summary's fix reruns offline.
16. The link to the handover-signal plan: part 1's judge plan is its 1.2, the reading in its
    `plan.json` before the first grade.
17. The judge's cap had no outcome and its re-asks no limit: a pause with Julia; six replies
    at most.
18. The selections were registered after stage 1's first check: «at `e5e135a`, before stage
    2's first request».
19. The part's cap restarts with each invocation: so registered, the part's hours set against
    its forecast.
20. The provenance checks were soft: a missing source file, a receipt without the archive's
    digest and a run of another tenant are refused; retrieval's settings have their digest.
21. `without_text` matches a document's name whole: worded so.
22. The judge's requests send texts to its provider: a request is neither a commit nor a
    publication.
23. The launch command failed on a fresh stand: it makes `runs/` first, with `;` before
    `nohup`.
24. Part 4's «33.8 h» read as its cap: 11.3 h a base, 33.8 h the three.
25. The judge's copies of a retrieval run lacked `launch.json`: added.
26. Closing stage 2 without part 3 needs Julia's word; the amendment's stand passes the same
    check.
27. The half-widths at 20 and 30 questions: added.
28. The K replay is exact for BM25 and approximate for HNSW: said.
