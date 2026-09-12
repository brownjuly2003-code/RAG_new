# GR-1b seed reservation — NO-SHIP

Measured 2026-09-12, code `0b88362`, clean tree at measurement.
[Raw report](../../reports/gr/gr1b-seed-expansion.json) pins code, corpus,
dataset, label sidecars, recovered inputs and configuration. The existing
[structural replay](gr1b-stage-replay.md) must match all 100 G1 outputs before
this experiment runs. No models, network or new embeddings are required.

| arm | precision | recall | FULL/PART/MISS | precision delta CI95 | FULL losses | fact-loss cases |
|---|---:|---:|---|---|---:|---:|
| seed_reserved_top5 | 0.5119 | 0.9300 | 89/8/3 | [-0.042840, -0.028263] | 0 | 0 |
| seed_reserved_coherent | 0.5472 | 0.9200 | 88/8/4 | [-0.000810, 0.000000] | 0 | 0 |

Deltas and losses are against G1 (0.5475 / 0.9200, 88/8/4). Ordinary
expansion without coherence gives 0.5125 / 0.9300, so neither variant improves
its direct predecessor. All variants miss precision 0.63. Runtime unchanged.

## Contract and findings

Reserve the exact seed texts that fit the existing 6000-character cap in
rank order. Only the remaining space can be used by section expansion, whose
candidate text still comes from the unchanged 3600-character expansion rule.
Allocate remaining characters by seed rank, taking nearest preceding text
first, then following text. Preserve source order within each context; partial
neighbour text is allowed. If seeds alone exhaust the cap, keep their original
truncation and add nothing. Allocation receives no query, labels or answers.

Two prespecified variants isolate allocation with and without coherence.
Ordinary expansion displaces some capped seed text in **11/100** top-five
cases and **1/100** coherent cases. Reservation changes exactly those cases
and preserves capped seed text in every output. This establishes a text
preservation issue, but the correction produces no keyword-metric gain:
FULL/PART/MISS and recall match each respective ordinary expansion variant.
Guaranteeing seed preservation does not guarantee retention of all additional
neighbour facts on other datasets. These measurements lost no G1 keyword hits.

No further parameter search on this repeatedly inspected dataset follows this
result. Labels remain agent-written and unapproved; substring metrics do not
establish semantic sufficiency. Paired case-bootstrap intervals (2000 draws,
seed 42) are exploratory and omit shared-source dependence. Original producer
attestation limits remain those in the GR-1b capsule.

```powershell
python -m scripts.gr1b_seed_expansion
python -m pytest tests/test_gr1b_seed_expansion.py tests/test_gr1b_stage_replay.py tests/test_docs_hygiene.py -q -p no:schemathesis --basetemp=.tmp/pytest-seed-published
```

Tests verify reservation across cap boundaries and reproduce every case,
paired interval and input digest. This closes the bounded seed-expansion
experiment. Resume planned **GR-4 structural product wiring**: opt-in graph
path through `/api/ask`, trace retrieval path, Evidence tab and E2E proof;
then GR-2/GR-3 with the separate multi-hop bucket and held-out confirmation.
The graph default remains off; no quality gate is relaxed.
