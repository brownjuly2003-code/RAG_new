# GR-1b — structural graph retrieval

Measured 2026-09-12 from the completed Mac rerank artifact. **NO-SHIP** for
making graph retrieval the default: precision remains below the 0.63 gate.

The graph arm scores 0.5475 precision and 0.9200 recall, compared with the
published GR-0.3 baseline's 0.5067 and 0.9050. FULL/PART/MISS changes from
87/7/6 to 88/8/4. These are descriptive results from different candidate pools,
not a controlled attribution of the gain to graph structure alone.

## Per-class result

| question class | cases | ctx precision | ctx recall | FULL | PART | MISS |
|---|---:|---:|---:|---:|---:|---:|
| aggregation | 0 | — | — | 0 | 0 | 0 |
| global | 0 | — | — | 0 | 0 | 0 |
| multi_hop | 1 | 0.4327 | 0.5000 | 0 | 1 | 0 |
| single_hop | 99 | 0.5487 | 0.9242 | 88 | 7 | 4 |
| all cases | 100 | 0.5475 | 0.9200 | 88 | 8 | 4 |

## Provenance and reproduction

- Report: [`gr1b-structure-graph.json`](../../reports/gr/gr1b-structure-graph.json).
- Archived exact input: [`gr1b-4436d61-candidates.json.gz`](../../evaluation/gr1b-4436d61-candidates.json.gz).
- Uncompressed pool SHA-256: `c862dcb76878d7a79db040ac13099b733ad769b08092094d174cc6814be4ee26`.
- Dataset SHA-256: `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720`.
- Corpus SHA-256: `c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343`.
- Measurement code commit: `b2db5425daf3507aab2c46af147ca45cb2b6236b`; individual source digests
  and label-sidecar digests are in the report. Its dirty-tree marker is honest:
  documentation and publication work were present while the report was built.
- The prior Mac handoff attributes pool/rerank production to `4436d61`, with
  completion markers `RERANK_EXIT=0` and `DONE`. The recovered JSON itself has
  no embedded code revision or model digest; this attribution is handoff
  evidence, not independently attested run provenance.
- Config: G1, top-k capped at 5, context cap 6000 characters, keyword metrics,
  no grading or generation, no additional parent expansion in the measurement.
  Graph section expansion has already happened in the input artifact.

Reproduce every case and aggregate from the archived pool without models or
network access (Windows or Mac):

```powershell
python -m pytest tests/test_gr1b_artifact.py -q -p no:schemathesis --basetemp=.tmp/pytest-gr1b-artifact
```

The test decompresses the archive into a temporary file, checks its digest,
rebuilds the report using the pinned dataset and labels, and compares every
case, class, aggregate and configuration field. Embeddings are not regenerated.

## Limits and next step

All 100 rows carry `graph_postprocessed=true`, but category matches and
prefilter applications are both 0/100. This run therefore measures coherence
and section expansion over an unfiltered pool; it does not validate the
category-prefilter benefit.

Graph output contains fewer than five candidates in some rows. The measurement
now explicitly permits short G1 outputs and scores the actual contexts, without
padding or dropping cases. The original baseline loader remains strict.
Empty graph outputs count as misses. Candidate counts before the character cap:
2 contexts: 4 cases, 3 contexts: 88 cases, 4 contexts: 7 cases, 5 contexts: 1 cases.

The questions and labels are `agent_labelled`, 0 approved. The case mix is
99 single-hop questions and one multi-hop question; aggregation and global
classes are empty. No multi-hop improvement claim is supported. GR-0.2's
supplemental bucket still needs its own pool and measurement.

Keep the graph default unchanged. Continue the planned GR-4/GR-2/GR-3 work;
any full integration, model or container run belongs on the Mac. The current
number alone does not authorize a default-model or retrieval-policy change.
