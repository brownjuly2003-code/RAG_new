# Bundle 0: reranker thresholds for role 2 — only keeping everything qualifies

**T00 is selected: threshold 0.0, every H document kept.**
No filtering threshold in the registered grid, and not the gap rule A, can replace
the batched document grader: each loses gold or empties contexts beyond the registered
limit, so the grader stays; T00 is H itself.

T01 (0.05): ConditionalQA zero kept 9/100; sent H 58 → 53, b/c 5/0, p 0.0625.
T02 (0.10): ConditionalQA zero kept 13/100; sent H 58 → 50, b/c 8/0, p 0.0078125.
T01 fails the per-base zero-kept condition, despite no detected per-base loss.
T02 fails both the ConditionalQA loss condition and the zero-kept condition.
T02 also exceeds the zero limit on WixQA: 6/100.
Every higher threshold also fails the registered choice. A keeps context but loses gold:
A pooled sent: H 125 → 90 of 180, b/c 35/0, p 5.820766091346741e-11, loss.
A fails the loss condition on both deciding bases, with no zero-kept questions there.

## What ran and why

[Research 8](../operations/research-2026-11-06/report-8-laptop-small-model.md), §3
«Негенеративные замены» and §4, row 0, proposed using the existing reranker scores for
role 2, the batched document grader. The [spec](../specs/bundle0-reranker-threshold.md)
was registered in `9672502` before the run. Role 2 asks whether each document contains
useful information, including partial relevance. This replay measures context gold
retention against H, using the saved bge-reranker-v2-m3 INT8 ONNX sigmoid scores.

The session ran the spec's Mac recipe on 2026-11-06 and copied only the three public
outputs below. H is stage 7's H_new, reconstructed from the existing score journal,
with parent expansion and V4's answer-window fit. T(t) keeps scores >= t in H's order.
The registered grid is T00..T20, t = i/20 for i = 0..20; equality keeps a document and
there is no forced first document. Scores are ranking scores, not calibrated probabilities.
A uses the largest adjacent gap in the stably sorted scores, taking the longest prefix
on a tied positive gap, all documents for a flat vector, then restoring H's order.
A is the registered maximum-gap baseline, not an implementation of Tail-Aware Adaptive-k.
Filtering acts on H's already expanded documents; retained documents are fitted anew,
without re-expanding seeds. No new search, rescoring, model call or product edit was made.

## Provenance and parity

The [record](../../reports/bundle0/9672502/record.json) names the measured Mac overlay
and its parent, the registering commit. The artifact directory names the registration,
not the measured HEAD. The score journal retains its original stage-7 HEAD.
The [artifact test](../../tests/test_bundle0_record_artifact.py) binds the copied bytes,
parses every table and rebuilds its numbers from the record; it also rebuilds the
readings from the rows and the choice through the replay tool's `eligible` and `select`.
The test reads the spec, tool and synthetic test with `git show` at the recorded parent.
There is no fallback and no lookup of the measured overlay, which exists only on the Mac.
The repository's full history is required; CI uses `fetch-depth: 0`.
A clone missing the parent fails that historical check rather than skipping it.

| Run item | Value |
| --- | --- |
| head | `41d5f45192a08b79e9d4d462691c6c7b1b2f1912` |
| head_parent | `9672502480afa34898c5fe4eb8ba02ef0a0c969d` |
| spec_sha256 | `ddc7fe4fbf5bed7d3089ba3d29587ae04d40b6fd7f611e10f971e56c9afabf1a` |
| tool_sha256 | `8a1d31439421808c041f6872d2b19afcdc17a2f92a9234ab8b37575a5d5b374a` |
| test_sha256 | `992ef18ee559b1d2e3d837332bbdc53b9fb427666f62b6bbb93eab335fe1dccc` |
| score_head | `f59169310a026f8962cfdfed01b573be28b9becc` |
| capture_sha256 | `a4eb14fed0f25d97f0bd7981718498cec10867d8b82709b69865279643670dd3` |

The spec's SHA list covers the tool and synthetic test, not the spec itself.
Their recorded hashes are checked against that list and the parent's committed bytes;
`spec_sha256` binds the registered spec bytes. The current copies must also match.
The record separately retains `measure_code_sha256` and `grader_code_sha256` maps,
bound here by the record's file digest. Its four frozen input digests are:

