# Stage 4, item 5a: INT8 of the same reranker on stage 2's saved pools — `int8` passes; the gold holds, the five changes — 2026-10-30

The question: on the Mac's CPU, is the product's reranker, `BAAI/bge-reranker-v2-m3`, faster in
ONNX Runtime 1.23.2 with INT8 weights, and does the five the answer reads keep its gold?
[`PLAN.md`](../../PLAN.md) stage 4, item 5a: «Сначала ONNX FP32 против PyTorch, затем INT8, на
сохранённых списках кандидатов этапа 2: пересечение пятёрок, эталон по базам, секунды, RSS».
The spec, [`stage4-step5a-int8-reranker.md`](../specs/stage4-step5a-int8-reranker.md), was
registered with its tool, its test and the export's manifest in `d9f9fd8` before the first
question was scored in ONNX (`ee0226a` wrote the commit into it); nothing changed after it. The
blocks ran on 2026-10-30, block 1 08:28–08:43 UTC, then blocks 2–6 10:04–12:40 UTC, in the
worktree `/Users/julia/RAG_new_s4p5a` at `d9f9fd8`; the series stopped after block 1 on its stop
file, as the spec's «Running it» says. No slice by the acceptance rule: no behaviour, case or
quality number of the path changes (the spec's).

Record: [`reports/stage4-step5a/d9f9fd8/`](../../reports/stage4-step5a/d9f9fd8/):
- `record.json`: the inputs and the export's manifest by SHA-256, the tool and the measuring code
  by SHA-256, the runs' provenance, each block's facts, the attempts, the fidelity, per base the
  blocks' score differences and fives, each variant's speed and gold, and the outcome;
- `rows.jsonl`, a question a line: its id, base and pool size, per block the largest score
  difference and the five's overlap, with gold the points of the recorded five and of `int8`'s.

The blocks' files, with their scores and seconds, stay on the Mac
(`/Users/julia/RAG_new_s4p5a_runs/blocks/`, by SHA-256 in the record).

Every number below is the record's unless named otherwise. The reader is the spec's tool,
[`reports/stage4-step5a/tools/int8_reranker.py`](../../reports/stage4-step5a/tools/int8_reranker.py)
`read`. Checked by
[`tests/test_stage4_step5a_artifact.py`](../../tests/test_stage4_step5a_artifact.py):
- the record was read by the committed tool, the export's tool and manifest by the SHA-256 the
  spec lists, at the registering commit, on stage 2's stand and inputs;
- the fidelity, the fives by base and block, both gold pairs and the outcome are read again from
  the rows with the tool's own functions; the speed's reading follows from its counts by the
  sign test;
- PyTorch's blocks are stage 2's reranker: every score to 1e-6 and stage 2's five on every
  question; the rows are stage 2's 400 with the export's pools;
- the blocks ran the schedule in order, each once; ONNX gave blocks 3 and 4 the same rows;
- the rows hold ids, flags and numbers only;
- every table row below is built from the record, and so is every number of the prose that comes
  from it; the others are the spec's or marked mine.

The record holds no question, document, score file or command line.

## Provenance and method

- **Stand:** stage 2's code `5e308fe`; the interpreter stage 2's stand's; the model's snapshot
  `953dc6f6…` from the Mac's cache, offline; the export's three files in
  `/Users/julia/RAG_new_ort/bge-reranker-v2-m3` by the manifest `9888d92b…`; 4 threads.
- **Inputs:** stage 2's runs of `5e308fe`, 100 questions a base, each question's pool, recorded
  scores and five; the bases' chunk archives; the committed export as the check of both.
- **Blocks:** each a process of its own: it holds the stand, loads its arm, scores aircargo's
  31st question as an unread warm-up, then its questions, one timed call a question. 1 FP32 and
  2–5 PyTorch, `int8`, `int8`, PyTorch on aircargo's first thirty; 6 `int8` on the 400.
- **The reading,** frozen in the spec: the fidelity to 1e-6 for PyTorch and 1e-3 for FP32; the
  speed per question, blocks 3 and 4's mean against 2 and 5's, by the exact two-sided sign test,
  readable when undisturbed in all four; the gold by each base's primary metric after the parent
  expansion, b gold with PyTorch's five only and c with `int8`'s only, by the exact McNemar test:
  a loss at b > c and p < 0.05, on a base or pooled, or at a pooled b − c above 2.

## The reading

| Reading | The spec's rule | Value |
| --- | --- | --- |
| PyTorch's blocks: stage 2's scores | to 1e-6 | the largest difference 0.000e+00 |
| FP32's block 1: the export's fidelity | to 1e-3 | the largest difference 5.126e-06: **holds** |
| int8's speed on aircargo's thirty | faster on more, sign test p < 0.05, 25 readable | 30 readable, faster on 30, slower on 0, p 1.86e-09: **faster** |
| int8's gold after the expansion | a loss: b > c at p < 0.05, or pooled b − c above 2 | pooled b 1, c 4, p 0.375: **holds** |
| The outcome | int8 holds the gold and reads faster | **int8 passes, 1.751×** |

The record rounds the sign test's p to six places, 0.0; the table prints the test's own value.

## The gold, by base

After the parent expansion, deciding:

| Base | With gold | Unread | Pairs | PyTorch's five | `int8`'s five | b | c | p | Reading |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| WixQA | 100 | 0 | 100 | 68 | 68 | 0 | 0 | 1.0 | no detected difference |
| ConditionalQA | 80 | 0 | 80 | 60 | 61 | 1 | 2 | 1.0 | no detected difference |
| MultiHop-RAG | 70 | 0 | 70 | 13 | 15 | 0 | 2 | 0.5 | no detected difference |
| The three pooled | 250 | 0 | 250 | 141 | 144 | 1 | 4 | 0.375 | no detected difference |

Before it, beside:

| Base | With gold | Unread | Pairs | PyTorch's five | `int8`'s five | b | c | p | Reading |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| WixQA | 100 | 0 | 100 | 68 | 68 | 0 | 0 | 1.0 | no detected difference |
| ConditionalQA | 80 | 0 | 80 | 46 | 46 | 1 | 1 | 1.0 | no detected difference |
| MultiHop-RAG | 70 | 0 | 70 | 7 | 8 | 0 | 1 | 1.0 | no detected difference |
| The three pooled | 250 | 0 | 250 | 121 | 122 | 1 | 2 | 1.0 | no detected difference |

## The fives and the scores, printed

Against stage 2's recorded five and scores, by base and block:

| Base | Block | Questions | Same five | Same order | At least four shared | Shared of five, mean | Largest score difference, median | Max |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| WixQA | 6, int8 | 100 | 51 | 22 | 96 | 4.47 | 8.700e-02 | 2.752e-01 |
| ConditionalQA | 6, int8 | 100 | 59 | 27 | 96 | 4.55 | 6.700e-02 | 2.294e-01 |
| MultiHop-RAG | 6, int8 | 100 | 47 | 13 | 91 | 4.37 | 1.000e-01 | 2.165e-01 |
| aircargo | 1, fp32 | 30 | 30 | 30 | 30 | 5.0 | 0.000e+00 | 5.126e-06 |
| aircargo | 3, int8 | 30 | 21 | 11 | 30 | 4.7 | 8.600e-02 | 1.754e-01 |
| aircargo | 4, int8 | 30 | 21 | 11 | 30 | 4.7 | 8.600e-02 | 1.754e-01 |
| aircargo | 6, int8 | 100 | 64 | 31 | 96 | 4.6 | 9.300e-02 | 2.053e-01 |
| The four pooled | 6, int8 | 400 | 221 | 93 | 379 | 4.4975 | 8.700e-02 | 2.752e-01 |

«Same five» is the same set of five chunks; «same order» the same list. Blocks 3 and 4 are one
row twice: ONNX scored the same pairs the same way.

## The blocks, printed

| Block | Arm | Questions | UTC | Minutes | Load, s | Warm-up, s | A question, median s | Sum, s | RSS after load, MiB | Peak, MiB | Disturbed | Others' CPU, max % | Swap, median MB |
| ---: | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | fp32 | 30 | 08:28–08:43 | 14.2 | 4.592 | 20.786 | 24.419 | 826.877 | 1,654.4 | 2,908.3 | 0 | 25.8 | 2,061.0 |
| 2 | pytorch | 30 | 10:04–10:21 | 17.5 | 27.775 | 133.093 | 30.153 | 912.021 | 548.9 | 2,684.0 | 0 | 95.9 | 1,933.0 |
| 3 | int8 | 30 | 10:22–10:30 | 8.2 | 7.288 | 14.677 | 15.157 | 474.289 | 1,426.7 | 2,593.3 | 0 | 68.3 | 1,933.0 |
| 4 | int8 | 30 | 10:30–10:38 | 7.8 | 4.286 | 13.18 | 14.971 | 456.086 | 1,425.4 | 2,595.2 | 0 | 84.7 | 1,933.0 |
| 5 | pytorch | 30 | 10:38–10:54 | 15.5 | 10.845 | 129.546 | 26.148 | 798.035 | 550.2 | 2,685.1 | 0 | 9.4 | 1,933.0 |
| 6 | int8 | 400 | 10:54–12:40 | 106.0 | 3.894 | 13.091 | 15.342 | 6,315.608 | 1,426.0 | 2,764.4 | 2 | 123.8 | 1,904.75 |

A disturbed question is not timed; block 6 is read for its fives and its gold, not its seconds.

## Forecast and outcome

| Forecast, the spec's | Outcome | Held |
| --- | --- | --- |
| The six blocks pass their gates | 6 of 6, each at its first attempt | yes |
| PyTorch gives stage 2's scores to the last bit | the largest difference 0.000e+00 | yes |
| FP32 differs by less than 1e-6 | 5.126e-06 | no |
| `int8` reads faster, on 30 of 30 | faster, on 30 of 30 | yes |
| The ratio ≈ 1.8 | 1.751 | yes |
| The saving ≈ 11–12 s a question | 12.047 s | yes |
| PyTorch's ≈ 26 s a question | 28.206 s | no |
| `int8`'s scores move by about a thousandth | the largest difference a question: a median 0.087, at most 0.275 | no |
| Its five stage 2's set on ≈ 85 % of the 400 | 221 of 400, 55.25 % | no |
| It shares at least four on ≈ 99 % | 379 of 400, 94.75 % | no |
| The gold holds, pooled b − c within ± 2 | holds; b 1, c 4, b − c −3 | the gold yes; ± 2 no |
| `int8` passes; blocks 7–11 do not run | int8 passes, 1.751×; blocks 7–11 did not run | yes |
| An INT8 block's peak not below a PyTorch block's: ≈ 3.1–3.2 GB against ≈ 2.9 GB | on the thirty 2,593.3 and 2,595.2 MiB against 2,684.0 and 2,685.1 MiB | no |
| A PyTorch block ≈ 14.5 min | 17.5 and 15.5 min | no |
| FP32's block ≈ 13 min | 14.2 min | no |
| An INT8 block on the thirty ≈ 8 min | 8.2 and 7.8 min | yes |
| Block 6 ≈ 1.75 h | 1.77 h | yes |

«Held» is mine: «≈» is read as within 5 % of the forecast, and a share of the 400 by its other
part, the questions forecast to differ (≈ 60 and ≈ 4). PyTorch's blocks overran by their first
call: PyTorch's warm-up took 133.093 and 129.546 s, `int8`'s 14.677 and 13.18 s. The ± 2 missed
toward `int8`.

## What it says

- **`int8` passes, as forecast.** Its gold holds on the 250 questions with gold: after the
  expansion PyTorch's five hold gold on 141 and `int8`'s on 144, b 1 and c 4, and no base reads a
  loss. On aircargo's thirty it reads faster on 30 of 30, a median 12.047 s saved of 28.206 s, a
  ratio 1.751.
- **But its five is not PyTorch's** ([`PLAN.md`](../../PLAN.md) item 5a, «Правка 30.10», F4).
  `int8`'s five is PyTorch's set on 221 of the 400 and PyTorch's list, in its order, on 93; it
  shares at least four on 379. The answer's prompt reads the order: `agent/prompts.py` numbers the
  documents as they come, and `agent/context_window.py` keeps the leading ones when the window
  cuts. So the five the answer reads differs on 307 of the 400 questions: by its set on 179, by
  its order alone on 128. In PLAN's words, «эталон держится», not «ответы те же»: INT8 changes
  the answer's path.
- **The change is the quantization's, not the export's.** FP32's largest difference 5.126e-06
  kept stage 2's five on all thirty. `int8`'s largest score difference a question is a median
  0.087 on the 400, at most 0.275; on the made-up pairs it was at most 0.0035 (the spec's).
- **The memory, printed:** on the thirty `int8` peaked at 2,593.3 and 2,595.2 MiB, PyTorch at
  2,684.0 and 2,685.1 MiB — lower, where the spec forecast no lower; after the load PyTorch held
  548.9 and 550.2 MiB, `int8` 1,426.7 and 1,425.4 MiB. Nothing reads them.

## What follows

- **INT8 in production is Julia's word** ([`PLAN.md`](../../PLAN.md) §9). Its five changes, so,
  like K = 14 and num_ctx 3,584, adopting it re-answers item 6 (aircargo's 100, ≈ 6–8 h of the
  Mac) and stage 5 (the 300 external answers, ≈ 17–30 h): PLAN's F4 edit. That costs nothing more
  if K = 14 or 3,584 is adopted too, and all ≈ 23–38 h if INT8 is the only change of the path. It
  joins the one package question (§8.3 item 2), asked once the n-gram lever is read.
- **Next, PLAN's short live series,** «затем короткая живая серия»: INT8 in the chat itself, where
  PyTorch reranked in 102 s against 27 s idle (the spec's). The product has to load the ONNX file
  behind a setting that defaults to PyTorch, with a spec and an E2E of its own.

## What it does not say

- **That the answers stay the same:** the gold here is retrieval's. What the changed fives do to
  the answers is item 6's and stage 5's to measure, if INT8 is adopted.
- **Whether INT8 enters the path:** the reranker's runtime is Julia's word
  ([`PLAN.md`](../../PLAN.md) §9). A pass here earns the short live series in the chat, not the
  path.
- **The chat's seconds:** here the reranker ran alone on an idle Mac; in the chat it shares the
  memory with the answer's model.
- **Memory as a gain:** the resident sizes are printed, not read.
- **Other schemes:** static quantization, other operator sets, other runtimes, a smaller
  reranker. One file was read; the fallback did not run.
- **Other bases' speed:** the speed is aircargo's thirty; the 400 give the fives and the gold.
- Thirty questions timed, 400 read, one stand, one day, on a Mac other projects share.

## Files

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `record.json` | 14,529 | `49352c2fe5d4f3a3f78b39a8c94c30ac21544b19eb069854d836b106dd9879ca` |
| `rows.jsonl` | 186,863 | `bf95250eef7462dcb6a22affa955c75333ff55bc512147a337a3c980924a01db` |
