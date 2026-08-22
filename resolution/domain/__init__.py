"""Pure deterministic domain types for support-case resolution."""

from resolution.domain.cases import (
    ALLOWED_CASE_TRANSITIONS,
    TERMINAL_CASE_STATUSES,
    CaseEvent,
    CaseEventType,
    CaseMutation,
    CaseStatus,
    SupportCase,
)
from resolution.domain.errors import (
    CaseVersionConflict,
    InvalidCaseTransition,
    InvalidDomainValue,
    ResolutionDomainError,
    TenantBoundaryViolation,
)
from resolution.domain.evidence import (
    EVIDENCE_ENCRYPTION_PROFILE,
    EvidenceConflict,
    EvidenceConflictKind,
    EvidenceLink,
    EvidencePurpose,
    EvidenceSnapshot,
    EvidenceSourceType,
    EvidenceStorage,
    EvidenceVisibility,
    FreshnessStatus,
    ProtectedEvidenceReference,
    detect_temporal_conflicts,
)
from resolution.domain.values import ContractVersionRef, TenantContext, TimeRange

__all__ = [
    "ALLOWED_CASE_TRANSITIONS",
    "TERMINAL_CASE_STATUSES",
    "CaseEvent",
    "CaseEventType",
    "CaseMutation",
    "CaseStatus",
    "CaseVersionConflict",
    "ContractVersionRef",
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
    "InvalidCaseTransition",
    "InvalidDomainValue",
    "ProtectedEvidenceReference",
    "ResolutionDomainError",
    "SupportCase",
    "TenantBoundaryViolation",
    "TenantContext",
    "TimeRange",
    "detect_temporal_conflicts",
]
