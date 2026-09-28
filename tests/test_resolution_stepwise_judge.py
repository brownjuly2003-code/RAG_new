from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from evaluation.resolution.stepwise_judge import (
    StepStatus,
    grade_evidence_export,
    grade_retrieval_path,
)
from resolution.application.shipment_status import (
    ClaimCandidate,
    ClaimEvidenceLink,
    PostconditionVersion,
)
from resolution.composition import load_shipment_response_contract
from resolution.evidence_view import evidence_view
from tests.test_resolution_response_shape import _run
from tests.test_shipment_status_shadow import NOW


class _EvidenceNLIScorer:
    def __init__(self, supported: bool | None) -> None:
        self.supported = supported
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def score(self, answer: str, contexts: tuple[str, ...]) -> dict[str, int]:
        self.calls.append((answer, contexts))
        if self.supported is None:
            return {"n_claims": 0, "n_supported_claims": 0}
        return {"n_claims": 1, "n_supported_claims": int(self.supported)}


def _grade(export):
    return grade_evidence_export(
        export, contract=load_shipment_response_contract(), as_of=NOW
    )


def test_verified_bundle_passes_each_deterministic_step() -> None:
    result = _grade(_run().evidence_export)

    assert result.status is StepStatus.PASS
    assert {step.name: step.status for step in result.steps} == {
        "contract": StepStatus.PASS,
        "source": StepStatus.PASS,
        "policy": StepStatus.PASS,
        "claims": StepStatus.PASS,
        "terminal": StepStatus.PASS,
    }


def test_pinned_contract_identity_is_checked() -> None:
    export = _run().evidence_export
    altered = replace(export, contract=replace(export.contract, digest="0" * 64))

    result = _grade(altered)

    assert result.status is StepStatus.FAIL
    assert result.step("contract").reason_codes == ("contract_identity_mismatch",)


def test_source_freshness_uses_the_contract_limit() -> None:
    export = _run().evidence_export
    altered = replace(
        export,
        source_observation=replace(
            export.source_observation, observed_at=NOW - timedelta(seconds=301)
        ),
    )

    result = _grade(altered)

    assert result.step("source").status is StepStatus.FAIL
    assert "source_stale" in result.step("source").reason_codes


def test_policy_must_allow_disclosure_and_cover_the_effective_time() -> None:
    export = _run().evidence_export
    altered = replace(
        export,
        policy=replace(
            export.policy, decision="deny", valid_to=NOW - timedelta(seconds=1)
        ),
    )

    result = _grade(altered)

    assert result.step("policy").status is StepStatus.FAIL
    assert result.step("policy").reason_codes == (
        "policy_not_effective",
        "policy_disallows_verified",
    )


def test_policy_with_naive_end_time_fails_closed() -> None:
    export = _run().evidence_export
    altered = replace(
        export,
        policy=replace(export.policy, valid_to=datetime(2026, 9, 2)),
    )

    result = _grade(altered)

    assert result.step("policy").reason_codes == ("policy_not_effective",)


def test_claim_digest_must_match_the_cited_evidence() -> None:
    export = _run().evidence_export
    claim = export.claim_links[0]
    altered = replace(
        export,
        claim_links=(
            replace(claim, evidence_digests=("0" * 64, *claim.evidence_digests[1:])),
            *export.claim_links[1:],
        ),
    )

    result = _grade(altered)

    assert result.step("claims").status is StepStatus.FAIL
    assert result.step("claims").reason_codes == ("claim_evidence_mismatch",)


def test_claim_cannot_drop_the_policy_reference() -> None:
    export = _run().evidence_export
    claim = export.claim_links[0]
    altered = replace(
        export,
        claim_links=(
            replace(
                claim,
                evidence_requirement_ids=claim.evidence_requirement_ids[:1],
                evidence_digests=claim.evidence_digests[:1],
            ),
            *export.claim_links[1:],
        ),
    )

    result = _grade(altered)

    assert result.step("claims").status is StepStatus.FAIL
    assert result.step("claims").reason_codes == ("claim_evidence_mismatch",)


def test_missing_source_cannot_match_a_null_claim_digest() -> None:
    export = _run((ClaimCandidate("insurance", "Fully insured.", ()),)).evidence_export
    forged = ClaimEvidenceLink(
        "shipment-status",
        "Shipment SHP-100 status is in_transit.",
        ("shipment-observation", "shipment-policy"),
        (None, export.policy.content_digest),
    )
    altered = replace(export, source_observation=None, claim_links=(forged,))

    result = _grade(altered)

    assert result.step("claims").status is StepStatus.FAIL
    assert result.step("claims").reason_codes == ("claim_evidence_mismatch",)


def test_empty_source_field_cannot_pass_as_a_literal_claim() -> None:
    export = _run().evidence_export
    claim = export.claim_links[1]
    altered = replace(
        export,
        source_observation=replace(export.source_observation, location=""),
        claim_links=(
            export.claim_links[0],
            replace(claim, text="Last reported location is ."),
            *export.claim_links[2:],
        ),
    )

    result = _grade(altered)

    assert result.step("claims").status is StepStatus.REVIEW
    assert result.step("claims").reason_codes == ("claim_semantics_unchecked",)


