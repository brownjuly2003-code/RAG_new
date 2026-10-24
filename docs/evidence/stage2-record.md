# Stage 2 record — the four corpora on the chat path — 2026-10-24

The first answer-quality numbers on the customer's path: 100 answers each on aircargo,
ConditionalQA, WixQA and MultiHop-RAG, graded by the registered judge, side by side with their
context, routes and times. This is part 5 of
[`stage2-four-corpora.md`](../specs/stage2-four-corpora.md): every number below was read by
the rules that spec registered before the answers were graded.

Record: [`reports/stage2/5e308fe/stage2-record.json`](../../reports/stage2/5e308fe/stage2-record.json),
written by [`reports/stage2/tools/stage2_record.py`](../../reports/stage2/tools/stage2_record.py)
from the committed records only, each pinned there by SHA-256. Checked by
[`tests/test_stage2_record_artifact.py`](../../tests/test_stage2_record_artifact.py): the tool
rebuilds the record byte for byte; the classes, marks, claims, defects, M2 counts, the sway
table and the stability verdicts are counted again from the rows; no counted question has a
path break; every table row below is built from the record. The records hold identifiers,
enums and counts — no text of a question, a document, an answer or the judge's note.

## Provenance and method

- **Stand** `5e308fe48cca0955c3007057a574a425f71e2a6a` on `deproject-mac`, Qwen3-4B-Instruct-2507
  on the CPU at the code defaults; the chat's `/api/ask/stream`, each question a visitor's
  first. Answers: aircargo [part 1](stage2-retrieval-baseline.md), the external bases
  [part 4](stage2-external-answers.md); contexts and gold coverage from part 2.
- **The judge** is `claude-opus-5-5` at effort max, one isolated request per answer
  (`evaluation/isolated_request.py`: a clean session, no tools, memory, plugins or hooks), the
  adapter `scripts/chat_answer_judge.py`. Each plan was frozen and its SHA-256 committed
  before its first grade; 15 of each plan's requests are retests of others.
- **M1 without the reference.** Part 4's M1 is read from plans whose requests carry no
  reference (`--withhold-references`), as aircargo's carry none; the m2 plans of the same
  answers carry it and give M2.
- **Intervals.** Each share prints its n and the read 95 % interval: Wilson for aircargo's
  shares of answers; the wider of Wilson and a cluster bootstrap (10,000 resamples, seed
  20261001) for an external base's shares and for every share of marks or claims — the
  question's cluster on an external base, the answer on aircargo. Differences: Newcombe's
  hybrid score interval on the read intervals.
- **Stability.** A plan counts when its 15 retest pairs give a quadratic κ of at least 0.6, or
  at least 13 agree with none two steps apart (good against bad).

## The judge's plans

| Plan | Requests | Cost | Retest | Status |
|---|---:|---:|---|---|
| `p1-aircargo-judge` | 115 | $17.55 | 15/15 agree, 0 two steps apart, κ 1.00 | counted |
| `p2-aircargo-context-judge` | 130 | $12.16 | 14/15 agree, 0 two steps apart, κ 0.63 | counted |
| `p4-conditionalqa-judge-m1` | 115 | $22.31 | 14/15 agree, 1 two steps apart, κ 0.86 | counted |
| `p4-wixqa-judge-m1` | 115 | $19.20 | 15/15 agree, 0 two steps apart, κ 1.00 | counted |
| `p4-multihoprag-judge-m1` | 115 | $18.84 | 15/15 agree, 0 two steps apart, κ 1.00 | counted |
| `p4-conditionalqa-judge-m2` | 115 | $23.15 | 12/15 agree, 2 two steps apart, κ 0.69 | counted |
| `p4-wixqa-judge-m2` | 115 | $21.41 | 14/15 agree, 0 two steps apart, κ 0.96 | counted |
| `p4-multihoprag-judge-m2` | 115 | $17.55 | 13/15 agree, 2 two steps apart, κ 0.59 | NOT_EVIDENCE |

935 valid requests, graded 2026-10-20 to 2026-10-24; part 4's 690 were each admitted at their
first reply.
`p4-multihoprag-judge-m2` failed the stability rule: two of its answers were good in one
request and bad in the other, and κ fell short of 0.6. By the spec its numbers are
`NOT_EVIDENCE`, and its prompt is not tuned on the same answers. So MultiHop-RAG's M2 and the
reference's sway there are `NOT_EVIDENCE` and are not printed below; MultiHop-RAG's M1, from
its m1 plan, counts.

## M1, the answer's verdict

good — complete against what the documents offer and fully supported, or a right decline;
partial_ok — faithful but partial; both only where the judge finds the answer in the
documents. Everything else is bad.

