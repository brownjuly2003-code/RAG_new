# Stage 3b record — the answer prompt V5 against V4, paired — 2026-10-28

The answer prompt V5 asks the model for its evidence first: for each part of the question, the
passage of the documents that answers it, copied word for word; then an answer that says only
what the passages say; then a status line — Evidence / Answer / Status, the whole text shown to
the user. Its 300 answers — WixQA, ConditionalQA and aircargo, written on V4's saved contexts
at V4's stand — were graded by stage 2's judge and read question by question against V4's
answers, by the rules [`answer-prompt-v5.md`](../specs/answer-prompt-v5.md) registered before
V5's first request.

**The decision is not adopted**: the table's first row, harm, holds — WixQA's bad share rises,
51 → 86 of 100, and its good share falls, 40 → 4. V4 stays in `agent/prompts.py`, and stage 4
goes on with V4. Three of V5's five plans do not count — WixQA's M2, ConditionalQA's M1 and
aircargo's: on a second draw the judge marks the format defect differently — so ConditionalQA's
and aircargo's harm and M2's are not read; their numbers are printed beside.

Record: [`reports/answer-prompt-v5/4f48fed/v5-record.json`](../../reports/answer-prompt-v5/4f48fed/v5-record.json),
written by [`reports/answer-prompt-v5/tools/v5_record.py`](../../reports/answer-prompt-v5/tools/v5_record.py)
from the committed records beside it and V4's, each named there by SHA-256. Checked by
[`tests/test_answer_prompt_v5_record_artifact.py`](../../tests/test_answer_prompt_v5_record_artifact.py):
the tool rebuilds the record from those records; each plan's status is its stability rule's,
counted again from its retest; the paired tables, the transitions, the guard's declines and the
defects are counted again from the rows; every table row below is built from the record and the
rows. The records hold identifiers, enums and counts, never the text of a question, a document,
an answer or a judge's note.

## Provenance and method

- **Stand** `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1` on `deproject-mac`, V4's, with
  `QA_PROMPT_V4` in `agent/prompts.py`: V5's text sits in the tools folder, and the product did
  not change. No retrieval: each V4 answer's saved prompt was cut into its question and documents
  and fitted again with V5 by the chat's own `_fit_stream_prompt`, which first rebuilt all 300 of
  V4's prompts byte for byte. The call is the chat's — Qwen3-4B-Instruct-2507 on the CPU,
  temperature 0.2, at most 1,024 tokens, the 3,600-s deadline; no self-evaluation, route or
  follow-up turn. Answers were written 2026-10-27, 13:56 – 23:44 UTC: WixQA, then ConditionalQA,
  then aircargo, V4's ten batches each, every key whole. The stand's four environment lines
  bracket them and show stage 2's Ollama 0.33.2 server (running since 2026-09-13) and stage 2's
  interpreter (`pip freeze` SHA-256 `ed8fe1c2…`).
- **The judge** is stage 2's: `claude-opus-5-5` at effort max, one isolated request per answer,
  the adapter `scripts/chat_answer_judge.py` with V5's marker, V4's salt and instructions, and 15
  retests in each plan. Each plan was frozen after its key's tenth batch and its SHA-256
  committed before its first grade: WixQA's in `e078f95`, ConditionalQA's in `2a9cc5c`,
  aircargo's in `6e7c02b`. M1 is read from plans whose requests carry no reference. No person
  graded an answer (D11).
- **Its order.** Amendment 1 staged the judge — the two bases' M1 first, a stop on harm — while
  more than half of the judge account's week was spent. On Julia's word of 2026-10-27, 22:25 UTC
  («можно запустить судью на весь объем - лимит есть»), all five plans and the three bridges were
  graded whole, and the decision is `v5_record.py`'s table, as first registered. The step
  `v5_core.py` printed after WixQA's M1, «stop, not adopted»
  ([`v5-core.json`](../../reports/answer-prompt-v5/4f48fed/v5-core.json)), decides nothing; that
  the session stopped three plans on it for up to half an hour, and why it resumed them, is in
  the spec's Amendment 1.
- **Bridges.** V4's 15 retested M1 requests of each key were graded again in V5's window. The
  stability rule, read between V4's verdict and the new one, shows that the judge has not moved
  on V4's answers: all three count.
