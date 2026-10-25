# Research brief R4 — a fast checker of grounded answers that reads Russian, on a 4-core CPU

Write the report in Russian to `D:/RAG_new/.tmp/research/r4-russian-checker.md` (write nothing
else anywhere). Return only a short summary (≤ 15 lines). Read-only web research: do not post,
sign up or contact anyone. Up to ~25,000 characters.

## Why

We build a RAG support assistant: a customer asks, the system answers from a company's
documents and shows its sources, and an answer it cannot stand behind should go to a person.
Most of our bad answers carry a claim the retrieved documents do not hold, so the signal that
should send an answer to a person is a check of the answer's claims against its context.

Three earlier research runs found fast checkers (seconds on a CPU) only for English, and none
with a measured grounding quality in Russian. Our own check — the generator itself checking
the answer's claims — takes 81–235 s on our machine. This run looks only for the missing piece:
a checker that reads Russian, is fast on our CPU, and can be tested on our saved answers. Do
not repeat the general RAG metrics, benchmarks or treatment methods of the earlier runs.

## Our system

- Generator Qwen3-4B-Instruct-2507, Q4_K_M, Ollama on one Intel i5-7500 (4 cores, no GPU),
  8 GB RAM; the generator's process holds about 3.3 GB, and swapping slows everything, so a
  checker must fit beside it. One answer takes about 4–5 min.
- Context: 5 chunks of 800 characters (about 1,000–1,500 tokens), the answer 100–300 tokens.
- Languages: Russian (our own base) and English (three public bases); any corpus and domain,
  no hand-made dictionaries or per-domain rules.
- No person grades answers: labels come from an LLM judge (per answer: good / partial / bad,
  and per claim: supported or not by the context). Our Russian base has 100 judged answers:
  63 good, 20 partial, 17 bad or declined (the routing targets).
- Cheap signals already failed on these targets: the generator's self-score, the reranker's
  top score, decline phrases, the answer's script against the question's.
- Known so far (from the earlier runs, RAGTruth numbers): HHEM-2.1-open (0.1B; balanced
  accuracy 74.3 on QA), FactCG-DeBERTa-L (82.3), MiniCheck-Flan-T5-L (78.0), LettuceDetect-large
  (example F1 79.2) — all English only; the FLAN-T5 tokenizer maps Cyrillic to `<unk>`.
  mDeBERTa-v3-base-xnli reads Russian (XNLI ru 0.803) but was never measured on grounding.
- A new model in the product is the owner's decision; the research prepares that choice.

## Questions

1. **Checkers that read Russian**, published 2024 – October 2026: multilingual or Russian
   encoders trained for grounding, hallucination or NLI (for example XLM-R, mDeBERTa, mmBERT,
   EuroBERT, ruBERT / ruRoBERTa NLI models), multilingual versions of the English detectors
   above if any exist, small decoder verifiers (≤ 2B parameters) and guard models with a
   groundedness check, span-level hallucination detectors. For each: size, languages, the
   task it was trained on, its measured quality on grounding or hallucination detection
   (benchmark, metric, Russian or multilingual numbers where reported), context length,
   licence (mark non-commercial ones), CPU latency if reported. A table.
2. **Russian or multilingual datasets and benchmarks** for detecting unsupported claims or
   hallucinated spans in grounded answers (for example multilingual span-detection shared
   tasks, translated RAGTruth-style sets): which include Russian, their size, label level
   (span, claim, answer), the best reported results on Russian, and the licence.
3. **Cross-lingual transfer:** how much a detector trained on English loses on Russian where
   measured; translating context and answer to English with a small CPU translation model and
   then using an English checker — evidence of quality and the cost.
4. **The generator itself, cheaper:** checking all claims in one short call, scoring the
   probability of a «supported» token, checking only the sentences without a citation —
   measured accuracy against a full check and the time saved, for small models (≤ 8B).
5. **Calibration without people:** choosing a threshold against an LLM judge's labels when
   there are only ~100 answers and ~17 targets; how others validate a checker without human
   labels, and the risk of fitting the threshold to the same answers it is read on.
6. **Ranking for us:** the top 3–5 candidates. For each: the expected latency on 4 cores for
   a 1,500-token context and a 200-token answer (measured or estimated — say which), RAM,
   licence, the expected quality on Russian and its evidence, and how we would test it
   offline on our saved, judged answers (no new generation).

## Rules for the report

- Every number with its source (link), its date and its setup; never invent a number. When a
  result is not found, say «не найдено» and what was searched. Mark vendor or marketing
  claims as such.
- Prefer primary sources (papers, model cards, official leaderboards); check a key number in a
  second source where possible.
- Separate facts from interpretation; mark the interpretation as such.
- Structure: summary (≤ 10 lines) → questions 1–5 (tables + notes) → the ranking → sources.
