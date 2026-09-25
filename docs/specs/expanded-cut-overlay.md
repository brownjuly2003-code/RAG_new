# Capability: expanded-cut-overlay

P1b replays fixed cuts of the reranked top five through production's parent-window
expansion. The arms, the ruler and the verdict were fixed before any expanded-context
metric was computed, in [`p1b-expanded-cut-plan.md`](p1b-expanded-cut-plan.md); this
file states what the evaluator (`scripts/p1b_expanded_cut.py`) and its published report
must do, so a test can check it.

## Requirement: the corpus is admitted only when it matches its manifest

The evaluator SHALL refuse to build a report unless the corpus directory it is given
holds exactly the files that `evaluation/aircargo_corpus.manifest.json` lists, each with
the recorded SHA-256.

### Scenario: a corpus file changed

- **GIVEN** a corpus directory in which one file differs from its manifest entry
- **WHEN** `build_report` runs on it
- **THEN** it raises `ValueError` whose message names that file

### Scenario: a file the manifest does not list

- **GIVEN** a corpus directory with one extra non-hidden file
- **WHEN** `build_report` runs on it
- **THEN** it raises `ValueError` whose message names that file

## Requirement: every candidate an arm can keep maps to exactly one chunk

The evaluator SHALL refuse to build a report unless every fresh top-5 candidate of every
case equals the text of exactly one rebuilt chunk whose source file name equals the
candidate's `prerank_sources` entry. It SHALL never pass an unmatched text on unexpanded.

### Scenario: a candidate that no chunk holds

- **GIVEN** a case whose rank-2 candidate text equals no rebuilt chunk
- **WHEN** `build_report` runs
- **THEN** it raises `ValueError` whose message names that case id

### Scenario: a candidate that two chunks hold

- **GIVEN** a case whose rank-1 candidate text equals two rebuilt chunks of its source file
- **WHEN** `build_report` runs
- **THEN** it raises `ValueError` whose message names that case id

### Scenario: a candidate from another source

- **GIVEN** a candidate whose text equals one chunk of `a.md` while its `prerank_sources` entry is `b.md`
- **WHEN** `build_report` runs
- **THEN** it raises `ValueError` whose message names that case id

## Requirement: expansion is production's own and runs on each arm's kept set

The evaluator SHALL stamp every rebuilt chunk with `metadata["chunk_index"]` in
ingestion order, as `vectordb/manager.py` does, refuse a chunk list in which two chunks
share a retriever key, and expand an arm's kept chunks by one call of
`HybridRetriever._expand_parents` per case on the whole kept set, in fresh rank order, at
window 2 and 3600 characters, the `config/settings.py` defaults.

### Scenario: two kept chunks with a neighbour between them

- **GIVEN** one document of header-less chunks at positions 0 to 4, short enough for every neighbour to fit the budget, with positions 1 and 3 kept
- **WHEN** the arm is expanded
- **THEN** the text of position 2 appears in exactly one expanded context

### Scenario: a cut frees a neighbour

- **GIVEN** that document, a control that keeps positions 1 and 3 and a cut that keeps only position 1
- **WHEN** both are expanded
- **THEN** the cut's context for position 1 contains the text of position 3 and the control's does not

### Scenario: a neighbour that repeats a kept chunk's text

- **GIVEN** one document of short header-less chunks at positions 0 to 4 whose positions 1 and 2 have the same text, with position 1 kept
- **WHEN** that chunk is expanded
- **THEN** its expanded context holds that text twice, since production keys chunks by source and index, not by text

### Scenario: two chunks with one retriever key

- **GIVEN** a rebuilt chunk list in which two chunks' metadata give them the same `_rrf_document_key`
- **WHEN** `build_report` runs
- **THEN** it raises `ValueError`

### Scenario: the production defaults

