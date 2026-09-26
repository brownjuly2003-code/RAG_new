# Capability: aircargo-label-approval

The 100 air-cargo cases in `evaluation/curated_cases_aircargo.jsonl` carry journey labels
that an agent proposed. Under [ADR 0008](../adr/0008-inherited-ci-red-disposition.md), only
a human approval makes a label `real_labelled`. The approval tool,
`scripts/aircargo_labels.py approve`, recorded an approval by rewriting that file in place.
The same file is an input of every published phase-C, GR, P1, D and Chroma measurement, and
the tests that replay those reports pin its bytes.

A probe on 2026-09-25 (NOT_EVIDENCE) ran `approve` for batches 1 to 5 in a throwaway clone
on the Mac. The unit suite then had 21 failures and 2 errors, all of them pins of the
dataset's bytes. So an approval must not touch the dataset. It is recorded in a sidecar
instead, the same pattern as the question-class labels in
`evaluation/curated_cases_question_class.jsonl`.

This capability changes how approvals are stored and read. It changes no label, no case and
no published number.

## Requirement: an approval never changes the dataset

Recording an approval SHALL leave `evaluation/curated_cases_aircargo.jsonl` byte-identical.
The label manifest's `dataset_sha256` SHALL stay the dataset's digest.

### Scenario: approving a batch
- **GIVEN** the checked-in dataset and no approval
- **WHEN** `python scripts/aircargo_labels.py approve --batch 1 --approver julia` runs
- **THEN** the dataset's bytes are unchanged
- **AND** the approval is written to `evaluation/curated_cases_aircargo.approvals.json`

## Requirement: approvals live in a sidecar pinned to the dataset

The sidecar SHALL name the dataset's path and its digest, as `dataset_digest` computes it.
It SHALL list one approval per batch. Each approval gives the batch number, the approver,
the approval date and the batch's case ids. It MAY carry a note of at most 512 characters.

Loading SHALL fail, and the error SHALL name the problem, when:
- the sidecar's digest differs from the dataset's;
- a listed case id is not in the dataset, or not in the named batch;
- an approval does not cover every case of its batch;
- a batch or a case is approved twice;
- an approved case's dataset line already carries `approved_by`;
- the approver is named like an agent: the name starts with `agent`, as every
  `labelled_by` in the dataset does.

### Scenario: the dataset moved under the approvals
- **GIVEN** a sidecar pinned to one dataset digest
- **WHEN** the dataset changes by one byte and the labels are loaded with the sidecar
- **THEN** loading fails and names the digest mismatch

### Scenario: a partial or foreign batch
- **GIVEN** a sidecar whose batch 2 approval lists 19 of its 20 cases, or a case from batch 3
- **WHEN** the labels are loaded with the sidecar
- **THEN** loading fails and names the batch

### Scenario: a double approval
- **GIVEN** a sidecar that approves batch 1 twice, or a case whose dataset line already has
  `approved_by`
- **WHEN** the labels are loaded with the sidecar
- **THEN** loading fails

## Requirement: the evidence class follows the sidecar

A case in an approved batch SHALL load with `approved_by` set to the approver, so its
evidence class is `real_labelled`. Every other case SHALL stay `agent_labelled`. The label
manifest's summary and its corpus `evidence_class` SHALL be computed over these merged
labels. The manifest SHALL pin the sidecar's path and SHA-256, or record that there is no
sidecar.

### Scenario: all five batches approved
- **GIVEN** a sidecar that approves batches 1 to 5
- **WHEN** the manifest is rebuilt
- **THEN** its summary has 100 `real_labelled`, 0 `agent_labelled` and approved batches 1 to 5
- **AND** its corpus `evidence_class` is `real_labelled`

### Scenario: no sidecar
- **GIVEN** no sidecar
- **WHEN** the labels are loaded
- **THEN** every case is `agent_labelled`, as before this capability

## Requirement: approve and verify keep the three files in step

`approve` SHALL refuse a batch that is already approved unless `--reapprove` is given;
`--reapprove` replaces that batch's approval. After an approval, `approve` SHALL rewrite the
manifest. `verify` SHALL fail when the manifest no longer describes the dataset and the
sidecar together, for example after a hand edit of the sidecar. Readers that parse only the
dataset's bytes, such as journey admission, SHALL keep their behaviour.

### Scenario: a hand-edited sidecar
- **GIVEN** a verified dataset, sidecar and manifest
- **WHEN** one approver name in the sidecar is edited by hand
- **THEN** `verify` fails and names the sidecar digest
