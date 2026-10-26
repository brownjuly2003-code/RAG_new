# The encoder checkers — three checkers that read Russian, on V4's saved aircargo answers — 2026-10-26

Whether a small encoder can flag the answers a person should see instead, where stage 3's
signals could not (outcome C, [record](handover-signal-v4-aircargo.md)): three checkers from
Hugging Face score V4's saved answers against their documents by the rules
[`encoder-checkers.md`](../specs/encoder-checkers.md), registered with the tool in `fa73683`
before the first checker call ([`PLAN.md`](../../PLAN.md) stage 3; §8.3, item 13). Each
checker's threshold is chosen on calibration answers of other bases, then read once on the 80
classed aircargo answers by the handover plan's frozen reading. No judge call, no change of
product code; 3.6 h of the Mac, one checker at a time.

Record: [`reports/encoder-checkers/4f48fed/record.json`](../../reports/encoder-checkers/4f48fed/record.json)
and its rows — [`scores-H`](../../reports/encoder-checkers/4f48fed/scores-H.jsonl),
[`scores-L`](../../reports/encoder-checkers/4f48fed/scores-L.jsonl),
[`scores-N`](../../reports/encoder-checkers/4f48fed/scores-N.jsonl) and the loading check
[`parity.json`](../../reports/encoder-checkers/4f48fed/parity.json) — written by
[`reports/encoder-checkers/tools/encoder_checkers.py`](../../reports/encoder-checkers/tools/encoder_checkers.py).
Checked by [`tests/test_encoder_checkers_artifact.py`](../../tests/test_encoder_checkers_artifact.py):
every number of the record is read again from the rows; the rows' classes are read again from
the committed plan and judge records; the rows name the registered tool, the pinned weights and
the inputs by SHA-256; every table row below is built from the record. The rows hold ids,
labels, scores, counts and seconds, never the text of a question, a document or an answer.

## Provenance and method

- **Checkers:** H — `Horizon-Labs/hallucination-guard-small` at `7c015323`; L —
  `KRLabsOrg/lettucedect-v2-mmbert-base` at `8831ce06`; N —
  `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` at `b5113eb3`. Each scores an
  answer by its card's own use (the spec's table); low means unsupported. PyTorch 2.2.2 on the
  Mac's CPU, fp32, four threads, `transformers` 4.57.6 in its own folder beside the ML venv.
- **Loading check, before any score, passed:** on 12 pairs H's and N's PyTorch path against
  their authors' ONNX exports — largest difference of a probability 1.3·10⁻⁶ and 3.3·10⁻⁶, the
  same top label on all; L's loaded config equals its file.
- **Answers:** calibration RU — 300 rows of RusHallu-RAG's human labels (commit `345907f9`;
  `sberquad-rag` 200, `ruscibench-rag` 100; its text stays on the Mac); calibration EN — V4's
  183 classed answers on WixQA and ConditionalQA, classes by the M1 judge with references
  withheld; reading — V4's 100 aircargo answers of the handover plan
  (`reports/handover-signal/d260d95/plan.json`), 17 targets, 63 good, 20 neither. A target is a
  bad answer or a decline; good is good and not declining.
- **Threshold:** the handover plan's S7 rule on the calibration answers, RU and EN weighing
  equally: the score below which the most targets are caught while at most a third of the good
  are marked.
- **Reading, frozen before the first call:** *worth wiring* — at least 12 of 17 caught, Wilson
  lower bound at least 1/3, at most 21 of 63 over-marked; *useless* — the Wilson upper bound of
  caught below 1/2, or over 1/2 over-marked; *in between* otherwise.
- **Measured** in the Mac's gate checkout at the overlay of `fa73683` (`af750391`); the record
  names the tool by SHA-256 (`fa226d38…`). Each checker ran whole in one segment, under its
  stop of three times the forecast: H 58.1 min, L 34.0, N 122.8 (forecast 30, 30, 80), the
  Mac's 5-minute load 1.5–5.9 at the starts and ends (other projects' runs on the shared Mac).

## The threshold, chosen on the calibration answers

| Checker | Threshold | EN caught | EN over-marked | RU caught | RU over-marked | AUROC EN | AUROC RU |
|---|---|---|---|---|---|---|---|
| Horizon guard small | 0.5851 | 74 of 116 | 23 of 67 | 33 of 94 | 49 of 206 | 0.646 | 0.571 |
| LettuceDetect v2 mmBERT | 0.7811 | 65 of 116 | 25 of 67 | 36 of 94 | 60 of 206 | 0.622 | 0.632 |
| mDeBERTa NLI | 0.2174 | 67 of 116 | 38 of 67 | 13 of 94 | 19 of 206 | 0.531 | 0.604 |

## The reading on the 80 classed aircargo answers — what decides

| Checker | Caught of 17 | Over-marked of 63 | Reading | AUROC | Seconds an answer, median (p90) | Peak memory, GB |
|---|---|---|---|---|---|---|
| Horizon guard small | 10 | 8 | in between | 0.805 | 2.3 (18.6) | 1.29 |
| LettuceDetect v2 mmBERT | 6 | 8 | in between | 0.733 | 4.6 (5.9) | 2.11 |
| mDeBERTa NLI | 5 | 7 | in between | 0.653 | 6.3 (38.5) | 2.64 |

**Outcome: in between: H, L, N.**

No checker is worth wiring: by the spec stage 3 stays at outcome C, with the handover line under
every answer that already ships. H comes closest: 10 of 17 caught (Wilson 0.360–0.784) while
marking 8 of 63 good, 2.3 s an answer — two catches short of the bar; stage 3's signals caught
11 marking 28 (S3) or 16 marking 34–43 at 81–235 s (S2, S6, the 4B's own check). L catches 6
(0.173–0.587), N 5 (0.133–0.531). On Julia's question of 2026-10-26 — should better checkers be
sought — research 4's next pick, Horizon guard base (308M, Russian among its languages), is
tested next under its own amendment, then the best read again on fresh answers.

## Beside it, deciding nothing

| Checker | RU grounding types caught | RU other types caught | Pairs cut: reading / EN / RU |
|---|---|---|---|
| Horizon guard small | 10 of 37 | 24 of 62 | 6 / 211 / 14 |
| LettuceDetect v2 mmBERT | 17 of 37 | 20 of 62 | 0 / 0 / 0 |
| mDeBERTa NLI | 4 of 37 | 10 of 62 | 0 / 0 / 0 |

Grounding types are RusHallu-RAG's `Contradiction` and `Unconfirmed`; the others `Missing`,
`Partial`, `Oversight`, `Excess`. H cut 211 sentence pairs of the EN answers at its 2,048
tokens — WixQA's and ConditionalQA's documents are long — so its EN threshold was read in part
on cut sources. No answer of any set went unscored.

## What it does not say

- The forecast held in part: none worth wiring, as written; but all three are in between, not
  at most one.
- 17 targets give wide intervals: «in between» is not «almost worth wiring». The AUROC on the
  reading set is above both calibration sets' for every checker; nothing here says the
  threshold would catch as many on other answers.
- The classes of V4's answers are one model's verdicts (D11: no person grades); RU's labels are
  RusHallu-RAG's own. One draw of each checker, on the shared Mac.
- Wiring a checker would be a new model in the product (Julia's word, §9), then its E2E test
  and its seconds on the chat's path; nothing here wires one.
