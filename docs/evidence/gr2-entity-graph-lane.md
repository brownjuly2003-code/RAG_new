# GR-2 — the entity-graph retrieval lane

Measured 2026-09-17 on `deproject-mac` over the archived pools of the finished
run. **NO-SHIP** for making graph retrieval the default, and no reason to make
the entity lane one either: phase-C precision moves from **0.5475** to
**0.5487** and stays far below the 0.63 gate, while the supplemental
multi-document bucket moves **by exactly nothing** although the lane fired on 11
of its 15 cases. The graph retrieval default stays unchanged.

The `G1` arm here is the published GR-1b arm, reproduced case by case: the
reranked phase-C `G1` pool is identical case by case in order, members,
`prerank_cands` and `reranked_cands` to
[`gr1b-4436d61-candidates.json.gz`](../../evaluation/gr1b-4436d61-candidates.json.gz)
over all 100 cases; the GR-2 copy adds a per-case `rerank_s`, so its file digest
differs. So `G2 − G1` is the entity lane's own effect on the same cases, not a
comparison of two different runs.

## Measured result

`render_gr2_table(report)`, quoted verbatim:

```
GR-2 entity graph retrieval comparison: phase_c
| labelled class | cases | G1 precision | G2 precision | delta | G1 recall | G2 recall | delta | G1 FULL/PART/MISS | G2 FULL/PART/MISS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aggregation | 0 | — | — | — | — | — | — | 0/0/0 | 0/0/0 |
| global | 0 | — | — | — | — | — | — | 0/0/0 | 0/0/0 |
| multi_hop | 1 | 0.4327 | 0.4327 | 0.0000 | 0.5000 | 0.5000 | 0.0000 | 0/1/0 | 0/1/0 |
| single_hop | 99 | 0.5487 | 0.5499 | 0.0012 | 0.9242 | 0.9293 | 0.0051 | 88/7/4 | 89/6/4 |
| all cases | 100 | 0.5475 | 0.5487 | 0.0012 | 0.9200 | 0.9250 | 0.0050 | 88/8/4 | 89/7/4 |
G1 graph_prefiltered=true: 0/100
G2 graph_prefiltered=true: 0/100
G2 routed class counts: {'global': 5, 'multi_hop': 1, 'single_hop': 94}
G2 entity lane: 6 cases, candidates max=50, hops max=2
Cost: G2 entity-search 6 lane cases, p50=5.105488991830498 ms p95=9.393642016220838 ms; paired rerank_s delta p50=0.2057 s p95=5.9479 s
G2 peak_rss_bytes: 1497853952 (1428.46 MiB)
G2 non-lane parity with G1: 0 divergent of 94 cases
Keyword transitions: FULL->FULL: 88, MISS->MISS: 4, PART->FULL: 1, PART->PART: 7
Keyword loss case ids: none

GR-2 entity graph retrieval comparison: multi_doc_bucket
| labelled class | cases | G1 precision | G2 precision | delta | G1 recall | G2 recall | delta | G1 FULL/PART/MISS | G2 FULL/PART/MISS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aggregation | 5 | 0.2809 | 0.2809 | 0.0000 | 0.5000 | 0.5000 | 0.0000 | 1/3/1 | 1/3/1 |
| global | 0 | — | — | — | — | — | — | 0/0/0 | 0/0/0 |
| multi_hop | 10 | 0.2612 | 0.2612 | 0.0000 | 0.3500 | 0.3500 | 0.0000 | 0/7/3 | 0/7/3 |
| single_hop | 0 | — | — | — | — | — | — | 0/0/0 | 0/0/0 |
| all cases | 15 | 0.2678 | 0.2678 | 0.0000 | 0.4000 | 0.4000 | 0.0000 | 1/10/4 | 1/10/4 |
G1 graph_prefiltered=true: 0/15
G2 graph_prefiltered=true: 0/15
G2 routed class counts: {'aggregation': 1, 'global': 1, 'multi_hop': 9, 'single_hop': 4}
G2 entity lane: 11 cases, candidates max=50, hops max=2
Cost: G2 entity-search 11 lane cases, p50=11.070430045947433 ms p95=15.295115008484572 ms; paired rerank_s delta p50=70.2358 s p95=91.757 s
G2 peak_rss_bytes: 1230897152 (1173.88 MiB)
G2 non-lane parity with G1: 0 divergent of 4 cases
Keyword transitions: FULL->FULL: 1, MISS->MISS: 4, PART->PART: 10
Keyword loss case ids: none
```

## What the lane did

The routed class comes from the production `classify_complexity` node over the
pinned model, never from the labelled classes — labels only group the reported
rows. The lane runs for `multi_hop`, `aggregation` and `global` only.

