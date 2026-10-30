# Stage 4, step 4b: num_ctx 3,584 against 4,096, timed — the answer and its self-evaluation

Status 2026-10-29: **registered before the first request**, with the tool and its test
([Records](#records)), in `d1ef9e5`. [`PLAN.md`](../../PLAN.md) stage 4, item 4: «Затем живой замер
этого окна против 4 096», after [step 4](stage4-step4-prompt-budget.md)'s count and
[its record](../evidence/stage4-step4-record.md): the smallest window without a detected loss is
3,584. This is the live timing that spec names in
[What comes after](stage4-step4-prompt-budget.md#what-comes-after). The one value filled in at
launch is `<c>`, the commit that registers this spec.

## Why

- **The window's gold:** at 3,584 the three bases with gold keep it at «sent» in 134 of 250
  questions against 137 at 4,096 (b 3, c 0, p = 0.25): no loss detected, none excluded. On
  aircargo the answer's prompt is a median 456 estimated tokens shorter, 2,152 instead of 2,604.5.
  Whether the window enters the path is Julia's word (§8.3); she needs its seconds beside its gold.
- **Its seconds are not measured yet.** The 4B read an answer's prompt at 28–37 tokens a second
  and the self-evaluation's at 24–37 ([step 0](../evidence/stage4-step0-record.md#per-request)),
  so 456 estimated tokens are about 11–16 s a call: a forecast, not a number.
- **What it changes, and so what is timed:** the window changes the documents the answer is given,
  and the self-evaluation reads those documents again. The retrieval and the rerank before them
  are the same at both windows, and the hints come after the result since `43874fc`. So the
  timing is of the chat's two calls a question — the answer, streamed, and the classic
  self-evaluation — read in Ollama's own counters.
- **Why a load in every block:** num_ctx is set when Ollama loads the model, and a request at
  another window loads it again. Every block starts with no model in Ollama, so both windows pay
  a load alike; Ollama counts it apart (`load_duration`), and the reading leaves it out.

## The stand

- **Code:** `<c>`'s, in a clean worktree on the Mac, as step 4 ran: today's chat. The settings
  are V4's stand's: `V4=/Users/julia/RAG_new_chat_4f48fed`, its first aircargo run's
  `chatlive/runs/v4-aircargo-b01/effective_settings.json`. Before its calls each block holds
  against it the provider profile, the model's name, the routing, the role parameters, the
  three timeouts, the quality evaluation and its threshold, and the RAG parity; the provider
  registry by SHA-256; the self-evaluation mode `classic`, the default. Only the window and the
  server differ.
- **Interpreter and environment:** step 2b's,
  `PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python` (3.11.15, langchain-ollama 1.1.0, as
  V4's stand), in `env -i` with the three timeouts at 3,600 s and `RAG_DEVICE=cpu`
  ([Running it](#running-it)). The model `qwen3:4b-instruct-2507-q4_K_M`, digest `0edcdef3…`,
  Ollama 0.33.2. No `~/.config/llama.cpp/config.ini`: item 5's `cache-ram` line comes after this
  series, and a block refuses one.
- **The chat's calls, not the API:** the tool runs the chat's stream path in process, on the
  documents the retrieval gave (`api/routers/conversation.py`, `ask_stream`, a first question),
  from its fitting to the classic self-evaluation:
  - the request's deadline and model budget, bound as `ask_stream` binds them;
  - `_fit_stream_prompt` on the documents, with no history;
  - the stream model's `generate_stream` with the role `generate`'s options;
  - the self-evaluation's own fitting and prompt on the answer without its citations, sent by
    `_invoke_llm` with the role `evaluate`, and its score's route.

  The stream model is the provider runtime's strong model, built from the settings: an
  `OllamaProvider` with no fallback. No API, database, retrieval or rerank runs. The tool's test
  holds its two calls against the chat's own through `/api/ask/stream` at both windows.
- **The proxy:** each request reaches Ollama through a local proxy that passes it unchanged. Of
  each call the proxy keeps the status, the model, the options, its prompt's SHA-256 and length,
  when the first token came, and the counters of the stream's last line: `prompt_eval_count`,
  `prompt_eval_duration`, `eval_count`, `eval_duration`, `load_duration`, `total_duration`. It
  keeps no text.

## The questions and the blocks

- **The questions:** step 3's, aircargo's registered order, its first thirteen, in the same
  order: `aircargo-probation-data` first — the series' first block finds the Mac cold, so it
  pairs with nothing — then `aircargo-probation-extend`, `aircargo-probation-dismissal`,
  `aircargo-dismissal-check`, `aircargo-dismissal-lawyer`, `aircargo-dismissal-order`,
  `aircargo-leave-sources`, `aircargo-leave-compensation`, `aircargo-leave-risk`,
  `aircargo-matliab-check`, `aircargo-matliab-disputed`, `aircargo-templates-choose` and
  `aircargo-templates-checklist`, the twelve of the pairs.
- **Their documents are step 4's.** The tool's inputs step runs step 4's tool on stage 2's
  records, run `p2-aircargo` of stand `5e308fe`, with every check of it. For the thirteen it keeps
  the documents the fitting starts from: the product's parent expansion of the recorded five. It
  stops unless, on each of the thirteen:
  - V4's live run retrieved what the record holds;
  - the chat's fitting at 4,096 gives the SHA-256 of the prompt V4's live run sent;
  - at both windows it gives step 4's committed row: the documents, the cut, the characters and
    the estimated tokens.

  By step 4's rows the twelve's answer prompts hold three to five documents, 2,550–2,636
  estimated tokens, at 4,096, and three or five, 2,003–2,175, at 3,584. The twelve save a median
  469 estimated tokens (377–591).
- **A block** is one question at one window:
  1. Ollama is made to hold no model and no llama-server: `keep_alive` 0, then `/api/ps` and
     `ps` until both are gone.
  2. A new process whose `OLLAMA_CONTEXT_WINDOW` is the block's window makes the chat's two
     calls.
- **26 blocks:** each question's two in a row, the windows' order ABBA over the questions —
  4,096 first at odd positions, 3,584 first at even ones. Each window goes first in six of the
  twelve pairs, so a drift of the shared Mac falls on both windows alike.

## What is read

By the tool's `read`, from each block's file. Of a block:
- of each call, Ollama's prompt tokens and seconds, the generated tokens and seconds, and the
  load;
- the **prompt seconds** — the two calls' `prompt_eval_duration`, summed;
- the **whole** — the two calls' `total_duration` less their loads;
- the **result** — the chat's wall from the stream's start to the self-evaluation's score, less
  the answer's load;
- the documents sent and the prompts' estimated tokens;
- the score, its source and the route;
- `/api/ps`'s size and context length, the unload's seconds, and the load average and swap
  before and after.

A shape not found leaves null, never a guess.

## How it is read — frozen before the first request

- **A block passes its gate** when all of these hold:
  - it is the schedule's block (number, position, question, window, order) and the series' (the
    code, the tool and the inputs by SHA-256);
  - it made exactly two calls to `/api/generate`. Each answered 200 and its stream ended `done`,
    with no error line, no line unread and Ollama's six counters;
  - each call is the model at num_ctx equal to the block's window, with the chat's options: the
    answer num_predict 1,024 and temperature 0.2, the self-evaluation 128 and 0.0;
  - the answer's prompt is the registered one of its question and window, and the block's; the
    self-evaluation's prompt is the block's;
  - after the calls Ollama holds the one model, by its digest, at the block's window;
  - Ollama is 0.33.2 before and after; the model was unloaded before the block; no llama.cpp
    `config.ini` is present;
  - the answer is neither empty nor cut at the chat's wall.

  A block that fails its gate stops the series ([Stops](#stops)).
- **A block is disturbed** when step 0's processes ran at its start or its end, another model was
  in Ollama at its start, or at its end Ollama held anything but its model, or not one
  llama-server. A disturbed block is kept and named, not read.
- **A question's pair** (positions 2–13) is its two blocks; **readable** when both passed their
  gates undisturbed.
- **The answer,** over the readable pairs, 3,584's prompt seconds against 4,096's:
  - **faster** when 3,584 is below on more pairs and the exact two-sided sign test gives p below
    0.05;
  - **slower** the other way round;
  - **no detected difference** otherwise;
  - `NOT_EVIDENCE` with fewer than ten readable pairs.

  A tie counts on neither side. With twelve, faster needs at least 10 of 12 (p = 0.039).
- **The number:** the median, over the readable pairs, of 4,096's prompt seconds less 3,584's —
  the saving — and of 3,584's over 4,096's — the ratio.
- **Printed, deciding nothing:**
  - the same counts, sign test and medians for the whole and the result;
  - the medians at each window of the prompt seconds, the result, each call's prompt tokens, the
    generated tokens, the load and `/api/ps`'s size;
  - the median tokens saved a call, and the prompt and generation rates;
  - the routes, the scores parsed, and the pairs with the same route and the same answer;
  - the pairs by the window that went first, and the first question's two blocks.

The prompt seconds decide because the window changes what the model reads. The answers' lengths
vary more than the saving: step 0's answers generated 58–281 tokens at 2.1–4.0 tokens a second.
So the whole and the result carry the generation's spread, and stand beside.

**Forecast, written before the first request:** **faster**, on 12 of 12. The tokens saved, about
430 exact tokens a call: 469 estimated, the estimate about 10% above the exact count. At 4,096
the two prompts take ≈ 150 s together, so the saving is ≈ 23–30 s and the ratio ≈ 0.82. The
whole and the result fall by about as much, with the answers' spread around it. `/api/ps`'s size
falls by about the KV cache of 512 tokens, ≈ 72 MiB at f16 (36 layers, 8 KV heads of 128).

## Running it

On the Mac: `G=/Users/julia/RAG_new_mf_gate`, `W=/Users/julia/RAG_new_s4p4b`,
`O=/Users/julia/RAG_new_s4p4b_runs`, `SITE=/Users/julia/RAG_new_mf_gate_site`, `V4` and `PY`
above, `T=reports/stage4-step4b/tools/window_timing.py`; `E` is the environment:

    env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME="$HOME" LC_ALL=C PYTHONPATH="$W:$SITE" PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 REQUEST_TIMEOUT_SEC=3600 OLLAMA_REQUEST_TIMEOUT_SEC=3600 STREAMING_TIMEOUT_SEC=3600 RAG_DEVICE=cpu

1. **The worktree:** `git -C $G worktree add --detach $W <c>`, by its full SHA;
   `git -C $W status --porcelain` prints nothing; `shasum -a 256 $W/$T
   $W/tests/test_stage4_step4b_tools.py` prints the two of [Records](#records).
2. **The inputs,** with step 4's interpreter for step 4's tool: `cd $W; PYTHONDONTWRITEBYTECODE=1
   PYTHONPATH=$SITE /Users/julia/RAG_new_gr4_venv/bin/python $T inputs
   /Users/julia/RAG_new_chat_5e308fe/chatlive/runs /Users/julia/RAG_new_external_s1 $O`. It
   prints the thirteen's sizes and `inputs.json`'s SHA-256.
3. **The series,** detached so ssh returns at once (`;`, never `&&`, before `nohup`, as in stage
   2): `cd $W; $E nohup $PY -u $T series $O $V4 >> $O/series.out 2>&1 </dev/null &`.
   - Before each block it waits for the idle Mac, by step 0's rule. No process matches
     `[p]ytest|[_]supervisor|[r]eplay\.py|[s]tep[0-3]_|[l]imactl`, Ollama holds no other model,
     no llama-server runs but its own model's, and `$HOME/ci_local/.lock_ci-local` is absent.
     Before its first block the 5-minute load is also below 2.
   - Nothing is stopped; it waits.
4. **One question first:** once `$O/series.log` names block 1, `touch $O/stop`; the series ends
   after block 1 with exit 3. Its line `block 1 read: …` must stand in the log: its gate passed.
   Else [Stops](#stops) applies. Then `rm $O/stop`, and the series is started again as in 3: it
   resumes at block 2.
5. **The record,** after `SERIES_DONE`: `cd $W; $E $PY $T read $O $O/record`. Its `record.json`
   and `rows.jsonl` are copied to the laptop as bytes.

### Stops

The series' exit codes:
- 3, the stop file;
- 4, the Mac not idle within an hour;
- 5, a block past 600 s, 3× the forecast of a block at 4,096 (it is killed, the model unloaded);
- 6, the settings, the model, the window or the series' facts not the registered ones;
- 7, a call to Ollama failed (nothing saved);
- 8, a block's gate failed (its file moved to `$O/rejected/`);
- 9, a block failed twice.

After 4, 5, 7 or 8, once the cause is read, the series is started again as in 3. It resumes at
its first block without a file, so a failed block gets its second attempt. A block that fails
twice ends the series — started again, it exits 9. Its pair and those after it are not read;
with fewer than ten readable pairs the answer is `NOT_EVIDENCE`, and Julia gets the measured
pace. A 6 is a fault of the stand or the tool. A fault of the tool is a marked error fix — the
change, its test, the new SHA-256, one commit — and the series starts over in a new `$O`.

**Forecast:** a block ≈ 200 s at 4,096 — a load ≈ 15 s, the answer's prompt ≈ 70 s, ≈ 190
tokens generated at ≈ 4 a second, the self-evaluation's prompt ≈ 75 s — and ≈ 180 s at 3,584.
That is ≈ 85 min for the 26, ≈ 1.5 h with the unloads and the checks, once the Mac is idle.

## Records

`reports/stage4-step4b/d1ef9e5/`:
- `record.json`: the series' facts, the inputs by SHA-256 with the thirteen's prompt sizes, the
  model, the environment's lines, the attempts and the files rejected, the pairs and the readings;
- `rows.jsonl`, a block a line: its schedule, its numbers, and its gate's and its disturbance's
  reasons.

Numbers, enums, ids, the model's name and SHA-256 strings: never a question, a document's text
or source, an answer or a prompt. `stage2_common.without_text` refuses a record with a string
that names a document or holds a question. The inputs, the blocks and the answers stay on the Mac.

Step 4b's timing is no slice by the acceptance rule: no behaviour, case or quality number
changes. Its record gets a row in [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md), a capsule in
`docs/evidence/` and a test that reads it again.

`tests/test_stage4_step4b_tools.py` holds the tool's calls against the chat's own, runs a block
whole against a fake Ollama, and covers the gate, the series' stops and the reading. The tool and
its test are committed with this spec, and the test checks each SHA-256 below; a later change is
a marked error fix that updates this list:

- `reports/stage4-step4b/tools/window_timing.py` `f2992901ca9428836bedfded26cb61e4615a5d90e8439317bc15a889ebfff651`
- `tests/test_stage4_step4b_tools.py` `1955e629002ee5e110655380c3114a073ea7f5986197eb3b9bd679c19831c576`

## Not said

- **Which window enters the path.** That is her word ([`PLAN.md`](../../PLAN.md) §8.3). A new
  num_ctx changes the answer path, and with it item 6 and stage 5, as K = 14 does. If both come,
  they are one re-answer, not two.
- **Answer quality.** The self-evaluation's scores and routes are printed; the answers are judged
  only at item 6. The gold sent is step 4's count.
- **The other calls.** num_ctx is shared by the hints, the graph path, `/api/ask` and the grader.
  Only the answer and its self-evaluation are timed.
- **The chat's whole wall.** No retrieval, rerank or hints run here. The final timing (item 7)
  measures the path as it ends up.
- **A resident model.** Every block loads the model, and its load is read apart. The chat with
  the model resident at one window reused at most 7 tokens of a prompt
  ([step 0](../evidence/stage4-step0-record.md#per-request)).
- **Memory.** `/api/ps`'s size is printed; item 5 measures memory.
- Twelve questions of one corpus, one stand, one day, on a Mac other projects share.
