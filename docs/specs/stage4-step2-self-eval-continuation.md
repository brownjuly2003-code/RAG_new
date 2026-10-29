# Stage 4, step 2: the self-evaluation as the answer's next turn, beside the classic one

Status 2026-10-28: **registered before the first request**, with the supervisor's copy, the reader
and their test ([Records](#records)); **read 2026-10-29**, the rerun's gate passed, the candidate
the continuation: [the record](../evidence/stage4-step2-record.md).
[`PLAN.md`](../../PLAN.md) stage 4, item 2 («Самооценка
(68 с)»): «Если значок остаётся — опыт: самооценка как продолжение промпта ответа, чтобы его
≈ 2 300 токенов брались из кэша». Julia's word of 2026-10-28 on the badge «Качество: N»:
«Оставить, но ускорить». It follows [step 0](stage4-step0-diagnostics.md) and
[step 1](stage4-step1-rerank-memory.md), with step 0's idle rule, on a stand of its own, the commit
that holds the continuation's code ([The stand](#the-stand)). The one value filled in at launch is
`<g>`, the commit that registers this spec.
[Amendment 1](#amendment-1-2026-10-29-the-rerun-unloads-the-model-before-each-question),
2026-10-29, after `s2-both` stopped at its thirteenth question and before `s2-both-r2`'s first
request: the rerun unloads the model before each question.

## Why

- **The 68 s:** the stream's self-evaluation today, the classic, sends a prompt of its own: V3's
  rubric (`SELF_EVAL_PROMPT_V3`, `agent/prompts.py`), the question, the five documents and the
  answer. llama-server reads it from its start. By step 0's record it read 2,377–2,690 prompt
  tokens, kept 7 of them from its cache, spent 65.0–105.1 s reading them and wrote 3–4 tokens
  ([its table](../evidence/stage4-step0-record.md#per-request)). Its documents are the answer
  prompt's, read a minute before.
- **The continuation:** the same rubric as the conversation's next turn, one request to Ollama's
  `/api/chat` with three messages. The user's: the answer's prompt exactly as the answer's call
  sent it. The assistant's: the answer as it streamed. The user's: `SELF_EVAL_CONTINUATION_V1`,
  V3's four criteria (the answer's relevance, its accuracy against the context, the retrieval's
  quality, the answer's language) and its one-integer output, with no question, document or
  answer of its own. The model's template (Qwen3-4B-Instruct-2507) renders the first two as the
  answer's own text, an assistant turn with no think block. So llama-server can keep its slot's
  tokens — the prompt's ≈ 2,100–2,400 at least, and the answer's up to the first token its text
  splits otherwise than the model wrote it — and read only the instruction's ≈ 300 and the turn
  markers: ≈ 10–15 s at step 0's 28 ms a token, against the classic's 65–105 s.
- **What could break it:** a prefix that does not match (a path that sent another string, a
  template or an option that renders otherwise, a slot not kept, an answer holding `</think>`,
  which the template cuts); a score that moves because the
  model rates its own answer in its own conversation; a reply that is not one integer. Each has a
  reading or a stop below.

## The stand

- **Code:** `S=/Users/julia/RAG_new_chat_57420db`,
  `CODE_SHA` `57420db746e0510465bb5a08b7610e092b32e650`. It is V4's stand (`4f48fed`)
  with the commits since: the dependency locks (`b557082`, `727b6e9`; the stand runs V4's
  interpreter, not the locks), the handover's line under every answer (`60dfd90`), the session
  store's three failures (`3f7b33d`), stage 6's service drafts (`deploy/macos/`, unused here),
  and the continuation, `57420db` itself:
  - `config/settings.py`: `streaming_self_eval_mode`, from `STREAMING_SELF_EVAL_MODE`: `classic`
    (the default, the code before step 2), `continuation` or `both`;
  - `llm/providers/ollama.py`: `generate_chat`, one plain `/api/chat` request (below);
  - `agent/prompts.py`: `SELF_EVAL_CONTINUATION_V1`;
  - `api/routers/conversation.py`: the stream's self-evaluation by the mode.

  A pair compares two self-evaluations of one answer in one process, so none of the other commits
  stands between its two sides.
- **The continuation's request:** the same base URL and model as the answer's stream; `stream:
  false`, `think: false`; `num_ctx` exactly as the answer's call sent it, `num_predict` 128,
  temperature 0.0; no `format`, `system`, `tools`, `raw`, `template`, `suffix` or `context`;
  `keep_alive` only where the answer's call sent one; the provider's timeout
  (`OLLAMA_REQUEST_TIMEOUT_SEC`). Its first message depends on the path. The provider's stream sent
  `"USER:\n"` and the stripped prompt (`flatten_messages`), the raw fallback the prompt as posted.
  Each of these gives no score, and the code falls back to the classic:
  - an unknown path;
  - a window too small for the three messages and 128 tokens;
  - an HTTP error;
  - a reply whose stripped text is not one integer of 1–100 (`(\d{1,3})\.?`, whole).

  Ollama's counters (prompt and generated tokens and seconds, from nanoseconds) are kept.
- **Mode `both`, this step's:**
  - The continuation runs first. Its score drives the badge, the route and the suggestions; where
    it gave none, the classic's does, as the fallback.
  - The classic then runs on the same answer, as the code ran it before step 2: V3, the evaluate
    role, its parse unchanged.
  - The result event carries `self_eval_both`: each side's score (−1 for none), seconds and
    counters.
- **Configuration:**
  - mode `prod`, the code defaults (K = 20 candidates, five kept, `RAG_DEVICE=cpu`, the 3,600-s
    ceiling since `468224b`), `STREAMING_SELF_EVAL_MODE=both`;
  - tenant `aircargo`, the questions `$S/evaluation/curated_cases_aircargo.jsonl`;
  - a byte-identical copy of the second generation's index, removed after the run, with V4's corpus
    files;
  - the supervisor's default model, `qwen3:4b-instruct-2507-q4_K_M` (`0edcdef34593…`), on the CPU.

  The host prompt cache keeps its default limit and is not reset between questions: item 5's cap
  is Julia's word.
- **Interpreter:** `PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python` (3.11); the tools need
  its standard library only. V4's `stand_env.py` writes a line before the run and after it. Both
  must name Ollama 0.33.2 and one and the same start of its server, or step 2 is `NOT_EVIDENCE`.

## The questions and the run

- **The questions:** step 3's thirteen, in aircargo's registered order
  (`reports/stage2/tools/stage2_cases.py aircargo`): step 0's five, step 1's four, then
  `aircargo-matliab-check`, `aircargo-matliab-disputed`, `aircargo-templates-choose` and
  `aircargo-templates-checklist`.
- **One run, `s2-both`:** each question is asked once, and its two self-evaluations of its one
  answer make its pair. A rerun, `s2-both-r2`, stands in its place, never beside it.
- **What thirteen pairs can show:** the sign test decides at 11 of 13 (two-sided p = 0.0225; 10 of
  13 gives 0.092), at 10 of 11 and at 9 of 10. The forecast saving, ≈ 55–90 s a question, is far
  beyond any reading's noise. Routes and scores are read on the same thirteen, which is why they
  decide no default (step 2b below).

## What is read

**Every 3 s,** the supervisor's own samples (`resources.jsonl`): the swap used, the swap-outs and
each process's RSS by its name, never its arguments or environment.

**Per question** (an ask), by `step2_reader.py` from the files the drivers write:

- **from its case file** (`live_runner.py`): its position, the request's start on the monotonic
  clock, its total, first-token and result seconds, its tokens, route, quality and that quality's
  source, the HTTP status, whether it delivered an answer (the runner's own rule), and the
  result's `self_eval_both`;
- **from `stages.jsonl`** (`live_api.py`): the answer's stream (`ollama.generate_stream`: its
  offset, seconds, first chunk and prompt estimate) and the model calls after it
  (`ollama.generate`: the classic's by its 128-token limit, the suggestions' by 256);
- **from the samples** within it: the swap used at its start and end, its swap-outs and
  llama-server's largest RSS.

A shape not found leaves null and a note, never a guess. What no reading below uses is printed and
decides nothing.

## How it is read — frozen before the first request

By `step2_reader.readings`, over the pairs `step2_reader.pair_of` forms:

- **An ask is read** when it delivered an answer, streamed it in one call without an error, and
  its result holds both self-evaluations, each with a score (1–100, or −1 for none) and seconds.
- **The continuation held** when it scored 1–100 and the result's quality, that quality's source
  (`llm`) and its route are that score's (auto at 80 or more, else human).
- **A pair** is a read ask of a run whose gate passed; otherwise the pair gives its reasons and no
  reading.
  - Its cost is the continuation's seconds, with the classic's added where it did not hold, as the
    code then falls back to the classic.
  - Its saving is the classic's seconds less that cost.
  - Its routes are **compared** where the continuation held and the classic scored 1–100.
- **Speed:**
  - **faster** when the continuation saves on more pairs than it loses and the exact two-sided
    sign test, ties dropped, gives p < 0.05;
  - **slower** the other way;
  - **no difference** otherwise;
  - `NOT_EVIDENCE` without at least ten readable pairs.
- **Useful** at a median saving of at least 30 s over the readable pairs; **not useful** under it;
  `NOT_EVIDENCE` where speed is. 30 s is under half the classic's least seconds in step 0, 65.0 s.
  A continuation that saves less reads back most of what the cache should hold.
- **Routes agree** when at most one compared pair routes differently, and **differ** otherwise;
  `NOT_EVIDENCE` with fewer than ten compared pairs.
- **Scores held** when the continuation held on all but at most one readable pair, and **not
  held** otherwise; `NOT_EVIDENCE` without ten readable pairs.
- **The candidate:**
  - **continuation** when faster, useful, agreeing and held;
  - **classic** otherwise;
  - `NOT_EVIDENCE` when any of the four is.

  A candidate is no default, and the default stays `classic` until step 2b reads. Step 2b is the
  continuation re-scoring the 80 labelled answers of stage 3, the 17 bad ones first, beside the
  classic's 2 caught of 17 and 0 marked of 63 (S1 of
  [the handover signals' record](../evidence/handover-signal-v4-aircargo.md)). It is registered in
  its own spec before its first request, and it runs only if the candidate is the continuation.
- **Printed, deciding nothing:**
  - per pair: each side's score and counters; the answer's, the classic's and the suggestions'
    call seconds; the total and first-token seconds; the memory;
  - over the pairs: the total and the worst saving; the median cost and the median classic
    seconds; the score differences (median; higher, same, lower); each side's routes and median
    counters; the swap used at most, llama-server's largest RSS and the swap-outs.

**The run gate,** in the run's own read:

1. `launch`: `code_sha` `57420db746e0510465bb5a08b7610e092b32e650`; label `s2-both` or `s2-both-r2`;
   status `complete` with runner exit 0; mode `prod`; the default model; tenant `aircargo`; the
   thirteen questions; no model in Ollama before the preload; no arm, but for `s2-both-r2`
   step 1's arm `B` on each of the thirteen ([Amendment 1](#amendment-1-2026-10-29-the-rerun-unloads-the-model-before-each-question));
   `STREAMING_SELF_EVAL_MODE=both`; K unset or 20.
2. `settings`, in `effective_settings.json`: K = 20, five kept, `cpu`, the stream's
   self-evaluation on at 80, the model, mode `both` and code
   `57420db746e0510465bb5a08b7610e092b32e650`.
3. `drivers`, two levels above the run, by the SHA-256 below: V4's `live_api.py`, step 1's
   `live_runner.py` and this step's `live_supervisor.py`.
4. `asks`: the thirteen, in order.

**Forecast, written before the first request:**
- **faster** on 13 of 13, and **useful**: the continuation's prompt read in ≈ 10–15 s against the
  classic's 65–105 s;
- **scores held**;
- **routes agree**, with the least confidence of the four. A model rating its own answer in its
  own conversation may score it higher, and a score that crosses 80 turns a route.

The forecast candidate: the continuation.

## Running it

**The stand,** on the laptop first:

    git -C D:/RAG_new archive 57420db746e0510465bb5a08b7610e092b32e650 | ssh deproject-mac "test ! -e /Users/julia/RAG_new_chat_57420db && mkdir /Users/julia/RAG_new_chat_57420db && tar -x -C /Users/julia/RAG_new_chat_57420db && echo 57420db746e0510465bb5a08b7610e092b32e650 > /Users/julia/RAG_new_chat_57420db/CODE_SHA && ln -s /Users/julia/RAG_new_ask100_20261012_7cad79f/.ask100-runtime /Users/julia/RAG_new_chat_57420db/.ask100-runtime"

This raises it as V4's `raise_stand.sh` raised V4's. Then, on the Mac, with `S` and `PY` above:
`T=$S/step2`, `IX=/Users/julia/RAG_new_external_s1/aircargo`, and `Q` the thirteen questions above,
comma-separated in their order. The run starts detached, so ssh returns at once (as in stage 2, a
`;` before `nohup`, never `&&`).

1. **Tools:**
   - `mkdir -p $T/runs`;
   - from the laptop, for each `<f>` of `live_supervisor.py` and `step2_reader.py`:
     `git -C D:/RAG_new show <g>:reports/stage4-step2/tools/<f> | ssh deproject-mac "cat > /Users/julia/RAG_new_chat_57420db/step2/<f>"`;
   - on the Mac: `cp -p $S/reports/stage2/tools/live_api.py $S/reports/stage4-step1/tools/live_runner.py $T/`;
   - then `shasum -a 256 $T/*.py` prints the four of the list below.
2. **Idle, before the run,** step 0's rule. Else wait; nothing is stopped.
   - the 5-minute load (`sysctl -n vm.loadavg`, its second number) is below 2;
   - `pgrep -f "[p]ytest|[l]lama-server|[_]supervisor|[r]eplay\.py|[s]tep[0-3]_|[l]imactl"` finds
     nothing;
   - `/api/ps` is `{"models":[]}`;
   - there is no `$HOME/ci_local/.lock_ci-local`.
3. **Environment:** `$PY $S/reports/answer-prompt-v4/tools/stand_env.py >> $T/environment.jsonl`,
   before the run and after it.
4. **The run,** `L=s2-both`:

       cp -Rp $IX/index/chroma $T/runs/$L.chroma; diff -rq $IX/index/chroma $T/runs/$L.chroma && echo same
       LIVE_VARIANTS=cpu nohup $PY -u $T/live_supervisor.py $L prod $Q 2010/1365 TENANT=aircargo,CHROMA=$T/runs/$L.chroma,CASES_FILE=$S/evaluation/curated_cases_aircargo.jsonl,STREAMING_SELF_EVAL_MODE=both >> $T/runs/$L.supervisor.log 2>&1 </dev/null &

5. **One question first:** when `$T/runs/s2-both/progress.log` holds its first `CASE` line, and
   while the run goes on, run `$PY -I $T/step2_reader.py $T/s2-both.q1.step2.json
   $T/runs/s2-both`. Its first ask must be read, with the continuation held and under half the
   classic's seconds. Else the run is stopped as [Stops](#stops) says.
6. **After `LIVE_DONE`,** the last line of `$T/runs/$L.supervisor.log`: `rm -rf $T/runs/$L.chroma;
   $PY -I $T/step2_reader.py $T/step2.json $T/runs/$L --corpus $IX`. Its gate must pass.
   - A failed point is a shape the reader did not know: a marked error fix (the change, its test,
     the new SHA-256, one commit), then the run is read again; or it is run again as `s2-both-r2`
     where its files cannot give the point back.
   - A second failure: `NOT_EVIDENCE`.

   The files are copied to the laptop as bytes.

### Stops

- **A question past its cap** (2,010/1,365 s: 2,010 s for the run's first question, 1,365 s for
  the others, 3× the forecasts below) stops the run. The supervisor stops the API and the database
  and unloads the model.
- **The first question's stop:** the first question's read must hold the continuation, and the
  continuation must take under half the classic's seconds. Else the run is stopped with `pkill -f
  "[R]AG_new_chat_57420db/step2/live_runner.py"` and closed as step 6 closes it.
  - The cause is read from the first ask's counters: a prompt read at the classic's ≈ 28 ms a
    token is a prefix not kept.
  - It is also read from the slot's lines in Ollama's serve log
    (`/Users/julia/gr2_bench/ollama_serve.log`): the tokens kept from the cache, and the cache
    state saved and restored. These lines stay on the Mac.
  - A fix of the code is a new stand and an amendment of this spec, registered before its first
    request. Else step 2 closes with the classic.
- **A run without `LIVE_DONE`** at 3× its forecast (≈ 5 h 15 min) is stopped the same way. Its
  unread questions are `NOT_EVIDENCE`, and Julia gets the measured pace.

**Forecast:** the Mac's time once it is idle.
- ≈ 1 h 25 min at step 1's pace: its asks took a median 366 s, the classic among them.
- ≈ 1 h 45 min at step 1's spec forecasts: a first question ≈ 670 s and a later one ≈ 455 s, that
  is step 1's 655 and 440 s with ≈ 15 s for the continuation.
- Both include the API's start and the preload (≈ 1.3 min) and the checks, the environment lines,
  the copy and the reads (≈ 10 min).

## The copy

`live_supervisor.py` is step 1's `reports/stage4-step1/tools/live_supervisor.py` with marked
changes only: a block between `# stage4-step2: begin` and `# stage4-step2: end`, or a line ending
in `# stage4-step2`. The test checks that the unmarked lines are the original's, line for line.
- `STREAMING_SELF_EVAL_MODE` joins the deployment settings, one of `classic`, `continuation` and
  `both`, and is passed to the API as the other settings are. Another value is refused before
  anything is written.
- One original line is replaced, `DEPLOYMENT`. Without the name the copy writes and runs as the
  original.

`live_runner.py` is step 1's copy, unchanged: with no `arm` in `launch.json` it runs as V4's.

## Records

`reports/stage4-step2/57420db/` holds:
- `step2.json`: the run, its pairs and the readings;
- the first question's read, `s2-both.q1.step2.json`;
- `environment.jsonl`;
- for a rerun, `step2.s2-both-r2.json` and `s2-both-r2.q1.step2.json`, beside `s2-both`'s.

They hold numbers, enums, ids, model names, the paths named here and SHA-256 strings. They never
hold a question, answer, prompt, source name, log line, command line or environment, and of an
error only its type. The run directory stays on the Mac; the record names its files by SHA-256.

Step 2 is no slice by the acceptance rule: the default is unchanged, and no case or quality number
changes. Its record gets a row in [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md) and a test that
reads it again. The tools and their test are committed with this spec, and the test checks each
SHA-256 below; a later change is a marked error fix that updates this list:

- `reports/stage2/tools/live_api.py` `43ff96f06af18538a2571d68a86e898ecfcdd5fcab47039f0d58bd245361a7b5`
- `reports/stage4-step1/tools/live_runner.py` `c87838014a0517d5e6a3dde0402ed0b067a9e0148aaf5d842ffe272ca451a072`
- `reports/stage4-step1/tools/live_supervisor.py` `915ffa9e22e3165f56cd54194fe20e89c8e4146f5a10170f32094a03138fe536`
- `reports/stage4-step2/tools/live_supervisor.py` `0de222a762085f49f2455e813a50895fd88826f687683be2d6cb814926da9132`
- `reports/stage4-step2/tools/step2_reader.py` `18a7aaa26237dc370bf22d8831968248663fc5c926de1b144dddaf5f05157b28`
  (Amendment 1; registered as `dc19cae35e451a445c89834b5b1b5b314d92e512c9e5a622cfd89f52437169c1`, which read `s2-both`)
- `tests/test_stage4_step2_tools.py` `9d3cc48577ef3a58f059404fc811b8456c61cc6893af12ca5b1093ac25b4bc58`
  (Amendment 1; registered as `10e449d3bdd13ea318cd937d4a70fc693590daeeee7780401253c7026ff4c5bf`)

## A second opinion

Codex (profile cw, 2026-10-28) read the design, with excerpts of the code and the template, before
any code was written ([`PLAN.md`](../../PLAN.md) §8.1). Its verdict: fix first.
- **Taken:** the first message by its path, the strict parse, the window check, the explicit
  timeout, the cost with the fallback, a least useful saving, routes over compared pairs only, the
  memory printed, and the labelled answers before any default.
- **Not taken:** routing by the classic during the run, since the stand has no users and the
  continuation's own route is what production would serve.
- **Not taken:** capping or resetting the host cache between questions. Item 5's cap is Julia's
  word, and the run keeps production's cache.

It read the code too, before the stand (the diff, the router, the provider, the template and the
tests): «Live run as is: go».
- **Taken:** a NaN or infinite counter is no counter, so the entry never raises past the call;
  the classic's order, the tokens and the window in [Not said](#not-said).
- **Not taken:** a test of the real template and tokenizer on the laptop, which runs no model —
  the first question's read is that test; and the request's context carried into the worker
  thread, which the classic call does not carry either.

## Not said

- Thirteen questions of one corpus, one stand and one day, on a Mac other projects share. The run
  shows what the continuation saves and how it routes on these. It does not show the product's
  speed (item 7) or the badge's quality (step 2b). K = 20 only.
- The classic runs second, a minute after the continuation, on the same answer: its seconds are a
  classic's after a continuation, not a classic-only run's. The host cache should still save three
  states a question, as in `classic` — the continuation matches its slot, so nothing is saved
  before it — but the state saved before the classic is the continuation's, ≈ 300 tokens longer
  than the answer's. Step 0 measured neither this order nor these saves, and the bias they put on
  the saving is not measured here.
- The two sides do not see the same text. The continuation sees the answer as it streamed, `[N]`
  markers in, beside the answer prompt's instructions and documents. The classic sees it without
  markers, beside the documents in V3's layout. A route difference is read, not explained.
- The host prompt cache grows over the run as in production, with no cap. The memory is printed;
  a series longer than thirteen is item 5's.
- The counters are Ollama's. The slot's own lines are read only where the first question stops.
  A prefix kept is read from the seconds and the counters, not from token ids: that the
  continuation's tokens are the answer call's is not proven token by token.
- The window check estimates the three messages' tokens, as the answer's own fitting does, with
  its 10 % margin: a long answer after a full prompt is refused and scored by the classic, and a
  truncation Ollama would make silently is not read token by token either.

## Amendment 1, 2026-10-29: the rerun unloads the model before each question

Registered before `s2-both-r2`'s first request, after `s2-both` was read. The questions, their
order, the forecasts, the caps, the stops, the drivers and the readings stay as above. The
reader's gate changes in one point, with its test; [Records](#records) lists their new SHA-256.

**What `s2-both` gave.** It ran 08:37–11:21 UTC on 2026-10-29. Its first twelve questions
delivered their answers. The thirteenth, `aircargo-templates-checklist`, ran past its 1,365-s
cap with its first token at 1,281 s, and the supervisor stopped the run: `failed`, exit 5. The
reader's gate failed on its launch point alone, so no pair is read and every reading is
`NOT_EVIDENCE` (`reports/stage4-step2/57420db/step2.json`). Both environment lines name Ollama
0.33.2 and one server.

**Why it stopped,** read from the run's files on the Mac, outside the frozen reading, deciding
nothing:
- The time went to the retrieval. The rerank took 166–266 s in eight questions and 458–760 s in
  the other five, the vector search 61–334 s, the answer's stream 75–204 s.
- The swap used rose from 1,836 MiB at the first question's start to 11,608 MiB in the twelfth,
  ≈ 750 MiB a question, and stayed there, while llama-server's resident memory stayed at
  3,357–3,741 MiB. So grows step 0's host prompt cache with no cap: a state saved a request, none
  restored (item 5).
- Step 1 found the rerank waiting on the resident model's memory: with the model unloaded it took
  a median 0.26 of its time.
- Other projects' processes ran beside it, among them two pytest suites over the third to the
  fifth question and a headless browser over the twelfth and the thirteenth.

A rerun as registered meets the same growth at the same questions, and each of its later
questions is one contention away from its cap.

**The change.** `s2-both-r2` runs with step 1's arm `B` on each of the thirteen questions,
`ARM=BBBBBBBBBBBBB`, which the registered supervisor and runner take as they are.
- Before each question the runner unloads the model and waits until Ollama holds none and no
  llama-server is left. An unload not done within 120 s stops the series with exit 6, which
  fails the gate.
- The host cache goes with its process, so no question starts on the states of the ones before
  it, and each retrieval runs without the model resident, as in step 1's arm B.
- The reader's gate wants that arm on `s2-both-r2` and no arm on `s2-both`.

**What stays.** A pair is still two self-evaluations of one answer in one llama-server process:
the answer's call loads the model, and the continuation's slot is the answer's own. The first
question's read and its stop are `s2-both-r2`'s own, as step 5 and [Stops](#stops) say for
`s2-both`.

**Forecast.** Step 1's B asks took 282–479 s, the classic among them. With the continuation's
≈ 10 s: ≈ 1 h 10 min – 1 h 30 min for the thirteen on an idle Mac, then ≈ 10 min of reads and
copies.

**Running it:** steps 2–6 of [Running it](#running-it) with `L=s2-both-r2`, and
`,ARM=BBBBBBBBBBBBB` added to the supervisor's settings after `STREAMING_SELF_EVAL_MODE=both`.
The reader writes `$T/step2.s2-both-r2.json`. A second failure of the gate is `NOT_EVIDENCE`, as
step 6 says.

**Not said, added.**
- `s2-both-r2`'s totals and first tokens are a stand's that unloads the model before each
  question: its retrieval runs without the model resident, and its answer pays the model's load.
  They say nothing of production's pace, which keeps the model resident.
- The host cache's growth over a series is item 5's. `s2-both`'s samples show it here and decide
  nothing.
