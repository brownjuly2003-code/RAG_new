# Stage 4, step 1: the rerank beside the resident model and without it — 2026-10-28

The question: where do the rerank's 102 s go? PLAN's hypothesis for stage 4, item 1: the API's
two encoders and llama-server with the 4B do not fit beside macOS in the Mac's 8 GB, and the
rerank waits for its pages. Four aircargo questions were each asked twice. In arm A, today's
order, the model stayed resident. In arm B it was unloaded before the question: the rerank
first, then the model's load. Two runs on V4's stand, BABA then ABAB, read by
[`stage4-step1-rerank-memory.md`](../specs/stage4-step1-rerank-memory.md). The spec was
registered with its reader and the two driver copies
in `44fd650` before the first request; nothing changed after it. The runs took 76 min of the Mac.

Record: [`reports/stage4-step1/4f48fed/`](../../reports/stage4-step1/4f48fed/):
- `step1.json`, both runs, the pairs and the readings;
- each run's own read, the gate's (`s1-baba.step1.json`, `s1-abab.step1.json`);
- the first question's read, taken while run 1 went on (`s1-baba.q1.step1.json`);
- the two runs' samples and the two environment lines.

The reader is
[`reports/stage4-step1/tools/step1_reader.py`](../../reports/stage4-step1/tools/step1_reader.py).
Checked by [`tests/test_stage4_step1_artifact.py`](../../tests/test_stage4_step1_artifact.py):
- the files are the bytes copied from the Mac, read by the tools the spec lists, by SHA-256;
- the pairs and both readings are read again from the record's asks with the committed reader;
- each run's own read is the record's run. The first question's read is run 1's first ask,
  read from the start of the same samples file;
- the samples are the committed files, and every window and state attaches again from them;
- both runs pass their gates on all seven points;
- the stand, the server and the interpreter are V4's;
- the files hold numbers, times, versions, ids, enums, the tools' fixed notes, model names, a
  distribution's name, the stand's and the specs' paths and SHA-256 strings only;
- every table row below is built from the record and its samples, and so is each number of the
  prose that the test pins, the load spike's place and the leave-one-out medians among them.

The record holds no question, answer, prompt, source name, log line, command line or environment.

## Provenance and method

- **The stand:** V4's and step 0's, `S=/Users/julia/RAG_new_chat_4f48fed`, code
  `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1`, mode `prod`, tenant `aircargo`. It ran the code
  defaults: K = 20 candidates, five kept, the CPU.
  - The drivers are V4's `live_api.py` and this step's copies of V4's runner and supervisor, by
    SHA-256. The corpus files, the questions file and the model's digest are V4's
    (`qwen3:4b-instruct-2507-q4_K_M`, `0edcdef34593…`, on the CPU).
  - Both environment lines name Ollama 0.33.2 with V4's one server start (pid 12377, started
    2026-09-13) and V4's interpreter distributions.
- **The arms:** before each A question the runner sent the preload again (`keep_alive` 30 min).
  That took 0.005–0.041 s, with no poll. Before each B question it unloaded the model and polled
  until Ollama held none and no llama-server ran. That took 0.254–0.577 s, with one poll. B's
  answer call then loaded the model again.
