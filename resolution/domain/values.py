from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from resolution.domain.errors import InvalidDomainValue

_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SCOPE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[.:_-][a-z0-9]+)*$")


def require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidDomainValue(f"{label} must be timezone-aware")


def require_text(value: str, label: str, *, max_length: int = 256) -> None:
    if not value or value != value.strip():
        raise InvalidDomainValue(f"{label} must be non-empty without surrounding whitespace")
    if len(value) > max_length or any(ord(character) < 32 for character in value):
        raise InvalidDomainValue(f"{label} is not a bounded safe identifier")


def require_digest(value: str, label: str) -> None:
    if _DIGEST_PATTERN.fullmatch(value) is None:
        raise InvalidDomainValue(f"{label} must be a lowercase SHA-256 digest")


def require_uuid(value: UUID, label: str) -> None:
    if value.int == 0:
        raise InvalidDomainValue(f"{label} cannot be the nil UUID")


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: UUID
    actor_id: UUID
    scopes: frozenset[str]

    def __post_init__(self) -> None:
        require_uuid(self.tenant_id, "tenant_id")
        require_uuid(self.actor_id, "actor_id")
        if not isinstance(self.scopes, frozenset) or not self.scopes:
            raise InvalidDomainValue("scopes must be a non-empty frozenset")
        if any(_SCOPE_PATTERN.fullmatch(scope) is None for scope in self.scopes):
            raise InvalidDomainValue("scopes contain an invalid scope identifier")


@dataclass(frozen=True, slots=True)
class ContractVersionRef:
    contract_id: str
    version: str
    digest: str

    def __post_init__(self) -> None:
        require_text(self.contract_id, "contract_id", max_length=128)
        require_text(self.version, "contract_version", max_length=128)
        require_digest(self.digest, "contract_digest")


@dataclass(frozen=True, slots=True)
class TimeRange:
    start: datetime
    end: datetime | None

    def __post_init__(self) -> None:
        require_aware(self.start, "time_range.start")
        if self.end is not None:
            require_aware(self.end, "time_range.end")
            if self.end <= self.start:
                raise InvalidDomainValue("time_range.end must be later than start")

    def contains(self, instant: datetime) -> bool:
        require_aware(instant, "instant")
        return self.start <= instant and (self.end is None or instant < self.end)

    def overlaps(self, other: TimeRange) -> bool:
        left_ends_after_right_starts = self.end is None or other.start < self.end
        right_ends_after_left_starts = other.end is None or self.start < other.end
        return left_ends_after_right_starts and right_ends_after_left_starts


__all__ = ["ContractVersionRef", "TenantContext", "TimeRange"]
