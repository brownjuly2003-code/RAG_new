# Roadmap — RAG_new

Status of every stream. Anything marked **frozen** stays frozen until its
unfreeze condition is met — not "until there is time", and not for
completeness. Order of work: [`PLAN.md`](PLAN.md), the one plan since 2026-10-17; this
file records progress against it (it replaces `archive/docs/plans/plan_06_09_26.md`).

WIP limit: **one measurement on the Mac at a time**; work without the Mac runs beside it
([`PLAN.md`](PLAN.md) §5).

## Active

**Now (2026-10-17): [`PLAN.md`](PLAN.md), the one plan — stage 0 done, stage 1 next at Julia's word.**
Stages: 1 — the production model's 100 aircargo answers on the client's path, judged, with the
handover signals; 2 — the code made ready for foreign corpora (an audit for Russian- and
aircargo-bound spots, each fixed or recorded), then retrieval without generation on the four
corpora (aircargo, ConditionalQA, WixQA, MultiHop-RAG), 300 judged answers on the three
external bases on the current path (Julia's «Вариант B», 2026-10-17) and the graph lane on aircargo; 3 — the handover signal chosen
and wired; 4 — speed and memory on the Mac, the final path, then Julia's SLO; 5 — the external
answers again, only if stage 4 changed the path; 6 — production running as a service; 7 — retrieval
mechanisms, the graph included, on end metrics; 8 — publication, Julia's gate. Each closed
stage adds its line here.

**Thread M — the chat on the production Mac (Julia, 2026-10-14/15): steps 1–4 done; steps 5
and 6 continue as [`PLAN.md`](PLAN.md) stages 1, 3 and 4.**
Production is `deproject-mac` («прод на маке», 2026-10-14). There the web chat answered
nothing under the code's default limits before step 1: every question ended with route
`timeout` after 30 s; on a timeout the client sees an apology badged «Качество: 0» and
«Маршрут: timeout», with no button to an
operator, and no ticket opens — the chat opens none on any route, only `/api/ask` does
([measured](CURRENT_STATE.md#web-chat-on-the-production-mac--measured-2026-10-14)). On
2026-10-15 Julia answered the session's four questions — push the five local commits: yes
(done, `c3f0fff..8850d6a`); time qwen3:1.7b in the live chat: yes; offer the operator on a
timeout: yes; the target answer time: «Пока стоит вообще снять ограничения» — and kept that
session to decisions and documents, with no tests. She said yes to lifting the limits and to
steps 2 and 3, and at 17:15 to a ceiling with the reranker on the CPU — the session's 1,800 s,
raised by her to 3,600 s that evening («давай 3600 с и стоп-кран») — and to giving a `human`
answer in the chat the same operator button; the order is the session's.
Each step is a slice of its own
([why, files and traps](docs/operations/session-handoff-2026-10-15-decisions.md)):

1. **Lift the time limits (rule (a)) — done 2026-10-15, `468224b`.** The request, Ollama and
   stream limits (`REQUEST_TIMEOUT_SEC` 30, `OLLAMA_REQUEST_TIMEOUT_SEC` 60,
   `STREAMING_TIMEOUT_SEC` 120) default to a ceiling of 3,600 s, not to none: a hung model
   call must still end and reach step 2's operator; `RAG_DEVICE` defaults to `cpu`, as the
   2026-10-14 runs measured — on the Mac's 4 GB GPU the reranker fails on memory and the
   answer is silently built on the unreranked order. Proof: the chat's stream on a real
   `Settings()` with no limit in the environment and a fake Ollama silent for 65 s, then
   streaming until 129 s, delivers the whole answer with route `auto`; on `f4818eb` it ended
   at 30 s with route `timeout` and the apology ([evidence row](EVIDENCE_INDEX.md)). The live
   tools' `prod` mode set the old values (`STANDARD` in their supervisors); step 3's tools set
   the new ones.
2. **Offer the operator on a timeout and on `human` (rule (a)) — done 2026-10-15, `056844d`.**
   The apology routed `timeout` and a stream `error` routed `timeout` or `error` show
   «Повторить» and «Передать оператору»; an answer routed `human` shows the same button, not a
   ticket (Julia, 2026-10-15). The button opens the chat's operator dialog and sends
   `/api/escalate` the question with the reason `route=timeout` / `route=human` /
   `route=error`, as `/api/ask` names its tickets. Proof: Chromium on the Mac drives the chat
   against a live server whose stream runs its real path to a fake Ollama — under an 8-s limit
   the test sets and a model silent for 60 s the apology comes in about 10 s with both
   buttons; an answer scored 40 comes routed `human` with the button; on `147db65` no message
   had it; run with `-rs`, no skip ([evidence row](EVIDENCE_INDEX.md)). Python Playwright is in
   `/Users/julia/RAG_new_playwright_site` on the Mac, installed with pip — never brew, never
   the stand's venv (Julia, 2026-10-15). The embeddable widget, done 2026-10-15 (`4977582`, the
   session's call on Julia's «Реши, как оптимальнее»): it calls `/api/ask`, which opens no
   ticket on a timeout; on that route's wall-time limit (HTTP 504) it said «Не удалось
   подключиться к сервису…», which was untrue, and on the graph's own deadline it showed the
   apology with nothing to do. Now both say the answer did not come in time and offer
   «Повторить» and «Передать оператору», and any other failure says the answer did not come;
   the button sends `/api/escalate` the reason `route=timeout` / `route=error` and fetches a
   new token once if the old one expired during the wait. Red on `30e97bd`, green with `-rs`,
   no skip ([evidence row](EVIDENCE_INDEX.md)). Its subtitle «Обычно отвечаем в течение пары
   секунд» stays untrue on this Mac until Julia names an SLO.
3. **Thinking off on the chat path, then qwen3:1.7b in the live chat (rule (a), then (c)) —
   done.**
   Thinking off is done (2026-10-15, `c2739af`): every model call of the chat — the answer, the
   self-evaluation, the suggested questions, the tool calls and the raw stream fallback —
   sends `think: false`; on `8464732` they sent `think: null`, and qwen3:1.7b thought for
   130–155 tokens before a one-sentence answer. Ollama 0.33.2 answers `think: false` from
   qwen2.5:7b, which cannot think, as it does without it and refuses only `think: true`
   ([evidence row](EVIDENCE_INDEX.md)). The live chat ran on 2026-10-16, 00:26–01:28 UTC, at
   the code defaults and code `9e1fc9e`, every question and its forecast named before the
   first launch (`reports/chat-live-qwen3/9e1fc9e/tools/series_plan.json`): one question took
   185 s to the whole answer (first token 142 s); five, median 211 s (177–301 s); Julia's stop
   rule ended the thirty at question 9, with no first token at 360 s, after eight answers of
   median 200 s (139–352 s). All 14 answers routed `auto`, and the rerank succeeded on the
   CPU in each. The time goes to the rerank — median 120 s (61–271 s), the same questions
   slowest in both runs — while the model reads its prompt in about 28 s, writes 9 tokens/s
   and evaluates the answer in 29 s. The stop was memory: over the thirty, swap grew from
   764 MB to 4,117 MB, the API and the model were paged out, and question 9's vector search
   alone took 147 s. Two findings for steps 4 and 5: the 8-GB Mac does not hold the API and a
   model through a long series without swapping; the BM25 warning every live run logged is the
   startup tenant `default`'s — the questions' tenant restores BM25 at the first question and
   retrieves hybrid (corrected 2026-10-16; [evidence row](EVIDENCE_INDEX.md)).
4. **Julia's production model — decided 2026-10-16: Qwen3-4B-Instruct-2507** (Ollama tag
   `qwen3:4b-instruct-2507-q4_K_M`, digest `0edcdef34593…`), the session's recommendation, to
   which she answered «Согласна с тобой» (02:11 UTC). Why: the judge on all 100 cases gave it
   67 good answers against 50 for qwen3:1.7b, 56 for qwen2.5:7b and 66 for qwen3:8b; in the
   live chat of 2026-10-14 (code `33d4b42`, 1,800-s limits, the rerank on the CPU) one
   question took 343 s to the whole answer and five a median 297 s, all `auto` — slower than
   qwen3:1.7b's ~200 s, which the judge puts behind it (after correcting for six pairs the 4B
   is apart from qwen3:1.7b only, [evidence row](EVIDENCE_INDEX.md)). No SLO is named: research acceptance on
   the Mac is still not product acceptance (phase Q below), and no quality default flips.
   **The code default since 2026-10-16, `7a99c45` (rule (a)):** `config/settings.py`,
   `config/providers.yml` (listed, the Ollama defaults, `local-first`, the GraceKelly
   fallback), `.env.example`, the deployment files and the quickstarts name the 4B; the chat's
   stream and `/api/ask`, on a clean `Settings()`, ask a fake Ollama for it and no other — red
   on `26fcb4a`, green after ([evidence row](EVIDENCE_INDEX.md)). **How often the chat would
   hand its answers to a person (rule (c)):** the chat's rule — the model's own score, `auto`
   at 80 — replayed on the 4B's 100 judged answers sends 2 of 100 to `human` (Wilson
   0.6–7.0 %), both declines; 10 of the judge's 12 bad answers go `auto`: the model scores 89
   of its answers 100. An estimate of the rule on the test set, not a chat run, and not the
   widget's rule ([evidence row](EVIDENCE_INDEX.md)). Which signal should send an answer to a
   person is measured first — step 5. **The first live series (2026-10-16, 20:12–21:12 UTC, stand
   `7a99c45`) is not the 4B's:** the stand's deployment environment pins
   `OLLAMA_MODEL_NAME=qwen2.5:7b`, and the stream's suggested questions, which read that
   setting, loaded the 7B (about 4.7 GB) beside the 4B after every answer; its thirty stopped
   at question 2 on a 503 of the session store's 60-s cooldown after a 2-s database timeout
   under swap — met through the runner's own session ids, which a web-chat visitor's first
   question does not send. Fixed in `19beeb1` (rule (a)): the suggestions follow the answer's
   model — with the 7B pinned, the stream's three calls ask the 4B, red on `da134d4`. Then
   the live chat 1 → 5 → 30 on `19beeb1` under the stop rule, plan and forecasts (340 s,
   then 400 s) in `cf25593` (rule (c), 2026-10-16 21:27 – 10-17 01:48 UTC): the whole answer
   median about 300 s — one question 281 s, five median 322 s, the thirty rerun (its first
   stopped at question 16 on the test client's expired token, `25ed888`) median 320 s
   (196–476 s); 2 of 47 past the 400-s forecast, none near the stop. All 51 answers `auto`,
   49 scored 100 by the model: the chat offered no handover. The wall is memory, not time:
   swap grew 600–700 MB a question to 12.3 GB, and Ollama's runner alone grows about 312 MB
   a request ([evidence row](EVIDENCE_INDEX.md)).
   Her answer is the explicit decision the stop-list asks of a model swap, for this one model;
   the no-flip rule is about phase Q's retrieval and generation defaults, not this one.
5. **Which answers go to a person — measured first (Julia, 2026-10-17: «Давай сначала
   замерим»).** Two signals are configured — the chat's self-score at 80, the widget's
   self-score, relevance and claim check — and neither was ever checked against answers
   known to be bad; the chat's misses 10 of the judge's 12. [The plan](docs/specs/handover-signal.md):
   100 answers in the chat's own form (the 30 of the rerun, 70 new on `19beeb1`), judged, and
   seven signals computed on them through the repository's code; since 2026-10-17 the 70
   come first, with no separate pilot, then the judge and the signals on all 100
   (rule (c)); WixQA's open part only if a signal lands in between. It withdraws the session's 2026-10-16 proposal to replay the widget's
   rule on the screening's answers, which cite no `[N]`.
6. **Then the speed levers, one at a time, each measured:** fewer rerank candidates first
   (Julia agreed 2026-10-16; `RAG_RETRIEVAL_TOP_K`, 20 candidates reranked to 5 today; time
   and quality, rule (c)) — not another reranker, the stop-list — then a shorter prompt, and
   the self-evaluation after the answer is shown, which changes what the client sees and is
   hers to decide.

The quality thread's campaign (phase Q) is stopped by [`PLAN.md`](PLAN.md) §7, which lists
what of it is reused and where.

**Phase A is done.** A.1 + A.5 landed on 2026-08-25 and are the first
slice this repository has had under rule (a): a shipment-status question
through the real `/api/ask` leaves an evidence bundle in the trace, read back
out of the trace store. A.4 closed with it, and A.1b put the same evidence
into the resolution tables where it can be queried.

**A.2 and A.3 landed the same day.** A.2 is the second slice under rule (a): `/api/ask` takes a durable session turn behind
`SESSION_DURABLE_TURNS`, so a session answers one request at a time and its
message pair is written by the transaction that ends the turn; the
process-wide database cooldown became per-tenant and bounded with it. A.3 is
the third: `GET /api/admin/traces/{id}/evidence` and the Evidence tab beside
Raw JSON, where a reviewer reads the contract, the policy decision, each claim
next to the evidence under it with its age, and the replay receipt. Building
it found that the shipment-id extractor could not match any id the fixture TMS
holds, so every bundle behind `/api/ask` had been empty; fixed with an
end-to-end test that sees a completed journey.

Both of FIN-01's unwired halves — `resolution/` and `services/session.py` —
now have production callers.

**Phase A then gained an admission gate and a measured number** (2026-08-27).
The shipment-status journey now decides whether a request is its own before
it asks for an id (`6651964`), that decision is scored against
`label.journey` on the 100 labelled cases (`36d4269`), and the vocabulary
has a Russian half built as a translation of the English one (`bd82297`).
Over the 100 agent-authored-over-real-documents cases, still
`agent_labelled` and 0 approved, admission recall is **0.0000**
([capsule](docs/evidence/a6-journey-admission-and-clarification.md)).
The shadow remains read-only. T-03 now lets `/api/ask` project only its
`CLARIFICATION_REQUIRED` terminal behind the independent, default-off
`RESOLUTION_CLARIFICATION_JOURNEYS` allowlist; both allowlists must name the
journey. Declines, other terminals and failures keep the legacy response.
T-04 makes the operator-visible side explicit: Evidence now distinguishes a
disabled shadow, a declined journey and producer failure while a decline still
calls neither source nor policy and never enters resolution persistence.

**Phase B has started, and B.1 changed the shape of the rest of it.** All 100
air-cargo cases carry a journey, an expected outcome and a root cause
([capsule](docs/evidence/b1-aircargo-journey-labels.md)). The corpus cannot
produce a verified-resolution number at all, now for **three independent
reasons** rather than one: no case names a shipment; the corpus is Russian
and the gate's vocabulary was English; and with the language removed, over
the 100 agent-authored-over-real-documents cases, still `agent_labelled`
and 0 approved, admission recall is still 0.0000 — the corpus contains no
case this journey should admit.
**B.2, B.3 and B.5 are blocked on data, not on work** — the brief's own
NO-GO check (§15) is what fired. On 2026-09-25 Julia approved all five label
batches (T-54, `73b13b9`), so the labels are `real_labelled`; the cases stay
agent-authored over real documents, so B.2, B.3 and B.5 stay blocked on data.

**Phase C.1 now has two published generator benchmarks.** Qwen 2.5 7B
completed 3 × 100 cases on the Mac with zero failures at LLM faithfulness
0.8295, NLI faithfulness 0.8919 and context precision 0.5067. Qwen3 8B then
completed the same contract at 0.8986 / 0.9908 / 0.506657, also with zero
failures; its report, sidecar and [capsule](docs/evidence/c1b-qwen3-generator-benchmark.md)
were published on 2026-09-11. Both reports pin the corpus, cached contexts,
source SHA, model digest and full config. C.4 is [closed as NO-SHIP](docs/evidence/c4-generator-model-decision.md):
Qwen3 misses 0.90, host peak RAM is unknown, and the default stays Qwen2.5.
This is a decision on existing evidence, not a new measurement.

**GR-0.2 now has a separate, provenance-pinned evaluation bucket** (2026-09-11):
15 agent-written questions over 13 real corpus documents, split into 10
`multi_hop` and 5 `aggregation` cases. The supplemental dataset digest is
`0949d756…`; its sidecar remains `agent_labelled` and unapproved. The published
phase-C dataset stays byte-identical at `3737d694…`. This is preparation, not a
new metric; retrieval still needs a new candidate pool.

**GR-0.4 structured query classification is implemented locally** (2026-09-11).
Schema-capable providers now fill `complexity`, `question_class`, bounded
`entities`, `needs_multi_hop` and `reason_code`; initial and legacy-provider
paths stay safe. Default `simple → vector`, other complexity → hybrid routing
is unchanged, and graph still requires explicit graph configuration. This is
preparation for GR-2 entity matching, not a measured slice. The GR-1 builder,
pipeline wiring (`782f03f`) and retrieval lane (`6e23630`) are now committed.
GR-1b's recovered Mac pool is now measured: precision 0.5475, recall 0.9200,
FULL/PART/MISS 88/8/4. It misses 0.63; category prefilter applied to zero cases.
The [capsule](docs/evidence/gr1b-structure-graph.md) links exact archived input,
reproduction tests and source-attribution limits. The owner's 2026-09-12
[Astra/Fable review](docs/specs/precision-improvement-review.md) puts same-pool
top-k controls and bounded diagnosis before GR-4/GR-2/GR-3. Both are measured:
plain top-k fails coverage; [label-dependent oracle](docs/evidence/gr1b-safe-subset-oracle.md)
reaches 0.6780 / 0.9250 with G1 fallback. The [query-only control](docs/evidence/gr1b-query-control.md) fails coverage
(0.6268 / 0.7250, 67/11/22); three infeasible cases have G1 hits absent from
uncapped top-five. [Stage replay](docs/evidence/gr1b-stage-replay.md) recovers metadata and matches
100/100 outputs; expansion alone gives 0.5125 / 0.9300 without G1 fact losses,
still NO-SHIP. [Seed reservation](docs/evidence/gr1b-seed-expansion.md) prevents displaced seed
text but yields no metric gain (0.5472 / 0.9200 with coherence). This bounded
experiment is closed. [GR-4 structural wiring](docs/evidence/gr4-structural-product-wiring.md) now passes HTTP and
browser checks. GR-2 is measured — 0.5487 / 0.9250, NO-SHIP at 0.63, lane on 6 of 100
cases ([capsule](docs/evidence/gr2-entity-graph-lane.md)). GR-3 is measured (2026-09-18/19):
NO-SHIP-to-default, `RAG_GRAPH_RETRIEVAL` default stays `off`
([capsule](docs/evidence/gr3-graph-lane-ab.md)). Do not repeat this pool or its embeddings.
C.3 [HTTP answers](docs/evidence/c3-contract-shaped-response.md) and
[manual copilot drafts](docs/evidence/c3-copilot-contract-draft.md) now share
the validated skeleton behind default-off flags; 555 Mac tests and both strict
type gates pass. Automatic/error/email drafts remain legacy. D.1–D.3 are
now measured in [ADR 0007](docs/adr/0007-pgvector-spike.md): the original
pre-reranker SQL trails Chroma/BM25, while the index-friendly HNSW arm reaches
recall@20 0.965217 and warm p95 3.45–3.64 ms over 115 cases. Final offline
rerank precision is 0.460985 vs 0.472891 for PostgreSQL and Chroma/BM25.
The 0.20 ANN outlier is measured and closed as a bounded replay
([capsule](docs/evidence/d2-pgvector-ann.md)): on the retained original index
ef_search=100 reproduces the canonical 4/20 ranking while ef_search 40 and
200 are both 20/20 — non-monotonic, not ordinary insufficient ef_search —
and a fresh rebuild is 20/20 across the measured grid; the behaviour is
localized to the retained index state, with no pgvector/HNSW root cause
claimed. D.4 was measured on 2026-09-25
([capsule](docs/evidence/d4-pgvector-graph-evidence.md)), published at `25c21e4`:
on a fresh migrated scratch database, 10300 nodes and 17327 edges reload
through `StructuralGraphRepository` with an identical persisted contract;
5589 chunk nodes join 5589 synthetic evidence rows by a diagnostic semantic
join, not a schema foreign key; RLS is forced on four tables, with 0
cross-tenant rows. This was one run on one corpus and one host;
`RAG_GRAPH_RETRIEVAL` remains `off` and the retrieval backend is unchanged.
D.5 was measured on 2026-09-25
([capsule](docs/evidence/d5-pgvector-cold-start.md)), published at `e0c1b3c`:
over seven new-process trials per arm, median time to first fused result
was 85.7 ms for PostgreSQL and 1494.7 ms for Chroma/BM25; client
resident set after the workload was 68,644,864 against 310,738,944
bytes, with the PostgreSQL backend's 98,246,656 bytes recorded apart.
PostgreSQL answered identically in every trial. Chroma answers changed
in 13 of 115 cases between processes, and each new Chroma process
re-inserted its unpersisted write-ahead-log tail. One run on one host
used precomputed query vectors without model load; file cache and the
PostgreSQL server were not controlled. D.5 measured no retrieval
quality. Phase D is measured, and [ADR 0007](docs/adr/0007-pgvector-spike.md)
is accepted: retain the current retrieval backend. No runtime default
changed; `RAG_GRAPH_RETRIEVAL` stays `off`.
The Chroma restart measurement followed on 2026-09-25
([capsule](docs/evidence/chroma-restart-stability.md), published at `49db561`):
on production's own write path, 128 of 5589 records stayed in the
write-ahead log, and one of seven restarted processes changed the
candidate set of one of 115 cases. No runtime default changed; the
fix is a separate slice with an end-to-end test. The fix landed at
`534612e`: production's staged build persists the vector index at
the end of every add call, proven by an end-to-end restart test.
The rerun at that commit
([capsule](docs/evidence/chroma-restart-stability-after-fix.md),
published at `4e4273d`) left no record in the write-ahead log,
and all seven restarted processes answered all 115 cases as the
build did.

P1 was measured 2026-09-24 ([capsule](docs/evidence/p1-adaptive-k.md)): 5-fold
held-out H precision 0.5372 vs valid `top_k_5` control 0.5067, recall 0.8900 vs
0.9050, FULL/PART/MISS 86/6/8 vs 87/7/6. **NO_SHIP**: the 0.63 precision gate,
H-relative coverage constraints and unreachable review floor are unmet. The
label-using, nondeployable prefix oracle bounds any cut that keeps every fact at
0.6505. This is H-relative exploratory evidence on 100 agent-authored
`agent_labelled` cases (0 approved) in the phase-C harness without parent-window
expansion. P1 is an offline evaluator; product behaviour is unchanged. P1b was
measured the same day ([capsule](docs/evidence/p1b-expanded-cut.md)), also an
H-relative exploratory verdict on 100 agent-authored `agent_labelled` cases
(0 approved). On H, `rel_0.2+exp` precision 0.5975 vs expanded control 0.5768,
delta +0.0207, CI95 [0.0104, 0.0327]; one FULL→MISS fact loss
(`aircargo-customs-broker-escalation`); held-out `p1_cv+exp` precision 0.6062.
**NO_SHIP**: no measured arm reaches the 0.63 gate. P1b is an offline evaluator;
product behaviour is unchanged. P2 was pre-registered 2026-09-25
([plan](docs/specs/p2-blinded-judge-plan.md)) and is now
[measured](docs/evidence/p2-blinded-relevance-judgment.md): GLM 5.3 and Sonnet 5
each graded 115/115 cases. On H, α 0.8566 and per-case τ_b 0.1561 (CI95
[0.0197, 0.2880]) give `RULER_DOES_NOT_TRACK` under the registered rule.
No human grades will be collected (plan decision D11, 2026-10-03); Mistral returned `zero_limit`. No ruler gate
or retrieval default changed. Alternative rerankers remain on the stop-list
below until Julia decides otherwise.

**Quality thread adopted 2026-09-30 by delegation and ratified the same night by delegation** (plan step 0.3 done; the owner may revisit any decision before the first track-3 experiment):
[`docs/specs/plan_03_10_26.md`](docs/specs/plan_03_10_26.md) — the 2026-10-03 revision of
[`plan_final_30_09_26.md`](docs/specs/plan_final_30_09_26.md), made on the owner's instruction; decisions D1–D10
stand except D2, D3 and D10, changed the same day by the owner's D11 («люди участвовать в процессе не будут»: no person grades, approves or checks — models from other vendors do, and the plan claims no human validation); the adoption and ratification are those of the 2026-09-30 text, the revision itself is unaudited — built on the
[2026-09-30 audit](docs/audits/audit_asta_30_09_26.md). It runs after phase E as one
thread: measurement (the P2 judge consensus checked against model references, a pre-registered
[development ruler](docs/specs/semantic-precision-metrics.md), a diagnostic dev set),
route observability, then at most two mechanisms chosen by the evidence-loss map on the Mac (plan D8; H1 in the graph lane by default, H5 as its candidate budget, not a mechanism; the graph branch itself stands under the [enablement policy](docs/specs/graph-enablement-policy.md) registered 2026-10-05, before any graph experiment — selection rule, the branch's own gate, stages shadow → tenant → default with rollback; preparation, none of it is in the code),
then a single locked-holdout acceptance. Its first executor slice (2.1/2.2: a requested
graph lane that falls back becomes visible in the trace and Evidence with a bounded
reason; the retrieval path carries candidates per source, coherence drops, rerank
scores, stage timings, graph digest and entity-graph status) is implemented (T-59,
2026-10-01; rule (a) by `tests/test_ask_contract_route.py`); no default changes.
The 2026-10-03 revision adds one frozen candidate and no mechanism: BM25 token
normalisation is H11 (gap G36), outside the first campaign with H6–H10 and with a
return condition in plan §4; the exploratory lexical-lane study behind it is
not evidence and stays outside the repository (owner, 2026-10-03).

Both inherited CI failures ([ADR 0008](docs/adr/0008-inherited-ci-red-disposition.md))
are closed. On `6cc810d` (T-17, pushed) both workflows that run on
push ended `success`: `CI` run 34461559172 with 11 of 11 jobs, and `Deploy docs
site (Astro Starlight) to Pages` run 34461559218. That green is the `build` job,
which carries `npm audit --audit-level=high`; the `deploy` job was skipped by
`if: github.event.repository.visibility == 'public'` (`docs-site.yml:89`)
because the repository is private, so nothing was published — the deploy half
is inert by design until phase E. After its last success on 2026-08-25 (run
32880095380) every push that ran docs-site failed through 2026-09-09 (four runs,
last 34393111514 on `95d408e`) at the npm audit step: ten GHSA advisories across
five npm packages landed upstream against pins that were correct when written.
T-18 raised the floors; `0aacb7b` (run 34408840657) was the first success and
`6cc810d` the second, so the fix is confirmed rather than assumed. The `paths`
filter in `docs-site.yml:6-17` starts no run for a push touching none of its
paths, so `d026804` (T-19, only `CURRENT_STATE.md` and `ROADMAP.md`) got `CI`
run 34449244275 alone. The other three workflows (`live-provider-gate`,
`live-quality-metrics-gate`, `weekly-report`) run on schedule or dispatch only,
so this is two of five. The chromadb CVE ignores were reviewed on
2026-09-24 (no fixed release); the next review is **2026-10-24**.

Observed 2026-10-03: GitHub Actions execute jobs again, and CI was red from
`70d272c` (run 37093493571) to `df1bf47` (run 37137697604; Pages run 37137697647):
`test-unit` on 3.11 and 3.13, `pre-commit`, `security`, and the Pages step
`Audit npm dependencies`. Four tasks fixed it. T-71 (`22bb68a`): a request's
context stayed on a pooled worker thread and reached the next request — a
product defect behind the flaky 3.13 failures. T-72 (`f197481`): full git
history for the artifact tests, a skip for the proof whose corpus is
gitignored, and whitespace hooks that leave byte-pinned reports alone. T-73
(`ebc343b`): six Python floors and both locks. T-74 (`45a417a`): two npm floors
and one dated exception for an advisory with no fixed release. CI is green on
`45a417a` (run 37157492007, 11 of 11 jobs); the Pages build passed on the same
commit (run 37157492017) and its deploy was skipped — the repository is
private, nothing is published. The Pages audit step is now `npm run audit:deps`
([ADR 0009](docs/adr/0009-npm-advisory-without-fix.md)) instead of
`npm audit --audit-level=high`. The exception (GHSA-ch52-4w7c-c8xp in
`http-cache-semantics`, high) expires 2026-11-03: from 2026-11-04 the Pages
build and the unit suite are red until it is renewed or removed. Its review is
**2026-10-24**, with the chromadb ignores. Not checked: `sentence-transformers`
from the lock with real models — the Mac environment is not built from the lock.

| Phase | What | Acceptance |
|---|---|---|
| **0** | Freeze, publish, truth about gates | root ≤ 8 md (≤ 9 since, `tests/test_docs_hygiene.py`), remote exists, CI status known, pricing/README/eval-gate claims true |
| **A** | Wire the shipment-status shadow into `/api/ask` | rule (a): E2E test on real endpoint behaviour + evidence bundle + replay receipt |
| **B** | 100 real labelled air-cargo cases | rule (b): corpus v1.0 at `evidence_class: real_labelled`, ≥40 double-annotated calibration routes (taken over 2026-10-17 by thread M step 5, [the handover plan](docs/specs/handover-signal.md), judged by the session's model under D11). B.1 done (`real_labelled` since the 2026-09-25 approval); B.2/B.3/B.5 blocked on data, now for three reasons rather than one |
| **C** | Quality leverage: Qwen3 benchmark, NLI second judge, claim-level compilation | rule (c): faithfulness ≥ 0.90 and precision ≥ 0.63 over 3 runs with a CI, **or** a NO-SHIP report with a cause |
| **GR** | Graph retrieval: structure graph (0 LLM calls) → entity graph → A/B → wired behind flags. Unfrozen 2026-09-06; called required by the 2026-09-10 plan to move the 0.63 precision gate, a ruler P2 found not to track meaning — re-decided on end metrics in [`PLAN.md`](PLAN.md) stages 2 and 7; GR-1a's cheap arm gave 0.5216, no better than plain top-4's 0.5214 ([capsule](docs/evidence/gr1a-section-coherence.md)) | rule (c): published context precision / multi-hop coverage with provenance per step; rule (a): graph lane behind `RAG_GRAPH_RETRIEVAL` with an E2E test; GR-3 measured 2026-09-18/19 — NO-SHIP-to-default, default stays `off` ([capsule](docs/evidence/gr3-graph-lane-ab.md)) |
| **D** | pgvector spike, ADR 0007 — D.1–D.5 measured; accepted 2026-09-25: retain the current retrieval backend (a vector-DB swap stays on the stop-list) | a table of numbers in the ADR; no migration without it |
| **E** | Public artefact: README-first, 3-minute demo, `resolution-contracts` sub-package; Q4 confirmed 2026-09-30: publish current `RAG_new` as **RAG assistant**, Pages base `/RAG_new/`; E.4 site prepared at `236f7c1`, pushed and unpublished; CI is green on `45a417a` (2026-10-03, run 37157492007, 11 of 11 jobs) and the Pages build passed on it (run 37157492017; deploy skipped, the repository is private and nothing is published), so the owner's order of 2026-10-03 — a green CI on HEAD before the quality thread's 2.5 chain — is met and that chain ran (2.5 closed 2026-10-05); making the repository public and deploying Pages are the owner's gate and do not hold that thread (plan D11) | E.5: Mac full suite and final [history scan](docs/evidence/e5-secret-scan.md); E.4: push, green CI, public repo, Pages deploy, links from the old repo and proof-pack; numbers in README |
| **Q** | **Campaign stopped 2026-10-17 by [`PLAN.md`](PLAN.md) §7.** Quality thread after E ([plan](docs/specs/plan_03_10_26.md), adopted and ratified by delegation 2026-09-30, revised 2026-10-03): ruler cross-checked by model references (no human grades, D11) → observable route → ≤ 2 mechanisms chosen by the evidence-loss map (D8; default H1 in the graph lane, H5 as its budget) → locked-holdout acceptance. 2.1/2.2 implemented 2026-10-01 (T-59, rule (a)); 1.1 done 2026-10-04 (T-57) and 1.3b done 2026-10-04 (T-78: [30 pilot drafts verified by one model](docs/evidence/devset-pilot-label-verification.md), `single_model_verified`, preparation); 1.3c done 2026-10-06 ([variance pilot](docs/evidence/variance-pilot-gold-metrics.md), rule (c), no verdict: development 60 cases in 37 clusters, holdout 64 in 18; the registered MDE stays 0.17–0.30 — the corpus has no more independent families — so the campaign checks effects of that size and no smaller, and a neutral mechanism is expected to end `INCONCLUSIVE`; whether the grading filter, in part a draw, is changed before the campaign is undecided); since D12 (2026-10-04) one model, the session's Opus 5.5, does every job and check, and no other vendor's model is called | rule (c) per experiment with the [development ruler](docs/specs/semantic-precision-metrics.md): +0.05 in the mechanism's registered primary metric (sent-precision for selection, all-evidence coverage for coverage mechanisms) with CI95 lower bound > 0, non-inferiority −0.02 on the rest, no critical-fact loss on H/Hm, p95 delta ≤ 200 ms at equal budget; the lexical 0.63 gate stays on its own ruler; research acceptance on the Mac is not product acceptance (deployment target + SLO, D5); no default flip before both — the target is named (`deproject-mac`, 2026-10-14), the SLO is not: on 2026-10-15 Julia decided to lift the time limits for now instead |
| **M** | The chat on the production Mac (Julia, 2026-10-14/15), steps 1–4 done: lift the time limits (done 2026-10-15, `468224b`: a 3,600-s ceiling, the reranker on the CPU), offer the operator on a timeout and on a `human` answer (done 2026-10-15, `056844d`), turn thinking off on the chat path (done 2026-10-15, `c2739af`) and time qwen3:1.7b in the live chat (done 2026-10-16: the whole answer 139–352 s, all `auto`, most of it the rerank on the CPU; the thirty stopped at question 9 as the Mac swapped); her production model is Qwen3-4B-Instruct-2507 (2026-10-16), no SLO named, the code default since `7a99c45` and timed live (`19beeb1`); next [`PLAN.md`](PLAN.md) stages 1, 3 and 4 | rule (a) for each product change, with an E2E test; rule (c) for each live run — code SHA, index, model digest and the configuration actually served, its time and routes |

Heavy runs (models, full suite, Docker) go to the Mac — never the Windows
laptop. Do not install or launch WSL, Docker or VMs on Windows (owner direction,
2026-09-12).

## Frozen

| Stream | Why frozen | Unfreeze condition |
|---|---|---|
| Trust Foundation steps 5–10 | Release machinery on synthetic fixtures; the missing input is real data, not more layers | Phase B produces 100 real labelled cases — literally met 2026-09-25; [`PLAN.md`](PLAN.md) §9 proposes a new condition, Julia's to decide |
| G9+ | Same — G1–G8 already exceed what 17 synthetic scenarios can support | Phase C publishes real numbers — literally met 2026-09-11; the same proposal |
| REL-03D (per-turn response replay) | Needed for a durable-HTTP story that has no consumer | A design partner asks for it |
| Durable HTTP semantics (`Idempotency-Key`, `ETag`/`If-Match`, 428/412/409/503), 2-replica floor | Enterprise DoD without an enterprise | A design partner appears |
| SSE as a projection of persisted events; removing the direct-stream path | Full FIN-04 close is a rewrite; the shadow path in phase A does not need it | Conditional track |
| Service accounts, forced RLS on legacy `sessions`/`messages`, JWT `iss/aud/iat/jti` + rotation | Full FIN-12; only the cheap Origin fix was in scope for phase 0 | Conditional track |
| Helm production hardening (encrypted backup fail-closed, restore drill, NetworkPolicy, PDB, digest pin, SBOM/SLSA) | FIN-15; no deployment target | A real deployment |
| MCP connectors, vector-DB swap, model swap, microservices/Kafka/OPA, new channels, new dashboards | Stop-list — none is on the critical path to a wired, measured, published system | Explicit decision by Julia |
| Framework-grade GraphRAG (LightRAG, MS GraphRAG, community summaries, Neo4j) | Still frozen. **GraphRAG as such was unfrozen on 2026-09-06 by Julia's decision** and scoped as stream GR — an in-repo structure + entity graph used to narrow and route retrieval ([`plan_06_09_26.md`](archive/docs/plans/plan_06_09_26.md) §4–5). The reason is measured: the phase-C precision gate (0.5067 → ≥ 0.63) is computed over cached contexts and can only be moved by the retriever | ADR 0001 scale trigger (> 50 000 chunks per tenant) or a measured GR-3 failure on the `global` class — neither can fire today (largest base 37,571 chunks; 0 `global` cases); [`PLAN.md`](PLAN.md) §9 proposes one |
| God-module refactor (FIN-16) | Large refactor before convergence loses more than it gains | After phases A–C converge — C never converged; [`PLAN.md`](PLAN.md) §9 proposes after stage 6 |

## Conditional track

Everything in the "frozen / conditional track" rows above becomes live **only**
on an external trigger: a design partner, or a real deployment. Not on an
agent's judgement that the system would be more complete with it. Whether
production on `deproject-mac` (Julia, 2026-10-14) is such a deployment is hers
to say; until she does, nothing here unfreezes on it.

## How this file is used

An agent that wants to start work on a frozen stream has misread the state.
The answer is in [`CURRENT_STATE.md`](CURRENT_STATE.md) — take the next
action there instead.
