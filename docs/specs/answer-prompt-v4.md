# The answer prompt V4: three defects of V3, measured against stage 2's answers

Status 2026-10-24: **registered before V4's first request**, with the tools that read it and
their test ([Records](#records)). The session's decision under Julia's rule of 2026-10-19
(«Прими решения сам из цели — лучший продукт в финале»), after her «надо разбираться и что-то
решать»; [`PLAN.md`](../../PLAN.md), amended the same day, makes it stage 2b, before stage 3.

## Why

| Per 100 answers, stage 2 ([record](../evidence/stage2-record.md)) | aircargo | ConditionalQA | WixQA | MultiHop-RAG |
|---|---|---|---|---|
| M1 bad | 14 | 64 | 63 | 34 |
| declined although the documents hold the answer, at least in part | 2 | 13 | 29 | 7 |
| advise to contact a support specialist | 4 | 28 | 42 | 43 |
| print the placeholder «[N]» as a citation | 0 | 14 | 8 | 3 |

Rows 1–2 are the committed judge records'; rows 3–4 are `answer_marks.py`'s over the private
answers: `\[N\]`, and V3's noun `specialist|специалист`, which the documents of 115 of these 117
answers do not hold (WixQA's 11 referrals to its Customer Care, which its articles name, are
left out). Up to 18 of ConditionalQA's 64 bad answers and 36 of WixQA's 63 have one of the three
as their cause; the rest are the 4B's reasoning and retrieval (stage 7's work).

## What changes

`QA_PROMPT_V4` in `agent/prompts.py`, the registered text: (1) **a decline only when nothing
answers** — a context that answers in part, or in general terms, gives its answer and names what
it does not cover; (2) **conditions** stated instead of a bare yes or no; (3) **no advice of its
own** — the chat keeps its operator button; (4) **citations by a real number**.
`CONVERSATIONAL_QA_PROMPT_V4` changes its citation sentence only. No word of a domain or a
language is added. The widget's `/api/ask` builds its answer from the same prompts
(`agent/graph.py`): its answers and the follow-up turns change too, unmeasured, as stage 2 left
them.

**The context moves with the template:** +249 characters, +61 estimated tokens against the input
limit of 2,636. `fit_context_docs` keeps whole documents while they fit and excerpts the next, so
V4 can cut a prompt V3 sent whole (V3's within 61 tokens of the limit: aircargo 1, ConditionalQA
1, WixQA 3), excerpt V3's last whole document, or excerpt other paragraphs. 98 of aircargo's 100
V3 prompts were cut: there the prompt and its shorter context are measured together.

**Rule (a):** `tests/test_chat_answer_prompt_e2e.py` proves the request the chat makes of its
model on the real stream path — `/api/ask/stream`, a real `ConversationSession`, the product's
Ollama client, a fake Ollama recording the prompt: the four instructions, no «[N]», no
«specialist». It passed on the Mac before the registering commit; a return to V3 reverts it with
the prompt.

## The stand and the run

- **Stand:** `sh reports/answer-prompt-v4/tools/raise_stand.sh <registering commit>`, the
  [stage-1 handoff](../operations/session-handoff-2026-10-18-stage1-closed.md)'s command, at
  `/Users/julia/RAG_new_chat_<7>`. It refuses a product diff against `5e308fe`, stage 2's stand,
  beyond the five files its `--stat` lists: `agent/prompts.py`, the two judges, which no product
  module imports, and comment lines of `.github/workflows/ci.yml` and `.pre-commit-config.yaml`.
  Path, model (`qwen3:4b-instruct-2507-q4_K_M`, digest `0edcdef34593…`), indexes and tenants are
  [stage 2's](stage2-four-corpora.md#what-is-measured-on-what).
- **Environment:** `stand_env.py` writes a line to `chatlive/v4-environment.jsonl` at the stand
  and after each base. The record refuses lines that do not bracket V4's answers, or that show
  other than stage 2's one server of Ollama 0.33.2, running since 2026-09-13, and its
  interpreter: `pip freeze` SHA-256
  `ed8fe1c2142b1a9ff7f1c80db891a0887860ba939131bf5cd3cbde324b161ada`, the newest package older
  than stage 2's first answer.
- **Questions:** stage 2's, in its order, batches of ten, `PART` `v4` (runs `v4-<key>-bNN`):
  `wixqa`, `conditionalqa` (80 answerable, 20 not), `aircargo` (the product's corpus), 100 each.
  MultiHop-RAG is advisory and not run.
- **Forecast and stops:** stage 2 part 4's — a batch 4,060 s, a base 11.3 h, its cap 33.8 h; a
  question past 1,020 s (a batch's first) or 1,200 s ends its batch. Stage 2 took 24.6 h on these
  bases against 34 h forecast. One, five, the rest as
  [stage 2](stage2-four-corpora.md#parts-forecasts-stop-rules): the first five answers of a base
  must be V4's by `prompt_id`, or the base stops and its batch 1 reruns on the right stand.

## The judge

Stage 2's request: `scripts/chat_answer_judge.py`, salt `chat-answer-judge-2026-10-18`,
instructions SHA-256 `fd015e742c835a17b17704ad629df90a34a61ac600762e8c74e52aababdcc9c2`,
`claude-opus-5-5` at effort `max` by stage 2's route, 15 retests a plan,
[the stability rule](stage2-four-corpora.md#the-judge); the adapter tells V3's saved prompts
from V4's by `prompt_id`. Five plans, each frozen after its base's tenth batch and committed
before its first grade: `v4-wixqa-judge-m1` and `v4-conditionalqa-judge-m1` (references
withheld), `v4-wixqa-judge-m2`, `v4-conditionalqa-judge-m2`, and `v4-aircargo-judge` with the
[handover plan](handover-signal.md)'s reading frozen in, as in stage 2.

**Bridges** catch a judge that moved since stage 2. `bridge_plan.py` cut each of stage 2's three
V3 M1 plans to its 15 retested requests, with stage 2's replies, and their copies; the copies are
graded again in V4's window, and the stability rule reads stage 2's verdict against the new one.
Their plans' SHA-256: aircargo `23e6e13eafd9ebb8aea1562c980bf1309988f9a6d850592cd7801b8f3882d1a3`,
WixQA `5697593e39d81ca8cf551b339b1624c0186cca16216ae03c54504fc6e6e107d5`, ConditionalQA
`ed89a6b6a2b939041e7df23ff8b749d9e4908fc91c89864cb4dc85da9179fc93`.

620 requests ≈ 14 h on one stream and ≈ $112 at stage 2's pace (its private journals); a plan
past 3× its forecast pauses. Private folder: `D:/RAG_new_stage2_private/v4/`.

## How it is read — before the first request

- **Pairs:** a question counts when both sides' M1 verdicts are valid; the others are listed.
- **A difference,** V4 minus V3, paired, gets Newcombe's interval (method 10, Wilson limits) and
  the cluster bootstrap over `evaluation/external_parts.py`'s clusters (seed 20261001, 10,000
  resamples, not stratified by base; an aircargo question is its own cluster). It **falls** or
  **rises** — detected — only when both exclude zero on the same side.
- **Primary:** the bad share, WixQA and ConditionalQA pooled (≈ 200 pairs); beside it, the same
  on the pairs whose context V4 read unchanged.

**The decision** is `v4_record.decision`: the first row that holds; harm is read on the bases
whose plans count.

| | Outcome | When |
|---|---|---|
| 1 | not adopted — harm | a base's bad share rises; or its good share falls while its bad share does not; or ConditionalQA's declines among its 20 not answerable fall; or the pooled bad share rises |
| 2 | `NOT_EVIDENCE` | an M1 plan of either side, or a bridge, is not counted; or a base is not run whole |
| 3 | adopted | the pooled bad share falls |
| 4 | kept | the two defects gone: «[N]» in at most one V4 answer of each base, and the referral's paired share falls on WixQA and on ConditionalQA |
| 5 | not adopted | no gain, a defect left |

Adopted or kept: V4 stays, and stage 3 reads its answers. Otherwise `agent/prompts.py` and its
E2E test return to V3 in a commit, stage 3 reads stage 2's answers, a V5 is a new registration,
and Julia is told. The table leans away from V4 on purpose: its eight one-sided harm reads, at
2.5 % each, give a false «not adopted» under no effect at most 20 % of the time.

- **Harm stops early:** after each base's judge, `v4_record.py STAND_DIR OUT --keys <judged>`;
  harm stops the bases not yet run, and a running one before its next batch.
- **Open outcomes:** a base not answered whole after stage 2's reruns leaves `--keys`; a product
  fix for a path break raises a new stand, and every V4 base reruns on it; an M2 plan failing the
  stability rule prints `NOT_EVIDENCE` and decides nothing.
- **Printed, deciding nothing:** the list in `v4_record.py`'s docstring — M2, the moves of class
  and of `context_has_answer`, the referrals routed to a person (the product's own handover text
  names a specialist), the times, the pairing, each plan's CLI, the environment.
- **Detectable:** paired, at least about 2.8·√(d/n), d = (b + c)/n: at 100 pairs 9, 13 and 15
  points for d = 0.1, 0.2 and 0.3; at 200, 6, 9 and 11. Smaller is «not detected», never «no
  effect».
- **Not said:** V4 was written after reading these answers and runs on the same questions — in
  sample; it names no question, aircargo is the least-fitted base, and stage 7's locked parts are
  the real check. One answer a side, the 4B unseeded, one draw of the judge; the judge and V4's
  author are the session's model (D12).

## Records

`reports/answer-prompt-v4/<stand7>/`, each file through `stage2_common.without_text`: the
answers' summaries, the plans' records with the bridges', both sides' marks, the environment and
`v4-record.json`. Rule (c): the record, a test deriving each published number from it, a row in
[`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md). The tools and their test are committed with this
spec, each SHA-256 below checked by the test; a later change is a marked error fix that updates
this list:

- `reports/answer-prompt-v4/tools/answer_marks.py` `115ed6a1252578b903d8cffc6cbc7ae0000de2a927bf5803d5ced393805fe51c`
- `reports/answer-prompt-v4/tools/bridge_plan.py` `41c72f480de3b093a74215d3ea89f00453c838cfaa27857e9c6f6c0d0701d244`
- `reports/answer-prompt-v4/tools/raise_stand.sh` `a88d63b26281a223e647c4c2086c0a529aeef1fc849f14b9f7a22729b42e75aa`
- `reports/answer-prompt-v4/tools/stand_env.py` `ac6401d504c3697e2350567ac8e9178c4e8112f0b71cad33c7ea41329e8b9c67`
- `reports/answer-prompt-v4/tools/v4_record.py` `b518daf26ea36d2ecb753e22029c4ab780a56b39d1e174d01650b4050659bd6d`
- `tests/test_answer_prompt_v4_record.py` `166ea10df25e3b3f4e664dbe66df0324fa775ce584be2fb61da5d6475fa4714b`

## Then

V4 stays: stage 3 reads its answers, and for them this spec overrides the handover plan's 1.1–1.2
(one commit's answers, the adapter of 1.0). V3's aircargo has 14 targets, under that plan's 15,
so stage 3 will likely read the external bases' answers too. Stage 5 compares the final path with
V4's numbers, and with stage 2's on MultiHop-RAG.

## What the cold read corrected

A cold read of the first text (the session's model, D12) found the decision and its tool apart,
the tools free to change after V4's answers, M1 rewarding answers where the gold has none, «kept»
resting on uncounted defects, an unchecked judge drift, «the wider interval» not always the
cautious one, and the context, environment, open outcomes and widget unsaid. The table, the pins,
row 1's guard, row 4, the bridges, «both intervals» and the text above answer them.
