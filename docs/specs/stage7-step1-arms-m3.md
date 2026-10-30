# Stage 7, step 1: the retrieval arms at M3 on stage 2's lists, without an answer

Status 2026-10-30: **registered before the run**, with its tool, its test and S's fix in one
commit, its [cold read](../operations/audit_opus55_30_10_26_stage7_gate.md)'s fifteen findings
applied ([Records](#records)). [`PLAN.md`](../../PLAN.md) stage 7, step 1:
«Поиск без генерации: М3 для каждой руки на ≈ 400 вопросах»; her word of 2026-10-28: stage 7
keeps both arms, the graph and P1b, and the entity graph's extraction cost is measured first.
No model call, no new retrieval.

Rewritten 2026-10-30 to PLAN's gate, after the [audit](../operations/audit_astra_30_10_26.md)'s
F5. The draft of 2026-10-29 opened answers on no detected loss and broke a tie by the prompts
an arm changes: with aircargo's M3 at its ceiling that opened answers almost always, and the
answers' paired reading (random seed, MDE 0.17–0.30) would most likely have read «not detected»
after hours of the Mac and the judge. Both rules are gone, from the tool and its test too. The
control is the path stage 4 accepts: K 20, a 4,096 window and PyTorch's fives today. If the
stage-4 package changes any of them — INT8 of the reranker keeps the gold but changes the five
on 307 of the 400 —, H changes, and the replay runs again, in minutes, after a registered
amendment: the spec and the tool fix K at 20 and the input limit at 2,636, and the tool stops
unless the checkout's `retrieval_top_k`, `ollama_context_window` and `reranker_runtime` are 20,
4,096 and `torch`, writing the three into its record. An amendment for INT8 brings INT8's
scores for all 415 questions: item 5a's comparison scored stage 2's 400, and aircargo-gr's 15
are scored anew. A replay after an amendment runs at another HEAD, which its judge runs'
`launch.json` name, so it takes a new PRIVATE; the old plan stays with the old record.

## Why

The retrieval code is stage 2's since stand `5e308fe` and the cross-encoder scores each pair on
its own, so the arms replay on stage 2's saved lists with the product's code, as the
[no-reranker point](no-rerank-point.md) and the [K curve](k-curve-expanded.md) did: minutes of
the Mac, not PLAN's ≈ 3.5 h an arm. Only the fit to the window is redone, under the answer
prompt V4 of stand `4f48fed`: its template moves the tail of the fit.

**The gate of step 2: PLAN's.** Answers open «только для лучшей руки и только если М3 выросла
больше MDE», and PLAN's MDE is the effect the sample can detect (§4.4); step 4 reads aircargo,
ConditionalQA and WixQA «вместе». So an arm goes on only on an M3 gain at ConditionalQA and
WixQA pooled that is detected and larger than the MDE, and no detected loss at any stop
reading. P keeps a prefix of H's five and S a subset widened inside sections, so neither adds
a candidate H's five lack, only the text its expansion and the window then let through.
aircargo's M3 is at its ceiling — stage 2's judge found the answer in all but one of 115
contexts, in full in 108 — so aircargo stops an arm and qualifies none; its context judge is
planned only for an arm that qualifies on the external bases. With no arm qualifying, steps 2
and 3 do not run and stage 7 closes with «H stays»: a negative result is a decision too.

## The arms

- **H** — `HybridRetriever.get_relevant_documents_with_path`: stage 2's path, today's default.
- **S** — `get_graph_documents_with_path` over the structural graph of the base's chunks, built
  and projected as `vectordb.manager.get_retriever` does with graph retrieval on and no entity
  database: H's pool and five, section coherence (a lone section at ≤ 0.25 of the strongest
  drops), then the section expansion. No categories and `single_hop`: the lane's defaults.
- **S's fix**, product code, in this step. `_expand_graph_sections` kept every sibling's header
  line and both copies of each seam's overlap, put the seed's header mid-text, and stepped over
  a chunk already in the context to join the next one. Now each side grows while the next chunk
  of the document is in the same section, not in the context and within the budget; the run is
  joined as the parent expansion joins it (`vectordb.parent_join`: one header, each seam once).
  The graph lane is off by default; H's path does not change. Pinned in
  `tests/test_graph_retriever.py`. GR-1b's published replays keep the old rule through
  `scripts.gr1b_stage_replay.legacy_expand_graph_sections`, a copy of it, which
  `scripts/gr1b_seed_expansion.py` and `tests/test_gr1b_stage_replay.py` use too;
  `scripts/ab_remote_contextual.py` calls the product's function and expands by the new rule.
- **P** — P1b, rel 0.2: of H's five the first `scripts.p1_adaptive_k.kept_count("rel", 0.2)` by
  their cross-encoder scores, then `HybridRetriever._expand_parents`; five kept is H.
- E stops: its probe's gate G2, the extraction cost, failed at the first look on 2026-10-29
  ([record](../evidence/stage7-entity-probe-record.md)).

K stays 20, the five stay five, the input budget stays V4's: a 4,096 window, 2,636 tokens in.

## Inputs, frozen

- Stage 2's runs `p2-wixqa`, `p2-conditionalqa`, `p2-multihoprag`, `p2-aircargo` and
  `p2-aircargo-gr` of `5e308fe48cca0955c3007057a574a425f71e2a6a`, on the Mac: a retrieval
  record a question (`lanes`, `pool`, `ranked`, `expanded`, `sent`, `prompt`, `path`),
  `launch.json`, `effective_settings.json`; 415 questions, with gold 100 WixQA, 80
  ConditionalQA, 70 MultiHop-RAG.
- The chunk archives with their index receipts, by SHA-256: WixQA
  `2cc24c6f56a394ff189366f70b6ed11b919ba8f545fa592e019c9b193814ba5a`, ConditionalQA
  `e25960d5e4263a0d7f7ea9b02ac217d29be912b078d65bbb4ac0480c677d8755`, MultiHop-RAG
  `db25b882fc9fe6cd6e76101330ffc816a9081813268706a016a263171cf80300`, aircargo
  `b3e4d3727f3456b66ee398698b6a610f60c0c269de5c81bd814ae4e2c0ebba15`.
- The committed export `reports/stage2/retrieval-20261021/`, manifest
  `f8dbfb9edbdd9af830017c2c583aedcbfc8f8fbedde6c806abb5de94288985e9`.
- V4 (`4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1`): `reports/answer-prompt-v4/4f48fed/v4-record.json`
  `81162268ad1c3af7cbe8f5cc885c7137c29864ed3a9acf5b778f17d28821749e`, which names its three
  committed rows files by hash; each row names its saved stream prompt by hash. 300 questions:
  WixQA, ConditionalQA and aircargo, 100 each.

## The parity gate, before any arm is read

On every question: the stand-ins give the recorded lists (the vector store the vector lane, the
BM25 index the BM25 lane in its order, the cross-encoder each candidate's recorded score,
refusing any other pool), each asked once; H gives the record's pool, five, scores, path and
expansion; under stage 2's V3 its sent documents and its prompt byte for byte, the hash the
record and the export hold; the M3 points read again are the export's. On the 300, all of them
among the records, H's replayed prompts equal V4's saved prompts byte for byte. One break
writes `parity.jsonl` (ids and flags) and exits 3; no arm is read, no question is left out.

## What is read, and how — frozen

Per question and arm: the documents and chunks given and sent, their token estimate, the cut,
the prompt's hash and whether it differs from H's; S's seeds, drops and reordering; P's count.
M3 at «sent», as `retrieval_summary.coverage` reads it, «expanded» beside. External bases, by
each base's gold: WixQA `gold_article`, the others `all_evidence_coverage`; the second metric
beside. H against each arm by the exact two-sided McNemar on b (gold with H only) and c (with
the arm only): **loss** at b > c and p < 0.05, **gain** at c > b and p < 0.05, else **no detected
difference**. Read per base and pooled; ConditionalQA, WixQA and the two pooled stop an arm,
MultiHop-RAG and the three pooled are printed, advisory (PLAN stage 7, step 4). A question whose
chunks or points cannot be read leaves that pair, counted; more than five on a base, or S
without a graph there, make the base and each pool holding it `NOT_EVIDENCE`.

aircargo: The context judge's plan, written before its first request — H's 115 prompts under
V4 and the prompts that differ from every prompt planned for the question of each arm that
qualifies on the external bases (no detected loss, no `NOT_EVIDENCE` stop reading, the pooled
gain above the MDE), 15 retests — under PRIVATE, once, after the record passes its checks; a
second replay must find the same files. Its verdicts pair H and each arm on «full» and on «full
or partial», both runs pooled, each run beside: the two pooled readings are stop readings of the
arm, a detected loss at either stops it. A failed stability (stage 2's rule: 12 pairs or more,
and κ ≥ 0.6 or 13 of 15 agreeing with none two steps apart) makes every arm's aircargo readings
`NOT_EVIDENCE`, more than five questions without a level that arm's; S without a graph of
aircargo's chunks has its aircargo readings `NOT_EVIDENCE` at the replay and is not planned.

**Gate G1.** An arm stops on a detected loss at any stop reading; else one `NOT_EVIDENCE`
leaves it `NOT_EVIDENCE`; else it is open. An open arm qualifies at one reading only, the two
deciding bases pooled: a detected gain larger than the MDE, c − b > 2.8·√(b + c) — the K
curve's 1.96 + 0.84 standard errors of the paired difference, the effect detected four times
in five; it holds the detection too (p ≤ 0.008 at its edge). A gain at one base alone, or one
the sample only just detects (six to none: p = 0.031, below 2.8·√6 = 6.9), does not qualify.
The family is the two arms at that one reading: under no effect an arm passes with a chance of
at most 0.004 (the exact binomial, any b + c), the two at most 0.008. One arm goes to answers:
the one qualifying alone; of two, the larger c − b at the two deciding bases pooled, P on a
tie. An arm left `NOT_EVIDENCE` does not hold back one that qualifies. None qualifying reads
«H stays», or `NOT_EVIDENCE` while an arm without a loss is unread. The replay decides when no
arm qualifies on the external bases; else the decision waits for `judged`. `NOT_EVIDENCE`
repeats on a re-run, the replay being deterministic: it opens no answers, stage 7 closes as
with «H stays» and names the arm unread, and that arm comes back only by a registered
amendment that removes the cause — the unread questions read, a graph, or a new judging run.
The survey's extra condition for S (a gain or a shorter median prompt) is not taken: a
prompt's length is not M3. It stands beside, as do the prompts each arm changes of V4's 300.

No forecast of the readings: S cannot be computed off the Mac. Under V3 P changes the sent
documents of 17 aircargo questions, none of aircargo-gr, 39 ConditionalQA, 11 WixQA and 13
MultiHop-RAG (the export, read again 2026-10-29; P1b keeps fewer than five on 23, 0, 40, 11
and 15). The smallest detectable loss is six questions lost and none gained (p = 0.031; seven
to one is not one); the smallest qualifying gain is eight to none, eleven to one, fourteen to
two.

## Running it on the Mac

Idle Mac, after registration and `python D:/RAG_new/.tmp/mf-mac/sync.py`:

```text
python D:/RAG_new/.tmp/mf-mac/remote.py --site pytest -q tests/test_stage7_arms_replay.py tests/test_graph_retriever.py tests/test_graph_retrieval_path.py tests/integration/test_graph_lane_e2e.py tests/test_gr1b_stage_replay.py tests/test_graph_route_observability.py tests/test_entity_retrieval.py tests/test_ab_remote_contextual_entity_arm.py tests/test_route_trace_units.py tests/test_route_trace_nodes.py
python D:/RAG_new/.tmp/mf-mac/remote.py --site reports.stage7.tools.arms_replay replay
```

Its defaults: runs `/Users/julia/RAG_new_chat_5e308fe/chatlive/runs`, archives
`/Users/julia/RAG_new_external_s1`, V4's runs `/Users/julia/RAG_new_chat_4f48fed/chatlive/runs`,
out `/Users/julia/RAG_new_stage7/out`, PRIVATE `/Users/julia/RAG_new_stage7/private`, all outside
the checkout. ≈ 10 minutes, stopped at 30. OUT goes to `reports/stage7/5e308fe/`, PRIVATE to
`D:/RAG_new_stage7_private/`, never committed. Then the laptop, beside the Mac:
`python -m scripts.context_judge run --out D:/RAG_new_stage7_private/judge` and
`python reports/stage7/tools/arms_replay.py judged --plan D:/RAG_new_stage7_private/judge`.

**The plan's size and cost:** only an arm that qualifies on the external bases is planned;
with none there is no plan, no request and no laptop time, and the replay's record holds the
decision. With both arms planned, at most 268 requests — 115 of H, at most 115 of S, at most
23 of P (the p2-aircargo questions where P1b keeps fewer than five; P is H on all 15 of
aircargo-gr), 15 retests; by V3's sent documents P's are about 17. $25.2 at stage 2's $0.094 a
request, $56.3 at $0.21; 2.7–9.7 h of the laptop at 36–130 s a request.

## Stops

Each writes nothing unless it says so. A run not complete or not of `5e308fe`; settings other
than stage 2's hybrid path at K 20 and the five; an input whose hash is not the frozen one; the
checkout's qa prompt not V4, or an input limit other than 2,636; the checkout's control other
than K 20, a 4,096 window and PyTorch's reranker, or an experiment's (`EXPERIMENT_ID` set); a
question V4 answered that is not among the records, or other than 300 of them read: the tool
stops. A parity break: `parity.jsonl` alone, exit 3. S that does not read H's pool, or keeps a
seed outside H's five: the tool stops and neither arm is read — S's path is then not the
product's, a defect to fix first. A record or row that would hold a text of a base or a
question: refused, and no plan is written. A plan already written that differs: refused. Past
30 minutes on the Mac: stop and read why.

## Records

- [`reports/stage7/tools/arms_replay.py`](../../reports/stage7/tools/arms_replay.py) `replay`
  writes `record.json` — the inputs, the tool and the measuring code by SHA-256, the frozen
  constants, each run's provenance, the gate's counts, each arm's spreads, the pairs, the stop
  readings, the prompts changed, the plan's size and hash, and the decision or «pending the
  aircargo context judge» — `rows.jsonl`, a question a line, and `parity.jsonl`; `judged`
  writes `judged.json`. Ids, flags and numbers: `stage2_common.without_text` refuses a text.
- `tests/test_stage7_arms_replay.py`: the arms through the product's code on a synthetic
  archive, the gate refusing one byte, the pairs at their edges, G1, the plan and its
  read-back, and a true gain of S from the replay through `judged`.
- The record goes to `reports/stage7/5e308fe/` with its artifact test, a capsule in
  `docs/evidence/` and a row in [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md).

SHA list of the run: the registration commit, written in by the next one; the SHA-256 of the
tool and of its test, below, which the test checks; the record's and the plan's, written in with
the evidence commit.

- `reports/stage7/tools/arms_replay.py` `7cd819655c9d2e88b1180518dc1413653b78209754dcc1541d441737b045e5a8`
- `tests/test_stage7_arms_replay.py` `14f504c6ebccd3443c8341ae4232beeb08c1d7213ed03e1ca460e2f89cfc4034`

## What it does not say

- Answer quality: M1 and M2 come in step 2, past G1.
- That S is the chat's path: the chat's stream calls the hybrid search. S here reads sections
  only — no links, no entities, no categories — over the archive's metadata, where the product
  reads Chroma's.
- E; and aircargo's gains: aircargo stops an arm and qualifies none, its M3 at the ceiling
  (under V3 at most 7 to turn on «full», 1 on «full or partial»).
- That no detected loss is no loss: a loss is read at p < 0.05, about two standard errors,
  while the effect detected four times in five is 2.8 of them (the K curve's 2.8·√(d/n)).
- That «H stays» means the arms do no good: a gain smaller than the MDE reads as none.
- That H's parent expansion is right: it still joins pieces across sections and gaps; it is the
  product's path, and the baseline.
- Another K, input budget or reranker runtime (stage 4): any of them changes H, and the
  replay runs again after a registered amendment.
