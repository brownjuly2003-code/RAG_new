# External bases: variance pilot and acceptance sizes (plan 1.6)

Recorded 2026-10-07 from the pilot completed at 2026-10-07T00:25:03+00:00.
Preparation, no mechanism verdict. The perturbation `pool30` is not a mechanism
candidate, and these runs are not the baseline of slice 1.7. The eleventh
revision of the [development ruler](../specs/semantic-precision-metrics.md)
and its cold review are still required to finish slice 1.6.

The pilot lost no pair. All primary variances stay below the registered
floor 0.10. At the control's measured seconds, acceptance step 1 can read
every eligible ConditionalQA page and all 200 locked WixQA questions within
the registered ceiling of eight nights of eight hours. These are sizes of
future selections; no locked question or our own holdout was opened here.

## Inputs and measurement

The two arms ran on `deproject-mac` at commit
`64a72e551c349913132ff880666e7ceaf8ae04dd`; source fingerprint
`199dbe569864d97342bf6cdb6570c3a6abf91f748988c2c67c03e110a746d783`.
The [connection capsule](external-bases-connection.md) records the separate
indexes. Both arms use hybrid retrieval, graph off, Qwen2.5 7B through
Ollama and the pinned BGE reranker. Only `retrieval_top_k` changes, 20 to 30.
The shared budget is five reranked seeds, parent expansion enabled, window
2 and at most 3,600 characters per expanded seed. This fixes the same
configured ceiling, not the number of characters actually sent.

ConditionalQA reads 50 answerable tuning questions on 25 pages through
grading. Its primary metric is `all_evidence_coverage` at `sent`; its
`several_sections` stratum has 27 questions on 19 pages. WixQA reads 40
Simulated tuning questions in 33 gold-article clusters through retrieval;
its primary is `gold_article` in the reranked top five. No answers were
generated and no relevance judge was run. The existing grading filter ran
only for ConditionalQA and was not changed.

Gold is attainable from the index for 50/50 and 40/40 questions, respectively.
Every arm measured every question, both lists of lost pairs are empty, and
the control has a nonzero primary mean in each base. Both pilots meet the
registered conditions for using their variance.

## Variance and its registered floor

Differences are paired `pool30` minus control. These descriptive movements
do not select a candidate or establish a quality improvement.

| Base | Questions | Clusters | Differing primary pairs | Sample variance | Registered variance |
|---|---:|---:|---:|---:|---:|
| conditionalqa | 50 | 25 | 1 | 0.0200 | 0.1000 |
| wixqa | 40 | 33 | 1 | 0.0250 | 0.1000 |

For ConditionalQA `several_sections`, no primary pair differs: sample
variance 0.0000 on 27 pairs. Its registered variance is still 0.1000,
the maximum of the grid, whole-pilot variance and stratum variance.
The primary means, which establish applicability only, are 0.580/0.560
on ConditionalQA and 0.525/0.500 on WixQA (control/perturbation).

The descriptive intraclass correlation is clamped to zero for both primary
rows; on WixQA the unclamped estimate is negative. The registered sizing
uses correlation 1 and the Student quantile at clusters minus one degrees
of freedom. A perturbation's correlation or mean does not choose the size.

## Time and the two alternatives for step 1

The timing sums `transform`, `embed`, `retrieve`, and for ConditionalQA
`grade`. Reranking is inside `retrieve` and is not added a second time.
Preparation, model loading outside these stages and waiting are excluded.
These are stage times on one host, a lower planning estimate, not speed
evidence or a wall-clock measurement of the entire pilot.

| Base | Arm | Seconds per question | Stage hours |
|---|---|---:|---:|
| conditionalqa | control | 364.04 | 5.06 |
| conditionalqa | pool30 | 363.12 | 5.04 |
| wixqa | control | 35.68 | 0.40 |
| wixqa | pool30 | 41.81 | 0.46 |

