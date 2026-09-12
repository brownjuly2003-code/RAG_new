# GR-1b query-only subset control — NO-SHIP

Measured 2026-09-12 on the frozen GR-1b archive, source `9322806`, clean
tree at measurement. [Raw report](../../reports/gr/gr1b-query-control.json)
pins corpus, dataset, labels, archive, code hashes and configuration.

| arm | precision | recall | FULL/PART/MISS |
|---|---:|---:|---|
| G1 | 0.5475 | 0.9200 | 88/8/4 |
| Query-only subset | 0.6268 | 0.7250 | 67/11/22 |

Precision delta is +0.079323, paired bootstrap CI95 [0.059243, 0.099616].
Recall delta is -0.195000, CI95 [-0.270000, -0.125000]. There are 22 FULL
regressions and 25 cases losing previously matched keywords. This fails all
joint acceptance thresholds; runtime retrieval remains unchanged.

## Prespecified control

Enumerate the 31 nonempty subsets of original reranked top-five, preserving
order and applying the 6000-character cap before scoring. Preserve query
terms found in capped original top-five, maximise existing context precision
with an empty expected-keyword list; ties prefer fewer indices then original
indices. Query preservation uses normalised word tokens of length >=3;
the inherited precision function uses normalised whitespace tokens. Fall
back to original top-five for empty queries or zero positive query signal.
The selector receives only query, candidate texts and cap. Labels are used
after selection to measure losses, never for selection or G1 fallback.

This is one exploratory control, not a tuned selector or evidence that all
query-only methods fail. Its lexical objective rewards concentration on query
words without ensuring answer sufficiency. No runtime change is justified.
The 100 agent-written, unapproved cases are repeatedly inspected, not held
out; case-bootstrap intervals do not model shared-source dependence.

## Three oracle-infeasible cases

The following G1 keyword hits are absent from the uncapped original top-five:

| case | missing hits | present elsewhere in archived reranked candidates |
|---|---|---|
| aircargo-dangerous-goods-clearance | UN | yes |
| aircargo-waybill-first-mile-fields | waybill_number, vehicle_number | no |
| aircargo-cross-border-required-fields | route_countries, vehicle_tir_carnet | no |

Thus top-five truncation alone cannot explain infeasibility. The latter two
need text beyond the archived reranked list to preserve these G1 hits.
This localises candidate-content differences; it does not prove which producer
stage introduced them, given the archive's metadata/provenance limitations.
Substring `UN` is a lexical hit, not independently verified dangerous-goods
evidence. No labels have been changed.

## Reproduction and next work

```powershell
python -m scripts.gr1b_query_control
python -m pytest tests/test_gr1b_query_control.py tests/test_gr1b_controls.py tests/test_docs_hygiene.py -q -p no:schemathesis --basetemp=.tmp/pytest-query-published
```

Tests reproduce every case, paired interval, input hash and the missing-hit
table directly from the archive. No models, network or new embeddings.
Next: recover source metadata for evidence-preserving expansion before a
further selector experiment; retain GR-4/GR-2/GR-3 and held-out semantic
confirmation. Do not tune this selector against these observed losses.
