# Web research of 2026-10-25 — our bases against the literature, how to treat our failures, the state of RAG

Literature, not measurement: nothing here changes a published number of this repository, and
no number below is ours unless it says so. Session `5ec44b60`; its
[handoff](../session-handoff-2026-10-25-stage3-signals-running.md) holds the context.

## Why

On 2026-10-25 Julia saw the metrics (aircargo good 63 of 100; WixQA 40; ConditionalQA 35;
MultiHop-RAG 65 on the earlier prompt) and the handover problem (no cheap signal finds the
answers that need a person) and asked (18:41 UTC): «текущие проблемы нужно же как-то лечить… И
по трем базам результат очень низкий… Вероятно стоит запустить 2 рисеча — как лечить текущие
проблемы и какие метрики по RAG актуальны». At 18:48 she added a third, the general state of
RAG in October 2026, «решение о 3-ем рисерче стоит принять перед его запуском»; at 19:06 she
asked for all three in this session, each repeated by Codex («gpt astra 6 xhigh»), one run at a
time.

## How it was made

- **Briefs** (`brief-*.md` here) state our system, our subsets, our numbers and the questions;
  they hold counts only — no question, document or answer of a base, no personal data.
- **Claude:** a `deep-researcher` subagent on the session's model (Claude Opus 5.5), read-only
  web search, the brief as its only input; it wrote the report itself.
- **Codex:** the same brief wrapped by `.tmp/research/build_cx_brief.py` (an output contract
  and citation rules added, nothing else changed), run through the Codex companion on profile
  cw with `gpt-6-astra`, effort `xhigh`, sandbox read-only, in a package folder outside the
  repository that holds only the brief; the report is its final message. Its rollout in
  `~/.codex-work/sessions/` names the model, the effort and the sandbox (thread ids below).
  This is the second-opinion role of `PLAN.md` §8.1: it writes no code and grades nothing.
- Research 3's scope was decided after reading research 1 and 2 (below).

| Run | Brief | Claude's report | Codex's report |
|---|---|---|---|
| 1 — results on our three bases, current metrics | [brief](brief-1-bases-and-metrics.md) | [report](claude-1-bases-and-metrics.md): 24.6k characters, 33 sources, 18:51–19:02 UTC | [report](codex-1-bases-and-metrics.md): 35.3k characters, 33 sources, 19:10–19:28 UTC, thread `01a17478-b668-7293-8418-91c299d212db` |
| 2 — how to treat claims, declines, retrieval, routing | [brief](brief-2-treatment.md) | [report](claude-2-treatment.md): 23.9k characters, 56 sources, 19:10–19:24 UTC | running |
| 3 — the state of RAG, October 2026 | [brief](brief-3-state-of-rag.md) | [report](claude-3-state-of-rag.md): 27.2k characters, 72 sources, 19:30–19:36 UTC | after Codex's run 2 |

## Research 1 — are our numbers low against others?

**Both agree:**

- Nothing published matches our setup, so «низкий» is not shown to be low. WixQA's own paper
  (2505.08643) reports on the Simulated subset a *graded* Factuality (a GPT-4o judge, 1–5 →
  0–1) of 0.63–0.77 with frontier API generators — an average score, not our share of good
  answers. ConditionalQA is published with the document given (FiD EM/F1 44.4/50.8; Mistral-7B
  with oracle passages 55.5/63.8); none with whole-corpus retrieval, none for the not
  answerable questions alone. MultiHop-RAG's official answer scorer counts an answer right if
  it shares any word with the reference, so its high accuracies are lax.
