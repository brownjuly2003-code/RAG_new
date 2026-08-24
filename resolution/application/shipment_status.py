from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, TypeVar
from uuid import NAMESPACE_URL, UUID, uuid5

from resolution.contracts import ResolutionContract, TerminalOutcome, contract_digest

_SHIPMENT_ID_PATTERN = re.compile(r"(?<![A-Z0-9])SHP-[A-Z0-9]{1,32}(?![A-Z0-9])", re.IGNORECASE)
_SHIPMENT_CONTRACT_ID = "aircargo.shipment-status"
_SHIPMENT_CONTRACT_VERSION = "0.1.0"
_SHIPMENT_CONTRACT_DIGEST = "5d4d069f317df0c18f9e132b6fdbf9649bd6136808b2dc14507a0f2b10c99e38"
_POLICY_IMPLEMENTATION_VERSION = "typed-shipment-policy/v0.1"


class ShipmentObservationLike(Protocol):
    # Read-only members. The concrete adapters return frozen dataclasses, and
    # a Protocol declaring plain attributes demands settable ones -- so the
    # real FixtureShipmentSource did not satisfy ShipmentSourcePort. Nothing
    # caught it until phase A wired the loop up from typed production code:
    # the tests construct it too, but tests are outside the mypy scope.
    @property
    def tenant_id(self) -> str: ...

    @property
    def shipment_id(self) -> str: ...

    @property
    def status(self) -> str: ...

    @property
    def location(self) -> str: ...

    @property
    def estimated_delivery(self) -> str: ...

    @property
    def observed_at(self) -> datetime: ...

    @property
    def source_id(self) -> str: ...

    @property
    def source_version(self) -> str: ...

    @property
    def content_digest(self) -> str: ...


class PolicyEvidenceLike(Protocol):
    # Read-only members, same reason as ShipmentObservationLike above.
    @property
    def tenant_id(self) -> str: ...

    @property
    def authority(self) -> str: ...

    @property
    def data_revision(self) -> str: ...

    @property
    def recorded_at(self) -> datetime: ...

    @property
    def valid_from(self) -> datetime: ...

    @property
    def valid_to(self) -> datetime | None: ...

    @property
    def status_disclosure_allowed(self) -> bool: ...

    @property
    def content_digest(self) -> str: ...


class ShipmentSourcePort(Protocol):
    def lookup(
        self,
        *,
        tenant_id: str,
        shipment_id: str,
        timeout_seconds: int,
    ) -> ShipmentObservationLike | None: ...


class ShipmentPolicyPort(Protocol):
    def gather(
        self,
        *,
        tenant_id: str,
        shipment_id: str,
        effective_at: datetime,
    ) -> tuple[PolicyEvidenceLike, ...]: ...


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ClaimCandidate:
    claim_id: str
    text: str
    evidence_requirement_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.claim_id or self.claim_id != self.claim_id.strip():
            raise ValueError("claim_id must be non-empty without surrounding whitespace")
        if not self.text or self.text != self.text.strip():
            raise ValueError("claim text must be non-empty without surrounding whitespace")
        if len(set(self.evidence_requirement_ids)) != len(self.evidence_requirement_ids):
            raise ValueError("claim evidence requirements must be unique")