| Frozen input | SHA-256 |
| --- | --- |
| `reports/stage7/tools/arms_replay.py` | `6ca8b723841d08dfd6f5d084bdc0883264c889eb495dc4d3728ac0a2ea623689` |
| `reports/stage7/5e308fe/record.json` | `b9db1434a6091536540112591e29cb3f02f373660dd06469e6abebc3780b55e4` |
| `reports/stage7/5e308fe/int8_scores.jsonl` | `5c4d2bbcc42fe17afb516c877fdeacf7bc3bd05beb8557870b7d1f7bedb156a6` |
| `reports/stage7/5e308fe/rows.jsonl` | `2d87859ecfd5e2442eefadcc5dafb471e5a80d13d8227907d59e568010109627` |

H uses K 14, window 3,584, input limit 2,176, runtime `onnx`.
INT8 export SHA-256: `57335a9f061fe31378c160ddd0861711a0fbdfa20f70aa2640d473dfc4bc1343`.
The service environment and offline settings are the ones already published in the
[stage-7 capsule](stage7-step1-arms-record.md#provenance-and-method); no new environment
paths are published here. The private capture stayed private; only its digest and match
counts are published. A match requires the same bound case and a byte-equal stripped
batch prompt over all of H's expanded documents in order, with one complete accepted call.
The product's grader parser supplies the keep set; unmatched capture is unavailable,
never an empty keep set.

Parity passed 415 of 415.
The gate compares each complete H entry, including both gold points, counts, prompt hash,
character/token estimates, cut and unresolved flags, plus the row's identity and gold flag,
to frozen stage-7 H. The scored pool and five are checked separately. Any break refuses
publication. This is H_new parity, not stage 7's earlier H_old/V4 byte-parity experiment.
The last line of `run.out` agrees with the record's parity and selection.

## How to read the tables

The deciding bases are WixQA and ConditionalQA. A primary hit is `gold_article` on WixQA,
`all_evidence_coverage` on ConditionalQA (and on the non-deciding MultiHop-RAG).
Secondary means are `gold_articles` and `evidence_recall`, respectively; no pooled
secondary mean is defined. b is H-only hit, c arm-only. p is exact two-sided McNemar,
printed as stored, including small nonzero values in scientific notation. Loss requires
b > c and p < 0.05; gain requires c > b and p < 0.05; otherwise no detected difference.

The registered choice takes the largest threshold with no detected loss at **sent** on
each deciding base, no unread/missing cases there, and at most 5% zero-kept questions
on each base. Gold-free questions remain in that zero denominator. Pooling cannot rescue
a failing base; the pooled readings stand beside and are not an additional selection gate.
A is assessed by the same conditions, without ranking it against the selected threshold.

T00..T20 and A have no unread or missing cases on any base.
The following common denominators apply to every T/A arm. Paired n counts available gold;
questions with no gold are not gold misses. aircargo pools its two labels and has no
context gold, so its gold readings are `NOT_EVIDENCE`. MultiHop-RAG is non-deciding;
its full readings and all arms' usage remain in the linked record.

| Base | Total | Gold | Unread | Missing | Paired sent | Paired expanded |
| --- | --- | --- | --- | --- | --- | --- |
| WixQA | 100 | 100 | 0 | 0 | 100 | 100 |
| ConditionalQA | 100 | 80 | 0 | 0 | 80 | 80 |
| Deciding bases pooled | 200 | 180 | 0 | 0 | 180 | 180 |
| MultiHop-RAG | 100 | 70 | 0 | 0 | 70 | 70 |
| aircargo | 115 | 0 | 0 | 0 | — | — |

H's usage is the T00 baseline. Means below are rounded to three decimals at most;
secondary means retain the record's four-decimal precision. Estimated sent tokens
count document text, not the full prompt. Zero kept is after filtering; zero sent is
after fitting. A zero-kept question remains in usage and is a miss when gold exists;
in the product it would route to a person. The two zero counts are reported separately.

| H base | Questions | Zero kept / sent | Kept mean / median | Sent documents mean / median | Sent estimated tokens mean / median |
| --- | --- | --- | --- | --- | --- |
| WixQA | 100 | 0 / 0 | 5 / 5 | 4.75 / 5 | 1633.87 / 1729.5 |
| ConditionalQA | 100 | 0 / 0 | 5 / 5 | 4.74 / 5 | 1544.52 / 1673.5 |
| Deciding bases pooled | 200 | 0 / 0 | 5 / 5 | 4.745 / 5 | 1589.195 / 1706.5 |
| MultiHop-RAG | 100 | 0 / 0 | 5 / 5 | 3.51 / 3 | 1682.93 / 1711 |
| aircargo | 115 | 0 / 0 | 5 / 5 | 3 / 3 | 1757.591 / 1784 |

## Sent — the deciding point

| Arm and base at sent | n | H → arm hits | b / c | p | Reading | Zero kept / sent | Mean sent documents | Mean sent estimated tokens | Secondary mean H / arm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T00: WixQA | 100 | 67 → 67 | 0 / 0 | 1.0 | no detected difference | 0 / 0 | 4.75 | 1633.87 | 0.6317 / 0.6317 |
| T00: ConditionalQA | 80 | 58 → 58 | 0 / 0 | 1.0 | no detected difference | 0 / 0 | 4.74 | 1544.52 | 0.8064 / 0.8064 |
| T00: Deciding bases pooled | 180 | 125 → 125 | 0 / 0 | 1.0 | no detected difference | 0 / 0 | 4.745 | 1589.195 | — |
| T01: WixQA | 100 | 67 → 65 | 2 / 0 | 0.5 | no detected difference | 3 / 3 | 4.42 | 1528.67 | 0.6317 / 0.6117 |
| T01: ConditionalQA | 80 | 58 → 53 | 5 / 0 | 0.0625 | no detected difference | 9 / 9 | 3.69 | 1210.52 | 0.8064 / 0.7637 |
| T01: Deciding bases pooled | 180 | 125 → 118 | 7 / 0 | 0.015625 | loss | 12 / 12 | 4.055 | 1369.595 | — |
| T02: WixQA | 100 | 67 → 63 | 4 / 0 | 0.125 | no detected difference | 6 / 6 | 4.2 | 1451.51 | 0.6317 / 0.5917 |
| T02: ConditionalQA | 80 | 58 → 50 | 8 / 0 | 0.0078125 | loss | 13 / 13 | 3.32 | 1098.9 | 0.8064 / 0.7171 |
| T02: Deciding bases pooled | 180 | 125 → 113 | 12 / 0 | 0.00048828125 | loss | 19 / 19 | 3.76 | 1275.205 | — |
| T03: WixQA | 100 | 67 → 60 | 7 / 0 | 0.015625 | loss | 8 / 8 | 3.99 | 1380.48 | 0.6317 / 0.5617 |
| T03: ConditionalQA | 80 | 58 → 47 | 11 / 0 | 0.0009765625 | loss | 15 / 15 | 3.02 | 1012.63 | 0.8064 / 0.6971 |
| T03: Deciding bases pooled | 180 | 125 → 107 | 18 / 0 | 7.62939453125e-06 | loss | 23 / 23 | 3.505 | 1196.555 | — |
| T04: WixQA | 100 | 67 → 60 | 7 / 0 | 0.015625 | loss | 10 / 10 | 3.86 | 1333.24 | 0.6317 / 0.5617 |
| T04: ConditionalQA | 80 | 58 → 46 | 12 / 0 | 0.00048828125 | loss | 16 / 16 | 2.84 | 945.13 | 0.8064 / 0.6825 |
| T04: Deciding bases pooled | 180 | 125 → 106 | 19 / 0 | 3.814697265625e-06 | loss | 26 / 26 | 3.35 | 1139.185 | — |
| T05: WixQA | 100 | 67 → 55 | 12 / 0 | 0.00048828125 | loss | 15 / 15 | 3.65 | 1254.23 | 0.6317 / 0.5150 |
| T05: ConditionalQA | 80 | 58 → 44 | 14 / 0 | 0.0001220703125 | loss | 20 / 20 | 2.64 | 892.49 | 0.8064 / 0.6638 |
| T05: Deciding bases pooled | 180 | 125 → 99 | 26 / 0 | 2.9802322387695312e-08 | loss | 35 / 35 | 3.145 | 1073.36 | — |
| T06: WixQA | 100 | 67 → 53 | 14 / 0 | 0.0001220703125 | loss | 18 / 18 | 3.5 | 1197.33 | 0.6317 / 0.4950 |
| T06: ConditionalQA | 80 | 58 → 42 | 16 / 0 | 3.0517578125e-05 | loss | 24 / 24 | 2.51 | 838.62 | 0.8064 / 0.6300 |
| T06: Deciding bases pooled | 180 | 125 → 95 | 30 / 0 | 1.862645149230957e-09 | loss | 42 / 42 | 3.005 | 1017.975 | — |
| T07: WixQA | 100 | 67 → 53 | 14 / 0 | 0.0001220703125 | loss | 20 / 20 | 3.34 | 1133.27 | 0.6317 / 0.4950 |
| T07: ConditionalQA | 80 | 58 → 39 | 19 / 0 | 3.814697265625e-06 | loss | 26 / 26 | 2.31 | 785.56 | 0.8064 / 0.6044 |
| T07: Deciding bases pooled | 180 | 125 → 92 | 33 / 0 | 2.3283064365386963e-10 | loss | 46 / 46 | 2.825 | 959.415 | — |
| T08: WixQA | 100 | 67 → 53 | 14 / 0 | 0.0001220703125 | loss | 21 / 21 | 3.27 | 1109.66 | 0.6317 / 0.4950 |
| T08: ConditionalQA | 80 | 58 → 36 | 22 / 0 | 4.76837158203125e-07 | loss | 28 / 28 | 2.1 | 720.16 | 0.8064 / 0.5773 |
| T08: Deciding bases pooled | 180 | 125 → 89 | 36 / 0 | 2.9103830456733704e-11 | loss | 49 / 49 | 2.685 | 914.91 | — |
| T09: WixQA | 100 | 67 → 53 | 14 / 0 | 0.0001220703125 | loss | 22 / 22 | 3.21 | 1090.09 | 0.6317 / 0.4950 |
| T09: ConditionalQA | 80 | 58 → 33 | 25 / 0 | 5.960464477539063e-08 | loss | 33 / 33 | 1.86 | 634.32 | 0.8064 / 0.5327 |
| T09: Deciding bases pooled | 180 | 125 → 86 | 39 / 0 | 3.637978807091713e-12 | loss | 55 / 55 | 2.535 | 862.205 | — |
| T10: WixQA | 100 | 67 → 52 | 15 / 0 | 6.103515625e-05 | loss | 22 / 22 | 3.1 | 1051.52 | 0.6317 / 0.4850 |
| T10: ConditionalQA | 80 | 58 → 33 | 25 / 0 | 5.960464477539063e-08 | loss | 37 / 37 | 1.71 | 580.77 | 0.8064 / 0.5307 |
| T10: Deciding bases pooled | 180 | 125 → 85 | 40 / 0 | 1.8189894035458565e-12 | loss | 59 / 59 | 2.405 | 816.145 | — |
| T11: WixQA | 100 | 67 → 51 | 16 / 0 | 3.0517578125e-05 | loss | 25 / 25 | 3 | 1019.96 | 0.6317 / 0.4750 |
| T11: ConditionalQA | 80 | 58 → 29 | 29 / 0 | 3.725290298461914e-09 | loss | 46 / 46 | 1.53 | 515.36 | 0.8064 / 0.4519 |
| T11: Deciding bases pooled | 180 | 125 → 80 | 45 / 0 | 5.684341886080802e-14 | loss | 71 / 71 | 2.265 | 767.66 | — |
| T12: WixQA | 100 | 67 → 51 | 16 / 0 | 3.0517578125e-05 | loss | 25 / 25 | 2.87 | 970.79 | 0.6317 / 0.4750 |
| T12: ConditionalQA | 80 | 58 → 29 | 29 / 0 | 3.725290298461914e-09 | loss | 48 / 48 | 1.39 | 473.42 | 0.8064 / 0.4519 |
| T12: Deciding bases pooled | 180 | 125 → 80 | 45 / 0 | 5.684341886080802e-14 | loss | 73 / 73 | 2.13 | 722.105 | — |
| T13: WixQA | 100 | 67 → 51 | 16 / 0 | 3.0517578125e-05 | loss | 26 / 26 | 2.77 | 943.57 | 0.6317 / 0.4750 |
| T13: ConditionalQA | 80 | 58 → 27 | 31 / 0 | 9.313225746154785e-10 | loss | 49 / 49 | 1.25 | 421.49 | 0.8064 / 0.4283 |
| T13: Deciding bases pooled | 180 | 125 → 78 | 47 / 0 | 1.4210854715202004e-14 | loss | 75 / 75 | 2.01 | 682.53 | — |
| T14: WixQA | 100 | 67 → 48 | 19 / 0 | 3.814697265625e-06 | loss | 30 / 30 | 2.65 | 904.08 | 0.6317 / 0.4500 |
| T14: ConditionalQA | 80 | 58 → 26 | 32 / 0 | 4.656612873077393e-10 | loss | 55 / 55 | 1.11 | 374.3 | 0.8064 / 0.4096 |
| T14: Deciding bases pooled | 180 | 125 → 74 | 51 / 0 | 8.881784197001252e-16 | loss | 85 / 85 | 1.88 | 639.19 | — |
| T15: WixQA | 100 | 67 → 44 | 23 / 0 | 2.384185791015625e-07 | loss | 34 / 34 | 2.52 | 859.77 | 0.6317 / 0.4150 |
| T15: ConditionalQA | 80 | 58 → 23 | 35 / 0 | 5.820766091346741e-11 | loss | 58 / 58 | 0.99 | 331.65 | 0.8064 / 0.3721 |
| T15: Deciding bases pooled | 180 | 125 → 67 | 58 / 0 | 6.938893903907228e-18 | loss | 92 / 92 | 1.755 | 595.71 | — |
| T16: WixQA | 100 | 67 → 43 | 24 / 0 | 1.1920928955078125e-07 | loss | 36 / 36 | 2.4 | 817.38 | 0.6317 / 0.4050 |
| T16: ConditionalQA | 80 | 58 → 20 | 38 / 0 | 7.275957614183426e-12 | loss | 63 / 63 | 0.86 | 282.41 | 0.8064 / 0.3346 |
| T16: Deciding bases pooled | 180 | 125 → 63 | 62 / 0 | 4.336808689942018e-19 | loss | 99 / 99 | 1.63 | 549.895 | — |
| T17: WixQA | 100 | 67 → 39 | 28 / 0 | 7.450580596923828e-09 | loss | 42 / 42 | 2.19 | 746.52 | 0.6317 / 0.3700 |
| T17: ConditionalQA | 80 | 58 → 20 | 38 / 0 | 7.275957614183426e-12 | loss | 68 / 68 | 0.72 | 239.26 | 0.8064 / 0.3139 |
| T17: Deciding bases pooled | 180 | 125 → 59 | 66 / 0 | 2.710505431213761e-20 | loss | 110 / 110 | 1.455 | 492.89 | — |
| T18: WixQA | 100 | 67 → 38 | 29 / 0 | 3.725290298461914e-09 | loss | 44 / 44 | 2 | 697.8 | 0.6317 / 0.3600 |
| T18: ConditionalQA | 80 | 58 → 15 | 43 / 0 | 2.2737367544323206e-13 | loss | 74 / 74 | 0.52 | 172.23 | 0.8064 / 0.2347 |
| T18: Deciding bases pooled | 180 | 125 → 53 | 72 / 0 | 4.235164736271502e-22 | loss | 118 / 118 | 1.26 | 435.015 | — |
| T19: WixQA | 100 | 67 → 31 | 36 / 0 | 2.9103830456733704e-11 | loss | 49 / 49 | 1.58 | 553.15 | 0.6317 / 0.2950 |
| T19: ConditionalQA | 80 | 58 → 11 | 47 / 0 | 1.4210854715202004e-14 | loss | 80 / 80 | 0.35 | 110.95 | 0.8064 / 0.1779 |
| T19: Deciding bases pooled | 180 | 125 → 42 | 83 / 0 | 2.0679515313825692e-25 | loss | 129 / 129 | 0.965 | 332.05 | — |
| T20: WixQA | 100 | 67 → 0 | 67 / 0 | 1.3552527156068805e-20 | loss | 100 / 100 | 0 | 0 | 0.6317 / 0.0000 |
| T20: ConditionalQA | 80 | 58 → 0 | 58 / 0 | 6.938893903907228e-18 | loss | 100 / 100 | 0 | 0 | 0.8064 / 0.0000 |
| T20: Deciding bases pooled | 180 | 125 → 0 | 125 / 0 | 4.70197740328915e-38 | loss | 200 / 200 | 0 | 0 | — |
| A: WixQA | 100 | 67 → 52 | 15 / 0 | 6.103515625e-05 | loss | 0 / 0 | 2.45 | 897.08 | 0.6317 / 0.4800 |
| A: ConditionalQA | 80 | 58 → 38 | 20 / 0 | 1.9073486328125e-06 | loss | 0 / 0 | 1.75 | 616.54 | 0.8064 / 0.6508 |
| A: Deciding bases pooled | 180 | 125 → 90 | 35 / 0 | 5.820766091346741e-11 | loss | 0 / 0 | 2.1 | 756.81 | — |

## Expanded — beside the deciding point

Expanded is the retained expanded context before answer-window fitting. Its gold
reading does not select the threshold; differences from sent expose window effects
without by themselves establishing a cause.

| Arm and base at expanded | n | H → arm hits | b / c | p | Reading | Secondary mean H / arm |
| --- | --- | --- | --- | --- | --- | --- |
| T00: WixQA | 100 | 68 → 68 | 0 / 0 | 1.0 | no detected difference | 0.6417 / 0.6417 |
| T00: ConditionalQA | 80 | 58 → 58 | 0 / 0 | 1.0 | no detected difference | 0.8064 / 0.8064 |
| T00: Deciding bases pooled | 180 | 126 → 126 | 0 / 0 | 1.0 | no detected difference | — |
| T01: WixQA | 100 | 68 → 66 | 2 / 0 | 0.5 | no detected difference | 0.6417 / 0.6217 |
| T01: ConditionalQA | 80 | 58 → 53 | 5 / 0 | 0.0625 | no detected difference | 0.8064 / 0.7637 |
| T01: Deciding bases pooled | 180 | 126 → 119 | 7 / 0 | 0.015625 | loss | — |
| T02: WixQA | 100 | 68 → 64 | 4 / 0 | 0.125 | no detected difference | 0.6417 / 0.6017 |
| T02: ConditionalQA | 80 | 58 → 50 | 8 / 0 | 0.0078125 | loss | 0.8064 / 0.7171 |
| T02: Deciding bases pooled | 180 | 126 → 114 | 12 / 0 | 0.00048828125 | loss | — |
| T03: WixQA | 100 | 68 → 61 | 7 / 0 | 0.015625 | loss | 0.6417 / 0.5717 |
| T03: ConditionalQA | 80 | 58 → 47 | 11 / 0 | 0.0009765625 | loss | 0.8064 / 0.6971 |
| T03: Deciding bases pooled | 180 | 126 → 108 | 18 / 0 | 7.62939453125e-06 | loss | — |
| T04: WixQA | 100 | 68 → 61 | 7 / 0 | 0.015625 | loss | 0.6417 / 0.5717 |
| T04: ConditionalQA | 80 | 58 → 46 | 12 / 0 | 0.00048828125 | loss | 0.8064 / 0.6825 |
| T04: Deciding bases pooled | 180 | 126 → 107 | 19 / 0 | 3.814697265625e-06 | loss | — |
| T05: WixQA | 100 | 68 → 55 | 13 / 0 | 0.000244140625 | loss | 0.6417 / 0.5150 |
| T05: ConditionalQA | 80 | 58 → 44 | 14 / 0 | 0.0001220703125 | loss | 0.8064 / 0.6638 |
| T05: Deciding bases pooled | 180 | 126 → 99 | 27 / 0 | 1.4901161193847656e-08 | loss | — |
| T06: WixQA | 100 | 68 → 53 | 15 / 0 | 6.103515625e-05 | loss | 0.6417 / 0.4950 |
| T06: ConditionalQA | 80 | 58 → 42 | 16 / 0 | 3.0517578125e-05 | loss | 0.8064 / 0.6300 |
| T06: Deciding bases pooled | 180 | 126 → 95 | 31 / 0 | 9.313225746154785e-10 | loss | — |
| T07: WixQA | 100 | 68 → 53 | 15 / 0 | 6.103515625e-05 | loss | 0.6417 / 0.4950 |
| T07: ConditionalQA | 80 | 58 → 39 | 19 / 0 | 3.814697265625e-06 | loss | 0.8064 / 0.6044 |
| T07: Deciding bases pooled | 180 | 126 → 92 | 34 / 0 | 1.1641532182693481e-10 | loss | — |
| T08: WixQA | 100 | 68 → 53 | 15 / 0 | 6.103515625e-05 | loss | 0.6417 / 0.4950 |
| T08: ConditionalQA | 80 | 58 → 36 | 22 / 0 | 4.76837158203125e-07 | loss | 0.8064 / 0.5773 |
| T08: Deciding bases pooled | 180 | 126 → 89 | 37 / 0 | 1.4551915228366852e-11 | loss | — |
| T09: WixQA | 100 | 68 → 53 | 15 / 0 | 6.103515625e-05 | loss | 0.6417 / 0.4950 |
| T09: ConditionalQA | 80 | 58 → 33 | 25 / 0 | 5.960464477539063e-08 | loss | 0.8064 / 0.5327 |
| T09: Deciding bases pooled | 180 | 126 → 86 | 40 / 0 | 1.8189894035458565e-12 | loss | — |
| T10: WixQA | 100 | 68 → 52 | 16 / 0 | 3.0517578125e-05 | loss | 0.6417 / 0.4850 |
| T10: ConditionalQA | 80 | 58 → 33 | 25 / 0 | 5.960464477539063e-08 | loss | 0.8064 / 0.5307 |
| T10: Deciding bases pooled | 180 | 126 → 85 | 41 / 0 | 9.094947017729282e-13 | loss | — |
| T11: WixQA | 100 | 68 → 51 | 17 / 0 | 1.52587890625e-05 | loss | 0.6417 / 0.4750 |
| T11: ConditionalQA | 80 | 58 → 29 | 29 / 0 | 3.725290298461914e-09 | loss | 0.8064 / 0.4519 |
| T11: Deciding bases pooled | 180 | 126 → 80 | 46 / 0 | 2.842170943040401e-14 | loss | — |
| T12: WixQA | 100 | 68 → 51 | 17 / 0 | 1.52587890625e-05 | loss | 0.6417 / 0.4750 |
| T12: ConditionalQA | 80 | 58 → 29 | 29 / 0 | 3.725290298461914e-09 | loss | 0.8064 / 0.4519 |
| T12: Deciding bases pooled | 180 | 126 → 80 | 46 / 0 | 2.842170943040401e-14 | loss | — |
| T13: WixQA | 100 | 68 → 51 | 17 / 0 | 1.52587890625e-05 | loss | 0.6417 / 0.4750 |
| T13: ConditionalQA | 80 | 58 → 27 | 31 / 0 | 9.313225746154785e-10 | loss | 0.8064 / 0.4283 |
| T13: Deciding bases pooled | 180 | 126 → 78 | 48 / 0 | 7.105427357601002e-15 | loss | — |
| T14: WixQA | 100 | 68 → 48 | 20 / 0 | 1.9073486328125e-06 | loss | 0.6417 / 0.4500 |
| T14: ConditionalQA | 80 | 58 → 26 | 32 / 0 | 4.656612873077393e-10 | loss | 0.8064 / 0.4096 |
| T14: Deciding bases pooled | 180 | 126 → 74 | 52 / 0 | 4.440892098500626e-16 | loss | — |
| T15: WixQA | 100 | 68 → 44 | 24 / 0 | 1.1920928955078125e-07 | loss | 0.6417 / 0.4150 |
| T15: ConditionalQA | 80 | 58 → 23 | 35 / 0 | 5.820766091346741e-11 | loss | 0.8064 / 0.3721 |
| T15: Deciding bases pooled | 180 | 126 → 67 | 59 / 0 | 3.469446951953614e-18 | loss | — |
| T16: WixQA | 100 | 68 → 43 | 25 / 0 | 5.960464477539063e-08 | loss | 0.6417 / 0.4050 |
| T16: ConditionalQA | 80 | 58 → 20 | 38 / 0 | 7.275957614183426e-12 | loss | 0.8064 / 0.3346 |
| T16: Deciding bases pooled | 180 | 126 → 63 | 63 / 0 | 2.168404344971009e-19 | loss | — |
| T17: WixQA | 100 | 68 → 39 | 29 / 0 | 3.725290298461914e-09 | loss | 0.6417 / 0.3700 |
| T17: ConditionalQA | 80 | 58 → 20 | 38 / 0 | 7.275957614183426e-12 | loss | 0.8064 / 0.3139 |
| T17: Deciding bases pooled | 180 | 126 → 59 | 67 / 0 | 1.3552527156068805e-20 | loss | — |
| T18: WixQA | 100 | 68 → 38 | 30 / 0 | 1.862645149230957e-09 | loss | 0.6417 / 0.3600 |
| T18: ConditionalQA | 80 | 58 → 15 | 43 / 0 | 2.2737367544323206e-13 | loss | 0.8064 / 0.2347 |
| T18: Deciding bases pooled | 180 | 126 → 53 | 73 / 0 | 2.117582368135751e-22 | loss | — |
| T19: WixQA | 100 | 68 → 31 | 37 / 0 | 1.4551915228366852e-11 | loss | 0.6417 / 0.2950 |
| T19: ConditionalQA | 80 | 58 → 11 | 47 / 0 | 1.4210854715202004e-14 | loss | 0.8064 / 0.1779 |
| T19: Deciding bases pooled | 180 | 126 → 42 | 84 / 0 | 1.0339757656912846e-25 | loss | — |
| T20: WixQA | 100 | 68 → 0 | 68 / 0 | 6.776263578034403e-21 | loss | 0.6417 / 0.0000 |
| T20: ConditionalQA | 80 | 58 → 0 | 58 / 0 | 6.938893903907228e-18 | loss | 0.8064 / 0.0000 |
| T20: Deciding bases pooled | 180 | 126 → 0 | 126 / 0 | 2.350988701644575e-38 | loss | — |
| A: WixQA | 100 | 68 → 52 | 16 / 0 | 3.0517578125e-05 | loss | 0.6417 / 0.4800 |
| A: ConditionalQA | 80 | 58 → 38 | 20 / 0 | 1.9073486328125e-06 | loss | 0.8064 / 0.6508 |
| A: Deciding bases pooled | 180 | 126 → 90 | 36 / 0 | 2.9103830456733704e-11 | loss | — |

## G — captured grader comparison

G matched 2 of 415; unmatched 413, ambiguous 0, incomplete 0.
Full-cohort G is `NOT_EVIDENCE` at both points on every base and pooled deciding.
Missing verdicts leave gold pairs unread; aircargo has no context gold. The matched-only
subset has one gold pair on WixQA, also the only pooled deciding pair; the other match
is on aircargo without gold. The table preserves these denominators. Both points agree
for G. A dash for n means that no full-cohort pair statistic is published, not zero cases.
The available pair is a possibly selected subset, cannot establish grader gold retention
on the full cohort, and never enters threshold selection.

| G scope and base (sent = expanded) | Total | Gold | Matched | Unread | Missing | n | H → G hits | b / c | p | Reading |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Full: WixQA | 100 | 100 | 1 | 99 | 99 | — | — | — | — | NOT_EVIDENCE |
| Matched only: WixQA | 1 | 1 | 1 | 0 | 0 | 1 | 1 → 1 | 0 / 0 | 1.0 | no detected difference |
| Full: ConditionalQA | 100 | 80 | 0 | 80 | 100 | — | — | — | — | NOT_EVIDENCE |
| Matched only: ConditionalQA | 0 | 0 | 0 | 0 | 0 | — | — | — | — | NOT_EVIDENCE |
| Full: Deciding bases pooled | 200 | 180 | 1 | 179 | 199 | — | — | — | — | NOT_EVIDENCE |
| Matched only: Deciding bases pooled | 1 | 1 | 1 | 0 | 0 | 1 | 1 → 1 | 0 / 0 | 1.0 | no detected difference |
| Full: MultiHop-RAG | 100 | 70 | 0 | 70 | 100 | — | — | — | — | NOT_EVIDENCE |
| Matched only: MultiHop-RAG | 0 | 0 | 0 | 0 | 0 | — | — | — | — | NOT_EVIDENCE |
| Full: aircargo | 115 | 0 | 1 | 0 | 114 | — | — | — | — | NOT_EVIDENCE |
| Matched only: aircargo | 1 | 0 | 1 | 0 | 0 | — | — | — | — | NOT_EVIDENCE |

## What it does not say

The choice is in-sample across the registered grid, not a held-out result.
Selection across multiple thresholds is optimistic; it is not an equivalence test.
No detected difference is not equivalence or proof of no loss.
No answers or answer quality were measured.
The grader's own effect on gold is unmeasured for the full cohort.
H is the hybrid control before grading, not evidence that the existing grader preserves
gold. The result covers the registered grid and A only; it does not exclude an untested
threshold or another rule. It does not justify replacing role 2 in the running graph,
predict performance on other questions, or measure latency, memory, power or saved call time.
Recorded retrieval lanes need not equal a fresh approximate-index search.

## Files

Under `reports/bundle0/9672502/`. SHA-256 binds the three copied files. They carry ids,
flags, hashes, scores, positions, counts and readings, never question, case text,
document, answer, raw verdict or filled-prompt text. The artifact test applies the
existing `stage2_common.without_text` guard and recursive field checks, and requires
UTF-8 without BOM and LF. No private capture or new environment path is reproduced.

| File | SHA-256 |
| --- | --- |
| `record.json` | `ade70227621f5e0233423d7fa600c4f5bf085255a770f81bc7cd954dab9e288d` |
| `rows.jsonl` | `bf5ffdaf83ad8069d2f4169935535d5ef82c001a0ab114ef5706733fcdc324bd` |
| `run.out` | `00ea5032f1529cbc4b5506ea559b7909efb761533800b74523fe75bd41a473ef` |
