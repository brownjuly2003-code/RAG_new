# Preliminary H evidence-loss map — slice 2.5 (T-63)

**Evidence proxy, not gold:** H has no gold spans. Required terms are the agent-authored
`expected.answer_contains` labels; existing phase-C/P1 `_kw_status` is reused
(lowercase substring, including underscores/punctuation). This is not semantic
`evidence_recall_pool`, `all_evidence_coverage` or `fact_coverage` and proves no
answer sufficiency. An absent corpus term could be a label problem, not pipeline loss.

Registered before counting — G2 RU→EN definition: Cyrillic letter in query and ASCII Latin letter in at least one required term; case-level lexical RU-to-EN proxy, registered before counting.
This does not establish the evidence document's language or multilingual semantic recall.

## Stages and scope

Index uses the archived GR-1b chunk set because it exists; no external corpus directory
is needed. It shares arm-C structural/contextual chunking, but no archived index manifest
attests byte identity with the older C.1a index. Its coverage is a snapshot proxy.
A term must match inside one chunk. Initial per-source candidates before caps are
**not observable**. `prerank_cands` (hybrid) and original G1 pool `cands` are already
after RRF/caps/dedup, exactly the reranker input. P1 score files contain scores aligned
to that pool, not another earlier pool. Hybrid sent context is phase-C cached top-five
under the evaluation cap. G1 is a separate diagnostic lane with structural processing.

First loss is the earliest absent required term at an observed stage; later recovery
does not erase it. Index→pool losses span retrieval and caps/dedup: their cause is unknown.
Pool→sent losses are **between pool and sent context — stage unknown**
(rerank / selection / coherence not observable). No loss is attributed to rerank.
Grading, answer and API parity remain unknown. These archived contexts are harness
contexts, not an attestation of production `/api/ask` packing.

Counts below use case-term occurrences. Missing-at-stage counts can overlap; first-loss
counts partition the population. RU→EN rows include all required terms of selected cases.

| lane / stratum | stage | observed cases / denominator | missing-any cases | observed terms / denominator | missing terms | FULL/PART/MISS |
|---|---|---:|---:|---:|---:|---|
| hybrid/summary | index | 100/100 | 0 | 200/200 | 0 | 100/0/0 |
| hybrid/summary | initial_pool: not observable | 0/100 | N/A | 0/200 | N/A | N/A |
| hybrid/summary | after_caps_dedup | 100/100 | 4 | 200/200 | 8 | 96/0/4 |
| hybrid/summary | sent_context | 100/100 | 13 | 200/200 | 19 | 87/7/6 |
| hybrid/ru_to_en | index | 55/55 | 0 | 110/110 | 0 | 55/0/0 |
| hybrid/ru_to_en | initial_pool: not observable | 0/55 | N/A | 0/110 | N/A | N/A |
| hybrid/ru_to_en | after_caps_dedup | 55/55 | 4 | 110/110 | 8 | 51/0/4 |
| hybrid/ru_to_en | sent_context | 55/55 | 11 | 110/110 | 17 | 44/5/6 |
| graph/summary | index | 100/100 | 0 | 200/200 | 0 | 100/0/0 |
| graph/summary | initial_pool: not observable | 0/100 | N/A | 0/200 | N/A | N/A |
| graph/summary | after_caps_dedup | 100/100 | 4 | 200/200 | 8 | 96/0/4 |
| graph/summary | sent_context | 100/100 | 12 | 200/200 | 16 | 88/8/4 |
| graph/ru_to_en | index | 55/55 | 0 | 110/110 | 0 | 55/0/0 |
| graph/ru_to_en | initial_pool: not observable | 0/55 | N/A | 0/110 | N/A | N/A |
| graph/ru_to_en | after_caps_dedup | 55/55 | 4 | 110/110 | 8 | 51/0/4 |
| graph/ru_to_en | sent_context | 55/55 | 9 | 110/110 | 13 | 46/5/4 |

