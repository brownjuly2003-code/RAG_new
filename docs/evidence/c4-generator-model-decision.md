# C.4 — Generator default model decision: NO-SHIP `qwen3:8b`

**Decision item:** C.4 of phase C (`plan_06_09_26.md`) · **Date:** 2026-09-21 ·
**Decision:** NO-SHIP. The default generator remains `qwen2.5:7b`; no
defaults change. This document decides on the two existing measured C.1
reports; it adds no new measured slice and no new benchmark.

## Canonical inputs

- C.1a (incumbent): [`evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json`](../../evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json), created 2026-08-30.
- C.1b (candidate): [`evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json`](../../evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json), created 2026-09-08, beside its [SHA-256 sidecar](../../evaluation/c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json.sha256).

Both are `evidence_class: measured`; every aggregate reports n=3 over 100
cases, and values below are rounded from these JSONs for display.

## Comparison (published aggregates; run-level 95% Student-t CIs, n=3)

| Metric | qwen2.5:7b (C.1a) | qwen3:8b (C.1b) | Note |
|---|---:|---:|---|
| LLM faithfulness (gate ≥ 0.90) | 0.8295 [0.8295, 0.8295] | 0.8986 [0.8986, 0.8986] | both miss; qwen3 short by 0.0014 |
| NLI faithfulness (supporting) | 0.8919 [0.8916, 0.8923] | 0.9908 [0.9908, 0.9908] | favors qwen3; not a gate |
| NLI supported-claim rate | 0.9004 | 1.0000 | supporting only |
| Answer relevancy | 0.8960 | 0.8095 | regression −0.0865 |
| Mean latency per case | 197.50 s [192.10, 202.90] | 176.81 s [105.34, 248.29] | CIs overlap; significance not established |
| Ollama runtime size | 5,062,566,870 B | 5,937,257,512 B | not host peak; +874,690,642 B |
| NLI process peak RSS | 2,124,476,416 B | 2,111,406,080 B | not host peak; not summable |

Context precision (0.506657) and recall (0.9050) are identical across the
two reports because both consumed the same hash-pinned cached contexts
(`91ce1745…8ff10`). They are retriever metrics in this harness and are
excluded as model-selection criteria.

## Rationale

1. **The faithfulness gate fails for both models.** The phase-C gate is LLM
   faithfulness ≥ 0.90: incumbent 0.8295, candidate 0.8986. A switch that
   still ships a below-gate generator cannot pass on "closer to the gate";
   NO-SHIP follows from the gate alone.
2. **NLI is supporting evidence, not a gate replacement.** qwen3's NLI
   faithfulness 0.9908 and supported-claim rate 1.0000 corroborate a
   direction but do not override the failed LLM-judge gate.
3. **Answer relevancy regresses (secondary limitation).** 0.8960 → 0.8095.
   The switch would buy a still-failing faithfulness at the cost of a
   measured relevancy regression.
4. **Latency does not decide.** qwen3's mean is lower (176.81 s vs
   197.50 s) but its interval [105.34 s, 248.29 s] overlaps the
   incumbent's [192.10 s, 202.90 s]; no significance claim is made.
5. **Memory evidence is bounded and non-decisive.** qwen3's Ollama runtime
   footprint is 874,690,642 B larger and NLI peak RSS is near-identical;
   neither is host peak RAM, and they cannot be summed into a host figure.

## Limitations

- LLM-judge quality scores are identical across seeds within each report,
  so their run-level CIs are degenerate. C.1a NLI faithfulness varies
  slightly. These run-level intervals do not estimate uncertainty across
  unseen cases; no broad generalization follows.
- Single host (macOS-13.7.8 x86_64, Python 3.11.15), single prompt
  `aircargo-context-only-ru-v1`, one `agent_labelled` dataset (zero
  approvals); qwen3 measured with `think: false`.
- n=3 runs; latency intervals are wide and overlapping.

## Provenance

| | C.1a | C.1b |
|---|---|---|
| Code SHA (`code_tree_clean: true`) | `c06bdf5721b434eff32dcf5b9991221d5b2a15f8` | `b8ecc8efb780d423a267595584ef0927ebb77cc5` |
| Dataset SHA-256 | `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720` | identical |
| Cached contexts SHA-256 | `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10` | identical |
| Generator digest | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` | `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` |
| NLI judge | `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` @ `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c` | identical |
| Report SHA-256 | `ac8d9cc20a8d414490fd0ada46e35731d7a2891e7169c3ec22ef88a4644db534` | `1663ea598b769af2aee6464c5da90a001b9187f83114217f03f6552856a70f5f` |

Shared config: 3 × 100 cases; seeds 42–44; temperature 0.0;
`num_ctx=4096`; `num_predict=384`; context cap 6000 chars; NLI batch 4;
support threshold 0.5; both models Q4_K_M GGUF (7.6B vs 8.2B params).

## Verification status

The C.1 artifact tests pin the report bytes, provenance, and config and
rebuild the aggregates from case rows; this decision reuses those
published numbers without re-measuring. On 2026-09-21, the Mac ran
`python -m pytest tests/test_phase_c_baseline_artifact.py tests/test_phase_c_qwen3_artifact.py -q -p no:schemathesis -p no:cacheprovider`: **2 passed**, exit 0.
Independent review checked the table, hashes and limitations against those
reports. Retaining the incumbent is not a claim that it meets the quality gate.

## Next step

C.3: default-off contract-shaped shipment-status answers. That is the next
decision-relevant evidence. C.4 deliberately does not open another
benchmark or another model A/B.