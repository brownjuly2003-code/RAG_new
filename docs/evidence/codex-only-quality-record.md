# Stage 6 item 0: codex-only quality record

The registered outcome is row 3: **holds (no detected fall)**.
Publish these numbers as product quality under codex-only.
The [registered spec](../specs/codex-only-quality.md) reads falls in Q or R. A detected rise in Q decides nothing beyond no fall.

| Metric | Baseline hits / n (share) | Product hits / n (share) | Change, pp | Newcombe95, pp | Cluster95, pp | read95, pp | Clusters | Detected | Direction |
|---|---:|---:|---:|---|---|---|---:|---|---|
| Pooled Q | 268/300 (89.33%) | 279/300 (93.00%) | +3.67 | [+0.08, +7.44] | [+0.34, +7.06] | [+0.08, +7.44] | 237 | true | rises |
| Pooled R | 125/180 (69.44%) | 116/180 (64.44%) | -5.00 | [-12.42, +2.50] | [-12.57, +2.59] | [-12.57, +2.59] | 117 | false | not detected |

R's fall of 5.00 percentage points is not detected.
R hit transitions, n = 180: both hit 97, lost 28, gained 19, neither hit 36.

## What was compared

The product path itself answered the same 300 questions, with the same ids and order, on the owner's laptop under `codex-only`.
Every model call used Codex, profile `cw`, `gpt-6-astra`. Its own retrieval used query transformation and batched document grading at `low`; the answer used `xhigh` in stage 5v's wrapper.
The baseline is stage 5v's Codex arm: the same model at xhigh answered the package's saved contexts, selected on the Mac by the 4B.
One unseeded generation per side, in-sample, one judge.
Q is primary: M1 good and context_has_answer true, over all 300 questions. R is gold in the sent context, without a judge, over 180 gold-bearing WixQA and ConditionalQA questions.
Differences are product minus baseline. read95 is the envelope of paired Newcombe method-10 and cluster-bootstrap intervals.
Intervals are 95%, with 10,000 bootstrap resamples and seed 20261001. A fall requires both upper endpoints below zero.
External clusters use frozen stage 5v labels; aircargo uses singleton cases. No denominator shrinks for failures.

## Per key

| Metric | Baseline hits / n (share) | Product hits / n (share) | Change, pp | Newcombe95, pp | Cluster95, pp | read95, pp | Clusters | Detected | Direction |
|---|---:|---:|---:|---|---|---|---:|---|---|
| WixQA Q | 87/100 (87.00%) | 89/100 (89.00%) | +2.00 | [-4.87, +9.05] | [-4.08, +8.25] | [-4.87, +9.05] | 77 | false | not detected |
| ConditionalQA Q | 81/100 (81.00%) | 92/100 (92.00%) | +11.00 | [+2.90, +19.55] | [+3.96, +18.28] | [+2.90, +19.55] | 60 | true | rises |
| aircargo Q | 100/100 (100.00%) | 98/100 (98.00%) | -2.00 | [-7.00, +1.97] | [-5.00, +0.00] | [-7.00, +1.97] | 100 | false | not detected |
| WixQA R | 67/100 (67.00%) | 60/100 (60.00%) | -7.00 | [-17.02, +3.25] | [-18.10, +3.57] | [-18.10, +3.57] | 77 | false | not detected |
| ConditionalQA R | 58/80 (72.50%) | 56/80 (70.00%) | -2.50 | [-13.59, +8.66] | [-13.75, +8.75] | [-13.75, +8.75] | 40 | false | not detected |

## Printed, deciding nothing

M1 good includes supported declines. Counts below are good / partial_ok / bad. Routes are accepted answers; other routes are shown separately below.
The acceptance share belongs to the owner (PLAN stage 6). Bad per auto uses all auto answers as its denominator.

| Key | n | Baseline M1 | Product M1 | Baseline auto / human | Product auto / human | Product bad / auto (share) | Tickets |
|---|---:|---|---|---|---|---|---:|
| WixQA | 100 | 92 / 6 / 2 | 96 / 3 / 1 | 86 / 14 | 96 / 4 | 0/96 (0.00%) | 0 |
| ConditionalQA | 100 | 92 / 8 / 0 | 97 / 3 / 0 | 85 / 15 | 93 / 7 | 0/93 (0.00%) | 0 |
| aircargo | 100 | 100 / 0 / 0 | 98 / 0 / 2 | 98 / 2 | 96 / 4 | 2/96 (2.08%) | 0 |
| Pooled | 300 | 284 / 14 / 2 | 291 / 6 / 3 | 269 / 31 | 285 / 15 | 2/285 (0.70%) | 0 |