- **The runs:** `s1-baba` (B, A, B, A) and `s1-abab` (A, B, A, B) asked the four questions that
  follow step 0's five in aircargo's registered order. Each question stood at the same position
  in both runs.
  - A question's two asks reranked the same candidates, by the pool's SHA-256: 30, 39, 37 and 39.
  - The supervisor's preload took 51.087 s in run 1 and 31.378 s in run 2.
  - Each run's samples saw three llama-server pids: the preload's, and one loaded by each B
    ask's answer call. An A ask ran beside the preload's (run 2's first) or beside the one the
    B ask before it had loaded. So A's model had served at most one question.
  - The sampler read the Mac every 5 s. The reader placed each ask's retrieval, vector search
    and rerank on the monotonic clock that the samples share.
- **The gates:** both runs' gates passed on all seven points: launch, settings, drivers, asks,
  actions, samples and b_held.
  - The one sample note was `ps: no process named llama-server`, in 83 samples of run 1 and 54
    of run 2: a note the spec counts as nothing wrong. Both samplers stopped on their stop file.
  - The first question's read was taken while run 1 went on. It read its one ask, with its arm,
    B, held. Its gate fails only `launch` and `asks`, as a read of one question of a running
    run must.
- **The Mac was shared:** the 1-minute load had a median of 4.15 in run 1 (up to 30.5) and 4.72
  in run 2 (up to 9.65). Each run began idle as far as the record shows:
  the 5-minute load was 1.18 and 1.92 at the runs' first samples, below the idle rule's 2,
  and Ollama held no model at either launch.

## The readings

| Reading, the spec's rule | Read | Measured | Forecast |
|---|---|---|---|
| Contention: B's rerank seconds over A's, a median at most 0.5 | **yes** | a median 0.2594 over 4 readable pairs | yes, a ratio ≈ 0.3–0.45 |
| Net: B's whole seconds less A's, a median below zero | **faster** | a median −47.009 s over 4 readable pairs: within 90 s of zero, the sign alone | faster at step 0's pace, a wash at V4's |

Each rule needs at least three readable pairs, and all four pairs were readable. Both gates
passed, all eight asks were read and held their arms, and each pair shares its position and its
candidates.

## Per ask

Seconds. The answer's first chunk is timed from its call's start, so B's holds the model's
load. The first token is timed from the question's request. The whole is the arm's action plus
the question's total, so B pays its unload and its answer's load.

| Run | Position | Question | Arm | Action | Retrieval | Vector search | Rerank | Answer's first chunk | First token | Whole |
|---|---|---|---|---|---|---|---|---|---|---|
| s1-baba | 1 | `aircargo-dismissal-order` | B | 0.308 | 225.0 | 104.0 | 120.9 | 100.5 | 333.0 | 478.5 |
| s1-baba | 2 | `aircargo-leave-sources` | A | 0.008 | 186.4 | 70.5 | 115.0 | 62.3 | 248.7 | 342.0 |
| s1-baba | 3 | `aircargo-leave-compensation` | B | 0.443 | 100.2 | 66.7 | 33.5 | 93.7 | 194.1 | 282.1 |
| s1-baba | 4 | `aircargo-leave-risk` | A | 0.041 | 475.7 | 97.7 | 377.9 | 135.1 | 611.0 | 715.8 |
| s1-abab | 1 | `aircargo-dismissal-order` | A | 0.014 | 143.5 | 52.4 | 91.1 | 63.3 | 209.8 | 326.7 |
| s1-abab | 2 | `aircargo-leave-sources` | B | 0.254 | 100.4 | 65.4 | 34.9 | 120.7 | 221.2 | 389.8 |
| s1-abab | 3 | `aircargo-leave-compensation` | A | 0.005 | 214.1 | 58.0 | 155.6 | 86.2 | 300.4 | 423.9 |
| s1-abab | 4 | `aircargo-leave-risk` | B | 0.577 | 112.4 | 70.9 | 41.3 | 88.9 | 201.4 | 291.3 |

### The pairs

| Question | A: run, position | B: run, position | B's rerank over A's | B's whole less A's, s |
|---|---|---|---|---|
| `aircargo-dismissal-order` | s1-abab, 1 | s1-baba, 1 | 1.3281 | +151.784 |
| `aircargo-leave-sources` | s1-baba, 2 | s1-abab, 2 | 0.3037 | +47.792 |
| `aircargo-leave-compensation` | s1-abab, 3 | s1-baba, 3 | 0.2151 | −141.810 |
| `aircargo-leave-risk` | s1-baba, 4 | s1-abab, 4 | 0.1093 | −424.565 |
| **The median, 4 readable pairs** | | | **0.2594** | **−47.009** |

### One pair left out

Each leaves three readable pairs, the rules' minimum; the rules are read as registered.

| Left out | Contention: the median ratio | Read | Net: the median, s | Read |
|---|---|---|---|---|
| `aircargo-dismissal-order` | 0.2151 | yes | −141.810 | faster |
| `aircargo-leave-sources` | 0.2151 | yes | −141.810 | faster |
| `aircargo-leave-compensation` | 0.3037 | yes | +47.792 | not faster |
| `aircargo-leave-risk` | 0.3037 | yes | +47.792 | not faster |

## Printed, deciding nothing

The spec prints these beside the readings; no rule reads them.

| Question | Retrieval, B over A | Vector search, B over A | Retrieval, B − A, s | Answer call's start, B − A, s | First chunk, A / B, s | First chunk, B − A, s | First token, B − A, s | Total, B − A, s |
|---|---|---|---|---|---|---|---|---|
| `aircargo-dismissal-order` | 1.5685 | 1.9864 | +81.567 | +85.937 | 63.264 / 100.522 | +37.258 | +123.151 | +151.490 |
| `aircargo-leave-sources` | 0.5385 | 0.9271 | −86.007 | −86.016 | 62.256 / 120.720 | +58.464 | −27.559 | +47.546 |
| `aircargo-leave-compensation` | 0.4682 | 1.1499 | −113.852 | −113.808 | 86.158 / 93.687 | +7.529 | −106.328 | −142.248 |
| `aircargo-leave-risk` | 0.2363 | 0.7263 | −363.314 | −363.309 | 135.090 / 88.878 | −46.212 | −409.549 | −425.101 |

The memory columns are the whole Mac's, a window's by its time. Pages faulted back are page-ins
plus decompressions inside the rerank. The state is the last sample at or before the rerank's
start. The record keeps llama-server's footprint (top's MEM), not its RSS: the RSS and the
compressed size beside it are the same sample's, read from the samples file.

