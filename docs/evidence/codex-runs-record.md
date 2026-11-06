# Codex runs: calls, tokens, duration and the account window

The cost side is now recorded beside the [codex-only quality reading](codex-only-quality-record.md).
The owner's question of 2026-11-06 was «Почему запуски на Codex записаны только наполовину?».
Until now the product measurement recorded call counts and quality, not the cost side.
This record reads the copied public outputs; it makes no new requests.

## Provenance

The session ran `reports/codex-usage/tools/codex_usage.py`, commit `79652de`, on 2026-11-06.
Its SHA-256 and the copied outputs' SHA-256 are below. Three sources supplied the reading:

- The product measurement's capture folders of the codex-only attempts.
- Codex's own task logs of the account profile used for this project, classified by folder prefix:
  `executor` is the executor's package; `stage5v` is stage 5в's private stand;
  `rag_new_session` is the repository folder through 2026-10-30. Private prefixes are not published.
- Stage 5в's committed arm files, `reports/generator-ceiling/attempt-02`.

The [artifact test](../../tests/test_codex_runs_record_artifact.py) binds the capsule to these
files and the tool, checks every table against summary.json, and checks the public guard and LF.
It does not reopen the private sources or repeat extraction.

## Files

CSV counts exclude their headers; summary.json is one summary object, not a row table.
The tool is source code. All files use UTF-8 and LF.

| File | SHA-256 | Data rows |
| --- | --- | --- |
| `reports/codex-usage/tools/codex_usage.py` | `6a38e31318940ef3835dc270226a2564122d133d0ad1de2d9b413c6b9fe85ba1` | — |
| `reports/codex-usage/capture-calls.csv` | `87ad716cae16153401cbf8bf5d22d92b704b1394f779415cf28ecaca94258600` | 1952 |
| `reports/codex-usage/rollouts.csv` | `e633ccc7aaae85190c6bd02c641a70577a1ef5dac080eac52f4636bd20f011a4` | 553 |
| `reports/codex-usage/window-hours.csv` | `94a6ee19f294f01b8b527da932855d22f1228add91be06f7e0e8b9bffc672f90` | 739 |
| `reports/codex-usage/summary.json` | `c4341031146549c988ed5ad60871683a49d616e2569b05e1f720b4f5ad825893` | — |

## Capture calls

Helper means low effort: query transform and document grade. Answer means xhigh.
Counts cover the captured attempts, including probes, pilots and interrupted work;
Questions is the tool's distinct-question count, not the quality reading's accepted denominator.

| Series | Questions | Helper | Answer | Other | Completed |
| --- | --- | --- | --- | --- | --- |
| attempt-01 | 12 | 22 | 12 | 0 | 33 |
| attempt-03 | 132 | 262 | 131 | 0 | 392 |
| attempt-04 | 22 | 42 | 22 | 0 | 64 |
| attempt-05 | 187 | 372 | 187 | 0 | 558 |
| attempt-06 | 302 | 601 | 301 | 0 | 902 |

## Capture tokens and durations

Tokens are per-role sums. Durations are per call in seconds; missing durations are omitted
from the percentiles. A dash is absent, not zero. Cache write is printed separately.

| Series | Role | Input | Cached input | Cache write | Output | Reasoning | Median s | P90 s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| attempt-01 | helper | 357290 | 196096 | 0 | 1781 | 0 | 18.916 | 23.772 |
| attempt-01 | answer | 183503 | 33024 | 0 | 4588 | 3037 | 32.723 | 41.476 |
| attempt-01 | other | 0 | 0 | 0 | 0 | 0 | — | — |
| attempt-03 | helper | 4231887 | 2969088 | 0 | 21916 | 290 | 17.141 | 22.240 |
| attempt-03 | answer | 2182955 | 1323008 | 0 | 53451 | 36477 | 27.767 | 35.582 |
| attempt-03 | other | 0 | 0 | 0 | 0 | 0 | — | — |
| attempt-04 | helper | 682423 | 479232 | 0 | 3939 | 85 | 14.722 | 19.123 |
| attempt-04 | answer | 367586 | 258048 | 0 | 9991 | 6701 | 24.915 | 32.166 |
| attempt-04 | other | 0 | 0 | 0 | 0 | 0 | — | — |
| attempt-05 | helper | 6037292 | 4396800 | 0 | 31635 | 108 | 14.245 | 19.162 |
| attempt-05 | answer | 3088224 | 2001408 | 0 | 75616 | 52667 | 23.418 | 34.643 |
| attempt-05 | other | 0 | 0 | 0 | 0 | 0 | — | — |
| attempt-06 | helper | 9759679 | 7178496 | 0 | 55900 | 236 | 16.288 | 21.160 |
| attempt-06 | answer | 5022029 | 3458304 | 0 | 122416 | 82158 | 28.413 | 40.518 |
| attempt-06 | other | 0 | 0 | 0 | 0 | 0 | — | — |

## Capture window share — upper bound

Before → after are account-window snapshots, in percent. Difference and per-question share
are percentage points; the divisor is Questions above. A series with a reset has no share.

| Series | Before % | After % | Difference pp | Per question pp | Reset | Upper bound |
| --- | --- | --- | --- | --- | --- | --- |
| attempt-01 | 86.000 | 94.000 | 8.000 | 0.667 | false | true |
| attempt-03 | 89.000 | 94.000 | 5.000 | 0.038 | false | true |
| attempt-04 | 95.000 | 99.000 | 4.000 | 0.182 | false | true |
| attempt-05 | 95.000 | 17.000 | — | — | true | true |
| attempt-06 | 7.000 | 17.000 | 10.000 | 0.033 | false | true |

## Rollout classes

These are task-log totals by the classes above. Duration is per task, in seconds,
not an answer's latency; tasks may include several turns and pauses.

| Class | Tasks | Turns | Responses | Input | Cached input | Cache write | Output | Reasoning | Total | Median s | P90 s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| executor | 41 | 91 | 1888 | 160097172 | 152805888 | 0 | 1810509 | 445596 | 161907681 | 928.853 | 2196.723 |
| rag_new_session | 206 | 457 | 9998 | 796993015 | 752210176 | 0 | 6252411 | 2972403 | 803245426 | 932.518 | 6776.141 |
| stage5v | 306 | 306 | 306 | 5534061 | 2824192 | 0 | 125104 | 85302 | 5659165 | 20.700 | 29.731 |

## Window lengths seen

| Minutes |
| --- |
| 300 |
| 10080 |
| 43200 |

## Hours the window was reached

UTC hour buckets observed in account snapshots; these are not durations spent at the limit.

| Hour UTC |
| --- |
| 2026-09-30T21:00:00Z |
| 2026-10-02T17:00:00Z |
| 2026-10-09T20:00:00Z |
| 2026-10-17T20:00:00Z |
| 2026-11-01T23:00:00Z |
| 2026-11-05T01:00:00Z |

## How to read

The window share is an upper bound: the measurement's calls leave no Codex task log,
so other tasks' snapshots bracket them, and other work of the account shares that window.
Brackets can overlap; do not add series shares. A reset between brackets leaves no share.
Tokens are not money: the account is a subscription. Cached input is part of input;
reasoning is part of output. Do not add either subset again to its parent count.

## What it does not say

This is not a bill, an isolated attribution of account usage, or a complete account history.
It does not establish cost per accepted answer, answer quality, or comparable speed across
classes. The private sources were read by the session; their extraction cannot be reproduced
from these public aggregates. No question, case id, base path or base text is published here.
