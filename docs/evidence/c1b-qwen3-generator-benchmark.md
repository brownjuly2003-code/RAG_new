# C.1b — Qwen3 8B generator benchmark

**Slice:** C.1b of phase C (`plan_06_09_26.md`) · **Evidence class:**
`measured` over `agent_labelled` · **Published:** 2026-09-11 · **Rule:** (c) —
a published quality number with provenance.

## What landed

The canonical Mac report is committed as
[`evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json`](../../evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json),
beside its [SHA-256 sidecar](../../evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json.sha256).
`tests/test_phase_c_qwen3_artifact.py` pins the bytes, provenance, configuration,
three complete runs, case order, per-run aggregates and final confidence
intervals. It also rebuilds the aggregates from all case rows.

The run happened on the Mac against a clean checkout of `b8ecc8e`, with Qwen3
thinking disabled. Each of seeds 42–44 completed all 100 cases; all 300 rows
have valid generation, LLM-judge and NLI results, and none has an error.

## Published result

| Metric | Mean | Run-level 95% CI |
|---|---:|---:|
| LLM faithfulness | 0.8986 | [0.8986, 0.8986] |
| NLI faithfulness | 0.9908 | [0.9908, 0.9908] |
| NLI supported-claim rate | 1.0000 | [1.0000, 1.0000] |
| Answer relevancy | 0.8095 | [0.8095, 0.8095] |
| Context precision | 0.506657 | [0.506657, 0.506657] |
| Context recall | 0.9050 | [0.9050, 0.9050] |
| Mean latency per case | 176.81 s | [105.34 s, 248.29 s] |

The LLM-faithfulness mean is 0.0014 below the phase-C 0.90 threshold. The
three quality runs are identical, so their run-level intervals are degenerate;
latency differs by run and its interval is correspondingly wide. This result
publishes the comparison input for C.4. It does not change the default model.

Context precision and recall match C.1a because both generator benchmarks use
the same hash-pinned cached contexts. They are retriever metrics in this
harness; the Qwen3 generator cannot move them. The answer-relevancy and
faithfulness changes therefore must not be described as retrieval gains.

## Provenance

| | |
|---|---|
| Source code | `b8ecc8efb780d423a267595584ef0927ebb77cc5` (`code_tree_clean: true`) |
| Dataset SHA-256 | `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720` |
| Cached contexts SHA-256 | `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10` |
| Generator | `qwen3:8b`, digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`, `think: false` |
| NLI judge | `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`, revision `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c` |
| Config | prompt `aircargo-context-only-ru-v1`; 3 × 100; seeds 42–44; temperature 0; `num_ctx=4096`; `num_predict=384`; context cap 6000; NLI batch 4; support threshold 0.5 |
| Report SHA-256 | `1663ea598b769af2aee6464c5da90a001b9187f83114217f03f6552856a70f5f` |

The report records an NLI-process peak RSS of 2,111,406,080 bytes and an
Ollama runtime size of 5,937,257,512 bytes. Neither is total-host peak RAM, so
C.4 must not present either value as a whole-machine memory measurement.

## What this is not

- **Not a shipment-resolution metric.** The questions are agent-authored over
  real documents, still `agent_labelled` with zero approvals, and the benchmark
  uses cached retrieval contexts rather than the shipment-status journey.
- **Not a precision improvement.** The cached-context digest is identical to
  C.1a, so precision remains the GR stream's gate.
- **Not a model flip.** C.4 owns that decision and must weigh faithfulness,
  relevancy, latency and the bounded memory evidence explicitly.
