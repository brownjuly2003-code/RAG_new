# Research brief R3 — the state of RAG in October 2026: the numbers reached, the methods behind them, and how support assistants measure quality and handover

Write the report in Russian to `D:/RAG_new/.tmp/research/r3-state-of-rag.md` (write nothing
else anywhere). Return only a short summary (≤ 15 lines). Read-only web research: do not post,
sign up or contact anyone. Up to ~25,000 characters.

## Why

We build a RAG support assistant: a customer asks, the system answers from a company's
documents and shows its sources, and an answer it cannot stand behind should go to a person.
Two earlier research runs covered (1) the published results on the three public datasets we
test on (WixQA, ConditionalQA, MultiHop-RAG) and the evaluation metrics in use, and (2) the
methods against our own failures (unsupported claims of a small model, wrong declines, weak
multi-hop retrieval, cheap checkers). Do not repeat them. What is missing is the frame: what a
good RAG system reaches in 2026, by size, which method families are behind the best results
and which of them a small model on a CPU can use, and how support assistants in production
measure answer quality and the handover to a person.

## Our system (for the «by size» and «transfers to us» judgements)

- Generator Qwen3-4B-Instruct-2507, Q4_K_M, Ollama on one Intel i5-7500 (4 cores), 8 GB RAM,
  no GPU; one answer about 4–5 min. Retrieval: BM25 + BGE-M3 dense, RRF, bge-reranker-v2-m3
  keeps 5; 800-character chunks. Any corpus, domain and language (now Russian and English),
  no hand-made dictionaries or per-domain rules; no person grades answers.
- Our judged answers: good 35–63 of 100 depending on the dataset; most bad answers carry a
  claim the retrieved documents do not hold. Cheap signals (the model's self-score, the
  reranker's score, decline phrases) do not find the answers that need a person.

## Questions

1. **Benchmarks and levels.** Which RAG benchmarks are the reference points in 2025 –
   October 2026 (for example CRAG, FRAMES, TREC RAG 2024/2025, RAGTruth, BRIGHT, open-domain
   HotpotQA/MuSiQue, long-document or enterprise QA, multilingual or Russian RAG benchmarks)?
   For each: what it measures, the best reported numbers, and the numbers of open models of
   ≤ 8B and ≤ 4B where reported, with the setup (retrieval given or open, judge or exact
   match). A table per benchmark.
2. **Method families behind the best results** in 2025–2026: e.g. agentic or iterative
   retrieval, reasoning rerankers, late interaction, graph-based RAG, long context instead of
   or beside retrieval, context compression, models trained for search with reinforcement
   learning, faithfulness training. For each: the measured gain and its setup, the compute it
   needs, and whether it transfers to a 4B on a 4-core CPU (yes / partly / no, and why).
3. **Small models.** What open ≤ 4B and ≤ 8B models reach on RAG tasks in 2026 against
   frontier models — the gap, and which tasks it is smallest and largest on. Which small
   models lead for grounded answering and for Russian.
4. **Support assistants in production.** How companies and papers measure a RAG support
   assistant: answer acceptance or resolution rate, containment or deflection, escalation to a
   person (its precision and recall, how the decision is made), CSAT, groundedness checks in
   production, online versus offline evaluation. The levels reported (with source and whether
   it is a vendor's claim), and which of these metrics need no human grading.
5. **What this means for us** (mark it as interpretation): where our numbers would sit, the
   2–4 method families worth our attention given the hardware, and which production metric of
   question 4 we could compute from our records.

## Rules for the report

- Every number with its source (link), its date and its setup; never invent a number. When a
  result is not found, say «не найдено» and what was searched. Mark vendor or marketing
  claims as such.
- Prefer primary sources (papers, official leaderboards, model cards); check a key number in a
  second source where possible.
- Separate facts from interpretation; mark the interpretation as such.
- Structure: summary (≤ 10 lines) → questions 1–4 (tables + notes) → what this means for us →
  sources.
