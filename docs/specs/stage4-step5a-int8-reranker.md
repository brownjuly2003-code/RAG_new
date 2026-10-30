# Stage 4, item 5a: INT8 of the same reranker, on stage 2's saved pools

Status 2026-10-30: **registered before the first question was scored in ONNX**, with the tool,
its test and the export's manifest ([Records](#records)), in `d9f9fd8`. [`PLAN.md`](../../PLAN.md)
stage 4, item 5a, the first lever of research 6: «INT8 того же реранкера в ONNX Runtime 1.23.2 …
Сначала ONNX FP32 против PyTorch, затем INT8, на сохранённых списках кандидатов этапа 2:
пересечение пятёрок, эталон по базам, секунды, RSS; затем короткая живая серия.» This spec is
that comparison; the short live series comes after it, and only if an INT8 file passes here.
The one value filled in at launch is `d9f9fd8`, the commit that registers this spec.

## Why

- **The rerank is a large share of the wait.** Stage 2 recorded the product's reranker —
  `BAAI/bge-reranker-v2-m3` in sentence-transformers' CrossEncoder on the CPU — at a median
  26.8 s a question on aircargo (13.9–47.5 s), 21.3–32.9 s by base, on pools of 23–40
  candidates; the 400 questions took 11,323 s of rerank. In the chat it took 102 s against 27 s
  idle
  ([the research's analysis](../operations/research-2026-10-25/analysis.md#item-5a--speed-research-6--and-what-our-log-and-arithmetic-add)).
- **What INT8 promises, and what it may cost.** The export's card gives ≈ 1.8× on a 4-thread
  AVX2 CPU and a process no smaller; another card's own INT8 kept the first document on 0.625 of
  its queries. So the gold is read beside the seconds: a faster reranker that changes the five the
  answer reads is another product.
- **Why the saved pools:** stage 2 kept, per question, the pool the reranker scored, each
  candidate's score and the five it kept, and [the K curve](k-curve-expanded.md) gave every
  recorded five again from those scores through the product's own fusion, rerank cut and parent
  expansion. Scored again in another runtime, the same pools read the change of the reranker
  alone: the same candidates, texts and order, and the same selection after it.
- **Why FP32 first:** an INT8 file differs from PyTorch by the export and by the quantization.
  The FP32 export, scored first, must give the recorded scores; else what follows measures the
  export, and nothing is read.

## The stand

- **The model** is the product's (`vectordb/_base_manager.get_reranker`): `BAAI/bge-reranker-v2-m3`,
  snapshot `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`, from the Mac's Hugging Face cache,
  offline. The interpreter is stage 2's stand's,
  `PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python`: Python 3.11.15, torch 2.2.2,
  transformers 4.44.2, sentence-transformers 2.7.0, ONNX Runtime 1.23.2 (the CPU provider),
  numpy 1.26.4.
- **The export,** preparation before this spec, on no question of stage 2:
  `reports/stage4-step5a/tools/export_onnx.py`, run on the Mac with the onnx 1.23.2 package from a
  folder of its own (`/Users/julia/RAG_new_ort_site`). torch.onnx at opset 17, batch and length
  dynamic, the weights in one external file (`fp32/`); then `quantize_dynamic` on it, all else
  its defaults:
  - `int8/`: QInt8 weights per channel with reduce_range — ONNX Runtime's documented remedy for
    its kernel's saturation on AVX2 without VNNI, the Mac's i5-7500;
  - `int8_u8u8/`: QUInt8 weights per channel — its other remedy;
    run only after a loss of `int8` ([the outcome](#how-it-is-read--frozen-before-the-first-question-was-scored-in-onnx)).

  Its manifest — the files by SHA-256 and size, the versions, and on 32 made-up pairs each file's
  largest score difference from the CrossEncoder and its seconds — is committed as
  `reports/stage4-step5a/onnx/manifest.json`, the files stay in `M=/Users/julia/RAG_new_ort/bge-reranker-v2-m3`.
  On the made-up pairs, FP32 differs from the CrossEncoder by at most 1.2e-7 and keeps its
  order; `int8` by at most 0.0035, a median 0.0008, and `int8_u8u8` by 0.0041, a median
  0.0007, both changing the order. One call of the 32 pairs, of 59–445 tokens (stage 2's pairs
  hold 44–487), took 40.3 s in PyTorch, 36.1 s in FP32, 22.3 s in `int8` and 25.8 s in
  `int8_u8u8`: the median of three calls after a warm-up.
- **A block's scorer:** PyTorch is `CrossEncoder.predict` as the product calls it, 32 pairs a call.
  ONNX is the same tokenization — each text stripped, the pairs padded to the longest, truncated
  longest first at the tokenizer's own limit, as sentence-transformers 2.7.0's collate does — and
  logit 0's sigmoid, at 4 intra-op threads. torch's default on the Mac is 4 threads too; a block
  that finds another number stops. transformers' tokenizer imports torch, so ONNX's blocks
  hold it too; the end line names it.
- **The tool's own pre-check,** before this spec, on the made-up pairs, a process an arm: the
  stand held for all four arms; FP32 and `int8` gave the manifest's differences from PyTorch,
  1.2e-7 and 0.0035; the processes peaked at 2,881 MiB in PyTorch, 3,291 in FP32 and 3,187 in
  `int8`.
- **The pairs** of a question are the question stage 2's record holds with each pool candidate's
  archive text (the chunk the record names, its source checked), in the pool's recorded order: the
  product's rerank input (`HybridRetriever._rerank_scored_with_status`). Before this spec, a design
  probe scored three questions so in PyTorch: the recorded scores, to the last bit.

## The questions and the blocks

- **Stage 2's records:** runs `p2-wixqa`, `p2-conditionalqa`, `p2-multihoprag` and `p2-aircargo`
  of stand `5e308fe`, `R=/Users/julia/RAG_new_chat_5e308fe/chatlive/runs`, 100 questions each,
  with the bases' chunk archives in `D=/Users/julia/RAG_new_external_s1`.
- **A block** is one arm on a list of questions, in a process of its own: it holds the stand,
  loads its model, scores aircargo's 31st question as a warm-up that is not read, then its
  questions, each one timed call of the scorer. It writes a head line, a line a question (the
  record's SHA-256, the scores, the seconds, what ran beside) and an end line.
- **The schedule:**
  1. FP32 ONNX on aircargo's first thirty — the export;
  2. PyTorch, 3. INT8, 4. INT8, 5. PyTorch on the same thirty — the speed, in ABBA, so a drift of
     the shared Mac falls on both arms alike;
  6. INT8 on all 400 — the fives and the gold;
  7. PyTorch, 8. and 9. `int8_u8u8`, 10. PyTorch on the thirty, 11. `int8_u8u8` on the 400 — the
     same for the fallback, run only when block 6's gold reads a loss.

  Aircargo is the chat's corpus. Its first thirty hold pools of 28–39 candidates, which stage 2
  reranked in 16.96–40.60 s, a median 26.1. The 400 hold the three bases with gold.

## What is read

By the tool's `read`, from the blocks' files. Of each question a block scored:
- the largest difference of its scores from stage 2's;
- the block's five: the product's selection on the recorded lanes with the block's scores
  (`k_curve.Selection` at K = 20: `_rrf_merge`, then `_rerank_scored_with_status`, cut at five);
  how many it shares with stage 2's five, and whether the set and the order are the same;
- with gold (WixQA, ConditionalQA, MultiHop-RAG), stage 2's metrics of block 6's five before and
  after the product's parent expansion (`scripts/external_pilot.read_gold`), beside the recorded
  five's, which the read holds to the committed export first.

Of each block: the load, the warm-up, the seconds a question, the peak resident size after the
load and at the end, whether torch was imported, and what ran beside each question — the
other processes' CPU, Ollama's models, the swap.

## How it is read — frozen before the first question was scored in ONNX

- **A block passes its gate** when:
  - before its first question the stand held: the export's manifest by the SHA-256 registered
    here; the versions it records of torch, transformers, tokenizers, sentence-transformers,
    onnxruntime and numpy; the cached snapshot; the arm's files by SHA-256; 4 threads; the
    tokenizer's own limit;
  - its head names its number, arm and kind, and the tool by SHA-256; its end line stands;
  - its questions are the schedule's, by base and by the record's SHA-256, in order;
  - each question holds a score a candidate, each finite and in [0, 1].

  A block that fails its gate stops the series ([Stops](#stops)).
- **The fidelity:** PyTorch's blocks give stage 2's scores to 1e-6 on every candidate, and the
  FP32 block to 1e-3. Else the series stops with 7, and nothing is read: the scorer or the export
  would be measured, not INT8.
- **A question is disturbed in a block** when at its end a process ran that matches the idle
  pattern ([Running it](#running-it)), Ollama held a model, or the other processes took more than
  one core (100 % CPU). A disturbed question is kept and named, not read for speed.
- **The speed** of a variant, on aircargo's thirty: per question, its two blocks' mean seconds
  against the two PyTorch blocks' mean; **readable** when undisturbed in all four.
  - **faster** when the variant is below on more questions and the exact two-sided sign test
    gives p below 0.05; **slower** the other way round; **no detected difference** otherwise;
    `NOT_EVIDENCE` with fewer than 25 readable. A tie counts on neither side.
  - The number: the median over the readable of PyTorch's seconds over the variant's — the ratio
    — and of their difference — the saving.
- **The gold** of a variant, from its block on the 400: per base with gold and pooled, the
  questions whose primary metric hits with stage 2's five only (b) against the variant's five
  only (c), after the expansion, by the exact McNemar test:
  - **a loss** when on a base or pooled b > c with p below 0.05, or when pooled b − c is above
    2: the same reranker is meant, so a net loss of three questions counts even where the test
    cannot see it;
  - **holds** otherwise;
  - `NOT_EVIDENCE` when on a base more than 5 questions' variant five cannot be expanded and read.

  The same pair before the expansion stands beside.
- **The outcome:**
  - FP32's fidelity fails: `NOT_EVIDENCE`;
  - `int8` holds the gold: it **passes** when its speed reads faster, with its ratio;
  - `int8` loses the gold: blocks 7–11 run, and `int8_u8u8` is read the same way;
  - both lose: no INT8 file passes.
- **Printed, deciding nothing:** the score differences and the fives shared, by base and by block;
  the gold before the expansion; each block's load, warm-up and resident sizes; FP32's seconds
  against PyTorch's — block 1 ran before blocks 2 and 5, not between them; the swap.

**Forecast, written before the first question was scored:** the six blocks pass their gates
and the fidelity holds: PyTorch gives stage 2's scores to the last bit, as the design probe
did, and FP32 differs by less than 1e-6, as on the made-up pairs. `int8` reads **faster**, on
30 of 30: the ratio ≈ 1.8 — the made-up pairs' 1.81, the card's 1.8 — and the saving ≈ 11–12 s
of PyTorch's ≈ 26 s a question. Its scores move by about a thousandth, so its five is stage
2's set on ≈ 85% of the 400 and shares at least four on ≈ 99%, and the gold **holds**: pooled,
b − c within ± 2. `int8` passes; blocks 7–11 do not run. As the card says and the pre-check
showed, an INT8 block's peak does not fall below a PyTorch block's: ≈ 3.1–3.2 GB against
≈ 2.9 GB.

## Running it

On the Mac: `G=/Users/julia/RAG_new_mf_gate`, `W=/Users/julia/RAG_new_s4p5a`,
`O=/Users/julia/RAG_new_s4p5a_runs`, `SITE=/Users/julia/RAG_new_mf_gate_site`, `M`, `R`, `D`
and `PY` above, `T=reports/stage4-step5a/tools/int8_reranker.py`; `E` is the blocks' environment:

    env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME="$HOME" LC_ALL=C PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

1. **The worktree:** `git -C $G worktree add --detach $W d9f9fd8`, by its full SHA;
   `git -C $W status --porcelain` prints nothing; `shasum -a 256` of the four files of
   [Records](#records) in `$W` prints their four; `shasum -a 256 $M/manifest.json` prints the
   manifest's.
2. **The series,** detached so ssh returns at once (`;`, never `&&`, before `nohup`):
   `mkdir -p $O; cd $W; $E nohup $PY -u $T series $R $D $M $O 6 >> $O/series.out 2>&1 </dev/null &`.
   - Before each block it waits for the idle Mac: no process matches
     `pytest|_supervisor|replay\.py|step[0-3]_|limactl|llama-server`, Ollama holds no model,
     `$HOME/ci_local/.lock_ci-local` is absent, and the other processes take at most one core.
     Before its first block the 5-minute load is also below 2.
   - Nothing is stopped; it waits.
3. **One block first:** once `$O/series.log` names block 1, `touch $O/stop`; the series ends after
   block 1 with exit 3. Its line `block 1 read: …` must stand in the log: its gate and its fidelity
   passed. Else [Stops](#stops) applies. Then `rm $O/stop`, and the series is started again as in
   2: it resumes at block 2.
4. **The record,** after `SERIES_DONE`, in the gate's environment, which has the product's
   retrieval code and no model: `cd $W; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$SITE
   /Users/julia/RAG_new_gr4_venv/bin/python $T read $R $D $M $O $O/record`. Its `record.json` and
   `rows.jsonl` are copied to the laptop as bytes.
5. **The fallback,** only when the record reads `int8`'s gold a loss: the series as in 2 with
   `11` for `6`, then the record again as in 4.

### Stops

The series' exit codes:
- 3, the stop file;
- 4, the Mac not idle within an hour;
- 5, a block with no head line within 900 s or no next question within 300 s — six times stage
  2's slowest rerank (48.9 s); it is killed;
- 6, the stand not the registered one;
- 7, a block past its fidelity (the file is kept);
- 8, a block's gate failed (its files moved to `$O/rejected/`);
- 9, a block failed twice.

A block kept from an earlier start is read again at every start, so a 7 or 8 holds. After 4, 5
or 8, once the cause is read, the series is started again as in 2. It resumes at its first block
without a file, so a failed block gets its second attempt; a block that fails twice ends the
series — started again, it exits 9. A 6 or a 7 is a fault of the stand, the export or the tool. A
fault of the tool is a marked error fix — the change, its test, the new SHA-256, one commit — and
the series starts over in a new `$O`.

**Forecast:** ≈ 3 h of the Mac once it is idle. A PyTorch block ≈ 14.5 min: stage 2 reranked
aircargo's thirty and its 31st in 829 s, and the load takes under a minute. FP32's block
≈ 13 min, an INT8 block on the thirty ≈ 8 min, block 6 ≈ 1.75 h — stage 2's 11,348 s of the
401 over 1.8. The stop after block 1, the idle checks and the read add ≈ 15 min. The
fallback, if it runs, ≈ 3 h more, at the made-up pairs' 1.56.

## Records

`reports/stage4-step5a/d9f9fd8/`:
- `record.json`: the inputs and the export's manifest by SHA-256, the tool and the measuring code
  by SHA-256, the runs' provenance, each block's facts, the attempts and the files rejected, the
  fidelity, per base the blocks' score differences and fives, each variant's speed and gold, and
  the outcome;
- `rows.jsonl`, a question a line: its id, base and pool size, per block the largest difference
  and the five's overlap, with gold the points of the recorded five and of each variant's.

Numbers, enums, ids and SHA-256 strings: never a question, a document's text or source.
`stage2_common.without_text` refuses a record with a string that names a document or holds a
question. The blocks' files, with their scores, stay on the Mac.

Item 5a's comparison is no slice by the acceptance rule: no behaviour, case or quality number
of the path changes. Its record gets a row in [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md), a
capsule in `docs/evidence/` and a test that reads it again.

`tests/test_stage4_step5a_tools.py` runs blocks on a synthetic archive with a stand-in scorer, and
covers the stand, the gate, the series' stops, the selection through the product's code and the
reading on hand-made blocks and rows. The tool, the export's tool and manifest, and the test are
committed with this spec, and the test checks each SHA-256 below; a later change is a marked
error fix that updates this list:

- `reports/stage4-step5a/tools/int8_reranker.py` `fda37df5139ae4c2b8d2e0679660b2696ce9e9459dbbcb53af366af68e497cfb`
- `reports/stage4-step5a/tools/export_onnx.py` `40ab7c504e41de8ce30bc9a545ea5858e181df413848c2a75478fe5a40c8facd`
- `tests/test_stage4_step5a_tools.py` `4fbd14574e99887a3ad0acbfa61c92f616b5ee7e6c950c161a4e96d5fa971438`
- `reports/stage4-step5a/onnx/manifest.json` `9888d92b97600dad487bf29de64483a4afe15d2e0e06e21497b8595dcf7c5408`

## Not said

- **Whether INT8 enters the path.** The reranker's runtime is her word ([`PLAN.md`](../../PLAN.md)
  §9). Passing here earns the short live series in the chat, not the path.
- **The chat's seconds.** Here the reranker runs alone on an idle Mac; in the chat it shares the
  memory with the answer's model, and there it took 102 s against 27 s idle.
- **Memory.** The resident sizes are printed; the export's card says INT8 does not lower them.
- **Other schemes:** static quantization, other operator sets, other runtimes, a smaller
  reranker. One file and its fallback are read.
- **Other bases' speed.** The speed is aircargo's thirty; the 400 give the fives and the gold.
- Thirty questions timed, 400 read, one stand, one day, on a Mac other projects share.
