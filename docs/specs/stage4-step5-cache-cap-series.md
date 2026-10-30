# Stage 4, item 5: thirty questions under a 1,024-MiB prompt cache — does the swap hold?

Status 2026-10-30: **registered before the first request**, with its reader and the reader's
test ([Records](#records)), in `<c>`. [`PLAN.md`](../../PLAN.md) stage 4, item 5: «Проверка — серия из 30
вопросов, своп не растёт (≈ 2,5 ч)», for the policy's first candidate, a limit on llama-server's
host prompt cache, under Julia's «да» of 29.10 to `cache-ram = 1024` (§8.1). The one value filled
in at launch is `<c>`, the commit that registers this spec.

## Why

- **Without a limit the swap climbs for a dozen questions.** The 4B's thirty-question rerun at
  `19beeb1` ([its record](../../reports/chat-live-4b/19beeb1/runs.json), the 4B's row in
  [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md)) asked these thirty questions, in this order, in
  one API and one llama-server process. The swap in use, as the record prints each question's
  lowest and highest, rose from 914.75–1,339.0 MB at question 1 to 9,329.5–10,918.75 MB at
  question 13. It stayed there to question 30, at 9,309.0–10,978.25 MB. llama-server reached an
  11-GB footprint on this 8-GB Mac.
- **Step 0 named the cause** ([its record](../evidence/stage4-step0-record.md)):
  - the host prompt cache grows 280.69 MiB a request and is llama-server's growth, ratio 1.0;
  - its limit is llama.cpp's default, 8,192 MiB;
  - no state was restored, so a limit takes away no reuse step 0 saw.

  An answer and a self-evaluation each leave 330–380 MiB, the suggestions 53–67 MiB: ≈ 770 MiB
  a question, so 8,192 MiB fill by about question 11 — near where the rerun's swap stopped
  rising (mine).
- **Under a 1,024-MiB limit** the cache is full during question 2 and holds at most 1,024 MiB
  from then on. If the cache is what fills the swap, the swap stops rising by then, and
  questions 6–10 read like questions 26–30.
- **The route:** Ollama 0.33.2 passes no `--cache-ram`. llama.cpp b10630 reads
  `/etc/llama.cpp/config.ini`, then `~/.config/llama.cpp/config.ini`, at each start
  (`common_params_apply_system_config`, `common/arg.cpp`, read 2026-10-29). A line before any
  section applies, an unknown key is skipped, and the command line and the environment win over
  the file. While the line stands it reaches every llama.cpp program of the user, so it stands
  for this series only. The other route, `LLAMA_ARG_CACHE_RAM` in `ollama serve`'s environment,
  needs `ollama serve` restarted and is not taken.

## The stand

- **Code:** step 0's stand ([its spec](stage4-step0-diagnostics.md#the-stand)),
  `S=/Users/julia/RAG_new_chat_4f48fed`, `CODE_SHA` `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1`.
  Its four `chatlive/` drivers are checked by the SHA-256 step 0's runs read (the reader's
  `DRIVERS_SHA256`, read again on the Mac 2026-10-29). The API's code since adds the
  self-evaluation's continuation, off by default (`57420db`), the hints after the result
  (`43874fc`) and the session store's breaker (`3f7b33d`). None changes what llama-server is sent
  or keeps (mine); the stand keeps the series beside step 0's reading.
- **One process for the thirty:** a fresh API, database and llama-server, the cache empty, the
  model loaded by the supervisor and unloaded at its end.
- **Configuration:** step 0's. Mode `prod`, the code defaults (the 3,600-s ceiling since
  `468224b`, `RAG_DEVICE=cpu`), tenant `aircargo`, the questions
  `$S/evaluation/curated_cases_aircargo.jsonl` (`3737d694…`). A byte-identical copy of the index,
  made before the run and removed after it; the corpus files named by SHA-256 in the record. The
  supervisor's default model, `qwen3:4b-instruct-2507-q4_K_M` (`0edcdef34593…`), on the CPU, never
  a fake one. Ollama 0.33.2 as it runs, not restarted.
