# Stage 2 external answers — 2026-10-23

All 300 registered external answers completed on the stage-2 stand: 100 each on
ConditionalQA, WixQA and MultiHop-RAG, in 30 counted batches, with no path break. This
publishes part 4's answer collection and its prompt parity with part 2. It is **not** an
answer-quality grade: the registered judge (Claude) is unavailable, and no replacement judge
was used. Stage 2 remains open until the judge records exist.

Record: [`reports/stage2/external-answers-20261023/`](../../reports/stage2/external-answers-20261023/),
checked by [`tests/test_stage2_external_answers_artifact.py`](../../tests/test_stage2_external_answers_artifact.py).
The immutable export has a SHA-256 manifest. Its summaries and per-question rows contain
identifiers, hashes, counts and times — no external question, answer or document text.
Answers, prompts and traces stay in a private archive; the manifest pins its SHA-256 and
its 1,356 members.

## Provenance and method

Stand `5e308fe48cca0955c3007057a574a425f71e2a6a` on `deproject-mac`; Qwen3-4B-Instruct-2507
(`qwen3:4b-instruct-2507-q4_K_M`) on the CPU at the code defaults, the registered 3,600-s
limits. Indexes: the second generation, `/Users/julia/RAG_new_external_s1`, built at
`e5e135a`. Questions, order and batches are those of
[`stage2-four-corpora.md`](../specs/stage2-four-corpora.md); each batch ran on a fresh API with
the model unloaded. All 30 batches ran one configuration: their settings differ only by each
run's own trace and index-copy paths. Every tool is pinned by SHA-256 to its copy in
`reports/stage2/tools/` or `reports/stage1/tools/`.

Collection ran 2026-10-21 to 2026-10-23. On 2026-10-22 Julia reclaimed the Mac after WixQA
batch 4; the driver stopped before batch 5 by its stop file, and the 140 finished answers were
preserved and hash-checked. On her word the same driver resumed at WixQA batch 5, then
MultiHop-RAG. No batch was repeated or replaced; each appears once in the driver log as
complete with exit 0. ConditionalQA's summary re-derived after the resume is byte-identical
to the one captured at the pause.

## Results

| Base | Answers | Routed to a person | Median total, s | Median first token, s |
|---|---:|---:|---:|---:|
| ConditionalQA | 100 | 27 | 253.1 | 168.8 |
| WixQA | 100 | 24 | 256.4 | 165.1 |
| MultiHop-RAG | 100 | 33 | 275.0 | 180.2 |
| All three | 300 | 84 | 266.9 | 173.1 |

- **Path:** every answer HTTP 200, hybrid retrieval with a successful rerank, one retrieval
  per question; no question reached its cap; the longest took 719.3 s.
- **Language:** all 300 English questions got English answers, without one Cyrillic letter —
  stage 1's language fix holds on every external answer.
- **Parity:** each answer's prompt has the SHA-256 of part 2's retrieval prompt for the same
  question, 100/100 on each base. Part 2's published retrieval numbers are unchanged by the
  rewrite after the answers; only the parity field was filled.
- **Routing:** the chat sends an answer to a person exactly when its self-score is below 80.
  By registered stratum: ConditionalQA answerable 18/80, unanswerable 9/20; WixQA 24/100;
  MultiHop-RAG inference 13/70, null 20/30.

The routes and self-scores describe the product's behaviour, not answer correctness. Whether a
route was right is stage 3's question, and answer quality waits for the registered judge. The
times are from a run across three days, not an idle-host speed measurement; stage 4 owns speed.
