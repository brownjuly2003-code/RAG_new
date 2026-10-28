# Stage 4, step 0: the 4B's prompt cache, memory and reused prefix, before any lever

Status 2026-10-28: **registered before the first request**, with the sampler and the reader that
read it and their test ([Records](#records)). **Read 2026-10-28** in two runs, run 1's gate
passed: [the record](../evidence/stage4-step0-record.md). [`PLAN.md`](../../PLAN.md) stage 4, item 0
(«Диагностика до рычагов», ≈ 1 h, changing nothing: the amendment of 2026-10-26); the [research
analysis](../operations/research-2026-10-25/analysis.md#item-5a--speed-research-6--and-what-our-log-and-arithmetic-add),
step 0. The one value filled in at launch is `<c>`, the commit that registers this spec.

## Why

Stage 4's levers rest on three questions and the model load's lines. **Q1:** does llama-server's
host prompt cache grow by ≈ 300 MiB a request, and is it the 4B process's +312 MB a request
(PLAN.md §3)? Ollama 0.33.2 starts llama-server with one slot, no mmap (`--load-mode none`) and
no `--cache-ram`, so the cache may hold up to llama.cpp's default 8,192 MiB on this 8-GB Mac (9
prompts, 1,826 → 2,098 MiB, in the [handoff of 2026-10-25](../operations/session-handoff-2026-10-25-stage3-signals-running.md#what-the-macs-log-shows));
item 5's first candidate, `--cache-ram`, rests on Q1. **Q2:** does generation wait on memory? It
runs at 4.3–4.7 tokens/s, about half of what this i5-7500's dual-channel DDR4-2400 allows.
**Q3:** does an answer reuse its ≈ 140 tokens before the documents? They are worth ≤ ≈ 4 s, so
«instructions in cache» is a lever only if step 0 shows more. **At the load:** the CPU backend
(`libggml-cpu-*`) and whether the weights are repacked, which item 5a measures only if not.

## The stand

- **Code:** V4's and V5's stand, `S=/Users/julia/RAG_new_chat_4f48fed`, `CODE_SHA`
  `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1`, its `chatlive/` drivers V4's by the `tools_sha256`
  of [its record](../../reports/answer-prompt-v4/4f48fed/v4-aircargo.json). No file the API runs
  has changed since: beyond docs, tests, reports and root `.md` files, `git diff --name-only
  4f48fed 6ce7a77` names only `static/`, two offline scripts and the requirements files. Each run
  starts a fresh API, database and llama-server process (its cache empty, the load timed apart),
  asks through `/api/ask/stream` and unloads the model.
- **Configuration:** mode `prod`, the code defaults (the 3,600-s ceiling since `468224b`,
  `RAG_DEVICE=cpu`), tenant `aircargo`, the questions `$S/evaluation/curated_cases_aircargo.jsonl`
  (`3737d694…`); a byte-identical copy of the second generation's index, made before a run and
  removed after it as in stage 2, with V4's corpus files (`corpus.manifest.json` `2b2e9232…`,
  `chunks-report.json` `bf01530e…`, `index/index-receipt.json` `2dcc80e7…`); the supervisor's
  default model, `qwen3:4b-instruct-2507-q4_K_M` (`0edcdef34593…`), on the CPU, never a fake one.
- **Interpreter:** `PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python` (3.11); the tools need
  its standard library only. V4's `stand_env.py` writes a line before run 1 and after run 2; both
  must name Ollama 0.33.2 and one start of its server, or step 0 is `NOT_EVIDENCE`.

## The questions

aircargo's registered order (`reports/stage2/tools/stage2_cases.py aircargo`, the file order), its
first five: the product's corpus, each timed in V4's batch 1. One question first, the rest after
it is read: run `s0-first` asks `aircargo-probation-data`, run `s0-rest`
`aircargo-probation-extend,aircargo-probation-dismissal,aircargo-dismissal-check,aircargo-dismissal-lawyer`.
Five is PLAN's upper bound; Q3 needs later answers in one process, and run 2 holds three. By V4's
routes (`human`: the answer and the self-evaluation; `auto`: the suggestions too), 14 requests.

## What is read

**Every 5 s** (`step0_sampler.py`, the handoff's `vm_stat 5`): UTC and `time.monotonic()` (the
clock of `stages.jsonl`), the log's byte size, `vm_stat`'s page size and counters, `vm.swapusage`,
`vm.loadavg`, and for each process whose executable is named `llama-server` its pid, RSS (`ps`),
footprint and compressed size (`top`'s MEM and CMPRS); never a process's arguments or environment.

**Per request** (`step0_reader.py`, the log between a run's first and last sample): its cache
lines (common prefixes, states saved and removed, the `cache state`), first `cached n_tokens`,
`print_timing` and release; from the samples, its counters' change and peaks, the footprint after
its cache state, and the samples surely inside its prompt and its generation (generation ends as
its summary is printed, between samples *b* and *a*, so it ran at least from *a* − its eval time
to *b*); from `stages.jsonl`, its call (answer, self-evaluation, suggestions, other) and case.
**At a load:** build, `system_info`, backend file, load mode, buffers. A shape not found leaves
null and a note, never a guess. What no reading below uses is printed and decides nothing.

## How it is read — frozen before the first request

By `step0_reader.readings`, both runs pooled:

- **Q1 yes** when the `cache state` grows by at least 200 MiB a request (per process from its
  first cache-state line to its last, pooled as the growths' sum over the requests') across
  at least three requests, and llama-server's footprint grows by 0.75 to 1.25 of the cache's
  growth between the same lines (the first and last with a prompt cached and a footprint read);
  **no** when it grows less or the footprint falls outside; `NOT_EVIDENCE` with fewer requests,
  or growth enough and no footprint. 200 MiB is about two thirds of 312 MB; the band spares a
  quarter for other allocations; the footprint, unlike RSS, counts compressed and swapped pages.
- **Q2 yes** when the pages brought back in a generation window (`vm_stat`'s page-ins plus
  decompressions, × its page size) per generated token (the window's seconds × the request's
  tokens per second) have a median of at least 25 MiB a generated token over
  at least two generation windows; **no** below; `NOT_EVIDENCE` with fewer. (mine) 25 MiB is 1 %
  of the ≈ 2.5 GB a token reads ([research](../operations/research-2026-10-25/README.md)): read
  back at an assumed 1–2 GB/s, ≈ 12–25 ms of a token's ≈ 220 ms.
- **Q3 yes** when the later answers, each after the first of its process, reuse a median of
  100 tokens or more (the first `cached n_tokens`) over at least two later answers; **no** below.
  **Its lever yes** when the median saving of the best reuse at hand — (the longer of the slot's
  and the best cached prompt's common prefix − the tokens reused) × the prompt's milliseconds a
  token — is at least 4,000 ms; **no** below. Both `NOT_EVIDENCE` with fewer readable later
  answers. 100 tokens are most of the ≈ 140 before the documents; 4,000 ms is PLAN's ≤ ≈ 4 s.
- **Repacking on** when a model buffer is `CPU_REPACK` (`CPU_AARCH64`, its older name), **off**
  when every model buffer is `CPU` or `CPU_Mapped`, else `NOT_EVIDENCE`; only off opens item 5a's.

**Forecast, written before the first request:** Q1 yes (the log's tail read on 2026-10-28 held 21
prompts, 7,856.5 MiB of the 8,192-MiB limit, ≈ 374 MiB a prompt); Q2 no; Q3 no (that tail reused
48 and 78 tokens) and its lever no; the backend `haswell` (mine: the i5-7500 has AVX2, not
AVX-512) and the repacking on (llama.cpp's `ggml-cpu/repack.cpp` repacks Q4_K given AVX2).

## Running it

On the Mac, with `S` and `PY` above: `CL=$S/chatlive`, `T=$S/step0`,
`LOG=/Users/julia/gr2_bench/ollama_serve.log`, `IX=/Users/julia/RAG_new_external_s1/aircargo`. A
run starts detached, so ssh returns at once (`;`, never `&&`, before `nohup`, as in stage 2).

1. **Tools:** `mkdir -p $T $CL/runs`; from the laptop, for each `<f>`, `git -C D:/RAG_new show
   <c>:reports/stage4-step0/tools/<f> | ssh deproject-mac "cat > /Users/julia/RAG_new_chat_4f48fed/step0/<f>"`;
   then `shasum -a 256 $T/step0_*.py` prints the list below.
2. **Idle, before each run:** the 5-minute load (`sysctl -n vm.loadavg`, its second number) below
   2; `pgrep -f "[p]ytest|[l]lama-server|[_]supervisor|[r]eplay\.py|[s]tep0_|[l]imactl"` finds no
   pytest, model, supervisor, replay, sampler or CI VM (the brackets keep it off its own shell);
   `/api/ps` is `{"models":[]}`; no `$HOME/ci_local/.lock_ci-local`. Else wait; nothing is stopped.
3. **Environment:** `$PY $S/reports/answer-prompt-v4/tools/stand_env.py >> $T/environment.jsonl`
   before run 1 and after run 2.
4. **A run,** as `stage2.sh` runs one, its sampler first: `L=s0-first`, `Q` its id, `M=1800`; then
   `L=s0-rest`, `Q` its four ids, `M=5400` (each `--max-sec` past its run's 3× below):

       cp -Rp $IX/index/chroma $CL/runs/$L.chroma; diff -rq $IX/index/chroma $CL/runs/$L.chroma && echo same
       nohup $PY -I $T/step0_sampler.py $T/$L.samples.jsonl --max-sec $M > $T/$L.sampler.err 2>&1 </dev/null & sleep 6; LIVE_VARIANTS=cpu nohup $PY -u $CL/live_supervisor.py $L prod $Q 1020/1200 TENANT=aircargo,CHROMA=$CL/runs/$L.chroma,CASES_FILE=$S/evaluation/curated_cases_aircargo.jsonl >> $CL/runs/$L.supervisor.log 2>&1 </dev/null &

   When `$CL/runs/$L.supervisor.log` ends on a `LIVE_DONE` line: `sleep 10; touch $T/$L.samples.jsonl.stop;
   rm -rf $CL/runs/$L.chroma; sleep 3; $PY -I $T/step0_reader.py $T/$L.step0.json $LOG --part
   $T/$L.samples.jsonl $CL/runs/$L`.
5. **Run 1's gate,** in `s0-first.step0.json`, before run 2: (i) `launch` has `code_sha`
   `4f48fed5…` and status `complete`, `drivers_sha256` V4's three; (ii) `joined`: `calls` =
   `matched` = `requests`; (iii) each request `complete` with `cached_tokens`, `prompt_ms`,
   `eval_ms` and `total_ms`, and a cache state after the first; (iv) `pid` read, and no sample note
   but `ps: no process named llama-server`; the load lines are printed, not gated. A failed point
   is a shape the tools did not know: a marked error fix (the change, its test, the new SHA-256,
   one commit), then run 1 is read again, or run again as `s0-first-r2` where its files cannot
   give the point back. A second failure: `NOT_EVIDENCE`.
6. **The record,** after run 2's environment line: `$PY -I $T/step0_reader.py $T/step0.json $LOG
   --part $T/s0-first.samples.jsonl $CL/runs/s0-first --part $T/s0-rest.samples.jsonl
   $CL/runs/s0-rest --corpus $IX`; its files are copied to the laptop as bytes.

**Stops.** A question past its cap (1,020 s for a run's first, 1,200 s for the others: 3× stage
2's forecasts of 340 and 400 s) stops its run; the supervisor stops the API and the database and
unloads the model. A run without `LIVE_DONE` at 3× its forecast (23 min for run 1, 61 for run 2)
is stopped as stage 2 stops a part, `pkill -f "[R]AG_new_chat_4f48fed/chatlive/live_runner.py"`,
and closed as step 4 closes a run. Its unread questions are `NOT_EVIDENCE`; step 0 stops, and
Julia gets the measured pace.

**Forecast:** ≈ 40 min of the Mac, within PLAN's ≈ 1 h, once it is idle. Run 1 ≈ 7.6 min (V4's
batch 1: the API's 30 s, the model's 51.0-s load, the question's 374.9 s); run 2 ≈ 20.4 min (the
same 81 s, its four's 1,145.5 s); checks, environment lines, copies and reads ≈ 10 min.

## Records

`reports/stage4-step0/4f48fed/`: `step0.json` (both runs, the readings), each run's own read
(`s0-first.step0.json` is the gate's), the two `.samples.jsonl` and `environment.jsonl`: numbers,
enums, ids, the paths named here and SHA-256 strings, never a log line, prompt, question, answer,
command line or environment. The log stays on the Mac; the record names each slice by its bytes
and SHA-256. Step 0 is no slice by the acceptance rule (no behaviour, case or quality number
changes); its record gets a row in [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md) and a test that
reads it again. The tools and their test are committed with this spec, each SHA-256 below checked
by the test; a later change is a marked error fix that updates this list:

- `reports/stage4-step0/tools/step0_reader.py` `2bdca7e9288b41857651d1a91ec823c2437d7ed8b6305da183148dc3df95e978`
- `reports/stage4-step0/tools/step0_sampler.py` `a0b3e53d78584f454d252770898efb884b77aa80f0fff1729992ec1a37c6d18c`
- `tests/test_stage4_step0_tools.py` `c30676c3e4e278e4509bad3e3547c290a4b53753accd7303c6b668cebaaa2218`

**Error fix after run 1** (2026-10-28, its gate passed on all four points): this llama-server
prints its build and `system_info` lines after common's tag, `cmn  common_param: `, the build as
`common_params_print_info: build N (commit)`, and no `load_backend` line, so run 1's read left
both null with a note. The reader now reads both shapes (`step0_reader.py` was `655d7c22…b8b5ed`,
the test `744aab32…4008fd`); no reading's rule or threshold changed, and the gate does not read
the load lines. Run 1's gate file stays as it was read; step 6's record is read by the fixed reader.

## Not said

- Five questions of one corpus, one draw, one stand: what the server does, not the product's speed
  (item 7) nor whether a 30-question series swaps (item 5). No lever is tried; nothing on quality.
- `vm_stat` and swap are the whole Mac's: a fault is the generation's by its time, not by its
  process. The footprint is `top`'s MEM as macOS counts it. The shapes of `vm_stat`, `sysctl`,
  `ps` and `top` follow macOS 13, unread on this Mac before run 1; its gate reads them.
- The sampler's own cost is not measured; a generation under about 10 s holds fewer than two
  samples and gives no window. Q2's no would not say why generation runs at half memory speed.
