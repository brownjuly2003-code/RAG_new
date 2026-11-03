# Stage 5v: generator ceiling record

The registered outcome is row 2: **the generator is the bottleneck**.
The [registered spec](../specs/generator-ceiling.md) decides on pooled M1 good share where the answer is in the sent context.

| Metric | Package hits / n (share) | Codex hits / n (share) | Change, pp | read95, pp | Clusters | Detected | Direction |
|---|---:|---:|---:|---|---:|---|---|
| Pooled M1 good, answer in context | 120/224 (53.57%) | 220/224 (98.21%) | +44.64 | [+37.33, +51.83] | 191 | true | rises |

The next step is a strong model for the product. The host (a GPU or an API instead of the Mac, decision D5) is the owner's.
Production stays the 4B on the Mac until her word. No production change is authorized by this reading.

## What was compared

The package (Qwen3-4B on the Mac, prompt V4) was compared with one GPT-6-Astra answer to each of the same 300 saved prompts, byte for byte inside the wrapper.
Retrieval and context were held. Each Codex answer used profile `cw`, effort `xhigh`, in an isolated read-only task.
One unseeded generation per side, in-sample, one judge. This diagnoses the generator's share of the losses; it is not a product candidate.
The [reading](../../reports/generator-ceiling/attempt-02/reading.json) holds the public result. Differences are Codex minus package, in percentage points.
read95 is the envelope of the paired Newcombe and cluster-bootstrap intervals. A difference is detected only when both exclude zero on the same side.

## M1 by key and stratum

M1 grades without references. Undefined cells have no observations.

| Metric | Package hits / n (share) | Codex hits / n (share) | Change, pp | read95, pp | Clusters | Detected | Direction |
|---|---:|---:|---:|---|---:|---|---|
| WixQA M1 good, all | 30/100 (30.00%) | 92/100 (92.00%) | +62.00 | [+50.13, +71.26] | 77 | true | rises |
| WixQA M1 bad, all | 59/100 (59.00%) | 2/100 (2.00%) | -57.00 | [-66.67, -45.88] | 77 | true | falls |
| WixQA M1 good, answer in context | 19/67 (28.36%) | 64/67 (95.52%) | +67.16 | [+53.40, +79.03] | 56 | true | rises |
| WixQA M1 bad, answer in context | 41/67 (61.19%) | 1/67 (1.49%) | -59.70 | [-72.22, -46.08] | 56 | true | falls |
| WixQA M1 good, not in context | 11/33 (33.33%) | 28/33 (84.85%) | +51.52 | [+27.60, +70.59] | 27 | true | rises |
| WixQA M1 bad, not in context | 18/33 (54.55%) | 1/33 (3.03%) | -51.52 | [-70.97, -29.06] | 27 | true | falls |
| WixQA M1 good, no gold | 0/0 (undefined) | 0/0 (undefined) | undefined | undefined | 0 | false | not detected |
| WixQA M1 bad, no gold | 0/0 (undefined) | 0/0 (undefined) | undefined | undefined | 0 | false | not detected |
| ConditionalQA M1 good, all | 38/100 (38.00%) | 92/100 (92.00%) | +54.00 | [+42.65, +64.89] | 60 | true | rises |
| ConditionalQA M1 bad, all | 53/100 (53.00%) | 0/100 (0.00%) | -53.00 | [-63.27, -42.61] | 60 | true | falls |
| ConditionalQA M1 good, answer in context | 28/58 (48.28%) | 57/58 (98.28%) | +50.00 | [+35.00, +64.91] | 36 | true | rises |
| ConditionalQA M1 bad, answer in context | 27/58 (46.55%) | 0/58 (0.00%) | -46.55 | [-61.40, -31.48] | 36 | true | falls |
| ConditionalQA M1 good, not in context | 4/22 (18.18%) | 19/22 (86.36%) | +68.18 | [+37.74, +91.30] | 18 | true | rises |
| ConditionalQA M1 bad, not in context | 14/22 (63.64%) | 0/22 (0.00%) | -63.64 | [-85.00, -38.16] | 18 | true | falls |
| ConditionalQA M1 good, no gold | 6/20 (30.00%) | 16/20 (80.00%) | +50.00 | [+22.33, +70.00] | 20 | true | rises |
| ConditionalQA M1 bad, no gold | 12/20 (60.00%) | 0/20 (0.00%) | -60.00 | [-80.00, -33.26] | 20 | true | falls |
| aircargo M1 good, all | 73/100 (73.00%) | 100/100 (100.00%) | +27.00 | [+18.43, +36.43] | 100 | true | rises |
| aircargo M1 bad, all | 13/100 (13.00%) | 0/100 (0.00%) | -13.00 | [-20.98, -6.58] | 100 | true | falls |
| aircargo M1 good, answer in context | 73/99 (73.74%) | 99/99 (100.00%) | +26.26 | [+17.74, +35.70] | 99 | true | rises |
| aircargo M1 bad, answer in context | 12/99 (12.12%) | 0/99 (0.00%) | -12.12 | [-20.00, -5.84] | 99 | true | falls |
| aircargo M1 good, not in context | 0/1 (0.00%) | 1/1 (100.00%) | +100.00 | [-12.21, +100.00] | 1 | false | not detected |
| aircargo M1 bad, not in context | 1/1 (100.00%) | 0/1 (0.00%) | -100.00 | [-100.00, +12.21] | 1 | false | not detected |
| aircargo M1 good, no gold | 0/0 (undefined) | 0/0 (undefined) | undefined | undefined | 0 | false | not detected |
| aircargo M1 bad, no gold | 0/0 (undefined) | 0/0 (undefined) | undefined | undefined | 0 | false | not detected |

