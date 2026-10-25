# Stage 2b record — the answer prompt V4 against V3, paired — 2026-10-25

The answer prompt V4 fixes three of V3's own instructions that stage 2's judge found in the
bad answers: a decline when the documents answer in part, advice to contact a specialist whom
no document names, and the placeholder «[N]». Its 300 answers — WixQA, ConditionalQA and
aircargo, stage 2's questions on stage 2's stand code — were graded by stage 2's judge and read
question by question against V3's answers, by the rules
[`answer-prompt-v4.md`](../specs/answer-prompt-v4.md) registered before V4's first request.

**The decision is adopted**: the pooled bad share of the two external bases falls, and no harm
row of the table holds. V4 stays in `agent/prompts.py`, and stage 3 reads its answers.

Record: [`reports/answer-prompt-v4/4f48fed/v4-record.json`](../../reports/answer-prompt-v4/4f48fed/v4-record.json),
written by [`reports/answer-prompt-v4/tools/v4_record.py`](../../reports/answer-prompt-v4/tools/v4_record.py)
from the committed records beside it and stage 2's, each named there by SHA-256. Checked by
[`tests/test_answer_prompt_v4_record_artifact.py`](../../tests/test_answer_prompt_v4_record_artifact.py):
the tool rebuilds the record from those records; each plan's stability verdict, the paired
tables, the transitions, the guard's declines and the two defects are counted again from the
rows; no V4 answer has a path break; every table row below is built from the record. The records
hold identifiers, enums and counts, never the text of a question, a document, an answer or a
judge's note.

## Provenance and method

- **Stand** `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1` on `deproject-mac`. It differs from
  stage 2's stand `5e308fe` in `agent/prompts.py`, the two judges no product module imports, and
  comment lines of two CI files (`raise_stand.sh` refuses any other). Qwen3-4B-Instruct-2507 on
  the CPU, the chat's `/api/ask/stream`, each question a visitor's first. Answers were collected
  2026-10-24 13:12 – 2026-10-25 15:06 UTC: WixQA, then ConditionalQA, then aircargo, ten batches
  each, every batch complete with no path break. The stand's four environment lines bracket
  them and show stage 2's Ollama 0.33.2 server (pid 12377, running since 2026-09-13) and stage
  2's interpreter (`pip freeze` SHA-256 `ed8fe1c2…`).
- **The judge** is stage 2's: `claude-opus-5-5` at effort max, one isolated request per answer,
  the adapter `scripts/chat_answer_judge.py`, and 15 retests in each plan. Each plan was frozen
  and its SHA-256 committed before its first grade: the external bases' in `410a642`,
  aircargo's in `d5f6e91`. M1 is read from plans whose requests carry no reference. No person
  graded an answer (D11).
- **Bridges.** Stage 2's 15 retested M1 requests of each key were graded again in V4's window.
  The stability rule, read between stage 2's verdict and the new one, shows that the judge has
  not moved: all three count.
- **Pairs and the read.** A question counts when both sides' M1 verdicts are valid: all 300 do.
  A difference is V4 minus V3. It falls or rises (detected) only when both Newcombe's paired
  interval and the cluster bootstrap (stage 2's clusters, seed 20261001, 10,000 resamples)
  exclude zero on the same side. Each cell reads V3 → V4 of n (the difference; the read 95 %
  interval), its direction.

## The judge's plans

| Plan | Requests | Cost | Retest | Status |
|---|---:|---:|---|---|
| `v4-aircargo-judge` | 115 | $17.25 | 14/15 agree, 0 two steps apart, κ 0.94 | counted |
| `v4-wixqa-judge-m1` | 115 | $20.34 | 15/15 agree, 0 two steps apart, κ 1.00 | counted |
| `v4-wixqa-judge-m2` | 115 | $22.76 | 14/15 agree, 0 two steps apart, κ 0.96 | counted |
| `v4-conditionalqa-judge-m1` | 115 | $23.43 | 12/15 agree, 2 two steps apart, κ 0.68 | counted |
| `v4-conditionalqa-judge-m2` | 115 | $24.14 | 14/15 agree, 1 two steps apart, κ 0.86 | counted |
| `v4-bridge-aircargo` | 30 | $4.70 | 15/15 agree, 0 two steps apart, κ 1.00 | counted |
| `v4-bridge-wixqa` | 30 | $5.39 | 14/15 agree, 0 two steps apart, κ 0.96 | counted |
| `v4-bridge-conditionalqa` | 30 | $5.83 | 12/15 agree, 2 two steps apart, κ 0.69 | counted |

620 new requests, 2026-10-25 08:58 – 17:07 UTC, $116.15 by the replies' own cost (the spec
forecast ≈ $112); a bridge's row counts stage 2's 15 replies beside its 15 new ones.

## The decision

| Primary: the bad share, paired | V3 → V4 |
|---|---|
| WixQA and ConditionalQA pooled | 127 → 108 of 200 (-9.5 pp; -15.7 to -3.1), falls |
| the same, on the pairs whose context V4 read unchanged | 110 → 92 of 170 (-10.6 pp; -17.5 to -3.5), falls |

| Base | Pairs | Bad | Good | Declines where the gold says not answerable |
|---|---:|---|---|---|
| aircargo | 100 | 14 → 17 of 100 (+3.0 pp; -5.0 to +11.1), not detected | 69 → 63 of 100 (-6.0 pp; -14.3 to +2.5), not detected | — |
| WixQA | 100 | 63 → 51 of 100 (-12.0 pp; -20.8 to -3.3), falls | 27 → 40 of 100 (+13.0 pp; +4.6 to +21.2), rises | — |
| ConditionalQA | 100 | 64 → 57 of 100 (-7.0 pp; -16.2 to +2.5), not detected | 31 → 35 of 100 (+4.0 pp; -4.5 to +12.4), not detected | 8 → 4 of 20 (-20.0 pp; -40.0 to +0.4), not detected |

