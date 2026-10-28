# Stage 4, step 0: the 4B's prompt cache, memory and reused prefix, before any lever — 2026-10-28

The question: stage 4's levers rest on what llama-server does with memory on this 8-GB Mac.
Does its host prompt cache grow by ≈ 300 MiB a request, and is that the 4B process's growth
(Q1)? Does generation wait on memory (Q2)? Does an answer reuse its instructions, and is the
reuse worth 4 s (Q3)? Are the weights repacked at load? Five aircargo questions, in two runs on
V4's stand, read by [`stage4-step0-diagnostics.md`](../specs/stage4-step0-diagnostics.md),
registered with its sampler and reader in `ab8be4b` before the first request. One marked error
fix of the reader came after run 1, in `1d21173`. The runs took 49 min of the Mac.

Record: [`reports/stage4-step0/4f48fed/`](../../reports/stage4-step0/4f48fed/):
- `step0.json`, both runs and the readings;
- each run's own read (`s0-first.step0.json` is the gate's);
- the two runs' samples and the two environment lines.

The reader is
[`reports/stage4-step0/tools/step0_reader.py`](../../reports/stage4-step0/tools/step0_reader.py).
Checked by [`tests/test_stage4_step0_artifact.py`](../../tests/test_stage4_step0_artifact.py):
- every reading is read again from the record's rows with the committed reader;
- the samples are the committed files, and every request's windows attach again from them;
- both runs pass the gate run 1 was held to;
- the stand, the server and the interpreter are V4's;
- the files hold numbers, ids, the spec's paths and SHA-256 strings only;
- every table row below is built from the record.

The record holds no log line, prompt, question, answer, command line or environment.

## Provenance and method

- **The stand:** V4's, `S=/Users/julia/RAG_new_chat_4f48fed`, code
  `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1`, mode `prod`, tenant `aircargo`.
  - The drivers are V4's by SHA-256, and so are the corpus files, the questions file and the
    model's digest (`qwen3:4b-instruct-2507-q4_K_M`, `0edcdef34593…`, on the CPU).
  - Both environment lines name Ollama 0.33.2 with V4's one server start (pid 12377, started
    2026-09-13) and V4's interpreter distributions.
- **The runs:** `s0-first` asked `aircargo-probation-data`; `s0-rest` asked the next four of
  aircargo's registered order.
  - Each run started a fresh API, database and llama-server, asked through
    `/api/ask/stream` and unloaded the model.
  - The sampler read the Mac every 5 s; the reader read Ollama's log between a run's first and
    last sample.
  - Run 1's gate passed on all four points before run 2 started.
- **The error fix:** this llama-server prints its build and `system_info` lines after common's
  tag, `cmn  common_param: `, and no `load_backend` line. Run 1's read therefore left the build
  and `system_info` null with a note.
  - The reader now reads both shapes; no reading's rule or threshold changed.
  - `s0-first.step0.json` stays as the reader before the fix wrote it. `step0.json` reads both
    runs with the fixed reader, and differs from it only in those load lines.
- **The Mac was shared:** other projects' processes ran throughout — browser tests, a CI
  container's Python, another project's Python. The spec stops nothing.
  - The 1-minute load had a median of 3.4 in run 1 (up to 17.8) and 3.7 in run 2 (up to 14.4).
  - The idle check before each run still held: the 5-minute load under 2.
- **Fifteen requests, not the spec's 14:** V4 routed `aircargo-probation-extend` to `human` (its
  self-evaluation scored 60); here it went `auto`, with suggestions. No reading depends on the
  route.

## The readings

| Question | Read | Measured | Forecast |
|---|---|---|---|
| Q1, the cache grows ≈ 300 MiB a request | **yes** | 280.69 MiB a request over 13; the footprint 2,944.0 MiB for the cache's 2,943.248 (ratio 1.0) | yes |
| Q2, generation waits on memory | **no** | a median 8.227 MiB brought back a generated token, 6 windows | no |
| Q3, a later answer reuses its instructions | **no** | a median 5 tokens reused, 3 answers | no |
| Q3's lever, the best prefix at hand saves ≥ 4 s | **yes** | a median 5.0 s an answer | no |
| Repacking | **on** | model buffers CPU and CPU_REPACK, `system_info` REPACK = 1 | on |

The forecast's CPU backend, `haswell`, is not read. This llama-server prints no `load_backend`
line, so no backend file is named. Its `system_info` lists AVX, AVX2, FMA, F16C and BMI2 and no
AVX-512 flag, on 4 threads of 4; the build is `1 (d222767c7)`.

## Per request

The cache state is the line llama-server prints as the request arrives, after it saved the
slot's previous state. The footprint is llama-server's at the first sample after that line.