- **GIVEN** an environment without `RAG_PARENT_EXPANSION_WINDOW` and `RAG_PARENT_EXPANSION_MAX_CHARS`
- **WHEN** the evaluator's window and character cap are compared with the settings defaults
- **THEN** they equal `parent_expansion_window` and `parent_expansion_max_chars`, 2 and 3600

## Requirement: the arms are fixed and nothing is selected on expanded results

The evaluator SHALL build exactly the arms `top_k_5+exp`, `rel_0.2+exp`, `p1_cv+exp` (H
only) and `top_k_3+exp`. The primary cell SHALL be the P1 report's
`h.in_sample_best.cell`, and each H case's `p1_cv+exp` cell SHALL be the one that
`h.cross_validation.per_case` records for it.

### Scenario: a case whose P1 cell is `rel_0.7`

- **GIVEN** a P1 report whose per-case entry for one case names `rel_0.7`
- **WHEN** `p1_cv+exp` is built
- **THEN** that case keeps exactly the ranks `rel_0.7` keeps, and every other case the ranks of its own recorded cell

### Scenario: a case the P1 report does not list

- **GIVEN** a P1 report without a per-case entry for one H case
- **WHEN** `build_report` runs
- **THEN** it raises `ValueError` whose message names that case id

## Requirement: the primary ruler has no combined cap

The primary ruler SHALL score the expanded texts through P1's ruler path with no
combined character cap; only the diagnostic ruler applies P1's 6000-character cap.

### Scenario: a keyword past the cap

- **GIVEN** a case whose expanded texts hold its only keyword after the first 6000 characters
- **WHEN** both rulers score it
- **THEN** the primary ruler counts the keyword and the diagnostic ruler does not

## Requirement: an unexpanded selection that does not reproduce P1 invalidates the verdict

The report SHALL carry `INVALID_CONTROL` whenever a reproduction aggregate (H `top_k_5`,
`rel_0.2` and cross-validation; Hm `top_k_5` and `rel_0.2`) differs from the P1 report in
any field, whatever the expanded arms score.

### Scenario: one reproduction aggregate differs

- **GIVEN** a P1 report whose H `rel_0.2` recall differs from the recomputed one
- **WHEN** the report is built
- **THEN** `verdict.decision` is `INVALID_CONTROL`

## Requirement: SHIP_CANDIDATE needs every pre-registered condition

With every reproduction check passed, the decision SHALL be `SHIP_CANDIDATE` exactly when
the plan's five verdict conditions hold, and `NO_SHIP` otherwise. The report SHALL state
each condition as its own boolean.

### Scenario: a precise cut that loses one fact

- **GIVEN** `rel_0.2+exp` at precision ≥ 0.63 that meets the floor and keeps the control's aggregate recall, while one case loses a keyword the control matched
- **WHEN** the verdict is computed
- **THEN** the decision is `NO_SHIP` and that case appears in the fact losses

### Scenario: the held-out check fails

- **GIVEN** `rel_0.2+exp` meeting conditions 1, 2, 3 and 5 while `p1_cv+exp` misses the precision gate
- **WHEN** the verdict is computed
- **THEN** the decision is `NO_SHIP`

### Scenario: every condition holds

- **GIVEN** arms that meet all five conditions
- **WHEN** the verdict is computed
- **THEN** the decision is `SHIP_CANDIDATE` and the scope says it changes no default

## Requirement: the published report is pinned and quoted exactly

A committed P1b report SHALL be guarded by a test that pins the report's SHA-256, the
code commit it was built at, the corpus, pool, score-artifact and P1-report SHA-256
values and its decision, and the evidence capsule SHALL quote no number that the report
does not contain.

### Scenario: the committed report changes

- **GIVEN** the committed P1b report altered by any byte
- **WHEN** the artifact test runs
- **THEN** it fails on the pinned SHA-256

### Scenario: the capsule states a number

- **GIVEN** a number written in the capsule outside code spans
- **WHEN** the artifact test runs
- **THEN** it fails unless that number occurs in the report