- **The one change:** the line `cache-ram = 1024` in `~/.config/llama.cpp/config.ini`, written
  before the run and removed after it ([Running it](#running-it)).
- **Interpreter:** `PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python` (3.11); the tools need
  its standard library only. V4's `stand_env.py` writes a line before the run and after it; both
  must name Ollama 0.33.2 and one start of its server, or the series is `NOT_EVIDENCE`.

## The questions

aircargo's registered order, its first thirty (`step5_reader.CASES`, from
`aircargo-probation-data` to `aircargo-road-seal`): the thirty of `19beeb1`'s rerun, in its order.
One run, `s5-30`. By V4's routes (`aircargo-probation-extend` `human`, the others `auto`), 89
requests: an answer and a self-evaluation each, and the suggestions of the 29 `auto`.

## What is read

**Every 10 s,** step 0's sampler, unchanged: UTC and `time.monotonic()` (the clock of
`stages.jsonl`), the log's byte size, `vm_stat`'s counters, `vm.swapusage`, `vm.loadavg`, and for
each process named `llama-server` its pid, RSS and footprint (`top`'s MEM).

**Every 3 s,** the supervisor's own `resources.jsonl`, as in every chat-live run: the processes
whose path names python, ollama, postgres or llama, and the five largest. The reader keeps the
API's RSS, by the pid in `launch.json`, and the names the disturbance below needs. The file stays
on the Mac.

**Per request,** step 0's reader, by the SHA-256 its spec lists: the cache's lines — the `cache
state` with its limit, the entries removed and their sizes, a save skipped, a limit reduced — and
the request's call and case.

**Per question,** `step5_reader.py`: its window, from its start to its end on the monotonic
clock. Inside it, the medians of the swap in use, of llama-server's footprint, of the API's RSS
and of the 5-minute load; its requests, and the cache as its last request arrived (llama-server
prints the cache's state as a request takes the slot).

## How it is read — frozen before the first request

- **The gate** passes when all of these hold:
  - `launch.json` names `CODE_SHA`, status `complete`, runner exit 0, the thirty in their order,
    the model and its digest, and no model in Ollama before; the four drivers are V4's; the API's
    pid is read;
  - the thirty questions are read in their order, none with a client error, each with a sample
    inside its window, and the sampler saw llama-server in them;
  - `joined`: `calls` = `matched` = `requests`, one log request a model call;
  - every complete request has a cache-state line;
  - **the limit is in force:** every cache-state line prints 1,024 MiB, no limit was reduced, and
    the cache never held more than 1,024 MiB.

  A failed point that is a shape the tools did not know is a marked error fix — the change, its
  test, the new SHA-256, one commit — and the series is read again from its files. Any other
  failure leaves the series `NOT_EVIDENCE`.
- **Disturbed,** from the first question's start to the last one's end, when:
  - the sampler saw more than one llama-server pid;
  - a Python process other than the API held 512 MiB or more, in the supervisor's list or among
    the five largest (a path with a capital `Python` alone misses the list);
  - a process whose name holds `qemu`, `limactl` or `virtualization` (any case) was among the
    five largest.

  None of the three fired in the 34 earlier runs of this stand (step 0's two, V4's thirty, the
  widget's two), read on the Mac 2026-10-30; the API's RSS peaked at 1,732–2,794 MiB there. A
  disturbed series is kept and named, not read.
- **The reading, «своп не растёт»:** the growth is the median over questions 26–30 of each
  question's median swap, less the same median over questions 6–10.
  - **holds** when the growth is below 512 MiB, a fall included;
  - **grows** at 512 MiB or more;
  - `NOT_EVIDENCE` when the gate failed, the series was disturbed, or a question of the two
    windows has no swap.

  Questions 1–5 hold the start: the load, and the cache filling to its limit. Five questions a
  window spare an outlier or two. 512 MiB is half the limit: under it the cache adds at most
  1,024 MiB in all, and it is full long before question 6. It is also below one question's
  growth at `19beeb1`, 600–700 MB. On the midpoints of that rerun's ranges, its questions 6–10
  (5,691.5 MB) and 26–30 (10,143.6 MB) give + 4,452 MB, so the rule reads that run as grows.
- **Printed, deciding nothing:**
  - the change of the footprint and of the API's RSS between the same windows;
  - the swap's slope a question from question 6 (least squares), its first and last samples and
    its highest inside the questions;
  - the cache's maximum, its removals and their size, the saves skipped;
  - the questions' seconds (median and sum), the 5-minute load's median;
  - the config file llama-server named at its start, if it names one.

**If it grows,** the footprint's and the API's change name the process that grew. The next
candidate is PLAN's other one, unloading every N requests or at a swap threshold; if it needs
`ollama serve` changed or restarted, that is Julia's word. **If it holds,** the limit enters the
product only by her word (§8.3), and the line, removed after the series, comes back only by her
word (§8.1).

**Forecast, written before the first request:** the gate passes, the series is not disturbed,
and the swap **holds**, its growth within ± 256 MiB. The cache holds at most 1,024 MiB from
question 2 on and removes entries from then. llama-server's footprint stays within ≈ 3,174–4,198
MiB: step 0's 3,174 MiB after the load, plus up to 1,024 MiB. The swap at questions 26–30 sits far
below `19beeb1`'s 9.3–11.0 GB (mine: below 5,000 MiB).

## Running it

On the Mac, with `S` and `PY` above: `CL=$S/chatlive`, `T=$S/step5`,
`LOG=/Users/julia/gr2_bench/ollama_serve.log`, `IX=/Users/julia/RAG_new_external_s1/aircargo`,
`C=/Users/julia/.config/llama.cpp`. The run starts detached, so ssh returns at once (`;`, never
`&&`, before `nohup`, as in stage 2). Nothing else is started on the Mac while it lasts: no test,
no sync.

1. **Tools:** `mkdir -p $T`; from the laptop, `git -C D:/RAG_new show
   <c>:reports/stage4-step5/tools/step5_reader.py | ssh deproject-mac "cat >
   /Users/julia/RAG_new_chat_4f48fed/step5/step5_reader.py"`, and the same from
   `reports/stage4-step0/tools/` for `step0_reader.py` and `step0_sampler.py`. Then `shasum -a 256
   $T/*.py` prints the reader's SHA-256 below and step 0's two in
   [its spec](stage4-step0-diagnostics.md#records).
2. **Idle,** as step 0: the 5-minute load below 2; `pgrep -f
   "[p]ytest|[l]lama-server|[_]supervisor|[r]eplay\.py|[s]tep[0-5]_|[l]imactl"` finds nothing;
   `/api/ps` is `{"models":[]}`; no `$HOME/ci_local/.lock_ci-local`; neither `/etc/llama.cpp` nor
   `$C` exists, nor `$CL/runs/s5-30` or `$T/s5-30.samples.jsonl`. Else wait; nothing is stopped.
3. **The limit,** in the ssh call whose idle check passed: `mkdir $C && printf 'cache-ram =
   1024\n' > $C/config.ini && shasum -a 256 $C/config.ini` prints
   `c75f44912ea2c7f54ea0cf0e9ffea8f05466ae447961d99c8f12d716589b4e6c`. If `$C` appeared since the
   check, `mkdir` fails and nothing is written. **The guard,** started detached in the same call
   right after the line, removes it — `rm $C/config.ini; rmdir $C`, only while the file's SHA-256
   is still the line's — at the first of: the supervisor's exit, by its pid in
   `$T/s5-30.supervisor.pid`, polled every 30 s, and 10 s more; no pid 5 min after the line; 8 h
   after the line. It writes the cause to `$T/s5-30.guard.log`. So the line goes if the laptop
   loses the run, or if the supervisor dies before `LIVE_DONE`. A failure in this call before the
   supervisor starts removes the line at once and stops the guard.
4. **Environment:** `$PY $S/reports/answer-prompt-v4/tools/stand_env.py >> $T/environment.jsonl`,
   before the run and after it.
5. **The run,** its sampler first, `L=s5-30`, `Q` the file's first thirty ids:

       Q=$(head -n 30 $S/evaluation/curated_cases_aircargo.jsonl | $PY -I -c 'import json, sys; print(",".join(json.loads(l)["case_id"] for l in sys.stdin))')
       cp -Rp $IX/index/chroma $CL/runs/$L.chroma; diff -rq $IX/index/chroma $CL/runs/$L.chroma && echo same
       nohup $PY -I $T/step0_sampler.py $T/$L.samples.jsonl --every 10 --max-sec 28800 > $T/$L.sampler.err 2>&1 </dev/null & sleep 12
       LIVE_VARIANTS=cpu nohup $PY -u $CL/live_supervisor.py $L prod $Q 1020/1200 TENANT=aircargo,CHROMA=$CL/runs/$L.chroma,CASES_FILE=$S/evaluation/curated_cases_aircargo.jsonl >> $CL/runs/$L.supervisor.log 2>&1 </dev/null & echo $! > $T/$L.supervisor.pid

   Each line runs only if the one before held: `Q` names thirty ids, `same` is printed, and the
   sampler is running with its first row 12 s after its start; else nothing more starts and the
   line goes at once. The gate holds `launch.json`'s list against the reader's thirty.
6. **One question first:** once `$CL/runs/s5-30/progress.log` has its `CASE 1` line, `$PY -I
   $T/step5_reader.py check $T/s5-30.samples.jsonl $LOG`. Exit 0, with `limits_mib` `[1024.0]`:
   the run goes on. Any other exit: the limit is not shown in force; the run is stopped as
   [Stops](#stops) stops it, and Julia gets what the check printed.
7. **At `LIVE_DONE`** in `$CL/runs/s5-30.supervisor.log`: `sleep 10; touch
   $T/s5-30.samples.jsonl.stop; rm -rf $CL/runs/s5-30.chroma`; `/api/ps` is `{"models":[]}`, the
   supervisor having unloaded the model.
8. **The line goes,** whatever the outcome: the guard has removed it, and its log names the
   cause; `ls $C` fails. If `$C` is still there, `rm $C/config.ini; rmdir $C`. Then the
   environment line.
9. **The record:** `$PY -I $T/step5_reader.py read $T/step5.json $LOG $T/s5-30.samples.jsonl
   $CL/runs/s5-30 --corpus $IX`. `step5.json`, the samples and `environment.jsonl` are copied to
   the laptop as bytes.

### Stops

- A question past its cap — 1,020 s for the first, 1,200 s for the others, as step 0 — stops the
  run; the supervisor stops the API and the database and unloads the model.
- No `LIVE_DONE` 7.5 h after the start, 3× the forecast: `pkill -f
  "[R]AG_new_chat_4f48fed/chatlive/live_runner.py"`, and the run is closed as step 0 closes one.
- The first question's check exits other than 0: the same `pkill`.
- The supervisor gone with no `LIVE_DONE`: steps 7 and 8 at once.

After a stop, steps 7 and 8 follow: the line goes. A stopped series is `NOT_EVIDENCE`, and Julia
gets the measured pace and the cause. A disturbed series is run once more as `s5-30-r2` (steps
2–9) once the Mac is idle; disturbed again, it is `NOT_EVIDENCE`.

**Forecast:** ≈ 2.5 h of the Mac once it is idle. The API's start and the model's load take
≈ 1.5 min. The thirty take ≈ 2.3–2.7 h: V4's took 8,428 s in three fresh processes, `19beeb1`'s
rerun 9,482 s in one without a limit. Checks, copies and the read take ≈ 10 min. The first
question's check comes ≈ 7 min after the start.

## Records

`reports/stage4-step5/4f48fed/`:
- `step5.json`: the series, its questions, its cache, its gate, its disturbance and its reading;
- `s5-30.samples.jsonl`;
- `environment.jsonl`.

Numbers, enums, ids, the paths named here, process names and SHA-256 strings: never a log line,
prompt, question, answer, command line or environment. The log and the supervisor's
`resources.jsonl` stay on the Mac; the record names the log's slice by its bytes and SHA-256, and
`resources.jsonl` by its SHA-256.

The series is no slice by the acceptance rule: no behaviour, case or quality number changes. Its
record gets a row in [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md), a capsule in
`docs/evidence/` and a test that reads it again.

`tests/test_stage4_step5_tools.py` reads a synthetic thirty-question run whole, in the shapes
step 0's reader reads and llama.cpp b10630 prints. It covers the gate, the limit, the
disturbance and the reading at its threshold. Step 0's reader and sampler are used as they are:
the reader refuses another step 0 reader by its SHA-256. The tool and its test are committed with
this spec, and the test checks each SHA-256 below; a later change is a marked error fix that
updates this list:

- `reports/stage4-step5/tools/step5_reader.py` `6e2a8b910d83a1b98d8dfc25f48d1150497583b8fa3edbf4a3860caa8c510d4f`
- `tests/test_stage4_step5_tools.py` `5fa653cc6cec7af6c562cdd33d700e270ae33758e075f8b1b9792e2d673e8ad4`

## Not said

- **One series, one corpus, one draw:** whether the swap holds under this limit on this Mac and
  stand. Not the product's speed (item 7), not quality, not whether the limit enters the product
  (§8.3).
- **The swap is the whole Mac's.** Whatever else runs shows in it; the disturbance names only
  another model, a large Python process and a virtual machine. macOS gives swap back slowly, so
  its level carries what ran before; the reading reads its growth, not its level.
- **The limit's cost.** Step 0 saw no state restored, so the limit removes no reuse it saw. The
  questions' seconds are printed, not tested: V4's and `19beeb1`'s paces differ in code and in
  processes.
- **The other route** (`LLAMA_ARG_CACHE_RAM`) and an unload every N requests are not tried.
