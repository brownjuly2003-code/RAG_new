# Capability: adaptive-k-cut

P1 evaluates a label-free cut of the reranked top five (rank 1 always kept) on fresh
`BAAI/bge-reranker-v2-m3` scores. The grid, the ruler and the verdict thresholds were
fixed before any score was seen, in [`p1-adaptive-k-plan.md`](p1-adaptive-k-plan.md);
this file states what the evaluator (`scripts/p1_adaptive_k.py`) and its published
report must do, so a test can check it.

## Requirement: fresh scores are admitted only when they reproduce the archived ranking

The evaluator SHALL refuse to build a report unless the score artifact is complete, was
captured with `BAAI/bge-reranker-v2-m3`, belongs to the archive it is paired with, and
its fresh order reproduces the archived candidate order of every case.

### Scenario: an incomplete score artifact

- **GIVEN** a score artifact whose `complete` is false
- **WHEN** `build_report` runs on it
- **THEN** it raises `ValueError` and returns no report

### Scenario: scores from another reranker

- **GIVEN** a score artifact whose provenance names a model other than `BAAI/bge-reranker-v2-m3`
- **WHEN** `build_report` runs on it
- **THEN** it raises `ValueError`

### Scenario: one case ranked differently from the archive

- **GIVEN** an archive in which one case's candidates are not in the fresh score order
- **WHEN** `build_report` runs on it
- **THEN** it raises `ValueError` whose message names that case id

## Requirement: a control that does not reproduce the published baseline invalidates the verdict

The report SHALL carry the decision `INVALID_CONTROL` whenever the aggregate of the
`top_k_5` control differs from the published H baseline in any field of `PUBLISHED_H`,
whatever the other cells score. Only a reproducing control can yield `SHIP_CANDIDATE`
or `NO_SHIP`.

### Scenario: the control misses the published numbers

- **GIVEN** a pool whose `top_k_5` aggregate differs from `PUBLISHED_H`
- **WHEN** the report is built
- **THEN** `h.control_reproduces_published` is false and `verdict.decision` is `INVALID_CONTROL`

### Scenario: the control reproduces the published numbers

- **GIVEN** a pool whose `top_k_5` aggregate equals `PUBLISHED_H`
- **WHEN** the report is built
- **THEN** `verdict.decision` is `SHIP_CANDIDATE` exactly when both `precision_gate_met` and `h_relative_constraints_met` are true, and `NO_SHIP` otherwise

## Requirement: the headline cell is chosen on training cases only

The cross-validated headline SHALL choose one primary cell per fold from that fold's
training cases alone: the highest exact train precision among cells whose train recall,
FULL count and MISS count are no worse than `top_k_5` on the same cases, the control
itself when no cell qualifies. The chosen cell is applied to the held-out fold, and
every case appears exactly once in the held-out rows.

### Scenario: a cell that loses a fact only on one fold

- **GIVEN** a cell that is better on the fold-1 cases but loses a FULL on the fold-0 cases
- **WHEN** `cross_validate` runs over the two folds
- **THEN** the fold whose training set holds the fold-0 cases picks the control and the other fold picks the cell

### Scenario: a MISS increase alone disqualifies a cell

- **GIVEN** a candidate cell that keeps recall and FULL equal to the control but turns one PART into a MISS
- **WHEN** `select_cell` compares it with the control
- **THEN** the control is returned, while the same cell without the MISS is picked

### Scenario: a case without a fold

- **GIVEN** `folds_by_case` that omits one control case
- **WHEN** `cross_validate` runs
- **THEN** it raises `ValueError`

## Requirement: the label-using oracle never counts a lost fact

The best-prefix oracle SHALL pick, per case, the shortest highest-precision prefix whose
matched keywords include every keyword the control matched and whose keyword status is no
worse than the control's; it is reported as a diagnostic that is not deployable.

### Scenario: a prefix with the control's keywords but a worse status

- **GIVEN** a control row with status FULL and a `top_k_1` row with the same matched keywords, status PART and the highest precision
- **WHEN** `oracle_best_prefix` runs
- **THEN** it does not pick `top_k_1` and picks the best admissible prefix instead

## Requirement: the published report is pinned and quoted exactly

A committed P1 report SHALL be guarded by a test that pins the report's SHA-256, the
code commit it was built at, the score-capture commit, both score artifacts' SHA-256 and
its decision, and the evidence capsule SHALL quote no number that the report does not
contain, the counts of its named case lists included.

### Scenario: the committed report changes

- **GIVEN** `reports/p1/p1-adaptive-k.json` altered by any byte
- **WHEN** the artifact test runs
- **THEN** it fails on the pinned SHA-256

### Scenario: the capsule states a number

- **GIVEN** a number written in the capsule outside code spans
- **WHEN** the artifact test runs
- **THEN** it fails unless that number occurs in the report, either as a JSON number
  (not a boolean) or as a count the report's table prints, the number of entries of a
  comparison's `lost_keyword_cases` or `full_regressions` list
