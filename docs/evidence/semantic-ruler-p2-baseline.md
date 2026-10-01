# Semantic ruler — P2 development baseline (T-58, slice 1.4)

Published from the committed [P2 report](../../reports/p2/p2-blinded-judge-glm+sonnet.json)
and its pinned pools/replies by
`python -m evaluation.semantic_ruler p2-baseline --out evaluation/semantic-ruler-p2-baseline.json`.
The [artifact](../../evaluation/semantic-ruler-p2-baseline.json) is the source
of every number below; this is slice rule (c), a development baseline, with
`provisional_ruler: true` until the human calibration in slice 1.1 closes.

P2 graded the phase-C **unexpanded** top-five reranked seeds (`top_k_5`).
`precision_at_5` and `ndcg_at_5` use those seeds; `sent_precision` uses the
same documents because the phase-C harness sent them unexpanded. This is
**NOT the production-expansion path**; that baseline belongs to slice 2.5.
Grades are the P2 lower-median consensus of GLM 5.3 and Sonnet 5. Human
relevance grades are absent. No semantic gain or product acceptance is claimed.

| Pool | Metric | Point | Cluster-bootstrap CI95 | n | Excluded |
|---|---|---:|---|---:|---:|
| H | `precision_at_5` | 0.608000 | [0.544327, 0.669814] | 100 | 0 |
| H | `sent_precision` | 0.608000 | [0.544327, 0.669814] | 100 | 0 |
| H | `ndcg_at_5` | 0.965901 | [0.953501, 0.976594] | 100 | 0 |
| H | `context_precision` | 0.506657 | [0.466967, 0.543024] | 100 | 0 |
| Hm | `precision_at_5` | 0.840000 | [0.750000, 1.000000] | 15 | 0 |
| Hm | `sent_precision` | 0.840000 | [0.750000, 1.000000] | 15 | 0 |
| Hm | `ndcg_at_5` | 0.962285 | [0.908110, 1.000000] | 15 | 0 |
| Hm | `context_precision` | 0.252727 | [0.231460, 0.439400] | 15 | 0 |

The official lexical `context_precision` gate remains **0.63** on its own
ruler; the H lexical point misses it. Semantic precision is unweighted by
rank, relevant at grade >=2, with a fixed denominator of five for seeds.
nDCG uses linear grade gain, log2(rank+1), deduplication by document id and
the ideal over all graded documents of each case. Both seed metrics use the
first five original positions; a duplicate has zero gain at its existing
rank and never pulls in position six or later. P2 only graded these five;
the API supports a larger graded universe. Zero-IDCG cases are excluded
and counted (none in this baseline).

`evidence_recall_pool`, `all_evidence_coverage` and `fact_coverage` are **N/A**
on both pools: P2 has no approved gold spans, required groups or atomic facts.
Their implementations are tested on fixtures only, not quality evidence;
measuring them awaits the first approved gold of slice 1.3b. The fact matcher
version is `semantic-ruler/claim-window-v3`: normalized containment or numeric
value/unit within a sentence/window carrying subject, polarity and condition;
polarity uses the registered English/Russian lexicon with word boundaries.
Any negation cue anywhere in a window, conflicting or unknown polarity markers,
or disagreement between candidate windows prevents automatic presence;
`needs_blind_judgment` reports unresolved fact indices for explicit blind judgments.
Critical facts still require
the registered blind human acceptance check.

## Clustering and intervals

The family register does not exist yet. Cluster unit is
**provisional, replaced by the 1.3a family register**. H uses the first two `tags` as one
topic identity: **45 groups** over 100 cases; extra tags are not families.
Hm uses `source_documents`: **3 connected components** over 15 cases.
The full case mapping and components are in the artifact. Multiple families
touched by one case join into a single connected component.

Bootstrap: **10,000** component resamples, seed **20261001**, percentile
CI95 with linear quantiles, equal case weights (not equal cluster weights).
This is a single arm: its intervals are descriptive, especially Hm's three
components. No paired gain, non-inferiority verdict, MDE or achieved-power
claim can be derived from this baseline; those require a registered control
and paired pilot from slice 1.3c.