| Corpus | good | partial_ok | bad | The plan's retest |
|---|---|---|---|---|
| aircargo | 69/100 (69.0 %; 59.4–77.2) | 17/100 (17.0 %; 10.9–25.6) | 14/100 (14.0 %; 8.5–22.1) | 15/15 agree, 0 two steps apart, κ 1.00 |
| ConditionalQA | 31/100 (31.0 %; 22.0–40.6) | 5/100 (5.0 %; 1.0–10.7) | 64/100 (64.0 %; 54.3–73.5) | 14/15 agree, 1 two steps apart, κ 0.86 |
| WixQA | 27/100 (27.0 %; 18.2–35.9) | 10/100 (10.0 %; 5.5–17.4) | 63/100 (63.0 %; 53.2–71.8) | 15/15 agree, 0 two steps apart, κ 1.00 |
| MultiHop-RAG | 65/100 (65.0 %; 50.8–75.2) | 1/100 (1.0 %; 0.2–5.5) | 34/100 (34.0 %; 24.1–46.2) | 15/15 agree, 0 two steps apart, κ 1.00 |

M1's other parts — marks are the `[N]` marks naming a listed document, a share of marks;
claims a share of claims:

| Corpus | Supported marks | Supported claims | Answers with a defect | Marks naming no listed document | Answers without context |
|---|---|---|---|---|---:|
| aircargo | 135/199 (67.8 %; 58.2–77.2) | 495/509 (97.2 %; 95.2–98.8) | 2/100 (2.0 %; 0.5–7.0) | 3 in 3 | 0 |
| ConditionalQA | 71/98 (72.5 %; 62.9–80.3) | 277/363 (76.3 %; 71.1–81.0) | 14/100 (14.0 %; 8.5–22.1) | 0 in 0 | 1 |
| WixQA | 70/95 (73.7 %; 60.0–85.6) | 342/402 (85.1 %; 80.5–89.0) | 7/100 (7.0 %; 2.3–12.6) | 0 in 0 | 3 |
| MultiHop-RAG | 113/131 (86.3 %; 72.2–96.9) | 133/168 (79.2 %; 56.2–82.5) | 2/100 (2.0 %; 0.0–8.0) | 0 in 0 | 0 |

aircargo's two defects are copied context; the external bases' are `other` but one MultiHop-RAG
repetition. By stratum — without an answer, good is a right decline:

| Base | Stratum | Questions | good | partial_ok | bad | good, read |
|---|---|---:|---:|---:|---:|---|
| ConditionalQA | `answerable` | 80 | 24 | 3 | 53 | 24/80 (30.0 %; 20.0–40.0) |
| ConditionalQA | `not_answerable` | 20 | 7 | 2 | 11 | 7/20 (35.0 %; 15.0–55.0) |
| MultiHop-RAG | `inference_query` | 70 | 42 | 1 | 27 | 42/70 (60.0 %; 23.8–69.0) |
| MultiHop-RAG | `null_query` | 30 | 23 | 0 | 7 | 23/30 (76.7 %; 60.0–90.0) |

## Two corpora: aircargo against each external base

aircargo's share minus the base's, in percentage points; «not detected» is not «no difference».
Three comparisons per class, none corrected for the others.

| aircargo minus | good | partial_ok | bad |
|---|---|---|---|
| ConditionalQA | +38.0 pp (+24.4 to +50.2), detected | +12.0 pp (+3.7 to +21.4), detected | -50.0 pp (-60.9 to -37.3), detected |
| WixQA | +42.0 pp (+28.9 to +54.1), detected | +7.0 pp (-2.6 to +16.7), not detected | -49.0 pp (-59.4 to -36.3), detected |
| MultiHop-RAG | +4.0 pp (-10.1 to +20.4), not detected | +16.0 pp (+8.4 to +24.6), detected | -20.0 pp (-33.3 to -7.2), detected |

## M2, against the gold

| Base | With a reference | Counts | agrees, read | Without a reference |
|---|---:|---|---|---|
| aircargo, keywords (weak gold) | 100 | FULL 57, PART 23, MISS 20 | 57/100 (57.0 %; 47.2–66.3) | — |
| ConditionalQA | 80 | agrees 43, partial 9, disagrees 15, declined 13 | 43/80 (53.8 %; 42.5–65.0) | right 8/20 |
| WixQA | 100 | agrees 29, partial 17, disagrees 18, declined 36 | 29/100 (29.0 %; 18.4–39.2) | — |
| ConditionalQA, conditional | 26 | agrees 12, partial 6, disagrees 6, declined 2 | 12/26 (46.2 %; 28.0–64.5) | — |
| ConditionalQA, not conditional | 54 | agrees 31, partial 3, disagrees 9, declined 11 | 31/54 (57.4 %; 43.8–70.4) | — |

