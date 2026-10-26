# Stage 3 record — the handover signals on V4's 100 aircargo answers — 2026-10-26

Which of V4's 100 aircargo answers should go to a person, and can any automatic signal tell? The
eight signals of the [handover plan](../specs/handover-signal.md) were computed on all 100
answers of stand `4f48fed` and set against the judge's classes, by the reading frozen on
2026-10-17 and S7's threshold rule (`f520cde`). [`PLAN.md`](../../PLAN.md) stage 3, steps 1–3.

**Outcome C.** No signal is worth wiring: on this Mac, with the 4B, no automatic signal finds
the answers that need a person. One signal is **in between** — S3, the claim check's verdicts —
and is the plan's candidate for its stage 2 on other answers.

Record: [`reports/handover-signal/d260d95/record.json`](../../reports/handover-signal/d260d95/record.json),
written by [`reports/handover-signal/tools/signal_record.py`](../../reports/handover-signal/tools/signal_record.py)
(`5049430`, before the rows it reads) from the signal plan, the run's rows and the judge's
export, each named there by SHA-256. Checked by
[`tests/test_handover_signal_record_artifact.py`](../../tests/test_handover_signal_record_artifact.py):
the tool rebuilds the record; each signal's counts, S7's threshold, the reading, R2 and R3 are
counted again from the rows; every table row below is built from the record. The rows hold
identifiers, flags, counts and seconds, never the text of a question, a document or an answer.

## Provenance and method

- **Plan** `reports/handover-signal/d260d95/plan.json` (`b7ad62a`, SHA-256 `30e0a598…df16e`),
  built before the first model call; signal code `d260d95b749913d98193a89fb181490865ca42c4`; the
  answers of stand `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1`; the 4B
  `qwen3:4b-instruct-2507-q4_K_M` in Ollama 0.33.2 on `deproject-mac`, at the code defaults.
- **Run** 2026-10-25 17:26:57 – 2026-10-26 05:31:56 UTC, 100 answers, no node error; 11.46 h
  of the signals' own seconds; a median of 380.8 s an answer. **One stop:** answer 100 passed the
  cap (3 × the first five's median, 1,149 s) at 04:54:49 while another project's browser tests
  loaded the Mac (load 15–20); resumed once, as the plan allows, at 05:12:52, it took 1,143.5 s,
  under the same cap.
- **Targets:** the judge's bad answers and every decline — 17, all bad (V4 declined no aircargo
  question); good and not declining 63; partial 20. The judge `claude-opus-5-5`, stage 2b's
  export `v4-aircargo-judge.cases.jsonl`; no person graded an answer (D11).
- **Reading, frozen:** worth wiring — caught at least 2 of 3 with Wilson's lower limit at least
  1 of 3, over-marked at most 1 of 3; useless — Wilson's upper limit of caught below 1 of 2, or
  over-marked above 1 of 2; otherwise in between.

## The signals

| Signal | Marked | Caught of 17 (Wilson 95 %) | Over-marked of 63 | Added seconds, median | Reading |
|---|---|---|---|---|---|
| S1 self-score below 80 | 3 | 2 (0.033–0.343) | 0 | 0 | useless |
| S1′ self-score below 100 | 14 | 3 (0.062–0.410) | 4 | 0 | useless |
| S2 the widget's claim check | 59 | 16 (0.730–0.990) | 34 | 137.3 | useless |
| S3 the claim check's verdicts | 44 | 11 (0.413–0.827) | 28 | 137.3 | in between |
| S4 the widget's relevance | 17 | 3 (0.062–0.410) | 11 | 274.1 | useless |
| S5 a decline | 0 | 0 (0.000–0.184) | 0 | 0 | useless |
| S6 the widget's first pass | 70 | 16 (0.730–0.990) | 43 | 380.8 | useless |
| S7 rerank top below 0.981153 | 33 | 4 (0.096–0.473) | 19 | 0 | useless |
| S8 the answer's script | 8 | 3 (0.062–0.410) | 4 | 0 | useless |

S2 and S6 catch 16 of the 17, but mark more than half of the good answers — 34 and 43 of 63.
S3 catches 11 (below 2 of 3) and over-marks 28 (above 1 of 3, not above 1 of 2). S7's threshold
was chosen on these answers by its rule, so it would stay a candidate even if it read well.

## Notes the reading needs

- **S5 could not fire:** its phrases are those of V2 and the widget; V4 declines in its own
  words, and declined no aircargo question here. Its wording is settled before any further
  reading, not on these answers.
- **S8 counts letters, not language:** all 8 answers it marks are Russian, dense with Latin
  terms such as AWB and field names.
- **R1 not checked here:** the run sets no `RAG_ENV` (`rag_env` none), and S6's routes — retry
  70, auto 30 — are development's. [`PLAN.md`](../../PLAN.md) stage 3, step 4 checks it.
- **R2 refuted on these answers:** no answer had zero claims, so no vacuous «verified» with
  factuality 0 arose.
- **R3 confirmed on 4 answers:** 607 claims, 491 supported, 474 cited; 4 answers were marked by S2
  with every claim supported, only for a claim without a cited `[N]`.
- **The grader (S4):** 100 outcomes `ok`, no failure, no answer with every document dropped.
  The claim check's status: verified 41, not verified 25, unsupported 34.

## What follows

By the plan: **C** — Julia is told plainly, with her options (a line under every answer
pointing to the operator button; a route by topic, which needs a list of topics, a dictionary —
against universality; a stronger checker on other hardware). **S3 in between** — the handover
plan's stage 2: a plan of its own on WixQA's and ConditionalQA's open parts, named before its
first request, with an English judge prompt and its own retest; S2, S3, S4 and S6 there take
5–17 h of the Mac a hundred, and the hours are hers to give. Proposed for her word
([`PLAN.md`](../../PLAN.md) §8.3, item 13): research 4's offline test of three encoder checkers
that read Russian, on the saved answers — about 2–4 h of the Mac, no judge.