Paired machinery is exercised on fixtures: the bootstrap can decide only
with at least ten clusters carrying a non-zero summed paired difference and at least
five percent of pairs differing. Otherwise it prints the one-sided 95%
Clopper–Pearson loss-rate upper bound and its implied metric lower bound,
and returns `INCONCLUSIVE`, unless structurally invariant as registered
before the run. With fewer than ten clusters it also prints the cluster
sandwich t-interval (df=clusters-1); the conservative envelope governs.
One cluster cannot estimate variance and gets the full bounded difference
range. The common pair mask, excluded counts, worst-case sensitivity and
the registered missing-pair limits are reported. The closed deciding table
is represented in code; nDCG is diagnostic and never deciding.
`citation_correctness` always requires a blind human check; `faithfulness`
requires one while `provisional_judge` (the default until calibration).
A missing human result is `INCONCLUSIVE`, an explicit failed check is `NO_SHIP`.
Registered structural invariance is an explicit decision basis independent
of sampled uncertainty, including when there is only one component; observed
non-zero differences contradict that registration and are rejected.

## Provenance and verification

Generation HEAD: `629f903f938b823e6caceab1885957890df5dc95`.
`tree_clean: false`: the artifact was built before the slice commit, so it
records the SHA-256 of the module/CLI and P2 helpers that built it rather
than implying that HEAD contains the new module. Module and CLI are the same
file. The artifact test checks those digests against the blobs at the commit
that added the artifact, so later edits of the module do not rewrite this
provenance; the numbers themselves are re-derived from the live module.

P2 report SHA-256:
`4c1e60cdad361799a291fa88d0d0c3a35675ad772630a0147615ab30d3a31e7d`.
Corpus/cached-pool identities carried forward from P2:

| Pool | Pool SHA-256 | Dataset SHA-256 |
|---|---|---|
| H | `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10` | `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720` |
| Hm | `3a3020799e8310fcaf3532783cae9d83f8f03b3b0a741488b425ac7edec0aeee` | `0949d7563983b96500074e61f10274b28cb9341612206e02733a59b5c7968f5f` |

The artifact retains P2's archive/dataset/sidecar digests, raw reply digests,
instruction hash, reranker digest, effective batch size, full metric/bootstrap
config and case counts. Loaders verify pinned inputs and parse original raw
replies with request hashes before reconstructing consensus. No judge calls,
models or fresh retrieval are run. P2 lacks the future campaign's registered
ingestion/index/family manifest and generator fingerprint; this publication
is limited to the cached P2 ruler and cannot certify campaign acceptance.

New tests: `tests/test_semantic_ruler.py` (fixture contracts) and
`tests/test_semantic_ruler_p2_artifact.py` (artifact/capsule reproduction and CLI).
`tests/test_semantic_ruler_negation.py` covers conservative negation and mixed windows.
Focused command:
`python -m pytest -q --noconftest -p no:schemathesis -p no:cacheprovider tests/test_semantic_ruler.py tests/test_semantic_ruler_p2_artifact.py`.
Ruff and `python -m mypy evaluation/semantic_ruler.py --strict` cover the
new module; the MyFlow full gate on `deproject-mac` re-runs the suite.

Review pass 1 (2026-10-01) found three defects, each fixed with a failing
test first: `precision_at_5` and `ndcg_at_5` pulled a sixth seed in when an id
repeated inside the first five (now the first five positions only, a repeat
is a zero-gain position); `check_rule` treated a missing blind human check as
passed (now `INCONCLUSIVE` when absent, `NO_SHIP` when failed, for
`citation_correctness` and for `faithfulness` under `provisional_judge`); and
the numeric-fact matcher accepted "not allowed" for "allowed" (matcher
`claim-window-v2`: polarity markers at word boundaries, negated or conflicting
markers left to a blind judgment). The rebuilt artifact has identical
populations, per-case values, points and intervals; only the matcher version
and the module digest changed.
Review pass 2 (2026-10-01) strengthens the matcher to `claim-window-v3`: every registered negation cue, including apostrophe-normalized contractions, anywhere in a candidate window and any disagreement across windows require blind judgment; P2 numbers remain identical.