| Question | Faulted back in the rerank, A / B, MiB | The same a second, A / B, MiB | Free at the rerank's start, A / B, MiB | Swap in use then, A / B, MiB | A's llama-server then: footprint / RSS / compressed, MiB |
|---|---|---|---|---|---|
| `aircargo-dismissal-order` | 1,235.1 / 1,588.3 | 14.5 / 13.8 | 11.8 / 748.1 | 1,736 / 1,530 | 2,998 / 2,913.4 / 89 |
| `aircargo-leave-sources` | 1,940.2 / 55.6 | 17.6 / 1.9 | 30.6 / 2,781.5 | 2,324 / 2,032 | 3,871 / 5.2 / 3,869 |
| `aircargo-leave-compensation` | 3,076.9 / 116.2 | 20.5 / 3.9 | 53.2 / 2,789.5 | 2,238 / 2,472 | 3,846 / 8.9 / 3,842 |
| `aircargo-leave-risk` | 4,785.7 / 189.5 | 12.8 / 4.7 | 22.1 / 3,080.3 | 2,611 / 2,291 | 3,838 / 1,896.8 / 1,946 |

| Printed | The median over the 4 pairs |
|---|---|
| The retrieval, B over A | 0.503 |
| The vector search, B over A | 1.038 |
| The retrieval, B − A | −99.930 s |
| The answer call's start, B − A | −99.912 s |
| The answer's first chunk, A / B | 74.711 / 97.105 s |
| The answer's first chunk, B − A | +22.394 s |
| The first token, B − A | −66.944 s |
| The total, B − A | −47.351 s |
| Pages faulted back in the rerank, A / B | 2,508.569 / 152.879 MiB |
| The same a second, A / B | 16.086 / 4.306 MiB |
| A's llama-server footprint at its rerank's start | 3,842.0 MiB |
| The arm's action, A / B | 0.011 / 0.376 s |

## The load inside the reranks

