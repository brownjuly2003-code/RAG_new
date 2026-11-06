# Bundle 0: reranker scores in place of the document grader — offline preparation

Status 2026-11-06: **registered before the run**. No private replay or model call is part
of this registration. The tool and synthetic tests belong to the registering commit.
The four inputs below are committed; the session rehashed all four in the repository on
2026-11-06 and each equals its listed digest. A missing or different input stops the tool.
This registration reports no experimental result.

## Why

[Research 8](../operations/research-2026-11-06/report-8-laptop-small-model.md), §3
«Негенеративные замены» and §4, row 0, asks whether existing bge-reranker-v2-m3 INT8 ONNX
scores can replace role 2: `agent/graph.py:make_grade_docs_node` and
`agent/prompts.py:build_doc_grade_batch_prompt` (`DOC_GRADE_BATCH_PROMPT_V1`).
The batch asks whether each document contains useful information, including partial relevance.
Its accepted documents keep their original order; Codex's malformed batch fails closed.

This is an offline count and preparation. It becomes a slice only when a rule replaces
the call in the product (rule (a)) or a number is re-measured (rule (c)). No product edit,
new search, rescoring, LLM call, answer or judge is authorized by this recipe.

## Inputs, frozen

SHA-256, repository-relative paths:

- `reports/stage7/tools/arms_replay.py` `6ca8b723841d08dfd6f5d084bdc0883264c889eb495dc4d3728ac0a2ea623689`
- `reports/stage7/5e308fe/record.json` `b9db1434a6091536540112591e29cb3f02f373660dd06469e6abebc3780b55e4`
- `reports/stage7/5e308fe/int8_scores.jsonl` `5c4d2bbcc42fe17afb516c877fdeacf7bc3bd05beb8557870b7d1f7bedb156a6`
- `reports/stage7/5e308fe/rows.jsonl` `2d87859ecfd5e2442eefadcc5dafb471e5a80d13d8227907d59e568010109627`

All four were hashed in the repository. The JSONL digests are also published in
[`stage7-step1-arms-record.md`](../evidence/stage7-step1-arms-record.md), Records; the journal's
digest and full header also live in `record.json`. This tool imports the unchanged
`arms_replay`; it does not copy or modify its selection, prompt fitting or gold calculation.

The journal holds fresh INT8 scores of every candidate in each K-14 pool, 415 questions.
Its original header, including HEAD, environment and per-run provenance, is checked against
the frozen record. The replay has a new HEAD: it does not regenerate the old header with
the new HEAD/spec. Private inputs' provenance and serialized-record digests must equal
the old header. The journal's question order, pool, scores and five are checked by
`arms_replay.score_rows` and `new_h`; duplicate, missing or extra question ids are refused.

