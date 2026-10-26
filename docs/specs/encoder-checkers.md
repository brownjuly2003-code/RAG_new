# The encoder checkers: three small models that read Russian, offline on saved answers

Status 2026-10-26: **registered before the first checker call**, with the tool that runs and
reads it and its test ([Records](#records)). [`PLAN.md`](../../PLAN.md) stage 3, «Что следует
за исходом»: «офлайн-тест трёх энкодер-чекеров, читающих русский (рисерч 4), на сохранённых
ответах. Порог каждого выбирается на RusHallu-RAG … и на открытых частях английских баз, а
читается один раз на этих 100 ответах по замороженному чтению»; §8.3, item 13; the
[research analysis](../operations/research-2026-10-25/analysis.md), item 4. Julia's «да» of
2026-10-26 took it as the fourth of four items. No generation, no judge call.

## Why

Stage 3 ended at outcome C ([record](../evidence/handover-signal-v4-aircargo.md)): of V4's 17
bad aircargo answers the 4B's own claim checks (S2, S6) catch 16 but mark 34 and 43 of the 63
good ones, and they take 81–235 s an answer; the cheap signals catch 0–4. An encoder checker
reads the documents and the answer in seconds. None of the three has a measured Russian
grounding quality or a CPU time like ours. If one reaches the handover plan's frozen reading on
those 100 answers, it is a signal worth wiring — a new model in the product, so Julia's word.

## The checkers

Weights, tokenizer and card from Hugging Face at a pinned revision; no repository code runs.
PyTorch 2.2.2 on the Mac's CPU, fp32, four threads; `transformers` 4.57.6 in a separate
target directory beside the Mac's ML venv. The ModernBERT configs were written by
`transformers` 5, which needs PyTorch 2.5 — not built for the Mac's Intel CPU — so the tool
reads their rope bases from each config's own `rope_parameters` into 4.57's fields.

| | Model | Revision | Size, licence | How an answer is scored (each card's own use) |
|---|---|---|---|---|
| **H** | `Horizon-Labs/hallucination-guard-small` (mmBERT-small) | `7c015323` | 141M, Apache-2.0 | each sentence against the source, source first; truncation as the card's call (2,048 tokens, the longer side cut); P(`SUPPORTED`) a sentence; **the minimum over sentences** |
| **L** | `KRLabsOrg/lettucedect-v2-mmbert-base` (mmBERT-base) | `8831ce06` | 307M, Apache-2.0 | the card's plain-`transformers` use: the pair (context, answer), the context cut at 4,096 tokens; P(hallucinated) of each answer token; **1 − the maximum** |
| **N** | `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` | `b5113eb3` | 279M, MIT | each sentence (hypothesis) against each window of each document (premise): windows of at most 400 of its tokens, 50 shared with the next, shorter when the pair would pass 512; a sentence past 300 tokens cut; P(entailment); the maximum over windows a sentence, **the minimum over sentences** (SummaC's zero-shot form, research 4) |

Low means unsupported for all three. The source and the context are the documents in their
order, joined by a blank line: for V4's answers the documents of the saved answer prompt
(`scripts/chat_answer_judge.read_prompt`, without the source labels), for RusHallu-RAG the row's
`docs`. An answer loses its reference marks `[n]` and `[n, m]` (`chat_answer_judge.MARK`) and
the spaces before them — format the product would strip the same way. Sentences: the card's
split after `. ! ? 。 ！ ？` and a space, and at line breaks; a piece without a letter or a digit
is dropped. An answer with no sentence, or whose prompt held no document, is unscored.

## The answers

- **Calibration, Russian (RU):** RusHallu-RAG's human labels
  (`results/annotation/human/merged/`, commit `345907f9`, each file by its SHA-256 in the
  record) — a seeded shuffle (seed 20261026) of each file, its first 200 rows of
  `sberquad-rag` (655) and 100 of `ruscibench-rag` (345), the 300 then shuffled together
  with the same seed. Good — the labels hold only the type
  `None`; target — any other type. Grounding types: `Contradiction`, `Unconfirmed`; the others:
  `Missing`, `Partial`, `Oversight`, `Excess`. Evaluation only: its text stays on the Mac, rows
  hold ids, labels and numbers.
- **Calibration, English (EN):** V4's answers on WixQA and ConditionalQA (stage 2b, stand
  `4f48fed`) with the M1 judge's class (`reports/answer-prompt-v4/4f48fed/v4-*-judge-m1.cases.jsonl`,
  references withheld). Target — bad, or a decline; good — good and not declining; `partial_ok`
  neither, and not scored. WixQA 56 targets and 35 good, ConditionalQA 60 and 32.
- **Reading:** V4's 100 aircargo answers of stage 3's plan
  (`reports/handover-signal/d260d95/plan.json`), the classes as there
  (`v4-aircargo-judge.cases.jsonl`): 17 targets, 63 good, 20 neither. All 100 are scored, for
  the seconds; the 80 classed ones are read.

Each V4 answer is found once in its run on the Mac (`chat_answer_judge.run_answers`) with the
prompt SHA-256 its judge row names, and aircargo's with the plan's answer SHA-256.

## Checks before any number

1. **The loading path.** H and N ship their authors' ONNX exports (`onnx/model.onnx`). On the
   tool's own 12 pairs from no base — six short, written by hand in Russian and English, and
   six on a templated source of about 1,500 tokens (cut at 512 for N) — the PyTorch path's probabilities must equal ONNX Runtime's within 0.01, with
   the same top label on every pair; otherwise the test stops. L has no export: it shares H's
   architecture and rope bases, read the same way, so H's check covers its path, and the tool
   checks that the loaded configs hold the bases their files name.
2. **The inputs** as above: an answer not found once, or a hash that differs, stops the tool.
3. **Truncation** is counted per checker and set — H's cut sources, L's cut contexts, N's cut
   sentences. Reported, not stopping.

## The threshold — frozen before the first call

Per checker, on the calibration answers only, S7's rule of the handover plan
(`reports/handover-signal/tools/signal_record.s7_threshold`): every distinct answer score is a
candidate; a candidate marks the answers scored below it. RU and EN weigh equally — the
reading set's language is RU's, its generator, prompt and retrieval are EN's — so a candidate's
over-marking is ½ (RU's marked good ÷ RU's good) + ½ (EN's likewise), and its catching the
same over targets. The threshold is the candidate catching the most among those over-marking
at most 1/3, the lowest on a tie. If it catches nothing, the checker has no threshold and reads
*useless*.

## How it is read — frozen before the first call

On the 80 classed aircargo answers a checker marks those scored below its threshold; an
unscored answer is unmarked. Caught — marked targets of 17; over-marked — marked good of 63;
the handover plan's frozen reading (`signal_record.read`):

- **worth wiring** — caught at least 2 of 3 with the Wilson lower bound at least 1 of 3, and
  over-marked at most 1 of 3 (12 of 17 and at most 21 of 63);
- **useless** — the Wilson upper bound of caught below 1 of 2, or over-marked above 1 of 2;
- **in between** — otherwise.

**The outcome:** a checker *worth wiring* — the one catching the most, then over-marking the
fewest, then with the fewest seconds; else `NOT_EVIDENCE` if a checker is; else the checkers
*in between*, listed; else none. Beside
it, deciding nothing: each checker's seconds an aircargo answer (median, p90), its peak memory,
the Mac's load; AUROC per set — threshold-free, published apart from the point (research 4);
RU's catching by grounding and other types; the truncation counts.

What it does not decide: wiring. A checker *worth wiring* is a new model in the product —
Julia's word (§9), then its E2E test and its seconds on the chat's path. None *worth wiring*
closes stage 3 at outcome C, with the line under every answer that already ships.

**Forecast, written before the first call:** none *worth wiring*; at most one *in between*,
H or L. The cards give balanced accuracy near 0.7 at a fixed 0.5 and no Russian grounding
number; catching 12 of 17 while marking at most 21 of 63 asks for a separation they do not
show. Time ≈ 2.3 h of the Mac: H ≈ 30 min, L ≈ 30 min, N ≈ 80 min (an estimate from the token
counts of the inputs, about 150 GFLOP/s on the shared i5-7500); an aircargo answer H 2–6 s,
L 2–5 s, N 5–12 s.

## Order and stop

One checker at a time, each in its own process: the 100 aircargo answers in the plan's order,
then EN's 183 in run order, then RU's 300 in the shuffle's order. A checker whose answers'
summed seconds pass three times its forecast (H 90, L 90, N 240 min) stops and is not resumed;
the answers not reached are counted and left out. A run broken otherwise resumes where it
ended, the same tool, weights and inputs. A checker whose reading set is not whole, or whose RU or EN half keeps
fewer than 30 good or 15 targets, is `NOT_EVIDENCE`. Another project's runs on the shared Mac
are not stopped; the load average is recorded at each checker's start and end.

## Records

- Tool: [`reports/encoder-checkers/tools/encoder_checkers.py`](../../reports/encoder-checkers/tools/encoder_checkers.py):
  `parity` and `score` run on the Mac (the ML venv's interpreter with the separate
  `transformers`), `record` reads the committed rows anywhere. Rows hold ids, labels, scores,
  counts and seconds — never a text of a question, a document or an answer.
- Tests: `tests/test_encoder_checkers.py` (the splitting, the windows, the threshold, the
  reading and the outcome on hand-made rows); `tests/test_encoder_checkers_artifact.py` (the
  record read again from its rows and the committed judge records).
- The record: `reports/encoder-checkers/4f48fed/`, its capsule in `docs/evidence/`, one row in
  [`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md).
