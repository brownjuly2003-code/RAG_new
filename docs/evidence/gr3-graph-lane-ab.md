# GR-3 — three-arm graph-lane A/B (`H` / `G1` / `G2`) on phase C and the multi-document bucket

**Measured 2026-09-18/19 on `deproject-mac`. Verdict: `NO_SHIP_TO_DEFAULT` — NO-SHIP-to-default.** `RAG_GRAPH_RETRIEVAL` stays at its default (`off`), unchanged, and the lane stays opt-in. Failed criteria: `retrieve_p95_within_200ms` — **fail** (phase-C total p95 delta +8765.2 ms over hybrid, threshold 200 ms); `llm_faithfulness_not_significantly_fallen` and `nli_faithfulness_not_significantly_fallen` — both `not_evidence`, because the generation half is `not_evidence`. `precision_rose` and `full_not_fallen` pass; they do not outweigh the failures. This capsule publishes the numbers required by `docs/specs/graph-lane-ab.md` (requirements 3 and 4) and `plan_06_09_26.md` §GR-3, whose gate demands this table before any default flip. Nothing was measured in this slice and no model runs here.

Numbers as rendered by `render_gr3_table(report)`, inserted verbatim:

```text
# GR-3 graph-lane A/B

schema gr-graph-lane-ab/v1.0

## phase_c retrieval

| class | H precision | H recall | H FULL/PART/MISS | Hm precision | Hm recall | Hm FULL/PART/MISS | G1 precision | G1 recall | G1 FULL/PART/MISS | G2 precision | G2 recall | G2 FULL/PART/MISS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aggregation | — | — | 0/0/0 | — | — | 0/0/0 | — | — | 0/0/0 | — | — | 0/0/0 |
| global | — | — | 0/0/0 | — | — | 0/0/0 | — | — | 0/0/0 | — | — | 0/0/0 |
| multi_hop | 0.5401 | 0.5000 | 0/1/0 | 0.5401 | 0.5000 | 0/1/0 | 0.4327 | 0.5000 | 0/1/0 | 0.4327 | 0.5000 | 0/1/0 |
| single_hop | 0.5063 | 0.9091 | 87/6/6 | 0.5063 | 0.9091 | 87/6/6 | 0.5487 | 0.9242 | 88/7/4 | 0.5499 | 0.9293 | 89/6/4 |
| all cases | 0.5067 | 0.9050 | 87/7/6 | 0.5067 | 0.9050 | 87/7/6 | 0.5475 | 0.9200 | 88/8/4 | 0.5487 | 0.9250 | 89/7/4 |

### deltas

| pair | class | precision | recall |
|---|---|---:|---:|
| G1 − H | aggregation | — | — |
| G1 − H | global | — | — |
| G1 − H | multi_hop | -0.1074 | 0.0000 |
| G1 − H | single_hop | 0.0424 | 0.0151 |
| G1 − H | all cases | 0.0408 | 0.0150 |
| G1 − Hm | aggregation | — | — |
| G1 − Hm | global | — | — |
| G1 − Hm | multi_hop | -0.1074 | 0.0000 |
| G1 − Hm | single_hop | 0.0424 | 0.0151 |
| G1 − Hm | all cases | 0.0408 | 0.0150 |
| G2 − G1 | aggregation | — | — |
| G2 − G1 | global | — | — |
| G2 − G1 | multi_hop | 0.0000 | 0.0000 |
| G2 − G1 | single_hop | 0.0012 | 0.0051 |
| G2 − G1 | all cases | 0.0012 | 0.0050 |
| G2 − H | aggregation | — | — |
| G2 − H | global | — | — |
| G2 − H | multi_hop | -0.1074 | 0.0000 |
| G2 − H | single_hop | 0.0436 | 0.0202 |
| G2 − H | all cases | 0.0420 | 0.0200 |
| G2 − Hm | aggregation | — | — |
| G2 − Hm | global | — | — |
| G2 − Hm | multi_hop | -0.1074 | 0.0000 |
| G2 − Hm | single_hop | 0.0436 | 0.0202 |
| G2 − Hm | all cases | 0.0420 | 0.0200 |
| Hm − H | aggregation | — | — |
| Hm − H | global | — | — |
| Hm − H | multi_hop | 0.0000 | 0.0000 |
| Hm − H | single_hop | 0.0000 | 0.0000 |
| Hm − H | all cases | 0.0000 | 0.0000 |

### contexts handed on

| arm | mean contexts | mean characters |
|---|---:|---:|
| H | 5.0000 | 3441.5 |
| Hm | 5.0000 | 3441.5 |
| G1 | 3.0400 | 2435.8 |
| G2 | 3.0400 | 2435.0 |

### keyword transitions

G1 − H counts: FULL->FULL: 86, FULL->PART: 1, MISS->FULL: 2, MISS->MISS: 3, MISS->PART: 1, PART->MISS: 1, PART->PART: 6
G1 − H FULL->MISS: none
G1 − H FULL->PART: aircargo-templates-checklist
G1 − H PART->MISS: aircargo-customs-special-cargo-manual-check
G1 − Hm counts: FULL->FULL: 86, FULL->PART: 1, MISS->FULL: 2, MISS->MISS: 3, MISS->PART: 1, PART->MISS: 1, PART->PART: 6
G1 − Hm FULL->MISS: none
G1 − Hm FULL->PART: aircargo-templates-checklist
G1 − Hm PART->MISS: aircargo-customs-special-cargo-manual-check
G2 − G1 counts: FULL->FULL: 88, MISS->MISS: 4, PART->FULL: 1, PART->PART: 7
G2 − G1 FULL->MISS: none
G2 − G1 FULL->PART: none
G2 − G1 PART->MISS: none
G2 − H counts: FULL->FULL: 86, FULL->PART: 1, MISS->FULL: 2, MISS->MISS: 3, MISS->PART: 1, PART->FULL: 1, PART->MISS: 1, PART->PART: 5
G2 − H FULL->MISS: none
G2 − H FULL->PART: aircargo-templates-checklist
G2 − H PART->MISS: aircargo-customs-special-cargo-manual-check
G2 − Hm counts: FULL->FULL: 86, FULL->PART: 1, MISS->FULL: 2, MISS->MISS: 3, MISS->PART: 1, PART->FULL: 1, PART->MISS: 1, PART->PART: 5
G2 − Hm FULL->MISS: none
G2 − Hm FULL->PART: aircargo-templates-checklist
G2 − Hm PART->MISS: aircargo-customs-special-cargo-manual-check
Hm − H counts: FULL->FULL: 87, MISS->MISS: 6, PART->PART: 7
Hm − H FULL->MISS: none
Hm − H FULL->PART: none
Hm − H PART->MISS: none

## multi_doc_bucket retrieval

| class | Hm precision | Hm recall | Hm FULL/PART/MISS | G1 precision | G1 recall | G1 FULL/PART/MISS | G2 precision | G2 recall | G2 FULL/PART/MISS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aggregation | 0.2510 | 0.6000 | 2/2/1 | 0.2809 | 0.5000 | 1/3/1 | 0.2809 | 0.5000 | 1/3/1 |
| global | — | — | 0/0/0 | — | — | 0/0/0 | — | — | 0/0/0 |
| multi_hop | 0.2536 | 0.4500 | 2/5/3 | 0.2612 | 0.3500 | 0/7/3 | 0.2612 | 0.3500 | 0/7/3 |
| single_hop | — | — | 0/0/0 | — | — | 0/0/0 | — | — | 0/0/0 |
| all cases | 0.2527 | 0.5000 | 4/7/4 | 0.2678 | 0.4000 | 1/10/4 | 0.2678 | 0.4000 | 1/10/4 |

### deltas

| pair | class | precision | recall |
|---|---|---:|---:|
| G1 − Hm | aggregation | 0.0299 | -0.1000 |
| G1 − Hm | global | — | — |
| G1 − Hm | multi_hop | 0.0076 | -0.1000 |
| G1 − Hm | single_hop | — | — |
| G1 − Hm | all cases | 0.0151 | -0.1000 |
| G2 − G1 | aggregation | 0.0000 | 0.0000 |
| G2 − G1 | global | — | — |
| G2 − G1 | multi_hop | 0.0000 | 0.0000 |
| G2 − G1 | single_hop | — | — |
| G2 − G1 | all cases | 0.0000 | 0.0000 |
| G2 − Hm | aggregation | 0.0299 | -0.1000 |
| G2 − Hm | global | — | — |
| G2 − Hm | multi_hop | 0.0076 | -0.1000 |
| G2 − Hm | single_hop | — | — |
| G2 − Hm | all cases | 0.0151 | -0.1000 |

### contexts handed on

| arm | mean contexts | mean characters |
|---|---:|---:|
| Hm | 5.0000 | 4042.1 |
| G1 | 2.9333 | 3108.3 |
| G2 | 2.9333 | 3108.3 |

### keyword transitions

G1 − Hm counts: FULL->FULL: 1, FULL->PART: 3, MISS->MISS: 4, PART->PART: 7
G1 − Hm FULL->MISS: none
G1 − Hm FULL->PART: aircargo-gr-compare-loss-damage-evidence, aircargo-gr-customs-export-readiness, aircargo-gr-offload-road-handover
G1 − Hm PART->MISS: none
G2 − G1 counts: FULL->FULL: 1, MISS->MISS: 4, PART->PART: 10
G2 − G1 FULL->MISS: none
G2 − G1 FULL->PART: none
G2 − G1 PART->MISS: none
G2 − Hm counts: FULL->FULL: 1, FULL->PART: 3, MISS->MISS: 4, PART->PART: 7
G2 − Hm FULL->MISS: none
G2 − Hm FULL->PART: aircargo-gr-compare-loss-damage-evidence, aircargo-gr-customs-export-readiness, aircargo-gr-offload-road-handover
G2 − Hm PART->MISS: none

## parity

### phase_c
G1m_vs_G1: identical
G2m_vs_G2: identical
Hm_vs_H: identical

### multi_doc_bucket
G1m_vs_G1: identical
G2m_vs_G2: identical

## latency

host: deproject-mac, Intel i5-7500, 8 GiB, macOS 13.7.8

### phase_c
| arm | cases | pools p50 | pools p95 | rerank p50 | rerank p95 | total p50 | total p95 | p95 total delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | 100 | 13.2000 | 17.7000 | 50044.7000 | 68455.6000 | 50055.6000 | 68472.5000 | — |
| G1 | 100 | 12.7000 | 17.2000 | 49946.8000 | 66337.8000 | 49961.9000 | 66355.9000 | -2116.6000 |
| G2 | 100 | 13.1000 | 19.7000 | 49284.7000 | 77221.2000 | 49298.5000 | 77237.7000 | 8765.2000 |

### multi_doc_bucket
| arm | cases | pools p50 | pools p95 | rerank p50 | rerank p95 | total p50 | total p95 | p95 total delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | 15 | 19.3000 | 58.0000 | 60455.2000 | 104331.2000 | 60472.1000 | 104389.2000 | — |
| G1 | 15 | 19.6000 | 24.0000 | 59565.3000 | 104524.1000 | 59583.6000 | 104545.9000 | 156.7000 |
| G2 | 15 | 32.8000 | 39.3000 | 132715.6000 | 155548.7000 | 132748.4000 | 155578.4000 | 51189.2000 |

## generation

paired case-level percentile bootstrap; resamples=10000; seed=20260918; cases=99
hybrid evidence: measured
graph evidence: not_evidence (run 1 failed_cases=1; run 2 failed_cases=1; run 3 failed_cases=1)
excluded: aircargo-business-trip-foreign-approval
graph mean context_count: 3.04

| metric | hybrid | graph | difference | 95% CI | better | worse | equal |
|---|---:|---:|---:|---|---:|---:|---:|
| answer_relevancy | 0.8949 | 0.8859 | -0.0091 | [-0.0293, 0.0101] | 16 | 18 | 65 |
| context_precision | 0.5078 | 0.5498 | 0.0420 | [0.0341, 0.0496] | 89 | 8 | 2 |
| context_recall | 0.9040 | 0.9242 | 0.0202 | [-0.0101, 0.0556] | 4 | 2 | 93 |
| latency_ms | 198110.0438 | 100707.6128 | -97402.4310 | [-106804.4781, -88541.4040] | 1 | 98 | 0 |
| llm_faithfulness | 0.8278 | 0.8005 | -0.0273 | [-0.0591, 0.0061] | 15 | 30 | 54 |
| nli_faithfulness | 0.8909 | 0.8877 | -0.0032 | [-0.0496, 0.0429] | 38 | 48 | 13 |
| nli_supported_claim_rate | 0.8994 | 0.8999 | 0.0004 | [-0.0470, 0.0485] | 16 | 15 | 68 |

### run-level aggregates

hybrid_aggregate:
- answer_relevancy: mean=0.8960 [0.8960, 0.8960]
- context_precision: mean=0.5067 [0.5067, 0.5067]
- context_recall: mean=0.9050 [0.9050, 0.9050]
- llm_faithfulness: mean=0.8295 [0.8295, 0.8295]
- mean_latency_ms: mean=197501.8300 [192103.9417, 202899.7183]
- nli_faithfulness: mean=0.8919 [0.8916, 0.8923]
- nli_supported_claim_rate: mean=0.9004 [0.9004, 0.9004]
graph_aggregate:
- answer_relevancy: mean=0.8770 [0.8770, 0.8770]
- context_precision: mean=0.5487 [0.5487, 0.5487]
- context_recall: mean=0.9250 [0.9250, 0.9250]
- llm_faithfulness: mean=0.7925 [0.7925, 0.7925]
- mean_latency_ms: mean=100277.0000 [95265.2853, 105288.7147]
- nli_faithfulness: mean=0.8888 [0.8888, 0.8888]
- nli_supported_claim_rate: mean=0.9009 [0.9009, 0.9009]

## decision

verdict: NO_SHIP_TO_DEFAULT

| criterion | status |
|---|---|
| full_not_fallen | pass |
| llm_faithfulness_not_significantly_fallen | not_evidence (hybrid=measured; graph=not_evidence) |
| nli_faithfulness_not_significantly_fallen | not_evidence (hybrid=measured; graph=not_evidence) |
| precision_rose | pass |
| retrieve_p95_within_200ms | fail (host=deproject-mac, Intel i5-7500, 8 GiB, macOS 13.7.8; delta_ms=8765.2) |
failed: llm_faithfulness_not_significantly_fallen, nli_faithfulness_not_significantly_fallen, retrieve_p95_within_200ms
```

