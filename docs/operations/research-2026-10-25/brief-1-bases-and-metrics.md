# Research brief R1 — published results on our three bases, and current RAG evaluation metrics

Write the report in Russian to `D:/RAG_new/.tmp/research/r1-bases-and-metrics.md` (create the
folder if needed; write nothing else anywhere). Return only a short summary (≤ 15 lines).
Read-only web research: do not post, sign up or contact anyone. Up to ~25,000 characters.

## Why

We run a RAG support assistant and measure it on open subsets of three public datasets. Our
answer quality there looks low (see «Our numbers»). We need to know whether it is low against
what others report on the same datasets, and which evaluation metrics are current practice
(2025 – October 2026), so that our numbers can be compared and our metric set completed.

## Our system (for comparability)

- Generator: Qwen3-4B-Instruct-2507, Q4_K_M, Ollama on a CPU (Intel i5-7500, 4 cores, 8 GB);
  one answer takes ~4–5 min. No GPU.
- Retrieval: BM25 + BGE-M3 dense, 20 candidates each, RRF fusion, bge-reranker-v2-m3 keeps 5;
  markdown-section chunks of 800 characters, 200 overlap, neighbour expansion.
- Open-domain setup: the retriever searches the whole corpus of each dataset (no gold document
  is handed to the model).

## Our subsets

- **WixQA**: 100 questions from the *Simulated* subset (those sharing no gold article with
  ExpertWritten); corpus — the WixQA knowledge base (37,571 chunks).
- **ConditionalQA**: 80 answerable questions plus 20 *not answerable* ones; retrieval over all
  documents (13,778 chunks), unlike the original setup that gives the document.
- **MultiHop-RAG**: 100 questions of the types *inference_query* and *null_query* only;
  corpus 11,231 chunks.

## Our numbers (each base 100 questions; the judge is an LLM, Claude Opus; no human grading)

- Judge classes without the reference answer (M1): *good* = complete and fully supported by the
  retrieved documents, or a right decline; *partial* = supported but incomplete; *bad* = an
  unsupported claim, a defect, no answer, or a decline when the documents held the answer.
  Current prompt: WixQA good 40 / partial 9 / bad 51; ConditionalQA 35 / 8 / 57; MultiHop-RAG
  (previous prompt) 65 / 1 / 34. Our own domain base (air cargo, Russian): 63 / 20 / 17.
- With the reference (M2), the share of answers that agree with the gold answer: WixQA 34 of
  100; ConditionalQA 43 of 80 on the previous prompt.
- Retrieval: ConditionalQA — all gold evidence in the context for 60/80, mean evidence recall
  0.83; WixQA — at least one gold article in the context for 68/100, mean gold-article coverage
  0.63; MultiHop-RAG — all evidence for 10/70, mean evidence recall 0.49.
- By the judge, the context held the answer for 92–100 % of questions; most bad answers carry
  an unsupported claim (WixQA 32 of 51, ConditionalQA 50 of 57), and WixQA has 22 declines
  although the context held the answer.

## Questions

1. **Per dataset** (WixQA, ConditionalQA, MultiHop-RAG): the original paper and later work
   (2024 – October 2026) that report QA or RAG results on it. For each: the metric and its exact
   definition, the numbers per system, the setup (retriever, generator and its size, open-domain
   or given document, which subset or query type), and the date. Look especially for small open
   models (≤ 8B), local or CPU deployments, WixQA's Simulated subset, ConditionalQA's not
   answerable questions and conditional answers, and MultiHop-RAG's inference and null queries
   and its retrieval metrics (Hits@k, MRR@k, MAP@k).
2. **Comparability**: for each published number, how close its setup is to ours (high / medium /
   low, and why). Which of their metrics we could compute from what we already record (the
   answer, the retrieved chunks with sources, the gold answer and gold documents, the judge's
   per-claim support), and what the closest comparable number would be.
3. **Current evaluation practice, 2025 – October 2026**: which answer and retrieval metrics
   serious RAG evaluations report now — e.g. claim-level faithfulness and completeness
   (RAGChecker, RAGAS), nugget-based evaluation (TREC RAG), context precision and recall,
   citation precision and recall, abstention and refusal on unanswerable questions, LLM-as-judge
   agreement with people and its known biases. What a credible report includes.
4. **Recommendation**: 1–3 metrics to add to ours, each with how to compute it from our
   records, what it would reveal that our classes hide, and its cost.

## Rules for the report

- Every number with its source (link), its date and its setup; never invent a number. When a
  result is not found, say «не найдено» and what was searched.
- Prefer primary sources (papers, official leaderboards, dataset cards); check a key number in
  a second source where possible.
- Separate facts from interpretation; mark the interpretation as such.
- Structure: summary (≤ 10 lines) → per dataset (table + notes) → comparability → current
  metrics → recommendation → sources.
