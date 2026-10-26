# The seven research runs of 2026-10-25, analysed — what they change in `PLAN.md`

Session of 2026-10-26 (UTC), at Julia's words of 2026-10-25 22:22 UTC («Напиши для след сессии
детальный анализ рисерчев и внесение изменений в общий план») and ≈23:05 («первый пункт для
след сессии — поменять план разработки?»). Inputs: the [research folder](README.md) — its seven
runs, the comparison and the twenty-two checked claims; the
[session handoff](../session-handoff-2026-10-25-stage3-signals-running.md); `PLAN.md` §5, §8, §9.
Written while stage 3's signal run measured on the Mac (82 of 100 answers at 02:05 UTC) and
before its record: nothing here reads a signal of that run.

**What counts as evidence here.** Each item says which of three it rests on: a **checked
claim** (a primary source opened and read, in the folder's table or in [§3](#3-what-stays-open)
below), a **report's word** (a claim in a report, not checked), or **mine** (an estimate or a
count of this session). Literature never changes a published number of this repository; only
our own records do.

## In short

1. **The literature confirms the plan's order and adds no reason to swap a model now.** No
   generator, reranker, embedder or checker is shown to beat ours on this Mac with Russian
   kept; every candidate needs our own offline test first.
2. **Our own records answer three questions the reports could not** (no model call; [below](#what-our-own-records-add)):
   - The reranker loses gold documents the pool already holds. WixQA: the gold article is
     among the candidates for 84 of 100 questions and in the five kept for 68. MultiHop-RAG:
     all the evidence is in the pool for 22 of 70, in the five kept for 7. So «no reranker»
     and «another reranker» are quality questions, not only speed ones.
   - The chat's fixed start before the documents is about 140 tokens. «Keep the instructions
     cached» can save at most about 4 s an answer, not tens.
   - The Mac's memory is dual-channel DDR4-2400. Generation at 4.3–4.7 tokens/s is about half
     of what that bandwidth allows, so memory pressure stays the suspect, not the hardware.
3. **A new hypothesis for the memory growth** (mine, not measured): llama-server's host prompt
   cache keeps every prompt's KV state, about 144 KiB a token, ≈ 320 MiB for a 2,270-token
   prompt. The plan has carried «+312 MB a request, only an unload frees it» since 2026-10-16;
   the cache is allowed 8 GiB on an 8-GB Mac. A cap on it is the cheapest memory lever, and
   stage 4's step 0 can confirm or refute it in minutes.
4. **Applied now** (her words cover them): stage 4 gets a step 0 of diagnostics and research 6's
   levers, each with its own timing; INT8 of the same reranker becomes a stage-4 experiment; the
   plan's no-call recomputations go beside the run; stage 3 says what follows outcome B and
   outcome C.
5. **Proposed, for her word:** an evidence-first answer prompt measured as a stage 3б before
   stage 4; under C or a slow B, an offline test of three Russian-reading encoder checkers;
   the judge budget for comparable metrics; a generator pilot after stage 4; a reranker swap
   test; query decomposition in stage 7.

## What our own records add

Counted in this session from committed files and two read-only looks at the Mac; no model call.

**Gold at each retrieval stage** (`reports/stage2/retrieval-20261021/p2-*.cases.jsonl`, code
`5e308fe`, the same retrieval as V4's answers; the metric: WixQA gold article, ConditionalQA and
MultiHop-RAG all evidence):

| Base | Questions with gold | Vector top 20 | BM25 top 20 | Pool (fused) | Five kept by the reranker | After expansion | Sent to the model |
|---|---|---|---|---|---|---|---|
| WixQA | 100 | 83 | 53 | 84 | 68 | 68 | 68 |
| ConditionalQA | 80 | 56 | 37 | 60 | 46 | 60 | 60 |
| MultiHop-RAG | 70 | 8 | 12 | 22 | 7 | 13 | 10 |

- The pool is wider than 20: the two lanes merge to about 33 candidates (33 on the first WixQA
  question), and the reranker scores all of them.
- On WixQA, 16 questions have the gold article in the pool and lose it at the rerank; 16 never
  reach the pool. On ConditionalQA the rerank drops 14, and the expansion to neighbouring chunks
  brings all of them back. On MultiHop-RAG the rerank keeps 7 of 22.
- The stage-2 K curve (the five kept when the reranker sees the first K of each lane) on WixQA:
  0.60 at K = 5, 0.65 at 10, 0.68 at 20. Fewer candidates lose a little; it is stage 4's
  step 3 data.
- What these files cannot say: whether the fused order's first five, without the reranker,
  keep more or fewer. The per-question files on the Mac hold the lanes and the fused order;
  that point is a light script there, no model ([the short list](#4-a-ranked-short-list),
  «after the run»).

**The chat's prompt** (`agent/prompts.py`, `QA_PROMPT_V4`). The fixed text before
`{context_block}` is about 640 characters — about 140 tokens; the citation and language
instructions come after the question, so no later request can reuse them. The self-evaluation
prompt (`SELF_EVAL_PROMPT_V3`) starts with its own instructions and the question, then the same
documents: it shares no prefix with the answer, so its ≈ 2,300 tokens are read again.

**The Mac** (`system_profiler SPMemoryDataType`, 02:08 UTC): two 4-GB DDR4-2400 SO-DIMMs in two
banks — dual channel, ≈ 38 GB/s in theory; macOS 13.7.8. By weight reads alone a 2.5-GB Q4_K_M
model could generate up to ≈ 15 tokens/s; research 6's one i5-7500 number (a 3.4-GB model at
7.06 tokens/s, not checked) puts ours near 9–10. We see 4.35–4.74.

**The host prompt cache** (mine, arithmetic; the log's lines read 2026-10-25 22:20 UTC).
Qwen3-4B has 36 layers, 8 KV heads and head dimension 128 (research 6, from the model's config),
so an f16 KV state is 2 × 36 × 8 × 128 × 2 bytes = 144 KiB a token: ≈ 320 MiB for the chat's
2,270-token answer prompt. The signal run's log showed the cache at 9 prompts, 1,826 → 2,098
MiB, limit 8,192 MiB — ≈ 230 MiB a prompt. Both are of the order of the plan's «+312 MB a
request» (§3, record `reports/chat-live-4b/19beeb1/`), which only an unload frees — and an
unload ends the process that holds the cache. Not measured: whether the chat's requests each
add a state, and how the cache evicts.

## 1. Every item

Costs: Mac hours on the idle Mac; judge requests at stage 2b's measured rates — $116.15 for 620
requests (≈ $0.19 each) and 287 requests to 0.89 of a five-hour window (≈ 320 a window, the
usage probe of 2026-10-25). «Universal» means any corpus and language, no dictionaries.

### Item 1 — measure by the published rules, no model call

- **What:** MultiHop-RAG's Hits@K and MAP@10 by the official `retrieval_evaluate.py`; from
  M1/M2, the decline matrix (answerable / not × answered / declined) and the CRAG-style score
  (+1 right, 0 decline, −1 wrong); Codex's three numbers — coverage, quality among the answered,
  the share of answers given out with an unsupported claim.
- **Evidence:** checked — the official script counts a hit when any one gold fact is a
  substring of a top-K chunk. The rest is arithmetic over committed records:
  `reports/answer-prompt-v4/4f48fed/*-judge.cases.jsonl` hold `grade`, `answers_question`,
  `context_has_answer`, `claims_supported` and `claims_total` per answer.
- **What it changes:** no answer; it changes how the published numbers read. MultiHop-RAG's
  10/70 «all evidence» becomes comparable with the published Hits@4 of 0.62–0.66 only by the
  official rule, likely much higher (mine).
- **Cost:** 0 judge calls. The decline matrix, the CRAG score and the three numbers: the laptop,
  minutes. MultiHop-RAG's Hits@K needs the top-K chunk texts: the per-question files on the Mac
  (`retrieval/NNN-<case>.json` of stage 2's run) — a light script there, no model; the texts stay
  on the host.
- **Risk:** choosing the flattering metric after seeing it. Against it: print ours and the
  official one side by side, both named before the count.
- **Universal:** yes.
- **Plan:** new, «Параллельно, без Mac» (and a light Mac script between runs); rule (c) once
  published with provenance. Needs no word.

### Item 2 — judge metrics that make us comparable

- **What:** WixQA's own Context Recall and Factuality prompts on its Simulated rows (≈ 200
  requests); nugget recall in the answer and in the context — ≈ 100 requests a base to split
  the references, then ≈ 2 an answer: ≈ 1,200 for four bases.
- **Evidence:** the reports' word: the paper's appendix holds the prompts (Claude 1); nugget
  scoring is TREC RAG 2025's method (both). Not checked.
- **What it changes:** one WixQA number set beside the paper's 0.63–0.77 Factuality, with another
  judge (ours is `claude-opus-5-5`, theirs GPT-4o), so still not equal. Nugget recall separates a
  retrieval miss from a generation miss in the answer; M3 and M1 already do much of that.
- **Cost:** ≈ 1,400 requests ≈ 4.4 five-hour windows ≈ $260; 0 Mac hours.
- **Risk:** the same model splits the nuggets and scores them; the comparison stays across
  judges.
- **Universal:** yes.
- **Plan:** judge budget beyond §4.4's estimate — hers. Rule (c). **My reading:** not now. Its
  useful core — a recall guard for a prompt change — is covered by M2 in item 3's own run; the
  comparison is for stage 8, if she wants it.

### Item 3 — an evidence-first answer, with an explicit status

- **What:** one call: the answer first quotes the evidence for each part of the question, then
  states only what it supports, and ends with a status — answered, partly, declined (Codex 2,
  after ReClaim). Claude's alternative — a second «partial answer» pass for declines only —
  lost its support: the 1.5 % → 99 % it cited is a trained model (Trust-Align), not a prompt.
- **Evidence:** checked — ReClaim's training-free prompt on Llama3-8B, ASQA: correctly
  attributed sentences 54.7 → 77.7, EM recall 55.2 → 50.7. English, an 8B, another task.
- **Our data say it aims at the main loss:** unsupported claims in 14 of 17 bad aircargo
  answers, 32 of 51 on WixQA, 50 of 57 on ConditionalQA; 22 wrong declines on WixQA. No other
  treatment found touches both without a new model.
- **What it would change:** the bad share, if the gain transfers in part; the time — quoting the
  evidence lengthens the output. At 4.3 tokens/s, 100–200 more tokens are +25–45 s an answer
  (mine). The quotes are verbatim copies of the context, the case where n-gram decoding (5a)
  was fastest — the two fit together.
- **Cost:** a paired screen on V4's saved contexts of WixQA's and ConditionalQA's open parts —
  only the prompt differs, no retrieval run: ≈ 200 × 2–3 min ≈ 8–12 h of Mac with a small replay
  tool (new code). The judge: M1 and M2 with retests, as in stage 2b, ≈ 460 requests ≈ 1.4
  windows ≈ $86. M2 is the recall guard, so that fewer bad answers cannot come from emptier ones.
- **Risk:** lower recall and more declines (ReClaim's −4.5 EM recall); longer answers; the 4B
  may not follow a structured format; Russian untested.
- **Universal:** yes — no domain or language words.
- **Plan:** a prompt change. §9 allows only stage 1's fixes, V4 and stage 4's speed levers, so
  it needs an amendment — hers. Where: a stage 3б after stage 3 and before stage 4, so that
  stage 4's final path and stage 5 measure the final prompt once. Rule (c) for the screen; (a)
  and (c) on the path if adopted.

### Item 4 — the router

- **What:** stage 3's outcome decides. B — how a check of minutes enters the chat is hers (wait
  for it; show the answer and the button later; check some answers). C, or a B too slow for
  her — research 4's offline test of three encoder checkers on saved answers: Horizon
  Hallucination Guard small (141M), LettuceDetect v2 on mmBERT-base (0.3B), mDeBERTa-xnli per
  sentence.
- **Evidence:** checked — the cards' numbers (LettuceDetect v2 RAGTruth example F1 74.3, 4k
  window, Apache-2.0; Horizon-small 0.714 balanced accuracy on translated non-English HaluEval,
  Russian not among its tested languages); RusHallu-RAG: 1,000 Russian pairs with human span
  labels (its data licence not stated); mFAVA's Russian F1 89.1 against GPT-4 labels and 65.5
  against human ones. No checker has a measured Russian grounding quality or a CPU time like
  ours.
- **What it would change:** a router of seconds instead of minutes, if one reaches the frozen
  reading. The 4B's own claim check takes 81–235 s an answer (the signal run's first rows).
- **Cost:** no generation; per model ≈ 1,300 pairs (RusHallu-RAG's 1,000 and our 300 V4 answers)
  — ≈ 2–4 h of Mac for three; 0 judge calls (the judge's per-answer `claims_supported` exist).
- **Design that keeps the frozen rules** (mine): each checker's threshold is chosen on
  RusHallu-RAG's human labels and on the English open parts, then read once on the 100
  aircargo answers by the handover plan's frozen reading — never tuned and read on the same
  answers.
- **Risk:** agreement with our judge may overstate a checker (≈ 20 F1 points in mFAVA); a 0.6–1.2
  GB encoder beside the 4B on 8 GB; RusHallu-RAG's licence — evaluation only, aggregates
  published.
- **Universal:** yes, multilingual encoders; no word lists.
- **Plan:** stage 3. A new signal outside the frozen signal plan and a new model in the product —
  hers. Rule (c) for the test, (a) when wired.

### Item 5 — a shorter context

- **What:** context pruning or compression (research 3) — already stage 4's step 4 («Промпт
  короче», 67 s on 2,270 tokens).
- **Evidence:** the report's word on transfer to a small model on a CPU.
- **What our data add:** the five documents sent hold the gold at the rates above; cutting
  documents is read against them on stage 2's per-question files before any live run.
- **Plan:** planned; needs no word; (a) and (c).

### Item 5a — speed, research 6 — and what our log and arithmetic add

Her «Давай попробуем» (2026-10-25 22:18) covers the checks and each lever as an experiment,
`ollama serve`'s settings included and restored after (my reading, written in the handoff).
Adopting a lever into the path goes by its numbers; production settings and the reranker's
runtime are hers.

| Lever | Evidence | Expected on our answer | Mac | Rank |
|---|---|---|---|---|
| **Step 0: diagnostics** — `cached n_tokens`, `print_timing` and `cache state` per request in a 3–5 question chat series; page-ins (`vm_stat`), swap and llama-server's RSS during generation; the CPU backend and repack lines at load | checked: Ollama 0.33.2 sends `cache_prompt: true`; the log's lines exist | none — it tells which levers can pay | ≈ 1 h | first |
| **A cap on the host prompt cache** (`--cache-ram`; whether `LLAMA_ARG_CACHE_RAM` in `ollama serve`'s environment reaches the runner — `ps eww` of its pid) | mine: the arithmetic above; the 8,192-MiB limit read in the log | the swap growth over a series (12,274 MB in 30 questions on `19beeb1`) and part of the rerank's 102 s against 27 s idle, if contention is the cause; the cache saves the chat ≤ 4 s a request | a series in step 5's 30-question check | second |
| **INT8 of the same reranker**, ONNX Runtime 1.23.2 (the last with macOS 13 x86_64 wheels; 1.24.1 needs macOS 14) | checked: 1.8× on a 4-thread AVX2 CPU, top-8 overlap 1.00 on 2 × 32 pairs; RSS not reduced | 27 → ≈ 15 s idle; in the chat unknown | ≈ 2–4 h: ORT FP32, then INT8, on stage 2's saved pools, then a short live series | third |
| **n-gram decoding** — llama-server outside Ollama, the same GGUF and flags, `--spec-type ngram-simple` | the report's word: one laptop test, 2.5× on editing, the default n-gram slower (24.0 against 32.0 tokens/s), no gain on a free answer | 14–42 s if the 2.5× held; possibly slower | ≈ 2–3 h | fourth |
| **Repacking**, if the load log shows it off | the report's word: llama.cpp's PR, pp512 45.8 → 73.8 on a Ryzen; on by default in current llama-server | 0 if on; ≈ 25 s of the 67 s if off | ≈ 1 h, only if off | if step 0 says |
| **Instructions kept cached** | mine: the fixed start is ≈ 140 tokens | ≤ 4 s | none of its own; read in step 0 | only if step 0 shows more |
| **Self-evaluation as a continuation of the answer's prompt**, if she keeps the badge (stage 4, step 2) | mine: it would reuse the ≈ 2,300 tokens it now reads again | ≈ 55 of its 68 s | ≈ 1 h | only if the self-score stays |
| A small draft model | the report's word: 1.72× on an i7-8700 | 10–29 s, eaten by RAM on 8 GB | — | not at all |
| KV cache in q8_0 / q4_0, flash attention, FP16 | the reports: not sure speed-ups on an old CPU; one q4 KV quality collapse | — | — | not now |

Stage 4 grows by ≈ 6–11 h: ≈ 20–28 h instead of 14–17.

### Item 6 — retrieval: query rewrite or decomposition; BGE-M3's multi-vector scores

- **What:** one LLM rewrite or decomposition of the question before retrieval; separately,
  BGE-M3's own multi-vector (ColBERT-style) scores on stored token vectors instead of a
  cross-encoder.
- **Evidence:** the report's word (Claude 2) for Hits@4 0.611 → 0.763 on MultiHop-RAG with a 32B
  decomposer; checked (research 3) that prompted agents on a 3B did worse than plain RAG (EM
  0.181–0.255 against 0.270). BGE-M3's paper: multi-vector 71.2 against dense 70.1 on MIRACL-ru
  (research 7, checked in §3; multi-vector there re-ranks dense's top 200).
- **Our data:** MultiHop-RAG's evidence reaches the pool for 22 of 70 questions — the first
  loss there is before the reranker, which is what decomposition targets.
- **Cost:** decomposition: one short 4B call (≈ 15–25 s, mine) and a second retrieval (27–100 s)
  an answer; multi-vector: a new index generation (≈ 10 h, the second generation took 10 h 01
  min) and a new scorer; token vectors on disk (WixQA ≈ 15 GB in fp16, mine).
- **Risk:** a small model's rewrites hurt (research 3); multi-hop is advisory in our total.
- **Universal:** yes.
- **Plan:** new mechanisms. Stage 7 takes only code that exists; the vector store (ADR 0007)
  and the embedder are frozen (§9). Hers; after item 1 shows the real multi-hop gap.

### Item 6a — another generator

- **What:** a pilot of Qwen3.5-4B and Gemma 4 E2B: a feasibility check in Ollama 0.33.2 (loads,
  thinking off, `[N]` citations, memory beside the retrieval models), then 80 paired answers each
  on saved contexts, judged.
- **Evidence:** checked — no candidate beats ours by a margin in one protocol; Qwen3.5-4B is
  slower on a CPU (prompt ×0.91, generation ×0.79); Gemma 4 E2B reads prompts at 96.2 and
  generates at 18.2 tokens/s on an i7-10700 (Qwen3.5-4B 44.0 and 10.3 there; no Qwen3-4B row);
  in one English ESG study Gemma 4 E2B's faithfulness 0.784 against qwen3:4b-instruct's 0.719,
  correctness 0.423 against 0.449, judged by qwen3:4b-instruct; Gemma-3-4B answers 67.3 % of
  Vectara's documents against Qwen3-4B's 99.9 % (§3).
- **What it would change:** maybe speed (Gemma 4 E2B), maybe faithfulness; Russian unknown; its
  file is 3.1–3.4 GB against our 2.5 GB on an 8-GB Mac.
- **Cost:** ≈ 20 h of Mac; ≈ 300–450 judge requests.
- **Risk:** every published number is measured again after a swap.
- **Plan:** a model swap — §9, «явное решение Юли с числами». After stage 4: a faster runtime
  helps any model, and research 5 itself put the speed question first.

### Item 6b — research 7: the reranker, kept, removed or replaced

- **What:** offline on stage 2's saved pools, in this order: (i) no reranker — the fused order's
  first five; (ii) ONNX FP32, then INT8, of the same BGE reranker (item 5a); (iii) a smaller
  reranker — `gte-multilingual-reranker-base` (306M) first, Horizon multilingual-reranker-base
  (308M) and `ru-reranker-edge-150m` as reserves.
- **Evidence:** research 7 found no replacement both as good and faster on our CPU; its numbers
  are spot-checked in [§3](#3-what-stays-open) — exact but one (USER-bge-m3). On the same
  candidates Horizon-small scores below BGE-M3 dense alone on MIRACL, and both Horizon models
  trail the BGE reranker on Russian RuBQ (0.826 and 0.842 against 0.861).
- **Our data:** the reranker cuts gold the pool holds (16 of 84 on WixQA, 15 of 22 on
  MultiHop-RAG), and costs 27 s idle and 102 s in the chat, with 2.27 GB of FP32 weights. Its
  removal is the one lever that could win speed and memory at once — or lose quality; only the
  offline point tells which.
- **Cost:** (i) a light script on the Mac, no model, minutes — the code already has the switch
  (`RAG_RERANKER_MODEL=""`). (ii) ≈ 2–4 h (item 5a). (iii) ≈ 1–2 h of Mac a model on the saved
  pools, 0 judge calls.
- **Risk:** removing the reranker also removes S7 (useless by the counts so far); a smaller
  model's quality on our bases is unknown; Horizon truncates at 384–512 tokens.
- **Universal:** yes.
- **Plan:** (i) data analysis — no word to measure; dropping the reranker from the path changes
  the path — hers, in stage 4. (ii) stage 4, her 22:18 word for the experiment. (iii) a reranker
  swap — §9, hers; worth asking only if (i) shows the reranker matters.

### Item 7 — not worth this hardware

Graph-RAG frameworks (also ADR 0001), long context instead of retrieval, RL or fine-tuning (no
GPU), large reasoning rerankers, semantic entropy (≈ 10 generations an answer), token
log-probabilities as a router (AUC ≈ 0.51 on RAGTruth), a small draft model on 8 GB, blind human
labelling of the judge (D11). They go into §9's stop-list as one row.

## 2. Against `PLAN.md`

| Item | Stage | Planned, frozen or new | Slice rule it can meet | Her word |
|---|---|---|---|---|
| 1 | «Параллельно, без Mac»; a light Mac script | new | (c) | no |
| 2 | judge, laptop | new; budget beyond §4.4 | (c) | yes |
| 3 | proposed stage 3б | new; §9 forbids the prompt change without an amendment | (c); (a) + (c) if adopted | yes |
| 4 | stage 3 | B: planned; the encoder test: new | (c); (a) when wired | B's form; the test; any new model |
| 5 | stage 4, step 4 | planned | (a), (c) | no |
| 5a | stage 4, step 0 and the levers | step 0 and the levers: new, covered by her 22:18 word | (a), (c) | production settings; the reranker's runtime |
| 6 | stage 7 | new mechanism; vector store and embedder frozen | (c), then (a) | yes |
| 6a | after stage 4 | frozen (§9: model swap) | (c) | yes |
| 6b | stage 4 (i, ii); §9 (iii) | (i) new analysis of saved data; (ii) covered; (iii) frozen | (c); (a) if the path changes | (i) adoption; (iii) yes |
| 7 | §9 | stop-list | — | — |

## 3. What stays open

**Conflicts between the reports** are settled by the sources in the folder's
[table](README.md#how-good-the-two-reports-are): Hits@K (Codex), Trust-Align (a trained model),
Qwen3.5-4B's speed (Claude), RusHallu-RAG's existence (Codex), the recomputed MAP@10 (0.2619).

**Research 7, spot-checked 2026-10-26** against its primary sources (arXiv tables, the model
cards' `README.md`, the papers' PDFs, PyPI's JSON, GitHub), with two more checks the analysis
needed:

| Claim | Source | Verdict | What the claim leaves out |
|---|---|---|---|
| LAMAR, MIRACL nDCG@10 ru/en: BGE reranker 67.4/66.0, LAMAR 67.5/68.8 | arXiv 2607.22042, Table 4 | exact | MMTEB's reranking task; no first stage, depth or length named |
| mGTE: BGE reranker MIRACL 72.6, BEIR 54.6; mGTE reranker 68.5, 55.4; dense alone 62.1 | arXiv 2407.19669, Table 5 | numbers exact; "dense top-100" mixes Table 5 (dense) with Appendix E (top 100 of dense + sparse) | its dense retriever (62.1) is weaker than BGE-M3's (67.7); length 8192 |
| Saegus INT8 card: RSS ≈ 2 GB at batch 1, 570 MB file against 2.2 GB, top-8 overlap 0.81 at length 256 | the card | exact; it names no ONNX Runtime version | "int8 saves time, not RAM"; the 0.81 is truncation, not quantization |
| a-ivanovitch ONNX card: 8.9 s against 11.8 s, 10 documents, Spearman 1.0; own INT8 top-1 overlap 0.625 | the card | exact | no CPU, threads or ORT version |
| RusBEIR: BGE-M3 → + BGE reranker, mean of 17 sets 61.13 → 65.85 | Dialogue 2025, Table 3 | exact | the rerank depth is not stated; the reranker lowers SberQuad and ru-facts; BM25 is the best single model on 4 sets |
| Horizon small/base: MIRACL-ru 0.790/0.846 against BGE 0.838; 384 tokens | the cards | exact | on MIRACL the small model (0.779) is below BGE-M3 dense alone (0.797) on the same candidates; on RuBQ small 0.826 and base 0.842 against BGE 0.861; MIRACL is in-domain for all three |
| ru-reranker-edge-150m: 60.9 against 60.7 on 5 RusBEIR sets; RuBQ 83.9 against 84.8 | the card | exact | GPU timing only; 512 tokens; on a legal corpus it lost to BM25 alone (gold@5 0.702 against 0.736) |
| BGE-M3 on MIRACL-ru: dense 70.1, multi-vector 71.2, all 71.7 | arXiv 2402.03216, Table 2 | exact | multi-vector re-ranks dense's top 200; it is not a first stage |
| ruMTEB retrieval mean: BGE-M3 74.79, mE5-large 74.04, USER-bge-m3 73.63 | NAACL 2025, Table 5 | **differs**: USER-bge-m3 is not in the paper; the other five are exact | the mean covers 3 tasks |
| OpenVINO 2026.0 drops Intel macOS | its release notes; PyPI | confirmed: "MacOS x86 is no longer supported"; the last x86_64 macOS wheel is 2025.4.1 | the CPU plugin needs AVX2 (the i5-7500 has it) |
| The last ONNX Runtime for macOS 13 on x86_64 | PyPI | **1.23.2**, `macosx_13_0_x86_64`, cp310–cp313; 1.24.1+ is arm64 and macOS 14 only | — |
| Gemma-3-4B's answer rate (item 6a) | Vectara's leaderboard, 2026-10-22 | checked: 67.3 % (Qwen3-4B 99.9 %) | its 6.4 % hallucination rate covers only the documents it answered |

None of the differences moves a lever: the reranker stays first to test removed (item 6b, i),
then as INT8 (ii); among smaller models `gte-multilingual-reranker-base` stays first, since
Horizon's Russian numbers trail BGE's on RuBQ.

**Checks still not done** — none decides anything before stage 4:

- the Reddit i5-7500 number (Reddit refuses scripts) — stage 4's step 0 measures our own;
- WixQA's appendix prompts (item 2) — only if she takes item 2;
- the 2026 preprint on deleting unsupported sentences (64.3 % kept, 83.5 % of clean answers
  edited) — only under outcome B, before any repair;
- Codex 6's n-gram (2.5×) and draft-model (1.72×) tests — the n-gram lever measures its own;
- Claude 2's decomposition gain (0.611 → 0.763, 32B) — before item 6, if she takes it.

## 4. A ranked short list

Chosen by the product goal ([`PLAN.md`](../../../PLAN.md) §2): answers a customer can trust,
the ones it cannot vouch for handed to a person, an answer time she can promise, on any corpus.

**Now — the laptop, no word needed:**

1. **Item 1's no-call metrics** from the committed V4 exports: the decline matrix, the CRAG
   score, Codex's three numbers. Free; every later choice is read by coverage against quality,
   and the plan has no such number yet.

**After the signal run's end, before stage 4 — light Mac scripts, no model, no word:**

2. **The fused order's first five without the reranker, and MultiHop-RAG's Hits@K by the
   official rule**, on stage 2's per-question files. Minutes. The first says whether the
   reranker earns its 27–102 s and 2.27 GB — the largest speed-and-memory question of the plan;
   the second makes the advisory base comparable.

**After stage 3 — its outcome decides:**

3. **The router.** B: her choice of form, then an E2E test and the added seconds. C, or a slow
   B: item 4's encoder test (her word) — the only way a handover check of seconds fits this Mac.
4. **Item 3's evidence-first screen as stage 3б** (her word). It targets the main measured loss
   with no new model; it must come before stage 4's final path, or the final path is measured
   twice.

**In stage 4 — her 22:18 word covers the experiments:**

5. Step 0 → the host-cache cap → INT8 of the same reranker → n-gram decoding → repack only if
   off; the cached instructions and the self-evaluation continuation only if step 0 or step 2
   makes them pay. The cap first: it is a setting, minutes to try, and it addresses the memory
   growth the plan has carried since 2026-10-16. INT8 next: the one lever measured on the same
   model. n-gram later: a second server to set up, and slow-downs found.

**Later — her word:**

6. **The generator pilot** (6a), after stage 4: none is shown better; a faster runtime helps any
   model; a swap measures everything again.
7. **A reranker swap test** (6b iii), only if item 2 of this list shows the reranker matters.
8. **Query decomposition** (6), in stage 7 after item 1 shows the multi-hop gap.
9. **Comparable judge metrics** (item 2), for stage 8 if she wants the comparison.

**Not at all:** item 7's list.

## 5. What the amendment does

Applied in `PLAN.md` on 2026-10-26, before the signal run's record:

- §8.1: her words of 2026-10-25 — 18:41 (treat after the full run), 21:46 (Codex's budget for
  research), 22:18 («Давай попробуем»), 22:22 and ≈23:05 (this analysis, the plan first).
- Stage 3: what follows outcome B and outcome C (A cannot happen: every cheap signal's upper
  limit of caught is below 1/2 by the counts of 2026-10-25); the frozen reading is untouched.
- Stage 4: step 0; the host-cache cap in step 5; the INT8, n-gram and repack levers; the
  no-reranker point in step 3; the hours 20–28.
- «Параллельно, без Mac»: item 1 and the light Mac scripts.
- §9: INT8 of the same reranker as a stage-4 experiment; one stop-list row for item 7.
- §10: the host prompt cache as the memory hypothesis.
- §8.3, items 12–17: items 2, 3, 4's test, 6, 6a, 6b (iii) and dropping the reranker, each
  with its cost — proposed, not applied.