## Parity — the arms are the published ones

- All five parity checks are `identical`: `Hm` vs `H`, and `G1m`/`G2m` vs `G1`/`G2`, on phase C and on the bucket. Every re-run is identical case by case to its published pool — `Hm` to `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10` (the hybrid pool C.1a generated from), `G1m`/`G2m` to the GR-2 archives — across `cands`, `cand_sources`, `prerank_cands`, `prerank_sources`, `reranked_cands`, `reranked_sources` and the top-5 fields, with zero differing cases.
- On the raw rows, `Hm` differs from `H` in the added `timing_ms` and in `rerank_s` on all 100 phase-C rows (both re-measured); the candidate and source fields are identical case by case, which is why `H` and `Hm` agree on every retrieval number.
- The generation contexts `aa5bf94c2e12f7de29b20e625cf1a338320b7fc82feeb95072bfb5a68e38a654` are the published GR-2 `G2` phase-C archive; no fresh pool was produced for this slice.

## Retrieval

**Phase C (100 cases).** `G2` − `H`: precision +0.0420 (0.5067 → 0.5487), recall +0.0200 (0.9050 → 0.9250), FULL 87 → 89 (PART/MISS 7/4 vs 7/6). `G1` sits between: 0.5475 / 0.9200, FULL 88. Keyword losses vs hybrid: `aircargo-templates-checklist` (FULL→PART) and `aircargo-customs-special-cargo-manual-check` (PART→MISS).

