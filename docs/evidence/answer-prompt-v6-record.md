# Stage 5b: answer V6 record

The registered outcome is row 1: **not adopted — harm**.
The [registered spec](../specs/answer-prompt-v6.md) reads harm first. The package stays.
The deciding read is pooled M2 agreement with the reference. Detected harm wins over the pooled M1 gain by the registered order.

| Metric | Package hits / n (share) | V6 hits / n (share) | Change, pp | read95, pp | Clusters | Detected | Direction |
|---|---:|---:|---:|---|---:|---|---|
| Pooled M2 agrees | 81/180 (45.00%) | 64/180 (35.56%) | -9.44 | [-16.48, -2.38] | 117 | true | falls |

## What was compared

V6 uses the owner's V1 answer prompt in V5's frame: evidence first, then the answer. The registered shown-text function hides the evidence from the user.
It was compared with the package's own shown answers on the same 100 question ids per key, WixQA and ConditionalQA. Retrieval was held; the package's contexts were fitted to the window.

One unseeded generation per side, in-sample, one judge; policy fallbacks were allowed.

The [final reading](../../reports/answer-prompt-v6/reading-final.json) holds the public record. Differences are V6 minus package, in percentage points; read95 is the envelope of the paired Newcombe and cluster-bootstrap intervals.
A change is detected only when both intervals exclude zero in the same direction.

## The gain and the counts beside it

M1 grades without references. The pooled bad-share fall is detected. WixQA's bad-share fall is detected; ConditionalQA's is not.

| Metric | Package hits / n (share) | V6 hits / n (share) | Change, pp | read95, pp | Clusters | Detected | Direction |
|---|---:|---:|---:|---|---:|---|---|
| Pooled M1 bad | 112/200 (56.00%) | 85/200 (42.50%) | -13.50 | [-22.68, -4.57] | 137 | true | falls |
| WixQA M1 bad | 59/100 (59.00%) | 42/100 (42.00%) | -17.00 | [-31.36, -2.22] | 77 | true | falls |
| WixQA M1 good | 30/100 (30.00%) | 32/100 (32.00%) | +2.00 | [-10.78, +14.42] | 77 | false | not detected |
| ConditionalQA M1 bad | 53/100 (53.00%) | 43/100 (43.00%) | -10.00 | [-20.83, +0.96] | 60 | false | not detected |
| ConditionalQA M1 good | 38/100 (38.00%) | 41/100 (41.00%) | +3.00 | [-6.49, +12.50] | 60 | false | not detected |
| Same-context pooled M1 bad | 49/95 (51.58%) | 40/95 (42.11%) | -9.47 | [-20.56, +2.04] | 79 | false | not detected |
| ConditionalQA unanswerable declines | 5/20 (25.00%) | 10/20 (50.00%) | +25.00 | [+3.19, +45.00] | 20 | true | rises |

ConditionalQA's declines on unanswerable questions rise. These are right declines; row 1 guards against their fall. This rise is not harm.
The same-context subset does not replace the primary reading. Wrong declines are declines where the judge finds an answer in the context. These counts do not establish a cause for the M2 fall.

| Base | Wrong declines, package / n to V6 / n | Supported claims, package | Supported claims, V6 | Same contexts / n |
|---|---|---|---|---:|
| WixQA | 18/100 to 36/100 | 453/512 (88.48%) | 228/240 (95.00%) | 46/100 |
| ConditionalQA | 7/100 to 16/100 | 314/384 (81.77%) | 195/225 (86.67%) | 49/100 |

| Defect | WixQA package to V6 (n = 100) | ConditionalQA package to V6 (n = 100) |
|---|---:|---:|
| empty | 0 to 0 | 0 to 0 |
| citation_only | 0 to 0 | 0 to 0 |
| wrong_language | 0 to 0 | 0 to 0 |
| copied_context | 0 to 0 | 0 to 0 |
| cut_off | 0 to 0 | 0 to 0 |
| repetition | 0 to 0 | 2 to 1 |
| other | 0 to 0 | 4 to 6 |

