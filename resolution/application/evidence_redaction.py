from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from resolution.domain import EvidenceSnapshot, EvidenceVisibility

CUSTOMER_SAFE_REDACTION_PROFILE = "customer-safe-v1"


class EvidenceRedactionDenialReason(StrEnum):
    RESTRICTED_EVIDENCE = "restricted_evidence"
    VISIBILITY_NOT_CUSTOMER_SAFE = "visibility_not_customer_safe"
    UNKNOWN_REDACTION_PROFILE = "unknown_redaction_profile"


class EvidenceRedactionDenied(ValueError):
    def __init__(self, reason: EvidenceRedactionDenialReason) -> None:
        self.reason = reason
        super().__init__(f"evidence redaction denied: {reason.value}")


@dataclass(frozen=True, slots=True)
class RedactedEvidenceReference:
    evidence_id: UUID
    content_digest: str
    visibility: EvidenceVisibility
    redaction_profile: str


def redact_evidence_reference(snapshot: EvidenceSnapshot) -> RedactedEvidenceReference:
    """Project a customer-safe evidence identity without exposing its locator."""
    if snapshot.visibility is EvidenceVisibility.RESTRICTED:
        raise EvidenceRedactionDenied(EvidenceRedactionDenialReason.RESTRICTED_EVIDENCE)
    if snapshot.visibility is not EvidenceVisibility.CUSTOMER_SAFE:
        raise EvidenceRedactionDenied(EvidenceRedactionDenialReason.VISIBILITY_NOT_CUSTOMER_SAFE)
    if snapshot.reference.redaction_profile != CUSTOMER_SAFE_REDACTION_PROFILE:
        raise EvidenceRedactionDenied(EvidenceRedactionDenialReason.UNKNOWN_REDACTION_PROFILE)
    return RedactedEvidenceReference(
        evidence_id=snapshot.id,
        content_digest=snapshot.content_digest,
        visibility=snapshot.visibility,
        redaction_profile=snapshot.reference.redaction_profile,
    )


__all__ = [
    "CUSTOMER_SAFE_REDACTION_PROFILE",
    "EvidenceRedactionDenied",
    "EvidenceRedactionDenialReason",
    "RedactedEvidenceReference",
    "redact_evidence_reference",
]
