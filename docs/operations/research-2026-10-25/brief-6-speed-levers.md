# Research brief R6 — making our CPU RAG answer faster without changing its models

Write the report in Russian (one report, nothing written anywhere else). Read-only web research:
do not post, sign up or contact anyone. Up to ~25,000 characters.

## Why

We build a RAG support assistant: a customer asks, the system answers from a company's
documents with numbered citations [N], declines when the documents do not answer, and an
answer it cannot stand behind should go to a person. It runs on one small CPU machine, and one
answer takes about 5 minutes. The next stage of our plan tests speed levers one at a time,
each with its own timing. This run looks for levers we have not listed, with measured gains,
that keep **the same models** (a change of model, reranker or embedder is a separate decision
and is not asked here) and do not change the answers, or change them in a way that can be
measured. Do not repeat general RAG benchmarks, metrics or methods.

## Our system

- Machine: an iMac of 2017, one Intel i5-7500 (Kaby Lake, 4 cores / 4 threads, AVX2, no
  AVX-512), 8 GB DDR4, macOS; its Radeon Pro 570 (4 GB) is not used: Ollama does not use it,
  and the reranker on Metal (MPS) ran out of memory. Memory speed is not measured.
- Generator: Qwen3-4B-Instruct-2507, Q4_K_M GGUF, Ollama 0.33.2 (its llama.cpp runner),
  thinking off, default Ollama settings; the runner's process holds about 3.3 GB and uses
  about 380 % CPU while answering.
- Retrieval on the same machine, in a Python process: BM25 plus BGE-M3 dense vectors, fused by
  RRF; then bge-reranker-v2-m3 through sentence-transformers' `CrossEncoder` on the CPU
  (PyTorch, fp32) scores 20 candidates and keeps 5. Chunks of 800 characters with 200 overlap.
- One chat answer, measured on this machine (medians):
  - rerank: 27 s with no model loaded, about 100–130 s while the generator is loaded (we
    suspect memory pressure, not yet proven);
  - the prompt: about 2,270 tokens (fixed instructions first, then the 5 chunks, then the question),
    read in about 67 s (≈ 34 tokens/s);
  - generation: 100–300 tokens at about 4.3 tokens/s;
  - a second model call that scores the answer: about 68 s;
  - whole answer: 250–300 s median, p90 340–470 s.
- Over a long series of questions swap grows (in one series 0.8 → 4.1 GB) and everything
  slows; the operating system and our API share the 8 GB.
- Already planned levers (do not research these as such, but say if the literature changes
  their expected gain): fewer rerank candidates (20 → K); a shorter prompt; dropping the
  scoring call; a model-unload policy against swap; the order «rerank, then load the model».

## Questions

1. **Generation side (Ollama / llama.cpp on a 4-core AVX2 CPU):** for each lever — measured
   speed-up on similar CPUs, effect on output, how to switch it on in Ollama 0.33 (or only in
   llama-server), and the risk:
   - reuse of the KV cache for the fixed prompt prefix (prompt caching, `cache_prompt`, slot
     reuse, keep-alive), and how it depends on the prompt's order;
   - speculative decoding with a small draft model of the same family, and draft-free
     variants (prompt lookup / n-gram decoding, which fits answers that copy the context);
   - thread count and pinning on 4 cores without hyper-threading, batch and micro-batch size
     for prompt processing, flash attention on CPU, KV-cache quantisation (q8_0 / q4_0) and its
     measured quality loss, `num_ctx`, mmap / mlock;
   - other quantisation formats of the same model that run faster on AVX2 (for example
     Q4_0 with repacking, IQ4 types, online repacking), with their measured quality loss;
   - Ollama against llama-server directly on the same GGUF: measured differences.
2. **Expected tokens per second for a 4B Q4 model on this CPU class:** reported prompt and
   generation speeds on Kaby Lake / Skylake desktop i5 with DDR4; whether 4.3 tokens/s
   generation and 34 tokens/s prompt reading are normal for this class or a sign of a
   misconfiguration (what to check first).
3. **Rerank and embedding, the same models, faster:** bge-reranker-v2-m3 and BGE-M3 on a CPU —
   ONNX Runtime or OpenVINO export, int8 dynamic or static quantisation, bf16 / fp16 on CPUs
   without native support, thread settings, truncating the pair length, batching; measured
   speed-ups and measured ranking-quality loss (NDCG, MRR or recall on a public set), and
   which of these keeps the model «the same» in a fair sense.
4. **Memory on 8 GB:** how others run an LLM runner plus Python embedding / reranking models
   on 8 GB without swap — sharing threads between the two, unloading, smaller runtimes for the
   retrieval models, the memory of each option.
5. **Ranking for us:** the top 5 levers by expected seconds saved per answer on our machine,
   each with its evidence (measured or estimated — say which), the risk to answer quality, and
   how to test it in isolation: one lever, a few questions, time per stage, answers compared
   with the current ones on the same retrieved context.

## Rules for the report

- Every number with its source (link), its date and its setup (hardware, model, quantisation,
  prompt length); never invent a number. When a result is not found, say «не найдено» and what
  was searched. Mark vendor or marketing claims as such.
- Prefer primary sources (llama.cpp and Ollama repositories, issues, pull requests and
  discussions with benchmarks; ONNX Runtime / OpenVINO docs; papers); check a key number in a
  second source where possible.
- Separate facts from interpretation; mark the interpretation as such.
- Structure: summary (≤ 10 lines) → questions 1–4 (tables + notes) → the ranking → sources.