| Base | n | Parse | Repeat | Language | Language after release | Fallbacks | Prefix/whole disagreements |
|---|---:|---:|---:|---:|---:|---:|---:|
| WixQA | 100 | 0 | 0 | 0 | 0 | 0 | 0 |
| ConditionalQA | 100 | 0 | 0 | 0 | 0 | 0 | 0 |

## Timing

Each timing cell is median / p90 seconds, with its n. All batches and clean batches are shown separately.
V6-only stream time is not a latency claim. First-shown time and fallback-inclusive totals sit beside it. Full buffer is the observed answer-part end, or fallback first shown on the same clock.
Fallback stream spreads are absent: WixQA 0/100, ConditionalQA 0/100 fallbacks. Batch idle readings remain in the public record.

| Base / batches | n | Package first | V6 first shown | Full buffer | Package whole | V6-only stream | Total with fallback |
|---|---:|---:|---:|---:|---:|---:|---:|
| WixQA / all | 100 | 52.547 / 74.115 | 54.563 / 71.880 | 59.462 / 80.349 | 79.735 / 149.661 | 59.466 / 80.355 | 59.466 / 80.355 |
| WixQA / clean | 100 | 52.547 / 74.115 | 54.563 / 71.880 | 59.462 / 80.349 | 79.735 / 149.661 | 59.466 / 80.355 | 59.466 / 80.355 |
| ConditionalQA / all | 100 | 52.365 / 68.419 | 58.314 / 102.237 | 65.864 / 105.409 | 83.276 / 149.335 | 65.870 / 105.413 | 65.870 / 105.413 |
| ConditionalQA / clean | 90 | 52.164 / 70.334 | 57.208 / 74.463 | 63.265 / 83.911 | 82.724 / 148.416 | 63.270 / 83.918 | 63.270 / 83.918 |

## Bridges and execution

The laptop judge used `claude-opus-5-5`, effort `max`, tools `none`, on the frozen stage 5 isolated route. A bridge re-grades kept package replies to check judge drift; it is not another judge.

| Bridge | Agree / n | Quadratic kappa | Status |
|---|---:|---:|---|
| WixQA | 14/15 | 0.9589 | counted |
| ConditionalQA | 13/15 | 0.8148 | counted |

For each key the order was M1 (115 requests), bridge (15 new re-grades), then M2 (115 requests), in foreground chunks. No plan stopped. Every plan and bridge counts.
Operator history, 2026-11-02 UTC: attempt-02 began at 02:22; WixQA and ConditionalQA completed. Receipts froze their plans before grading: `d15fa87` (WixQA), `a7202e4` (ConditionalQA).

aircargo is **NOT_EVIDENCE**, not answered whole; it is `not_run`, with no receipt, grade or public file.
aircargo attempt-02 ended in its first batch on the owner's external stop at 10:22:58. attempt-03 refused in preflight before any request because the model server was down.
aircargo attempt-04 began at 14:17 after restarting the same Ollama 0.33.2 with the same model digest. The judge's harm STOP ended it at 17:18. The spec requires detected harm to decide without later keys.

## Provenance and limits

Both recorded stands are `2057ad0`. Registration: `9f968bb`; amendment 1: `4a5c36e`.
Spec SHA-256: `2ea4da508c4812e0fe38ffac2a6d0fc04ee6ecbafa877fbc75a7d14f52983fce`.
The operator reports the final reader ran on the laptop in the focused venv with Python 3.11.13 and exited 2 for detected harm.
The final reading is byte-identical to `2057ad0/reading-conditionalqa-after-m2.json`. The other per-key readings are earlier partial readings, each with its own hash.
The [artifact test](../../tests/test_answer_prompt_v6_record_artifact.py) pins public file hashes and LF bytes, verifies the registered tool hashes, and rebuilds the public reading. Its docstring names the private replay and admission checks it cannot repeat.

The spec has nine one-sided harm reads: the union-bound false-harm probability is up to 22.5%. This is a conservative selection rule, not multiplicity-adjusted confirmatory inference.

"Not detected" does not mean "no difference".

No person graded anything (owner's decision D11). Author and judge share one model family (D12).

The package stays. The next quality step is the generator pilot.
