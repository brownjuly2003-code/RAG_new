# Session handoff 2026-10-30 — stage 4: items 4 and 5 read; item 5a's INT8 registered, its block 1 passed, the series resumes at block 2

> **Superseded** by the next session's handoff,
> [item 5a's blocks 2–5 passed and block 6 ran on; the audit of 2026-10-30 taken into PLAN](session-handoff-2026-10-30-stage4-step5a-block6.md),
> which keeps this file's item 5a model, exits table, record steps, glossary and «Do not» in
> force. PLAN's F4 edit of 2026-10-30 overturns «They reopen neither item 6 nor stage 5» for
> INT8 if its five changes on any question.

The session ran 2026-10-29 21:48 UTC – 2026-10-30 ≈ 09:53 UTC. All times are UTC; the laptop's
clock is EDT (git's `-0400`) and the Mac's UTC+3. The previous handoff
([step 2 and step 2b read, the continuation not adopted; the probe ready to register](session-handoff-2026-10-29-stage4-step2b-read.md))
still holds for its model, its glossary and its «Do not». Its next actions 1 and 2 are done, and
3 up to item 5a; this file's next actions replace them. Stage 7 step 1's model stays in the handoff
before it ([step 2 running](session-handoff-2026-10-29-stage4-step2-running.md), «Stage 7 step
1: the arms at M3», and its next action 6).

## Read this first

- **Stage 4** cuts the chat's median answer of ≈ 320 s on the Mac (i5-7500, 4 cores, 8 GB) with
  levers that lose no quality ([PLAN.md](../../PLAN.md) stage 4). Each speed lever is measured on
  the idle Mac and recorded; none is adopted. Adopting one is Julia's word (§8.3; the reranker's
  runtime §9). Only the hints' reorder, `43874fc`, is in the code.
- **Read this session,** each with its record (the numbers are the records'):
  - **Step 2b:** not held, on the catches; the self-evaluation's default stays `classic`
    ([record](../evidence/stage4-step2b-record.md)).
  - **Stage 7's probe:** G2, the entity extraction's cost, failed at the first look; E stops
    ([record](../evidence/stage7-entity-probe-record.md)).
  - **Item 4, the answer prompt's window,** counted without a model on stage 2's lists: the
    smallest window without a detected loss of gold in «sent» is num_ctx 3,584, a step above the
    forecast's 3,328; aircargo's answer prompt is a median 456 estimated tokens shorter there
    ([record](../evidence/stage4-step4-record.md)).
  - **Item 4's hints:** since `43874fc` the chat draws the answer, its sources and badge and
    frees the input before the suggested questions, which follow in their own stream event;
    an E2E in Chromium, red on `2fc3ff0`.
  - **Item 4b, the window timed live:** 3,584 reads the answer's and the self-evaluation's
    prompts faster on 12 of 12 pairs (p 0.000488), a median 24.7 s less, a ratio 0.792; one
    route went to `human` at 3,584; no window adopted
    ([record](../evidence/stage4-step4b-record.md)).
  - **Item 5, thirty questions under `cache-ram = 1024`** (her «да» of 2026-10-29): the swap
    holds, −180.25 MiB from questions 6–10 to 26–30 against `19beeb1`'s +4,452 MB without the
    limit; the line was removed after the series; the limit is not adopted
    ([record](../evidence/stage4-step5-record.md)).
- **Item 5a, INT8 of the product's reranker, runs in parts.** It was registered in `d9f9fd8`
  before the first question was scored in ONNX; `ee0226a` filled in `<c>`
  ([spec](../specs/stage4-step5a-int8-reranker.md)). Its block 1, the FP32 export's fidelity
  on aircargo's thirty, ran 08:28–08:43 and passed. The largest difference from stage 2's
  recorded scores was **5.126e-06**, under the tolerance 1e-3. The series stopped after it on
  its stop file, as the spec's «Running it» step 3 says. Next come blocks 2–6, ≈ 2.5 h of the
  idle Mac, then the read and the record ([below](#item-5a-int8-of-the-reranker)).
- **One forecast line already missed.** The spec forecast FP32 «by less than 1e-6, as on the
  made-up pairs» (1.19e-7 there). The real pools gave 5.126e-06: 5× the forecast, 1/195 of the
  gate. The record's capsule must say so; no reading changes.
- **Not pushed:** 43 commits after `7caaf21`, this stop point's the last. The push needs her
  word and a full ci_local run, never during a live Mac measurement.
- **Open for her, one question, not yet asked: the lever package** (PLAN §8.3 item 2).
  - K = 14 (step 3) and num_ctx 3,584 (item 4) change the answer's path. Together they cost one
    re-answer: item 6, ≈ 6–8 h of the Mac, and stage 5, ≈ 17–30 h; ≈ 23–38 h in all (PLAN
    item 3).
  - The levers «с её настройкой» are the cache cap (item 5), INT8 (5a, once read) and n-gram
    (once measured, if its answers are byte-equal). They reopen neither item 6 nor stage 5:
    INT8's quality is its own comparison's gold on the 400. Item 7's final timing measures them
    with the rest.
  - Ask once, when 5a and n-gram are read, as one yes/no on a recommended package. Do not ask
    lever by lever (memory «Decide by the product goal»).
  - Her other open items are CURRENT_STATE's «Open for Julia».

## Julia's words in this session (UTC)

- 21:48, pasted: «продолжи доработку. Начни с последнего handoff:
  docs/operations/session-handoff-2026-10-29-stage4-step2b-read.md … и выполняй его Next actions
  по порядку: 1) запись шага 2b …; 2) проба этапа 7: регистрация спеки, прогон на свободном Mac,
  чтение, запись; 3) п. 4 плана этапа 4 (короче промпт и подсказки). Агентов не запускать
  параллельно. Режим самооценки по умолчанию не менять. Без пуша. cache-ram 1024: да.»
  1–3 are done. «cache-ram 1024: да» covered item 5's series alone and is spent.
- 08:33 «в итоге проект движется к финалу?» — my answer, by PLAN §2's six criteria:
  - Ч (the handover signal): done in substance; the handover line is under every answer.
  - С (speed and memory, her SLO): in progress, stage 4.
  - К (quality on the final path): stage 2's numbers stand unless the path changes.
  - Р (prod as a service): prepared, not installed; her word.
  - П (search mechanisms): E stopped; stage 7 step 1 is a draft.
  - О (publication): her gate.
  - The re-measurement the path levers bring is ≈ 35 h of the Mac.
  - Two slips in that answer, against PLAN: I counted INT8 among the path levers, which §8.3
    does not, and gave stage 5 as ≈ 25–33 h, stage 2's figure, for its ≈ 17–30 h. The
    package question should give her PLAN's grouping and ≈ 23–38 h ([above](#read-this-first)).
- 08:38 «сессия очень долгая. вероятно ее стоит закрыть?» — my answer: yes, at a clean
  boundary: block 1's end, this file and a wip backup.
- ≈ 08:39, mid-turn: «и продолжить в новой» — the next session starts from this file.

## What this session did

The commits, all local, in order:
- `bbbc2c9` — step 2b's record: capsule, artifact test, index row, status lines.
- `52dd160`, `27e21fd`, `e0f5185` — the probe registered, `<c>` filled in, read.
- `b192fb0`, `b2a4d8b`, `2fc3ff0` — item 4's window count registered, `<c>` filled in, read. At
  3,328 the three bases with gold together lose 127 against 137 of 250 (b 10, c 0, p 0.002).
- `43874fc`, `0c54cb8`, `27dcde9` — the hints after the answer, with its E2E; a test-order fix
  (an earlier module's teardown took stage 2's tools off `sys.path`); the status lines.
- `d1ef9e5`, `d6af746`, `4524de1` — item 4b registered, `<c>` filled in, read.
- `f214459`, `2b44bb6`, `b80ac96` — item 5's series registered, `<c>` filled in, read. The 30
  questions took 2.93 h against a forecast of 2.3–2.7 h: five of them ran 499–516 s.
- `d9f9fd8`, `ee0226a` — item 5a registered, `<c>` filled in.
- ≈ 08:20–08:43 — 5a's worktree; the series started at 08:24, block 1 ran 08:28–08:43, then the
  stop.
- This stop point's commit: this file and the status lines.

## Item 5a: INT8 of the reranker

**Why.** The product reranks each question's candidate pool with `BAAI/bge-reranker-v2-m3`, a
cross-encoder in PyTorch. Stage 2 recorded it at a median 26.8 s a question on aircargo
(13.9–47.5 s); in the chat it took 102 s against 27 s idle. INT8 in ONNX Runtime 1.23.2
promises ≈ 1.8×: the export's card says so, and the made-up pairs gave 40.3 s → 22.3 s a call
of 32. But another card's own INT8 kept the first document on only 0.625 of its queries. So
the gold is read beside the seconds: a faster reranker that changes the five is another product.

**How, without an answer model.** Stage 2's runs recorded each question's pool: the lanes, the
chunk ids and PyTorch's scores. A block scores the same pools. The product's own selection code
(`k_curve.Selection` at K = 20: `_rrf_merge`, then `_rerank_scored_with_status`, cut at five)
then gives the five the answer would see. Stage 2's gold read (`scripts/external_pilot.read_gold`,
with the parent expansion) scores them on the 250 questions with gold. Not read here: the chat's
seconds, memory as a gain, other schemes (the spec's «Not said»).

**The export** (`reports/stage4-step5a/tools/export_onnx.py`; its manifest
`reports/stage4-step5a/onnx/manifest.json`, SHA-256 `9888d92b…`, pins every file in `$M`):

| Arm | `$M/<arm>/model.onnx` | Max diff from PyTorch (made-up pairs) | s a call of 32 |
|---|---|---|---|
| `pytorch` | — (sentence-transformers' CrossEncoder, the product's) | — | 40.3 |
| `fp32` | 0.64 MB + 2.27 GB `.data` | 1.19e-7 | 36.1 |
| `int8` | 571 MB, QInt8, per channel, reduce_range | 0.0035 | 22.3 |
| `int8_u8u8` | 571 MB, QUInt8, per channel — the fallback | 0.0041 | 25.8 |

`reduce_range` is ORT's remedy for its INT8 kernel's saturation on AVX2 without VNNI, as on this
i5-7500. The tool's own pre-check on the made-up pairs, one process an arm, put the peaks at
2,881 MiB (PyTorch), 3,291 (FP32) and 3,187 (`int8`). INT8 does not save memory, as the card says.

**The schedule** (the tool's `SCHEDULE`; every block a process of its own):

| Block | Arm | Questions | Read for | Forecast |
|---|---|---|---|---|
| 1 | `fp32` | the thirty | fidelity ≤ 1e-3 | ≈ 13 min — **done**, 14.6 min |
| 2 | `pytorch` | the thirty | speed A; stops above 1e-6 | ≈ 14.5 min |
| 3, 4 | `int8` | the thirty | speed B, B | ≈ 8 min each |
| 5 | `pytorch` | the thirty | speed A; stops above 1e-6 | ≈ 14.5 min |
| 6 | `int8` | the 400 | the fives and the gold | ≈ 1.75 h |
| 7–11 | as 2–6 for `int8_u8u8` | | only after `int8`'s gold loss | ≈ 3 h more |

**Block 1's facts** (its head and end lines, read on the Mac):
- load 4.6 s;
- 30 timed questions, a median 24.4 s (16.5–78.3), 826.9 s in all;
- the warm-up 20.8 s;
- RSS 1,654 MiB after the load, a peak of 2,908 MiB;
- torch imported, by the tokenizer.
- Beside it, no question was disturbed. The other processes took a median 3% CPU, at most 25.8%;
  Ollama held no model; the swap stayed at 2,061 MB.
- The 5-minute load of ≈ 5 came from the block's own four threads: the others' CPU stayed low.
  `01.jsonl` SHA-256 `3b6d2952…`.
- `blocks.out` holds `tokenizers`' fork warning. After the block's first fork once the tokenizer
  has run (a `ps` of the beside-sample), it turns its own parallelism off. Every block samples
  the same way, so the arms stay alike; the made-up pairs' timings had no fork.
- For scale: stage 2's PyTorch took 829 s for the same thirty and a 31st question.

**How each outcome reads** (the tool's `speed`, `quality` and `outcome`, frozen in the spec):
- **Gold.** By base with gold and pooled, after the expansion: b is gold in PyTorch's five only,
  c in the variant's only.
  - A loss: any base or the pool reads «loss» by the exact McNemar, or the pooled b − c is
    above 2.
  - `NOT_EVIDENCE`: a base has more than 5 rows the read cannot resolve.
- **Speed.** Per question, the mean of blocks 2 and 5 against the mean of blocks 3 and 4, by the
  exact two-sided sign test. «Faster» needs p < α = 0.05 with more questions faster; else
  «slower» or «no detected difference». `NOT_EVIDENCE`: fewer than 25 of the 30 questions
  undisturbed in all four blocks.
- **The outcome.** `int8` passes when its gold holds and it reads faster. A gold loss runs the
  fallback, blocks 7–11, read the same way. Both losing: no INT8 file passes.
- **A trap: after blocks 1–6, `int8`'s gold loss prints `"outcome": "pending"`,** not a loss.
  Block 11 does not exist yet, so the fallback's gold is `None`. Read
  `variants.int8.quality.reading` in `record.json`: `loss` sends you to next action 1.6, the
  fallback.
- **The forecast:**
  - `int8` faster on 30 of 30, a ratio ≈ 1.8, ≈ 11–12 s saved of ≈ 26 s;
  - its five the same set on ≈ 85% of the 400, at least four shared on ≈ 99%;
  - the gold holds, pooled b − c within ± 2;
  - the peak RSS not below PyTorch's.
- **What to tell her,** by the record's `outcome`:
  - **`int8` passes:** INT8 keeps the gold on stage 2's pools, its five stage 2's set on X of the
    400. It is N× faster on aircargo's thirty: a median S s saved of P s
    (`speed.saved_sec_median` of `speed.pytorch_sec_median`). Next comes the short live series
    (below). The runtime is her word (§9).
  - **`int8_u8u8` passes:** the same, naming the file, and saying `int8` lost the gold (the
    base, b and c) and the fallback kept it.
  - **The gold holds, the speed «no detected difference» or «slower»:** no gain; the lever
    closes.
  - **Both files lose the gold** (`variant` null): no INT8 file keeps the quality; the reranker
    stays PyTorch.
  - **`NOT_EVIDENCE`** (fidelity, gold or speed): name the cause (disturbed questions,
    unresolved rows), give no number, and say what a rerun would need.
  - **The series stopped on 6, 7 or 9, or `read` refused:** there is no record of numbers. Name
    what stopped it ([the exits](#next-actions)) and its cause.
- **The short live series,** PLAN 5a's «затем короткая живая серия», follows only a pass, before
  the package question. My reading, not decided: the chat's reranker loads PyTorch today, so the
  series needs the product to load the ONNX file behind a setting that defaults to PyTorch. That
  is code with a spec and an E2E of its own; adopting INT8 in production stays her word (§9).

## The n-gram lever, 5a's second

- PLAN: «n-gram-декодирование — llama-server без Ollama на том же GGUF и тех же флагах: сначала
  база без speculation, затем `--spec-type ngram-simple`. ≈ 2–3 ч. Найденный тест дал и
  ускорение, и замедление.»
- Found this session, from `--help`: Ollama 0.33.2's llama-server,
  `/Users/julia/RAG_new_tools_ollama_v0.33.2/llama-server` (version 0.3.0-dev, commit
  d222767c7), takes `--spec-type ngram-simple` with `--spec-ngram-simple-size-n` (default 12),
  `--spec-ngram-simple-size-m` (48) and `--spec-ngram-simple-min-hits` (1).
- No spec yet. It has to settle these before the first request (my suggestions, not decided):
  - the GGUF, by Ollama's digest;
  - the runner's flags as Ollama starts them, read from `ps` of the runner, as
    `.tmp/s7probe/runner_flags.sh` did for the probe;
  - Ollama holding no model during the run, for the 8 GB;
  - the prompts: aircargo's saved V4 prompts, so no retrieval runs;
  - the product's sampling settings, read from the code;
  - the measure: ABBA by question on the decode's seconds from llama-server's timings;
  - whether the answers' text is byte-equal. Speculation verifies each drafted token, but a
    batch of drafted tokens can round differently: read it, do not assume it.

## Stage 7 step 1

- Its model and steps: the [earlier handoff](session-handoff-2026-10-29-stage4-step2-running.md),
  «Stage 7 step 1: the arms at M3» and next action 6.
- Item 4 is read and no window is adopted, so V4's prompts stand and the replay builds them as
  they are. If she adopts 3,584 later, the product's prompts change, and the replay's must be
  built again on the new window.
- Changed this session: the spec draft's line 44 names E's stop with the probe's record.
- SHA-256 on disk at the stop point:
  - `vectordb/_base_manager.py` (M), the S fix, `44cf16b6…`;
  - `tests/test_graph_retriever.py` (M) `49933e9d…`;
  - `reports/stage7/tools/arms_replay.py` `f1bde2e0…`;
  - `tests/test_stage7_arms_replay.py` `78cb1f69…`;
  - `docs/specs/stage7-step1-arms-m3.md` `006fa73e…`, new;
  - `scripts/gr1b_stage_replay.py` (M) `e5c987dc…`;
  - `scripts/gr1b_seed_expansion.py` (M) `5756955f…`;
  - `tests/test_gr1b_stage_replay.py` (M) `9e3cfe14…`.
- The S fix and GR-1b's three go in one commit: GR-1b's test fails without them.
- Tell her the gate's change for answers in the message that registers it. The draft opens
  answers on no detected M3 loss, only on the questions whose prompt changes; PLAN opens them
  «только для лучшей руки и только если М3 выросла больше MDE».

## Next actions

1. **Item 5a, blocks 2–6** (the spec's «Running it» 3–5; [glossary](#glossary) for the names).
   1. **Before any start,** check that nothing of 5a runs:
      `ssh deproject-mac 'pgrep -fl "[i]nt8_reranker" || echo none; tail -n 2 /Users/julia/RAG_new_s4p5a_runs/series.log; ls /Users/julia/RAG_new_s4p5a_runs/stop'`.
      Expected: `none`; this first time also the last line `… stop file` and the stop file
      listed. The series has no lock: two series on one `$O` would run one block into one
      partial file.
   2. **The start,** from the laptop:
      `ssh deproject-mac 'rm /Users/julia/RAG_new_s4p5a_runs/stop'`, then
      `ssh deproject-mac 'bash -s 6' < D:/RAG_new/.tmp/s5a/series.sh`. It prints the series'
      pid; without a second argument no stop helper starts.
      - The series keeps block 1 and checks it again.
      - Before block 2 it waits for the idle checks and a 5-minute load under 2; before each
        later block, for the idle checks without the load.
      - Then it runs blocks 2–6, ≈ 2.5 h.
   3. **The wait:** one background ssh loop on that pid (`run_in_background`), capped at 4 h:
      `ssh -o ServerAliveInterval=30 deproject-mac 'end=$(( $(date +%s) + 14400 )); while kill -0 <pid> 2>/dev/null && [ $(date +%s) -lt $end ]; do sleep 60; done; kill -0 <pid> 2>/dev/null && echo STILL_RUNNING || echo SERIES_EXITED; tail -n 3 /Users/julia/RAG_new_s4p5a_runs/series.log'`.
      At the cap, with the pid alive and the log moving, arm it once more: an idle wait of up to
      an hour before each block is the rule. Never kill the series.
      - While it runs: no tests and nothing heavy on the Mac, no Ollama request, and no ssh
        command whose text holds a word of the pattern (`pytest`, `_supervisor`, `replay.py`,
        `step0_`–`step3_`, `limactl`, `llama-server`). The beside-sample sees such a command in
        `ps` and marks the question disturbed, or the idle wait holds. Next action 2's `--help`
        and `ps` wait for the end.
   4. **The exit.** The series runs under `nohup`, so its code is not seen; the last line of
      `$O/series.log` names it:

      | Last line | Exit | What follows |
      |---|---|---|
      | `SERIES_DONE` | 0 | the read, 5 |
      | `stop file` | 3 | someone touched `$O/stop`: 1, then 2 |
      | `the Mac not idle within an hour` | 4 | no attempt spent: 1 and 2 once it is idle |
      | `block N failed: exit 5` | 5 | killed as slow, its files in `$O/rejected/`; once the cause is read, 1 and 2 give its second attempt |
      | `block N failed: exit 6`, `another tool started this series` | 6 | the stand; the reason in `$O/blocks.out` (`block N: …`) |
      | `block N fidelity: … above …` | 7 | holds at every start; on block 2 or 5, PyTorch did not give stage 2's scores |
      | `block N failed: <reasons>`, or `… exit 1` | 8 | the gate, a traceback in `$O/blocks.out`; once the cause is read, 1 and 2 give the second attempt |
      | `block N kept but failing: …` | 8 | a kept file fails at every start |
      | `block N failed twice` | 9 | the series ends |
      | nothing new, the pid gone | — | the series crashed: `$O/series.out` |

      On 6, 7, 9 or a kept failure, do not start again. The spec has one path, for a fault of
      the tool: a marked error fix and a new `$O`. A fault of the stand (packages, snapshot,
      threads) lies in the ML venv, which is `RAG_Support_Assistant`'s: leave it alone without
      her word. The comparison then has no reading: write the stop down (a capsule and an index
      row, no numbers) and tell her the cause.
   5. **The read,** on `SERIES_DONE`, on the Mac:
      `ssh deproject-mac 'cd /Users/julia/RAG_new_s4p5a; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/julia/RAG_new_mf_gate_site /Users/julia/RAG_new_gr4_venv/bin/python reports/stage4-step5a/tools/int8_reranker.py read /Users/julia/RAG_new_chat_5e308fe/chatlive/runs /Users/julia/RAG_new_external_s1 /Users/julia/RAG_new_ort/bge-reranker-v2-m3 /Users/julia/RAG_new_s4p5a_runs /Users/julia/RAG_new_s4p5a_runs/record'`.
      It prints the fidelity and the outcome and writes `$O/record/record.json` and
      `rows.jsonl`. `"pending"` after blocks 1–6 is the trap
      [above](#item-5a-int8-of-the-reranker): check `variants.int8.quality.reading`. A `read`
      that exits with a message writes nothing; that is a stop, as in 4.
   6. **The fallback,** only on `int8`'s gold loss: 1, then
      `ssh deproject-mac 'bash -s 11' < D:/RAG_new/.tmp/s5a/series.sh`, ≈ 3 h; no `rm`, the stop
      file is gone. It keeps blocks 1–6 and runs 7–11. Then 3–5 again.
   7. **The copy,** as bytes: `mkdir -p D:/RAG_new/reports/stage4-step5a/d9f9fd8`, then for each
      of `record.json` and `rows.jsonl`
      `ssh deproject-mac 'cat /Users/julia/RAG_new_s4p5a_runs/record/record.json' > D:/RAG_new/reports/stage4-step5a/d9f9fd8/record.json`.
      `ssh deproject-mac 'shasum -a 256 /Users/julia/RAG_new_s4p5a_runs/record/*'` and
      `sha256sum D:/RAG_new/reports/stage4-step5a/d9f9fd8/*` must agree. Not `scp` to a `D:/`
      path: scp reads `D:` as a host.
   8. **The record:**
      - the capsule `docs/evidence/stage4-step5a-record.md`;
      - `tests/test_stage4_step5a_artifact.py`, on `tests/test_k_curve_artifact.py`'s model. It
        loads the tool by importlib, rebuilds the gold's readings from the rows, and checks the
        provenance and the capsule's tables. `rows.jsonl` has no seconds and the blocks stay on
        the Mac, so the speed is checked from the record's counts alone: `faster` and `slower`
        through the sign test to the reading;
      - `ruff format` and `ruff check` on the new test, in the laptop venv;
      - the spec's Status line. Keep «registered before the first question was scored in ONNX»
        and «Forecast, written before the first question was scored» each on one line: the
        tools test pins both;
      - the row in `EVIDENCE_INDEX.md`;
      - the status lines, in place: CURRENT_STATE 4, 99 and 100 (150 lines exactly), PLAN 5a,
        ROADMAP's row 4, BACKLOG's first item, docs/README's 5a paragraph;
      - the Mac tests on the bytes to commit. Copy `.tmp/s4p4/ev4b_gate.py` to
        `.tmp/s5a/rec_gate.py`, with FILES the capsule, the spec, the two copied files, the
        artifact test and the six status files, and TESTS `docs_gate.TESTS` (35 files: the
        docs tests and the tests that read the root files) plus both 5a tests. Through
        `.tmp/s4p4/tool_gate.py` it builds HEAD plus FILES in a temporary index and ships that
        tree, so the drafts stay out;
      - one commit, `evidence(stage4-step5a): …`. Item 5a is no slice by the acceptance rule;
        the spec says so.
   9. **Tell her** the outcome in her terms ([above](#item-5a-int8-of-the-reranker)).
   10. **After a pass, the short live series** ([above](#item-5a-int8-of-the-reranker)): its
       spec, the product's setting, the E2E, the run, the record.
2. **The n-gram lever:** its spec, registered before the first request; the run on the idle Mac;
   the read; the record.
3. **Stage 7 step 1**, as [above](#stage-7-step-1).
4. **The lever package**, one question to her, once 5a and n-gram are read. Items 6 and 7 follow
   her answer.
5. **The push**, only on her word, after a full ci_local run (memory «Before asking for a push»).

**Do not:**
- create or touch `/Users/julia/.config/llama.cpp/config.ini` without her word: item 5's «да»
  is spent;
- change the self-evaluation's default: step 2b closed it;
- run tests or another heavy job on the Mac while a block runs;
- edit the 5a tool, its test or the export. Their SHA-256 are in the spec and go into the record.
  A fault of the tool is a marked error fix and a new `$O` (the spec's Stops);
- delete `$O`, `$W` or `$M` before the record is committed;
- commit stage 7 step 1's or GR-1b's drafts before their Mac tests on the bytes committed;
- start a second subagent while one runs; no MyFlow; Codex (cw) only as a second opinion;
- commit `demo/phase-e-raw.webm` or `reports/ask100/`, or push without her word.

## State at the end

- **Mac:**
  - The series exited at 08:43:09 on its stop file, exit 3. `$O/stop` stays until next action
    1.2 removes it.
  - `$O/blocks/01.jsonl` is kept; `$O/rejected/` is empty.
  - No 5a process; Ollama holds no model; `~/.config/llama.cpp/` does not exist: item 5's
    guard removed the line and the folder.
  - The worktree `$W` is at `d9f9fd8`, clean.
  - Scratch that may go: `/Users/julia/RAG_new_s4p5a_dry` (the dry read before registration)
    and `/Users/julia/RAG_new_ort/precheck` (the pre-check's scores).
- **Committed at the stop point:** this file; the superseded note in the previous handoff;
  CURRENT_STATE lines 4, 99, 100 and 150; BACKLOG's first item; docs/README's latest handoff.
- **Laptop, not committed:**
  - stage 7 step 1's five files and GR-1b's three;
  - `.tmp/s5a/` (this stop point's scripts, `series.sh`, the wip script), `.tmp/s5/`,
    `.tmp/s4p4/` (`tool_gate.py` among them), `.tmp/s2bcap/`, `.tmp/s7probe/`;
  - `.tmp/ask100-split/sync_commit.py`, which `tool_gate.py` calls to ship a tree to the Mac.
- **Backup:** the branch `wip/stage4-step5a-block1-stop` ([Verification](#verification)).
- **No Monitor, agent or background job** of this session runs after it closes.
- **Not this session's:** `demo/phase-e-raw.webm`, `reports/ask100/`.

## Glossary

The previous handoffs' glossaries hold, but for 5a this file's terms replace theirs: in the
2b glossary `$R` is V4's runs, `$T` step 2b's directory and `stand` the probe's reason.

- **Arm** — what scores a block: `pytorch`, `fp32`, `int8` or `int8_u8u8` (table above).
  **Variant** — `int8` or `int8_u8u8`, the two read against PyTorch.
- **Block** — one schedule entry in a process of its own. Its file is `$O/blocks/NN.jsonl`, and
  `NN.partial.jsonl` while it runs. It holds:
  - a head line: the stand, the packages, the load, the RSS;
  - a line a question: the scores, the seconds, what ran beside;
  - an end line: done, the RSS peak, whether torch was imported.
- **The thirty** — aircargo's first 30 questions of stage 2, timed after one warm-up question.
  **The 400** — stage 2's questions, 100 a base. **With gold** — 250 of them: WixQA 100,
  ConditionalQA 80, MultiHop-RAG 70; aircargo has none.
- **Fidelity** — a block's largest score difference from stage 2's recorded scores. FP32 holds at
  ≤ 1e-3; a PyTorch block stops the series above 1e-6, exit 7.
- **ABBA** — blocks 2–5, PyTorch, INT8, INT8, PyTorch on the same thirty, so drift over time
  falls on both arms.
- **Disturbed** — a question's line where a process matched the pattern
  `pytest|_supervisor|replay\.py|step[0-3]_|limactl|llama-server`, Ollama held a model, or the
  others took over 100% CPU.
- **Idle** (before a block) — none of the above, no `$HOME/ci_local/.lock_ci-local`, and before
  the first block a start runs, a 5-minute load under 2. It waits up to an hour, then exits 4.
- **Beside-sample** — the tool's `sample()`, taken with each question and in the head line: the
  pattern's processes, the others' CPU, Ollama's models, the load and the swap.
- **The stand** (5a) — the tool's `stand()`: the export's manifest by SHA-256, the packages'
  versions, the cached snapshot and the arm's files by SHA-256; a block also exits 6 on other
  than 4 threads.
- **The five** — the product's selection for the answer: the recorded lanes merged by RRF, reranked
  by the block's scores, cut at five; K = 20. **Expansion** — the product's parent expansion of the
  five before gold is read.
- **b, c** — gold in PyTorch's five only, in the variant's only; the exact McNemar on them.
- **`NOT_EVIDENCE`** — a reading the rules refuse to make. It is never a pass.
- **α** — 0.05 (`no_rerank_point.ALPHA`), for the sign test and the McNemar.
- **The stop file** — `$O/stop`. The series stops before its next block, exit 3. Other exits: 4
  idle, 5 slow, 6 stand, 7 fidelity, 8 gate, 9 twice (the spec's Stops).
- **Paths** (the Mac):
  - `$G` `/Users/julia/RAG_new_mf_gate`, the gate checkout;
  - `$W` `/Users/julia/RAG_new_s4p5a`, its worktree at `d9f9fd8`;
  - `$O` `/Users/julia/RAG_new_s4p5a_runs`;
  - `$M` `/Users/julia/RAG_new_ort/bge-reranker-v2-m3`, the export;
  - `$R` `/Users/julia/RAG_new_chat_5e308fe/chatlive/runs`, stage 2's runs `p2-*`;
  - `$D` `/Users/julia/RAG_new_external_s1`, the chunk archives;
  - `$PY` `/Users/julia/RAG_Support_Assistant/.venv/bin/python`, the ML venv;
  - `$SITE` `/Users/julia/RAG_new_mf_gate_site`.
- **The gate env** — `/Users/julia/RAG_new_gr4_venv/bin/python` with `PYTHONPATH=$SITE`: the
  product's retrieval code, no model. The read runs there.
- **The card** — the export's card in research 6: ≈ 1.8× on a 4-thread AVX2 CPU, a process no
  smaller. **Another card** — one whose own INT8 kept the first document on 0.625 of its queries.
- **The made-up pairs** — the export's 32 synthetic pairs, English and Russian, 59–445 tokens:
  no corpus text.
- **Ч, С, К, Р, П, О** — PLAN §2's done criteria.
- **Item 6, item 7, stage 5** — PLAN: stage 4's item 6, aircargo's 100 answers again on the
  final path with the judge, if K or the prompt changed; item 7, the final timing, 30
  questions on the idle Mac, then the SLO she names; stage 5, the external bases' 300
  answers again, if stage 4 changed the path.
- **G2** — the probe's gate on the entity extraction's cost; it failed at the first look, so
  E stops.
- **«sent»** — item 4's point of reading (`retrieval_summary.coverage`): the documents the
  answer prompt keeps once it is fitted to the window.
- **The catches** — step 2b's count of the 17 targets (answers the judge graded bad, or
  declined) that a self-evaluation flags. Flagged is a score under 80, the stream's route to
  a person.
- **`human`** — the route that hands an answer to a person.

## Lessons

- **Size a synthetic set by the real inputs.** The first export ran made-up pairs of up to
  ≈ 1,400 tokens and crawled. The tokenizer alone on stage 2's pools gave 44–487 tokens. Pairs
  of that length ran the whole export again in ≈ 11 min.
- **A spec's claim needs a source.** «About half the kernel's speed» for `int8_u8u8` had none;
  the smoke showed ≈ 16% slower. It came out before registration.
- **Check a forecast cheaply before freezing it.** «INT8 below PyTorch's RSS» was wrong. The
  tool's own pre-check on the made-up pairs showed it, and the spec changed before registration.
- **Made-up pairs forecast the real ones loosely.** FP32's 1.19e-7 there became 5.126e-06 on
  stage 2's pools: inside the gate, 5× the forecast. Forecast the real pools' spread, not the
  smoke's.
- **A test on hand-made blocks must change every block it reads.** The zero-seconds test zeroed
  block 3 alone, so the mean was not zero. The read test's stand-in lacked `by_document` for two
  bases. Both were test defects, found by the Mac gate.
- **`from transformers import AutoTokenizer` imports torch,** so an ONNX process holds torch too.
- **The gate checkout's HEAD is the gate's overlay commit,** not a moved HEAD. Check the files by
  SHA-256.
- **Read `others_cpu` before blaming a neighbour.** I first put block 1's load of ≈ 5–6 on another
  project; the sample showed 3%. The load was our own four threads.
- **A live series' forecast needs its tail.** Item 5's thirty overran by five questions of
  ≈ 500 s; a median alone forecasts too short.
- **A module's teardown can take another's `sys.path` off.** The full suite found it (`0c54cb8`);
  the focused gate did not.
- **Quote PLAN after a grep, never from memory.** This file's first draft counted INT8 among
  the path levers and gave stage 5 stage 2's hours; I had told her both at 08:33. The cold
  read caught them against §8.3 and stage 5's text.
- **A stop point's handoff says what each exit looks like.** A detached series' code is never
  seen; only its log's last line is. The first draft said «read the Stops» and gave no line.

## Verification

- **Commits:** `git rev-list --count 7caaf21..HEAD` gives 43; this session's 18 run from
  `bbbc2c9` to `ee0226a`, and the stop point's comes after them.
- **Block 1:** `series.log` reads `2026-10-30T08:28:33+00:00 block 1 fp32 thirty, attempt 1`,
  `2026-10-30T08:43:09+00:00 block 1 read: largest difference from the record 5.126e-06` and
  `2026-10-30T08:43:09+00:00 stop file`. The facts above
  come from `01.jsonl`, read on the Mac with Python (`.tmp/s5a/block1_facts.py`). The file's
  SHA-256 is `3b6d29525bd68a0c6261f3b976ed92377b9638dabe940a916aa6afca71f702b3`.
- **The Mac after the stop:** `pgrep` finds no 5a process; `/api/ps` is empty;
  `/Users/julia/.config/llama.cpp/config.ini` does not exist (09:50, the last check).
- **Docs tests:** `docs_gate.TESTS`, 35 files, ran on the Mac on this commit's bytes by
  `.tmp/s5a/stop_gate.py`; the commit message gives the count.
- **The wip branch:** `wip/stage4-step5a-block1-stop`, commit
  `da722a81e31fd9e1df6e30d75e0db2fc26b2d4dc` on `ee0226a`, built through a temporary index before
  the stop-point commit by `.tmp/s5a/make_wip_backup.sh`. Its 180 files:
  - stage 7 step 1's five and GR-1b's three;
  - the previous backup's git-ignored files that still exist;
  - this session's `.tmp/s2bcap/`, `.tmp/s4p4/`, `.tmp/s5/`, `.tmp/s5a/` and `.tmp/s7probe/`;
  - `.tmp/ask100-split/sync_commit.py`, in no branch before it;
  - the stop point's own docs, as they stood before the wip line and the gate.

  None differs from disk by `git hash-object`. It is local, never pushed. Restore only if the
  working tree lost them:
  `git -C D:/RAG_new diff --name-only wip/stage4-step5a-block1-stop~1 wip/stage4-step5a-block1-stop | xargs git -C D:/RAG_new restore --source=wip/stage4-step5a-block1-stop --worktree --`.