The table read in its order:

1. **Harm — does not hold.** No base's bad share rises. No good share falls, so no base has a
   good share falling while its bad share does not. ConditionalQA's declines among its 20 not
   answerable questions are not detected falling, and the pooled bad share does not rise.
2. **`NOT_EVIDENCE` — does not hold.** Every M1 plan of both sides and every bridge counts, and
   each base ran whole.
3. **Adopted — holds.** The pooled bad share falls, and it falls on the pairs of unchanged
   context too: the gain is the prompt's, not a shorter context's.

## Close to the line, deciding nothing

- **ConditionalQA's guard.** V3 declined 8 of the 20 questions whose gold says the documents do
  not answer them; V4 declines 4. No question moved the other way. The bootstrap excludes zero;
  Newcombe's interval reaches +0.4 pp, so the drop is not detected and row 1 does not hold. It
  is the cost the guard was written against: «answer what the documents cover» also answers
  some questions they do not.
- **aircargo, the product's own corpus.** No change is detected, but both shares lean against
  V4. Nine answers good under V3 are bad under V4, and one moves the other way. In eight of the
  nine the judge finds V4 adding one or two claims the context does not support, where V3's
  answer was fully supported. The context is not the cause: on the 40 questions whose context V4
  read unchanged, good went 28 → 22. Aircargo's supported claims went 97.2 % → 96.7 %, while
  WixQA's rose 85.1 % → 90.5 %. Stage 3 reads its handover signals on these answers, and its
  S3 marks an answer when any of its claims is unsupported.

## The two defects

| Base | «[N]» in answers, V3 → V4 | Referral to a specialist, paired | Of them routed to a person |
|---|---|---|---|
| aircargo | 0 → 0 | 4 → 2 of 100 (-2.0 pp; -7.8 to +3.2), not detected | 2 → 0 |
| WixQA | 8 → 0 | 42 → 0 of 100 (-42.0 pp; -52.3 to -32.1), falls | 18 → 0 |
| ConditionalQA | 14 → 0 | 28 → 0 of 100 (-28.0 pp; -37.5 to -19.3), falls | 16 → 0 |

The referral is V3's noun «specialist» or «специалист» in an answer. Aircargo's two V4 answers
holding it are ones whose documents name a specialist. On the external bases, no V4 answer
holds it.

## Printed beside, deciding nothing

| Base | Wrong declines, V3 → V4 | Bad turned good by a decline | `context_has_answer`: same, lost, gained | Claims supported | Routed to a person, paired | Same context |
|---|---|---:|---|---|---|---:|
| aircargo | 2 → 0 | 0 | 100, 0, 0 | 97.2 % → 96.7 % | 3 → 3 of 100 (+0.0 pp; -4.8 to +4.8), not detected | 40/100 |
| WixQA | 29 → 22 | 3 | 99, 1, 0 | 85.1 % → 90.5 % | 24 → 14 of 100 (-10.0 pp; -18.1 to -2.1), falls | 81/100 |
| ConditionalQA | 13 → 6 | 1 | 97, 1, 2 | 76.3 % → 79.2 % | 27 → 17 of 100 (-10.0 pp; -18.0 to -2.1), falls | 89/100 |

A wrong decline is a decline while the judge finds the answer in the context. «Same context»
counts the questions whose prompt held V3's documents unchanged; on the rest, V4's longer
template (+249 characters) left a shorter tail of the same retrieval. Fewer answers routed to a
person is a product change: the chat routes an answer whose self-evaluation scores below 80, and
fewer of V4's do.

| Base | M1 transitions V3 → V4 (good · partial_ok · bad, from good / partial_ok / bad) | Median answer, V3, s | Median answer, V4, s |
|---|---|---:|---:|
| aircargo | 57 · 3 · 9 / 5 · 12 · 0 / 1 · 5 · 8 | 304.3 | 296.3 |
| WixQA | 24 · 0 · 3 / 5 · 4 · 1 / 11 · 5 · 47 | 256.4 | 301.1 |
| ConditionalQA | 24 · 0 · 7 / 1 · 3 · 1 / 10 · 5 · 49 | 253.1 | 249.3 |

The times compare nothing: V4's answers ran on a Mac shared with other projects' tests
(retrieval alone took 2.7× stage 2's on WixQA's first batches), and time decides nothing in the
spec.

| Base | M2 status | Agrees with the reference, paired | Right declines without a reference |
|---|---|---|---|
| WixQA | counted | 29 → 34 of 100 (+5.0 pp; -0.5 to +10.6), not detected | — |
| ConditionalQA | counted | 43 → 48 of 80 (+6.2 pp; -1.3 to +13.6), not detected | 8 → 4 of 20 |

## What this does not say

- V4 was written after reading these V3 answers, and it runs on the same questions: the
  comparison is in sample. V4 names no question. Aircargo is the least-fitted base, and stage
  7's locked parts are the real check.
- One answer a side: the 4B samples without a seed. One draw of the judge, which, like V4's
  author, is the session's model (D12).
- The widget's `/api/ask` and the follow-up turns build on the same prompts and change with V4,
  unmeasured.
- MultiHop-RAG was not run (advisory in the spec); stage 5 compares the final path with stage
  2's numbers there.
