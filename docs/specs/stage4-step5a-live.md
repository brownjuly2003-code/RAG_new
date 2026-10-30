# Stage 4, item 5a: the short live series — INT8 of the reranker in the chat, behind its setting

Status 2026-10-30: **registered before the first request**, with the supervisor's copy, the reader,
the stand's script and their test ([Records](#records)). [`PLAN.md`](../../PLAN.md) stage 4, item
5a: «Сначала ONNX FP32 против PyTorch, затем INT8, на сохранённых списках кандидатов этапа 2 …
затем короткая живая серия.» It follows [item 5a's comparison](stage4-step5a-int8-reranker.md)
and [its record](../evidence/stage4-step5a-record.md), with [step 1](stage4-step1-rerank-memory.md)'s
runner, reader, sampler, idle rule and stop rule. The one value filled in at launch is `<c>`, the
commit that registers this spec. Its [cold read](../operations/audit_opus55_30_10_26_live_spec.md)
was applied before registration: it moved the reranker's load to the API's start, and the
noise it found doubled the runs, eight in four blocks, twenty pairs.

## Why

- **INT8 passed on the idle Mac.** On stage 2's saved pools the INT8 export kept the gold (141 →
  144 of 250 after the expansion) and reranked aircargo's thirty faster on 30 of 30, a ratio
  1.751: 12.0 s saved of PyTorch's 28.2 s. There the reranker ran alone.
