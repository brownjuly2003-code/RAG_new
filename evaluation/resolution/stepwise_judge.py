"""Contract-based checks for a shipment shadow evidence export.

Rules check structure and known literal claims. An unfamiliar claim needs an
independent NLI scorer; without one, its status remains review.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from resolution.application.shipment_status import ShipmentEvidenceExport
from resolution.contracts import ClaimPolicy, ResolutionContract, TerminalOutcome, contract_digest


class StepStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    REVIEW = "review"
    NOT_OBSERVED = "not_observed"


@dataclass(frozen=True, slots=True)
class StepGrade:
    name: str
    status: StepStatus
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvidenceGrade:
    steps: tuple[StepGrade, ...]

    @property
    def status(self) -> StepStatus:
        if any(step.status is StepStatus.FAIL for step in self.steps):
            return StepStatus.FAIL
        if any(step.status is StepStatus.REVIEW for step in self.steps):
            return StepStatus.REVIEW
        return StepStatus.PASS

    def step(self, name: str) -> StepGrade:
        return next(step for step in self.steps if step.name == name)


class ClaimNLIScorer(Protocol):
    def score(self, answer: str, contexts: Sequence[str]) -> Mapping[str, object]: ...


def _is_digest(value: str) -> bool:
    return re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _is_current(recorded_at: datetime, as_of: datetime, max_age_seconds: int) -> bool:
    if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
        return False
    age = (as_of - recorded_at).total_seconds()
    return 0 <= age <= max_age_seconds


def _literal_claims(export: ShipmentEvidenceExport) -> dict[str, str]:
    source = export.source_observation
    if source is None:
        return {}
    claims = {}
    if source.shipment_id and source.status:
        claims["shipment-status"] = f"Shipment {source.shipment_id} status is {source.status}."
    if source.location:
        claims["shipment-location"] = f"Last reported location is {source.location}."
    if source.estimated_delivery:
        claims["estimated-delivery"] = f"Estimated delivery is {source.estimated_delivery}."
    return claims


def grade_evidence_export(
    export: ShipmentEvidenceExport,
    *,
    contract: ResolutionContract,
    as_of: datetime,
    nli_scorer: ClaimNLIScorer | None = None,
) -> EvidenceGrade:
    """Grade each evidence stage against the pinned contract at the run time."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")

    identity = export.contract
    expected_identity = (
        contract.schema_version,
        contract.id,
        contract.version,
        contract_digest(contract),
    )
    actual_identity = (
        identity.schema_identity,
        identity.contract_id,
        identity.version,
        identity.digest,
    )
    contract_step = StepGrade(
        "contract",
        StepStatus.PASS if actual_identity == expected_identity else StepStatus.FAIL,
        () if actual_identity == expected_identity else ("contract_identity_mismatch",),
    )

    requirements = {item.id: item for item in contract.evidence_requirements}
    verified = export.terminal_state is TerminalOutcome.VERIFIED

    source = export.source_observation
    source_issues: list[str] = []
    if source is None:
        source_step = StepGrade(
            "source",
            StepStatus.FAIL if verified else StepStatus.NOT_OBSERVED,
            ("verified_source_missing",) if verified else (),
        )
    else:
        requirement = requirements.get("shipment-observation")
        if (
            requirement is None
            or not source.shipment_id
            or not source.status
            or not source.source_id
            or not source.source_version
            or not _is_digest(source.content_digest)
        ):
            source_issues.append("source_identity_invalid")
        if requirement is not None and not _is_current(
            source.observed_at, as_of, requirement.freshness.max_age_seconds
        ):
            source_issues.append("source_stale")
        source_step = StepGrade(
            "source", StepStatus.FAIL if source_issues else StepStatus.PASS, tuple(source_issues)
        )

    policy = export.policy
    policy_issues: list[str] = []
    if policy is None:
        policy_step = StepGrade(
            "policy",
            StepStatus.FAIL if verified else StepStatus.NOT_OBSERVED,
            ("verified_policy_missing",) if verified else (),
        )
    else:
        requirement = requirements.get("shipment-policy")
        if (
            requirement is None
            or policy.authority != requirement.authority
            or not policy.data_revision
            or not _is_digest(policy.content_digest)
        ):
            policy_issues.append("policy_identity_invalid")
        if requirement is not None and not _is_current(
            policy.recorded_at, as_of, requirement.freshness.max_age_seconds
        ):
            policy_issues.append("policy_stale")
        if (
            policy.valid_from.tzinfo is None
            or policy.valid_from.utcoffset() is None
            or policy.valid_from > as_of
            or (
                policy.valid_to is not None
                and (
                    policy.valid_to.tzinfo is None
                    or policy.valid_to.utcoffset() is None
                    or policy.valid_to <= as_of
                    or policy.valid_to <= policy.valid_from
                )
            )
        ):
            policy_issues.append("policy_not_effective")
        if verified and policy.decision != "allow":
            policy_issues.append("policy_disallows_verified")
        policy_step = StepGrade(
            "policy", StepStatus.FAIL if policy_issues else StepStatus.PASS, tuple(policy_issues)
        )

    claims = export.claim_links
    claim_issues: list[str] = []
    if not claims:
        claims_step = StepGrade(
            "claims",
            StepStatus.FAIL if verified else StepStatus.NOT_OBSERVED,
            ("verified_claims_missing",) if verified else (),
        )
    else:
        actual_digests = {
            "shipment-observation": source.content_digest if source else None,
            "shipment-policy": policy.content_digest if policy else None,
        }
        required_bindings = (
            {
                field.claim_id: field.evidence_requirement_ids
                for field in contract.response_shape.fields
            }
            if contract.response_shape is not None
            else None
        )
        if len({claim.claim_id for claim in claims}) != len(claims):
            claim_issues.append("claim_id_duplicate")
        literal_claims = _literal_claims(export)
        disputed_claims = []
        for claim in claims:
            if required_bindings is not None and claim.claim_id not in required_bindings:
                claim_issues.append("claim_not_in_response_shape")
            expected_requirements = (
                required_bindings.get(claim.claim_id)
                if required_bindings is not None
                else (
                    ("shipment-observation", "shipment-policy")
                    if claim.claim_id in literal_claims
                    else None
                )
            )
            if (
                not claim.evidence_requirement_ids
                or (
                    expected_requirements is not None
                    and claim.evidence_requirement_ids != expected_requirements
                )
                or len(claim.evidence_requirement_ids) != len(claim.evidence_digests)
                or any(
                    requirement_id not in requirements
                    or not isinstance(digest, str)
                    or not _is_digest(digest)
                    or actual_digests.get(requirement_id) != digest
                    for requirement_id, digest in zip(
                        claim.evidence_requirement_ids, claim.evidence_digests, strict=True
                    )
                )
            ):
                claim_issues.append("claim_evidence_mismatch")
            if not claim.text or literal_claims.get(claim.claim_id) != claim.text:
                disputed_claims.append(claim)
        claim_issues = list(dict.fromkeys(claim_issues))
        if claim_issues:
            claims_step = StepGrade("claims", StepStatus.FAIL, tuple(claim_issues))
        elif disputed_claims and nli_scorer is None:
            claims_step = StepGrade(
                "claims", StepStatus.REVIEW, ("claim_semantics_unchecked",)
            )
        elif disputed_claims:
            assert nli_scorer is not None
            contexts_by_requirement = {
                "shipment-observation": tuple(literal_claims.values()),
                "shipment-policy": (
                    f"Shipment status disclosure policy decision is {policy.decision}.",
                ) if policy is not None else (),
            }
            unsupported = False
            unchecked = False
            for claim in disputed_claims:
                contexts = tuple(
                    context
                    for requirement_id in claim.evidence_requirement_ids
                    for context in contexts_by_requirement.get(requirement_id, ())
                )
                if not claim.text or not contexts:
                    unchecked = True
                    continue
                try:
                    summary = nli_scorer.score(claim.text, contexts)
                    count = summary.get("n_claims")
                    supported = summary.get("n_supported_claims")
                except Exception:
                    unchecked = True
                    continue
                if (
                    type(count) is not int
                    or type(supported) is not int
                    or count < 1
                    or supported < 0
                    or supported > count
                ):
                    unchecked = True
                elif supported < count:
                    unsupported = True
            if unsupported:
                claims_step = StepGrade("claims", StepStatus.FAIL, ("claim_unsupported_nli",))
            elif unchecked:
                claims_step = StepGrade(
                    "claims", StepStatus.REVIEW, ("claim_semantics_unchecked",)
                )
            else:
                claims_step = StepGrade("claims", StepStatus.PASS)
        else:
            claims_step = StepGrade("claims", StepStatus.PASS)

    terminal_issues: list[str] = []
    definition = contract.terminal_outcomes.get(export.terminal_state)
    if definition is None:
        terminal_issues.append("terminal_undefined")
    else:
        if definition.claim_policy is ClaimPolicy.NO_MATERIAL_CLAIMS and claims:
            terminal_issues.append("terminal_forbids_claims")
        if definition.requires_all_postconditions:
            expected_postconditions = {
                item.id: item
                for item in contract.postconditions
                if export.terminal_state in item.required_for
            }
            actual_postconditions = {item.postcondition_id: item for item in export.postcondition_versions}
            if (
                len(actual_postconditions) != len(export.postcondition_versions)
                or actual_postconditions.keys() != expected_postconditions.keys()
                or any(
                    (actual := actual_postconditions.get(postcondition_id)) is None
                    or actual.result != "pass"
                    or actual.version != expected.checker.version
                    or actual.schema_digest != expected.checker.schema_digest
                    for postcondition_id, expected in expected_postconditions.items()
                )
            ):
                terminal_issues.append("postcondition_missing_or_failed")
        if verified and export.reason_codes:
            terminal_issues.append("verified_has_reasons")
        if definition.handoff_required:
            handoff = export.escalation_brief
            contract_version = (
                f"{identity.contract_id}@{identity.version}#{identity.digest}"
            )
            if (
                handoff is None
                or not export.reason_codes
                or handoff.case_id != export.case_id
                or handoff.reason_codes != export.reason_codes
                or handoff.contract_version != contract_version
            ):
                terminal_issues.append("handoff_missing_or_mismatched")
        elif export.escalation_brief is not None:
            terminal_issues.append("unexpected_handoff")
    terminal_step = StepGrade(
        "terminal", StepStatus.FAIL if terminal_issues else StepStatus.PASS, tuple(terminal_issues)
    )
    return EvidenceGrade((contract_step, source_step, policy_step, claims_step, terminal_step))


def grade_retrieval_path(
    path: Mapping[str, object] | None,
    *,
    target_section_ids: Collection[str],
) -> StepGrade:
    """Check whether a GR-4 path reached an independently labelled section."""
    targets = set(target_section_ids)
    if not targets or "" in targets:
        return StepGrade("retrieval", StepStatus.REVIEW, ("target_sections_unlabelled",))
    if path is None:
        return StepGrade("retrieval", StepStatus.REVIEW, ("retrieval_path_unavailable",))
    sections = path.get("sections")
    if (
        path.get("kind") not in {"structural", "structural_entity"}
        or not isinstance(sections, (list, tuple))
        or any(not isinstance(section, str) or not section for section in sections)
    ):
        return StepGrade("retrieval", StepStatus.FAIL, ("retrieval_path_invalid",))
    if targets.issubset(sections):
        return StepGrade("retrieval", StepStatus.PASS)
    return StepGrade("retrieval", StepStatus.FAIL, ("target_section_missing",))
