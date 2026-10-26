# Coverage beside quality: the committed judge records read by published rules

Status 2026-10-26: **registered before the count**, with the tool that reads it and its test
([Records](#records)). [`PLAN.md`](../../PLAN.md), «Параллельно, без Mac», «пересчёт по
опубликованным правилам» (the amendment of 2026-10-26, after the
[research analysis](../operations/research-2026-10-25/analysis.md), item 1). No model call; it
needs no word of Julia's.

## Why

Every published answer number of this repository is a share of graded answers: good, bad,
partial. None says how many questions got an answer at all, and V4 was adopted for declining
less. A prompt that answers more can look better or worse by the bad share alone; coverage beside
quality among the answered is how the literature reads it: the decline matrix (Codex) and
CRAG's score (Claude) of research 2, Codex's three numbers of research 3. Stage 3б and stage 4
change the answer; this is their baseline.

## Inputs

Committed judge exports only, M1 (read without the reference), one row per question:

| Key | V3 (stage 2) | V4 (stage 2b) |
|---|---|---|
| aircargo | `reports/stage2/5e308fe/p1-aircargo-judge.cases.jsonl` | `reports/answer-prompt-v4/4f48fed/v4-aircargo-judge.cases.jsonl` |
| WixQA | `reports/stage2/5e308fe/p4-wixqa-judge-m1.cases.jsonl` | `reports/answer-prompt-v4/4f48fed/v4-wixqa-judge-m1.cases.jsonl` |
| ConditionalQA | `reports/stage2/5e308fe/p4-conditionalqa-judge-m1.cases.jsonl` | `reports/answer-prompt-v4/4f48fed/v4-conditionalqa-judge-m1.cases.jsonl` |
| MultiHop-RAG (advisory) | `reports/stage2/5e308fe/p4-multihoprag-judge-m1.cases.jsonl` | — (V4 did not run it) |

## What each number is

A row with no counted verdict (`missing`) is listed and left out. Of the rest, each answer is
one of three:

- **declined** — the judge's `answers_question` is `declined`;
- **empty** — `empty_answer`: no text, no verdict;
- **answered** — every other: a text that is not a decline.

Per key and side:

1. **Coverage** — answered among the graded.
2. **Good among the answered** — grade `good`; printed beside it, **good or `partial_ok` among
   the answered**.
3. **Unsupported among the answered** — `claims_supported` below `claims_total`: an answer given
   out with at least one claim the documents do not hold.
4. **The CRAG score** — CRAG's four levels (perfect 1, acceptable 0.5, missing 0, incorrect −1),
   mapped once: grade `good` and answered 1; `partial_ok` 0.5; declined or empty 0; every other
   answered −1. The mean over the graded.
5. **The decline matrices**, counts: the judge's `context_has_answer` (true, false) against
   declined, answered; and, on the external bases, `has_reference` (the base's own gold)
   against declined, answered, empty. From each: **decline precision** — of the declines, those
   where the answer is not there (`false`) — and **decline recall** — of the questions where it
   is not there, those declined.

Shares carry Wilson's 95 % interval; on the external bases also the cluster bootstrap of stage 2
(`evaluation.semantic_ruler.cluster_summary` over each row's `cluster`), and the CRAG mean only
the bootstrap, each aircargo question its own cluster.

## How it is read

It decides nothing and changes no published number: V3's and V4's M1 records stay as they are.
It prints V3 and V4 side by side, unpaired; a paired reading is V4's record's. Both quality lines
of number 2 are named here, before the count, and both are printed. Rule (c) of
[`CLAUDE.md`](../../CLAUDE.md) on publication: the input files' SHA-256, the tool's, and the
commits of the stands that made them.

## Records

- `reports/coverage/tools/coverage_record.py` — reads the inputs above, writes
  `reports/coverage/coverage-record.json`.
- `tests/test_coverage_record.py` — the definitions on hand-made rows, and the committed
  record against the inputs.