Transitions read from the package grade to the Codex grade.

| Base | Package grade | n | Codex good | Codex partial_ok | Codex bad |
|---|---|---:|---:|---:|---:|
| WixQA | good | 30 | 28 | 1 | 1 |
| WixQA | partial_ok | 11 | 11 | 0 | 0 |
| WixQA | bad | 59 | 53 | 5 | 1 |
| ConditionalQA | good | 38 | 37 | 1 | 0 |
| ConditionalQA | partial_ok | 9 | 8 | 1 | 0 |
| ConditionalQA | bad | 53 | 47 | 6 | 0 |
| aircargo | good | 73 | 73 | 0 | 0 |
| aircargo | partial_ok | 14 | 14 | 0 | 0 |
| aircargo | bad | 13 | 13 | 0 | 0 |

## Loss accounting

The loss categories partition the package's not-good answers. Kept and lost use the package's good answers as their denominator.

| Base | Package not good / n | Generator losses | Retrieval losses | Neither | Codex good without gold in context | Package good kept | Package good lost |
|---|---:|---:|---:|---:|---:|---:|---:|
| WixQA | 70/100 | 45/70 | 3/70 | 3/70 | 19/70 | 28/30 | 2/30 |
| ConditionalQA | 62/100 | 29/62 | 6/62 | 1/62 | 26/62 | 37/38 | 1/38 |
| aircargo | 27/100 | 26/27 | 0/27 | 0/27 | 1/27 | 73/73 | 0/73 |
| Pooled | 159/300 | 100/159 | 9/159 | 4/159 | 46/159 | 138/141 | 3/141 |

## M2 beside M1

M2 measures agreement with the reference. The pooled rise is not detected. ConditionalQA's overall rise and its answer-in-context rise are detected; WixQA's are not.
aircargo has no references and no M2. The no-gold strata have no reference-agreement denominator.

