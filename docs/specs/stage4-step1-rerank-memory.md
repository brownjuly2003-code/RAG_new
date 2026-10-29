# Stage 4, step 1: where the rerank's 102 s go — the retrieval beside the resident model and without it

Status 2026-10-28: **registered before the first request**, with the two driver copies, the reader
and their test ([Records](#records)). **Read 2026-10-28** in two runs, both gates passed:
[the record](../evidence/stage4-step1-record.md). [`PLAN.md`](../../PLAN.md) stage 4, item 1 («Куда уходят
102 с реранка», ≈ 1 h): «проверка гипотезы о борьбе за память — сравнить порядок «реранк, затем
загрузка модели» с нынешним». It follows [step 0](stage4-step0-diagnostics.md) and
[its record](../evidence/stage4-step0-record.md), on the same stand, with step 0's sampler, idle
rule and stop rule. The one value filled in at launch is `<c>`, the commit that registers this
spec.

## Why

- **The 102 s:** in the 30-question record on the idle Mac
  ([`reports/chat-live-4b/19beeb1/`](../../reports/chat-live-4b/19beeb1/), PLAN.md §3) the search
  took 134 s of a question's median 320 s, and the rerank 102 s of it. With no model loaded the
  same rerank takes about a quarter of that: stage 2's retrieval-only series
  ([`p2-aircargo`](../../reports/stage2/retrieval-20261021/p2-aircargo.json), code `5e308fe`) had
  a median of 26.71 s after its first question. Question by question it took a median 0.346 of
  the rerank seconds of V4's series on this stand
  ([V4's cases](../../reports/answer-prompt-v4/4f48fed/v4-aircargo.cases.jsonl), the model
  resident), and its vector search 0.2 s against V4's 4.8–22.6 s for the four questions below.
- **The hypothesis,** PLAN's: the API's process with its two encoders (the retrieval-only series
  peaked at 4,439 MB of RSS) and llama-server with the 4B (3,049 MiB at step 0's first answer,
  then ≈ 281 MiB more a request by step 0's Q1) do not fit beside macOS in the Mac's 8 GB, and the
  rerank waits for its pages. By step 0's last sample with the model, 2,583 MiB of llama-server's
  6,162-MiB footprint sat in the compressor, and the swap had risen from 1,837 to 4,654 MiB; its
  record says: «The API's two encoders compete for that memory (mine), and step 1 measures it.»
- **The comparison:** today's order loads the model once and keeps it resident. PLAN's other
  order, «реранк, затем загрузка модели», runs the retrieval with no model and loads it for the
  answer. If the rerank's lost time is the memory's, it falls to half or less without the model;
  the whole question's seconds then say whether the load the answer pays leaves it faster.

## The stand

- **Code:** V4's and step 0's stand, `S=/Users/julia/RAG_new_chat_4f48fed`, `CODE_SHA`
  `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1`. The drivers run from `T=$S/step1`: V4's
  `live_api.py`, copied from `$S/chatlive` and checked by V4's SHA-256 (its file here is
  `reports/stage2/tools/live_api.py`), and this step's two copies of V4's supervisor and runner
  ([The copies](#the-copies)). Each run starts a fresh API, database and llama-server process,
  asks through `/api/ask/stream` and unloads the model, as step 0's did.
- **Configuration:** mode `prod`, the code defaults (K = 20 candidates, five kept,
  `RAG_DEVICE=cpu`, the 3,600-s ceiling since `468224b`), tenant `aircargo`, the questions
  `$S/evaluation/curated_cases_aircargo.jsonl` (`3737d694…`); a byte-identical copy of the second
  generation's index for each run, removed after it, with V4's corpus files
  (`corpus.manifest.json` `2b2e9232…`, `chunks-report.json` `bf01530e…`,
  `index/index-receipt.json` `2dcc80e7…`); the supervisor's default model,
  `qwen3:4b-instruct-2507-q4_K_M` (`0edcdef34593…`), on the CPU, never a fake one.
- **Interpreter:** `PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python` (3.11); the tools need
  its standard library only. V4's `stand_env.py` writes a line before run 1 and after run 2; both
  must name Ollama 0.33.2 and one and the same start of its server, or step 1 is `NOT_EVIDENCE`.

## The arms and the questions

- **A, today's order:** the model stays resident. The supervisor loads it before the first
  question, as in V4. Before each A question the runner sends that load request again
  (`keep_alive` 30 min): on a resident model it loads nothing and renews the keep-alive, so the
  model outlives any retrieval. The product's calls send no `keep_alive`
  (`llm/providers/ollama.py`), and Ollama's own default could unload it inside a long one.
- **B, «реранк, затем загрузка модели»:** before each B question the runner unloads the served
  model (`keep_alive` 0) and reads `/api/ps` and `ps` every 0.5 s until Ollama holds no model and
  no `llama-server` process is listed, for at most 120 s. The retrieval then runs with no model,
  and the answer's call loads it. Another model is never unloaded; Ollama holding one stops the
  run.
- **The questions:** aircargo's registered order
  (`reports/stage2/tools/stage2_cases.py aircargo`, the file order) after step 0's five:
  `aircargo-dismissal-order`, `aircargo-leave-sources`, `aircargo-leave-compensation`,
  `aircargo-leave-risk`. V4 timed each in its batch 1, at positions 6–9: rerank 56.7–68.1 s,
  retrieval 61.9–90.9 s, the question 214.5–237.3 s. The retrieval-only series reranked them in
  19.7–31.1 s.
- **Two runs, the same four in the same order:** run `s1-baba` with the arms BABA, run `s1-abab`
  with ABAB. Each question is asked once in each arm, at the same position, so its two asks share
  the API's cold start, which a run's first question pays; they make its pair. Each run holds both
  arms, so the shared Mac's drift between the runs falls on both.
- **What four pairs can show** (mine, resampling the 100 questions of V4's series, of stage 2's
  chat-path series [`p1-aircargo`](../../reports/stage2/retrieval-20261021/p1-aircargo.json) and
  of its retrieval-only one): p1's rerank seconds over V4's, the same arm in two series days apart
  (a median 1.09), are at most 0.5 for 17 % of the questions and their median of four for 3.9 %;
  retrieval alone over V4 (a median 0.346), for 71 % and 81 %. With three pairs, 7.8 % and 80 %.
  The median of four of p1's whole seconds less V4's lies within ±90 s of its centre at 95 %. So
  four pairs tell a halved rerank from day-to-day noise, and the net's sign only when it is well
  beyond 90 s.
- **What they cannot:** A's llama-server is young. Every B question unloads it, so at an A
  retrieval it holds at most one question's prompt cache beyond its load (≈ 0.7 GB by step 0),
  not the gigabytes of V4's long series: about what item 5's cache cap would keep.

## What is read

**Every 5 s,** step 0's sampler (`step0_sampler.py`, unchanged): UTC and `time.monotonic()` (the
clock of `stages.jsonl` and of the case files), the byte size of Ollama's serve log (its default,
`/Users/julia/gr2_bench/ollama_serve.log`: a missing one notes every sample and fails the run's
gate), `vm_stat`'s page size and counters, `vm.swapusage`, `vm.loadavg`, and for each process
whose executable is named `llama-server` its pid, RSS, footprint and compressed size; never a
process's arguments or environment.

**Per question** (an ask), by `step1_reader.py` from the files the drivers write:

- **from its case file** (`live_runner.py`): its position, the request's start on the monotonic
  clock, its total, first-token and result seconds, its tokens, route and HTTP status, whether it
  delivered an answer (the runner's own rule), and its arm's action: the arm, polls, seconds, the
  model names Ollama listed before and after, B's count of `llama-server` processes, an error's
  type;
- **from `stages.jsonl`** (`live_api.py`), start and end paired per stage and thread, each span
  given to the last question begun before it if it starts before that question's last event: the
  retrieval (`hybrid.get_relevant_documents_with_path`, with its path's kind, rerank status,
  candidates and `timings_ms`), its vector search (`hybrid._vector_search`), its rerank
  (`hybrid._rerank_scored_with_status`), the rerank's pool (`hybrid.rerank_pool`: the candidates'
  count and the SHA-256 of their `[source, chunk_index]` set), the retriever's build
  (`vectordb.manager.get_retriever`), the answer's call (`ollama.generate_stream`: its offset,
  seconds, first chunk and prompt estimate) and the other model calls (`ollama.generate`);
- **from the samples:** those taken inside its retrieval, its vector search and its rerank, their
  count, how many `ps` read and how many listed a `llama-server`, its pids, the counters' change
  from the first to the last, and the pages faulted back (page-ins plus decompressions) in MiB and
  MiB a second; at the rerank's start, the last sample's swap, free pages, compressor and
  `llama-server` footprint;
- **its whole seconds:** the action's seconds plus the question's total, so B pays its unload and
  its answer's load.

A shape not found leaves null and a note, never a guess. What no reading below uses is printed and
decides nothing.

## How it is read — frozen before the first request

By `step1_reader.readings`, over the pairs `step1_reader.pair_up` forms:

- **An ask is read** when it delivered an answer; it has one retrieval, one vector search and one
  rerank, each with a time and no error, and one rerank pool; the rerank succeeded
  (`reranker_ok`, rerank status `ok`); and its answer's call exists, without an error.
- **An ask's arm held** when its action is its arm's and ran without an error, and, for A, Ollama
  listed the served model alone before and after the action, and every sample inside the
  retrieval that `ps` read lists one and the same `llama-server`; for B, neither a model in Ollama
  nor a `llama-server` process outlasted the unload, and no sample inside the retrieval lists one.
  Either way, at least one sample inside the retrieval that `ps` read.
- **A pair** is a question's one ask in A and one in B. It is **readable** when both runs passed
  their gates, both asks are read and held their arms, they stand at the same position with the
  same candidates (the pool's SHA-256), and both have rerank and whole seconds. Otherwise the pair
  gives its reasons and no reading.
- **Contention yes** when the median, over the readable pairs, of B's rerank seconds over A's is
  at most 0.5, with at least three readable pairs; **no** above it; `NOT_EVIDENCE` with fewer. 0.5
  lies between the same arm in two series (a median 1.09) and retrieval alone (0.346): a false yes
  ≈ 4 % and a true one ≈ 81 % at four pairs, by the resampling above.
- **Net faster** when the median, over the readable pairs, of B's whole seconds less A's is
  below zero, with at least three readable pairs; **not faster** at zero or above; `NOT_EVIDENCE`
  with fewer. Faster keeps B as a lever candidate, no more; within 90 s of zero it is the sign
  alone.
- **Printed, deciding nothing:** per pair, and but for the swap as medians: the vector and
  retrieval ratios; B less A in the retrieval's seconds, the answer call's offset, the answer's
  first chunk (B's load and what its fresh process lacks, not told apart), the first token and the
  total; the first chunk and the pages faulted back inside the rerank in each arm; A's
  `llama-server` footprint and each arm's swap at the rerank's start; the actions' seconds. Per
  run, the preload's seconds and how many `llama-server` pids its samples saw.

**The run gate,** in each run's own read: (i) `launch`: `code_sha` `4f48fed5…`, status `complete`
with runner exit 0, mode `prod`, the default model, the run's registered arms and the four
questions; (ii) `settings`: K = 20, five kept and `cpu` in `effective_settings.json`; (iii)
`drivers`: V4's `live_api.py` and the two copies two levels above the run, and step 0's sampler
beside the reader, by the SHA-256 below; (iv) `asks`: the four in order, each read; (v)
`actions`: one for each, none failed; (vi) `samples`: step 0's schema, samples from before every
question's start to after its last event, and no sample note but `ps: no process named
llama-server`, `top: no row for pid …` and, in a sample one of whose `llama-server` processes the
next sample no longer lists (B's unload, a run's end), `top: failed`; (vii) `b_held`: at least one
B ask held its arm.

**Forecast, written before the first request:** contention **yes**, a median ratio ≈ 0.3–0.45:
retrieval alone took 0.35–0.55 of V4's rerank for these four, a median 0.43, and the shared Mac
ran step 0's questions 1.05–2.2× slower than V4's; A's young process may give part of that back.
Net **faster** at step 0's pace: its first question's retrieval took 317.3 s and its rerank 185.5 s
against V4's 166.1 and 93.3 s for the same question (the session's read of step 0's run 1 on the
Mac, not in its record). At V4's pace it would be a wash: B saves 31–61 s of these four's retrieval
and pays ≈ 48 s of load.

## Running it

On the Mac, with `S` and `PY` above: `CL=$S/chatlive`, `T=$S/step1`,
`IX=/Users/julia/RAG_new_external_s1/aircargo`,
`Q=aircargo-dismissal-order,aircargo-leave-sources,aircargo-leave-compensation,aircargo-leave-risk`.
A run starts detached, so ssh returns at once (`;`, never `&&`, before `nohup`, as in stage 2).

1. **Tools:** `mkdir -p $T/runs`; from the laptop, for each `<f>` of `step1_reader.py`,
   `live_runner.py` and `live_supervisor.py`, `git -C D:/RAG_new show
   <c>:reports/stage4-step1/tools/<f> | ssh deproject-mac "cat > /Users/julia/RAG_new_chat_4f48fed/step1/<f>"`,
   and `git -C D:/RAG_new show <c>:reports/stage4-step0/tools/step0_sampler.py | ssh deproject-mac
   "cat > /Users/julia/RAG_new_chat_4f48fed/step1/step0_sampler.py"`; on the Mac,
   `cp -p $CL/live_api.py $T/`; then `shasum -a 256 $T/*.py` prints the five of the list below.
2. **Idle, before each run,** step 0's rule: the 5-minute load (`sysctl -n vm.loadavg`, its
   second number) below 2; `pgrep -f "[p]ytest|[l]lama-server|[_]supervisor|[r]eplay\.py|[s]tep[01]_|[l]imactl"`
   finds no pytest, model, supervisor, replay, sampler or CI VM; `/api/ps` is `{"models":[]}`; no
   `$HOME/ci_local/.lock_ci-local`. Else wait; nothing is stopped.
3. **Environment:** `$PY $S/reports/answer-prompt-v4/tools/stand_env.py >> $T/environment.jsonl`
   before run 1 and after run 2.
4. **A run,** its sampler first, its `--max-sec` past the run's 3× below: `L=s1-baba A=BABA` for
   run 1, then `L=s1-abab A=ABAB`:

       cp -Rp $IX/index/chroma $T/runs/$L.chroma; diff -rq $IX/index/chroma $T/runs/$L.chroma && echo same
       nohup $PY -I $T/step0_sampler.py $T/$L.samples.jsonl --max-sec 6600 > $T/$L.sampler.err 2>&1 </dev/null & sleep 6; LIVE_VARIANTS=cpu nohup $PY -u $T/live_supervisor.py $L prod $Q 1965/1320 TENANT=aircargo,CHROMA=$T/runs/$L.chroma,CASES_FILE=$S/evaluation/curated_cases_aircargo.jsonl,ARM=$A >> $T/runs/$L.supervisor.log 2>&1 </dev/null &

5. **One question first:** when `$T/runs/s1-baba/progress.log` holds its first `CASE` line, while
   the run goes on, `$PY -I $T/step1_reader.py $T/s1-baba.q1.step1.json --run
   $T/s1-baba.samples.jsonl $T/runs/s1-baba`. Its one ask must be read with its arm, B, held;
   else run 1 is stopped as [Stops](#stops) says, and step 6's rule for a failed point applies.
6. **After a run's `LIVE_DONE`,** the last line of `$T/runs/$L.supervisor.log`: `sleep 10; touch
   $T/$L.samples.jsonl.stop; rm -rf $T/runs/$L.chroma; sleep 3; $PY -I $T/step1_reader.py
   $T/$L.step1.json --run $T/$L.samples.jsonl $T/runs/$L`. Its gate must pass before the next
   step. A failed point is a shape the tools did not know: a marked error fix (the change, its
   test, the new SHA-256, one commit), then the run is read again, or run again as `$L-r2` with its
   run's arms where its files cannot give the point back. A second failure: `NOT_EVIDENCE`.
7. **The record,** after run 2's environment line: `$PY -I $T/step1_reader.py $T/step1.json --run
   $T/s1-baba.samples.jsonl $T/runs/s1-baba --run $T/s1-abab.samples.jsonl $T/runs/s1-abab
   --corpus $IX`, a rerun read in its run's place, never beside it; its files are copied to the
   laptop as bytes.

### Stops

A question past its cap (1,965/1,320 s: 1,965 s for a run's first question, 1,320 s for the
others, 3× the forecasts below) stops its run; the supervisor stops the API and the database and
unloads the model. An arm's action that fails stops its run before its question (exit 6). A run
without `LIVE_DONE` at 3× its forecast (≈ 108 min) is stopped as stage 2 stops a part,
`pkill -f "[R]AG_new_chat_4f48fed/step1/live_runner.py"`, and closed as step 6 closes a run. Its
unread questions are `NOT_EVIDENCE`; step 1 stops, and Julia gets the measured pace.

**Forecast:** ≈ 1 h 20 min of the Mac once it is idle, over PLAN's ≈ 1 h; ≈ 50 min at V4's pace.
A run's first question ≈ 655 s (step 0's first took 651.9 s) and a later one ≈ 440 s (twice V4's
223.2-s median for these four; step 0's later four took a median 1.88× V4's), in either arm: B
pays ≈ 48 s of load (step 0's two, 41.4 and 54.3 s) and may save as much in its retrieval. A run
≈ 36 min: the questions ≈ 33 min, the API's start and the preload ≈ 1.3 min, B's two loads again
as a margin ≈ 1.6 min. Two runs ≈ 72 min; checks, environment lines, copies and reads ≈ 10 min.

## The copies

Each is V4's driver with marked changes only: a block between `# stage4-step1: begin` and
`# stage4-step1: end`, or a line ending in `# stage4-step1`. Its first block holds `# fmt: off`,
so the original's layout is kept, and the test checks that the unmarked lines are the original's,
line for line.

- **`live_supervisor.py`,** V4's `reports/stage1/tools/live_supervisor.py`:
  `RAG_RETRIEVAL_TOP_K` joins `RAG_DEVICE` as a deployment setting, 1 to 99, passed to the API as
  the other settings are, for step 3's K = 14 against 20; step 1 leaves it unset. `ARM=` takes one
  letter, A or B, a question, in mode `prod` or `floor`, and is kept in `launch.json` as `arm` for
  the runner. Two original lines are replaced, `DEPLOYMENT` and the check of the names a run
  takes. Without the two names it writes and runs as the original.
- **`live_runner.py`,** V4's `reports/stage1/tools/live_runner.py`: it reads `arm` and `model`
  from `launch.json`, one letter a question. Before each question, after its token and before its
  request, `arm_action` acts as [the arms](#the-arms-and-the-questions) say; the action goes into
  the case file as `arm_action`, and a failed one stops the series with exit code 6 before its
  question is asked. B's count of `llama-server` processes uses the sampler's own `ps` listing and
  its test of a name. No original line is replaced; without `arm` it runs as the original.

## Records

`reports/stage4-step1/4f48fed/`: `step1.json` (both runs, the pairs and the readings), each run's
own read (`s1-baba.step1.json` and `s1-abab.step1.json`, the gates'), the first question's read
(`s1-baba.q1.step1.json`), the two `.samples.jsonl` and `environment.jsonl`: numbers, enums, ids,
model names, the paths named here and SHA-256 strings, never a question, answer, prompt, source
name, log line, command line or environment, and of an error its type alone. The run directories
stay on the Mac; the record names their files by SHA-256. Step 1 is no slice by the acceptance rule
(no behaviour, case or quality number changes); its record gets a row in
[`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md) and a test that reads it again. The tools and their
test are committed with this spec, and the test checks each SHA-256 below, the originals', V4's
`live_api.py`'s and step 0's sampler's too; a later change is a marked error fix that updates this
list:

- `reports/stage1/tools/live_runner.py` `fd5f7d7b66e5be827cb1cbc23074d6b7955f64d18143a11a1f9cd4dbe9caf4d1`
- `reports/stage1/tools/live_supervisor.py` `32e5a40552b62c37ee1e3cc387ae01a453b7729adadd7b9f790d73bb1906138c`
- `reports/stage2/tools/live_api.py` `43ff96f06af18538a2571d68a86e898ecfcdd5fcab47039f0d58bd245361a7b5`
- `reports/stage4-step0/tools/step0_sampler.py` `a0b3e53d78584f454d252770898efb884b77aa80f0fff1729992ec1a37c6d18c`
- `reports/stage4-step1/tools/live_runner.py` `c87838014a0517d5e6a3dde0402ed0b067a9e0148aaf5d842ffe272ca451a072`
- `reports/stage4-step1/tools/live_supervisor.py` `915ffa9e22e3165f56cd54194fe20e89c8e4146f5a10170f32094a03138fe536`
- `reports/stage4-step1/tools/step1_reader.py` `38f0abfe20143085ad593b361377ee09f5a59d30ca0c3ed69a75863ec288ea3b`
- `tests/test_stage4_step1_tools.py` `fc7500b27b74542b5c0679594a3f08c8620a162f9177cfce66b7cabe0c37d9e4`

## Not said

- Four pairs of one corpus, one stand, one day, on a Mac other projects share: where the rerank's
  seconds go at A's footprint, not the product's speed (item 7) nor a 30-question series (item 5).
  No lever is adopted: a faster B is a candidate for item 5's unload policy (every request),
  measured there in its 30-question series first. K = 20 only; nothing on quality.
- A's llama-server is young (above): a yes says the resident model costs the rerank even so; a no
  does not clear V4's long series, whose footprint grew by gigabytes.
- B frees the weights and the prompt cache at once, and step 1 cannot tell their shares apart; nor
  which of the two encoders waits, beyond the vector search's and the rerank's own seconds.
- B's load is read as its answer's first chunk less A's: the load and whatever else a fresh
  process pays, not told apart; the cache it lacks gave A's answers 5 tokens each by step 0's Q3.
- `vm_stat` and swap are the whole Mac's: a fault is a window's by its time, not by its process. A
  retrieval under about 10 s holds fewer than two samples and gives no window.
- A question's two asks are ≈ 36 min apart, in two runs; the pace of a shared Mac can move between
  them, and four pairs average that only so far.