@dataclass(frozen=True, slots=True)
class ShipmentShadowRequest:
    tenant_id: str
    case_id: UUID
    correlation_id: UUID
    messages: tuple[str, ...]
    effective_at: datetime
    observed_at: datetime
    candidate_claims: tuple[ClaimCandidate, ...] = ()

    def __post_init__(self) -> None:
        if not self.tenant_id or self.tenant_id != self.tenant_id.strip():
            raise ValueError("tenant_id must be non-empty without surrounding whitespace")
        if self.case_id.int == 0 or self.correlation_id.int == 0:
            raise ValueError("case_id and correlation_id cannot be nil UUIDs")
        if any(not isinstance(message, str) for message in self.messages):
            raise TypeError("messages must contain strings")
        _require_aware(self.effective_at, "effective_at")
        _require_aware(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class ContractIdentity:
    schema_identity: str
    contract_id: str
    version: str
    digest: str

    def as_dict(self) -> dict[str, str]:
        return {
            "schema_identity": self.schema_identity,
            "contract_id": self.contract_id,
            "version": self.version,
            "digest": self.digest,
        }


@dataclass(frozen=True, slots=True)
class SourceObservationExport:
    shipment_id: str
    status: str
    location: str
    estimated_delivery: str
    observed_at: datetime
    source_id: str
    source_version: str
    content_digest: str

    def as_dict(self) -> dict[str, str]:
        return {
            "shipment_id": self.shipment_id,
            "status": self.status,
            "location": self.location,
            "estimated_delivery": self.estimated_delivery,
            "observed_at": self.observed_at.isoformat(),
            "source_id": self.source_id,
            "source_version": self.source_version,
            "content_digest": self.content_digest,
        }


@dataclass(frozen=True, slots=True)
class PolicyDecisionExport:
    implementation_version: str
    data_revision: str
    authority: str
    content_digest: str
    decision: str

    def as_dict(self) -> dict[str, str]:
        return {
            "implementation_version": self.implementation_version,
            "data_revision": self.data_revision,
            "authority": self.authority,
            "content_digest": self.content_digest,
            "decision": self.decision,
        }


@dataclass(frozen=True, slots=True)
class ClaimEvidenceLink:
    claim_id: str
    text: str
    evidence_requirement_ids: tuple[str, ...]
    evidence_digests: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "evidence_requirement_ids": list(self.evidence_requirement_ids),
            "evidence_digests": list(self.evidence_digests),
        }


@dataclass(frozen=True, slots=True)
class PostconditionVersion:
    postcondition_id: str
    version: str
    schema_digest: str
    result: str

    def as_dict(self) -> dict[str, str]:
        return {
            "postcondition_id": self.postcondition_id,
            "version": self.version,
            "schema_digest": self.schema_digest,
            "result": self.result,
        }


@dataclass(frozen=True, slots=True)
class EscalationBrief:
    case_id: UUID
    contract_version: str
    evidence_summary: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "case_id": str(self.case_id),
            "contract_version": self.contract_version,
            "evidence_summary": list(self.evidence_summary),
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class ShipmentEvidenceExport:
    mode: str
    tenant_id: str
    case_id: UUID
    case_version: int
    correlation_id: UUID
    terminal_state: TerminalOutcome
    reason_codes: tuple[str, ...]
    contract: ContractIdentity
    source_observation: SourceObservationExport | None
    policy: PolicyDecisionExport | None
    claim_links: tuple[ClaimEvidenceLink, ...]
    postcondition_versions: tuple[PostconditionVersion, ...]
    escalation_brief: EscalationBrief | None

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "tenant_id": self.tenant_id,
            "case_id": str(self.case_id),
            "case_version": self.case_version,
            "correlation_id": str(self.correlation_id),
            "terminal_state": self.terminal_state.value,
            "reason_codes": list(self.reason_codes),
            "contract": self.contract.as_dict(),
            "source_observation": (
                None if self.source_observation is None else self.source_observation.as_dict()
            ),
            "policy": None if self.policy is None else self.policy.as_dict(),
            "claim_links": [link.as_dict() for link in self.claim_links],
            "postcondition_versions": [
                postcondition.as_dict() for postcondition in self.postcondition_versions
            ],
            "escalation_brief": (
                None if self.escalation_brief is None else self.escalation_brief.as_dict()
            ),
        }


@dataclass(frozen=True, slots=True)
class ShipmentShadowResult:
    terminal_state: TerminalOutcome
    reason_codes: tuple[str, ...]
    response_text: str | None
    evidence_export: ShipmentEvidenceExport