Archives, index receipts, stage-2 runs, export manifest and V4 records retain every frozen
hash and path in [stage 7's spec](stage7-step1-arms-m3.md), Inputs and Amendment 1.
`run_inputs` and `export_manifest` enforce those contracts. Only the Mac session reads them.
The same service interpreter/environment and K 14, five, window 3,584/input limit 2,176 apply.

## The arms

**Score scale.** `vectordb/onnx_reranker.py:OnnxCrossEncoder.predict` returns
`1 / (1 + exp(-logits[:, 0]))`, float32: sigmoid scores in [0, 1], not raw logits.
These are ranking scores, not calibrated probabilities of document relevance. The range
defines the grid before reading any score distribution; no corpus-specific fitting.

- **H:** H_new's five, rebuilt from the journal through the product's hybrid retriever,
  including its parent expansion, then V4's window fit exactly as in stage 7.
- **T(t):** keep every H document with score **>= t**, in H's order. The grid is
  `{i/20: i = 0,...,20}`: 0.00, 0.05, ..., 0.95, 1.00, named T00 through T20.
  Equality keeps a document, including at 0 and 1. No forced first document.
- **A:** sort the five scores descending, stably. For n >= 2 let
  `g_i = s_i - s_(i+1)`, i = 1,...,n-1. If the maximum gap is positive, keep the first
  `max {i: g_i = max(g)}` sorted documents, returning them in H's original order.
  Thus a tied maximum gap keeps the longest prefix; an all-equal vector keeps all.
  Empty/singleton vectors stay empty/singleton. Comparisons use the stored floats without
  tolerance or fitted parameter. Equal scores are never split by a positive gap.
  Research 8 [S30], [Tail-Aware Adaptive-k](https://arxiv.org/abs/2606.11907), motivates
  testing score-distribution shape without training. A is our precisely specified maximum-gap
  baseline, not an implementation of that paper and not an adoption of its reported gains.
- **G:** the actual captured batch grader's keep set, comparison only; details below.

T, A and G filter the already expanded H documents. They do not re-expand seeds after a
drop. Each retained list is fitted anew through `arms_replay.Builder` at 2,176 input tokens;
the same `arm_entry`, `points` and `sent_point` calculate both points. A zero-document
selection remains a row and a gold miss when gold is present; in the product it would route
to a person. Record both zero kept and zero actually sent (window fitting can differ).

## Recorded grader source — found in code

Stage 2's `reports/stage2/tools/live_retrieval.py` explicitly runs retrieval alone, without
generation or grading; its saved schema has lanes/pool/ranked/expanded/sent/prompt/path,
not per-document grader verdicts. `live_api.py:observe_generate` records timings and output
length, not the raw response. Those records cannot supply G.

Codex-only capture **does** preserve it: the shim
`reports/codex-only-quality/tools/shim/CaptureShim.cs` writes `calls/<id>/stdin.bin`,
`stdout.bin`, `start.json`, `end.json`. `capture_journal.py:read_call`, `unwrap` and
`parse_stdout` expose the prompt, response text, integrity checks and active case;
`quality_driver.py:inspect` records the corresponding capture hashes. This is the source
for G, not the output of the separate context/answer quality judge.

If available, the session places the unchanged capture under `PRIVATE/capture/calls/`.
The reader uses `capture_journal` read-only and checks active-case binding and capture
integrity. A comparable call must have the same base and case id and a byte-equal stripped
batch prompt built from the question and H's complete expanded documents in order.
Only one complete, accepted call may match. Another five, trimmed views, another template,
multiple matching attempts or an incomplete call are explicitly unavailable comparisons;
never transfer verdicts by document index from another five. Parse the matched response
with the product's `_parse_doc_grade_batch_text`; malformed accepted output keeps none,
as Codex's batch path does. No new grader calls, fallback or manual decisions.

G is always present in the output schema: absent capture/match is null, never an empty
keep set. Publish matched/unmatched/ambiguous/incomplete counts and the capture digest.
Full-cohort G readings with missing gold pairs are `NOT_EVIDENCE`; available-case G pairs
stand separately, with their denominators, per base and pooled deciding. They are a
possibly selected subset and enter no threshold selection. Source existence does not
assert that this session has a matching capture for any of the 415 questions.

## The parity gate

For every question, H's complete `arm_entry` must equal the frozen stage-7 row's H:
both points and all metrics, document/chunk counts, excerpt misses, cut, prompt hash,
character/token counts and unresolved flags. Also compare label, base, case id, index and
gold flag. `new_h` separately enforces the scored pool and recorded five. No aggregate
parity shortcut. One break exits 3 and writes no record/rows; no readings are published
before all 415 pass. This gate targets H_new, not stage 7's older H_old parity experiment.

## Readings and selection, frozen

For H against every arm, per WixQA, ConditionalQA, MultiHop-RAG, aircargo, and pooled on
WixQA + ConditionalQA: gold at **sent**, expanded beside. WixQA uses `gold_article`,
ConditionalQA and MultiHop-RAG `all_evidence_coverage`; stage 7's secondary metric is
also printed per base. A hit is the primary metric equal to 1. Exact two-sided McNemar:
b = H-only hit, c = arm-only hit;
`p = min(1, 2 * sum(comb(b+c,j), j=0..min(b,c)) / 2**(b+c))`, p = 1 if b+c = 0.
Use `arms_replay.pair`/its exact McNemar helper; retain unrounded p for selection.
Loss means b > c and p < .05, gain c > b and p < .05, otherwise no detected difference.

Gold-free questions stay in usage/zero denominators. aircargo's two labels are pooled:
no context gold exists in these inputs, so its gold comparison is `NOT_EVIDENCE`, with
usage beside; no new judge and no borrowing old H_old verdicts for changed prompts.
Report total, gold, unread, missing and paired n explicitly. Any unresolved T/A point or
unmatched excerpt stops the run, rather than silently dropping a question. Missing G
is counted separately. H and each arm report mean/median documents kept, documents
sent and estimated tokens of sent document text (not full prompt tokens), and zero counts.

**Registered choice:** t* is the largest grid value with **no detected loss at sent on
each of WixQA and ConditionalQA (exact two-sided McNemar p < .05 and b_h_only > c_arm_only
defines a detected loss)**, no unread/missing cases there, and at most 5% zero-kept
questions on **each** base (denominator: all that base's questions, including no gold).
No pooling can rescue a failing base. The session's review on 2026-11-06, before the run
and before any result exists, set this loss-only rule because the product asks whether
a rule loses gold; a detected gain is not a reason to reject it. If none qualifies, t* is
null. A is assessed by exactly the same conditions; no ranking of A against t* is implied.
`external_stops`/`qualifies` are not reused: stage 7's gain/MDE gate answers another question.

t* is chosen **in-sample on these questions** across 21 thresholds. This is an optimistic,
multiple-comparison reading, not a held-out test, equivalence test or proof of no loss.
p >= .05 does not establish equal gold retention. A later product run re-measures the
chosen rule, including empty-context routing. No forecast numbers are registered.

## Running it on the Mac

Commit this registration and sync a clean checkout first. The stage-7 JSONL artifacts
are committed at their registered paths; the tool checks their digests above and
requires `git status --porcelain` empty. Do not run stage 7 score again.
Use the service's Python 3.11.15, with the stage-7 offline stack (transformers 4.44.2,
ORT 1.23.2, cached tokenizer snapshot `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`).
The environment, including interpreter/module paths and versions, must match the
frozen header. The export's hash is checked, but no model/session is loaded for scoring.

```sh
cd /Users/julia/RAG_new_mf_gate
env -i HOME="$HOME" PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  LANG=en_US.UTF-8 PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ANONYMIZED_TELEMETRY=False \
  PYTHONPATH=/Users/julia/RAG_new_mf_gate:/Users/julia/RAG_new_mf_gate_site \
  RAG_RERANKER_ONNX=/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx \
  /Users/julia/RAG_Support_Assistant/.venv/bin/python -u \
  -m reports.bundle0.tools.threshold_replay \
  --out /Users/julia/RAG_new_bundle0/out \
  --private /Users/julia/RAG_new_bundle0/private
```

Default `--runs`: `/Users/julia/RAG_new_chat_5e308fe/chatlive/runs`;
`--data-root`: `/Users/julia/RAG_new_external_s1`;
`--v4-runs`: `/Users/julia/RAG_new_chat_4f48fed/chatlive/runs`.
No `RAG_RERANK_BATCH` or experiment override. PRIVATE is read-only; absent capture is
allowed and reported. OUT must not already contain record.json or rows.jsonl.

## Stops and records

Missing/changed frozen inputs, dirty checkout, wrong service environment or control,
wrong private provenance, incomplete journal, duplicate/missing ids, nonfinite/out-of-range
scores, pool/five drift, changed H, unresolved gold/excerpts, invalid capture integrity,
text-bearing output or an existing output: refuse. The imported 30-minute replay budget
stops at a question boundary and before writing; inspect the cause before another attempt.
No failed run publishes partial readings or overwrites prior evidence.

OUT/record.json and OUT/rows.jsonl go to `reports/bundle0/<short sha>/`, where short sha
names the registering checkout; record.json names its full measured HEAD (and overlay,
if used), input/tool/test/spec/measuring-code hashes, capture digest, frozen constants,
parity counts, all readings and the in-sample choice. A row contains ids, numeric seed
positions/scores/kept indices, flags, hashes, counts and gold points. No private text.
Both complete outputs pass `stage2_common.without_text` with all source names/questions
and a recursive forbidden-text-field guard before either is written, UTF-8 without BOM, LF.
PRIVATE, raw capture, questions, document names/text and filled prompts are never copied.

SHA list of the tool and synthetic test, computed after edits:

- `reports/bundle0/tools/threshold_replay.py` `8a1d31439421808c041f6872d2b19afcdc17a2f92a9234ab8b37575a5d5b374a`
- `tests/test_bundle0_threshold_replay.py` `992ef18ee559b1d2e3d837332bbdc53b9fb427666f62b6bbb93eab335fe1dccc`

## What it does not say

This does not prove a rule replaces role 2 in the running graph, preserves answer quality,
or is safe on another corpus. H is the stage-7 hybrid control, not a freshly measured
graph lane. Recorded lane prefixes need not equal a new approximate-index search.
It measures gold availability after the answer window, not grader agreement alone;
the optional G comparison is conditional on exact recorded input matches. Latency,
memory, power and saved model-call time are not measured here.
