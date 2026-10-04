# Capability: Evidence loss map over baseline artifacts

<!-- Durable spec: it outlives the run. One capability per file; MyFlow injects the requirements a task
     references into the WorkOrder and the review pack. Format is OpenSpec-compatible. -->

Plan slice 2.5 (G14) requires a map of where gold evidence is lost on its way
to the model: for every historical case, the first stage at which the gold is
no longer observed, or `unknown`. `scripts/evidence_loss_map.py` builds it. Its
archive mode reads archived candidate files and produced the
[preliminary map](../evidence/evidence-loss-map-prelim.md). Its baseline mode
reads a finished run of `scripts/production_baseline.py`, which records the
reranked, expanded and sent texts. The map selects nothing: the choice of
mechanisms belongs to the baseline slice.

## Requirement: the baseline map reads a finished, intact run

The baseline mode SHALL read the run through the collector's own loaders. It
SHALL refuse a run that is not finished, a run with an open abort, a run in
which the record of any case at any stage — prepare, transform, embed,
retrieve, grade — is missing or fails its integrity check, a chunk archive
whose SHA-256 differs from the corpus SHA-256 in the run's index receipt, and
a run whose records do not share one routing mode with the graph lane off. It
SHALL NOT write a partial map. The output SHALL carry the run's manifest digest and the path and
SHA-256 of every file it read: a file of the run by its path inside the run
directory, the chunk archive by its base name, a source file by its name in
the source manifest. The same run SHALL give the same bytes, wherever the
chunk archive and the sources are placed.

### Scenario: the chunk archive is not the indexed one
- **GIVEN** a finished run and a chunk archive with another SHA-256
- **WHEN** the baseline map is built
- **THEN** it refuses and writes nothing

### Scenario: a record the map takes no text from is damaged
- **GIVEN** a finished run in which the transform record of one case fails its
  integrity check
- **WHEN** the baseline map is built
- **THEN** it refuses and writes nothing

## Requirement: a loss is the first stage where a gold term is no longer observed

Gold of an H case SHALL be the terms of `expected.answer_contains`, looked for
in every text of a stage. Gold of an Hm case SHALL be the pairs of
`answer_sources` (term, document), looked for only in the texts of that
document. Terms SHALL be matched by the archive mode's rule (`_hits`).

The stages, in order, and the texts observed at each:

| stage | observed texts |
|---|---|
| `index` | every chunk of the chunk archive |
| `initial_pool` | the chunks of `vector` and of `pool` |
| `caps_dedup` | the chunks of `pool` |
| `rerank` | `seed_documents` |
| `expansion` | `expanded_documents` |
| `packing` | `documents` of the retrieve record |
| `grading` | `documents` of the grade record |

A term is lost when the `grading` stage does not hold it. Its first loss SHALL
be the first stage in this order that does not hold it, with one exception: a
term the index holds and neither `vector` nor `pool` holds SHALL be
`index_to_pool_unknown`. The collector records no BM25 candidate ids, so the
artifacts cannot tell a term no lane retrieved from a term the caps removed.
A term the `grading` stage holds is `no_observed_loss`, whatever the earlier
stages show. The first loss of a case SHALL be the earliest first loss of its
lost terms.

The answer stage SHALL be reported `unknown`: the run generates no answers.
The graph lane's caps and coherence stages SHALL be reported `not_observable`:
the run's mode is graph off. No loss is attributed to them, nor to the query
transform; the effective query is listed for reference only. An excluded case
and a case without gold SHALL be `unknown` with the reason. They are outside
the denominators, and the denominators SHALL be published for every stage.

### Scenario: gold reaches the sent context
- **GIVEN** a case whose gold term is missing from the reranked texts, is
  brought back by expansion and stays in the sent context
- **WHEN** the map is built
- **THEN** the case is `no_observed_loss` and is in no loss list

### Scenario: a term is found only in another document
- **GIVEN** an Hm case whose gold term occurs in the sent context only in a
  document other than its `answer_sources` document
- **WHEN** the map is built
- **THEN** the term is lost

### Scenario: an excluded case
- **GIVEN** a case the collector excluded at the grade stage
- **WHEN** the map is built
- **THEN** the case is `unknown` with the exclusion's stage and reason, and it
  is counted in no stage denominator

## Requirement: index losses, the RU→EN stratum and expansion losses are reported apart

A gold term the index does not hold SHALL be listed apart with its kind:
`split_by_chunking` when the source text holds it, `absent_from_sources` when
it does not, `unknown` when the sources cannot be read. The output SHALL say
that an index loss needs a code fix before the baseline is published.

The RU→EN stratum (G2) SHALL follow `ru_to_en` and `RU_TO_EN_RULE` of
`evaluation/devset.py`, with the case query as the question and the gold terms
as the facts, and the output SHALL carry the rule's version. The first-loss
counts SHALL be given for the stratum and for the rest: for H, for Hm and for
both together. A second set of rows under the archive mode's stratum proxy
SHALL be given the same way and labelled as such: the preliminary map is over
H alone, and only the H rows compare with it.

Expansion losses (G3) SHALL count three things apart: the terms the reranked
texts hold and the expanded texts do not, the terms the reranked texts hold
and the sent context does not, and the terms expansion adds.

### Scenario: a term cut by chunking
- **GIVEN** a gold term that a source file holds and no single chunk holds
- **WHEN** the map is built
- **THEN** the term is in the index-loss list as `split_by_chunking`
