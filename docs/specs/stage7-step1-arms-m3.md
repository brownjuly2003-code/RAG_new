# Stage 7, step 1: the retrieval arms at M3 on stage 2's lists, without an answer

Status 2026-10-31: **registered before the run**, Amendment 1 with the stage-4 package, tool
and tests in the same commit, `6c52b06`; a cold read of this registration preceded it. The original
registration and S's fix were commit `8b922a1`, its [cold read](../operations/audit_opus55_30_10_26_stage7_gate.md)'s fifteen
findings applied ([Records](#records)). [`PLAN.md`](../../PLAN.md) stage 7, step 1:
«Поиск без генерации: М3 для каждой руки на ≈ 400 вопросах»; her word of 2026-10-28: stage 7
keeps both arms, the graph and P1b, and the entity graph's extraction cost is measured first.
No answer generation or new index search. Amendment 1 adds one live INT8 scoring phase.
**Read 2026-10-31:** parity 415 of 415, V4's prompts byte-equal 300 of 300; S stopped by a
detected loss, P no detected difference, so stage 7 closes with H
([the record](../evidence/stage7-step1-arms-record.md)).

A cold read of Amendment 1 (docs/operations/audit_opus55_31_10_26_stage7_amendment1.md) found 1 blocking, 2 should fix and 4 minor; each is applied (its Disposition says how).

Rewritten 2026-10-30 to PLAN's gate, after the [audit](../operations/audit_astra_30_10_26.md)'s
F5. The draft of 2026-10-29 opened answers on no detected loss and broke a tie by the prompts
an arm changes: with aircargo's M3 at its ceiling that opened answers almost always, and the
answers' paired reading (random seed, MDE 0.17–0.30) would most likely have read «not detected»
after hours of the Mac and the judge. Both rules are gone, from the tool and its test too. The
original control was K 20, a 4,096 window and PyTorch's fives. The registration required that
a package that changes them takes a registered amendment first. Amendment 1 below replaces
the arms' control; the old control remains the parity gate's. A replay after an amendment runs at another HEAD, which its judge runs'
`launch.json` name, so it takes a new PRIVATE; the old plan stays with the old record.

## Amendment 1, 2026-10-31: the stage-4 package

The product now defaults to K 14 per retrieval lane, an Ollama window of 3,584 (the product's
input limit is 2,176), and the INT8 reranker in ONNX Runtime. The fourth accepted lever is
llama.cpp's `cache-ram = 1024` on the Mac; it is not the replay's concern. H changes: fewer
candidates, a different five and a shorter fitted context. H in the arms, G1 and the aircargo
plan henceforth means **H_new** at this package; **H_old** means the original recorded control.

The parity gate stays exactly at H_old: K 20, the recorded PyTorch scores, a 4,096 window and
2,636 input limit (`K_RECORDED`, `WINDOW_V4`, `LIMIT_V4`). It checks all 415 records against
V3's sent documents and prompts and the export, and all 300 saved V4 prompts byte for byte.
It proves the reader faithfully reads stage 2; it remains the precondition, before any arm.
Both phases call the same parity gate: score after its input preconditions, before loading
the model or opening the journal, and replay again before reading the arms. A break writes
`parity.jsonl` and exits 3 in either phase.

H_new uses the recorded vector and BM25 lanes cut to 14 by the product. The vector Store
returns its first k when the product asks with `retrieval_k = 14`; the BM25 stand-in ranks its
recorded lane and the product slices it. This is the K curve's method
(`reports/k-curve/tools/k_curve.py`, `Selection`): both use the same lane prefixes and the
product's fusion and rerank. The curve sliced both lists before fusion; this replay obtains
those slices through the product's retrieval calls, and uses fresh INT8 scores instead of
the curve's recorded PyTorch scores.

All 415 questions are scored anew, including aircargo-gr, through
`vectordb._base_manager.get_reranker()` and `HybridRetriever`'s own rerank, with
`RAG_RERANKER_RUNTIME=onnx`. `RAG_RERANKER_ONNX` must name the measured export, SHA-256
`57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343`; its digest is checked in
chunks before loading, and another file is refused. ONNX Runtime must be 1.23.2.
The service passes no `RAG_RERANK_BATCH` (deploy/macos/start.py), so the product calls
`predict` once per question at its default of 32. A set `RAG_RERANK_BATCH` stops score and
replay, even if empty or 32; the header always holds `rerank_batch: null`, `batch_size: 32`.
Item 5a's scores cannot be reused: they score K-20 pools.
The export uses `quantize_dynamic` (`reports/stage4-step5a/tools/export_onnx.py`), which
quantizes activations over the whole input tensor of a call: a candidate's score depends on
the other candidates in its batch, and a K-14 pool is another batch.

Both phases use one recipe: the service's Python
`/Users/julia/RAG_Support_Assistant/.venv/bin/python` (3.11.15), with
`PYTHONPATH=<checkout>:/Users/julia/RAG_new_mf_gate_site`, in a clean environment, offline.
Before any model load both refuse transformers other than 4.44.2, ONNX Runtime other than
1.23.2, either `HF_HUB_OFFLINE` or `TRANSFORMERS_OFFLINE` other than `1`, or the cached
BAAI/bge-reranker-v2-m3 `refs/main` naming a snapshot other than
`953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`. This is step 5a's tokenizer snapshot and stack;
the gate's `remote.py --site` environment has transformers 4.41.2 and is only for pytest.
The header's `environment` is computed without loading a model: `sys.executable`, package
versions from `importlib.metadata` (transformers, tokenizers, numpy, chromadb,
sentence-transformers, langchain-ollama, langchain-community, onnxruntime), the offline flags,
cached snapshot, imported ORT version/module path and its default intra-op thread setting.
After loading, score verifies the tokenizer's actual snapshot (commit or resolved vocab path)
and records/checks the session's `intra_op_num_threads` against that setting. The product's
`OnnxCrossEncoder` passes no SessionOptions: the recorded value is 0, ORT's automatic choice,
not an assertion of four explicit threads. Product code is unchanged.

Two phases: `score` checks the clean checkout, environment, frozen inputs, complete runs,
amended `control()` and old parity gate before its first question, then writes
`OUT/int8_scores.jsonl`. Its header names HEAD, HEAD's parent and subject, the spec and
tool hashes, the `MEASURE_CODE` SHA-256 map, input provenance and record hashes, export
digest, environment, ORT version, batch and K. Both phases refuse a nonempty
`git status --porcelain`; ignored files (including `.tmp/` basetemps) are excluded.
Each subsequent line holds the label, case id, pool by archive positions, scores, the five
seen, effective batch size and seconds; no text. Each complete line is flushed to disk.
Score takes `fcntl.flock(LOCK_EX | LOCK_NB)` on the journal before truncating it and holds
it to exit; a taken lock stops with "another score holds the journal". An existing journal
is locked before reading or model loading. For a new journal the factory is validated before
creating it; if another writer creates it during loading, score refuses under the lock.
A restart resumes after the last newline-terminated line only if the header and complete rows
match; it truncates a torn last line, refuses another header or question order, and never
repeats a completed question. It prints a forecast after ten questions and checks the
three-times budget after each question and before a resume, counting the saved durations.
Model loading and the parity gate are additional to this forecast. Once the 3× stop fires,
keep the journal: move it aside with its stop time in the filename, and register it as
`NOT_EVIDENCE` in the run's record of evidence. Read the cause before starting score afresh
at a new OUT; do not resume or erase the stopped journal to reset its clock.

`replay` loads no model, checks the same environment and completes the old parity gate.
It compares the whole header, including environment, and copies it into `record.json`.
It then reads all INT8 score
lines, refuses any pool other than the scored one (positions and order as well as text), and
requires H_new's replayed five to equal the five seen by `score`. S uses that same pool and
INT8 scores before coherence and section expansion; P1b keeps by H_new's INT8 scores. V4's
prompt is fitted by the product at 3,584, and `prompt_input_limit` must give 2,176. G1 and the
aircargo plan are otherwise unchanged. Beside them, `package_advisory` reads H_new against
H_old on the 415's available context gold, with the same McNemar pairs at sent and expanded,
per base and pooled: b is old-only, c new-only. It is labelled advisory and enters no gate;
aircargo has no context gold here and gains no new judge merely for that comparison.

`control()` now requires `retrieval_top_k = 14`, `ollama_context_window = 3584` and
`reranker_runtime = onnx`, and records the export digest. The new OUT is
`/Users/julia/RAG_new_stage7/out-a1`, PRIVATE `/Users/julia/RAG_new_stage7/private-a1`.
RECORD stays `reports/stage7/5e308fe/`: it names the source stand, while the record, journal
and judge launches name the overlay of the registering commit, both SHAs named. The journal
and record hold HEAD, its parent and subject ("mf-gate overlay of <laptop sha>") and the
measuring-code hashes. The previous OUT and PRIVATE are preserved.

Run `python -m reports.stage7.tools.arms_replay score`, then
`python -m reports.stage7.tools.arms_replay replay`, with the environment and paths below.
Forecast: score ≈ 85–90 minutes plus load (415 × ≈ 12 s), stopped at 3× its forecast;
replay ≈ 10 minutes, stopped at 30. The idle-Mac record measured PyTorch at 28.2 s for K 20,
INT8 at ≈ 16 s; the K-14 pool is ≈ 30% smaller. These are planning estimates, not new results.
This amendment says nothing about generated answers or fresh approximate-index searches;
the limitations below still apply.

## Why

The original parity reading replays stage 2's lists and recorded PyTorch scores from stand
`5e308fe` with the product's code, as the
[no-reranker point](no-rerank-point.md) and the [K curve](k-curve-expanded.md) did: minutes of
the Mac, not PLAN's ≈ 3.5 h an arm. Amendment 1 scores INT8 once before that fast replay;
its arms redo the fit under the answer prompt V4 of stand `4f48fed` at the package's window.

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

- **H** — H_new, `HybridRetriever.get_relevant_documents_with_path` at the package's defaults.
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

Amendment 1: K is 14 for the arms, the five stay five, V4's prompt has a 3,584 window and
2,176 tokens in. K 20 and 4,096/2,636 remain only the parity gate's old control.

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

At H_old (K 20, recorded PyTorch scores, 4,096/2,636), on every question: the stand-ins give
the recorded lists (the vector store the vector lane, the
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

No forecast of the new readings: S cannot be computed off the Mac. Historically, at H_old
under V3 P changes the sent
documents of 17 aircargo questions, none of aircargo-gr, 39 ConditionalQA, 11 WixQA and 13
MultiHop-RAG (the export, read again 2026-10-29; P1b keeps fewer than five on 23, 0, 40, 11
and 15). The smallest detectable loss is six questions lost and none gained (p = 0.031; seven
to one is not one); the smallest qualifying gain is eight to none, eleven to one, fourteen to
two.

## Running it on the Mac

After registration and `python D:/RAG_new/.tmp/mf-mac/sync.py`, run the tests from the laptop:

```text
python D:/RAG_new/.tmp/mf-mac/remote.py --site pytest -q tests/test_stage7_arms_replay.py tests/test_graph_retriever.py tests/test_graph_retrieval_path.py tests/integration/test_graph_lane_e2e.py tests/test_gr1b_stage_replay.py tests/test_graph_route_observability.py tests/test_entity_retrieval.py tests/test_ab_remote_contextual_entity_arm.py tests/test_route_trace_units.py tests/test_route_trace_nodes.py
```

On the Mac, confirm it is idle before score (no competing chat/model or measurement job).
From the clean synced checkout, launch score detached and read its log; wait for its successful
completion (`"score": "complete", "questions": 415`) before replay. Both use the service
interpreter and exactly the same environment:

```sh
cd /Users/julia/RAG_new_mf_gate
mkdir -p /Users/julia/RAG_new_stage7/out-a1
nohup env -i HOME="$HOME" PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  LANG=en_US.UTF-8 PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ANONYMIZED_TELEMETRY=False \
  PYTHONPATH=/Users/julia/RAG_new_mf_gate:/Users/julia/RAG_new_mf_gate_site \
  RAG_RERANKER_ONNX=/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx \
  /Users/julia/RAG_Support_Assistant/.venv/bin/python -u -m reports.stage7.tools.arms_replay score \
  >> /Users/julia/RAG_new_stage7/out-a1/score.out 2>&1 </dev/null &
tail -n 30 /Users/julia/RAG_new_stage7/out-a1/score.out

env -i HOME="$HOME" PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  LANG=en_US.UTF-8 PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ANONYMIZED_TELEMETRY=False \
  PYTHONPATH=/Users/julia/RAG_new_mf_gate:/Users/julia/RAG_new_mf_gate_site \
  RAG_RERANKER_ONNX=/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx \
  /Users/julia/RAG_Support_Assistant/.venv/bin/python -u -m reports.stage7.tools.arms_replay replay
```

Its defaults: runs `/Users/julia/RAG_new_chat_5e308fe/chatlive/runs`, archives
`/Users/julia/RAG_new_external_s1`, V4's runs `/Users/julia/RAG_new_chat_4f48fed/chatlive/runs`,
out `/Users/julia/RAG_new_stage7/out-a1`, PRIVATE `/Users/julia/RAG_new_stage7/private-a1`, all
outside the checkout. The recipe sets only the export path; the package's K, window and ONNX
runtime defaults remain in effect, with no `RAG_RERANK_BATCH`. Score ≈ 90 minutes
plus load, stopped at 3× the first-ten forecast; replay ≈ 10 minutes, stopped at 30.
OUT goes to `reports/stage7/5e308fe/`, PRIVATE to `D:/RAG_new_stage7_private-a1/`, never
committed. Then the laptop, beside the Mac:
`python -m scripts.context_judge run --out D:/RAG_new_stage7_private-a1/judge` and
`python reports/stage7/tools/arms_replay.py judged --plan D:/RAG_new_stage7_private-a1/judge`.

**The plan's size and cost:** only an arm that qualifies on the external bases is planned;
with none there is no plan, no request and no laptop time, and the replay's record holds the
decision. Amendment 1 removes the old-control bound of 23 changed P prompts: the INT8 five
and smaller window can change that count. With both arms planned the conservative bound is
360 requests — 115 each of H, S and P, plus 15 retests — $33.84 at stage 2's $0.094 a request,
$75.60 at $0.21; 3.6–13 h at 36–130 s a request. The replay prints the actual frozen plan's size.

## Stops

Each writes nothing unless it says so. A run not complete or not of `5e308fe`; settings other
than stage 2's hybrid path at K 20 and the five; an input whose hash is not the frozen one; the
checkout's qa prompt not V4, or an input limit other than 2,636 for the old gate or 2,176 for
the arms; the checkout's control other than K 14, a 3,584 window and ONNX, or an experiment's
(`EXPERIMENT_ID` set); a dirty checkout; a set `RAG_RERANK_BATCH`; an absent or wrong INT8
export, ORT other than 1.23.2, transformers other than 4.44.2, another cached snapshot or an
offline flag other than `1` in either phase; a loaded tokenizer/session that disagrees at score; a
question V4 answered that is not among the records, or other than 300 of them read: the tool
stops. A mismatched score header, invalid complete line, missing scores at replay, a different
pool or a replayed five different from score's: refused. A taken journal lock refuses score
without changing the file. Score preserves its completed lines
on failure; a parity break writes `parity.jsonl` alone beside that journal, exit 3. S that does not read H's pool, or keeps a
seed outside H's five: the tool stops and neither arm is read — S's path is then not the
product's, a defect to fix first. A record or row that would hold a text of a base or a
question: refused, and no plan is written. A plan already written that differs: refused. Past
30 minutes at replay, or 3× score's forecast: the tool stops at a question boundary; inspect
why before another run. After score's 3× stop, keep and rename the journal with its stop time,
record it as `NOT_EVIDENCE`, and start afresh at a new OUT only after reading the cause.
No elapsed-time claim includes an interrupted, unfinished model call.

## Records

- [`reports/stage7/tools/arms_replay.py`](../../reports/stage7/tools/arms_replay.py) `score`
  writes the resumable `int8_scores.jsonl`; `replay`
  writes `record.json` — the inputs, the tool and the measuring code by SHA-256, the frozen
  constants, each run's provenance, the gate's counts, each arm's spreads, the pairs, the stop
  readings, the advisory H_new/H_old pairs, the score journal's hash and full header including
  environment, HEAD/parent/subject and measuring-code hashes, the prompts
  changed, the plan's size and hash, and the decision or «pending the
  aircargo context judge» — `rows.jsonl`, a question a line, and `parity.jsonl`; `judged`
  writes `judged.json`. Ids, flags and numbers: `stage2_common.without_text` refuses a text.
- `tests/test_stage7_arms_replay.py`: the arms through the product's code on a synthetic
  archive, the gate refusing one byte, the pairs at their edges, G1, the plan and its
  read-back, and a true gain of S from the replay through `judged`.
- The record goes to `reports/stage7/5e308fe/` with its artifact test, a capsule in
  `docs/evidence/` and a row in [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md).

SHA list of the run: Amendment 1 is registered with the stage-4 package in
`6c52b06c12505305c41714327b52e8bd01a36b0f`; the original
registration commit was `8b922a16999e9956f0aa36ecfc7e024e04d4069a`;
the SHA-256 of the tool and of its test, below, which the test checks; the record's and the
plan's, written in with the evidence commit.

- `reports/stage7/tools/arms_replay.py` `6ca8b723841d08dfd6f5d084bdc0883264c889eb495dc4d3728ac0a2ea623689`
- `tests/test_stage7_arms_replay.py` `3e8fe6c15290816ab1dda08eb73fe4c1151621592dc73b699fb0531fb19cbe72`

Written in with the evidence commit: `reports/stage7/5e308fe/record.json` SHA-256
`b9db1434a6091536540112591e29cb3f02f373660dd06469e6abebc3780b55e4`; no plan, as no arm
qualified ([the record](../evidence/stage7-step1-arms-record.md)).

## What it does not say

- A K-20 vector lane's first 14 equal a fresh K-14 search only if the index returns top 14 as
  the first 14 of top 20; Chroma's HNSW search is approximate.
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