| lane / stratum | first observed loss | cases / denominator | terms / denominator |
|---|---|---:|---:|
| hybrid/summary | index_absent_proxy | 0/100 | 0/200 |
| hybrid/summary | index_to_after_caps_unknown | 4/100 | 8/200 |
| hybrid/summary | pool_to_sent_unknown | 9/100 | 11/200 |
| hybrid/summary | no_observed_loss | 87/100 | 181/200 |
| hybrid/ru_to_en | index_absent_proxy | 0/55 | 0/110 |
| hybrid/ru_to_en | index_to_after_caps_unknown | 4/55 | 8/110 |
| hybrid/ru_to_en | pool_to_sent_unknown | 7/55 | 9/110 |
| hybrid/ru_to_en | no_observed_loss | 44/55 | 93/110 |
| graph/summary | index_absent_proxy | 0/100 | 0/200 |
| graph/summary | index_to_after_caps_unknown | 4/100 | 8/200 |
| graph/summary | pool_to_sent_unknown | 10/100 | 12/200 |
| graph/summary | no_observed_loss | 86/100 | 180/200 |
| graph/ru_to_en | index_absent_proxy | 0/55 | 0/110 |
| graph/ru_to_en | index_to_after_caps_unknown | 4/55 | 8/110 |
| graph/ru_to_en | pool_to_sent_unknown | 7/55 | 9/110 |
| graph/ru_to_en | no_observed_loss | 44/55 | 93/110 |

Official lexical ruler beside the proxy (target is diagnostic here):

| lane | cases | context precision | context recall | phase-C target |
|---|---:|---:|---:|---:|
| hybrid | 100 | 0.5067 | 0.9050 | 0.63 |
| graph | 100 | 0.5475 | 0.9200 | 0.63 |

## G3: expansion and evaluation-cap diagnostics

The replay contrast uses its **archived normalized hits**, distinct from the raw
FULL/PART/MISS matcher above. `expansion_only` vs `reranked_top_5` changes section
expansion and then applies the same evaluation cap; uncapped section losses cannot
be separated from cap losses in that report. It is outside the main causal map.

| diagnostic | case denominator | term denominator | present-before terms | lost cases | lost terms | gained cases | gained terms |
|---|---:|---:|---:|---:|---:|---:|---:|
| section expansion + cap (normalized) | 100 | 200 | 181 | 0 | 0 | 3 | 5 |
| hybrid cap only (raw) | 100 | 200 | 181 | 0 | 0 | 0 | 0 |
| graph cap only (raw) | 100 | 200 | 184 | 0 | 0 | 0 | 0 |

P1b parent-expanded arms archive aggregate rulers and selection losses, not expanded
texts or per-case capped hits. Expansion-only and cap-only term losses are **not
observable**. Uncapped→capped status totals below are marginals, not paired transitions;
selection-vs-expanded-control losses are not attributed to parent expansion.
Selection-loss terms use P1b's archived normalized matches. Lost-term denominators
are the present-before terms for paired contrasts; gained-term denominators are
the remaining required terms. P1b selection losses use all required terms because
the expanded control's per-case matched terms are not archived.

| P1b H arm | case denominator | term denominator | uncapped FULL/PART/MISS | capped FULL/PART/MISS | selection-loss cases | selection-loss terms |
|---|---:|---:|---|---|---:|---:|
| top_k_5+exp | 100 | 200 | 97/2/1 | 89/7/4 | 0 | 0 |
| rel_0.2+exp | 100 | 200 | 96/2/2 | 89/7/4 | 1 | 2 |
| p1_cv+exp | 100 | 200 | 94/3/3 | 88/7/5 | 3 | 5 |
| top_k_3+exp | 100 | 200 | 94/4/2 | 91/5/4 | 3 | 4 |

## Index-stage losses — fix before the 2.5 baseline

Absent-index term occurrences: 0.
Every required term has an individual archived-chunk witness (ordinal, source, text SHA
in JSON). No ingestion/index loss or absent-corpus label problem is demonstrated by
this proxy. Gold-span cuts and incorrect labels can still be missed. No ingestion fix
is made in this slice; any later proven loss requires a separate fix before baseline.

## Per-case first observation

`initial_pool` is not observable for every case. Term-level presence at each stage,
index witnesses and sent-text hashes are in the linked JSON. Main hybrid and G1
results remain separate; `unknown` never names a hidden mechanism.

