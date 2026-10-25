# Research brief R5 — the best local generator for a grounded support assistant on a 4-core CPU with 8 GB

Write the report in Russian to `D:/RAG_new/.tmp/research/r5-local-model.md` (write nothing
else anywhere). Return only a short summary (≤ 15 lines). Read-only web research: do not post,
sign up or contact anyone. Up to ~25,000 characters.

## Why

We build a RAG support assistant: a customer asks, the system answers from a company's
documents with numbered citations [N], declines when the documents do not answer, and an
answer it cannot stand behind should go to a person. Its generator runs locally. Most of our
bad answers carry a claim the retrieved documents do not hold; on one dataset the model also
declines questions the documents answer. The owner may decide to change the generator — but
only with numbers, because a change means measuring every published result again. This run
asks whether a better local generator than ours exists within our hardware, and how to test
the best candidates cheaply. Do not repeat general RAG benchmarks, metrics or methods.

## Our system

- Generator now: Qwen3-4B-Instruct-2507, Q4_K_M, Ollama 0.33.2 (llama.cpp runner, GGUF).
  Machine: one Intel i5-7500 (4 cores, AVX2, no GPU), 8 GB RAM, macOS. The generator's
  process holds about 3.3 GB; the retrieval models (BGE-M3, bge-reranker-v2-m3) run on the
  same machine, and swapping slows everything.
- One answer: a prompt of about 2,300 tokens (instructions plus 5 chunks of 800 characters),
  an answer of 100–300 tokens with citations. Median whole-answer time 250–300 s, p90
  340–470 s; prompt processing alone about 67 s. Measured earlier on this machine: a 7B
  answers in about 8 min, a 1.5B in about 100 s.
- Languages: Russian (our own base) and English (three public bases); any corpus and domain,
  no hand-made dictionaries or per-domain rules. No person grades answers: an LLM judge does.
- Our judged answers: good 35–63 of 100 depending on the dataset.
- Already known (earlier runs):
  - «Little Brains, Big Feats» (arXiv 2606.30062, 06.2026; Russian RAG, context given, CPU,
    16 GB): Qwen3-4B-Instruct-2507 Q5_K_M correctness 0.71 / faithfulness 0.80; Qwen3-8B
    0.72 / 0.83; GPT-5-mini 0.73 / 0.89.
  - Vectara's hallucination leaderboard (22.10.2026, summarisation): Qwen3-4B 5.7 %,
    Gemma-3-4B 6.4 %, Phi-4-mini 23.5 %, Qwen3-8B 4.8 %.
  - Newer models named without RAG numbers: Qwen3.5-4B (card 02.03.2026), Granite-4.2-3B and
    -8B (25.08.2026), Gemma 4 E2B / E4B (5.1B / 8B parameters with embeddings). Runtime
    support of Qwen3.5's hybrid architecture in llama.cpp / Ollama was not confirmed.
  - Grounding-trained readers exist (Trust-Align weights for small models, English).
- A model change is the owner's decision; the research prepares it.

## Questions

1. **Candidates**, open weights, released 2025 – October 2026, that fit beside the retrieval
   models in 8 GB at 4-bit (about 4.5 GB or less for the model; dense ≤ ~5B, or MoE whose
   *total* size fits): parameters (total / active), release date, Russian ability, licence
   (mark non-commercial), context length, GGUF / llama.cpp / Ollama support of the
   architecture, Q4 file size. A table.
2. **Grounded answering quality**, Russian and English apart: published numbers on answering
   from given documents — faithfulness or hallucination rate, correctness, following
   citation instructions, declining when the documents do not answer (and over-declining).
   Prefer same-protocol comparisons that include Qwen3-4B-Instruct-2507; Russian benchmarks
   where they exist.
3. **Speed on a 4-core AVX2 CPU**: prompt processing and generation tokens per second at
   Q4 for each candidate, measured or reported by others on similar CPUs; the effect of the
   architecture (hybrid or linear attention, MoE, per-layer embeddings) on a 2,300-token
   prompt; the expected whole-answer time on our machine (2,300-token prompt, 250-token
   answer) — measured or estimated, say which.
4. **Grounding-specialised small readers** (≤ 4B) fine-tuned for faithful answers and
   refusal in 2025–2026: the gain against their base model, languages, availability, licence.
5. **Quantisation:** the measured quality loss of Q4_K_M against Q5 / Q8 for small models on
   grounded tasks, where measured.
6. **Ranking for us:** the top 3–5 candidates against Qwen3-4B-Instruct-2507 as the
   baseline — expected gain or loss in Russian and English with its evidence, time per
   answer, RAM, risks (runtime support, licence, declines). Say plainly whether any candidate
   is likely to beat the baseline by enough to justify measuring everything again. Then a
   pilot design on our saved questions: about 20 questions per dataset, paired with the
   baseline on the same retrieved context, judged by our LLM judge, and its time on our
   machine.

## Rules for the report

- Every number with its source (link), its date and its setup; never invent a number. When a
  result is not found, say «не найдено» and what was searched. Mark vendor or marketing
  claims as such.
- Prefer primary sources (papers, model cards, official leaderboards, llama.cpp issues and
  benchmarks); check a key number in a second source where possible.
- Separate facts from interpretation; mark the interpretation as such.
- Structure: summary (≤ 10 lines) → questions 1–5 (tables + notes) → the ranking and the
  pilot → sources.
