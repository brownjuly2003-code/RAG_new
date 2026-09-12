# GR-1b exact structural replay and stage ablations

Measured 2026-09-12 with source `bd4145f`, clean tree at measurement.
[Raw report](../../reports/gr/gr1b-stage-replay.json) pins code, corpus,
dataset, labels, configuration and recovered input hashes.
All **100/100** G1 outputs replay exactly, including texts, sources and metadata.
No model, embedding or reranker invocation was needed.

| arm | precision | recall | FULL/PART/MISS | precision delta CI95 | FULL losses | fact-loss cases |
|---|---:|---:|---|---|---:|---:|
| reranked_top_5 | 0.5067 | 0.9050 | 87/7/6 | [-0.048316, -0.033230] | 2 | 3 |
| coherence_only | 0.5416 | 0.8950 | 86/7/7 | [-0.009951, -0.002655] | 2 | 3 |
| expansion_only | 0.5125 | 0.9300 | 89/8/3 | [-0.042035, -0.027872] | 0 | 0 |
| g1_replay | 0.5475 | 0.9200 | 88/8/4 | [0.000000, 0.000000] | 0 | 0 |

Deltas and losses are against archived G1. All arms use the same original
reranked top-five and the 6000-character evaluation cap. Coherence is the
existing section grouping, ordering and pruning; expansion is the existing
section-neighbour algorithm with a 3600-character per-context budget.
`expansion_only` bypasses coherence, while `coherence_only` bypasses expansion.
The constructor fallback 2400 reproduced 98 cases; the configured default
3600 reproduces all 100. Exact replay supports this configuration, not a
claim that the original environment has been independently attested.

## Findings

Expansion without coherence loses no G1 keyword hits and yields one more
FULL, one fewer MISS, recall +0.01; precision falls by about 0.035.
Coherence alone raises lexical precision relative to unprocessed top-five
but lowers recall. The full combination retains expansion-supplied hits in
the three previously diagnosed oracle-infeasible cases; dropping expansion
would lose them. This is direct same-pool stage evidence, replacing the
earlier inability to separate structural processing from pool differences.

Every arm still misses precision 0.63. **NO-SHIP** for changing the default.
Substring keyword preservation is not semantic answer sufficiency. All 100
questions remain agent-written and unapproved, with repeated inspection;
bootstrap intervals are exploratory, conditional on these cases, without
shared-source clustering. The 15-question supplemental bucket is not measured.

## Recovered inputs

Read-only copies came from `deproject-mac`, directory
`/Users/julia/RAG_new_gr1b_results_4436d61/main-b8`. SHA-256 values matched
between Mac files and Windows copies before deterministic gzip archival:

- [Original pool](../../evaluation/gr1b-4436d61-prerank-pool.json.gz), raw SHA
  `97a2ab819db03431dabd6c79994d567eb1db5d202169b14d276aab5cf551767c`.
- [5,589 graph chunks](../../evaluation/gr1b-4436d61-graph-chunks.json.gz), raw SHA
  `5b35883f741deefc0698eb829f927413fc6588b72b9add9ee7697f3fc5806c94`.

Recovery checks case order, exact prerank texts/sources and the reranked
permutation, mapping by text plus source. Conflicting metadata for the same
key is rejected. A mismatch of reconstructed G1 text, metadata or source
aborts measurement. Numeric reranker scores remain unavailable. The original
[producer-attestation limits](gr1b-structure-graph.md) still apply.

```powershell
python -m scripts.gr1b_stage_replay
python -m pytest tests/test_gr1b_stage_replay.py tests/test_gr1b_controls.py tests/test_docs_hygiene.py -q -p no:schemathesis --basetemp=.tmp/pytest-stage-published
```

Tests reproduce all cases and intervals and reject an altered replay baseline.
Next: a bounded expansion experiment that preserves retrieved seed text under
the global cap, using these recovered inputs. Measure fact losses explicitly;
do not tune against expected answers. GR-4/GR-2/GR-3 remain on the plan.