**Multi-document bucket (15 cases).** Both graph arms raise precision by +0.0151 (0.2527 → 0.2678) but cut recall by 0.1000 (0.5000 → 0.4000) and FULL from 4 to 1; the three FULL→PART cases are `aircargo-gr-compare-loss-damage-evidence`, `aircargo-gr-customs-export-readiness` and `aircargo-gr-offload-road-handover`. The graph arms hand on 2.9333 contexts per case against 5.0000 for hybrid. `G2` equals `G1` on every bucket retrieval-quality number. This is a measured result that counts against the lane for multi-document questions; the report does not establish a cause, and none is claimed here.

## Latency and the failed criterion

Host: `deproject-mac, Intel i5-7500, 8 GiB, macOS 13.7.8`. Retrieve time per case is the pools stage plus rerank. The pools stage is milliseconds — phase-C p95 17.7 ms (hybrid), 17.2 ms (`G1`), 19.7 ms (`G2`) — while the reranker takes about 50 s per case on this host at `RAG_RERANK_BATCH=8` (phase-C rerank p50 49.3–50.0 s across the arms).

Five of the six phase-C lane cases (five routed `global`, one `multi_hop`) are the five slowest `G2` cases, spanning 92.7–134.3 s total, with prerank pools of 73–90 candidates against at most 40 for hybrid. The nearest-rank p95 of 100 cases is the 95th value, so it falls on the next case: `aircargo-breach-notification-required-fields`, 77.2 s of rerank for `G2` (total p95 77237.7 ms), against `aircargo-dangerous-goods-fields`, 68.5 s for hybrid (total p95 68472.5 ms). Delta +8765.2 ms against the 200 ms threshold: **fail**. (`G1` phase-C p95 is 66355.9 ms, −2116.6 ms vs hybrid; bucket p95 deltas are +156.7 ms for `G1` and +51189.2 ms for `G2`.)