Latency is dispatch to product result on her laptop under her load. It differs from stage 5v's task time. Both percentiles use nearest rank.

| Key | With cold, n | Median / p90, s | Without cold, n | Median / p90, s | Over 180 s / accepted n |
|---|---:|---|---:|---|---|
| WixQA | 100 | 60.797 / 71.796 | 86 | 59.766 / 68.641 | 0/100 |
| ConditionalQA | 100 | 70.844 / 83.469 | 85 | 71.344 / 83.734 | 0/100 |
| aircargo | 100 | 69.469 / 88.078 | 83 | 69.125 / 88.078 | 0/100 |
| Pooled | 300 | 66.016 / 83.281 | 254 | 65.703 / 83.281 | 0/300 |

| Key | Questions, n | Infrastructure attempts | Pending | Product failures | Counted out | Language mismatches / n |
|---|---:|---:|---:|---:|---:|---|
| WixQA | 100 | 0 | 0 | 0 | 0 | 0/100 |
| ConditionalQA | 100 | 0 | 0 | 0 | 0 | 0/100 |
| aircargo | 100 | 1 | 0 | 0 | 0 | 3/100 |
| Pooled | 300 | 1 | 0 | 0 | 0 | 3/300 |

Language mismatch is a script-count heuristic, not a human language grade.

| Key | Questions, n | Low calls | Low / question | Xhigh calls | Xhigh / question |
|---|---:|---:|---:|---:|---:|
| WixQA | 100 | 200 | 2.0000 | 100 | 1.0000 |
| ConditionalQA | 100 | 200 | 2.0000 | 100 | 1.0000 |
| aircargo | 100 | 201 | 2.0100 | 100 | 1.0000 |
| Pooled | 300 | 601 | 2.0033 | 300 | 1.0000 |

Aircargo document identity: 50/100 equal source-id sets against the saved package prompts. This is document identity, not passage equality or gold coverage.
Ollama observations: 2, in 1 chunk refused with code 1 `ollama_observed` before its request; it changed nothing.
The operator traced this to Ollama's own updater. It was gone at the check; no answer ran beside Ollama.

## Retests, bridges and execution

The laptop judge was `claude-opus-5-5` through Claude Code CLI `2.1.312`, effort `max`, tools `none`, on the frozen safe-mode route.
Safe mode has no instruction file, memory, hook, skill, plugin or MCP server; no tools; an empty working directory; nothing stored; one turn.
A bridge compares the judge now with the judge then on the same kept stage 5v Codex answers. It checks judge drift. Retests grade current answers again.

| Plan | New requests | Pairs / planned | Agree / pairs | Quadratic kappa | Two steps apart / pairs | Passed |
|---|---:|---|---|---|---|---|
| WixQA M1 | 115 | 15/15 | 15/15 | 1.0000 | 0/15 | true |
| WixQA bridge | 15 | 15/15 | 15/15 | 1.0000 | 0/15 | true |
| ConditionalQA M1 | 115 | 15/15 | 15/15 | undefined | 0/15 | true |
| ConditionalQA bridge | 15 | 15/15 | 15/15 | 1.0000 | 0/15 | true |
| aircargo M1 | 115 | 15/15 | 15/15 | 1.0000 | 0/15 | true |
| aircargo bridge | 15 | 15/15 | 15/15 | undefined | 0/15 | true |