| | phase C (100 cases) | multi-document bucket (15 cases) |
|---|---|---|
| routed classes | 94 `single_hop`, 5 `global`, 1 `multi_hop` | 9 `multi_hop`, 4 `single_hop`, 1 `global`, 1 `aggregation` |
| cases with the entity lane | 6 | 11 |
| entity candidates, max | 50 | 50 |
| co-occurrence hops, max | 2 | 2 |
| non-lane parity with `G1` | 0 divergent of 94 | 0 divergent of 4 |
| keyword transitions | 88 FULL→FULL, 7 PART→PART, 4 MISS→MISS, 1 PART→FULL | 1 FULL→FULL, 10 PART→PART, 4 MISS→MISS |
| keyword losses | none | none |

Every case the lane skipped is identical in candidates and contexts to `G1`, as
the contract requires: a case routed `single_hop` yields exactly the structural
`G1` result. Two of the six lane cases changed their top-5 —
`aircargo-waybill-escalation-events` (0.3000 → 0.3545, PART→FULL) and
`aircargo-customs-broker-escalation` (0.2364 → 0.3000, still MISS) — and together
they account for the whole +0.0012 aggregate move; only one of them crosses a
keyword-status boundary. In the bucket, 11 lane cases produced **no change to
any top-5**: precision 0.2678 and recall 0.4000 in both arms, `aggregation`
0.2809 / 0.5000 and `multi_hop` 0.2612 / 0.3500 in both arms, FULL/PART/MISS
1/10/4 in both arms. The lane fired and the reranker put the same five contexts
on top.

The category prefilter matched **0 cases** in both arms and both datasets
(`graph_prefiltered_count` 0/100 and 0/15), so this run says nothing about the
prefilter — same limit as GR-1b.

## Gate verdicts

| # | Plan gate | Evidence | Verdict |
|---|---|---|---|
| 1 | single-hop precision not worse than GR-1 | `single_hop` 0.5487 → 0.5499 over 99 cases (delta +0.0012); recall 0.9242 → 0.9293 | **PASS** |
| 2 | `entity_candidates_max` at most 50 | 50 in both datasets, hops max 2 | **PASS** |
| 3 | retrieve p95 at most +200 ms | `G1` rows carry no timings, so the lane-only entity search is the added retrieve time: p95 **9.39 ms** (phase C, 6 lane cases) and **15.30 ms** (bucket, 11 lane cases) | **PASS**, with the cost note below |
| 4 | phase-C precision at the 0.63 gate | `G2` aggregate 0.5487 | **NO-SHIP** — default activation is not authorized |
| 5 | multi-document bucket shows the lane's value | zero difference between arms on all 15 cases | **NO** value shown |

Gate 3 passes on the letter and hides the real cost. Entity search itself is
milliseconds (phase C p50 5.11 / p95 9.39 ms; bucket p50 11.07 / p95 15.30 ms),
but the lane hands the reranker a pool with up to 50 extra candidates. The
table's `paired rerank_s delta` percentiles are **whole-dataset**: on phase C
they are dominated by the 94 cases whose pools are identical in candidates, so
p50 **+0.2057 s** / p95 **+5.9479 s** is measurement noise, not the lane. Over
the six lane cases the paired rerank deltas are **+0.7184, +42.3914, +56.285,
+59.543, +63.5408 and +65.6788 s** (median ≈ 57.9 s, max 65.6788 s). The bucket
figures (11 of 15 lane) are representative of the lane: p50 **+70.2358 s** /
p95 **+91.7570 s**. That is an 8 GiB Intel Mac at `RAG_RERANK_BATCH=8`, not
production hardware, and the whole-pool `G2` retrieve times stay small (phase C
p50 13.094 / p95 18.1457 ms; bucket p50 29.5503 / p95 37.3597 ms). The honest
statement is that the retrieve gate does not measure where this lane spends
time — reranking a 50-candidate entity pool does.

Peak resident memory published here is the **pools-phase** peak recorded in the
`G2` pool meta: 1 497 853 952 bytes (1428.46 MiB) for phase C and
1 230 897 152 bytes (1173.88 MiB) for the bucket. The rerank phase loads the same
reranker for both arms and records no RSS, so no rerank memory number is
published.

## Provenance

Report: [`gr2-entity-graph.json`](../../reports/gr/gr2-entity-graph.json)
(`gr-entity-graph-retrieval/v1.0`, `evidence_class: measured`). Measurement code
commit `9ca86301bd53d327e48aaed811a47c4542b08bd2` — the `git archive` the Mac run
used; per-file source digests are in the report. Config: top-k 5, context cap
6000 characters, `graph_retrieval_default: unchanged`.

Corpus `aircargo`, 201 files, corpus SHA-256
`c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343`, manifest
`evaluation/aircargo_corpus.manifest.json`
(`2b2e9232e69b4f52a55237f3ee620f34c91d1900383877c2310ba616c6590444`).