This is an 8 GiB Intel Mac, not production hardware, and the rule is evaluated on the host that measured it.

## Generation — `not_evidence`

- The locked C.1a contract holds; the report's `paired_generation` check enforces it. The run differs from C.1a in its contexts (`aa5bf94c…` vs `91ce1745…`), in its code (`32de532` vs `c06bdf5`) and in `--allow-short-contexts` (mean `context_count` 3.04).
- Why the report is `not_evidence`: in each of the 3 runs, `aircargo-business-trip-foreign-approval` has `llm_judge_valid: false`. The judge answered `'Score: 1.0'`, which the strict parser rejects as prose. The row does not say which of the two judge prompts answered that, so none is named here. That leaves 297/300 valid rows — 99 in each run — and 99 paired cases; the report's three reasons are `run 1 failed_cases=1`, `run 2 failed_cases=1`, `run 3 failed_cases=1`.
- The benchmark writes 0.0 for both LLM scores of an invalid row and still averages it, so its run-level LLM faithfulness 0.7925 is not comparable with C.1a's 0.8295; the paired means over the 99 comparable cases are.
- Paired (hybrid → graph): LLM faithfulness 0.8278 → 0.8005, difference −0.0273, 95% CI [−0.0591, 0.0061]; NLI faithfulness 0.8909 → 0.8877, difference −0.0032, 95% CI [−0.0496, 0.0429]. Both are recorded as `not_evidence` rather than pass.
- Generation time per case: 197.5 s (C.1a) vs 100.3 s run-level; the paired difference is −97.4 s (95% CI −106804.5 to −88541.4 ms).