All 6 plans and bridges count: 390 new requests; missing 0. Each M1 has 100 originals and 15 retests; each bridge has 15 kept grades and 15 new grades.
ConditionalQA M1 and aircargo bridge have undefined kappa and pass by agreement. M2 is absent by spec.
The M1 exports report 345 valid replies among 346 logged replies. Their replies.cost_usd sum is $14.9158 + $13.8187 + $14.1262 = $42.8607 (WixQA, ConditionalQA, aircargo). This is the M1 export cost, not total bridge or product cost.
WixQA M1 had 1 unavailable reply. The operator reports `cli_exit` and a retry after persisted `retry_at`.
The arm made 301 question attempts for 300 accepted answers. The probe passed in 19.9 s; the pilot passed 20/20, all auto.
Aircargo's 1 infrastructure attempt lasted 442 s. It accounts for the arm's extra other route and its over-180 attempt; accepted answers have 0/100 over 180 s.
There are 2 series-wide stops, both resolved: code 5 `verified_stop_failed`; code 5 `state_stop`.
The operator diagnosed a Windows Update stall, resumed with `--resume-infrastructure`, and asked the pending question again; it was accepted. Stops, resumes and chunks repeat in every arm file and must not be added across keys.
Judging used foreground `--budget 600` chunks; each first re-hashed the copy for offline admission. The route receipt came from a one-shot probe in WixQA's first grade chunk.
Operator actions, all reverted after the reading: Claude Code updates held with `DISABLE_AUTOUPDATER`; seven temporary Microsoft Defender exclusions for the release venv, model caches and private roots; High QoS (EcoQoS opt-out), ABOVE_NORMAL priority and P-core affinity for the grade driver; AC power overlay at best performance.
The laptop's firmware caps its E-cores. These environment changes changed no series data or rule.

## Retired series

The Series table of the [measurement handoff](../operations/session-handoff-2026-11-05-codex-only-measurement.md) records the history below. Each retirement required a new registration; no answer carried over. The artifact test pins every retained public file.

attempt-01 (`6f272f2`, `5b7e71f`): code 5 twice, then retired. The watch raced with the owner's other session's short-lived pythons.

attempt-02 (`9530861`): code 2 before any request. The shared capture root still held attempt-01's call records.

attempt-03 (`616798d`): pilot 20/20 (`b366a0c`), WixQA frozen (`53a701a`), then code 2 `outside_codex`. The owner's second Claude session started Codex.

attempt-04 (`e31c8c3`): pilot 20/20 (`215d96a`), then closed by the orchestrator without a stop. Full-tree chunk admission took 691 s; a stat cache followed.

attempt-05 (`97062cd`): pilot (`11c99b5`) and WixQA frozen (`42e559e`), then code 2 on ConditionalQA. The drain's check time became a killed call's end, falsely implying overlap; instrument fix `6d4e32f` left the overlap rule unchanged.

## Provenance and limits

Spec SHA-256: `0fe4275734b2a87da2ccef5bcc284ba0cbfe4b6eb0f52a17a071a9209c1adebc`; amendment 2026-11-05. Registration `5a2d2fe` preceded requests; release `19ecbbb7489f83121dbc3c817ee948a6115bed7d` (`19ecbbb`).
Registration config_sha256: `eb700c2d78f6f986d852b59d4d42b67e3701022109db3209b87a6360447e3dfe`. copy_receipt_sha256: `6d2798fdaa4e2d75d23246f094f836917eab34a0247c348a3e45bd5abb6c6332`.
Probe and pilot: `2f07562`. Frozen receipts: `32ff420` (WixQA), `86a6ab4` (ConditionalQA), `4bf203a` (aircargo). Judge route: `e2845c9`.
Exports: `557c2d0` (WixQA), `cd1223d` (ConditionalQA), `8c0014e` (aircargo). Reading: `090dcd1`.
The operator reports the laptop reader used Python 3.11.13 in the release venv, exited 0 in 337 s, and wrote stdout identical to reading.json.
The [reading](../../reports/codex-only-quality/attempt-06/reading.json) holds the result. The [artifact test](../../tests/test_codex_only_quality_record_artifact.py) pins public SHA-256 and LF bytes, registered codex-only tool/spec hashes, receipts and public provenance, and reads Q/R again.
The test docstring names the private checks it cannot repeat. Current product files outside the registered codex-only tools and spec may change in later slices. Public record ids stay in the full repository; raw questions, answers and journals stay private.

In-sample; one unseeded generation per side; one judge; no human grades (D11).
Contexts, release, Windows numerics and exec framing change together; no isolated auxiliary causal effect.
M2 absent; laptop under owner load; no detected fall does not establish equivalence.
The one judge was `claude-opus-5-5`. Overall M1 can reward a supported decline, so Q and R expose different losses.
