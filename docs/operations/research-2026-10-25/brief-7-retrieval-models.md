# Research brief R7 — retrieval models that read Russian and are fast on a 4-core CPU

Write the report in Russian (one report, nothing written anywhere else). Read-only web research:
do not post, sign up or contact anyone. Up to ~25,000 characters.

## Why

We build a RAG support assistant: a customer asks, the system answers from a company's
documents with numbered citations [N], declines when the documents do not answer, and an
answer it cannot stand behind should go to a person. Our cross-encoder reranker takes 27 s per
question on our CPU when it runs alone and 100–130 s while the generator is loaded — up to
a third of the answer's time. A change of reranker or embedder is the owner's decision and
means measuring every published result again, so it needs numbers. This run asks whether
smaller or faster retrieval models exist that keep the ranking quality, in Russian and English,
and how to test them cheaply. Do not repeat general RAG benchmarks, metrics or methods.

## Our system

- Machine: one Intel i5-7500 (4 cores, AVX2, no GPU used), 8 GB RAM, macOS. The generator
  (a 4B model, Q4, Ollama) holds about 3.3 GB on the same machine; swapping slows everything.
- Retrieval: BM25 plus BGE-M3 dense vectors (sentence-transformers, fp32, CPU), fused by RRF;
  bge-reranker-v2-m3 (568M, `CrossEncoder`, fp32, CPU) scores 20 candidates per question and
  keeps 5. Chunks of 800 characters with 200 overlap, so one pair is about 250–400 tokens.
  Vector search itself takes 0.2 s; the documents are embedded once, offline.
- Languages: Russian (our own base, support documents of one company) and English (three
  public bases: support articles, conditional questions on public-service pages, multi-hop news); any
  corpus and domain, no hand-made dictionaries or per-domain rules.
- Our retrieval quality on those bases varies; our larger loss is in generation, not retrieval,
  so a faster reranker that keeps quality is worth more than a slower one that gains a little.

## Questions

1. **Rerankers** released 2024 – October 2026 that read Russian, ≤ ~600M parameters, open
   weights: for each — size, languages (Russian named or measured?), licence (mark
   non-commercial), maximum length, published ranking quality with Russian numbers where they
   exist (for example ruMTEB reranking tasks, MIRACL-ru, mMARCO-ru, RusBEIR) and English
   numbers (BEIR or similar), and CPU latency per pair or per 20 pairs if reported. Include
   bge-reranker-v2-m3 as the baseline, and smaller rerankers (for example multilingual
   MiniLM / gte / jina / mxbai / Russian cross-encoders), late-interaction rerankers (ColBERT
   style, including BGE-M3's own multi-vector and sparse scores), and LLM-based rerankers only
   if they fit our CPU. A table.
2. **Embedders** that read Russian, ≤ ~600M parameters: published Russian retrieval quality
   (ruMTEB retrieval, encodechka or similar) against BGE-M3, CPU speed for a query, memory,
   licence. Only what would change the answer for us: is there an embedder clearly better
   than BGE-M3 on Russian retrieval at a similar or lower cost?
3. **Do we need the reranker at all, and how many candidates:** measured gains of reranking
   over hybrid BM25 + dense retrieval in Russian or multilingual settings, and how the gain
   changes with the number of candidates (top-10, top-20, top-50) — measured studies.
4. **The same reranker, smaller:** distilled, pruned or quantised versions of
   bge-reranker-v2-m3 (ONNX int8 and similar) with measured quality on a public set, and their
   CPU speed.
5. **Ranking for us:** the top 3–5 options against bge-reranker-v2-m3 (and against no
   reranker) — expected ranking quality in Russian and English with its evidence, expected
   seconds per question on our CPU for 20 pairs of ~300 tokens (measured or estimated — say
   which), RAM, licence, risks. Then an offline test design: rerank the saved candidate lists
   of our judged questions with each option and compare the kept 5 with the baseline's (hits on
   the gold documents where we have them, overlap with the baseline's top 5), and time each on
   our CPU — no new answers generated.

## Rules for the report

- Every number with its source (link), its date and its setup; never invent a number. When a
  result is not found, say «не найдено» and what was searched. Mark vendor or marketing
  claims as such.
- Prefer primary sources (papers, model cards, official leaderboards such as MTEB / ruMTEB,
  benchmark repositories); check a key number in a second source where possible.
- Separate facts from interpretation; mark the interpretation as such.
- Structure: summary (≤ 10 lines) → questions 1–4 (tables + notes) → the ranking and the test
  → sources.