| H case | RU→EN | hybrid first loss | graph first loss |
|---|---|---|---|
| `aircargo-probation-data` | no | no_observed_loss | no_observed_loss |
| `aircargo-probation-extend` | no | no_observed_loss | no_observed_loss |
| `aircargo-probation-dismissal` | no | no_observed_loss | no_observed_loss |
| `aircargo-dismissal-check` | no | no_observed_loss | no_observed_loss |
| `aircargo-dismissal-lawyer` | no | no_observed_loss | no_observed_loss |
| `aircargo-dismissal-order` | no | no_observed_loss | no_observed_loss |
| `aircargo-leave-sources` | no | no_observed_loss | no_observed_loss |
| `aircargo-leave-compensation` | no | no_observed_loss | no_observed_loss |
| `aircargo-leave-risk` | no | no_observed_loss | no_observed_loss |
| `aircargo-matliab-check` | no | no_observed_loss | no_observed_loss |
| `aircargo-matliab-disputed` | no | no_observed_loss | no_observed_loss |
| `aircargo-templates-choose` | no | no_observed_loss | no_observed_loss |
| `aircargo-templates-checklist` | no | no_observed_loss | pool_to_sent_unknown |
| `aircargo-templates-insufficient` | no | no_observed_loss | no_observed_loss |
| `aircargo-secret-check` | yes | no_observed_loss | no_observed_loss |
| `aircargo-secret-not-auto` | no | no_observed_loss | no_observed_loss |
| `aircargo-secret-disclosure` | yes | no_observed_loss | no_observed_loss |
| `aircargo-pdp-scope` | no | no_observed_loss | no_observed_loss |
| `aircargo-pdp-data` | no | no_observed_loss | no_observed_loss |
| `aircargo-pdp-uncertain` | no | no_observed_loss | no_observed_loss |
| `aircargo-claims-delay` | yes | no_observed_loss | no_observed_loss |
| `aircargo-claims-damage` | no | no_observed_loss | no_observed_loss |
| `aircargo-claims-lawyer` | no | no_observed_loss | no_observed_loss |
| `aircargo-claims-forbidden` | no | no_observed_loss | no_observed_loss |
| `aircargo-expedition-vs-carrier` | yes | no_observed_loss | no_observed_loss |
| `aircargo-expedition-mawb-hawb` | yes | no_observed_loss | no_observed_loss |
| `aircargo-expedition-risks` | yes | no_observed_loss | no_observed_loss |
| `aircargo-road-cutoff` | yes | no_observed_loss | no_observed_loss |
| `aircargo-road-penalty` | yes | no_observed_loss | no_observed_loss |
| `aircargo-road-seal` | no | no_observed_loss | no_observed_loss |
| `aircargo-road-driver-pdn` | no | no_observed_loss | no_observed_loss |
| `aircargo-business-trip-advance-report` | no | no_observed_loss | no_observed_loss |
| `aircargo-business-trip-foreign-approval` | no | no_observed_loss | no_observed_loss |
| `aircargo-remote-work-monitoring-limits` | no | no_observed_loss | no_observed_loss |
| `aircargo-remote-work-equipment-compensation` | yes | no_observed_loss | no_observed_loss |
| `aircargo-maternity-duration-normal` | no | no_observed_loss | no_observed_loss |
| `aircargo-maternity-dismissal-ban` | no | no_observed_loss | no_observed_loss |
| `aircargo-internal-transfer-consent` | no | no_observed_loss | no_observed_loss |
| `aircargo-internal-transfer-documents` | no | no_observed_loss | no_observed_loss |
| `aircargo-contract-termination-open-awb` | yes | no_observed_loss | no_observed_loss |
| `aircargo-contract-termination-fields` | yes | no_observed_loss | no_observed_loss |
| `aircargo-road-contract-aircargo-fields` | yes | no_observed_loss | no_observed_loss |
| `aircargo-dangerous-goods-fields` | yes | no_observed_loss | no_observed_loss |
| `aircargo-dangerous-goods-clearance` | yes | pool_to_sent_unknown | pool_to_sent_unknown |
| `aircargo-customs-clearance-fields` | yes | pool_to_sent_unknown | pool_to_sent_unknown |
| `aircargo-customs-special-cargo-manual-check` | yes | pool_to_sent_unknown | pool_to_sent_unknown |
| `aircargo-waybill-first-mile-fields` | yes | index_to_after_caps_unknown | index_to_after_caps_unknown |
| `aircargo-waybill-escalation-events` | yes | pool_to_sent_unknown | pool_to_sent_unknown |
| `aircargo-trade-compliance-hold` | yes | no_observed_loss | no_observed_loss |
| `aircargo-trade-compliance-screening` | no | pool_to_sent_unknown | pool_to_sent_unknown |
| `aircargo-incident-response-bridge` | yes | no_observed_loss | no_observed_loss |
| `aircargo-incident-response-required-fields` | yes | no_observed_loss | no_observed_loss |
| `aircargo-access-control-need-to-know` | yes | no_observed_loss | no_observed_loss |
| `aircargo-access-control-review` | yes | no_observed_loss | no_observed_loss |
| `aircargo-employment-contract-essential-terms` | no | pool_to_sent_unknown | pool_to_sent_unknown |
| `aircargo-employment-contract-special-form` | no | no_observed_loss | no_observed_loss |
| `aircargo-driver-job-documents` | no | no_observed_loss | no_observed_loss |
| `aircargo-driver-dangerous-goods-refusal` | no | no_observed_loss | no_observed_loss |
| `aircargo-sick-leave-required-fields` | yes | no_observed_loss | no_observed_loss |
| `aircargo-sick-leave-lawyer-escalation` | no | no_observed_loss | no_observed_loss |
| `aircargo-cargo-loss-evidence-bundle` | yes | no_observed_loss | no_observed_loss |
| `aircargo-cargo-loss-required-fields` | yes | no_observed_loss | no_observed_loss |
| `aircargo-late-delivery-reply-evidence` | yes | no_observed_loss | no_observed_loss |
| `aircargo-late-delivery-reply-no-admission` | yes | no_observed_loss | no_observed_loss |
| `aircargo-driver-hours-required-fields` | yes | no_observed_loss | no_observed_loss |
| `aircargo-driver-hours-terminal-discrepancy` | yes | no_observed_loss | no_observed_loss |
| `aircargo-warehouse-3pl-required-fields` | yes | no_observed_loss | no_observed_loss |
| `aircargo-warehouse-3pl-escalation` | yes | no_observed_loss | no_observed_loss |
| `aircargo-perishable-temperature-controls` | yes | index_to_after_caps_unknown | index_to_after_caps_unknown |
| `aircargo-perishable-special-cargo-evidence` | yes | pool_to_sent_unknown | pool_to_sent_unknown |
| `aircargo-oversized-permit-route` | yes | no_observed_loss | no_observed_loss |
| `aircargo-oversized-manual-check` | yes | no_observed_loss | no_observed_loss |
| `aircargo-data-retention-legal-hold` | yes | no_observed_loss | no_observed_loss |
| `aircargo-data-retention-required-fields` | yes | no_observed_loss | no_observed_loss |
| `aircargo-subject-rights-third-party-masking` | yes | pool_to_sent_unknown | pool_to_sent_unknown |
| `aircargo-subject-rights-required-fields` | yes | no_observed_loss | no_observed_loss |
| `aircargo-customs-broker-evidence` | yes | no_observed_loss | no_observed_loss |
| `aircargo-customs-broker-escalation` | yes | index_to_after_caps_unknown | index_to_after_caps_unknown |
| `aircargo-salary-payment-dates` | no | no_observed_loss | no_observed_loss |
| `aircargo-salary-bonus-conditions` | no | no_observed_loss | no_observed_loss |
| `aircargo-overtime-limits` | no | no_observed_loss | no_observed_loss |
| `aircargo-overtime-protected-categories` | no | no_observed_loss | no_observed_loss |
| `aircargo-harassment-complaint-data` | no | no_observed_loss | no_observed_loss |
| `aircargo-harassment-investigation-timeline` | no | no_observed_loss | no_observed_loss |
| `aircargo-conflict-interest-disclosure` | no | no_observed_loss | no_observed_loss |
| `aircargo-conflict-interest-sanctions` | no | no_observed_loss | no_observed_loss |
| `aircargo-cargo-insurance-evidence` | yes | no_observed_loss | no_observed_loss |
| `aircargo-cargo-insurance-operational-limits` | yes | no_observed_loss | no_observed_loss |
| `aircargo-fuel-supply-evidence` | yes | no_observed_loss | no_observed_loss |
| `aircargo-fuel-supply-required-fields` | yes | no_observed_loss | no_observed_loss |
| `aircargo-gps-monitoring-required-fields` | yes | no_observed_loss | no_observed_loss |
| `aircargo-gps-monitoring-scope` | yes | no_observed_loss | no_observed_loss |
| `aircargo-weight-control-required-fields` | yes | no_observed_loss | no_observed_loss |
| `aircargo-weight-control-discrepancy` | no | no_observed_loss | no_observed_loss |
| `aircargo-cross-border-required-fields` | yes | index_to_after_caps_unknown | index_to_after_caps_unknown |
| `aircargo-cross-border-special-cargo` | yes | no_observed_loss | no_observed_loss |
| `aircargo-breach-notification-required-fields` | yes | no_observed_loss | no_observed_loss |
| `aircargo-breach-notification-participants` | yes | pool_to_sent_unknown | pool_to_sent_unknown |
| `aircargo-cross-border-pdn-required-fields` | yes | no_observed_loss | no_observed_loss |
| `aircargo-cross-border-pdn-no-transfer` | yes | no_observed_loss | no_observed_loss |