- **The chat is another place.** In the 30-question record the rerank took 102 s of a question's
  median 320 s, and step 1 read why: without the answer's model resident the same rerank took a
  median 0.2594 of its seconds ([step 1's record](../evidence/stage4-step1-record.md)). The
  rerank waits for memory, not only for its arithmetic.
- **What INT8 changes there, and what it does not.** Its weights are a quarter of PyTorch's (the
  INT8 file 571 MB, the FP32 export's data 2,271 MB), but on the idle Mac its process was no
  smaller: a peak of 2,593 MiB against PyTorch's 2,684 MiB, and 1,426 MiB against 549 MiB after
  the load. In the chat the load falls in the API's start, before the model is preloaded, so an
  INT8 run holds that memory beside the resident model from its first question. Whether its idle
  gain holds, grows or vanishes there is read here, in the product's own path.
- **The setting.** Since `81cd2ad` the chat reranks with the ONNX export `RAG_RERANKER_ONNX`
  names when `RAG_RERANKER_RUNTIME=onnx`; PyTorch stays the default
  ([its E2E](../../tests/test_reranker_onnx_e2e.py)). Both runtimes run one commit here. Whether
  INT8 enters the path stays her word (PLAN.md §9): this series gives the chat's number.

## The stand

- **Code:** `81cd2ad`'s tree, `S=/Users/julia/RAG_new_chat_81cd2ad`, `CODE_SHA`
  `81cd2ade80ea9bc5a4f3ea721a16bd05037136fd`, raised once by
  [`raise_stand.sh`](../../reports/stage4-step5a-live/tools/raise_stand.sh) (V4's, without its
  check of the product's diff against `5e308fe`) and reused: the script refuses an existing
  stand. The drivers run from `T=$S/live5a`: V4's `live_api.py` and step 1's `live_runner.py`,
  unchanged, and this series' copy of step 1's supervisor ([The copy](#the-copy)). Each run
  starts a fresh API, database and llama-server process, asks through `/api/ask/stream` and
  unloads the model, as step 1's did.
- **Configuration:** mode `prod`, the code defaults (K = 20 candidates, five kept,
  `RAG_DEVICE=cpu`, the 3,600-s ceiling since `468224b`), tenant `aircargo`, the questions
  `$S/evaluation/curated_cases_aircargo.jsonl` (`3737d694…`); a byte-identical copy of the second
  generation's index for each run, removed after it, with V4's corpus files
  (`corpus.manifest.json` `2b2e9232…`, `chunks-report.json` `bf01530e…`,
  `index/index-receipt.json` `2dcc80e7…`, gated by the reader); the supervisor's default model,
  `qwen3:4b-instruct-2507-q4_K_M` (`0edcdef34593…`, gated by the reader), on the CPU, never a
  fake one.
- **The reranker:** the product's, `BAAI/bge-reranker-v2-m3`, snapshot `953dc6f6…` from the Mac's
  Hugging Face cache, checked before run 1 and after the last (step 4), in either runtime:
  PyTorch's CrossEncoder (`RAG_RERANKER_RUNTIME=torch`), or item 5a's INT8 export
  (`RAG_RERANKER_RUNTIME=onnx`), the file
  `/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx`
  (`57335a9f…`, by [its manifest](../../reports/stage4-step5a/onnx/manifest.json)), in ONNX
  Runtime 1.23.2's CPU provider with its default threads, the tokenizer the model's own from
  the same snapshot. Each run names its runtime, PyTorch's too, so no run relies on a default.
- **Interpreter:** `PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python` (3.11), the API's and
  item 5a's, with ONNX Runtime 1.23.2; the tools need its standard library only. V4's
  `stand_env.py` writes a line before run 1 and after the last; the reader's stand gate wants
  each to name Ollama 0.33.2 and one server, the same pid and start and the same installed
  distributions in both, or every reading is `NOT_EVIDENCE`.

## The runs and the questions

- **The questions:** aircargo's registered order (`reports/stage2/tools/stage2_cases.py
  aircargo`, the file order) from step 0's fifth: `aircargo-dismissal-lawyer`, step 1's four —
  `aircargo-dismissal-order`, `aircargo-leave-sources`, `aircargo-leave-compensation`,
  `aircargo-leave-risk` — and `aircargo-matliab-check`; the same six in every run, in this order.
- **The reranker's load:** the API loads its reranker at its start, building the default
  tenant's retriever in its lifespan (`api/app.py` at `81cd2ad`): before it answers its health
  check, before the supervisor preloads the model, before any question. Item 5a's idle loads
  took 10.8–27.8 s with PyTorch and 3.9–7.3 s with INT8. The first question's build gets the
  loaded model back; the load is printed per run, never paired.
- **The warm-up:** a run's first question, `aircargo-dismissal-lawyer`, is read and gated but
  never paired. It pays the reranker's first call: item 5a's PyTorch blocks took 133.1 and
  129.5 s for their first question against a median 28.2 s, while INT8's 14.7 and 13.2 s sat
  below its median, ≈ 15 s. Paired, PyTorch's cold call would read as INT8's gain; its seconds
  are printed instead.
- **Every question in step 1's arm A:** the model stays resident, the runner renews its
  keep-alive before each question (`ARM=AAAAAA`), as in the product.
- **Eight runs, ABBA twice:** `s5a-torch-1` (PyTorch), `s5a-int8-1` (INT8), `s5a-int8-2` (INT8),
  `s5a-torch-2` (PyTorch), then `s5a-torch-3`, `s5a-int8-3`, `s5a-int8-4` and `s5a-torch-4` the
  same way, one after another. Block n is `s5a-torch-n` with `s5a-int8-n`. A later question's
  pair is its ask in a block's PyTorch run and in its INT8 run: five pairs a block, twenty in
  all. ABBA puts both runtimes at the same mean time, so a steady drift of the shared Mac falls
  on both.
- **Why eight: the noise comes by run.** In the 30-question record's two runs of one code
  (`reports/chat-live-4b/19beeb1/runs.json`, `qwen3-4b-instruct-q30` and its `-r2`) the same
  question at the same position reranked at a ratio of 0.17–1.97 between the runs, in
  stretches: 0.17–0.24 at positions 2–6, 0.97–1.02 at 7–9, 0.63 at 10, 1.44–1.97 at 11–15, a
  median 0.987. A run's state moves its questions together, so a block's five pairs are not
  five independent signs: four blocks read four states, and a reading holds only when every
  block leans its way.
- **What twenty pairs can show:** the sign test reads a difference at p below 0.05 when one
  runtime is below on at least 15 of 20 readable pairs (p = 0.041; 14 of 20 gives 0.115), 15 of
  19, 14 of 18, 13 of 17 or 13 of 16. If q is the chance that INT8 is below on one pair, the
  chance to read faster with every block leaning INT8 is 0.96 at q = 0.9, 0.87 at 0.85 and 0.72
  at 0.8, for independent pairs (four runs' ten pairs: 0.74, 0.54 and 0.38). Both sides' noise
  counts: a pair flips where PyTorch's ask runs far below its own seconds or INT8's far above
  its own. The whole question's ≈ 330–720 s carries the answer's seconds too; there the same
  saving can go unseen.

## What is read

**Every 5 s,** step 0's sampler (`step0_sampler.py`, unchanged), as in step 1: the monotonic
clock, Ollama's serve log size, `vm_stat`, the swap and the load, and each `llama-server`
process's pid, RSS, footprint and compressed size; never a process's arguments or environment.

**Per question** (an ask), by step 1's `step1_reader.py`, byte for byte, which
`live5a_reader.py` loads beside it by its SHA-256: everything step 1 reads — the case file, the
spans of `stages.jsonl`, the samples inside the retrieval, the vector search and the rerank, the
whole seconds (the action's plus the question's total) — and, added here:

- **the five:** the `[source, chunk_index]` list the rerank kept, from its end row, as the
  SHA-256 of the list in its order and of the same list sorted; never a source name;
- **the load:** the highest 1-minute load (`vm.loadavg`'s first) the samples read inside the
  rerank and inside the whole question.

**Per run:** the runtime its label registers, the overrides in `launch.json`, the API's
`reranker_runtime` and `reranker_onnx_path` from `effective_settings.json` (every setting the API
took) beside step 1's three and the reranker's model, the drivers' SHA-256; the reranker's load:
each `vectordb._base_manager.get_reranker` call's seconds, an error's type and whether it ended
before the first question, in order, the first the load; the `llama-server` pids the samples
saw; and for an INT8 run the ONNX file's SHA-256 — hashed once the run is over, never while it
runs: its 571 MB read then would stand in the page cache beside the processes the series times.

**Per series:** V4's corpus files by SHA-256 (`--corpus`) and the `stand_env.py` lines
(`--environment`): of a line its time, Ollama's version, its servers' pid and start and the
installed distributions' SHA-256, nothing else.

A shape not found leaves null and a note, never a guess. What no reading below uses is printed and
decides nothing.

## How it is read — frozen before the first request

By `live5a_reader.readings`, over the pairs `live5a_reader.pair_up` forms:

- **An ask is read, and its arm A held,** by step 1's rules, unchanged.
- **A pair** is a paired question's ask in a block's PyTorch run and in its INT8 run. It is
  **readable** when both runs passed their gates, both asks are read and held arm A, they stand
  at the same position with the same candidates (the pool's SHA-256), and both have rerank and
  whole seconds. Otherwise the pair gives its reasons and no reading.
- **The rerank:** INT8's rerank seconds against PyTorch's over the readable pairs, each block's
  pairs below and above counted too — **faster** when INT8 is below on more pairs, the exact
  two-sided sign test gives p below 0.05 and every block leans its way, below on more of its
  pairs than above; **slower** the other way round; **no detected difference** otherwise; each
  with at least sixteen readable pairs of the twenty and a stand that passed its gate,
  `NOT_EVIDENCE` without. A tie counts on neither side. The number: the median over the readable
  pairs of PyTorch's seconds over INT8's — the ratio, item 5a's — and of their difference — the
  saving.
- **The whole question:** the same, on the whole seconds. The answer read from INT8's five may
  differ (below), and its seconds stand in this reading.
- **The outcome:** the rerank **faster** — INT8's idle gain reaches the chat, with its ratio and
  saving: the number the package question takes (PLAN.md §8.3, item 2); the whole reading says
  whether a question is detectably faster at twenty pairs. **No detected difference** — the gain
  is not shown in the chat at twenty pairs: the package question names INT8 with its idle
  numbers and this series' medians as not shown, and the choice stays hers. **Slower** — INT8
  costs the chat time, and the package goes without it. `NOT_EVIDENCE` — nothing is read.
- **Printed, deciding nothing:** per pair, and as medians by runtime: the rerank and whole
  seconds, the vector search, retrieval, first-token and total seconds, the answer's first
  chunk, the pages faulted back inside the rerank, `llama-server`'s footprint and the swap at the
  rerank's start, the highest 1-minute load inside the rerank and inside the question; the
  fives' agreement, the same order, the same set or another set. Per run: the reranker's load,
  the `llama-server` pids seen and the warm-up's rerank, build and whole seconds.

**The run gate,** in each run's own read: (i) `launch`: `code_sha` `81cd2ade…`, status `complete`
with runner exit 0, mode `prod`, the default model by its name and its digest `0edcdef3…`, a
registered label, arm `AAAAAA`, the six questions in order, and `RAG_RERANKER_RUNTIME` the run's
runtime, with `RAG_RERANKER_ONNX` the file for INT8 and absent for PyTorch; (ii) `settings`:
K = 20, five kept, `cpu` and the reranker `BAAI/bge-reranker-v2-m3`, and the API's runtime and
file the run's (the file, or empty for PyTorch); (iii) `drivers`: V4's `live_api.py`, step 1's
`live_runner.py` and this copy two levels above the run, and step 0's sampler beside the reader,
by the SHA-256 below; (iv) `asks`: the six in order, each read; (v) `actions`: one for each,
none failed; (vi) `samples`: step 1's rule — step 0's schema, samples from before every
question's start to after its last event, no note but the three step 1 allows; (vii)
`reranker`: the first `get_reranker` call ended before the first question, none with an error,
and for INT8 the file's SHA-256 item 5a's; (viii) `llama`: one `llama-server` pid in the run's
samples, the resident model's — a second is a reload or another model beside it.

**The stand gate,** in the series' read: V4's three corpus files by the SHA-256 above, and two or
more `stand_env.py` lines, each naming Ollama 0.33.2 and one server, with the same pid and start
and the same distributions' SHA-256 in every line.

**Forecast, written before the first request:** the eight run gates pass, and the stand's. The
rerank reads **faster**: INT8 below on ≈ 16–19 of the 20 pairs, every block leaning INT8, a
ratio ≈ 1.5–2 and a saving ≈ 35–65 s of PyTorch's ≈ 100–135 s: INT8 keeps its arithmetic's
gain, and has a quarter of the weights to fault back, but its peak is no lower, so the memory
the chat contends for stays. The whole question: INT8 below on ≈ 12–15 of the 20, the median
saving about the rerank's; **no detected difference** is more likely than **faster**. Printed:
the same order on 16 pairs and the same set on `aircargo-matliab-check`'s four, as item 5a
scored these six, if the chat's pools are stage 2's; the warm-up's rerank ≈ 90–180 s for
PyTorch (item 5a's idle first calls took 133.1 and 129.5 s, step 1's first ask in arm A 91.1 s)
and ≈ 35–70 s for INT8, below its later reranks' ≈ 50–90 s: INT8 pays no cold first call, and a
run's first rerank is its least pressed — step 1's 91.1 s was the lowest of its four in arm A,
and item 5a's ratio puts INT8 at ≈ 52 s there.

## Running it

On the Mac, with `S` and `PY` above: `T=$S/live5a`, `IX=/Users/julia/RAG_new_external_s1/aircargo`,
`ONNX=/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx`,
`HF=$HOME/.cache/huggingface/hub/models--BAAI--bge-reranker-v2-m3`,
`Q=aircargo-dismissal-lawyer,aircargo-dismissal-order,aircargo-leave-sources,aircargo-leave-compensation,aircargo-leave-risk,aircargo-matliab-check`.
Each command below is one line, and a step goes on only when the one before printed what it
names. A line that starts a run detaches it, so ssh returns at once. The laptop's lines run in
Git Bash, whose pipe passes the bytes as they are.

1. **The stand and the tools.** On the Mac,

       cat $S/CODE_SHA

   prints `81cd2ade80ea9bc5a4f3ea721a16bd05037136fd`. What an earlier smoke left in `$T` is
   moved out of it, never into the record. From the laptop:

       git -C D:/RAG_new show <c>:reports/stage4-step5a-live/tools/live5a_reader.py | ssh deproject-mac "cat > /Users/julia/RAG_new_chat_81cd2ad/live5a/live5a_reader.py"
       git -C D:/RAG_new show <c>:reports/stage4-step5a-live/tools/live_supervisor.py | ssh deproject-mac "cat > /Users/julia/RAG_new_chat_81cd2ad/live5a/live_supervisor.py"

   On the Mac:

       cp -p $S/reports/stage2/tools/live_api.py $S/reports/stage4-step1/tools/live_runner.py $S/reports/stage4-step1/tools/step1_reader.py $S/reports/stage4-step0/tools/step0_sampler.py $T/
       shasum -a 256 $T/*.py; ls -A $T $T/runs

   `shasum` prints the six by [the list below](#records): `live5a_reader.py` and
   `live_supervisor.py` this series' (`reports/stage4-step5a-live/tools/`), `live_api.py` V4's,
   `live_runner.py` and `step1_reader.py` step 1's, `step0_sampler.py` step 0's; `ls` prints the
   six and `runs`, and nothing in `runs`. Else nothing runs.
2. **The runtime:**

       PYTHONPATH=$S:/Users/julia/RAG_new_mf_gate_site $PY -c "import onnxruntime; print(onnxruntime.__version__)"
       shasum -a 256 $ONNX

   print `1.23.2` and item 5a's `57335a9f…`; else nothing runs.
3. **Idle, before each run,** step 1's rule:

       sysctl -n vm.loadavg; pgrep -f "[p]ytest|[l]lama-server|[_]supervisor|[r]eplay\.py|[s]tep[01]_|[n]gram_decode|[l]imactl"; curl -s http://127.0.0.1:11434/api/ps; ls $HOME/ci_local/.lock_ci-local

   the 5-minute load, the second number, below 2; `pgrep` finds no pytest, model, supervisor,
   replay, sampler, n-gram series or CI VM; `/api/ps` is `{"models":[]}`; no lock. Else wait;
   nothing is stopped.
4. **The stand's state, before run 1 and after the last run:**

       $PY $S/reports/answer-prompt-v4/tools/stand_env.py >> $T/environment.jsonl
       (cat $HF/refs/main; echo; ls $HF/snapshots) >> $T/hf.txt

   `hf.txt` names `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` alone, both times: the snapshot of
   PyTorch's model and of both runtimes' tokenizer. Before run 1 else nothing runs; after the
   last else the series is `NOT_EVIDENCE`. The reader's stand gate reads `environment.jsonl`
   (step 8).
5. **A run,** in the order `L=s5a-torch-1 R=RAG_RERANKER_RUNTIME=torch`, `L=s5a-int8-1
   R=RAG_RERANKER_RUNTIME=onnx,RAG_RERANKER_ONNX=$ONNX`, `L=s5a-int8-2` with the same `R`,
   `L=s5a-torch-2` with PyTorch's, then `s5a-torch-3`, `s5a-int8-3`, `s5a-int8-4` and
   `s5a-torch-4` alike. The index first:

       cp -Rp $IX/index/chroma $T/runs/$L.chroma; diff -rq $IX/index/chroma $T/runs/$L.chroma && echo same

   after `same` the sampler, its `--max-sec` past the longest run's stop below:

       nohup $PY -I $T/step0_sampler.py $T/$L.samples.jsonl --max-sec 9000 > $T/$L.sampler.err 2>&1 </dev/null &
       sleep 6; test -s $T/$L.samples.jsonl && echo sampling

   after `sampling` the supervisor:

       nohup $PY -u $T/live_supervisor.py $L prod $Q 1440/1200 TENANT=aircargo,CHROMA=$T/runs/$L.chroma,CASES_FILE=$S/evaluation/curated_cases_aircargo.jsonl,ARM=AAAAAA,$R >> $T/runs/$L.supervisor.log 2>&1 </dev/null &

6. **One question first,** in runs 1 and 2, the first of each runtime: when
   `$T/runs/$L/progress.log` holds its first `CASE` line, while the run goes on,

       $PY -I $T/live5a_reader.py $T/$L.q1.live5a.json --run $T/$L.samples.jsonl $T/runs/$L
       $PY -I -c "import json,sys; r=json.load(open(sys.argv[1]))['runs'][0]; a=[x for x in r['asks'] if x['case_id']=='aircargo-dismissal-lawyer'][0]; print(a['read'], a['arm_held'], a['five'] is not None, r['reranker_loads'][:1], r['llama_pids_seen'])" $T/$L.q1.live5a.json

   prints `True True True`, the load with `'error': None` and `'before_first_case': True`, and
   `1`; else the run is stopped as [Stops](#stops) says, and step 7's rule for a failed point
   applies.
7. **After a run's `LIVE_DONE`,** the last line of `$T/runs/$L.supervisor.log`:

       sleep 10; touch $T/$L.samples.jsonl.stop; rm -rf $T/runs/$L.chroma; sleep 10
       echo "$L $(date -u +%FT%TZ) $(sysctl -n vm.loadavg) $(pgrep -f '[p]ytest|[l]lama-server|[_]supervisor|[r]eplay\.py|[s]tep[01]_|[n]gram_decode|[l]imactl' | wc -l) $(curl -s http://127.0.0.1:11434/api/ps) $(ls $HOME/ci_local/.lock_ci-local 2>/dev/null | wc -l)" >> $T/after-runs.txt
       $PY -I $T/live5a_reader.py $T/$L.live5a.json --run $T/$L.samples.jsonl $T/runs/$L

   The line in `after-runs.txt` is step 3's look at the run's end, its own sampler and
   supervisor gone: no match, `{"models":[]}` and no lock — else a foreign job, a model or a CI
   VM may have run beside it, and the run is run again as `$L-r2` with its runtime. Its gate
   must pass before the next step; a second `llama-server` (`llama`) also runs it again as
   `$L-r2`. Another failed point is a shape the tools did not know: a marked error fix (the
   change, its test, the new SHA-256, one commit), then the run is read again, or run again as
   `$L-r2` where its files cannot give the point back. A run that fails again as `-r2` leaves
   its block's five pairs unread, and the series below sixteen: `NOT_EVIDENCE`.
8. **The record,** after the last run's step 4:

       $PY -I $T/live5a_reader.py $T/live5a.json --run $T/s5a-torch-1.samples.jsonl $T/runs/s5a-torch-1 --run $T/s5a-int8-1.samples.jsonl $T/runs/s5a-int8-1 --run $T/s5a-int8-2.samples.jsonl $T/runs/s5a-int8-2 --run $T/s5a-torch-2.samples.jsonl $T/runs/s5a-torch-2 --run $T/s5a-torch-3.samples.jsonl $T/runs/s5a-torch-3 --run $T/s5a-int8-3.samples.jsonl $T/runs/s5a-int8-3 --run $T/s5a-int8-4.samples.jsonl $T/runs/s5a-int8-4 --run $T/s5a-torch-4.samples.jsonl $T/runs/s5a-torch-4 --corpus $IX --environment $T/environment.jsonl

   a rerun read in its run's place, never beside it; its files are copied to the laptop as
   bytes.

### Stops

A question past its cap (1,440/1,200 s: 1,440 s for a run's first question, 1,200 s for the
others, 3× the forecasts below) stops its run; the supervisor stops the API and the database and
unloads the model. An arm's action that fails stops its run before its question (exit 6). A run
without `LIVE_DONE` at 3× its forecast (≈ 132 min for PyTorch, ≈ 114 min for INT8) is stopped as
stage 2 stops a part, `pkill -f "[R]AG_new_chat_81cd2ad/live5a/live_runner.py"`, and closed as
step 7 closes a run. Its unread questions are `NOT_EVIDENCE`; the series stops, and Julia gets the
measured pace.

**Forecast:** ≈ 5 h 30 min of runs once the Mac is idle, ≈ 6 h 15 min with the idle waits,
reads and copies between them. A run's first question ≈ 480 s with PyTorch — its cold first
call ≈ 90–180 s and the answer — and ≈ 350 s with INT8, no more than its later ones; a later one
≈ 400 s with PyTorch (step 1's four in arm A, a median 383 s) and ≈ 350 s with INT8. A run
≈ 44 min with PyTorch and ≈ 38 min with INT8, the API's start with the reranker's load in it
and the preload ≈ 1.3 min each; the reads, the after-run line and the copies ≈ 5 min a run.

## The copy

**`live_supervisor.py`,** step 1's copy `reports/stage4-step1/tools/live_supervisor.py`
(`915ffa9e…`), with marked changes only: a block between `# stage4-step5a-live: begin` and
`# stage4-step5a-live: end`, or a line ending in `# stage4-step5a-live`; the test checks that the
unmarked lines are step 1's copy's, line for line, but for the two it replaces. Two deployment
settings join `RAG_DEVICE` and `RAG_RETRIEVAL_TOP_K`, passed to the API as the others are:
`RAG_RERANKER_RUNTIME`, `torch` or `onnx`, and `RAG_RERANKER_ONNX`, an absolute path to a file
under the Mac user's home, with `onnx` and only with it, checked as `CHROMA` and `CASES_FILE` are.
The lines replaced are step 1's `DEPLOYMENT` and `TARGET_PATHS`. Without the two names it writes
and runs as step 1's copy. The runner and step 1's reader are not copied: they run unchanged.

## Records

`reports/stage4-step5a-live/81cd2ad/`: `live5a.json` (the eight runs, the pairs, the stand gate
and the readings), each run's own read (`<L>.live5a.json`, the gates'), the two first-question
reads (`s5a-torch-1.q1.live5a.json` and `s5a-int8-1.q1.live5a.json`), the eight
`.samples.jsonl`, `environment.jsonl`, `after-runs.txt` and `hf.txt`: numbers, enums, ids, model
names, the paths named here and SHA-256 strings, never a question, answer, prompt, source name,
log line, command line or environment, and of an error its type alone. The run directories stay
on the Mac; the record names their files by SHA-256. The series is no slice by the acceptance
rule (no behaviour, case or quality number changes); its record gets a row in
[`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md) and a test that reads it again. The tools and
their test are committed with this spec, and the test checks each SHA-256 below, the drivers'
and step 1's reader's too; a later change is a marked error fix that updates this list:

- `reports/stage2/tools/live_api.py` `43ff96f06af18538a2571d68a86e898ecfcdd5fcab47039f0d58bd245361a7b5`
- `reports/stage4-step0/tools/step0_sampler.py` `a0b3e53d78584f454d252770898efb884b77aa80f0fff1729992ec1a37c6d18c`
- `reports/stage4-step1/tools/live_runner.py` `c87838014a0517d5e6a3dde0402ed0b067a9e0148aaf5d842ffe272ca451a072`
- `reports/stage4-step1/tools/live_supervisor.py` `915ffa9e22e3165f56cd54194fe20e89c8e4146f5a10170f32094a03138fe536`
- `reports/stage4-step1/tools/step1_reader.py` `38f0abfe20143085ad593b361377ee09f5a59d30ca0c3ed69a75863ec288ea3b`
- `reports/stage4-step5a-live/tools/live5a_reader.py` `7420673c65c97b05d9ecf6df18eea4062e1df66b8ba4d49bafa05565d0bfea2b`
- `reports/stage4-step5a-live/tools/live_supervisor.py` `e903a1498aa1d48fb7ef6a9ba8cd2e4bd94e866433420fb132a6ab7179bd8e59`
- `reports/stage4-step5a-live/tools/raise_stand.sh` `6489520719823bc94bbd6c71e6e24718933025c13bf10aef3fca6c6305a5c110`
- `tests/test_stage4_step5a_live_tools.py` `2a5f4e879bd7a7b6839aa68295eff4f001a1c72e848d19fbfbe9e927dda17bf3`

## Not said

- Twenty pairs of five questions of one corpus, one stand, one day, on a Mac other projects
  share: whether INT8's rerank is faster in the chat beside the resident model at K = 20, not
  the product's speed (item 7) nor a 30-question series.
- **Whether INT8 enters the path:** her word (PLAN.md §9). Its five differs from PyTorch's on 307
  of item 5a's 400, so adopting it re-answers item 6 and stage 5; this series reads seconds, not
  answers.
- **Memory:** step 0's sampler reads `llama-server`'s processes and the whole Mac, not the API's
  process, so the reranker's own footprint in the chat is not read; `vm_stat` and the swap are
  the whole Mac's.
- **The cold start:** the load and the warm-up's seconds are printed, not compared; what a fresh
  process pays for its load and its first rerank stays item 5a's idle reading.
- **The file's pages:** the reads between runs hash the 571-MB file, so the next run may find it
  in the page cache; its load falls in the API's start, printed, not paired.
- **The noise:** a question's two asks are one run apart, ≈ 40 min; ABBA evens a steady drift
  across the blocks, not a jump. The block rule keeps one run's state from carrying a reading;
  the after-run line, the `llama` gate and the samples' load show a foreign job at a run's end,
  beside the model or in the load, not every one; the power above assumes independent pairs,
  which the stretches deny in part.
