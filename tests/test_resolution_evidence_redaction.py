from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from resolution.application.evidence_redaction import (
    CUSTOMER_SAFE_REDACTION_PROFILE,
    EvidenceRedactionDenialReason,
    EvidenceRedactionDenied,
    RedactedEvidenceReference,
    redact_evidence_reference,
)
from resolution.domain import (
    EvidenceSnapshot,
    EvidenceSourceType,
    EvidenceStorage,
    EvidenceVisibility,
    ProtectedEvidenceReference,
    TimeRange,
)

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
EVIDENCE_ID = UUID("00000000-0000-0000-0000-000000000811")
TENANT_ID = UUID("00000000-0000-0000-0000-000000000101")
LOCATOR = "secret://customer-locator-marker"


def _snapshot(
    *,
    visibility: EvidenceVisibility = EvidenceVisibility.CUSTOMER_SAFE,
    redaction_profile: str = CUSTOMER_SAFE_REDACTION_PROFILE,
    locator: str = LOCATOR,
) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        id=EVIDENCE_ID,
        tenant_id=TENANT_ID,
        logical_key="secret-logical-key-marker",
        source_type=EvidenceSourceType.SOURCE_SYSTEM,
        source_id="secret-source-id-marker",
        source_version="secret-source-version-marker",
        content_digest="b" * 64,
        valid_range=TimeRange(start=NOW, end=NOW + timedelta(hours=1)),
        recorded_at=NOW,
        authority="secret-authority-marker",
        applicability_key="secret-applicability-marker",
        visibility=visibility,
        reference=ProtectedEvidenceReference(
            storage=EvidenceStorage.POSTGRES_ENCRYPTED,
            locator=locator,
            encryption_profile="tenant-envelope-v1",
            redaction_profile=redaction_profile,
            retention_class="secret-retention-marker",
        ),
    )


def test_customer_safe_profile_projects_exact_safe_allowlist() -> None:
    snapshot = _snapshot()

    redacted = redact_evidence_reference(snapshot)

    assert redacted == RedactedEvidenceReference(
        evidence_id=EVIDENCE_ID,
        content_digest="b" * 64,
        visibility=EvidenceVisibility.CUSTOMER_SAFE,
        redaction_profile=CUSTOMER_SAFE_REDACTION_PROFILE,
    )
    representation = repr(redacted)
    for secret_marker in (
        LOCATOR,
        str(TENANT_ID),
        "secret-logical-key-marker",
        "secret-source-id-marker",
        "secret-source-version-marker",
        "secret-authority-marker",
        "secret-applicability-marker",
        "secret-retention-marker",
        "tenant-envelope-v1",
    ):
        assert secret_marker not in representation


def test_customer_safe_projection_is_deterministic_and_locator_independent() -> None:
    first = _snapshot(locator="secret://first-locator-marker")
    second = replace(
        first,
        reference=replace(first.reference, locator="secret://second-locator-marker"),
    )

    assert redact_evidence_reference(first) == redact_evidence_reference(second)


def test_unknown_profile_fails_closed_without_echoing_values() -> None:
    profile_marker = "secret-unknown-profile-marker"
    snapshot = _snapshot(redaction_profile=profile_marker)

    with pytest.raises(EvidenceRedactionDenied) as exc_info:
        redact_evidence_reference(snapshot)

    assert exc_info.value.reason is EvidenceRedactionDenialReason.UNKNOWN_REDACTION_PROFILE
    assert LOCATOR not in str(exc_info.value)
    assert profile_marker not in str(exc_info.value)


def test_restricted_evidence_fails_closed_even_with_known_profile() -> None:
    snapshot = _snapshot(visibility=EvidenceVisibility.RESTRICTED)

    with pytest.raises(EvidenceRedactionDenied) as exc_info:
        redact_evidence_reference(snapshot)

    assert exc_info.value.reason is EvidenceRedactionDenialReason.RESTRICTED_EVIDENCE
    assert LOCATOR not in str(exc_info.value)


def test_support_only_evidence_requires_a_future_authorized_boundary() -> None:
    snapshot = _snapshot(visibility=EvidenceVisibility.SUPPORT_ONLY)

    with pytest.raises(EvidenceRedactionDenied) as exc_info:
        redact_evidence_reference(snapshot)

    assert exc_info.value.reason is EvidenceRedactionDenialReason.VISIBILITY_NOT_CUSTOMER_SAFE
    assert LOCATOR not in str(exc_info.value)
