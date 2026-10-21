# Stage 2 retrieval baseline — 2026-10-21

All 415 registered retrieval questions completed on the stage-2 stand; none has a path
break. This publishes part 2's retrieval measurements and part 1's answer/context parity.
Stage 2 remains open: the external answers, context judge and final combined record remain.

Record: [`reports/stage2/retrieval-20261021/`](../../reports/stage2/retrieval-20261021/),
checked by [`tests/test_stage2_retrieval_artifact.py`](../../tests/test_stage2_retrieval_artifact.py).
The immutable export has a SHA-256 manifest. Its summaries and per-question rows contain
identifiers, hashes and measurements, with no external questions or document text.

## Provenance and method

The runs finished on 2026-10-20; the summaries were exported on 2026-10-21 without rerunning
retrieval. Stand: `5e308fe48cca0955c3007057a574a425f71e2a6a` on `deproject-mac`.
Indexes: the second generation, `/Users/julia/RAG_new_external_s1`, built at `e5e135a`.
Each record names its corpus manifest, chunk archive, index receipt, settings and tools by
SHA-256; its receipt must name the same chunk archive. BM25 and BGE-M3, 20 candidates each;
CPU reranker, five documents, parent expansion and the fitted stream prompt.

The registered selections and denominators are those of
[`stage2-four-corpora.md`](../specs/stage2-four-corpora.md). Retrieval ran without the answer
model. M3 uses the registered `external-gold/range-coverage-v1` rule; it does not grade an
answer. Time recorded here is not a speed decision: stage 4 requires its own idle-host run.

## Results

| Corpus | Completed | Questions with gold | Gold covered in the sent context |
|---|---:|---:|---|
| aircargo | 100 | Semantic context judge pending | All 100 prompts match those used for the 100 completed chat answers |
| aircargo-gr | 15 | Semantic context judge pending | Retrieval complete; no semantic quality claim yet |
| ConditionalQA | 100 | 80 | All evidence on 60/80 (75%); mean evidence recall 0.8337 |
| WixQA | 100 | 100 | At least one gold article on 68/100 (68%); mean gold-article coverage 0.6317 |
| MultiHop-RAG | 100 | 70 | All evidence on 10/70 (14.29%); mean evidence recall 0.4857 |

ConditionalQA's 20 unanswerable and MultiHop-RAG's 30 null questions are counted separately;
they never enter the gold-coverage denominator. All gold-bearing questions have their gold
in the index. These descriptive point estimates do not establish a difference between
systems; the final stage-2 record still owes the registered uncertainty estimates.

Every question has both retrieval lanes, a successful rerank and five expanded documents.
For all 250 external questions with gold, the K=20 replay reproduces the ranked five;
the record keeps the K=1…20 curve for stage 4. Vector-search replay at a smaller K remains
approximate, as registered; this does not select a new K.

Part 1's 100 answers completed in ten counted batches. Their routes were 97 `auto` and
3 `human`. The preserved answer summaries make the 100/100 prompt parity independently
checkable. The earlier answer judge's record stays at
[`reports/stage2/5e308fe/`](../../reports/stage2/5e308fe/); this export makes no new judge call.
