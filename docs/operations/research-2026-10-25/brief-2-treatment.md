# Research brief R2 — how to treat unsupported claims, wrong declines and weak multi-hop retrieval in a small-model RAG on a CPU

Write the report in Russian to `D:/RAG_new/.tmp/research/r2-treatment.md` (write nothing else
anywhere). Return only a short summary (≤ 15 lines). Read-only web research: do not post, sign
up or contact anyone. Up to ~25,000 characters.

## Why

Our RAG support assistant gives too many bad answers on public datasets, and the answers that
need a person are not recognised. The diagnosis (below) says the main loss is generation: the
model adds claims the retrieved documents do not hold, and on one dataset declines questions
the documents answer; retrieval is the second loss, worst on multi-hop questions. We need the
options that fix answers or route them to a person, ranked by measured gain, cost on our
hardware and universality, so that the owner can choose what to build next.

## Our system and its constraints

- **Hardware:** one Intel i5-7500 (4 cores), 8 GB RAM, no GPU; Ollama. One answer of the
  generator takes about 4–5 min; retrieval alone 27.6 s, of which the CPU reranker 27.3 s.
- **Generator:** Qwen3-4B-Instruct-2507, Q4_K_M. **Retrieval:** BM25 + BGE-M3 dense, 20
  candidates each, RRF, bge-reranker-v2-m3 keeps 5; markdown-section chunks of 800 characters,
  200 overlap, up to two neighbour chunks each side. Vector store ChromaDB.
- **Swapping the generator, the vector store or the reranker is the owner's decision.**
  Include such options, but mark each one «требует решения владельца».
- **Universality:** any corpus, domain and language (now Russian and English). No hand-made
  dictionaries, keyword lists or per-domain rules — an option that needs them ranks low.
- **No person in the quality loop:** no human grading, approval or review of answers.
- **Time:** no latency target; a hard ceiling of 3,600 s per answer; each added minute counts.
- **Two answer paths.** The web chat (production): retrieval → answer → self-evaluation (the
  same 4B gives a score 0–100) → suggested questions. The widget: query rewriting, document
  grading by the 4B, claim checking (the 4B extracts the answer's claims, then checks each
  against the documents; 81–235 s an answer), up to two retries, a ticket to a person.
- **The answer prompt:** answer only from the documents, cite [N], answer partly when the
  documents answer partly, decline when they do not answer.

## Our numbers (100 questions a base; the judge is an LLM, Claude Opus; no human grading)

Judge classes without the reference: *good* — complete and fully supported by the retrieved
documents, or a right decline; *partial* — supported but incomplete; *bad* — an unsupported
claim, a defect, no answer, or a decline the documents did not justify.

| Base | Good | Partial | Bad | Claims supported | Routed to a person |
|---|---|---|---|---|---|
| Air cargo (own, Russian) | 63 | 20 | 17 | 96.7 % | 3 |
| WixQA, Simulated (English) | 40 | 9 | 51 | 90.5 % | 14 |
| ConditionalQA (English) | 35 | 8 | 57 | 79.2 % | 17 |
| MultiHop-RAG (English, earlier prompt) | 65 | 1 | 34 | — | — |

| Base | Bad | The context held the answer | With an unsupported claim | Declined though the context answered |
|---|---|---|---|---|
| Air cargo | 17 | 17 | 14 | 0 |
| WixQA | 51 | 48 | 32 | 22 |
| ConditionalQA | 57 | 54 | 50 | 6 |

Retrieval against the gold documents: ConditionalQA all evidence in the context 60/80 (mean
recall 0.83); WixQA at least one gold article 68/100 (mean coverage 0.63); MultiHop-RAG all
evidence 10/70 (mean evidence recall 0.49). A previous research run found that the closest
published number, MultiHop-RAG's Hit@4 with a similar retriever, is 0.62–0.64, so our
retrieval there looks weaker — possibly partly how we match evidence to chunks.

**Routing to a person.** The target is an answer the judge calls bad, or any decline. On the
air-cargo base 17 of 100 answers are targets. Cheap signals, each against the 17 targets and
the 63 good answers: the self-score < 80 catches 2 and marks 0 good; < 100 catches 3, marks 4;
decline phrases catch 0; the reranker's top score below the best threshold catches 4, marks 19;
the answer's script differing from the question's catches 3, marks 4. None is usable. The
widget's claim check and document grading are being measured as signals now; their result is
not known yet.

## Questions

1. **Unsupported claims in small models (≤ 8B) in RAG.** Which methods reduce them, with the
   measured effect and the setup: prompting (quote or extract first, then answer; citations per
   sentence), attributed or constrained generation, post-hoc verification with revision or
   removal of unsupported sentences, self-consistency, context-aware decoding, fewer or
   compressed context chunks, fine-tuning or LoRA for faithfulness. For each: the effect size,
   the cost in model calls and time on a CPU, universality, and the risk of more declines.
2. **Faithfulness checkers that run on a CPU in seconds.** Small NLI or encoder checkers and
   hallucination detectors (e.g. MiniCheck, HHEM, LettuceDetect, AlignScore, and newer ones of
   2025–2026): accuracy on public benchmarks (LLM-AggreFact, RAGTruth, others), Russian or
   multilingual support, the context length they take, CPU latency for 5 chunks of 800
   characters and a 1–2k-character answer. Usable as a routing signal, a repair trigger, or both?
3. **Wrong declines** when the context holds the answer: causes in small models, fixes, and
   how others balance them against unsupported claims; how the trade-off is measured.
4. **Multi-hop retrieval** with measured gains on MultiHop-RAG or similar (HotpotQA, MuSiQue,
   2WikiMultiHopQA) that are feasible on a CPU: query decomposition, iterative retrieval,
   HyDE, a larger candidate pool or k, chunk size, entity or graph linking. Also: how published
   MultiHop-RAG evaluations match gold evidence to retrieved chunks.
5. **Cheap predictors of a wrong RAG answer for routing:** verifier scores, token
   log-probabilities or entropy, semantic entropy, retrieval-score features, answer–context
   overlap; the published AUROC or precision at a given coverage, and their cost.
6. **Ranking for our system:** the top 5–8 options. For each: what it fixes (claims / declines
   / retrieval / routing), the expected gain and the evidence behind it, the cost on this
   hardware (calls, minutes, RAM), universality, whether it needs the owner's decision, and how
   we would measure it (claim-level faithfulness, nugget recall against the reference, a
   score of +1 right / 0 decline / −1 wrong, evidence recall, caught and over-marked targets).
   Rate each for both cases of the pending result: the widget's claim check does catch the bad
   answers, or it does not.

## Rules for the report

- Every number with its source (link), its date and its setup; never invent a number. When a
  result is not found, say «не найдено» and what was searched.
- Prefer primary sources (papers, model cards, official benchmarks); check a key number in a
  second source where possible. Mark results on models much larger than 8B as such.
- Separate facts from interpretation; mark the interpretation as such.
- Structure: summary (≤ 10 lines) → questions 1–5 (a table + notes each) → the ranking →
  what to measure first → sources.