| Metric | Package hits / n (share) | Codex hits / n (share) | Change, pp | read95, pp | Clusters | Detected | Direction |
|---|---:|---:|---:|---|---:|---|---|
| Pooled M2 agrees | 81/180 (45.00%) | 99/180 (55.00%) | +10.00 | [+0.00, +19.44] | 117 | false | not detected |
| WixQA M2 agrees, all | 34/100 (34.00%) | 40/100 (40.00%) | +6.00 | [-7.84, +20.23] | 77 | false | not detected |
| WixQA M2 agrees, answer in context | 25/67 (37.31%) | 31/67 (46.27%) | +8.96 | [-10.26, +26.98] | 56 | false | not detected |
| WixQA M2 agrees, not in context | 9/33 (27.27%) | 9/33 (27.27%) | +0.00 | [-18.18, +19.35] | 27 | false | not detected |
| WixQA M2 agrees, no gold | 0/0 (undefined) | 0/0 (undefined) | undefined | undefined | 0 | false | not detected |
| ConditionalQA M2 agrees, all | 47/80 (58.75%) | 59/80 (73.75%) | +15.00 | [+2.56, +26.79] | 40 | true | rises |
| ConditionalQA M2 agrees, answer in context | 36/58 (62.07%) | 47/58 (81.03%) | +18.97 | [+3.63, +33.33] | 36 | true | rises |
| ConditionalQA M2 agrees, not in context | 11/22 (50.00%) | 12/22 (54.55%) | +4.55 | [-19.06, +27.34] | 18 | false | not detected |
| ConditionalQA M2 agrees, no gold | 0/0 (undefined) | 0/0 (undefined) | undefined | undefined | 0 | false | not detected |
| ConditionalQA M1 right declines, unanswerable | 5/20 (25.00%) | 6/20 (30.00%) | +5.00 | [-18.38, +27.76] | 20 | false | not detected |

ConditionalQA's M2 right declines are 5/20 for the package and 5/20 for Codex. The M1 right-decline change above is not detected.
Training knowledge of products such as Wix may help. M1 penalizes unsupported claims; M2 agreement may not. These counts do not establish a cause for the gap between the rises.
Both instruments' diagnostics follow. Each diagnostic covers all answers in its key, including those without a reference. Unlisted defect categories have zero counts.

| Base / instrument | Side | n | Supported / total claims (share) | Unsupported-claim answers / n | Unsupported claims | Defects (answers) |
|---|---|---:|---:|---:|---:|---|
| WixQA / M1 | package | 100 | 453/512 (88.48%) | 43/100 | 59 | none 100 |
| WixQA / M1 | codex | 100 | 611/612 (99.84%) | 1/100 | 1 | none 100 |
| WixQA / M2 | package | 100 | 469/524 (89.50%) | 41/100 | 55 | none 99; other 1 |
| WixQA / M2 | codex | 100 | 602/603 (99.83%) | 1/100 | 1 | none 100 |
| ConditionalQA / M1 | package | 100 | 314/384 (81.77%) | 47/100 | 70 | none 94; other 4; repetition 2 |
| ConditionalQA / M1 | codex | 100 | 547/547 (100.00%) | 0/100 | 0 | none 100 |
| ConditionalQA / M2 | package | 100 | 324/390 (83.08%) | 43/100 | 66 | none 95; other 4; repetition 1 |
| ConditionalQA / M2 | codex | 100 | 536/540 (99.26%) | 1/100 | 4 | none 100 |
| aircargo / M1 | package | 100 | 468/482 (97.10%) | 10/100 | 14 | copied_context 2; none 97; other 1 |
| aircargo / M1 | codex | 100 | 561/561 (100.00%) | 0/100 | 0 | none 100 |

## Retests and bridges

The laptop judge used `claude-opus-5-5`, effort `max`, tools `none`, on the frozen stage 5 isolated route.
A bridge re-grades kept package answers to check judge drift. It does not add another judge. Retests repeat the grades of the current answers.

| Plan | New requests | Pairs / planned | Agree / n | Quadratic kappa | Two steps apart / n | Passed |
|---|---:|---:|---:|---:|---:|---|
| WixQA M1 | 115 | 15/15 | 15/15 | 1.0000 | 0/15 | true |
| WixQA bridge | 15 | 15/15 | 13/15 | 0.9231 | 0/15 | true |
| WixQA M2 | 115 | 15/15 | 15/15 | 1.0000 | 0/15 | true |
| ConditionalQA M1 | 115 | 15/15 | 15/15 | 1.0000 | 0/15 | true |
| ConditionalQA bridge | 15 | 15/15 | 15/15 | 1.0000 | 0/15 | true |
| ConditionalQA M2 | 115 | 15/15 | 13/15 | 0.5946 | 0/15 | true |
| aircargo M1 | 115 | 15/15 | 15/15 | undefined | 0/15 | true |
| aircargo bridge | 15 | 15/15 | 15/15 | 1.0000 | 0/15 | true |

