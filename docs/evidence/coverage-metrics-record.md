# Coverage beside quality — the committed judge records read by published rules — 2026-10-26

How many questions got an answer at all, and how good the answers given out were: the
committed M1 records of stage 2 (V3) and stage 2b (V4) read again by the rules
[`coverage-metrics.md`](../specs/coverage-metrics.md) registered before the count — the
literature's decline matrix, CRAG's score and coverage beside quality among the answered
([research analysis](../operations/research-2026-10-25/analysis.md), item 1). No model call;
no published number of either record changes.

Record: [`reports/coverage/coverage-record.json`](../../reports/coverage/coverage-record.json),
written by [`reports/coverage/tools/coverage_record.py`](../../reports/coverage/tools/coverage_record.py)
from the judge exports the spec names, each by SHA-256. Checked by
[`tests/test_coverage_record_artifact.py`](../../tests/test_coverage_record_artifact.py): the tool
rebuilds the record from those exports; each answer's kind and CRAG level is counted again from
the rows; every table row below is built from the record. The record holds identifiers and
counts, never the text of a question, a document or an answer.

## Provenance and method

- **Inputs:** M1 (the reference withheld from the judge), judge `claude-opus-5-5`, 100 questions
  a key and side, none missing. V3: stage 2's exports in `reports/stage2/5e308fe/`, stand code
  `5e308fe48cca0955c3007057a574a425f71e2a6a`. V4: stage 2b's in `reports/answer-prompt-v4/4f48fed/`,
  stand `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1`. The base's gold — has a reference or not —
  from the same side's M2 export (the spec's amendment of 2026-10-26).
- **Kinds:** declined (the judge's `answers_question` is `declined`), empty, answered (the rest).
- **CRAG:** good and answered 1, `partial_ok` 0.5, declined or empty 0, other answered −1.
- **Intervals:** the CRAG mean's cluster bootstrap over stage 2's clusters, each aircargo
  question its own; the shares' Wilson and cluster intervals are in the record.
- **Read unpaired**, deciding nothing; the paired V3-against-V4 reading is V4's
  [record](answer-prompt-v4-record.md). One model judges, no person (D11). MultiHop-RAG is
  advisory and V3 only.

## Coverage, quality among the answered, the CRAG score

| Base | Prompt | Answered | Good among the answered | Good or partial among the answered | With an unsupported claim, among the answered | CRAG score (95 %) |
|---|---|---|---|---|---|---|
| aircargo | V3 | 98/100 | 69/98 | 86/98 | 10/98 | 0.655 (0.520 to 0.780) |
| aircargo | V4 | 100/100 | 63/100 | 83/100 | 14/100 | 0.560 (0.415 to 0.700) |
| ConditionalQA | V3 | 81/100 | 27/81 | 32/81 | 47/81 | −0.195 (−0.363 to −0.025) |
| ConditionalQA | V4 | 91/100 | 32/91 | 40/91 | 50/91 | −0.150 (−0.346 to 0.054) |
| MultiHop-RAG | V3 | 66/100 | 42/66 | 43/66 | 22/66 | 0.195 (−0.125 to 0.321) |
| WixQA | V3 | 67/100 | 25/67 | 35/67 | 29/67 | −0.020 (−0.153 to 0.108) |
| WixQA | V4 | 73/100 | 35/73 | 44/73 | 29/73 | 0.105 (−0.045 to 0.258) |

## The declines

| Base | Prompt | Declines | of them, the documents held the answer (the judge) | Declined, of the questions the base's gold cannot answer |
|---|---|---|---|---|
| aircargo | V3 | 2 | 2 | — |
| aircargo | V4 | 0 | 0 | — |
| ConditionalQA | V3 | 19 | 13 | 8/20 |
| ConditionalQA | V4 | 9 | 6 | 4/20 |
| MultiHop-RAG | V3 | 34 | 7 | 29/30 |
| WixQA | V3 | 33 | 29 | — (0) |
| WixQA | V4 | 27 | 22 | — (0) |

aircargo's judge record carries no reference answers; WixQA's 100 questions all have one.

## What it says

1. **V4 answers more on every base, and on the external bases the answers it gives out are no
   worse by these counts** (unpaired): WixQA good among the answered 25/67 → 35/73,
   ConditionalQA 27/81 → 32/91. On aircargo they are: 69/98 → 63/100, the bad 14 → 17 that V4's
   paired record did not detect.
2. **On ConditionalQA the chat gives out more wrong answers than right ones** under both prompts:
   its CRAG score is below zero, V3's interval wholly, and declining every question would score
   0. WixQA moves from −0.020 to 0.105, both intervals across zero; aircargo is the only base
   clearly above it.
3. **The answers given out with a claim the documents do not hold:** ConditionalQA 50 of 91,
   WixQA 29 of 73, aircargo 14 of 100 under V4 — the answers a handover signal is for
   ([stage 3](../../PLAN.md)).
4. **Most declines are wrong by V4's own rule** (decline only when nothing answers): the
   documents held the answer, at least in part, for 22 of WixQA's 27 and 6 of ConditionalQA's 9
   under V4. Of ConditionalQA's 20 questions its gold cannot answer, V4 declines 4, V3 8 — V4's
   record's guard row, the same counts.

These are baselines: stage 3б and stage 4 change the answer, and they are read against them.