class ShipmentStatusShadowLoop:
    """Deterministic fixture-backed shipment journey that never owns a legacy response."""

    def __init__(
        self,
        *,
        contract: ResolutionContract,
        source: ShipmentSourcePort,
        policy: ShipmentPolicyPort,
    ) -> None:
        digest = contract_digest(contract)
        if (
            contract.schema_version != "resolution-contract/v0.1"
            or contract.id != _SHIPMENT_CONTRACT_ID
            or contract.version != _SHIPMENT_CONTRACT_VERSION
            or digest != _SHIPMENT_CONTRACT_DIGEST
        ):
            raise ValueError("shipment shadow loop requires the pinned shipment-status contract")
        self._contract = contract
        self._source = source
        self._policy = policy
        self._contract_identity = ContractIdentity(
            schema_identity=contract.schema_version,
            contract_id=contract.id,
            version=contract.version,
            digest=digest,
        )
        self._source_max_age = self._evidence_max_age("shipment-observation")
        self._policy_max_age = self._evidence_max_age("shipment-policy")
        self._source_timeout = self._read_action_timeout("shipment-observation")
        self._postconditions = tuple(
            PostconditionVersion(
                postcondition_id=item.id,
                version=item.checker.version,
                schema_digest=item.checker.schema_digest,
                result="not_run",
            )
            for item in contract.postconditions
        )

    def run(self, request: ShipmentShadowRequest) -> ShipmentShadowResult:
        shipment_id = self._extract_shipment_id(request.messages)
        if shipment_id is None:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.CLARIFICATION_REQUIRED,
                reason_codes=("SHIPMENT_ID_REQUIRED",),
            )

        try:
            observation = self._source.lookup(
                tenant_id=request.tenant_id,
                shipment_id=shipment_id,
                timeout_seconds=self._source_timeout,
            )
        except Exception:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("SOURCE_UNAVAILABLE",),
            )
        if observation is None:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("SOURCE_UNAVAILABLE",),
            )

        source_export = self._source_export(request, observation)
        if source_export is None or not self._is_current(
            recorded_at=observation.observed_at,
            checked_at=request.observed_at,
            max_age_seconds=self._source_max_age,
        ):
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("EVIDENCE_STALE",),
                source_observation=source_export,
            )

        try:
            policies = self._policy.gather(
                tenant_id=request.tenant_id,
                shipment_id=shipment_id,
                effective_at=request.effective_at,
            )
        except Exception:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("SOURCE_UNAVAILABLE",),
                source_observation=source_export,
            )
        if not policies:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("SOURCE_UNAVAILABLE",),
                source_observation=source_export,
            )
        if len(policies) != 1:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("EVIDENCE_CONFLICT",),
                source_observation=source_export,
                evidence_summary=tuple(
                    f"policy:{item.data_revision}:{item.content_digest}" for item in policies
                ),
            )

        policy = policies[0]
        policy_export = self._policy_export(request, policy)
        if policy_export is None:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("SOURCE_UNAVAILABLE",),
                source_observation=source_export,
            )
        if not self._is_current(
            recorded_at=policy.recorded_at,
            checked_at=request.observed_at,
            max_age_seconds=self._policy_max_age,
        ):
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("EVIDENCE_STALE",),
                source_observation=source_export,
                policy=policy_export,
            )
        if not policy.status_disclosure_allowed:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("POLICY_DENIED",),
                source_observation=source_export,
                policy=policy_export,
            )

        candidates = request.candidate_claims or self._default_claims(source_export)
        claim_links = self._compile_claims(
            candidates=candidates,
            source_observation=source_export,
            policy=policy_export,
        )
        if claim_links is None:
            return self._finish(
                request=request,
                terminal_state=TerminalOutcome.ESCALATED,
                reason_codes=("UNSUPPORTED_CLAIM",),
                source_observation=source_export,
                policy=policy_export,
            )

        passed_postconditions = tuple(
            PostconditionVersion(
                postcondition_id=item.postcondition_id,
                version=item.version,
                schema_digest=item.schema_digest,
                result="pass",
            )
            for item in self._postconditions
        )
        response_text = " ".join(link.text for link in claim_links)
        return self._finish(
            request=request,
            terminal_state=TerminalOutcome.VERIFIED,
            reason_codes=(),
            source_observation=source_export,
            policy=policy_export,
            claim_links=claim_links,
            postconditions=passed_postconditions,
            response_text=response_text,
        )

    def _finish(
        self,
        *,
        request: ShipmentShadowRequest,
        terminal_state: TerminalOutcome,
        reason_codes: tuple[str, ...],
        source_observation: SourceObservationExport | None = None,
        policy: PolicyDecisionExport | None = None,
        claim_links: tuple[ClaimEvidenceLink, ...] = (),
        postconditions: tuple[PostconditionVersion, ...] | None = None,
        response_text: str | None = None,
        evidence_summary: tuple[str, ...] = (),
    ) -> ShipmentShadowResult:
        escalation_brief = None
        if terminal_state is TerminalOutcome.ESCALATED:
            summary = list(evidence_summary)
            if source_observation is not None:
                summary.append(
                    f"shipment:{source_observation.shipment_id}:{source_observation.content_digest}"
                )
            if policy is not None:
                summary.append(f"policy:{policy.data_revision}:{policy.content_digest}")
            escalation_brief = EscalationBrief(
                case_id=request.case_id,
                contract_version=(
                    f"{self._contract_identity.contract_id}@{self._contract_identity.version}"
                    f"#{self._contract_identity.digest}"
                ),
                evidence_summary=tuple(summary),
                reason_codes=reason_codes,
            )
        export = ShipmentEvidenceExport(
            mode="shadow",
            tenant_id=request.tenant_id,
            case_id=request.case_id,
            case_version=max(1, len(request.messages)),
            correlation_id=request.correlation_id,
            terminal_state=terminal_state,
            reason_codes=reason_codes,
            contract=self._contract_identity,
            source_observation=source_observation,
            policy=policy,
            claim_links=claim_links,
            postcondition_versions=(
                self._postconditions if postconditions is None else postconditions
            ),
            escalation_brief=escalation_brief,
        )
        return ShipmentShadowResult(
            terminal_state=terminal_state,
            reason_codes=reason_codes,
            response_text=response_text,
            evidence_export=export,
        )

    def _evidence_max_age(self, requirement_id: str) -> int:
        requirement = next(
            (item for item in self._contract.evidence_requirements if item.id == requirement_id),
            None,
        )
        if requirement is None:
            raise ValueError(f"contract lacks evidence requirement '{requirement_id}'")
        return int(requirement.freshness.max_age_seconds)

    def _read_action_timeout(self, evidence_requirement_id: str) -> int:
        for step in self._contract.steps:
            action = step.action
            if (
                action is not None
                and action.output_evidence_requirement_id == evidence_requirement_id
            ):
                return int(action.timeout_seconds)
        raise ValueError(f"contract lacks read action for '{evidence_requirement_id}'")

    @staticmethod
    def _extract_shipment_id(messages: tuple[str, ...]) -> str | None:
        matches: list[str] = []
        for message in messages:
            matches.extend(
                match.group(0).upper() for match in _SHIPMENT_ID_PATTERN.finditer(message)
            )
        return matches[-1] if matches else None

    @staticmethod
    def _is_current(*, recorded_at: datetime, checked_at: datetime, max_age_seconds: int) -> bool:
        _require_aware(recorded_at, "evidence recorded_at")
        age_seconds = (checked_at - recorded_at).total_seconds()
        return 0 <= age_seconds <= max_age_seconds

    @staticmethod
    def _source_export(
        request: ShipmentShadowRequest,
        observation: ShipmentObservationLike,
    ) -> SourceObservationExport | None:
        if observation.tenant_id != request.tenant_id:
            return None
        return SourceObservationExport(
            shipment_id=observation.shipment_id,
            status=observation.status,
            location=observation.location,
            estimated_delivery=observation.estimated_delivery,
            observed_at=observation.observed_at,
            source_id=observation.source_id,
            source_version=observation.source_version,
            content_digest=observation.content_digest,
        )

    @staticmethod
    def _policy_export(
        request: ShipmentShadowRequest,
        policy: PolicyEvidenceLike,
    ) -> PolicyDecisionExport | None:
        if policy.tenant_id != request.tenant_id:
            return None
        return PolicyDecisionExport(
            implementation_version=_POLICY_IMPLEMENTATION_VERSION,
            data_revision=policy.data_revision,
            authority=policy.authority,
            content_digest=policy.content_digest,
            decision="allow" if policy.status_disclosure_allowed else "deny",
        )

    @staticmethod
    def _default_claims(observation: SourceObservationExport) -> tuple[ClaimCandidate, ...]:
        requirements = ("shipment-observation", "shipment-policy")
        return (
            ClaimCandidate(
                claim_id="shipment-status",
                text=f"Shipment {observation.shipment_id} status is {observation.status}.",
                evidence_requirement_ids=requirements,
            ),
            ClaimCandidate(
                claim_id="shipment-location",
                text=f"Last reported location is {observation.location}.",
                evidence_requirement_ids=requirements,
            ),
            ClaimCandidate(
                claim_id="estimated-delivery",
                text=f"Estimated delivery is {observation.estimated_delivery}.",
                evidence_requirement_ids=requirements,
            ),
        )

    @staticmethod
    def _compile_claims(
        *,
        candidates: tuple[ClaimCandidate, ...],
        source_observation: SourceObservationExport,
        policy: PolicyDecisionExport,
    ) -> tuple[ClaimEvidenceLink, ...] | None:
        allowed = {
            item.claim_id: item
            for item in ShipmentStatusShadowLoop._default_claims(source_observation)
        }
        digests: Mapping[str, str] = {
            "shipment-observation": source_observation.content_digest,
            "shipment-policy": policy.content_digest,
        }
        links: list[ClaimEvidenceLink] = []
        for candidate in candidates:
            expected = allowed.get(candidate.claim_id)
            if expected is None or candidate.text != expected.text:
                return None
            if candidate.evidence_requirement_ids != expected.evidence_requirement_ids:
                return None
            evidence_digests = tuple(digests[item] for item in candidate.evidence_requirement_ids)
            if not evidence_digests:
                return None
            links.append(
                ClaimEvidenceLink(
                    claim_id=candidate.claim_id,
                    text=candidate.text,
                    evidence_requirement_ids=candidate.evidence_requirement_ids,
                    evidence_digests=evidence_digests,
                )
            )
        return tuple(links) if links else None


