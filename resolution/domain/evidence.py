from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from itertools import combinations
from uuid import UUID

from resolution.domain.cases import SupportCase
from resolution.domain.errors import InvalidDomainValue, TenantBoundaryViolation
from resolution.domain.values import (
    TimeRange,
    require_aware,
    require_digest,
    require_text,
    require_uuid,
)

EVIDENCE_ENCRYPTION_PROFILE = "tenant-envelope-v1"


class EvidenceSourceType(StrEnum):
    SOURCE_SYSTEM = "source_system"
    KNOWLEDGE = "knowledge"
    USER_ASSERTION = "user_assertion"


class EvidenceVisibility(StrEnum):
    CUSTOMER_SAFE = "customer_safe"
    SUPPORT_ONLY = "support_only"
    RESTRICTED = "restricted"


class EvidenceStorage(StrEnum):
    POSTGRES_ENCRYPTED = "postgres_encrypted"
    OBJECT_STORE = "object_store"
    DEVELOPMENT_FILE = "development_file"


class EvidencePurpose(StrEnum):
    FACT = "fact"
    POLICY = "policy"
    POSTCONDITION = "postcondition"
    ESCALATION = "escalation"


class FreshnessStatus(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    UNKNOWN = "unknown"


class EvidenceConflictKind(StrEnum):
    AUTHORITY_OVERLAP = "authority_overlap"
    CONTENT_CONFLICT = "content_conflict"


@dataclass(frozen=True, slots=True)
class ProtectedEvidenceReference:
    storage: EvidenceStorage
    locator: str
    encryption_profile: str | None
    redaction_profile: str
    retention_class: str

    def __post_init__(self) -> None:
        require_text(self.locator, "evidence_reference.locator", max_length=512)
        require_text(
            self.redaction_profile,
            "evidence_reference.redaction_profile",
            max_length=128,
        )
        require_text(
            self.retention_class,
            "evidence_reference.retention_class",
            max_length=128,
        )
        if self.storage is not EvidenceStorage.DEVELOPMENT_FILE:
            if self.encryption_profile is None:
                raise InvalidDomainValue("durable evidence references require encryption_profile")
            require_text(
                self.encryption_profile,
                "evidence_reference.encryption_profile",
                max_length=128,
            )
            if self.encryption_profile != EVIDENCE_ENCRYPTION_PROFILE:
                raise InvalidDomainValue("unsupported evidence_reference.encryption_profile")
        elif self.encryption_profile is not None:
            require_text(
                self.encryption_profile,
                "evidence_reference.encryption_profile",
                max_length=128,
            )
            if self.encryption_profile != EVIDENCE_ENCRYPTION_PROFILE:
                raise InvalidDomainValue("unsupported evidence_reference.encryption_profile")


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    id: UUID
    tenant_id: UUID
    logical_key: str
    source_type: EvidenceSourceType
    source_id: str
    source_version: str
    content_digest: str
    valid_range: TimeRange
    recorded_at: datetime
    authority: str
    applicability_key: str
    visibility: EvidenceVisibility
    reference: ProtectedEvidenceReference

    def __post_init__(self) -> None:
        require_uuid(self.id, "evidence_id")
        require_uuid(self.tenant_id, "tenant_id")
        require_text(self.logical_key, "evidence.logical_key", max_length=256)
        require_text(self.source_id, "evidence.source_id", max_length=256)
        require_text(self.source_version, "evidence.source_version", max_length=256)
        require_digest(self.content_digest, "evidence.content_digest")
        require_aware(self.recorded_at, "evidence.recorded_at")
        require_text(self.authority, "evidence.authority", max_length=128)
        require_text(self.applicability_key, "evidence.applicability_key", max_length=256)

    def conflict_kind(self, other: EvidenceSnapshot) -> EvidenceConflictKind | None:
        if self.id == other.id:
            return None
        if (
            self.tenant_id != other.tenant_id
            or self.logical_key != other.logical_key
            or self.applicability_key != other.applicability_key
            or not self.valid_range.overlaps(other.valid_range)
        ):
            return None
        if self.authority == other.authority:
            return EvidenceConflictKind.AUTHORITY_OVERLAP
        if self.content_digest != other.content_digest:
            return EvidenceConflictKind.CONTENT_CONFLICT
        return None


@dataclass(frozen=True, slots=True)
class EvidenceConflict:
    tenant_id: UUID
    logical_key: str
    left_id: UUID
    right_id: UUID
    kind: EvidenceConflictKind


def detect_temporal_conflicts(
    snapshots: list[EvidenceSnapshot] | tuple[EvidenceSnapshot, ...],
) -> tuple[EvidenceConflict, ...]:
    conflicts: list[EvidenceConflict] = []
    for left, right in combinations(snapshots, 2):
        kind = left.conflict_kind(right)
        if kind is None:
            continue
        conflicts.append(
            EvidenceConflict(
                tenant_id=left.tenant_id,
                logical_key=left.logical_key,
                left_id=left.id,
                right_id=right.id,
                kind=kind,
            )
        )
    return tuple(conflicts)


@dataclass(frozen=True, slots=True)
class EvidenceLink:
    id: UUID
    tenant_id: UUID
    case_id: UUID
    case_version: int
    evidence_id: UUID
    requirement_id: str
    purpose: EvidencePurpose
    gathered_at: datetime
    freshness: FreshnessStatus

    def __post_init__(self) -> None:
        require_uuid(self.id, "evidence_link_id")
        require_uuid(self.tenant_id, "tenant_id")
        require_uuid(self.case_id, "case_id")
        require_uuid(self.evidence_id, "evidence_id")
        if self.case_version < 1:
            raise InvalidDomainValue("evidence link case_version must be positive")
        require_text(self.requirement_id, "evidence_link.requirement_id", max_length=128)
        require_aware(self.gathered_at, "evidence_link.gathered_at")

    @classmethod
    def create(
        cls,
        *,
        link_id: UUID,
        case: SupportCase,
        evidence: EvidenceSnapshot,
        requirement_id: str,
        purpose: EvidencePurpose,
        gathered_at: datetime,
        freshness: FreshnessStatus,
    ) -> EvidenceLink:
        if case.tenant_id != evidence.tenant_id:
            raise TenantBoundaryViolation("case and evidence belong to different tenants")
        return cls(
            id=link_id,
            tenant_id=case.tenant_id,
            case_id=case.id,
            case_version=case.version,
            evidence_id=evidence.id,
            requirement_id=requirement_id,
            purpose=purpose,
            gathered_at=gathered_at,
            freshness=freshness,
        )


__all__ = [
    "EVIDENCE_ENCRYPTION_PROFILE",
    "EvidenceConflict",
    "EvidenceConflictKind",
    "EvidenceLink",
    "EvidencePurpose",
    "EvidenceSnapshot",
    "EvidenceSourceType",
    "EvidenceStorage",
    "EvidenceVisibility",
    "FreshnessStatus",
    "ProtectedEvidenceReference",
    "detect_temporal_conflicts",
]