All 8 plans count: 620 new requests. Each metric has 100 originals plus 15 retests; each bridge has 15 kept grades plus 15 new grades.
ConditionalQA M2 passes by agreement; aircargo M1 has undefined kappa and passes by agreement. No plan stopped.
Operator history: aircargo grading paused after `31f29af` and resumed from kept verdicts. One `unavailable` reply was retried after its persisted `retry_at`.

## The arm

attempt-02 passed the data-free probe. The pilot accepted 20/20, with task p90 30.7 s. The resulting task forecast was 60 s and task stop 180 s.

| Attempts | Redos | Counted out / n | Infrastructure failures | Language mismatches / n | Raw-output mismatches | Stops | Pilot passed |
|---:|---:|---:|---:|---:|---:|---:|---|
| 300 | 0 | 0/300 | 0 | 2/300 | 0 | 0 | true |

| Tasks, n | Median, s | p90, s | Input tokens | Cached input tokens | Output tokens | Reasoning output tokens |
|---:|---:|---:|---:|---:|---:|---:|
| 300 | 25.829 | 34.703 | 5,434,591 | 2,814,208 | 125,074 | 85,302 |

AGENTS SHA-256: `89e340ed2c29d4c6e2834fe1b4d4caabc32f0e2af02c5dcff96b1821ecfab546`.
The 2 language mismatches were aircargo questions in Russian with Latin product terms (operator observation). They were kept and graded. The spec stops the arm at more than five among 300.
Raw-output mismatches are reported separately; they are not a route gate. The ChatGPT plan has no per-request price. Codex time and tokens are not product latency or cost.

attempt-01 was the data-free probe. It stopped with code 5 (`cleanup_failure`): TerminateProcess returned error 5 on a codex.exe exiting by itself (operator report).
Amendment `f93508a`, before the first corpus request, counted a signalled process handle as exited by itself and refreshed registration hashes. attempt-01's four arm files remain its record.

## Provenance and limits

Spec SHA-256: `95adbbe1bd391b14a7ac6d771d7ec3df7b6f90133e0045877d20d6b7b9d99ebe`. Registration: `54a46e2`; amendment: `f93508a`.
Plans were frozen and committed before each key's first grade: `e900f87` (WixQA), `adb35a7` (ConditionalQA), `3bb48dc` (aircargo).
Receipt `31f29af` holds the arm summaries and WixQA/ConditionalQA exports. Receipt `e166109` adds aircargo's exports and the reading.
Package stands: `2057ad0` for WixQA and ConditionalQA; `138f3b3` for aircargo (item 6).
The operator reports that the laptop reader ran in the focused venv with Python 3.11.13 and exited 0.
The [artifact test](../../tests/test_generator_ceiling_record_artifact.py) pins every public file's SHA-256 and LF bytes, checks registered tool/wrapper hashes and public provenance, and rebuilds the reading.
Its docstring names the private checks it cannot repeat. Public case ids stay in the full repository; raw prompts, answers and verdict journals stay private.

These reused questions are in-sample. There is one unseeded generation per side and one judge. No person graded anything (owner's decision D11).
Judge and arm are different vendors, but the judge's family is the orchestrator's (D12).
aircargo's stratum is a judge flag; the external strata are gold labels.
The spec's approximate detectable difference is `2.8 * sqrt(d / 224)`, where d is the discordant fraction: about 5.9, 8.4 and 10.2 percentage points at d = 0.1, 0.2 and 0.3. Clustering can widen the interval.
"Not detected" does not mean "no difference".