- **Pairs and the read.** A question counts when both sides' M1 verdicts are valid: all 300 do.
  A difference is V5 minus V4. It falls or rises (detected) only when both Newcombe's paired
  interval and the cluster bootstrap (stage 2's clusters, seed 20261001, 10,000 resamples)
  exclude zero on the same side. Each cell reads V4 → V5 of n (the difference; the read 95 %
  interval), its direction.

## The judge's plans

| Plan | Requests | Cost | Retest | Status |
|---|---:|---:|---|---|
| `v5-wixqa-judge-m1` | 115 | $33.74 | 14/15 agree, 0 two steps apart, κ 0.00 | counted |
| `v5-wixqa-judge-m2` | 115 | $36.83 | 12/15 agree, 1 two steps apart, κ -0.10 | NOT_EVIDENCE |
| `v5-conditionalqa-judge-m1` | 115 | $32.19 | 11/15 agree, 4 two steps apart, κ 0.32 | NOT_EVIDENCE |
| `v5-conditionalqa-judge-m2` | 115 | $34.20 | 14/15 agree, 1 two steps apart, κ 0.81 | counted |
| `v5-aircargo-judge` | 115 | $30.33 | 12/15 agree, 2 two steps apart, κ -0.06 | NOT_EVIDENCE |
| `v5-bridge-wixqa` | 30 | $5.13 | 13/15 agree, 2 two steps apart, κ 0.70 | counted |
| `v5-bridge-conditionalqa` | 30 | $6.05 | 15/15 agree, 0 two steps apart, κ 1.00 | counted |
| `v5-bridge-aircargo` | 30 | $4.82 | 14/15 agree, 0 two steps apart, κ 0.94 | counted |

620 new requests, 2026-10-27 17:14 – 2026-10-28 03:45 UTC, $175.71 by the replies' own cost
(the spec forecast ≈ $116–130): a grade of a V5 answer cost $0.26–0.32, of a V4 answer in the
bridges $0.16–0.20 — V5's answers hold about twice V4's tokens. A bridge's row counts V4's 15
replies beside its 15 new ones. WixQA's M1 counts by agreement — 14 of 15, none two
steps apart — while its κ is 0.00: 14 of its 15 retested answers are bad on both draws.

## The decision

| Primary: the bad share, paired | V4 → V5 |
|---|---|
| WixQA and ConditionalQA pooled | 108 → 167 of 200 (+29.5 pp; +21.7 to +36.9), rises |
| the same, on the pairs whose context V5 read unchanged | 90 → 136 of 164 (+28.1 pp; +19.2 to +36.4), rises |

| Base | Pairs | Bad | Good | Declines where the gold says not answerable |
|---|---:|---|---|---|
| WixQA | 100 | 51 → 86 of 100 (+35.0 pp; +23.0 to +45.6), rises | 40 → 4 of 100 (-36.0 pp; -45.6 to -26.2), falls | — |
| ConditionalQA | 100 | 57 → 81 of 100 (+24.0 pp; +13.5 to +33.8), rises | 35 → 17 of 100 (-18.0 pp; -28.1 to -7.5), falls | 4 → 4 of 20 (+0.0 pp; -13.2 to +13.2), not detected |
| aircargo | 100 | 17 → 89 of 100 (+72.0 pp; +61.2 to +81.0), rises | 63 → 8 of 100 (-55.0 pp; -65.0 to -44.1), falls | — |

The table read in its order:

1. **Harm — holds.** WixQA's M1 plans and its bridge count, and its bad share rises while its
   good share falls: each alone is row 1. ConditionalQA's V5 M1 plan and aircargo's plan do not
   count, so their harm is not read; their shares move the same way in the table and decide
   nothing. The pooled bad share is read for harm only when both bases are, and M2's agreement
   only when both bases' M2 plans count on both sides — WixQA's V5 M2 does not.
2. **Rows 2–4 are not read:** the first row that holds decides. Row 2 would hold as well —
   three plans are not counted — and it too keeps V4.

## The three parts on the page

| Base | «other», V4 → V5 | «copied_context», V4 → V5 | Other defects, V5 | Quoting their context, V4 → V5 | Format aside: good · partial_ok · bad, V4 → V5 |
|---|---|---|---:|---|---|
| WixQA | 0 → 63 | 0 → 12 | 4 | 59 → 96 | 40 · 9 · 51 → 33 · 28 · 39 |
| ConditionalQA | 4 → 55 | 0 → 8 | 2 | 70 → 99 | 35 · 8 · 57 → 43 · 11 · 46 |
| aircargo | 1 → 51 | 2 → 14 | 22 | 77 → 94 | 64 · 22 · 14 → 50 · 13 · 37 |

A defect makes an answer bad whatever its claims (`chat_answer_judge.classify`). V4's answers
almost never drew these two; V5's drew them in 75 of WixQA's 100 answers, 63 of ConditionalQA's
and 65 of aircargo's. The judge's notes are kept private; read by the session, they name the
visible scaffold — the quoted passages and the status line around the answer — as what is
wrong. The spec foresaw «copied_context» leaning against V5 and kept the judge's instructions on
purpose; that the scaffold itself would be graded a defect, it did not foresee. It is also where
the judge wavers: in the three plans that do not count, the retests agree on the defect in 8, 11
and 11 of 15 pairs, on whether the answer answers in 14 or 15, and on the context in all 15.

The last column is read after the grades, is not registered and decides nothing: each side's
classes on the pairs with these two defects set to none, every other field of the verdict as the
judge gave it. On it V5's bad share falls on both external bases (WixQA 51 → 39, ConditionalQA
57 → 46) and its partial answers rise (WixQA 9 → 28): under its evidence, V5's answer more often
says only what the documents say and less often all of it — ReClaim's trade, which the spec's
M2 was set to guard. On aircargo, the product's corpus, V5 stays worse even so (bad 14 → 37):
22 of its answers carry another defect — 11 in the wrong language, 10 repeating, 1 cut off at
the token cap.

