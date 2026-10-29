# Stage 4, step 3: K = 14 against 20, timed — the rerank's seconds with the retrieval alone

Status 2026-10-28: **registered before the first request**, with the reader and its test
([Records](#records)), in `3fc8ce7`; **read 2026-10-28**, four runs, all four gates passed:
[the record](../evidence/stage4-step3-record.md). [`PLAN.md`](../../PLAN.md) stage 4, item 3:
«Время — живой замер одного-двух K (≈ 1,5 ч)», after [the K curve](k-curve-expanded.md) and
[its record](../evidence/k-curve-record.md): the smallest K without a detected loss after
expansion is 14. It runs on [step 0](stage4-step0-diagnostics.md)'s and
[step 1](stage4-step1-rerank-memory.md)'s stand, with step 1's supervisor, unchanged. The one
value filled in at launch is `<c>`, the commit that registers this spec.

## Why

- **K's gold:** at K = 14 the three external bases together keep the gold after expansion in 136
  of 250 questions against 141 at K = 20 (b 6, c 1, exact McNemar p = 0.125): no loss detected,
  none excluded. The reranker then scores a median of 24–26 candidates instead of 34–36.
  Whether K enters the path is Julia's word (§8.3); she needs its seconds beside its gold.
- **Why the retrieval alone:** K is the retrieval's setting, read at the process's start, so it
  changes between runs, not between questions. With the model resident the rerank's seconds
  also hold the memory's wait — step 1's question — and their spread is wide: stage 2's chat-path
  series over V4's, the same arm days apart, 0.30–2.18 of each other (q10–q90, 100 questions,
  mine). A third less work does not show through that with a few pairs. Without a model the
  rerank is the cross-encoder's compute: stage 2's retrieval-only aircargo series
  ([`p2-aircargo`](../../reports/stage2/retrieval-20261021/p2-aircargo.json), code `5e308fe`)
  reranked its later questions in a median 26.71 s, 17.0–40.6 s for the twelve below.

## The stand

- **Code:** V4's stand, `S=/Users/julia/RAG_new_chat_4f48fed`, `CODE_SHA`
  `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1`. The tools run from `T=$S/step3`: step 1's
  `live_supervisor.py` (it takes `RAG_RETRIEVAL_TOP_K` from 1 to 99 as a deployment setting, for
  this step), stage 2's `live_retrieval.py` and its `stage2_common.py`, V4's `live_api.py`, each
  by the SHA-256 below, and this step's reader.
- **Mode `retrieval`:** the supervisor starts no API and no database, refuses a model in Ollama
  and runs `live_retrieval.py` once, on the CPU: the API's retriever
  (`vectordb.manager.get_retriever`) and its `get_relevant_documents_with_path`, a question at a
  time, nothing generated. Its file a question holds the walls of the retrieval, its vector search
  and its rerank, the lanes, the pool and the five kept.
- **Configuration:** the code defaults (five kept, `RAG_DEVICE=cpu`), K = 20 unless the run sets
  `RAG_RETRIEVAL_TOP_K=14`; tenant `aircargo`, the questions
  `$S/evaluation/curated_cases_aircargo.jsonl` (`3737d694…`), a byte-identical copy of the second
  generation's index for each run, removed after it, as in step 1. Interpreter
  `PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python` (3.11).

## The runs and the questions

- **The questions:** aircargo's registered order, its first thirteen, the same in every run and
  in the same order: `aircargo-probation-data` first — it loads the two encoders in every run and
  pairs with nothing — then `aircargo-probation-extend`, `aircargo-probation-dismissal`,
  `aircargo-dismissal-check`, `aircargo-dismissal-lawyer`, `aircargo-dismissal-order`,
  `aircargo-leave-sources`, `aircargo-leave-compensation`, `aircargo-leave-risk`,
  `aircargo-matliab-check`, `aircargo-matliab-disputed`, `aircargo-templates-choose` and
  `aircargo-templates-checklist`, the twelve of the pairs. The K curve gave them 20–27 candidates
  at K = 14 and 28–39 at 20.
- **Four runs, ABBA:** `s3-k20-1` (K = 20), `s3-k14-1` and `s3-k14-2` (K = 14), `s3-k20-2`
  (K = 20). Each question is asked twice at each K, at the same position; the order puts a drift
  of the shared Mac over the hour on both K alike.

## What is read

By `step3_reader.py`, from each run's `launch.json`, `effective_settings.json`,
`retrieval-cpu.json` and question files: of each question (an ask) its position, the walls of
the retrieval, its vector search and its rerank, the rerank's status and success, the lengths of
the vector and BM25 lanes, the merged candidates, the pool's count and the SHA-256 of its
`[source, chunk_index]` set, the five kept and their SHA-256 in order, the documents sent and the
prompt's estimated tokens. A shape not found leaves null and a note, never a guess.

## How it is read — frozen before the first request

- **An ask is read** when it has the three walls, the rerank succeeded (`reranker_ok`, status
  `ok`), its vector lane is K long and its BM25 lane holds one to K, and it has a pool and five
  kept.
- **The run gate:** (i) `launch`: `code_sha` `4f48fed5…`, mode `retrieval`, status `complete`
  with the one variant `cpu` at exit 0, the thirteen questions in order, no model in Ollama
  before or after, and the run's K — `RAG_RETRIEVAL_TOP_K=14` in a K = 14 run, absent or 20 in
  a K = 20 one; (ii) `settings`: `retrieval_top_k` the run's K, five kept and `cpu` in
  `effective_settings.json`; (iii) `drivers`: the four by the SHA-256 below, two levels above
  the run; (iv) `asks`: the thirteen at positions 1–13 in order, each read; (v) `summary`:
  `retrieval-cpu.json` lists the thirteen with their files' walls.
- **A question's pair** (positions 2–13) is its two asks at K = 20 and its two at K = 14, from
  runs whose gates passed, at its position; **readable** when all four are read. Each side is the
  mean of its two asks.
- **The answer,** over the readable questions, K = 14's rerank seconds against K = 20's:
  **faster** when K = 14 is below on more questions and the exact two-sided sign test gives p
  below 0.05; **slower** the other way round; **no detected difference** otherwise;
  `NOT_EVIDENCE` with fewer than ten readable questions. With twelve, faster needs
  at least 10 of 12 (p = 0.039).
- **The number:** the median, over the readable questions, of K = 20's rerank seconds less
  K = 14's — the saving — and of K = 14's over K = 20's — the ratio.
- **Printed, deciding nothing:** the same medians for the retrieval and its vector search; the
  median rerank seconds at each K; the same K's spread, the median of the two asks' difference
  over their mean; how many questions have the same pool and the same five in both asks of a K;
  how many pools have the K curve's count; per run, the retriever's build seconds.

**Forecast, written before the first request:** **faster**, on 12 of 12; the ratio ≈ 0.70, the
K curve's candidates at 14 over 20 for these twelve (0.64–0.73); a saving ≈ 7–9 s of a rerank
≈ 25–28 s at K = 20.

## Running it

On the Mac, with `S` and `PY` above: `CL=$S/chatlive`, `T=$S/step3`,
`IX=/Users/julia/RAG_new_external_s1/aircargo` and `Q` the thirteen questions above, comma-
separated in their order. A run starts detached, so ssh returns at once (`;`, never `&&`, before
`nohup`, as in stage 2).

1. **Tools:** `mkdir -p $T/runs`; from the laptop, `git -C D:/RAG_new show
   <c>:reports/stage4-step3/tools/step3_reader.py | ssh deproject-mac "cat >
   /Users/julia/RAG_new_chat_4f48fed/step3/step3_reader.py"`, and the same for
   `reports/stage4-step1/tools/live_supervisor.py`, `reports/stage2/tools/live_retrieval.py` and
   `reports/stage2/tools/stage2_common.py`, each to its name in `$T`; on the Mac,
   `cp -p $CL/live_api.py $T/`; then `shasum -a 256 $T/*.py` prints the five of the list below.
2. **Idle, before each run,** step 0's rule: the 5-minute load below 2; `pgrep -f
   "[p]ytest|[l]lama-server|[_]supervisor|[r]eplay\.py|[s]tep[0-3]_|[l]imactl"` finds nothing;
   `/api/ps` is `{"models":[]}`; no `$HOME/ci_local/.lock_ci-local`. Else wait; nothing is
   stopped.
3. **A run,** in the order above, `KX` empty for K = 20 and `,RAG_RETRIEVAL_TOP_K=14` for 14:

       cp -Rp $IX/index/chroma $T/runs/$L.chroma; diff -rq $IX/index/chroma $T/runs/$L.chroma && echo same
       LIVE_VARIANTS=cpu nohup $PY -u $T/live_supervisor.py $L retrieval $Q 1400 TENANT=aircargo,CHROMA=$T/runs/$L.chroma,CASES_FILE=$S/evaluation/curated_cases_aircargo.jsonl$KX >> $T/runs/$L.supervisor.log 2>&1 </dev/null &

4. **One question first:** when `$T/runs/s3-k20-1/retrieval/` holds its first file, while the run
   goes on, `$PY -I $T/step3_reader.py $T/s3-k20-1.q1.step3.json $T/runs/s3-k20-1`: its one ask
   must be read; else the run is stopped as [Stops](#stops) says and step 5's rule applies.
5. **After a run's `LIVE_DONE`,** the last line of `$T/runs/$L.supervisor.log`: `rm -rf
   $T/runs/$L.chroma; $PY -I $T/step3_reader.py $T/$L.step3.json $T/runs/$L`. Its gate must pass
   before the next run. A failed point is a shape the reader did not know: a marked error fix
   (the change, its test, the new SHA-256, one commit), then the run is read again, or run again
   as `$L-r2` with its K where its files cannot give the point back. A second failure:
   `NOT_EVIDENCE`.
6. **The record:** `$PY -I $T/step3_reader.py $T/step3.json $T/runs/s3-k20-1 $T/runs/s3-k14-1
   $T/runs/s3-k14-2 $T/runs/s3-k20-2`, a rerun read in its run's place, never beside it; its files
   are copied to the laptop as bytes.

### Stops

`live_retrieval.py`'s own caps, 3× its forecasts: 360 s for a run's first question, 120 s for
the others; a question past its cap ends the run with exit 5, a broken path (an empty lane, a
rerank not `ok`, fewer than five documents) with exit 6. The supervisor bounds the run at
1,400 s, 3× its forecast. A run so ended is run again once as `$L-r2`; a second end of the same
kind stops step 3, its unread questions `NOT_EVIDENCE`, and Julia gets the measured pace.

**Forecast:** a K = 20 run ≈ 7.6 min (the retriever's build and the first question ≈ 2 min,
twelve more at ≈ 27 s), a K = 14 run ≈ 6 min; ≈ 27 min for the four, ≈ 35 min with the copies,
the checks and the reads, once the Mac is idle.

## Records

`reports/stage4-step3/4f48fed/`: `step3.json` (the four runs, the pairs and the readings), each
run's own read (`<label>.step3.json`, the gates') and the first question's read
(`s3-k20-1.q1.step3.json`): numbers, enums, ids, model names, the paths named here and SHA-256
strings, never a question, document, source name or prompt. The run directories stay on the Mac
(their question files hold the question and the documents' texts); the record names their files
by SHA-256. Step 3's timing is no slice by the acceptance rule (no behaviour, case or quality
number changes); its record gets a row in [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md) and a
test that reads it again. The reader and its test are committed with this spec, and the test
checks each SHA-256 below; a later change is a marked error fix that updates this list:

- `reports/stage2/tools/live_api.py` `43ff96f06af18538a2571d68a86e898ecfcdd5fcab47039f0d58bd245361a7b5`
- `reports/stage2/tools/live_retrieval.py` `9e41910d371630ec7b215c8649d5c1a124da16ff5c0977d89c291f5de371e916`
- `reports/stage2/tools/stage2_common.py` `4d5241560ab5425faa0a1fe6c5b856454b3f8ee47e59187f0da6644b1bad48da`
- `reports/stage4-step1/tools/live_supervisor.py` `915ffa9e22e3165f56cd54194fe20e89c8e4146f5a10170f32094a03138fe536`
- `reports/stage4-step3/tools/step3_reader.py` `7fe8b2672773e3618da480368d6e2526af3adc3e0530f4edf3aa8e580577b8d9`
- `tests/test_stage4_step3_tools.py` `c55da72422533b17215c6cf78aa6af40d6f79d87f4f99b7b7bed164387ef8d26`

## Not said

- The rerank without a model: with the model resident its seconds also hold the memory's wait
  (step 1), and K's share of that wait is not measured here. The final timing (item 7) measures
  the path as it ends up.
- Twelve questions of one corpus, one stand, one day, on a Mac other projects share.
- K's gold is the K curve's: no loss detected at 14, none excluded; nothing here on quality. If
  K changes, step 6 answers the 100 aircargo questions again (PLAN).
- A live pool at K = 14 may differ from the K curve's: there the vector lane's first 14 stood in
  for a search of 14, whose HNSW search goes less deep. Printed beside, deciding nothing.