The reader reads no load, but the record lets each ask's rerank be placed in its run's
samples. A window's start and end are on the monotonic clock the samples share. The samples
found give back the window's count, seconds and six counters as the record holds them. The
answer call's span is the request's start (the retrieval's start less its offset) plus the
call's offset and seconds. Printed beside the readings, deciding nothing.

| Run | Position | Question | Arm | Samples in the rerank | 1-minute load: median / highest | Samples in the answer call | 1-minute load: median / highest |
|---|---|---|---|---|---|---|---|
| s1-baba | 1 | `aircargo-dismissal-order` | B | 24 | 3.815 / 5.98 | 28 | 6.31 / 11.19 |
| s1-baba | 2 | `aircargo-leave-sources` | A | 23 | 3.74 / 6.33 | 15 | 4.34 / 5.67 |
| s1-baba | 3 | `aircargo-leave-compensation` | B | 7 | 3.02 / 3.27 | 21 | 3.3 / 5.26 |
| s1-baba | 4 | `aircargo-leave-risk` | A | 76 | 2.425 / 4.37 | 33 | 21.92 / 30.5 |
| s1-abab | 1 | `aircargo-dismissal-order` | A | 18 | 1.73 / 2.39 | 19 | 4.61 / 5.22 |
| s1-abab | 2 | `aircargo-leave-sources` | B | 7 | 3.0 / 3.1 | 31 | 4.59 / 7.14 |
| s1-abab | 3 | `aircargo-leave-compensation` | A | 31 | 3.02 / 4.87 | 23 | 5.65 / 8.54 |
| s1-abab | 4 | `aircargo-leave-risk` | B | 9 | 3.68 / 3.88 | 20 | 3.97 / 5.09 |

- Inside the eight reranks the 1-minute load never passed 6.33.
  The answer calls ran higher: a median of 3.3–6.31, but for one ask.
- **Run 1's load spike falls after its fourth ask's rerank, not inside it.**
  Run 1's 1-minute load peaked at 30.5 at 19:58:29.846Z, inside its fourth ask's answer call
  (A, `aircargo-leave-risk`, a median of 21.92 over the call's 33 samples).
  Inside that ask's rerank (76 samples) the load had a median of 2.425 and a highest of 4.37; from the rerank's start on,
  the first sample above 4.37 is the first after the rerank, 19:55:54.855Z (4.46), 4.7 s into the answer call.
  - The swap's total went from 3,072 to 4,096 MiB at 19:57:39.848Z, inside the same call, with
    2,853.5 MiB in use; it went back to 3,072 MiB at 20:00:04.854Z, after the run's last ask.
  - That answer's first chunk took 135.09 s, against 62.256–86.158 s in A's other three asks.
    The spike weighs on the pair's whole seconds through A's answer.
  - The record names no process but llama-server, so what raised the load is not in it.
- **How far the net reading stands from that pair:**
  the net median stays below zero while this pair's difference is below −47.792 s.
  It was −424.565 s;
  less all 239.934 s of A's ask from its answer call's start, the difference is still −184.631 s.
  No share of the spike inside A's answer can turn the reading.
- **The one pair against the contention rule,** `aircargo-dismissal-order`, is both runs' first
  question. Its B ask's rerank ran under a 1-minute load of a median 3.815, its A ask's under
  1.73.

### The pace beside V4's batch 1

| Question | V4's batch 1: vector search / rerank, s | A: vector search / rerank, s | B: vector search / rerank, s |
|---|---|---|---|
| `aircargo-dismissal-order` | 4.8 / 56.7 | 52.4 / 91.1 | 104.0 / 120.9 |
| `aircargo-leave-sources` | 5.3 / 56.7 | 70.5 / 115.0 | 65.4 / 34.9 |
| `aircargo-leave-compensation` | 5.6 / 60.6 | 58.0 / 155.6 | 66.7 / 33.5 |
| `aircargo-leave-risk` | 22.6 / 68.1 | 97.7 / 377.9 | 70.9 / 41.3 |

## Forecast and outcome

| Forecast, written before the first request | Outcome |
|---|---|
| Contention **yes**, a median ratio ≈ 0.3–0.45 | **yes**, 0.2594: below the range |
| Net **faster** at step 0's pace, a wash at V4's | **faster**, −47.009 s: the sign alone |
| B pays ≈ 48 s of load in its answer | its first chunk less A's, a median +22.394 s |
| B may save as much in its retrieval | its retrieval less A's, a median −99.930 s |
| A run's first question ≈ 655 s | 478.2 s (B, s1-baba) and 326.7 s (A, s1-abab) |
| A later question ≈ 440 s | 281.7–715.8 s, a median 365.8 s |
| A run ≈ 36 min | the samples span 32.6 and 25.3 min |
| ≈ 1 h 20 min of the Mac | 76 min from the environment line before run 1 to the one after run 2 |

## What it says

- **Contention: yes.** Without the model, B's rerank took a median 0.2594 of A's on four
  readable pairs, below the forecast's 0.3–0.45. Three pairs lie at 0.1093–0.3037. The fourth,
  `aircargo-dismissal-order`, went the other way (1.3281). Leaving any one pair out keeps it
  yes, at 0.2151–0.3037.
- **Net: faster, by its sign alone.** Two pairs were faster in B (−141.810 and −424.565 s) and
  two slower (+47.792 and +151.784 s). The median, −47.009 s, is the mean of the middle two.
  Within 90 s of zero the spec reads its sign alone.
  Leaving out either faster pair turns it to +47.792 s, not faster; leaving out either slower
  one gives −141.810 s.
- **Where B's seconds went** (printed): B's retrieval took a median 99.93 s less than A's. Its
  answer's first chunk took a median 22.394 s more: its model's load and whatever else a fresh
  process pays, against the forecast's ≈ 48 s of load. Its first token came a median 66.944 s
  sooner.
- **The memory beside it** (printed, the whole Mac's): inside A's reranks the Mac faulted back a
  median 2,508.569 MiB of pages (16.086 MiB a second), inside B's 152.879 MiB (4.306).
  At A's rerank's start 11.8–53.2 MiB were free, at B's 748.1–3,080.3 MiB.
  - At A's rerank's start
    llama-server's footprint was 2,998–3,871 MiB
    and its RSS 5.2–2,913.4 MiB. In two A asks almost all of the model sat in the compressor
    (RSS 5.2 and 8.9 MiB; compressed 3,869 and 3,842 MiB).
- **The vector search was slow in both arms:** 52.4–104.0 s, against V4's 4.8–22.6 s for these
  four; B over A, a median 1.038. Unloading the model did not speed it.
- **The pace was the shared Mac's:** A's reranks took 91.1–377.9 s against V4's 56.7–68.1 s for
  the same questions, with the model resident in both.

## What it means for stage 4

- **Item 1 has its answer at A's footprint: the resident model costs the rerank.** Without the
  model the rerank took a median 0.2594 of its time, and less than a third on every pair but the
  first question's.
- **B is a candidate for item 5's unload policy (every request), no more.** Its net gain is a
  sign on four pairs, and item 5 measures a policy in its 30-question series first.
- **Step 3 reads K's rerank seconds with the retrieval alone,** so this contention stays out of
  K's work ([its spec](../specs/stage4-step3-k-timing.md)).

## What it does not say

- Four pairs of one corpus, one stand, one day, on a Mac other projects shared. It says where the
  rerank's seconds go at A's footprint: not the product's speed (item 7), nor a 30-question
  series (item 5). K = 20 only, and nothing on quality.
- **No lever is adopted on four pairs:** a faster B is a candidate for item 5's unload policy,
  measured there in its 30-question series first.
- **The reading holds at A's young footprint, not for V4's long series.** A's model had served
  at most one question. A yes says the resident model costs the rerank even so; what a footprint
  grown by gigabytes costs is not measured.
- **The mechanism stays open:** `vm_stat` and the swap are the whole Mac's, and a fault is a
  window's by its time, not by its process. B frees the weights and the prompt cache at once,
  and step 1 cannot tell their shares apart. Nor can it tell which of the two encoders waits,
  beyond the vector search's and the rerank's own seconds.
- B's load is read as its answer's first chunk less A's: the load and whatever else a fresh
  process pays, not told apart.
- A question's two asks were 47.3–50.4 min apart
  in two runs, against the spec's ≈ 36. The shared Mac's pace can move between them, and four
  pairs average that only so far.

## Files

| File | Bytes | SHA-256 |
|---|---|---|
| `step1.json` | 38,453 | `c3b5ad317fcfea93e807a3651011bbceea692514c14424bbb601bf17cf7c762b` |
| `s1-baba.step1.json` | 18,242 | `f0f214ee3e6902f0a5efcfd7ac2cb70682cf00db604556a525d6bc315771898f` |
| `s1-abab.step1.json` | 18,188 | `8fa78a96df26e044ada25f3008619dd577dced4d071a3c822c4b199ab3a841b7` |
| `s1-baba.q1.step1.json` | 7,398 | `e08075e0d09dc97fb4d782ba1a668493c926cd9153be2f59e7451d4f0253dfd0` |
| `s1-baba.samples.jsonl` | 249,564 | `1271d4358c7ab011efb4106875e838a633d7395a7b0790e36ae62d02b11e82d5` |
| `s1-abab.samples.jsonl` | 194,286 | `3daca175ed48f8c4becbc937f83b150884ad22e6a20c2e9239b017c19948ec02` |
| `environment.jsonl` | 1,964 | `75b50d60adcfa20c2045d2035a9df0d72a29e69562afd5ba8454637a9fd24551` |