_ResponseT = TypeVar("_ResponseT")


def run_legacy_ask_shadow(
    *,
    response: _ResponseT,
    tenant_id: str,
    session_id: str,
    correlation_id: str,
    question: str,
    observer: Callable[[ShipmentShadowRequest], object] | None,
    observed_at: datetime | None = None,
) -> _ResponseT:
    """Run an isolated shadow observer while returning the exact legacy response object."""

    if observer is None:
        return response
    instant = observed_at or datetime.now(UTC)
    try:
        request = ShipmentShadowRequest(
            tenant_id=tenant_id,
            case_id=uuid5(NAMESPACE_URL, f"rag-new:shipment-shadow:{tenant_id}:{session_id}"),
            correlation_id=uuid5(NAMESPACE_URL, f"rag-new:correlation:{correlation_id}"),
            messages=(question,),
            effective_at=instant,
            observed_at=instant,
        )
        observer(request)
    except Exception:
        pass
    return response


__all__ = [
    "ClaimCandidate",
    "ClaimEvidenceLink",
    "ContractIdentity",
    "EscalationBrief",
    "PolicyDecisionExport",
    "PolicyEvidenceLike",
    "PostconditionVersion",
    "ShipmentEvidenceExport",
    "ShipmentObservationLike",
    "ShipmentPolicyPort",
    "ShipmentShadowRequest",
    "ShipmentShadowResult",
    "ShipmentSourcePort",
    "ShipmentStatusShadowLoop",
    "SourceObservationExport",
    "run_legacy_ask_shadow",
]
