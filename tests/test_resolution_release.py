from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from evaluation.resolution import (
    ReleaseEvidenceIssueCode,
    SyntheticReleaseEvidenceBindingError,
    build_synthetic_release_evidence_manifest,
    canonical_synthetic_release_evidence_manifest_json,
    synthetic_outcome_comparison_input_digest,
    synthetic_outcome_comparison_report_digest,
    synthetic_release_evidence_manifest_digest,
)
from tests.test_resolution_comparison import _pair

_ARTIFACT_DIR = Path(__file__).parents[1] / "evaluation" / "resolution" / "releases" / "v0.1"


def _manifest():
    baseline, candidate, comparison = _pair()
    manifest = build_synthetic_release_evidence_manifest(
        manifest_id="shipment-status-synthetic-evidence",
        version="2026.08.23-g7",
        baseline=baseline[0],
        candidate=candidate[0],
        comparison=comparison,
    )
    return baseline[0], candidate[0], comparison, manifest


def test_manifest_binds_exact_inputs_and_recomputed_report_without_a_verdict() -> None:
    baseline, candidate, comparison, manifest = _manifest()

    assert manifest.comparison_id == comparison.comparison_id
    assert manifest.comparison_version == comparison.version
    assert manifest.metric_definition_digest == comparison.metric_definition_digest
    assert manifest.corpus_digest == comparison.corpus_digest
    assert manifest.corpus_case_count == comparison.corpus_case_count == 17
    assert manifest.baseline == comparison.baseline
    assert manifest.candidate == comparison.candidate
    assert manifest.baseline.input_digest == synthetic_outcome_comparison_input_digest(baseline)
    assert manifest.candidate.input_digest == synthetic_outcome_comparison_input_digest(candidate)
    assert manifest.comparison_report_digest == synthetic_outcome_comparison_report_digest(
        comparison
    )
    assert manifest.owner_status == "unconfirmed"
    assert manifest.evidence_class == "synthetic_local"
    assert manifest.decision_semantics == "evidence_only"
    assert manifest.business_claimable is False


def test_swapped_roles_and_incompatible_pair_fail_closed() -> None:
    baseline, candidate, comparison = _pair()

    with pytest.raises(SyntheticReleaseEvidenceBindingError) as swapped:
        build_synthetic_release_evidence_manifest(
            manifest_id="shipment-status-synthetic-evidence",
            version="2026.08.23-g7",
            baseline=candidate[0],
            candidate=baseline[0],
            comparison=comparison,
        )
    assert swapped.value.issue_codes == (ReleaseEvidenceIssueCode.ROLE_MISMATCH,)

    other_baseline, other_candidate, _ = _pair(
        definition=replace(baseline[0].definition, recontact_window_days=14)
    )
    with pytest.raises(SyntheticReleaseEvidenceBindingError) as incompatible:
        build_synthetic_release_evidence_manifest(
            manifest_id="shipment-status-synthetic-evidence",
            version="2026.08.23-g7",
            baseline=other_baseline[0],
            candidate=candidate[0],
            comparison=comparison,
        )
    assert incompatible.value.issue_codes == (ReleaseEvidenceIssueCode.INPUT_PAIR_INCOMPATIBLE,)
    assert other_candidate[0].metric_definition_digest != candidate[0].metric_definition_digest


def test_stale_comparison_input_reference_fails_closed() -> None:
    baseline, candidate, comparison = _pair()
    stale = replace(
        comparison,
        baseline=replace(comparison.baseline, input_digest="f" * 64),
    )

    with pytest.raises(SyntheticReleaseEvidenceBindingError) as error:
        build_synthetic_release_evidence_manifest(
            manifest_id="shipment-status-synthetic-evidence",
            version="2026.08.23-g7",
            baseline=baseline[0],
            candidate=candidate[0],
            comparison=stale,
        )

    assert error.value.issue_codes == (
        ReleaseEvidenceIssueCode.COMPARISON_REPORT_MISMATCH,
        ReleaseEvidenceIssueCode.INPUT_REFERENCE_MISMATCH,
    )


def test_foreign_comparison_identity_fails_closed() -> None:
    baseline, candidate, comparison = _pair()
    foreign = replace(comparison, metric_definition_digest="f" * 64)

    with pytest.raises(SyntheticReleaseEvidenceBindingError) as error:
        build_synthetic_release_evidence_manifest(
            manifest_id="shipment-status-synthetic-evidence",
            version="2026.08.23-g7",
            baseline=baseline[0],
            candidate=candidate[0],
            comparison=foreign,
        )

    assert error.value.issue_codes == (ReleaseEvidenceIssueCode.COMPARISON_REPORT_MISMATCH,)


def test_semantically_identical_inputs_reproduce_the_same_manifest() -> None:
    baseline, candidate, comparison, manifest = _manifest()
    reordered_baseline = replace(
        baseline,
        ledger=replace(baseline.ledger, records=tuple(reversed(baseline.ledger.records))),
    )

    reproduced = build_synthetic_release_evidence_manifest(
        manifest_id=manifest.manifest_id,
        version=manifest.version,
        baseline=reordered_baseline,
        candidate=candidate,
        comparison=comparison,
    )

    assert canonical_synthetic_release_evidence_manifest_json(reproduced) == (
        canonical_synthetic_release_evidence_manifest_json(manifest)
    )
    assert synthetic_release_evidence_manifest_digest(reproduced) == (
        synthetic_release_evidence_manifest_digest(manifest)
    )


def test_canonical_manifest_is_materialized_stable_and_private() -> None:
    _, _, _, manifest = _manifest()
    canonical = canonical_synthetic_release_evidence_manifest_json(manifest)
    digest = synthetic_release_evidence_manifest_digest(manifest)
    payload = json.loads(
        (_ARTIFACT_DIR / "shipment-status-synthetic-evidence.json").read_text(encoding="utf-8")
    )
    normalized = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    assert normalized == canonical
    assert (_ARTIFACT_DIR / "shipment-status-synthetic-evidence.sha256").read_text(
        encoding="utf-8"
    ).strip() == digest
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == digest

    lowered = canonical.lower()
    assert '"business_claimable":false' in lowered
    assert '"owner_status":"unconfirmed"' in lowered
    assert '"decision_semantics":"evidence_only"' in lowered
    for forbidden in (
        "private candidate message",
        "private-world",
        "private-fault",
        "private.expected.path",
        "private outcome evidence",
        "private raw response",
        '"release_decision"',
        '"release_verdict"',
        '"threshold"',
        '"promotion"',
        '"approved"',
        '"ready"',
    ):
        assert forbidden not in lowered
