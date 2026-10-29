# Stage 4, step 2b: the continuation read cold, on step 2's 25 answers and on stage 3's 80 labelled ones — 2026-10-29

The question: does the continuation, scoring the same 80 labelled answers, lose any of what the
classic catches? [Step 2](stage4-step2-record.md) found the continuation faster than the classic
on 13 of 13 unlabelled answers and routing them alike; a badge that is faster but blind to a bad
answer is a loss step 2 could not see. Stage 3's 80 aircargo answers of V4, 17 targets (graded
bad, or declined) and 63 goods, carry the judge's grades, and the classic's saved score flagged 2
of the 17 and 0 of the 63 ([the handover signals' record](handover-signal-v4-aircargo.md), S1).
They are saved answers, so the continuation scored them cold: the whole chat read afresh. The
bridge first asked whether a cold route is the warm one, on step 2's 25 answers. Both phases ran
on stand `57420db` and were read by
[`stage4-step2b-continuation-labels.md`](../specs/stage4-step2b-continuation-labels.md). The spec
was registered with its tools and their test
in `1e0600a` before the first request; Amendment 1, after the check stopped and before the first request, in `45f7e51`.
The bridge ran from 19:03 and the 80 from 19:43 UTC on 2026-10-29.

Record: [`reports/stage4-step2b/57420db/`](../../reports/stage4-step2b/57420db/):
- `step2b.json`, both phases: their launches, lines and gates, the pairs and the readings;
- `step2b.first.json`, the bridge's first answer's read, taken before the bridge's rest ran;
- `step2b.bridge.json`, the bridge's read, taken before the 80 ran;
- `environment.jsonl`, the lines before the bridge, between the phases and after the 80.

Every number below is `step2b.json`'s: its `readings`, its `pairs` (one of the 80 and its line),
its `bridge_pairs` (one of the 25, step 2's warm score beside its cold line) and its phases'
launches.

The reader is
[`reports/stage4-step2b/tools/step2b_reader.py`](../../reports/stage4-step2b/tools/step2b_reader.py),
the replay [`step2b_replay.py`](../../reports/stage4-step2b/tools/step2b_replay.py) beside it.
Checked by [`tests/test_stage4_step2b_artifact.py`](../../tests/test_stage4_step2b_artifact.py):
- the files are the bytes copied from the Mac, by SHA-256, read by the reader and the replay the
  spec lists;
- the pairs, the readings and the first answer are read again from the lines with the committed
  reader;
- both phases passed their gates on every point, and every answer was read;
- the first answer's read and the bridge's were taken while the replay went on;
- the stand, the settings and the inputs are the spec's: step 2's records and the 80's plan and
  labels as committed, by SHA-256;
- the environment lines bracket each phase on V4's Ollama server;
- the files hold numbers, times, ids, enums, the reader's fixed reasons, the paths the spec names,
  versions and SHA-256 strings only;
- every table row below is built from the record, and so is each number of the prose that the
  test pins; the forecasts are the spec's words.

The record holds no question, answer, prompt, document, reply, log line, command line or process environment.

## Provenance and method

- **The stand:** step 2's, `S=/Users/julia/RAG_new_chat_57420db`, code
  `57420db746e0510465bb5a08b7610e092b32e650`: the continuation as step 2 ran it, its instruction
  `SELF_EVAL_CONTINUATION_V1`. The model `qwen3:4b-instruct-2507-q4_K_M`, digest
  `0edcdef34593…`, on the CPU; the window 4,096 tokens and the chat's input limit 3,443;
  temperature 0.0 and 128 tokens, the evaluate role's; the stream path `provider`; the answer stop
  255 s.
- **The continuation, as the chat sends it** (`step2b_replay.py`): the answer's first turn, the
  answer as it streamed, unstripped, and the instruction, through the chat's own helpers; one
  `/api/chat` call to the stream model's provider, the strict parse and the entry. The bridge's
  first turn is its run's saved stream prompt; the 80's is rebuilt by V5's replay, byte for byte
  the saved one. The tools' test holds the request to the live function's on both stream paths.
- **Cold:** every continuation was read from its start, as for a saved answer; the chat's warm one
  reads its instruction and the turn markers after the answer's tokens in its slot.
- **The interpreter and the environment:** V5's, `/Users/julia/RAG_Support_Assistant/.venv/bin/python`
  with `/Users/julia/RAG_new_mf_gate_site`. By Amendment 1, each replay named V4's provider
  registry by the path V4's settings give it, under V4's stand, a file byte-identical to this
  stand's; every other setting V5's check reads was V4's.
- **The bridge's 25:** step 2's read asks, 12 of `s2-both` and 13 of `s2-both-r2`, each run's in
  its order, from step 2's records as committed.
- **The 80:** V4's runs `v4-aircargo-b01` … `v4-aircargo-b10` of stand `4f48fed`, as stage 3's
  classes: the 17 targets first, then the 63 goods, each class in the plan's order; the plan and
  the labels as committed. The 20 partial answers were not asked.
- **The reloads:** before answers n = 6, 11, …, 76 of the 80 the model was unloaded until Ollama
  held none and `ps` listed no llama-server, then loaded again, so the host prompt cache never
  held more than five answers' states. Julia's configuration was not touched.
- **The segments:** the bridge in two, its first answer read alone before the rest; the 80 in one.
  Each started on an idle Mac by the replay's own check, no model in Ollama and no llama-server.
- **The environment:** three lines, taken at 19:00:02, 19:33:49 and 21:18:45, before the bridge,
  between the phases and after the 80; each names Ollama 0.33.2 and one server, its start and
  binary unchanged.

## The reading

| Reading, the spec's rule | Read | Measured | Forecast |
|---|---|---|---|
| The bridge: at least 10 of the 25 readable and the cold route the warm one on all but at most 1 | **held** | 25 readable, the cold route another on 0 | held |
| Scores: at most 6 of the 80 without a score | **held** | 0 of 80 without a score | held |
| Catches: at least the classic's 2 of the 17 targets flagged by the effective score | **not held** | 0 of 17; the classic's 2, n = 2 and 6 | the least certain of the three |
| Over-marks: at most one of the 63 goods more than the classic's 0 flagged | **held** | 0 of 63; the classic's 0 | held |
| The signal: held when the bridge and the three hold, not held when any is not held | **not held** | on the catches | not held, on the catches, with low confidence |

An answer is flagged when its score is under 80, the stream's route to a person. Its effective
score is the continuation's where it scored 1–100, else the classic's saved one; every one of the
80 scored, so the effective score is the continuation's on all of them.

## The 17 targets

The answers the judge graded bad, or that declined, in the plan's order. The seconds are the
continuation's, and its prompt as Ollama counted it: the tokens and the seconds spent reading them.

| n | Question | Run | Scores, the classic / the continuation | Flagged, the classic / the continuation | Seconds | The prompt, tokens / s |
|---|---|---|---|---|---|---|
| 1 | `aircargo-probation-data` | `v4-aircargo-b01` | 100 / 100 | no / no | 81.943 | 2,613 / 81.016 |
| 2 | `aircargo-probation-extend` | `v4-aircargo-b01` | 60 / 90 | yes / no | 80.805 | 2,852 / 79.989 |
| 3 | `aircargo-secret-check` | `v4-aircargo-b02` | 100 / 100 | no / no | 75.906 | 2,642 / 72.549 |
| 4 | `aircargo-contract-termination-open-awb` | `v4-aircargo-b04` | 100 / 100 | no / no | 82.936 | 2,632 / 79.573 |
| 5 | `aircargo-contract-termination-fields` | `v4-aircargo-b05` | 100 / 100 | no / no | 74.737 | 2,880 / 73.352 |
| 6 | `aircargo-road-contract-aircargo-fields` | `v4-aircargo-b05` | 40 / 100 | yes / no | 77.223 | 2,888 / 76.367 |
| 7 | `aircargo-dangerous-goods-clearance` | `v4-aircargo-b05` | 95 / 100 | no / no | 71.897 | 2,799 / 70.769 |
| 8 | `aircargo-waybill-first-mile-fields` | `v4-aircargo-b05` | 100 / 100 | no / no | 74.362 | 2,884 / 73.231 |
| 9 | `aircargo-sick-leave-required-fields` | `v4-aircargo-b06` | 100 / 100 | no / no | 67.402 | 2,661 / 66.319 |
| 10 | `aircargo-driver-hours-required-fields` | `v4-aircargo-b07` | 100 / 100 | no / no | 75.238 | 2,740 / 74.162 |
| 11 | `aircargo-oversized-permit-route` | `v4-aircargo-b08` | 100 / 100 | no / no | 91.007 | 3,117 / 90.089 |
| 12 | `aircargo-oversized-manual-check` | `v4-aircargo-b08` | 100 / 100 | no / no | 71.780 | 2,759 / 70.637 |
| 13 | `aircargo-customs-broker-evidence` | `v4-aircargo-b08` | 100 / 100 | no / no | 64.392 | 2,561 / 63.275 |
| 14 | `aircargo-cargo-insurance-evidence` | `v4-aircargo-b09` | 100 / 100 | no / no | 75.333 | 2,865 / 74.229 |
| 15 | `aircargo-gps-monitoring-required-fields` | `v4-aircargo-b10` | 100 / 100 | no / no | 78.381 | 2,971 / 76.780 |
| 16 | `aircargo-weight-control-required-fields` | `v4-aircargo-b10` | 100 / 100 | no / no | 75.804 | 2,841 / 74.943 |
| 17 | `aircargo-cross-border-special-cargo` | `v4-aircargo-b10` | 100 / 100 | no / no | 66.283 | 2,639 / 65.164 |

## Scores by class

| Class | Side | Scores | A median | Flagged under 80 | Flagged under 100 |
|---|---|---|---|---|---|
| targets, 17 | the classic, saved | 100 × 14, 95 × 1, 60 × 1, 40 × 1 | 100 | 2 | 3 |
| targets, 17 | the continuation, cold | 100 × 16, 90 × 1 | 100 | 0 | 1 |
| goods, 63 | the classic, saved | 100 × 59, 95 × 4 | 100 | 0 | 4 |
| goods, 63 | the continuation, cold | 100 × 61, 95 × 1, 90 × 1 | 100 | 0 | 2 |

## The paired flags

The exact McNemar test of the flags under 80, the classic's against the effective score's, answer
by answer; printed beside the rules, deciding nothing.

| Flagged under 80 | Both | The classic alone | The continuation alone | Exact McNemar p | Found |
|---|---|---|---|---|---|
| Catches, of the 17 targets | 0 | 2 | 0 | 0.5 | no difference |
| Over-marks, of the 63 goods | 0 | 0 | 0 | 1.0 | no difference |

## Printed, deciding nothing

The spec's list for the 80:

| Printed | The 80 |
|---|---|
| Flagged under 100, S1′'s cut: catches, the classic / the effective score | 3 / 1 |
| Flagged under 100: over-marks, the classic / the effective score | 4 / 2 |
| The continuation's own flags where it scored: targets; goods | 0 of 17; 0 of 63 |
| Wilson's 95 % interval of the share of targets caught: the classic; the effective score | 0.0329–0.3434; 0.0000–0.1843 |
| Wilson's 95 % interval of the share of goods over-marked: the classic; the effective score | 0.0000–0.0575; 0.0000–0.0575 |
| The continuation scored higher / the same / lower than the classic, the median difference | 5 / 74 / 1, 0.0 |
| Seconds an answer: a median, the longest, summed | 68.165, 91.007, 5,560.141 |
| Counters, medians: prompt tokens, prompt s, generated tokens, generated s | 2,656, 67.181, 4, 0.752 |
| The chat's estimate of the input, tokens: a median, at most | 2,955.5, 3,363 |
| Done reasons | stop 80 |
| The replies by their length in characters | 3: 77, 2: 3 |
| Reloads, before answers n = 6, 11, …, 76 | 15 |
| A reload's load, s: a median, at most | 5.632, 7.140 |
| A reload's unload, s: a median, at most | 0.248, 0.312 |

## The bridge

Step 2's 25 read answers: the continuation's warm score and seconds, as step 2's records keep them,
beside this replay's cold line on the same answer. A route is `auto` at a score of 80 or more,
else `human`; the last column is the cold request as Ollama counted it.

| n | Run | Question | Warm, s | Cold, s | Scores, warm / cold | Routes, warm / cold | The cold prompt, tokens / s |
|---|---|---|---|---|---|---|---|
| 1 | `s2-both` | `aircargo-probation-data` | 9.035 | 74.294 | 100 / 100 | auto / auto | 2,660 / 69.773 |
| 2 | `s2-both` | `aircargo-probation-extend` | 10.622 | 76.226 | 95 / 90 | auto / auto | 2,833 / 75.140 |
| 3 | `s2-both` | `aircargo-probation-dismissal` | 14.000 | 67.153 | 100 / 100 | auto / auto | 2,674 / 66.046 |
| 4 | `s2-both` | `aircargo-dismissal-check` | 10.170 | 71.287 | 100 / 100 | auto / auto | 2,721 / 70.207 |
| 5 | `s2-both` | `aircargo-dismissal-lawyer` | 15.284 | 63.994 | 100 / 100 | auto / auto | 2,593 / 62.920 |
| 6 | `s2-both` | `aircargo-dismissal-order` | 9.254 | 71.388 | 100 / 100 | auto / auto | 2,692 / 70.556 |
| 7 | `s2-both` | `aircargo-leave-sources` | 8.962 | 65.640 | 100 / 100 | auto / auto | 2,590 / 64.584 |
| 8 | `s2-both` | `aircargo-leave-compensation` | 8.847 | 63.509 | 100 / 100 | auto / auto | 2,570 / 62.459 |
| 9 | `s2-both` | `aircargo-leave-risk` | 8.869 | 61.602 | 100 / 100 | auto / auto | 2,493 / 60.588 |
| 10 | `s2-both` | `aircargo-matliab-check` | 10.017 | 65.212 | 100 / 100 | auto / auto | 2,543 / 63.813 |
| 11 | `s2-both` | `aircargo-matliab-disputed` | 11.332 | 68.722 | 100 / 100 | auto / auto | 2,570 / 67.924 |
| 12 | `s2-both` | `aircargo-templates-choose` | 11.988 | 63.364 | 100 / 100 | auto / auto | 2,505 / 62.352 |
| 13 | `s2-both-r2` | `aircargo-probation-data` | 8.483 | 65.159 | 100 / 100 | auto / auto | 2,558 / 64.125 |
| 14 | `s2-both-r2` | `aircargo-probation-extend` | 8.570 | 73.993 | 90 / 90 | auto / auto | 2,832 / 73.139 |
| 15 | `s2-both-r2` | `aircargo-probation-dismissal` | 8.635 | 71.524 | 100 / 100 | auto / auto | 2,677 / 68.863 |
| 16 | `s2-both-r2` | `aircargo-dismissal-check` | 12.789 | 72.653 | 100 / 100 | auto / auto | 2,718 / 71.700 |
| 17 | `s2-both-r2` | `aircargo-dismissal-lawyer` | 13.853 | 64.807 | 100 / 100 | auto / auto | 2,593 / 63.749 |
| 18 | `s2-both-r2` | `aircargo-dismissal-order` | 8.782 | 67.178 | 100 / 100 | auto / auto | 2,671 / 66.125 |
| 19 | `s2-both-r2` | `aircargo-leave-sources` | 8.764 | 66.629 | 100 / 100 | auto / auto | 2,590 / 65.572 |
| 20 | `s2-both-r2` | `aircargo-leave-compensation` | 8.997 | 64.514 | 100 / 100 | auto / auto | 2,570 / 63.469 |
| 21 | `s2-both-r2` | `aircargo-leave-risk` | 8.527 | 64.807 | 100 / 100 | auto / auto | 2,493 / 64.039 |
| 22 | `s2-both-r2` | `aircargo-matliab-check` | 8.429 | 63.361 | 100 / 100 | auto / auto | 2,492 / 62.323 |
| 23 | `s2-both-r2` | `aircargo-matliab-disputed` | 8.526 | 64.932 | 100 / 100 | auto / auto | 2,570 / 63.900 |
| 24 | `s2-both-r2` | `aircargo-templates-choose` | 8.449 | 63.932 | 100 / 100 | auto / auto | 2,505 / 62.928 |
| 25 | `s2-both-r2` | `aircargo-templates-checklist` | 8.682 | 66.572 | 100 / 100 | auto / auto | 2,611 / 65.534 |

| Printed, deciding nothing | The bridge |
|---|---|
| Equal scores, warm and cold | 24 of 25 |
| Routes, warm → cold | auto → auto 25 |
| Cold minus warm: higher / the same / lower, the median | 0 / 24 / 1, 0 |
| Outcomes, cold | scored 25 |
| Answers by run | `s2-both` 12, `s2-both-r2` 13 |
| Scores, warm | 100 × 23, 95 × 1, 90 × 1 |
| Scores, cold | 100 × 23, 90 × 2 |
| Seconds, a median, warm / cold | 8.962 / 65.640 |
| Warm counters, medians: prompt tokens, prompt s, generated tokens, generated s | 2,590, 7.906, 4, 0.758 |
| Cold counters, medians: prompt tokens, prompt s, generated tokens, generated s | 2,590, 64.584, 4, 0.740 |

## The segments

| Phase | Segment | UTC | Status | From n | The model's load, s | The final unload: s, polls |
|---|---|---|---|---|---|---|
| the bridge | 1 | 19:03:24–19:04:53 | first | 1 | 14.428 | 0.314, 1 |
| the bridge | 2 | 19:06:09–19:33:27 | complete | 2 | 5.953 | 0.264, 1 |
| the 80 | 1 | 19:43:41–21:17:58 | complete | 1 | 6.130 | 0.245, 1 |

## Forecast and outcome

| Forecast, written before the first request | Measured |
|---|---|
| the bridge **held**: a cold continuation reads the same tokens the warm one held in its slot, and the 25 warm scores, 90–100, are far from 80 | **held**: the cold route the warm one on 25 of 25; 24 equal scores, one lower (95 → 90) |
| Scores held: warm, the continuation scored every one of the 25. | **held**: the continuation scored all 80, and all 25 of the bridge |
| Over-marks held: it scored none of them under 90. | **held**: 0 of 63 goods flagged; none of the 80 scored under 90 |
| Catches are the least certain of the three: two catches of 17 leave no room for a lost one | **not held**: 0 of 17 flagged, the classic's 2 |
| The forecast signal: **not held**, on the catches, with low confidence. | **not held**, on the catches |
| a cold continuation reads ≈ 2,370–3,130 tokens (median ≈ 2,665): 64–85 s an answer at ≈ 28 ms a token, 92–124 s at 41 ms | a median 2,656 tokens read in 67.181 s, 25.3 ms a token, at most 3,117; 60.721–91.007 s an answer |
| the bridge: its 25 answers ≈ 31 min, its two loads and four reloads ≈ 5 min — ≈ 40 min, ≈ 50 min at the slower pace | 30 min from the bridge's launch to its end, its two segments 28.8 min |
| the 80: ≈ 1 h 36 min, ≈ 2 h 19 min at the slower pace, its load and fifteen reloads ≈ 12 min at step 2's loads of 31–55 s — ≈ 1 h 48 min, ≈ 2 h 31 min at the slower pace | 1 h 34 min in one segment, its load 6.130 s and fifteen reloads a median 5.632 s |
| ≈ 2 h 45 min in all, ≈ 3 h 35 min at the slower pace | 2 h 19 min from the first environment line to the third |

The reloads took a few seconds where the forecast took step 2's loads of 31–55 s, so the 80 ran
under their forecast; the last row's span holds the amendment, the idle waits and both phases.

## What it says

- **The bridge held:** on all 25 the cold route was the warm one, `auto`, with
  24 equal scores and one lower, `aircargo-probation-extend` of `s2-both`, 95 → 90.
  A cold route stands for the warm one here. The cold read took
  a median 65.640 s cold against 8.962 s warm
  on the same median 2,590 prompt tokens.
- **The continuation flagged none of the 17 bad answers; the classic flagged two:**
  `aircargo-probation-extend` and `aircargo-road-contract-aircargo-fields`,
  n = 2 and 6, which
  the classic scored 60 and 40, the continuation 90 and 100.
- **It scored every one of the 80 at 90 or more:**
  on the 17 targets 100 × 16, 90 × 1; on the 63 goods 100 × 61, 95 × 1, 90 × 1.
  Beside it,
  the classic's targets 100 × 14, 95 × 1, 60 × 1, 40 × 1; its goods 100 × 59, 95 × 4.
  Against the classic, answer by answer, the continuation scored
  higher on 5, lower on 1 and the same on 74.
  Fast in the chat and, on these labels, blind.
- **The signal is not held, on the catches,** as the spec forecast it.
  **The default stays `classic`**, by the spec's «What follows»: «**not held** or `NOT_EVIDENCE`: the default stays `classic`».
  Step 2 closes with the classic, and the badge keeps the classic's seconds, step 2's median
  62.691 s.
- **Printed, deciding nothing:** under 100, S1′'s cut,
  the classic catches 3 and over-marks 4, the effective score 1 and 2.
  The McNemar test of the catches has the classic's two as its only discordant pairs,
  exact p 0.5:
  with two catches of 17 a lost catch is never significant, so the rule reads a margin, as the
  spec says.

## What it does not say

- **Not that the continuation is a worse check than the classic in general.** Two catches of 17
  cannot show a loss by a test; the rule read no net loss as a margin, and the continuation lost
  both. Wilson's intervals of the share caught overlap: 0.0329–0.3434 for the classic, 0–0.1843
  for the continuation.
- **The 80 were scored cold;** that a warm continuation would score them alike is inferred from the
  bridge's 25, whose scores sat at 90–100, far from the line of 80. The bridge reads whether a cold
  continuation keeps a well-scored answer with `auto`, not whether a cold one flags what a warm
  one would.
- **No other prompt for the continuation was tried.** Another continuation prompt would be a new
  spec, read on the same 80.
- **One corpus, one model and one stand:** V4's aircargo answers, `qwen3:4b-instruct-2507-q4_K_M`,
  stand `57420db`, one day.
- The classic's scores are V4's saved ones, single draws of the classic as V4's stand ran it; the
  continuation's are this replay's single draws, at temperature 0, on another day.
- The labels are the judge's, a model's grades from stage 3, not people's.
- **Not the badge's worth as a detector.** The classic itself flags 2 of the 17, which stage 3
  read as outcome C; this step reads the continuation against the classic, not the badge against a
  better check.
- **The seconds are a cold read's,**
  a median 68.165 s an answer, the longest 91.007 s,
  against the answer stop's 255 s. They say nothing of the chat's warm continuation, which reads
  only its instruction and the turn markers (step 2: a median 8.635 s).
- **Where each cold read began is not measured.** Four answers of five followed another in the
  slot, whose head of ≈ 165 tokens they could keep; the fifth came after a reload. Ollama's
  counters name the whole prompt, and the serve log's slot lines were not read.
- Step 2b counts by the acceptance rule's (c): a quality number, the continuation's catches and
  over-marks on stage 3's 80 labelled answers, published with its provenance — the stand's code
  SHA, the model's digest, the settings and the inputs' SHA-256. The default is unchanged, so not
  by (a).

## Files

| File | Bytes | SHA-256 |
|---|---|---|
| `step2b.json` | 275,790 | `54bfb186b908631ecec8646a0bcb0e9270402277ebdbc8328166bff26dac3d1e` |
| `step2b.first.json` | 80,059 | `c4f9397ddb5d6a8a4b9b8edaeace9b3e42172c92c4388716aeffcfac9625b24f` |
| `step2b.bridge.json` | 127,549 | `ce723ac82091067df0a8a2bd1f6983f9d3cc28e592776bde94261ee60d224310` |
| `environment.jsonl` | 2,946 | `47c806d835e14c654a64f2bad146feee105d1c11d28dba6d4305d39b30b321cd` |