def test_unfamiliar_claim_wording_requires_semantic_review() -> None:
    export = _run().evidence_export
    altered = replace(
        export,
        claim_links=(
            replace(export.claim_links[0], text="Shipment is fully insured."),
            *export.claim_links[1:],
        ),
    )

    result = _grade(altered)

    assert result.status is StepStatus.REVIEW
    assert result.step("claims").reason_codes == ("claim_semantics_unchecked",)


@pytest.mark.parametrize(
    ("supported", "status", "reason_codes"),
    [
        (True, StepStatus.PASS, ()),
        (False, StepStatus.FAIL, ("claim_unsupported_nli",)),
        (None, StepStatus.REVIEW, ("claim_semantics_unchecked",)),
    ],
)
def test_nli_checks_only_disputed_claim_against_cited_evidence(
    supported: bool | None, status: StepStatus, reason_codes: tuple[str, ...]
) -> None:
    export = _run().evidence_export
    altered = replace(
        export,
        claim_links=(
            replace(export.claim_links[0], text="The shipment is fully insured."),
            *export.claim_links[1:],
        ),
    )
    scorer = _EvidenceNLIScorer(supported)

    result = grade_evidence_export(
        altered, contract=load_shipment_response_contract(), as_of=NOW, nli_scorer=scorer
    )

    assert result.step("claims").status is status
    assert result.step("claims").reason_codes == reason_codes
    assert len(scorer.calls) == 1
    claim, contexts = scorer.calls[0]
    assert claim == "The shipment is fully insured."
    source = export.source_observation
    assert f"Shipment {source.shipment_id} status is {source.status}." in contexts
    assert "Shipment status disclosure policy decision is allow." in contexts


def test_literal_claims_do_not_invoke_nli() -> None:
    scorer = _EvidenceNLIScorer(False)

    result = grade_evidence_export(
        _run().evidence_export,
        contract=load_shipment_response_contract(),
        as_of=NOW,
        nli_scorer=scorer,
    )

    assert result.step("claims").status is StepStatus.PASS
    assert scorer.calls == []


def test_verified_terminal_requires_declared_postconditions() -> None:
    export = _run().evidence_export

    result = _grade(replace(export, postcondition_versions=()))

    assert result.step("terminal").status is StepStatus.FAIL
    assert result.step("terminal").reason_codes == ("postcondition_missing_or_failed",)


def test_verified_terminal_rejects_undeclared_postconditions() -> None:
    export = _run().evidence_export
    extra = PostconditionVersion("unknown-check", "0.1.0", "f" * 64, "pass")

    result = _grade(replace(export, postcondition_versions=(*export.postcondition_versions, extra)))

    assert result.step("terminal").reason_codes == ("postcondition_missing_or_failed",)


def test_escalation_without_claims_can_be_structurally_valid() -> None:
    export = _run((ClaimCandidate("insurance", "Fully insured.", ()),)).evidence_export

    result = _grade(export)

    assert result.status is StepStatus.PASS
    assert result.step("claims").status is StepStatus.NOT_OBSERVED
    assert result.step("terminal").status is StepStatus.PASS


def test_escalation_requires_a_matching_handoff() -> None:
    export = _run((ClaimCandidate("insurance", "Fully insured.", ()),)).evidence_export

    result = _grade(replace(export, escalation_brief=None))

    assert result.step("terminal").status is StepStatus.FAIL
    assert result.step("terminal").reason_codes == ("handoff_missing_or_mismatched",)


def test_gr4_path_hits_a_labelled_target_section() -> None:
    trace = {
        "steps": [
            {
                "node": "retrieve",
                "state": {
                    "retrieval_strategy_effective": "graph",
                    "retrieval_path": {
                        "kind": "structural",
                        "sections": ["section:other", "section:target"],
                    },
                },
            }
        ]
    }
    path = evidence_view(trace)["retrieval_paths"][0]["path"]

    result = grade_retrieval_path(path, target_section_ids=("section:target",))

    assert result.status is StepStatus.PASS
    assert result.reason_codes == ()


def test_gr4_path_reports_a_missed_target_section() -> None:
    result = grade_retrieval_path(
        {"kind": "structural_entity", "sections": ["section:other"]},
        target_section_ids=("section:target",),
    )

    assert result.status is StepStatus.FAIL
    assert result.reason_codes == ("target_section_missing",)


def test_gr4_path_requires_every_labelled_section_for_multi_hop() -> None:
    path = {"kind": "structural_entity", "sections": ["section:first"]}

    result = grade_retrieval_path(
        path, target_section_ids=("section:first", "section:second")
    )

    assert result.status is StepStatus.FAIL
    assert result.reason_codes == ("target_section_missing",)


def test_gr4_path_without_observation_or_gold_needs_review() -> None:
    unavailable = grade_retrieval_path(None, target_section_ids=("section:target",))
    unlabelled = grade_retrieval_path(
        {"kind": "structural", "sections": ["section:target"]},
        target_section_ids=(),
    )

    assert unavailable.status is StepStatus.REVIEW
    assert unavailable.reason_codes == ("retrieval_path_unavailable",)
    assert unlabelled.status is StepStatus.REVIEW
    assert unlabelled.reason_codes == ("target_sections_unlabelled",)


def test_gr4_path_rejects_malformed_sections() -> None:
    result = grade_retrieval_path(
        {"kind": "structural", "sections": "section:target"},
        target_section_ids=("section:target",),
    )

    assert result.status is StepStatus.FAIL
    assert result.reason_codes == ("retrieval_path_invalid",)