Graph inputs shared by both datasets: graph chunks
`5b35883f741deefc0698eb829f927413fc6588b72b9add9ee7697f3fc5806c94`, projection
digest `60a257ddf069b600718f4982edabacafd6e167744a714abcc722440b9aae9208`
(5589 chunk nodes, 2530 entity nodes, 4509 section nodes, 201 documents;
77 660 `co_occurs` and 39 998 `mentions` edges).

| Dataset | cases | dataset SHA-256 | label sidecar | label manifest |
|---|---:|---|---|---|
| phase C `curated_cases_aircargo.jsonl` | 100 | `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720` | `cc6356b9faa46d4b952a955e1d47e9a8b15003284c42f48e7e5236471f8ff17c` | `e2010fc94ee283c29308e6fa53e522c70b57d767aacf00113628858a061f7b10` |
| bucket `curated_cases_aircargo_gr_multihop.jsonl` | 15 | `0949d7563983b96500074e61f10274b28cb9341612206e02733a59b5c7968f5f` | `a4bf3433bf3b73a7d20741516d911b70aec7ad7488838cff34bc32928079c719` | `4f5417e7da1ef3dee4a106b36d1fb43e4d9fa7c298068029f6b3fd9dd911db77` |

Archived exact inputs under `evaluation/`, gzip (`gzip -n`). SHA-256 is of the
**uncompressed** bytes, which is what the report pins and the test checks:

| Archive | Uncompressed SHA-256 | Bytes |
|---|---|---:|
| [`gr2-9ca8630-phase-c-G1-candidates.json.gz`](../../evaluation/gr2-9ca8630-phase-c-G1-candidates.json.gz) | `6848b5f33787ca7a91c3137a5f7da90c0b532093048245d378e296a53482a059` | 8341699 |
| [`gr2-9ca8630-phase-c-G2-candidates.json.gz`](../../evaluation/gr2-9ca8630-phase-c-G2-candidates.json.gz) | `aa5bf94c2e12f7de29b20e625cf1a338320b7fc82feeb95072bfb5a68e38a654` | 8893885 |
| [`gr2-9ca8630-phase-c-G2-pool-meta.json.gz`](../../evaluation/gr2-9ca8630-phase-c-G2-pool-meta.json.gz) | `4825057628d00f7fc2926a42c623aaebaef5b783cc94cf6c90c7f0943747b396` | 901 |
| [`gr2-9ca8630-phase-c-classifications.jsonl.gz`](../../evaluation/gr2-9ca8630-phase-c-classifications.jsonl.gz) | `c5c79e9343b9b22dabc3b8d13a6565f959831ceaa178c017af1cd48e53cdf861` | 32949 |
| [`gr2-9ca8630-phase-c-classifications-manifest.json.gz`](../../evaluation/gr2-9ca8630-phase-c-classifications-manifest.json.gz) | `e0429f2b287efa733999e9fa9bea2f2feb91ad4be9cdacc3059ef2e6aae45404` | 531 |
| [`gr2-9ca8630-bucket-G1-candidates.json.gz`](../../evaluation/gr2-9ca8630-bucket-G1-candidates.json.gz) | `17db60197eaa7df9173f1c9377368996cbe1600254670057ef9dc397e3f0762b` | 1472052 |
| [`gr2-9ca8630-bucket-G2-candidates.json.gz`](../../evaluation/gr2-9ca8630-bucket-G2-candidates.json.gz) | `73a11d8fa11bd75b8ef9a3319f0659426cc6f9f1c86c95cb3412c56d3cfbec9d` | 2691344 |
| [`gr2-9ca8630-bucket-G2-pool-meta.json.gz`](../../evaluation/gr2-9ca8630-bucket-G2-pool-meta.json.gz) | `34bda4324e5ca093793d51da13350fa0a417c09aae704c23813bc95150f72326` | 919 |
| [`gr2-9ca8630-bucket-classifications.jsonl.gz`](../../evaluation/gr2-9ca8630-bucket-classifications.jsonl.gz) | `f5f9121eee391ef8e5cef96603b3f5f8e59e7fcdbdd4b784e3b5408eb0240755` | 6393 |
| [`gr2-9ca8630-bucket-classifications-manifest.json.gz`](../../evaluation/gr2-9ca8630-bucket-classifications-manifest.json.gz) | `f4709e7172a4d0afa7388c7707bf50891834e3c7277937257d9b17c9c7b6b816` | 530 |
| [`gr2-9ca8630-extraction-manifest.json.gz`](../../evaluation/gr2-9ca8630-extraction-manifest.json.gz) | `d763683ef4bb88202da3a0293099770c1b3933a4adc3945784866464221ef3fd` | 703 |

