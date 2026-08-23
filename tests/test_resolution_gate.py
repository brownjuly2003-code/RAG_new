from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from evaluation.resolution import (
    GateCheckStatus,
    OutcomeCheckStatus,
    ReleaseSafetyGateIssueCode,
    ReleaseSafetySurface,
    ResolutionDisposition,
    SyntheticReleaseEvidenceManifest,
    SyntheticReleaseSafetyCheck,
    SyntheticReleaseSafetyGateCompatibilityError,
    SyntheticReleaseSafetyStatus,
    build_manifest_coverage_report,
    build_synthetic_outcome_comparison_input,
    build_synthetic_outcome_comparison_report,
    build_synthetic_release_evidence_manifest,
    build_synthetic_release_safety_gate_report,
    canonical_synthetic_release_safety_gate_report_json,
    synthetic_release_evidence_manifest_digest,
    synthetic_release_safety_gate_report_digest,
)
from tests.test_resolution_comparison import _pair
from tests.test_resolution_release import _manifest

_ARTIFACT_DIR = Path(__file__).parents[1] / "evaluation" / "resolution" / "gates" / "v0.1"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _checks(
    manifest: SyntheticReleaseEvidenceManifest,
    *,
    overrides: dict[ReleaseSafetySurface, GateCheckStatus] | None = None,
) -> tuple[SyntheticReleaseSafetyCheck, ...]:
    statuses = overrides or {}
    manifest_digest = synthetic_release_evidence_manifest_digest(manifest)
    return tuple(
        SyntheticReleaseSafetyCheck(
            surface=surface,
            status=statuses.get(surface, GateCheckStatus.PASS),
            release_evidence_manifest_digest=manifest_digest,
            evidence_digest=_digest(
                f"PRIVATE {surface.value} "
                f"{statuses.get(surface, GateCheckStatus.PASS).value} EVIDENCE"
            ),
        )
        for surface in ReleaseSafetySurface
    )


def _report(
    *,
    overrides: dict[ReleaseSafetySurface, GateCheckStatus] | None = None,
    clean_candidate: bool = False,
):
    if clean_candidate:
        baseline_run, candidate_run, comparison = _pair()
        candidate_input, corpus, replay_manifest, plan, result, _, unverified_id = candidate_run
        clean_records = tuple(
            replace(
                record,
                resolution=ResolutionDisposition.NOT_CLAIMED,
                checks=tuple(
                    replace(check, status=OutcomeCheckStatus.PASS) for check in record.checks
                ),
            )
            if record.scenario_id == unverified_id
            else record
            for record in candidate_input.ledger.records
        )
        clean_ledger = replace(candidate_input.ledger, records=clean_records)
        clean_candidate_input = build_synthetic_outcome_comparison_input(
            role=candidate_input.role,
            input_id=candidate_input.input_id,
            version=candidate_input.version,
            definition=candidate_input.definition,
            corpus=corpus,
            manifest=replay_manifest,
            coverage_report=build_manifest_coverage_report(corpus, replay_manifest),
            plan=plan,
            replay_result=result,
            ledger=clean_ledger,
        )
        comparison = build_synthetic_outcome_comparison_report(
            comparison_id=comparison.comparison_id,
            version=comparison.version,
            baseline=baseline_run[0],
            candidate=clean_candidate_input,
        )
        manifest = build_synthetic_release_evidence_manifest(
            manifest_id="shipment-status-synthetic-evidence",
            version="2026.08.23-g7",
            baseline=baseline_run[0],
            candidate=clean_candidate_input,
            comparison=comparison,
        )
        baseline = baseline_run[0]
        candidate = clean_candidate_input
    else:
        baseline, candidate, comparison, manifest = _manifest()
    report = build_synthetic_release_safety_gate_report(
        gate_id="shipment-status-synthetic-safety",
        version="2026.08.23-g8",
        release_evidence_manifest=manifest,
        baseline=baseline,
        candidate=candidate,
        comparison=comparison,
        checks=_checks(manifest, overrides=overrides),
    )
    return baseline, candidate, comparison, manifest, report


def test_complete_passing_surface_set_is_safety_only_and_non_authorizing() -> None:
    _, candidate, _, manifest, report = _report(clean_candidate=True)

    assert report.release_evidence_manifest_digest == (
        synthetic_release_evidence_manifest_digest(manifest)
    )
    assert report.candidate_input_digest == manifest.candidate.input_digest
    assert report.candidate_outcome_report_digest == manifest.candidate.report_digest
    assert len(report.checks) == len(ReleaseSafetySurface) == 7
    assert {check.surface for check in report.checks} == set(ReleaseSafetySurface)
    assert all(check.status is GateCheckStatus.PASS for check in report.checks)
    assert report.safety_status is SyntheticReleaseSafetyStatus.PASS
    assert report.failed_surfaces == ()
    assert report.unverified_claimed_scenario_ids == ()
    assert report.owner_status == "unconfirmed"
    assert report.evidence_class == "synthetic_local"
    assert report.decision_semantics == "synthetic_safety_only"
    assert report.business_claimable is False
    assert report.deployment_authorized is False
    assert candidate.role.value == "candidate"


def test_unverified_claimed_outcome_fails_even_when_every_surface_passes() -> None:
    _, candidate, _, _, report = _report()

    assert candidate.report.unverified_claimed_scenario_ids
    assert report.unverified_claimed_scenario_ids == (
        candidate.report.unverified_claimed_scenario_ids
    )
    assert report.failed_surfaces == ()
    assert report.safety_status is SyntheticReleaseSafetyStatus.FAIL