## Printed beside, deciding nothing

| Base | Wrong declines, V4 → V5 | `context_has_answer`: same, lost, gained | Claims supported | Same context |
|---|---|---|---|---:|
| WixQA | 22 → 10 | 97, 0, 3 | 90.5 % → 94.7 % | 81/100 |
| ConditionalQA | 6 → 5 | 99, 0, 1 | 79.2 % → 88.5 % | 83/100 |
| aircargo | 0 → 0 | 100, 0, 0 | 96.7 % → 93.7 % | 36/100 |

A wrong decline is a decline while the judge finds the answer in the context. On the external
bases V5's claims are more often supported and it declines less often where the context holds
the answer — the gain the spec sought, under a form the judge grades bad. «Same context» counts
the questions whose V5 prompt held V4's documents unchanged; on the rest, V5's longer template
(+178 characters) left a shorter tail of the same retrieval.

| Base | M1 transitions V4 → V5 (good · partial_ok · bad, from good / partial_ok / bad) | Median stream, s | Median chunks | At the 1,024-token cap, V5 |
|---|---|---|---|---:|
| WixQA | 4 · 4 · 32 / 0 · 1 · 8 / 0 · 5 · 46 | 85.3 → 103.4 | 105 → 202 | 0 |
| ConditionalQA | 11 · 1 · 23 / 2 · 1 · 5 / 4 · 0 · 53 | 76.5 → 100.5 | 118 → 234 | 0 |
| aircargo | 8 · 0 · 55 / 0 · 3 · 17 / 0 · 0 · 17 | 85.7 → 104.0 | 80 → 182 | 1 |

A stream chunk is a token; the judge sees an answer cut at the cap as `cut_off`. Time decides
nothing in the spec.

| Base | M2 status | Agrees with the reference, paired | Right declines without a reference |
|---|---|---|---|
| WixQA | NOT_EVIDENCE | 34 → 29 of 100 (-5.0 pp; -11.9 to +1.7), not detected | — |
| ConditionalQA | counted | 48 → 49 of 80 (+1.2 pp; -7.5 to +11.2), not detected | 4 → 4 of 20 |

| M2: agrees with the reference, paired | V4 → V5 |
|---|---|
| WixQA and ConditionalQA pooled | 82 → 78 of 180 (-2.2 pp; -8.0 to +3.3), not detected |

## What this does not say

- V5 was written after reading V4's answers, and it runs on the same questions: the comparison
  is in sample. V5 names no question.
- V5 answered on V4's saved contexts, never more of them: the record compares two prompts, not
  two paths.
- One answer a side: the 4B samples without a seed. One draw of the judge, which, like V5's
  author, is the session's model (D12).
- The format-aside column is a reading after the grades, not V5 with its evidence hidden: a user
  who saw only the answer would read another text, and the judge would grade another text.
  Nothing here measured that.
- The routes, the self-evaluation and the widget's answers under V5 are unmeasured, and so is
  how a person reads an answer in three parts.
