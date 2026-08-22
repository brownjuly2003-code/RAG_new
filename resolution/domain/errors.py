from __future__ import annotations


class ResolutionDomainError(ValueError):
    """Base class for deterministic resolution-domain rejections."""


class InvalidDomainValue(ResolutionDomainError):
    """A value violates a domain invariant."""


class CaseVersionConflict(ResolutionDomainError):
    def __init__(self, *, expected_version: int, actual_version: int) -> None:
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"case version conflict: expected {expected_version}, actual {actual_version}"
        )


class InvalidCaseTransition(ResolutionDomainError):
    """A requested case state transition is not legal."""


class TenantBoundaryViolation(ResolutionDomainError):
    """Two tenant-owned domain values cannot be related."""


__all__ = [
    "CaseVersionConflict",
    "InvalidCaseTransition",
    "InvalidDomainValue",
    "ResolutionDomainError",
    "TenantBoundaryViolation",
]