@pytest.mark.parametrize("surface", tuple(ReleaseSafetySurface))
def test_each_required_surface_fails_the_gate(surface: ReleaseSafetySurface) -> None:
    *_, report = _report(
        overrides={surface: GateCheckStatus.FAIL},
        clean_candidate=True,
    )

    assert report.safety_status is SyntheticReleaseSafetyStatus.FAIL
    assert report.failed_surfaces == (surface,)
    assert report.deployment_authorized is False


@pytest.mark.parametrize(
    "status",
    (GateCheckStatus.FAIL, GateCheckStatus.ERROR, GateCheckStatus.SKIPPED),
)
def test_every_nonpass_status_fails_closed(status: GateCheckStatus) -> None:
    *_, report = _report(
        overrides={ReleaseSafetySurface.EVALUATOR_INFRASTRUCTURE: status},
        clean_candidate=True,
    )

    assert report.safety_status is SyntheticReleaseSafetyStatus.FAIL
    assert report.failed_surfaces == (ReleaseSafetySurface.EVALUATOR_INFRASTRUCTURE,)


def test_missing_duplicate_and_foreign_manifest_checks_fail_closed() -> None:
    baseline, candidate, comparison, manifest = _manifest()
    checks = _checks(manifest)
    cases = (
        (
            checks[:-1],
            ReleaseSafetyGateIssueCode.CHECK_SET_MISMATCH,
        ),
        (
            checks + (checks[0],),
            ReleaseSafetyGateIssueCode.CHECK_SET_MISMATCH,
        ),
        (
            (replace(checks[0], release_evidence_manifest_digest="f" * 64),) + checks[1:],
            ReleaseSafetyGateIssueCode.CHECK_MANIFEST_MISMATCH,
        ),
    )

    for supplied_checks, issue_code in cases:
        with pytest.raises(SyntheticReleaseSafetyGateCompatibilityError) as error:
            build_synthetic_release_safety_gate_report(
                gate_id="shipment-status-synthetic-safety",
                version="2026.08.23-g8",
                release_evidence_manifest=manifest,
                baseline=baseline,
                candidate=candidate,
                comparison=comparison,
                checks=supplied_checks,
            )
        assert error.value.issue_codes == (issue_code,)


def test_forged_release_evidence_manifest_fails_closed() -> None:
    baseline, candidate, comparison, manifest = _manifest()
    forged = replace(manifest, comparison_report_digest="f" * 64)

    with pytest.raises(SyntheticReleaseSafetyGateCompatibilityError) as error:
        build_synthetic_release_safety_gate_report(
            gate_id="shipment-status-synthetic-safety",
            version="2026.08.23-g8",
            release_evidence_manifest=forged,
            baseline=baseline,
            candidate=candidate,
            comparison=comparison,
            checks=_checks(forged),
        )

    assert error.value.issue_codes == (ReleaseSafetyGateIssueCode.RELEASE_EVIDENCE_MISMATCH,)


def test_direct_status_or_authorization_override_is_rejected() -> None:
    *_, report = _report(overrides={ReleaseSafetySurface.POSTCONDITION: GateCheckStatus.FAIL})

    with pytest.raises(ValueError, match="safety_status"):
        replace(report, safety_status=SyntheticReleaseSafetyStatus.PASS)
    with pytest.raises(ValueError, match="failed_surfaces"):
        replace(report, failed_surfaces=())
    with pytest.raises(ValueError, match="deployment_authorized"):
        replace(report, deployment_authorized=True)


def test_canonical_failing_report_is_materialized_stable_and_private() -> None:
    baseline, candidate, comparison, manifest, report = _report(
        overrides={ReleaseSafetySurface.CONTRACT: GateCheckStatus.FAIL}
    )
    canonical = canonical_synthetic_release_safety_gate_report_json(report)
    digest = synthetic_release_safety_gate_report_digest(report)
    payload = json.loads(
        (_ARTIFACT_DIR / "shipment-status-synthetic-safety.json").read_text(encoding="utf-8")
    )
    normalized = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    reordered = build_synthetic_release_safety_gate_report(
        gate_id=report.gate_id,
        version=report.version,
        release_evidence_manifest=manifest,
        baseline=baseline,
        candidate=candidate,
        comparison=comparison,
        checks=tuple(
            reversed(
                _checks(
                    manifest,
                    overrides={ReleaseSafetySurface.CONTRACT: GateCheckStatus.FAIL},
                )
            )
        ),
    )

    assert normalized == canonical
    assert (_ARTIFACT_DIR / "shipment-status-synthetic-safety.sha256").read_text(
        encoding="utf-8"
    ).strip() == digest
    assert synthetic_release_safety_gate_report_digest(reordered) == digest

    lowered = canonical.lower()
    assert '"safety_status":"fail"' in lowered
    assert '"deployment_authorized":false' in lowered
    assert '"business_claimable":false' in lowered
    assert '"decision_semantics":"synthetic_safety_only"' in lowered
    assert '"unverified_claimed_scenario_count":1' in lowered
    for forbidden in (
        "private contract fail evidence",
        "private candidate message",
        "private-world",
        "private-fault",
        "private.expected.path",
        "private outcome evidence",
        "private raw response",
        '"threshold"',
        '"approved"',
        '"ready"',
        '"promotion"',
    ):
        assert forbidden not in lowered