## Provenance and development ledger

Extraction date `2026-10-01`; code SHA `b448ee407caacc872015eb5193307762d96c8794`;
`tree_clean`: `false`. Working-tree code digests in JSON
pin the uncommitted extractor; its publishing commit later anchors those digests.
Config SHA-256 `bd4e23dee523bd49706aea7e4633b290f3a84c3b11bead2f63fda8948b049ec6`.
Corpus SHA-256 `c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343`;
archived chunks: 5589; corpus files: 201.

| input artifact | SHA-256 of stored bytes |
|---|---|
| [evaluation/curated_cases_aircargo.jsonl](../../evaluation/curated_cases_aircargo.jsonl) | `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720` |
| [evaluation/gr1b-4436d61-graph-chunks.json.gz](../../evaluation/gr1b-4436d61-graph-chunks.json.gz) | `2a9da515a4c69b46453a59ed6d0bb772b0aad6fed23c87ee465851b43dbdef12` |
| [evaluation/c1a-c06bdf5-phase-c-C-candidates.json.gz](../../evaluation/c1a-c06bdf5-phase-c-C-candidates.json.gz) | `c28d676ac79450d54904cc83c697ddb709dfe95e6bbe86d305c3505db50338c3` |
| [evaluation/gr1b-4436d61-prerank-pool.json.gz](../../evaluation/gr1b-4436d61-prerank-pool.json.gz) | `dfc67c281bef24c483ff105f96896bbaf7b5cf68c2f8e0f2ccf26963631ad410` |
| [evaluation/gr1b-4436d61-candidates.json.gz](../../evaluation/gr1b-4436d61-candidates.json.gz) | `4fdf2a128a23fedea08a2d465ee0605181ab5b014bfb4611f66b6acc62bbbb49` |
| [reports/gr/gr1b-stage-replay.json](../../reports/gr/gr1b-stage-replay.json) | `fcb091a6406125e1a3f133a053c52cd2bf3a18caa11dba4151c30e19ae43c8d6` |
| [reports/p1b/p1b-expanded-cut.json](../../reports/p1b/p1b-expanded-cut.json) | `6f48bb1957f67235792edb926cf44c4894b56439c9fd423feb6529a7a791bc8b` |
| [evaluation/p1-511f3f9-H-rerank-scores.json](../../evaluation/p1-511f3f9-H-rerank-scores.json) | `3ced6d0259fdee8da1d4cbf7dcb1cea55fed7e4379003d23f327a25e331bb50b` |
| [evaluation/aircargo_corpus.manifest.json](../../evaluation/aircargo_corpus.manifest.json) | `2b2e9232e69b4f52a55237f3ee620f34c91d1900383877c2310ba616c6590444` |
| [evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json](../../evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json) | `ac8d9cc20a8d414490fd0ada46e35731d7a2891e7169c3ec22ef88a4644db534` |

Compressed inputs also carry decompressed hashes in JSON. Historical producer code
SHAs, reranker revision/batch and phase-C generator fingerprint/config are retained
verbatim there. Archived embedder id is BGE-M3, matching the current default model id;
HF revision, prompts and index-manifest attestation are unknown. This is **not a
rerun on today's embedder/index**. Chunker version and graph digest are unknown;
historical structural/contextual chunk settings are described by the producer.

New-campaign baseline provenance is `NOT_EVIDENCE`: no current manifest check, API
parity, gold, judges, latency or model run. Non-applicable judge/bootstrap/host-model
fields are N/A in JSON. Historical H is agent-authored; later journey-label approval
does not create gold spans. No mechanism is selected on this incomplete causal map;
the complete map follows gold and parity slices. Runtime defaults are unchanged.

[JSON artifact](../../evaluation/evidence-loss-map-prelim.json) ·
[extractor](../../scripts/evidence_loss_map.py) ·
[reproducibility test](../../tests/test_evidence_loss_map.py) ·
[development ledger](../../evaluation/dev_ledger.jsonl). The ledger's first entry
registers this diagnostic as H development use with config and artifact hashes.
No holdout was read.