A question without a reference is right when the answer declines. ConditionalQA's conditional
references are the bare answers without their conditions, so `agrees` there can hide a missing
condition. aircargo's keywords are the repository's rule (`_kw_status`), a weak gold.

## The reference's sway

The m1 and m2 plans' classes on the same answers; printed, not gated. Columns of the last cell:
m1 good / partial_ok / bad, each split m2 good · partial_ok · bad.

| Base | Answers | Same class | Two steps apart | κ | m1 → m2 |
|---|---:|---:|---:|---:|---|
| ConditionalQA | 100 | 89 | 8 | 0.79 | 26 · 2 · 3 / 0 · 5 · 0 / 5 · 1 · 58 |
| WixQA | 100 | 95 | 3 | 0.91 | 27 · 0 · 0 / 1 · 8 · 1 / 3 · 0 · 60 |

## M3, the context

aircargo, part 2's context judge at «sent» (`full` and `partial` hold the answer); its 100
agree with part 1's `context_has_answer` on 100 of 100:

| Run | Contexts | full | partial | none | Holds the answer |
|---|---:|---:|---:|---:|---|
| aircargo | 100 | 99 | 1 | 0 | 100/100 (100.0 %; 96.3–100.0) |
| aircargo-gr | 15 | 9 | 5 | 1 | 14/15 (93.3 %; 70.2–98.8) |

External bases, the gold's coverage on the questions with gold (part 2's record):

| Base | Primary | Questions with gold | Fused pool | Reranked five | Sent |
|---|---|---:|---|---|---|
| ConditionalQA | `all_evidence_coverage` | 80 | 60/80 (75.0 %; 64.5–83.2) | 46/80 (57.5 %; 46.2–68.8) | 60/80 (75.0 %; 65.0–85.0) |
| WixQA | `gold_article` | 100 | 84/100 (84.0 %; 76.5–90.8) | 68/100 (68.0 %; 57.9–78.0) | 68/100 (68.0 %; 57.9–78.0) |
| MultiHop-RAG | `all_evidence_coverage` | 70 | 22/70 (31.4 %; 24.4–60.9) | 7/70 (10.0 %; 0.0–21.1) | 10/70 (14.3 %; 4.3–26.3) |

## Routes, times, parity

| Corpus | Routed to a person | Median total, s | Median first token, s | Prompt parity |
|---|---|---:|---:|---|
| aircargo | 3/100 (3.0 %; 1.0–8.5) | 304.3 | 178.2 | 100/100 |
| ConditionalQA | 27/100 (27.0 %; 19.3–36.4) | 253.1 | 168.8 | 100/100 |
| WixQA | 24/100 (24.0 %; 15.7–33.3) | 256.4 | 165.1 | 100/100 |
| MultiHop-RAG | 33/100 (33.0 %; 20.7–63.5) | 275.0 | 180.2 | 100/100 |

Parity: each answer's prompt has the SHA-256 of part 2's retrieval prompt for its question.

## Part 3, the graph lane

An archive diagnostic, no request (amended 2026-10-19; pinned by
`tests/test_stage2_part3_archives.py`): on GR-3's 100 + 15 aircargo questions the entity lane
changed the context on at most 2 of 115; otherwise the graph route trims the hybrid's five
documents to about three — on 57 of 100 (59 for the structural route alone) and 5 of 15
every document it keeps is one of the hybrid's verbatim. It cannot show answer quality, latency on the current path, the second
index generation's effect, or whether a graph helps on the final path; stage 7 measures that.

## What these numbers cannot show

- **One judge.** No person graded an answer (Julia's decision D11); every verdict is one
  model's, stable on its retests where the table says counted. A wrong verdict common to both
  requests of a pair passes the stability rule.
- **M1 weighs the answer against the documents the chat sent.** A good answer is complete
  against them, not necessarily against the question: on MultiHop-RAG 42 of the 70 answers
  with gold are good, while every evidence group reached the sent context for 10 of the 70 —
  the judge's `context_has_answer` is its own reading, M3's coverage counts every evidence
  group. M2 is the check against the gold, and on MultiHop-RAG it is `NOT_EVIDENCE`.
- **Clustered questions.** One of MultiHop-RAG's 45 clusters holds 49 of its 100 questions, so
  its read intervals are wide and its 100 answers say less than 100 independent ones would.
- **Small n.** At n = 100, 80 % power holds only for a difference of about 20 points between
  two corpora; a smaller one is likely to read «not detected». partial_ok and the strata are
  thin.
- **aircargo's questions are agent-written** with labels approved on 2026-09-25; the external
  bases' are the datasets' own, in English.
- **Routes and times describe behaviour.** Whether a route was right is stage 3's question;
  the times come from runs over several days, not an idle-host speed measurement (stage 4).
