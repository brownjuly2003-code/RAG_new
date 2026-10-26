# The answer prompt V5: evidence first, against V4's answers on V4's contexts

Status 2026-10-26: **registered before V5's first request**, with the tools that read it and
their test ([Records](#records)). [`PLAN.md`](../../PLAN.md)'s stage 3b, on Julia's «да» of
2026-10-26 to §8.3 item 12; its step 1 asks for this spec: the decision table, the forecasts,
the stops and the reading tools, as stage 2b's.

## Why

| Per 100 answers, V4 ([record](../evidence/answer-prompt-v4-record.md)) | aircargo | WixQA | ConditionalQA |
|---|---|---|---|
| M1 bad | 17 | 51 | 57 |
| bad, with a claim the documents do not support | 14 | 32 | 50 |
| declined although the documents hold the answer, at least in part | 0 | 22 | 6 |

Row 2 is the [coverage record](../evidence/coverage-metrics-record.md)'s. The claim no document
supports is V4's main loss. V5 asks the model for its evidence first: for each part of the
question, the passage of the documents that answers it, word for word; then an answer that
says only what the passages say; then a status line, answered fully, in part or not at all.
The model and the path stay; only the prompt changes. The source is ReClaim without training
(research 2): the share of correctly attributed sentences 54.7 → 77.7 and completeness
55.2 → 50.7 on Llama3-8B in English, so completeness is guarded here by M2.

## What changes

[`qa_prompt_v5.txt`](../../reports/answer-prompt-v5/tools/qa_prompt_v5.txt), the registered
text: (1) **Evidence** — for each part of the question the context answers, the shortest
passage, copied word for word in quotation marks, with its number; (2) **Answer** — only what
the quoted passages say, the conditions they give instead of a bare yes or no, each part the
context does not answer named, no facts, conditions or advice beyond them; (3) **Status** — one
line. Nothing in the context answers: nothing quoted, the decline and the status line. The frame
the chat writes and the judge reads stays: `CONTEXT:`, `QUESTION:`, «When you rely on», the
document labels; its citation sentence holds «[1] for the context's first document,», the
marker by which `scripts/chat_answer_judge.py` tells a V5 prompt (`QA_PROMPT_V5`). No word of a
domain or a language is added.

**The product does not change while V5 is measured.** The text sits in the tools folder; the
stand's and the repository's `agent/prompts.py` keep `QA_PROMPT_V4`. On adoption V5 becomes
`agent/prompts.py`'s "qa", byte for byte, `prompt_id` `QA_PROMPT_V5`, in a commit with
`tests/test_chat_answer_prompt_e2e.py` moved to it (rule (a)). The follow-up turns keep
`CONVERSATIONAL_QA_PROMPT_V4`; the widget's `/api/ask` builds from the same "qa" and changes
unmeasured, as with V4.

**The context moves with the template:** +178 characters against V4's, +49 estimated tokens
against the input limit of 2,636. The chat's `fit_context_docs` keeps whole documents
while they fit and excerpts the next, so a V5 prompt holds V4's documents, or fewer, or its last
one cut shorter, never more. `replay.py check` counts the pairs whose context V5 reads unchanged
before any answer; the record reads the primary on them beside the whole. Read on the stand on
2026-10-26, before V5's first request: V4's 300 prompts rebuilt byte for byte, and V5 reads the
context unchanged on 81 of WixQA's 100, 83 of ConditionalQA's and 36 of aircargo's — aircargo's
documents fill the window: 59 of its V5 prompts hold the last document cut shorter, 5 one
document fewer (WixQA 18 and 1, ConditionalQA 17 and 0).

## The replay

- **Stand:** V4's, `/Users/julia/RAG_new_chat_4f48fed` at
  `4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1`, its V4 runs `chatlive/runs/v4-<key>-bNN`; the
  tools copied into its `v5/`. Model `qwen3:4b-instruct-2507-q4_K_M`, digest `0edcdef34593…`,
  on the CPU.
- **No retrieval.** Each V4 answer's saved stream prompt is cut at the chat's labels into its
  question and documents; the chat's own `_fit_stream_prompt` (no history) must rebuild V4's
  prompt from them byte for byte, as the provider flattens it, or the key is refused before any
  model call (exit 3). The prompts are read as bytes: a carriage return, which the judge reads as
  a line feed, refuses the key (none of V4's 300 prompts holds one). The same fitting with V5 as
  the registry's "qa" text gives V5's prompt; a staged or experiment override standing before
  the registry stops the replay.
- **The call is the chat's:** the provider runtime's strong model, `generate_stream` with the
  "generate" role's kwargs (temperature 0.2, at most 1,024 tokens), the stream loop and its
  3,600-s deadline. Eight settings must equal V4's first run of the key
  (`effective_settings.json`), and the runtime's model must be the Ollama provider of the model
  above inside the runtime's wrapper, with no fallback, or the key is refused (exit 6). No
  self-evaluation, route or follow-up turn is replayed.
- **Environment:** V4's `stand_env.py` writes a line to `v5/v5-environment.jsonl` before the
  first key and after each. The record refuses lines that do not bracket V5's answers, or that
  show other than stage 2's one server of Ollama 0.33.2, running since 2026-09-13, and its
  interpreter: `pip freeze` SHA-256
  `ed8fe1c2142b1a9ff7f1c80db891a0887860ba939131bf5cd3cbde324b161ada`, the newest package older
  than stage 2's first answer. Read on 2026-10-26 at 14:03 UTC, it is stage 2's.
- **Order:** `v5_chain.sh`, unattended: WixQA, ConditionalQA, aircargo, V4's ten batches of each,
  runs `v5-<key>-bNN` in V4's layout, so the judge's adapter reads them as it read V4's. Before
  each key the Mac is idle as V4's chain read it (the 5-minute load below 2; no pytest,
  llama-server, supervisor or replay; Ollama holding no model), waited for up to 6 h.
- **Forecast and stops:** V4's stream took a median 85, 77 and 86 s; V5 writes its evidence too,
  +25–45 s by the plan's estimate: ≈ 110–130 s an answer, ≈ 3.5 h a key, ≈ 10.5 h in all.
  Aircargo, the harm guard on the product's corpus, is ≈ 3.5 h of it. An answer past 1,200 s
  stops its key (exit 4); a key past 3× its forecast, ≈ 11 h, is stopped by the session through
  its stop file; a model error stops the key (exit 7), and the chain run again resumes it at the
  question it stopped on. A prompt a killed process left without its case is removed on resuming.
  Both are counted in the batch's `launch.json` (`model_errors`, `orphan_prompts`) and printed:
  V4's 300 streams ended without an error, so a V5 question asked again after one had a second
  chance V4 did not need. A key not answered whole leaves `--keys`.

## The judge

V4's request: `scripts/chat_answer_judge.py`, salt `chat-answer-judge-2026-10-18`, instructions
SHA-256 `fd015e742c835a17b17704ad629df90a34a61ac600762e8c74e52aababdcc9c2`, `claude-opus-5-5` at
effort `max` by stage 2's route, 15 retests a plan,
[the stability rule](stage2-four-corpora.md#the-judge). Five plans, each frozen after its key's
tenth batch and its SHA-256 committed before its first grade: `v5-wixqa-judge-m1` and
`v5-conditionalqa-judge-m1` (references withheld), `v5-wixqa-judge-m2`,
`v5-conditionalqa-judge-m2`, and `v5-aircargo-judge` with the handover plan's reading frozen in,
as V4's (`judge_export.py` requires it).

**Bridges** catch a judge that moved since V4's. `bridge_plan.py` cut each of V4's three M1
plans to its 15 retested requests, with V4's replies, and their copies; the copies are graded
again in V5's window, and the stability rule reads V4's verdict against the new one. Their plans'
SHA-256: WixQA `db88932ee23275e4194081ec831992f93816074f2c5b2299803e6b26bf4de37a`,
ConditionalQA `582de3638d6b0e3652e80df9a44741c6d385242cce21c0c03cba56a4bc3da421`, aircargo
`f4e646b9904b2c6d419dab423155efa0bea52ae2105c416f9d1054c557e366cf`.

5 × 115 + 3 × 15 = 620 requests. V4's 620 took ≈ 8 h and $116.15: ≈ 8–10 h and ≈ $116–130. The
plan's ≈ 460 counted the four plans of the external bases; aircargo's guard (115) and the bridges
(45) are added, as stage 2b had them. A plan past 3× its forecast pauses. Private folder:
`D:/RAG_new_stage2_private/v5/`.

**The judge's instructions predate V5.** Their defect «copied_context» (an answer that mostly
copies the documents instead of answering) can catch an answer whose quoted evidence outweighs
its answer, and such an answer counts as bad: the measure leans against V5 there, on purpose
unchanged. The record prints the defects by kind and the answers that quote their context.

## How it is read — before the first request

- **Pairs:** a question counts when both sides' M1 verdicts are valid; the others are listed.
- **A difference,** V5 minus V4, paired, gets Newcombe's interval (method 10, Wilson limits) and
  the cluster bootstrap over `evaluation/external_parts.py`'s clusters (seed 20261001, 10,000
  resamples, not stratified by base; an aircargo question is its own cluster), as V4's record
  read them. It **falls** or **rises** — detected — only when both exclude zero on the same side.
- **Primary:** the bad share, WixQA and ConditionalQA pooled (≈ 200 pairs); beside it, the same
  on the pairs whose context V5 read unchanged.

**The decision** is `v5_record.decision`: the first row that holds. A key's harm is read when its
M1 plans and its bridge count; M2's when both bases' M2 plans count on both sides.

| | Outcome | When |
|---|---|---|
| 1 | not adopted — harm | a key's bad share rises; or its good share falls while its bad share does not; or ConditionalQA's declines among its 20 not answerable fall; or the pooled bad share rises; or M2's pooled `agrees` among the questions with a reference (WixQA's 100, ConditionalQA's 80) falls |
| 2 | `NOT_EVIDENCE` | an M1 plan of either side, an M2 plan or a bridge is not counted; or a key is not answered whole |
| 3 | adopted | the pooled bad share falls |
| 4 | not adopted | no gain |

Adopted: V5 replaces V4 as [What changes](#what-changes) says, and stages 4–5 measure the final
path with it. Otherwise V4 stays, and Julia is told. The table leans away from V5 on purpose:
its nine one-sided harm reads, at 2.5 % each, give a false «not adopted» under no effect at most
22.5 % of the time.

- **Harm stops early:** after each key's judge, `v5_record.py STAND_DIR OUT --keys <judged>`;
  harm stops the keys not yet replayed or judged.
- **Printed, deciding nothing:** the list in `v5_record.py`'s docstring — the moves of class and
  of `context_has_answer`, the wrong declines, the supported claims, the defects by kind, the
  quoting answers, the ones the deadline cut and the ones at the 1,024-token cap (a stream chunk
  is a token; the judge sees a capped answer as `cut_off`), the stream's seconds and chunks, M2's
  right declines, each plan's CLI, the environment.
- **Detectable:** paired, at least about 2.8·√(d/n), d = (b + c)/n: at 200 pairs 6, 9 and 11
  points for d = 0.1, 0.2 and 0.3; at 100, 9, 13 and 15. Smaller is «not detected», never «no
  effect».
- **Not said:** V5 was written after reading V4's answers and runs on the same questions — in
  sample; it names no question. It answers on V4's contexts: the record compares two prompts, not
  two paths. One answer a side, the 4B unseeded, one draw of the judge; the judge and V5's author
  are the session's model (D12). The routes, the self-evaluation and the widget's answers under
  V5 are unmeasured until stage 4's final path, and so is how a user reads an answer in three
  parts.

## Records

`reports/answer-prompt-v5/4f48fed/`, ids, flags and numbers, never a question's, a document's,
an answer's or a judge's text: V5's summaries (`replay.py summary`) and parity rows
`v5-<key>.check.jsonl` (`replay.py check`, as the chain writes them), the plans' records with
the bridges' (`judge_export.py export`), the environment and `v5-record.json`. The record
refuses a plan whose prompt hashes are not the replay's — V4's plans against the parity rows,
V5's against the summary's — a plan or bridge of V5's window not read by the judge below or not
exported by V4's `judge_export.py`, and an environment of another Ollama server than stage 2's. Rule (c): the record, a test deriving each published number from it, a row in
[`EVIDENCE_INDEX.md`](../../EVIDENCE_INDEX.md). The tools and their test are committed with this
spec, each SHA-256 below checked by the test; a later change is a marked error fix that updates
this list:

- `reports/answer-prompt-v4/tools/stand_env.py` `ac6401d504c3697e2350567ac8e9178c4e8112f0b71cad33c7ea41329e8b9c67`
- `reports/answer-prompt-v5/tools/qa_prompt_v5.txt` `835b0f2cf1ac7bc86ad30605367d81457b02e7436a5a5071642a5b881471c276`
- `reports/answer-prompt-v5/tools/replay.py` `ca954c59710e93925cc923f5b2a7f175ce86f7e1fa7b96a46d3b3bbeec4d6eed`
- `reports/answer-prompt-v5/tools/v5_chain.sh` `52b9f5f77881db021e802942ed0608c87438a3b32fe259406f3ad23991c03f1b`
- `reports/answer-prompt-v5/tools/v5_record.py` `1e77dd35f011d274a165e7fda606d54fafbfd27a45c66154e791a645a23f7620`
- `scripts/chat_answer_judge.py` `cdb2be82d3341afe0b1aba4e560f56eac4e2dec9cce69d0e038a18da4f2c7788` — the judge with V5's marker
- `tests/test_answer_prompt_v5.py` `dd1801a6fbecf53598df3e3a2182f9c1cec57497596322673ea93214c9da1f19`

## What the cold read corrected

A cold read of the package (the session's model, D12) found the replay refused on its first key
— the runtime's model is a wrapper around the Ollama provider — the parity rows written under
another name than the record reads, no tie between the prompts the judges grade and the ones
replayed, a prompt left without its case by a killed process, carriage returns unread, the
judge's code and the Ollama server's start unpinned, and the token cap unprinted. The text above
and the tools' test answer each.

## Then

Adopted: the product commit above, then stage 4 on V5's path. Not adopted: stage 4 goes on with
V4, and the record says which row decided.