Step 1 uses the control: 364.04 seconds per ConditionalQA
question and 35.68 seconds per WixQA question. WixQA's two arms
on 200 ExpertWritten questions take an estimated 3.96 hours.
For ConditionalQA one question is read per eligible page. The alternatives
below each include those same 200 WixQA questions in both arms; they are
not two selections to be read together. The mechanism's registered
hypothesis chooses the stratum, not these pilot results.

| ConditionalQA stratum | Pages/questions | Registered MDE | Gain for rule at power 0.8 | Combined hours | Eight-hour nights |
|---|---:|---:|---:|---:|---:|
| primary | 165 | 0.069 | 0.071 | 37.33 | 4.67 |
| several_sections | 145 | 0.074 | 0.074 | 33.29 | 4.16 |

For WixQA alone: n=200, clusters=154, registered MDE 0.091,
gain-rule power at a true +0.05 0.334 and non-inferiority
power at a true zero 0.087. For the two ConditionalQA
alternatives those powers are 0.500/0.471 and 0.123/0.112. A neutral
mechanism is therefore expected to be inconclusive on non-inferiority;
the margin remains -0.02. These are scenario approximations, not achieved
power or confidence intervals from this pilot.

Only one primary pair changes in each base. At those differing shares the
tool's independent-pair scenario upper bounds for satisfying the interval
validity rule are 0.001934 (165 pages), 0.000730 (145 pages), and 0.026181
(WixQA). They are conditional on that scenario and do not certify future
intervals: the mechanism's paired differences must be checked separately.
The pilot cannot separate the retrieval perturbation from grading variation.
WixQA also changes question authorship between Simulated tuning and
ExpertWritten acceptance. The later refinement may raise the registered
variance; it cannot lower it or enlarge a selection for better power.

## Artifacts and verification

The committed [directory](../../reports/external/64a72e5/pilot/) contains only
`conditionalqa.aggregates.json`, `wixqa.aggregates.json`, `sizes.json` and
`receipt.json`. Each aggregate includes corpus, index, checkpoint, embedding
and reranker identities, configuration and run digests, registrations and
the measuring-code hashes. The receipt records completion and transport
checks; it is not a substitute for the underlying measurement.

| Base | Aggregate SHA-256 | Full measure SHA-256 (Mac only) |
|---|---|---|
| conditionalqa | `d37938fdb0f48d589400af0358a807b23a7a4e0d41df0f27ce0e5902e1da3bf7` | `e9905af44f8737b59b33013daa90e883b2125c6c0f8ea3633eead1d0cccc81e7` |
| wixqa | `4fe0324e3bb92d85706188b7d130adb5c7b333d3b492bd31f83f4c49db55782d` | `0a040357391cb30a203a2f5f514e66d8131283effa8160c692b8314a3bc341cd` |

Before transfer, each full measure and aggregate matched the SHA-256 in the
completed runner state. On the Mac each aggregate also exactly equalled its
full measure with `per_case` removed and `measure_sha256` added. Only the
aggregates left that host. Neither `measure` nor a retrieval arm was rerun.
The registered `sizes` command computed 124 rows from these two aggregates;
its output SHA-256 is `7f26292dcc0bd36c2dfb05c4e64f04a078844dfad1be3b0040b112a8a92cd839`.

`tests/test_external_pilot_artifact.py` binds these files to the receipt and
connected indexes, checks binary paired variances independently from counts,
replays all size rows, verifies the timing arithmetic and checks the capsule's
tables. It runs on the Mac with the connection artifact tests and
`test_docs_hygiene.py`, `test_docs_quality.py`, `test_docs_publication.py`.
The underlying pilot, gold, parts, power and base tests are a separate gate.

Still required: revision eleven, including exact locked-selection access,
the opening/restart contract, nomination and second-base outcomes, the
baseline/tuning/refinement selections and MultiHop-RAG advisory metrics;
then a cold review of that revision. Slice 1.7 has not started. Product
acceptance, the mechanism's gain and the plan's gap G39 remain open.
