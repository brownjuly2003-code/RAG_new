# Stage 4, item 5a: n-gram decoding in the answer model's own llama-server

Status 2026-10-30: **registered before the first request**, with the tool and its test
([Records](#records)), in `5558ca8`. [`PLAN.md`](../../PLAN.md) stage 4, item 5a, the second lever
of research 6: «n-gram-декодирование — llama-server без Ollama на том же GGUF и тех же флагах:
сначала база без speculation, затем `--spec-type ngram-simple`. ≈ 2–3 ч. Найденный тест дал и
ускорение, и замедление.» This spec is that comparison. The one value filled in at launch is
`<c>`, the commit that registers this spec. **Read 2026-10-30**, five blocks, every gate passed
at its first attempt: `NOT_EVIDENCE`, seven of the thirteen readable — the lever closes;
[the record](../evidence/stage4-step5a-ngram-record.md).

## Why

- **The lever touches the writing only.** Step 4b timed the chat's answer call on aircargo's
  thirteen at num_ctx 4,096 ([its record](../../reports/stage4-step4b/d1ef9e5/record.json)). On
  the twelve read, each its own median, so they do not add up: a call 74.5 s, reading the prompt
  57.7 s, writing the answer 17.8 s, 81.5 tokens written, 223 ms a token; the whole answer with
  the self-evaluation 135.9 s. In all, the twelve calls took 972 s, of them 281 s writing.
  n-gram decoding can save part of the writing, nothing of the reading.
- **How it gains, and how it loses.** `ngram-simple` looks for the last 12 tokens earlier in the
  prompt and the answer so far; on a match it drafts the up to 48 tokens that followed, and the
  model checks the draft in one batch, keeping the tokens it would have written. Here a batch is
  read at ≈ 40 tokens a second and a token is written alone at ≈ 4.5 (step 4b's medians), so a
  token checked costs ≈ 25 ms and a token written ≈ 223 ms: a kept draft of 48 costs ≈ 1.2 s
  instead of ≈ 11, a draft thrown away at once costs ≈ 1 s.
- **Why the answers' bytes are read.** Only tokens the model would sample are kept, but the check
  reads a batch, and a batch can round differently from a token at a time. A lever that keeps the
  answers byte for byte is a setting; one that changes them changes the answer's path, as K and
  the window do (PLAN item 6).
- **Why outside Ollama.** Ollama 0.33.2 starts its runner with `--spec-type` only for its own
  draft models. `ngram-simple` would reach the runner only through `ollama serve`'s environment
  (`LLAMA_ARG_SPEC_TYPE`) or llama.cpp's `config.ini`, both her word (PLAN §8.3). So the runner's
  binary is started directly, with the runner's own arguments and environment, and a block
  through Ollama holds it to the product's generation.

## The stand

- **The model:** `qwen3:4b-instruct-2507-q4_K_M`, digest `0edcdef3…`, in Ollama 0.33.2; its
  GGUF is the blob the runner loads, named by its SHA-256, which the tool checks, and held by
  its size before each block.
- **The server:** the `llama-server` Ollama 0.33.2 runs as the model's runner
  (`/Users/julia/RAG_new_tools_ollama_v0.33.2/llama-server`, 0.3.0-dev, llama.cpp
  `d222767c7`), held by SHA-256. Its arguments are the runner's, read from `ps` while Ollama
  holds the model, all but `--port`; its environment is the runner's variables named `LLAMA_*`,
  `GGML_*`, `DYLD_*` or `OMP_*`, with `PATH`, `HOME` and `LC_ALL=C`. `inputs` refuses a runner
  without `DYLD_LIBRARY_PATH`, which Ollama sets on macOS, or with a space in a variable it
  keeps, and a binary whose `--version`, run in that environment, does not exit 0. One variable
  is drawn anew for each runner Ollama starts, `LLAMA_MEDIA_MARKER`, read by llama-server only
  with a projector: it is kept, but left out wherever two runners are compared. It listens on
  127.0.0.1:18093, a fresh process a block, and no `~/.config/llama.cpp/config.ini` exists.
- **The arms:** `base`, the runner as it is; `ngram`, the same with `--spec-type ngram-simple`
  at its defaults (size-n 12, size-m 48, min-hits 1): the sizes have no environment variable, so
  the defaults are what Ollama's runner could be given.
- **The call** is the chat's answer call (`llm/role_params.py`, role `generate`): `/api/generate`
  with `num_ctx` 4,096, `num_predict` 1,024, `temperature` 0.2 and `think` false, with one change,
  `seed` 1030 on every call. The product sends no seed, and a random one would make the answers
  differ by the draw, not by the lever. The direct server gets the `/completion` body Ollama's
  runner sends for this call — Ollama's defaults, then the model's parameters, then the request,
  Go's omitempty — on the prompt Ollama itself rendered (`_debug_render_only`). That body holds
  only for a model with no renderer and no parser: with a parser Ollama sends the runner the
  parser's preserved tokens and rewrites the answer. `inputs` records both, from `/api/show` and
  its Modelfile, and refuses a model with either.
- **The interpreter:** `PY=/Users/julia/RAG_new_gr4_venv/bin/python`, Python 3.11.15. The
  blocks and the read use the standard library only.

## The calls and the blocks

- **The prompts:** step 4b's thirteen aircargo questions at 4,096 — V4's answer prompt on step
  4b's documents — rebuilt by step 4's fitting from step 4b's inputs (SHA-256 `6dc8f49e…`) and
  held to step 4b's SHA-256 of each, each with the prompt tokens Ollama counted for it in step
  4b's record (`w4096_answer_prompt_tokens`), and a warm-up question that is not read. The tool's
  `inputs` renders the fourteen through Ollama once, reads the runner and the model file while
  Ollama holds the model, and unloads it.
- **A block** is one arm in a process of its own: it holds the stand, starts its server and sends
  the warm-up and the thirteen in order, each one streamed call. It writes a head line, a line a
  call (the SHA-256 of the prompt as it is sent, the text and its SHA-256, the seconds, the
  server's counters and timings, what ran beside before and after) and an end line; block 0's
  end line holds the runner Ollama started and what of it differs from the one `inputs` read.
- **The schedule:**
  0. through Ollama, the chat's own call: the warm-up and the first three — the fidelity;
  1. base, 2. ngram, 3. ngram, 4. base on the fourteen — ABBA, so a drift of the shared Mac falls
     on both arms alike.

  Ollama holds no model during blocks 1–4: the 8 GB hold one copy of the model.

## What is read

By the tool's `read`, from the blocks' files. Of each call of a direct block: its text's SHA-256
and length, how it stopped, the prompt's tokens cached and read, the prompt's and the writing's
milliseconds, the tokens written, drafted and kept, the wall seconds and the seconds to the first
text. Of each block: the server's load, its resident size after the load and the largest after a
call (read between calls, never during one), the settings it reports, the other processes' CPU,
the samples Ollama or `ps` did not answer, and the swap.

## How it is read — frozen before the first request

- **A block passes its gate** when its head names its number, arm, the tool and the inputs by
  SHA-256 and no difference of the stand; its end line stands; its calls are the schedule's, in
  order, each with its text and the text's SHA-256; and
  - a direct call sent the rendered prompt, by the SHA-256 of what it sent; for each of the
    thirteen the server counted as many prompt tokens as Ollama did in step 4b; it ended on end of
    text, a stop word or the limit, not truncated, with its timings, and its cached and read
    tokens add up to the prompt;
  - a call through Ollama sent the flat prompt, by the SHA-256 of what it sent, and finished with
    its counters, and the runner Ollama started is the one `inputs` read: the same binary,
    arguments and environment but `LLAMA_MEDIA_MARKER`, else the gate names what differs.

  A block that fails its gate stops the series ([Stops](#stops)).
- **The fidelity:** block 0's four calls and block 1's first four give the same text, the same
  prompt tokens (Ollama's `prompt_eval_count` against `cache_n + prompt_n`) and the same answer
  tokens (`eval_count` against `predicted_n`). Else the series stops with 7 and only the fidelity
  is read: the direct server would not be the product's generation.
- **A question is disturbed** when, before or after its call in a direct block, a process
  matched step 0's pattern ([Running it](#running-it)), the other processes took more than one
  core (100 % CPU), Ollama held a model, not one llama-server ran, or Ollama or `ps` did not
  answer the sample — an error or no answer in time, named in the sample. It is kept and named,
  not read for speed; the block goes on.
- **The speed,** per question: the mean milliseconds a written token (`predicted_ms /
  predicted_n`) of ngram's two blocks against base's two; **readable** when undisturbed in all
  four.
  - **faster** when ngram is below on more questions and the exact two-sided sign test gives p
    below 0.05; **slower** the other way round; **no detected difference** otherwise;
    `NOT_EVIDENCE` with fewer than 10 readable. A tie counts on neither side.
  - The numbers: the medians of each arm's milliseconds a token, of base's over ngram's — the
    ratio — and of the writing's seconds saved; each arm's median wall seconds a call.
- **The answers' bytes:** base's two blocks give the same text on all thirteen, else
  `NOT_EVIDENCE`; then **byte-equal** when each base–ngram pair of blocks (1–2, 4–3, 1–3, 4–2)
  gives the same text on all thirteen, **differ** otherwise.
- **The outcome:**
  - the fidelity fails: `NOT_EVIDENCE`;
  - not faster: `not faster`, or `NOT_EVIDENCE` with too few readable — the lever closes;
  - faster, base not repeating itself: `NOT_EVIDENCE`;
  - **faster and byte-equal:** a lever «с её настройкой» (PLAN §8.3, item 2),
    `LLAMA_ARG_SPEC_TYPE=ngram-simple` in `ollama serve`'s environment; it reopens neither item 6
    nor stage 5, and item 7's timing measures it with the rest of the package;
  - **faster, answers differ:** it changes the answer's path, as K and the window do, and can
    enter only with item 6's new answers.
- **Printed, deciding nothing:** ngram's two blocks against each other; where each differing pair
  first parts; the tokens drafted and kept, and their rate, a block; block 0's seconds; each
  block's load, its resident size after the load and the largest after a call, and its samples
  Ollama or `ps` did not answer; the swap.

**Forecast, written before the first request:** the five blocks pass their gates and the fidelity
holds: the direct base is Ollama's generation to the byte. Base repeats itself on all thirteen,
and `ngram` keeps base's text on all thirteen — **byte-equal**: at temperature 0.2 a batch's
rounding flips a token only when the draw falls in the sliver it moves. `ngram` reads **faster**,
on 11 or 12 of the thirteen (p 0.022 or 0.003). The size of the gain rests on two figures,
neither of them a record:
- **an off-record estimate:** step 4b's answers at 4,096 copy a run of 12 tokens or more from
  their documents on every question read, and past each run's first 12 tokens 265 of their 1,246
  tokens could be kept drafts. They were counted by characters, at each answer's own characters
  a token, by a script outside the repository on laptop copies of step 4b's answer files, which
  step 4b's spec keeps on the Mac, before any request of this spec; the repository cannot repeat
  the count;
- **a guess:** kept over drafted ≈ 0.2, so ≈ 1,325 tokens drafted and ≈ 1,060 thrown away.

At the costs above, over the twelve read:
- the gross gain, 265 kept × (223 − 25) ms: ≈ 52 s, ≈ 4.4 s a question;
- the cost of the drafts thrown away, ≈ 1,060 × 25 ms: ≈ 26 s, ≈ 2.2 s a question;
- the net: ≈ 26 s, ≈ 2.2 s a question — ≈ 9 % of the 281 s of writing, a ratio ≈ 1.1, and
  ≈ 2.7 % of the 972 s of calls.

The net leaves out two things that pull opposite ways: each checked batch also yields one more
token, which the net does not count, and a batch of a few dozen tokens may cost more a token than
a prompt of ≈ 2,300 tokens. The resident size after a call moves by a few MiB.

## Running it

On the Mac: `G=/Users/julia/RAG_new_mf_gate`, `W=/Users/julia/RAG_new_s4p5n`,
`O=/Users/julia/RAG_new_s4p5n_runs`, `SITE=/Users/julia/RAG_new_mf_gate_site`, `PY` above,
`T=reports/stage4-step5a-ngram/tools/ngram_decode.py`,
`I=/Users/julia/RAG_new_s4p4b_runs/inputs.json` — step 4b's inputs; `E` is the blocks'
environment:

    env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME="$HOME" LC_ALL=C PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1

1. **The worktree:** `git -C $G worktree add --detach $W <c>`, by its full SHA;
   `git -C $W status --porcelain` prints nothing; `shasum -a 256 $W/$T
   $W/tests/test_stage4_step5a_ngram_tools.py` prints the two of [Records](#records). The tool
   holds it so: `inputs` refuses a worktree that `git status --porcelain
   --untracked-files=normal` finds not clean, and the series does too, at its start and before
   each block.
2. **The inputs,** on the idle Mac, Ollama holding no model, with `$SITE` on the path for step
   4's fitting: `cd $W; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$SITE $PY $T inputs $I $O`.
   It prints the runner's arguments, the names of its environment's variables, the call's
   options and `inputs.json`'s SHA-256.
3. **Two blocks first,** detached so ssh returns at once (`;`, never `&&`, before `nohup`):
   `cd $W; $E nohup $PY -u $T series $O 1 >> $O/series.out 2>&1 </dev/null &`.
   - Before each block it waits for the idle Mac: no process matches
     `[p]ytest|[_]supervisor|[r]eplay\.py|[s]tep[0-3]_|[l]imactl`, Ollama holds no model, no
     llama-server runs, `$HOME/ci_local/.lock_ci-local` is absent, and the other processes take
     at most one core. Before its first block the 5-minute load is also below 2. Nothing is
     stopped; it waits.
   - It ends after block 1: the last line of its log, `$O/series.log`, is `blocks to 1 done`,
     after `block 1 read` — block 1's gate and the fidelity passed. Else [Stops](#stops)
     applies. `$O/series.out` holds only what the command prints, `$O/blocks.out` what the
     blocks print.
4. **The series,** as in 3 without the `1`: it resumes at block 2 and ends `SERIES_DONE`.
5. **The record:** `cd $W; $E $PY $T read $O $O/record`. Its `record.json` and `rows.jsonl` are
   copied to the laptop as bytes.

### Stops

The series' exit codes, each with its line in `$O/series.log`:
- 3, the stop file `$O/stop`, read before each block;
- 4, the Mac not idle within an hour — a sample Ollama or `ps` did not answer is not idle;
- 5, a block with no head line within 300 s or no next call within 900 s — six and a half times
  step 4b's slowest answer call, 137 s; it is killed with its server, and for block 0 Ollama's
  model is unloaded;
- 6, the stand not the registered one, the series begun by another tool, or the worktree not
  clean at the start or before a block;
- 7, block 1 against block 0 past the fidelity (the files are kept);
- 8, a block's gate failed, or the block ended on an error after its head line — its server
  exited or was not ready within 300 s, a stream error, a socket timeout; its files are moved to
  `$O/rejected/`, and an error's traceback is in `$O/blocks.out`;
- 9, a block failed twice.

A sample Ollama or `ps` did not answer during a block stops nothing: its question is disturbed.
Any other exit is an error of the series itself, its traceback in `$O/series.out`.

A block kept from an earlier start is read again at every start, so a 7 or 8 holds. After 4, 5
or 8, once the cause is read — in `$O/series.log`, and for an error in `$O/blocks.out` —, the
series is started again as in 4. It resumes at its first block without a file, so a failed block
gets its second attempt; a block that fails twice ends the series — started again, it exits 9. A
6 or a 7 is a fault of the stand or the tool. A fault of the tool is a marked error fix — the
change, its test, the new SHA-256, one commit — and the series starts over in a new `$O`.

**Forecast:** ≈ 1.5 h of the Mac once it is idle. The inputs ≈ 2 min; block 0 ≈ 5 min; a direct
block ≈ 17 min, fourteen calls at step 4b's ≈ 74 s and the load under half a minute; the idle
checks, the stop after block 1 and the read ≈ 10 min.

## Records

`reports/stage4-step5a-ngram/5558ca8/`:
- `record.json`: the inputs by SHA-256 — step 4b's, the calls' prompts, the model, its renderer,
  parser and options, the runner's binary, version, arguments and environment, the GGUF —, the
  tool by SHA-256 and the commit measured, each block's facts, the attempts and the files
  rejected, the readings and the outcome;
- `rows.jsonl`, a question a line: its id and position, per direct block the call's numbers and
  its text's SHA-256 and length, whether it was disturbed, where differing texts first part, and
  for the first three block 0's.

Numbers, enums, ids and SHA-256 strings: never a question, a prompt or an answer's text, which
stay in the blocks' files on the Mac.

Item 5a's n-gram comparison is no slice by the acceptance rule: no behaviour, case or quality
number of the path changes. Its record gets a row in [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md),
a capsule in `docs/evidence/` and a test that reads it again.

`tests/test_stage4_step5a_ngram_tools.py` runs blocks against a stand-in server and Ollama and
covers the call's body, the stand, the gate, the fidelity, the series' stops and the reading on
hand-made blocks. The tool and the test are committed with this spec, and the test checks each
SHA-256 below; a later change is a marked error fix that updates this list:

- `reports/stage4-step5a-ngram/tools/ngram_decode.py` `70c760c41a75b20f7ae6c31b6f0869a6892606d09c25ec60b09176aa1b871791`
- `tests/test_stage4_step5a_ngram_tools.py` `bfecddcb066510b1b271eca9642fec3f47f4c78f45947b96d4fad4dda02fe9f4`

## Not said

- **Whether n-gram enters the product.** Its setting in `ollama serve`'s environment is her word
  ([`PLAN.md`](../../PLAN.md) §8.3); passing here earns the package question, not the path.
- **The chat's seconds.** The answer call runs alone on an idle Mac; in the chat the reranker and
  the embedder share the 8 GB. Item 7 times the package in the chat.
- **The self-evaluation's call,** four tokens written: not measured.
- **Other settings:** sizes other than the defaults, `ngram-cache`, draft models.
- **The product's seed.** One seed for every call; the product draws one a call.
- Thirteen questions of one base at one window, one stand, one day, on a Mac other projects share.