- The same three metrics to add, all from what we already record: **claim-level
  faithfulness** (supported claims / claims, from the judge's per-claim support); **recall of
  the reference's key claims (nuggets)** in the answer and in the context — it separates a
  retrieval miss from a generation miss; **decline quality** — answerable × unanswerable
  against answered × declined (Codex), or a CRAG-style score of +1 right, 0 decline, −1 wrong
  with decline precision and recall (Claude).

**Where they differ:** Claude's report called MultiHop-RAG's Hits@K «the share of evidence in
the top K, our evidence recall», and so our 0.49 lower than the published 0.62–0.64. Codex's
report and research 2 say otherwise, and the official `retrieval_evaluate.py` (read on
2026-10-25) settles it: a query is a Hits@K hit when *any one* gold fact is a substring of a
top-K chunk (spaces and newlines removed, null queries excluded); MAP@10 counts the share, by
a non-standard formula. Our «all evidence 10/70» and mean evidence recall 0.49 are stricter
measures; they are not comparable until recomputed by that rule. Codex alone found that a
later paper recomputed the original voyage-02 MAP@10 as 0.2718 instead of the published 0.4795,
and Multi-Meta-RAG's Hits@4 0.77–0.79 with metadata filtering.

## Research 2 — how to treat it (Claude's; Codex's is running)

Claude's ranking, each with its cost on this Mac and whether it needs Julia's decision:

| # | Option | Aimed at | Cost | Her decision |
|---|---|---|---|---|
| 0 | Recompute MultiHop-RAG's retrieval by the official rule; check each fact in the joined context (an 800-character boundary can cut one) | measurement | no model call | no |
| 1 | An answer flag (answered / partly / declined) and a second «partial answer» pass for declines only (Trust-Align: a prompt alone moved an 8B's answer rate 1.5 % → 99 %) | WixQA's 22 wrong declines | +2–4 min, declines only | no |
| 2 | A claim check in the chat as the router: the 4B's own (81–235 s) or an encoder checker | handover | minutes, or seconds (English only) | a new model: better agreed |
| 3 | Repair by deleting unsupported sentences — only behind a calibrated signal (a 2026 preprint: 64.3 % of the text kept, 83.5 % of clean answers edited) | unsupported claims | one pass | no |
| 4 | Query decomposition plus rerank (Hits@4 0.611 → 0.763 on MultiHop-RAG, with a 32B decomposer) | multi-hop retrieval | +0.5–1 min | no |
| last | Fine-tuning, or an 8B generator | claims, declines | large | yes |

Seconds-fast checkers on a CPU — HHEM-2.1-open (0.1B; RAGTruth-QA balanced accuracy 74.3),
FactCG-DeBERTa-L (82.3), MiniCheck-FT5 (78.0), LettuceDetect-large (F1 79.2) — are **English
only**: the FLAN-T5 tokenizer turns Cyrillic into `<unk>`. For Russian only an XNLI model never
measured on grounding, and the 4B's own check, remain. Token log-probabilities as a routing
signal: AUC ≈ 0.51 on RAGTruth; semantic entropy needs ~10 generations — out of reach.

## Research 3 — the frame (Claude's; Codex's follows)

**The scope, decided ≈19:28 UTC:** research 1 had covered the metrics and research 2 the
methods, so research 3 asked what they did not: the levels reached on the reference RAG
benchmarks by system size, the method families behind the best results and which transfer to
a 4B on a CPU, and how production support assistants measure quality and the handover to a
person — the last one nobody had covered, and it is her handover question.

- **Levels:** CRAG's best industrial system truthfulness 51 %, a plain RAG on Llama-3-8B
  accuracy 32.1 %; FRAMES 0.66 with multi-step retrieval on Gemini-Pro-1.5; BRIGHT nDCG@10
  leader 66.9, a ~4B model 52.4, BM25 14.5; TREC RAG 2025 best vital nugget score 0.55.
  Russian RAG with the context given, on a CPU (2606.30062, 06.2026): Qwen3-4B-Instruct-2507
  correctness 0.71 and faithfulness 0.80 against GPT-5-mini's 0.73 and 0.89.
- **Transfers to a 4B on 4 cores:** cheap grounding detectors, context pruning or
  compression, late interaction; partly one LLM query rewrite or one extra retrieval step
  (prompted agents on a 3B do worse than plain RAG: EM 0.181–0.255 against 0.270). Not:
  graph RAG, 32B reasoning rerankers, long context instead of retrieval, RL training.
- **Support in production (vendor claims):** Intercom's resolution without a person 51–56 %
  (2024–2025) to 76 % (2026), counting a customer who just left; Zendesk's «verified»
  resolution checked by an LLM over the transcript (since 2026-05-18); no company publishes
  the precision and recall of its escalations on live traffic.
- **Computable from our records without people:** the CRAG-style truthfulness, the share of
  answers routed to a person with its precision and recall against the judge's labels, the
  share passing a grounding check, a risk–coverage curve.

**Where it disagrees with our data:** it reads the gap between 0.71 (context given) and our
0.35–0.63 as a retrieval loss, and calls faithfulness not the small models' main weakness.
Our judge found the context held the answer in 94–100 % of the bad answers (aircargo 17 of
17, WixQA 48 of 51, ConditionalQA 54 of 57) and an unsupported claim in most of them (14 of
17, 32 of 51, 50 of 57; [research 2's brief](brief-2-treatment.md), counted from
`reports/answer-prompt-v4/4f48fed/*-judge.cases.jsonl`) — research
3's brief did not carry that fact. Its own table shows the faithfulness gap (0.80 against
0.89) larger than the correctness gap. Its first recommended family, a cheap grounding
detector, meets research 2's finding that those detectors read no Russian.

## What it means — a proposal for Julia's decision, not a plan

Ordered by what it costs and what it unblocks; every item is universal (no dictionaries, any
corpus and language) unless marked.

1. **Measure before treating, no model calls:** MultiHop-RAG's retrieval by the official rule;
   the decline matrix and the CRAG-style score from the current classes; claim-level
   faithfulness from the recorded claim support. Nugget recall needs ~2 judge calls an answer
   (about 400 for the four bases) — a judge budget, her call.
2. **Wrong declines:** the answer flag and a second pass for declines only — the cheapest
   generation fix with a measured effect elsewhere; measured on WixQA's open part.
3. **The router:** waits for stage 3's outcome on the Mac. If the 4B's claim check is worth
   wiring (outcome B), how to wire minutes is hers; if not (C), an English checker covers the
   English bases only, and Russian has no proven fast checker.
4. **Retrieval:** after item 1 shows the real gap — one query rewrite or decomposition; BGE-M3's
   multi-vector mode would need a vector store that holds it (a stop-list item: hers).
5. **Not worth our hardware:** graph RAG, long context, RL training, large reasoning rerankers,
   semantic entropy.

The Codex reports of runs 2 and 3, once in, are compared here the same way.