| Run | Question | Call | Prompt tokens | Reused | Prompt s | Generated | Tokens/s | Cache state, MiB | Footprint after it, MiB |
|---|---|---|---|---|---|---|---|---|---|
| s0-first | `aircargo-probation-data` | answer | 2,105 | 0 | 74.1 | 254 | 2.144 | 0.0 | 3,049 |
| s0-first | `aircargo-probation-data` | self_eval | 2,381 | 7 | 97.2 | 4 | 1.719 | 331.6 | 3,511 |
| s0-first | `aircargo-probation-data` | suggestions | 400 | 5 | 13.3 | 45 | 2.689 | 667.9 | 3,847 |
| s0-rest | `aircargo-probation-extend` | answer | 2,380 | 0 | 75.0 | 281 | 3.134 | 0.0 | 3,174 |
| s0-rest | `aircargo-probation-extend` | self_eval | 2,690 | 7 | 105.1 | 3 | 4.633 | 374.1 | 3,554 |
| s0-rest | `aircargo-probation-extend` | suggestions | 429 | 5 | 13.4 | 44 | 5.803 | 753.7 | 3,934 |
| s0-rest | `aircargo-probation-dismissal` | answer | 2,327 | 5 | 67.8 | 58 | 3.961 | 820.8 | 4,002 |
| s0-rest | `aircargo-probation-dismissal` | self_eval | 2,422 | 7 | 65.0 | 4 | 4.011 | 1,156.7 | 4,338 |
| s0-rest | `aircargo-probation-dismissal` | suggestions | 329 | 5 | 7.8 | 43 | 8.247 | 1,498.8 | 4,680 |
| s0-rest | `aircargo-dismissal-check` | answer | 2,273 | 5 | 61.7 | 192 | 3.879 | 1,551.6 | 4,733 |
| s0-rest | `aircargo-dismissal-check` | self_eval | 2,499 | 7 | 67.4 | 4 | 5.402 | 1,898.9 | 5,080 |
| s0-rest | `aircargo-dismissal-check` | suggestions | 417 | 5 | 10.3 | 35 | 8.245 | 2,251.7 | 5,433 |
| s0-rest | `aircargo-dismissal-lawyer` | answer | 2,274 | 5 | 65.0 | 65 | 3.207 | 2,315.9 | 5,497 |
| s0-rest | `aircargo-dismissal-lawyer` | self_eval | 2,377 | 7 | 70.2 | 4 | 5.717 | 2,645.4 | 5,826 |
| s0-rest | `aircargo-dismissal-lawyer` | suggestions | 337 | 5 | 8.7 | 61 | 7.781 | 2,981.1 | 6,162 |

### Q2's generation windows

The samples surely inside a generation: a self-evaluation's 3–4 tokens, and most suggestions,
end before two samples fall inside them.

| Run | Question | Call | Window s | Brought back, MiB | MiB a token |
|---|---|---|---|---|---|
| s0-first | `aircargo-probation-data` | answer | 110 | 5,520.7 | 23.409 |
| s0-first | `aircargo-probation-data` | suggestions | 10 | 463.5 | 17.237 |
| s0-rest | `aircargo-probation-extend` | answer | 80 | 1,001.4 | 3.994 |
| s0-rest | `aircargo-probation-dismissal` | answer | 5 | 10.6 | 0.535 |
| s0-rest | `aircargo-dismissal-check` | answer | 40 | 88.4 | 0.57 |
| s0-rest | `aircargo-dismissal-lawyer` | answer | 15 | 599.5 | 12.46 |

### Q3's later answers

The saving is (the best prefix − the tokens reused) × the prompt's milliseconds a token.

| Question | Reused | Best prefix | Prompt ms a token | Saving s |
|---|---|---|---|---|
| `aircargo-probation-dismissal` | 5 | 177 | 29.147 | 5.0 |
| `aircargo-dismissal-check` | 5 | 142 | 27.149 | 3.7 |
| `aircargo-dismissal-lawyer` | 5 | 186 | 28.588 | 5.2 |

### The pace beside V4's batch 1

| Question | V4's batch 1, s | Step 0, s | V4's route | Step 0's route |
|---|---|---|---|---|
| `aircargo-probation-data` | 374.9 | 651.9 | auto | auto |
| `aircargo-probation-extend` | 306.7 | 654.3 | human | auto |
| `aircargo-probation-dismissal` | 262.6 | 573.1 | auto | auto |
| `aircargo-dismissal-check` | 350.1 | 367.6 | auto | auto |
| `aircargo-dismissal-lawyer` | 226.2 | 368.0 | auto | auto |

## What it says

- **The 4B's growth is its host prompt cache (Q1 yes).**
  - As each request arrived, llama-server saved the slot's state from the request before. An
    answer or a self-evaluation left 330–380 MiB; suggestions left 53–67 MiB.
  - In 15 requests no state was restored and none was removed. By run 2's last request the cache
    held 11 prompts in 2,981.1 MiB of its 8,192-MiB limit.
  - llama-server's footprint grew with the cache, ratio 1.0, from 3,174 to 6,162 MiB in run 2.