## Decision

| criterion | evidence | status |
|---|---|---|
| `precision_rose` | phase-C `G2` 0.5487 vs `H` 0.5067 | pass |
| `full_not_fallen` | phase-C FULL 89 (`G2`) vs 87 (`H`) | pass |
| `retrieve_p95_within_200ms` | total p95 77237.7 ms vs 68472.5 ms; delta +8765.2 ms > 200 ms | fail |
| `llm_faithfulness_not_significantly_fallen` | difference −0.0273, CI [−0.0591, 0.0061]; graph half `not_evidence` | not_evidence |
| `nli_faithfulness_not_significantly_fallen` | difference −0.0032, CI [−0.0496, 0.0429]; graph half `not_evidence` | not_evidence |

**Verdict: `NO_SHIP_TO_DEFAULT`.** The verdict does not depend on the invalid case: the retrieve criterion fails on measured retrieval inputs alone.

## Provenance

- Report `reports/gr/gr3-graph-lane-ab.json` — schema `gr-graph-lane-ab/v1.0`, `evidence_class: measured`.
- Report builder: `scripts/gr3_graph_lane_ab.py` (T-29 plus T-30's evidence-class guard) at commit `f0679a6da857cca2df48aee3353369649962a13e`.
- Measurement code (clean clones, T-28): `32de5324454ffbaa72b2b29bd41e466f0664e32a`.
- Host `deproject-mac, Intel i5-7500, 8 GiB, macOS 13.7.8`; device auto = `mps`.
- Environment `RAG_EMBED_BATCH=8 RAG_RERANK_BATCH=8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`; embedder `BAAI/bge-m3`; reranker `BAAI/bge-reranker-v2-m3`; `retr_k` 20; chunks 800/200.
- Retrieval venv `/Users/julia/RAG_Support_Assistant/.venv`: sentence-transformers 2.7.0, transformers 4.44.2, torch 2.2.2. Benchmark venv `/Users/julia/RAG_new_venvs/c1a`: transformers 4.41.2, torch 2.2.2, httpx 0.27.2. Ollama 0.33.2.
- Model `qwen2.5:7b` `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`; NLI `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` @ `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c`.
- Embeddings cache `chunks.npz` `3fcfaf2803187b73d42f0d25256dfbea5b4997bce28d2c4ad47fbe0985b2ab33`, reused from the GR-2 run; the pools stage loaded 5589 cached embeddings.
- The classification caches and the extraction manifest are identical to the GR-2 archives; preflight checked this.
- Corpus `c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343`, 201 files, manifest `evaluation/aircargo_corpus.manifest.json` (`2b2e9232e69b4f52a55237f3ee620f34c91d1900383877c2310ba616c6590444`).

Datasets (digests from the report):

| dataset | dataset SHA-256 | sidecar SHA-256 | label-manifest SHA-256 |
|---|---|---|---|
| phase C | `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720` | `cc6356b9faa46d4b952a955e1d47e9a8b15003284c42f48e7e5236471f8ff17c` | `e2010fc94ee283c29308e6fa53e522c70b57d767aacf00113628858a061f7b10` |
| multi-doc bucket | `0949d7563983b96500074e61f10274b28cb9341612206e02733a59b5c7968f5f` | `a4bf3433bf3b73a7d20741516d911b70aec7ad7488838cff34bc32928079c719` | `4f5417e7da1ef3dee4a106b36d1fb43e4d9fa7c298068029f6b3fd9dd911db77` |

Generation reports: hybrid (C.1a) `ac8d9cc20a8d414490fd0ada46e35731d7a2891e7169c3ec22ef88a4644db534`; graph `evaluation/gr3-g2-qwen25-7b-32de532-phase-c-generator-benchmark.json` = `76308bc8963b15c73ab9d75745f444068b2046a86864f2d786e88ccde2f9ada2` (1000646 bytes), with its `.json.sha256` sidecar in the same format as C.1a's.

Archives in `evaluation/` placed by the orchestrator (gzip, mtime 0; SHA-256 and bytes are of the uncompressed bytes):

| archive | SHA-256 (uncompressed) | bytes |
|---|---|---:|
| `gr3-32de532-phase-c-Hm-candidates.json.gz` | `0e93f6e82edc2830269baa803fab8f677fe3fda0803c5afccdfb5289960c2d55` | 7702433 |
| `gr3-32de532-phase-c-G1m-candidates.json.gz` | `cd139b0b113ce642613d955914e34d104a1eb74d258b56f311aae084e80feb7d` | 8350434 |
| `gr3-32de532-phase-c-G2m-candidates.json.gz` | `fb7a22613514434042695a531f85dae8b319c150e5c3ef25e50bdbf47745792e` | 8893910 |
| `gr3-32de532-bucket-Hm-candidates.json.gz` | `3a3020799e8310fcaf3532783cae9d83f8f03b3b0a741488b425ac7edec0aeee` | 1357434 |
| `gr3-32de532-bucket-G1m-candidates.json.gz` | `955c74d810e86282cf88a61c670ee9c241f0434763dad7d8206164e093370c93` | 1473362 |
| `gr3-32de532-bucket-G2m-candidates.json.gz` | `df4486ffe45a3244cf1d2254b3859570e8cb046258983326d0b43e05c3ba505d` | 2691353 |
| `c1a-c06bdf5-phase-c-C-candidates.json.gz` | `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10` | 7692098 |

Published GR-2 arms used as `G1`/`G2` (uncompressed digests, from the report): phase-C `G1` `6848b5f33787ca7a91c3137a5f7da90c0b532093048245d378e296a53482a059`; phase-C `G2` `aa5bf94c2e12f7de29b20e625cf1a338320b7fc82feeb95072bfb5a68e38a654` (also the generation contexts); bucket `G1` `17db60197eaa7df9173f1c9377368996cbe1600254670057ef9dc397e3f0762b`; bucket `G2` `73a11d8fa11bd75b8ef9a3319f0659426cc6f9f1c86c95cb3412c56d3cfbec9d`.

## The run

- Started 2026-09-18T13:04:35Z (`RUN code=32de532…`); preflight 47 s rc=0; `ollama_stop` 5 s.
- All 18 retrieval stages returned rc=0 (`failed_stages=0`); retrieval finished 18:30:46Z. Stage times — phase C: `C` pools 65 s / rerank 5085 s; `G2` 87 / 5302 s; `G1` 77 / 5028 s. Bucket: `C` 58 / 963 s; `G2` 60 / 1799 s; `G1` 53 / 939 s. Each parity stage ≤ 1 s.
- Generation ran 18:30:47Z → 2026-09-19T03:30:57Z (32410 s) and exited 1, because the benchmark exits 1 on `not_evidence`. The driver therefore logged `ABORT at generation rc=1` and skipped its last stage, the model unload. The supplied log ends at that line; it does not show what happened to loaded models afterwards.

## Reproduction

No fresh benchmark is run. Reproduce the checks with:

```
python -m pytest -q -p no:schemathesis tests/test_gr3_artifact.py tests/test_gr3_graph_lane_ab.py tests/test_docs_hygiene.py --basetemp=.tmp/pytest-gr3-artifact
```

`tests/test_gr3_artifact.py` decompresses the eleven archives into `tmp_path`, verifies each uncompressed SHA-256 and size against a pinned table, rebuilds the report once (module-scoped fixture; the bootstrap is 10000 resamples) with the same arguments as the CLI and compares it to the published JSON as a whole object, checks the generation report's digests and provenance (`code_sha` `32de532…`, `contexts_sha256` equal to the GR-2 `G2` archive digest, `allow_short_contexts: true`, `evidence_class` `not_evidence` with exactly the three reasons, one invalid row per run with `'Score: 1.0'`), confirms `H` is C.1a's pool, asserts the verdict and all five criterion statuses, the five `identical` parity blocks, the 99 paired cases with exactly the one excluded id, the bucket FULL→PART ids and the latency facts recomputed from the archived `G2m`/`Hm` rows (slowest cases, lane membership, prerank sizes, the rank-95 value), and checks this capsule's required digests and phrases. No model runs, no network is used, no corpus file is read.

## Limits

- Labels are `agent_labelled`, 0 approved.
- Phase C is 99 `single_hop` by label; the lane ran on 6 of 100 cases.
- There is one generation run and it covers `G2` only; no `G1` generation exists, so `G1`'s better phase-C latency decides nothing.
- The generation half is `not_evidence` (297/300 valid rows).
- The latency comes from one host.

## Next step

- The default stays `off` (unchanged), and the entity lane stays off by default.
- The plan's eval-based signal for `ingestion/graph_activation.py` — 'auto if the multi-hop bucket improves in GR-3' — is negative on this corpus: the bucket's recall and FULL fell. The activation gate is therefore not loosened, and `auto` keeps today's chunk-and-connectivity rule, under which this corpus (5589 chunks) resolves to disabled.
- The ADR 0001 postscript and the state documents are the next task; they are not edited here.
