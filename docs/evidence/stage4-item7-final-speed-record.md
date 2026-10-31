# Stage 4, item 7: final-path speed — 2026-10-31

The record is **counted**: 30 readable questions, 0 re-asks, and no marked disturbance.
The SLO proposals are **270 s to first word** and **360 s for the whole answer**.
They are proposals for Julia to name, not an adopted SLO.

Stand `138f3b3f6ac223540965cc831838ff4f671a2200` is the same stand as item 6.
This was a separate run under [item 7's spec](../specs/stage4-item7-final-speed.md), on an
idle Mac after all item 6 transfers. Its launch records `exclusive_owned_work=true`.
Only the run's own work was admitted on the Mac. It used the package and V4 prompt described
in [item 6's capsule](stage4-item6-final-aircargo-record.md), with the same questions and corpus.
The questions are the initial aircargo sequence used by the historical speed runs.

Public records are in [`reports/stage4-final/138f3b3/`](../../reports/stage4-final/138f3b3/).
The [artifact test](../../tests/test_stage4_item7_speed_artifact.py) pins the files and rebuilds
the quantiles, exact intervals, paired sign tests and proposals with the committed reader.

## Times

First word is `first_token_sec`; whole answer is `result_sec`. Stream close is `total_sec`,
including suggestions. All intervals below are exact order-statistic confidence sets;
their coverage can exceed the nominal level because the ranks are discrete.

| Time, seconds (n = 30) | Median | Exact 95% interval | Nearest-rank p90 | Exact 95% interval |
|---|---:|---|---:|---|
| First word | 89.2985 | [82.977, 98.644] | 255.5730 | [111.159, unbounded] |
| Whole answer | 170.1755 | [163.006, 190.617] | 338.8450 | [202.585, unbounded] |
| Stream close including suggestions | 183.2975 | [176.989, 208.851] | 351.8910 | [217.826, unbounded] |

Median interval ranks are 10 and 21, with coverage 95.722605%.
The p90 point is order statistic 27; interval ranks are 23 and 31, with coverage 99.221638%.
At n = 30, rank 31 is unbounded (`null` in the record); it is not the observed maximum.

## Historical comparison and proposal

The comparison is descriptive whole-path change against 19beeb1: V3 to V4, package, cache cap and intervening code; decides nothing.
The signs compare the same questions. Item 5's medians are also descriptive. Neither comparison
attributes the change to one lever or decides the SLO.

| Time (n = 30 pairs) | Faster | Slower | Ties | Exact sign-test p | 19beeb1 median, s | Item 5 median, s |
|---|---:|---:|---:|---:|---:|---:|
| First word | 25 | 5 | 0 | 0.000324914232 | 223.2910 | 230.6555 |
| Whole answer | 24 | 6 | 0 | 0.001430906355 | 319.6285 | 331.7055 |

Rule: ceil(p90 / 30) × 30 seconds. Julia; these are proposals, not an adopted SLO.
The proposals round the observed quantiles up; they do not turn the unbounded confidence
limits into guarantees.

The new run's question and corpus digests match item 6. Both baselines bind the same question
file and list their source-file hashes. Historical corpus digests are absent from both baseline extracts;
the test cannot independently establish equality of their historical corpus bytes.
The public per-question summaries retain swap and llama-server memory readings. Raw samples,
idle checks and launch logs remain private, so their hashes bind observations that this test
cannot repeat.

## Duration

The registered forecast was 10,980 s; the series stop was 32,940 s.
The orchestrator reports from the private run log: 2026-10-31, 11:31:38Z to 13:32:00Z,
7,222 s wall time, with `FINAL_DONE final-speed-aircargo-b01 complete`.
These timestamps and wall duration are not reconstructed from the public extracts.

## Files

| File | SHA-256 |
|---|---|
| `speed.json` | `41cd1a602e08cf5a3a69d4bed35269b11164bf14b7caf9cdab7596e360c403ba` |
| `baseline-19beeb1.json` | `967f11c896d618594b34cefcae4b1c1644ee8490b02be0535bd2b2a4f53455d5` |
| `baseline-item5.json` | `41cc0df7762de7393187c50229983b80a880c29c8856ed5141d843fc03eca9a3` |

## What it does not say

One Mac, one day, 30 questions. This is neither a throughput nor a concurrency measurement.
There is no attribution to a single lever. It does not measure answer quality; item 6 reads
aircargo quality and stage 5 addresses the external bases.