Both `G2` pool metas pin the extraction manifest
(`d763683ef4bb88202da3a0293099770c1b3933a4adc3945784866464221ef3fd`) and their
own classification manifest, so the pools cannot be recombined with a different
extraction or a different classification run without the mismatch showing.

## Extraction and classification

Entity extraction finished 2026-09-15T00:31:16Z: **5589 chunks cached, 0
rejected**. Manifest: corpus
`c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343`, chunk
payload `f664805f9758bb1854ce82517848306c3d74f3a7f884740d4686edc85a6beffd`,
prompt `ce290b1e80ccab6a62f3cf2293dd029190930edbc4909d6aa23b5008f2ca79f8`,
provider `ollama`, model `qwen2.5:7b` pinned by weights digest
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`,
`num_ctx` 4096, seed 42, temperature 0, normalizer `gr2-entity-v1`, schema
version 2.

**Deviation from the plan:** `plan_06_09_26.md` §GR-2 names `mistral-small` as
the extractor. It was not used. The Mistral free tier answered HTTP 429 and
there is no Colab account, so extraction ran on the local, digest-pinned
`qwen2.5:7b`. Every number here is that extractor's; a different extractor is a
different measurement.

Query classification used the same pinned model at temperature 0, cached with
the dataset digest, once per dataset (schema version 1, prompt template
`291501c891b4c8e8c03d4c86cf1246134e2325a26d7aa009a79b479b9e3576af`). The model
was unloaded (`ollama stop qwen2.5:7b`) before any embedding work.

## The run

Host `deproject-mac`: Intel Core i5-7500 3.40 GHz, 8 GiB RAM, macOS 13.7.8,
device auto = `mps`. Env `RAG_EMBED_BATCH=8 RAG_RERANK_BATCH=8 HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1`, matching GR-1b's `main-b8`.

Two virtual environments, and the reason matters for anyone reproducing this:

- classification — `/Users/julia/RAG_new_gr4_venv` (Python 3.11.15, numpy 1.26.4);
- pools and rerank — `/Users/julia/RAG_Support_Assistant/.venv` (Python 3.11.15,
  numpy 1.26.4, torch 2.2.2, transformers 4.44.2, sentence-transformers 2.7.0,
  huggingface_hub 0.25.2). It is the only Mac venv with `sentence-transformers`;
  the first attempt (2026-09-17T16:44:06Z) died after 3 seconds in the `gr4`
  venv with `ModuleNotFoundError: sentence_transformers`.

Ollama 0.33.2. Attempt 2 ran 2026-09-17T17:22:13Z → 22:55:36Z, all 17 stages
`rc=0`, about 5 h 33 min: phase-C `G1` pools 6779 s, `G1` rerank 4997 s, `G2`
pools 80 s (embeddings cache reused), `G2` rerank 5306 s; bucket 61 / 957 / 59 /
1745 s; classification 2 s per dataset from cache.

## Reproduction

```powershell
python -m pytest -q -p no:schemathesis tests/test_gr2_artifact.py --basetemp=.tmp/pytest-gr2-artifact
```

The test decompresses all eleven archives into a temporary directory, checks
every SHA-256 and byte count above, rebuilds the report with code commit
`9ca86301bd53d327e48aaed811a47c4542b08bd2` and compares `phase_c`,
`multi_doc_bucket` and every provenance digest with the published JSON,
skipping `provenance.code` and stored input paths (the rebuild hashes today's
working tree and reads its own temporary copies). A separate check decompresses
the published GR-1b pool next to the phase-C `G1` archive and asserts equal
case order and equal `cands`, `prerank_cands`, `reranked_cands` and sources.
No model, no network, no corpus read.

## Limits

- The questions and their classes are `agent_labelled`, **0 approved**. This is
  a retrieval comparison over unapproved cases, not a product result.
- The case mix still carries the measurement: phase C is 99 `single_hop` and 1
  `multi_hop` by label, and the classifier routed only 6 of 100 cases into the
  lane. A lane that runs on 6 % of a dataset cannot move that dataset's mean by
  much in either direction, and it did not.
- The bucket is the dataset built for multi-document questions, and there the
  lane ran on 11 of 15 cases and changed nothing measurable. That is the
  informative result of this slice: the entity lane, as specified and as
  implemented, does not currently improve multi-hop retrieval on this corpus.
- Both peak-RSS figures are pools-phase peaks on an 8 GiB host, not total host
  peak RAM, and not a production memory profile.
- The category prefilter is untested here (0 matches), as in GR-1b.

## Next step

Keep the graph retrieval default unchanged and keep the entity lane off by
default. The GR-2 question — "does entity traversal help multi-hop retrieval?" —
now has a measured answer on this corpus: not as built. Before any further
entity work, the cheaper explanations have to be excluded, and the extraction
quality (2530 entities over 5589 chunks from a 7B extractor) is the first of
them.