- **The cache bought nothing here.**
  - llama.cpp restores a cached state only when the new prompt keeps at least a quarter of it:
    `f_keep < 0.25` is skipped, «don't trash large prompts», in `server_prompt_cache::load` of
    `tools/server/server-task.cpp` at `d222767c7`, read 2026-10-28.
  - No cached state passed it. The 142–186 tokens a later answer shared with one were under 8 %
    of that state's 2,300 tokens and more. The 5 and 7 tokens each request reused came from the
    slot's own state.
- **Generation does not wait on memory (Q2 no).**
  - The pages brought back during a generation had a median of 8.2 MiB a token. The highest was
    23.4, run 1's answer under a load of up to 17.8.
  - The cache's states are written once and not read again. At run 2's last sample with the
    model, llama-server's footprint was 6,162 MiB, of it 2,583 MiB compressed, with an RSS of
    3,582 MiB.
  - The swap in use rose from 1,837 MiB at run 2's first sample to 4,654 MiB, and macOS added
    two 1-GiB swap files. It fell to 1,867 MiB after the unload.
- **Q3: no; its lever: yes by the frozen rule, against the forecast.**
  - Later answers reused 5 tokens each. The best prefix at hand was worth 3.7–5.2 s, a median of
    5.0 s: about 1 % of a question.
  - The cache cannot take it, by the rule above. The rate, 27–29 ms a prompt token, is this run's,
    under others' load.
- **The weights are repacked:** CPU_REPACK 1,683.28 MiB beside CPU 692.63 MiB at load.
- **The pace was the shared Mac's:** each question took 1.05–2.2× its time in V4's batch 1.
  Answers generated 2.1–4.0 tokens a second, against the 4.3–4.7 known.
- **The forecast:** four of its six items held: Q1, Q2, Q3 and the repacking. Q3's lever went
  the other way, and the backend was not read.

## What it means for stage 4

- **Item 5's first candidate stands: cap the host prompt cache.**
  - Here a cap costs no reuse: the cache restored nothing.
  - Ollama 0.33.2 passes no `--cache-ram`. Two routes reach llama-server, both read in the
    sources on 2026-10-28:
    - `LLAMA_ARG_CACHE_RAM` in `ollama serve`'s environment, which it hands to each llama-server
      (`cmd.Env = os.Environ()`, `llm/llama_server.go`). It takes an `ollama serve` restart.
    - The line `cache-ram = N` in `~/.config/llama.cpp/config.ini`. Every llama-server reads that
      file at start (`common_params_apply_system_config`, `common/arg.cpp`), so it takes no
      restart. It reaches every llama.cpp program of that user, and a value that does not parse
      stops every start.
  - Either is a change on Julia's shared Mac, so it waits for her word.
  - The proof is the log's own `cache state` line, which prints the limit; `ps eww` is not
    needed. The 30-question series then shows whether the swap stops growing.
- **Item 5a's repacking lever is closed;** INT8 and n-gram decoding stay.
- **Item 1 (where the rerank's seconds go)** gets a number, not an answer. By run 2's end,
  2,583 MiB of llama-server's footprint sat in the compressor. The API's two encoders compete
  for that memory (mine), and step 1 measures it.
- **Q3's lever is ≈ 5 s an answer that the cache cannot take;** no item is added for it.

## What it does not say

- Five questions of one corpus, one draw, one stand, on a Mac other projects loaded. It shows
  what the server does, not the product's speed (item 7). Nor does it show whether a 30-question
  series swaps (item 5): four questions are not a series.
- No lever was tried, and nothing was measured on quality.
- Q2 rests on six windows. Under the load, the prompt and generation rates are not the free
  Mac's, and Q3's saving scales with the prompt rate.

## Files

| File | Bytes | SHA-256 |
|---|---|---|
| `step0.json` | 61,596 | `a2a8d1de6033f5b7b81365d4bdbf53be124b66bab65e37a2dd826adb175f5bce` |
| `s0-first.step0.json` | 15,539 | `c4379a45683b1b6d0fe8f815c431cfa4a02b32bf8059a6097a020303e4053a36` |
| `s0-rest.step0.json` | 46,757 | `2bb74dcfca615b98e8dccc2a1710d7f9734db86c49497e28c356a9fd7a1d70b2` |
| `s0-first.samples.jsonl` | 99,428 | `600edd5e487026acaf44132744dda8310d609984c2039e1e0503506a0dff7eea` |
| `s0-rest.samples.jsonl` | 274,652 | `598a3a874c93c831955bc7db01a4950520071880c2bef8dcfc03a72bc265181a` |
| `environment.jsonl` | 1,964 | `a17d4ed5bda885463ce1dd264c8557631e08a68276826a016a637747fde6c5eb` |
