from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from itertools import combinations
from typing import TypeVar
from uuid import UUID

_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_KnowledgeEntity = TypeVar("_KnowledgeEntity", bound="KnowledgeObject | KnowledgeVersion")


class KnowledgeDomainError(ValueError):
    """A temporal-knowledge value or relationship violates the domain contract."""


class KnowledgeTemporalOverlap(KnowledgeDomainError):
    """Two versions overlap inside one authoritative source and applicability."""


class ApplicabilityDimension(StrEnum):
    PRODUCT = "product"
    REGION = "region"
    CUSTOMER_PLAN = "customer_plan"
    CARGO_TYPE = "cargo_type"
    CHANNEL = "channel"


class ConflictStatus(StrEnum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"


class KnowledgeSelectionStatus(StrEnum):
    ELIGIBLE = "eligible"
    MISSING = "missing"
    CONFLICT = "conflict"


def _require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise KnowledgeDomainError(f"{label} must be timezone-aware")


def _require_uuid(value: UUID, label: str) -> None:
    if not isinstance(value, UUID) or value.int == 0:
        raise KnowledgeDomainError(f"{label} must be a non-nil UUID")


def _require_text(value: str, label: str, *, max_length: int = 256) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise KnowledgeDomainError(f"{label} must be non-empty without surrounding whitespace")
    if len(value) > max_length or any(ord(character) < 32 for character in value):
        raise KnowledgeDomainError(f"{label} must be a bounded safe value")


def _require_digest(value: str, label: str) -> None:
    if _DIGEST_PATTERN.fullmatch(value) is None:
        raise KnowledgeDomainError(f"{label} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class TimeRange:
    start: datetime
    end: datetime | None

    def __post_init__(self) -> None:
        _require_aware(self.start, "time_range.start")
        if self.end is not None:
            _require_aware(self.end, "time_range.end")
            if self.end <= self.start:
                raise KnowledgeDomainError("time_range.end must be later than start")

    def contains(self, instant: datetime) -> bool:
        _require_aware(instant, "time_range instant")
        return self.start <= instant and (self.end is None or instant < self.end)

    def overlaps(self, other: TimeRange) -> bool:
        left_reaches_right = self.end is None or other.start < self.end
        right_reaches_left = other.end is None or self.start < other.end
        return left_reaches_right and right_reaches_left


@dataclass(frozen=True, slots=True)
class ApplicabilityTerm:
    dimension: ApplicabilityDimension
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, ApplicabilityDimension):
            raise KnowledgeDomainError("applicability dimension is unsupported")
        _require_text(self.value, "applicability value", max_length=128)
        if "*" in self.value:
            raise KnowledgeDomainError(
                "applicability wildcard is forbidden by exact-match semantics"
            )


@dataclass(frozen=True, slots=True)
class KnowledgeApplicability:
    terms: tuple[ApplicabilityTerm, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.terms, tuple):
            raise KnowledgeDomainError("applicability terms must be an immutable tuple")
        dimensions = tuple(term.dimension for term in self.terms)
        if len(set(dimensions)) != len(dimensions):
            raise KnowledgeDomainError("applicability dimensions must be unique")
        required = frozenset(ApplicabilityDimension)
        if frozenset(dimensions) != required:
            raise KnowledgeDomainError(
                "applicability must define every approved exact-match dimension"
            )

    @property
    def key(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((term.dimension.value, term.value) for term in self.terms))

    def matches(self, other: KnowledgeApplicability) -> bool:
        return self.key == other.key


@dataclass(frozen=True, slots=True)
class KnowledgeObject:
    id: UUID
    tenant_id: UUID
    logical_key: str
    source_id: str
    owner: str
    authority: str

    def __post_init__(self) -> None:
        _require_uuid(self.id, "knowledge_object.id")
        _require_uuid(self.tenant_id, "knowledge_object.tenant_id")
        _require_text(self.logical_key, "knowledge_object.logical_key")
        _require_text(self.source_id, "knowledge_object.source_id")
        _require_text(self.owner, "knowledge_object.owner", max_length=128)
        _require_text(self.authority, "knowledge_object.authority", max_length=128)


@dataclass(frozen=True, slots=True)
class KnowledgeVersion:
    id: UUID
    tenant_id: UUID
    object_id: UUID
    source_revision: str
    content_digest: str
    valid_range: TimeRange
    system_range: TimeRange
    applicability: KnowledgeApplicability
    locale: str

    def __post_init__(self) -> None:
        _require_uuid(self.id, "knowledge_version.id")
        _require_uuid(self.tenant_id, "knowledge_version.tenant_id")
        _require_uuid(self.object_id, "knowledge_version.object_id")
        _require_text(self.source_revision, "knowledge_version.source_revision")
        _require_digest(self.content_digest, "knowledge_version.content_digest")
        _require_text(self.locale, "knowledge_version.locale", max_length=32)


@dataclass(frozen=True, slots=True)
class KnowledgeSupersession:
    predecessor_version_id: UUID
    successor_version_id: UUID
    reason: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        _require_uuid(self.predecessor_version_id, "supersession.predecessor")
        _require_uuid(self.successor_version_id, "supersession.successor")
        if self.predecessor_version_id == self.successor_version_id:
            raise KnowledgeDomainError("a knowledge version cannot supersede itself")
        _require_text(self.reason, "supersession.reason", max_length=128)
        _require_aware(self.recorded_at, "supersession.recorded_at")


@dataclass(frozen=True, slots=True)
class KnowledgeConflict:
    id: UUID
    tenant_id: UUID
    fact_key: str
    left_version_id: UUID
    right_version_id: UUID
    status: ConflictStatus
    owner: str

    def __post_init__(self) -> None:
        _require_uuid(self.id, "knowledge_conflict.id")
        _require_uuid(self.tenant_id, "knowledge_conflict.tenant_id")
        _require_uuid(self.left_version_id, "knowledge_conflict.left_version_id")
        _require_uuid(self.right_version_id, "knowledge_conflict.right_version_id")
        if self.left_version_id == self.right_version_id:
            raise KnowledgeDomainError("a knowledge conflict requires two versions")
        _require_text(self.fact_key, "knowledge_conflict.fact_key")
        _require_text(self.owner, "knowledge_conflict.owner", max_length=128)
        if not isinstance(self.status, ConflictStatus):
            raise KnowledgeDomainError("knowledge conflict status is unsupported")


@dataclass(frozen=True, slots=True)
class KnowledgeQuery:
    tenant_id: UUID
    logical_key: str
    applicability: KnowledgeApplicability
    valid_at: datetime
    system_at: datetime

    def __post_init__(self) -> None:
        _require_uuid(self.tenant_id, "knowledge_query.tenant_id")
        _require_text(self.logical_key, "knowledge_query.logical_key")
        _require_aware(self.valid_at, "knowledge_query.valid_at")
        _require_aware(self.system_at, "knowledge_query.system_at")


@dataclass(frozen=True, slots=True)
class KnowledgeSelection:
    status: KnowledgeSelectionStatus
    versions: tuple[KnowledgeVersion, ...]
    conflicts: tuple[KnowledgeConflict, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status is KnowledgeSelectionStatus.ELIGIBLE:
            if not self.versions or self.conflicts or self.reason_codes:
                raise KnowledgeDomainError("eligible selection must contain only versions")
        elif self.status is KnowledgeSelectionStatus.MISSING:
            if self.versions or self.conflicts:
                raise KnowledgeDomainError("missing selection cannot contain evidence")
        elif self.versions:
            raise KnowledgeDomainError("conflicted selection cannot expose selected versions")


class KnowledgeCatalog:
    """Immutable, tenant-safe bitemporal selection boundary."""

    def __init__(
        self,
        *,
        objects: tuple[KnowledgeObject, ...],
        versions: tuple[KnowledgeVersion, ...],
        supersessions: tuple[KnowledgeSupersession, ...] = (),
        conflicts: tuple[KnowledgeConflict, ...] = (),
    ) -> None:
        self.objects = objects
        self.versions = versions
        self.supersessions = supersessions
        self.conflicts = conflicts
        self._objects_by_id = self._unique_by_id(objects, "knowledge object")
        self._versions_by_id = self._unique_by_id(versions, "knowledge version")
        self._validate_version_ownership()
        self._validate_temporal_ranges()
        self._validate_supersessions()
        self._validate_conflicts()

    @staticmethod
    def _unique_by_id(
        values: tuple[_KnowledgeEntity, ...],
        label: str,
    ) -> dict[UUID, _KnowledgeEntity]:
        result: dict[UUID, _KnowledgeEntity] = {}
        for value in values:
            if value.id in result:
                raise KnowledgeDomainError(f"duplicate {label} id")
            result[value.id] = value
        return result

    def _validate_version_ownership(self) -> None:
        for version in self.versions:
            knowledge_object = self._objects_by_id.get(version.object_id)
            if knowledge_object is None:
                raise KnowledgeDomainError("knowledge version references an unknown object")
            if knowledge_object.tenant_id != version.tenant_id:
                raise KnowledgeDomainError("knowledge version tenant ownership mismatch")

    def _validate_temporal_ranges(self) -> None:
        for left, right in combinations(self.versions, 2):
            left_object = self._objects_by_id[left.object_id]
            right_object = self._objects_by_id[right.object_id]
            same_identity = (
                left.tenant_id == right.tenant_id
                and left_object.source_id == right_object.source_id
                and left_object.logical_key == right_object.logical_key
                and left.applicability.key == right.applicability.key
                and left.locale == right.locale
            )
            if (
                same_identity
                and left.valid_range.overlaps(right.valid_range)
                and left.system_range.overlaps(right.system_range)
            ):
                raise KnowledgeTemporalOverlap(
                    "knowledge versions overlap within one authoritative source "
                    "and exact applicability"
                )

    def _validate_supersessions(self) -> None:
        seen: set[tuple[UUID, UUID]] = set()
        for relation in self.supersessions:
            identity = (relation.predecessor_version_id, relation.successor_version_id)
            if identity in seen:
                raise KnowledgeDomainError("duplicate knowledge supersession")
            seen.add(identity)
            predecessor = self._versions_by_id.get(relation.predecessor_version_id)
            successor = self._versions_by_id.get(relation.successor_version_id)
            if predecessor is None or successor is None:
                raise KnowledgeDomainError("supersession references an unknown version")
            if (
                predecessor.tenant_id != successor.tenant_id
                or predecessor.object_id != successor.object_id
            ):
                raise KnowledgeDomainError(
                    "supersession versions must share tenant and knowledge object"
                )

    def _validate_conflicts(self) -> None:
        seen_ids: set[UUID] = set()
        seen_pairs: set[tuple[UUID, UUID]] = set()
        for conflict in self.conflicts:
            if conflict.id in seen_ids:
                raise KnowledgeDomainError("duplicate knowledge conflict id")
            seen_ids.add(conflict.id)
            left_version_id, right_version_id = sorted(
                (conflict.left_version_id, conflict.right_version_id)
            )
            pair = (left_version_id, right_version_id)
            if pair in seen_pairs:
                raise KnowledgeDomainError("duplicate knowledge conflict pair")
            seen_pairs.add(pair)
            left = self._versions_by_id.get(conflict.left_version_id)
            right = self._versions_by_id.get(conflict.right_version_id)
            if left is None or right is None:
                raise KnowledgeDomainError("conflict references an unknown version")
            left_object = self._objects_by_id[left.object_id]
            right_object = self._objects_by_id[right.object_id]
            if conflict.tenant_id != left.tenant_id or left.tenant_id != right.tenant_id:
                raise KnowledgeDomainError("knowledge conflict tenant ownership mismatch")
            if left_object.logical_key != right_object.logical_key:
                raise KnowledgeDomainError("conflict versions must share a logical key")
            if left.applicability.key != right.applicability.key:
                raise KnowledgeDomainError("conflict versions must share applicability")
            if left_object.authority == right_object.authority:
                raise KnowledgeDomainError("cross-authority conflict requires distinct authorities")
            if left.content_digest == right.content_digest:
                raise KnowledgeDomainError("identical content is not a material conflict")

    def select(self, query: KnowledgeQuery) -> KnowledgeSelection:
        candidates: list[KnowledgeVersion] = []
        for version in self.versions:
            knowledge_object = self._objects_by_id[version.object_id]
            if (
                version.tenant_id == query.tenant_id
                and knowledge_object.logical_key == query.logical_key
                and version.applicability.matches(query.applicability)
                and version.valid_range.contains(query.valid_at)
                and version.system_range.contains(query.system_at)
            ):
                candidates.append(version)
        candidates.sort(key=lambda item: str(item.id))
        if not candidates:
            return KnowledgeSelection(
                status=KnowledgeSelectionStatus.MISSING,
                versions=(),
                conflicts=(),
                reason_codes=("KNOWLEDGE_MISSING",),
            )

        candidate_ids = {candidate.id for candidate in candidates}
        active_conflicts = tuple(
            conflict
            for conflict in self.conflicts
            if conflict.status is ConflictStatus.UNRESOLVED
            and conflict.left_version_id in candidate_ids
            and conflict.right_version_id in candidate_ids
        )
        if active_conflicts:
            return KnowledgeSelection(
                status=KnowledgeSelectionStatus.CONFLICT,
                versions=(),
                conflicts=active_conflicts,
                reason_codes=("KNOWLEDGE_CONFLICT",),
            )

        if len({candidate.content_digest for candidate in candidates}) > 1:
            return KnowledgeSelection(
                status=KnowledgeSelectionStatus.CONFLICT,
                versions=(),
                conflicts=(),
                reason_codes=("UNRECORDED_KNOWLEDGE_CONFLICT",),
            )
        return KnowledgeSelection(
            status=KnowledgeSelectionStatus.ELIGIBLE,
            versions=tuple(candidates),
            conflicts=(),
            reason_codes=(),
        )


__all__ = [
    "ApplicabilityDimension",
    "ApplicabilityTerm",
    "ConflictStatus",
    "KnowledgeApplicability",
    "KnowledgeCatalog",
    "KnowledgeConflict",
    "KnowledgeDomainError",
    "KnowledgeObject",
    "KnowledgeQuery",
    "KnowledgeSelection",
    "KnowledgeSelectionStatus",
    "KnowledgeSupersession",
    "KnowledgeTemporalOverlap",
    "KnowledgeVersion",
    "TimeRange",
]
