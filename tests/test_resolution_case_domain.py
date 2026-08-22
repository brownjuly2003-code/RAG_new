from __future__ import annotations

import ast
import inspect
import sys
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from resolution.domain import (
    CaseStatus,
    CaseVersionConflict,
    ContractVersionRef,
    EvidenceConflictKind,
    EvidenceLink,
    EvidencePurpose,
    EvidenceSnapshot,
    EvidenceSourceType,
    EvidenceStorage,
    EvidenceVisibility,
    FreshnessStatus,
    InvalidCaseTransition,
    InvalidDomainValue,
    ProtectedEvidenceReference,
    SupportCase,
    TenantBoundaryViolation,
    TenantContext,
    TimeRange,
    detect_temporal_conflicts,
)
from resolution.ports import EvidenceRepository, ResolutionUnitOfWork, SupportCaseRepository

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
TENANT_ID = UUID("00000000-0000-0000-0000-000000000101")
OTHER_TENANT_ID = UUID("00000000-0000-0000-0000-000000000202")
CASE_ID = UUID("00000000-0000-0000-0000-000000000301")
ACTOR_ID = UUID("00000000-0000-0000-0000-000000000401")
CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000501")


def _open_case() -> tuple[SupportCase, object]:
    mutation = SupportCase.open(
        case_id=CASE_ID,
        tenant_id=TENANT_ID,
        contract=ContractVersionRef(
            contract_id="aircargo.shipment-status",
            version="0.1.0",
            digest="a" * 64,
        ),
        correlation_id=CORRELATION_ID,
        event_id=UUID("00000000-0000-0000-0000-000000000601"),
        command_id=UUID("00000000-0000-0000-0000-000000000701"),
        actor_id=ACTOR_ID,
        occurred_at=NOW,
        recorded_at=NOW + timedelta(milliseconds=10),
        effective_at=NOW - timedelta(hours=1),
    )
    return mutation.case, mutation


def _evidence_snapshot(
    *,
    evidence_id: UUID,
    tenant_id: UUID = TENANT_ID,
    authority: str = "shipment-source-primary",
    digest: str = "b" * 64,
    valid_from: datetime = NOW - timedelta(hours=1),
    valid_to: datetime | None = NOW + timedelta(hours=1),
) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        id=evidence_id,
        tenant_id=tenant_id,
        logical_key="shipment.status:020-12345675",
        source_type=EvidenceSourceType.SOURCE_SYSTEM,
        source_id="shipment-source-primary",
        source_version="shipment-revision-7",
        content_digest=digest,
        valid_range=TimeRange(start=valid_from, end=valid_to),
        recorded_at=NOW,
        authority=authority,
        applicability_key="global:aircargo",
        visibility=EvidenceVisibility.CUSTOMER_SAFE,
        reference=ProtectedEvidenceReference(
            storage=EvidenceStorage.POSTGRES_ENCRYPTED,
            locator=f"evidence/{evidence_id}",
            encryption_profile="tenant-envelope-v1",
            redaction_profile="customer-safe-v1",
            retention_class="case-evidence-90d",
        ),
    )


def test_open_case_emits_the_first_append_only_event() -> None:
    case, mutation = _open_case()

    assert case.status is CaseStatus.RECEIVED
    assert case.version == 1
    assert case.tenant_id == TENANT_ID
    assert mutation.expected_version is None
    assert mutation.event.sequence == 1
    assert mutation.event.case_version == 1
    assert mutation.event.from_status is None
    assert mutation.event.to_status is CaseStatus.RECEIVED
    assert mutation.event.command_id == UUID("00000000-0000-0000-0000-000000000701")


def test_case_transition_uses_compare_and_swap_without_mutating_prior_state() -> None:
    case, _ = _open_case()

    mutation = case.transition(
        to_status=CaseStatus.ROUTED,
        expected_version=1,
        event_id=UUID("00000000-0000-0000-0000-000000000602"),
        command_id=UUID("00000000-0000-0000-0000-000000000702"),
        actor_id=ACTOR_ID,
        reason_code="ACTOR_ACCEPTED",
        occurred_at=NOW + timedelta(seconds=1),
        recorded_at=NOW + timedelta(seconds=1, milliseconds=10),
    )

    assert case.status is CaseStatus.RECEIVED
    assert case.version == 1
    assert mutation.expected_version == 1
    assert mutation.case.status is CaseStatus.ROUTED
    assert mutation.case.version == 2
    assert mutation.event.sequence == 2
    assert mutation.event.from_status is CaseStatus.RECEIVED
    assert mutation.event.to_status is CaseStatus.ROUTED

    with pytest.raises(CaseVersionConflict) as exc_info:
        mutation.case.transition(
            to_status=CaseStatus.EVIDENCE_GATHERING,
            expected_version=1,
            event_id=UUID("00000000-0000-0000-0000-000000000603"),
            command_id=UUID("00000000-0000-0000-0000-000000000703"),
            actor_id=ACTOR_ID,
            reason_code="CONTRACT_SELECTED",
            occurred_at=NOW + timedelta(seconds=2),
            recorded_at=NOW + timedelta(seconds=2, milliseconds=10),
        )

    assert exc_info.value.expected_version == 1
    assert exc_info.value.actual_version == 2


def test_illegal_and_terminal_case_transitions_fail_closed() -> None:
    case, _ = _open_case()

    with pytest.raises(InvalidCaseTransition):
        case.transition(
            to_status=CaseStatus.VERIFIED,
            expected_version=1,
            event_id=UUID("00000000-0000-0000-0000-000000000604"),
            command_id=UUID("00000000-0000-0000-0000-000000000704"),
            actor_id=ACTOR_ID,
            reason_code="INVALID_SHORTCUT",
            occurred_at=NOW + timedelta(seconds=1),
            recorded_at=NOW + timedelta(seconds=1),
        )

    routed = case.transition(
        to_status=CaseStatus.ROUTED,
        expected_version=1,
        event_id=UUID("00000000-0000-0000-0000-000000000605"),
        command_id=UUID("00000000-0000-0000-0000-000000000705"),
        actor_id=ACTOR_ID,
        reason_code="ACTOR_ACCEPTED",
        occurred_at=NOW + timedelta(seconds=1),
        recorded_at=NOW + timedelta(seconds=1),
    ).case
    escalated = routed.transition(
        to_status=CaseStatus.ESCALATED,
        expected_version=2,
        event_id=UUID("00000000-0000-0000-0000-000000000606"),
        command_id=UUID("00000000-0000-0000-0000-000000000706"),
        actor_id=ACTOR_ID,
        reason_code="UNKNOWN_JOURNEY",
        occurred_at=NOW + timedelta(seconds=2),
        recorded_at=NOW + timedelta(seconds=2),
    ).case

    with pytest.raises(InvalidCaseTransition, match="terminal"):
        escalated.transition(
            to_status=CaseStatus.ROUTED,
            expected_version=3,
            event_id=UUID("00000000-0000-0000-0000-000000000607"),
            command_id=UUID("00000000-0000-0000-0000-000000000707"),
            actor_id=ACTOR_ID,
            reason_code="ILLEGAL_REOPEN",
            occurred_at=NOW + timedelta(seconds=3),
            recorded_at=NOW + timedelta(seconds=3),
        )


def test_case_and_evidence_records_are_frozen() -> None:
    case, mutation = _open_case()
    snapshot = _evidence_snapshot(evidence_id=UUID("00000000-0000-0000-0000-000000000801"))

    with pytest.raises(FrozenInstanceError):
        case.version = 99  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        mutation.event.reason_code = "REWRITTEN"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        snapshot.authority = "rewritten"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        snapshot.reference.locator = "rewritten"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("storage", "profile"),
    [
        (EvidenceStorage.POSTGRES_ENCRYPTED, None),
        (EvidenceStorage.POSTGRES_ENCRYPTED, "unknown-envelope-profile"),
        (EvidenceStorage.OBJECT_STORE, None),
        (EvidenceStorage.OBJECT_STORE, "unknown-envelope-profile"),
    ],
)
def test_durable_evidence_rejects_missing_or_unknown_encryption_profile_without_echoing_locator(
    storage: EvidenceStorage,
    profile: str | None,
) -> None:
    locator = "secret://customer-record-marker"

    with pytest.raises(InvalidDomainValue) as exc_info:
        ProtectedEvidenceReference(
            storage=storage,
            locator=locator,
            encryption_profile=profile,
            redaction_profile="customer-safe-v1",
            retention_class="case-evidence-90d",
        )

    assert "encryption_profile" in str(exc_info.value)
    assert locator not in str(exc_info.value)


def test_evidence_link_rejects_cross_tenant_snapshots() -> None:
    case, _ = _open_case()
    foreign_snapshot = _evidence_snapshot(
        evidence_id=UUID("00000000-0000-0000-0000-000000000802"),
        tenant_id=OTHER_TENANT_ID,
    )

    with pytest.raises(TenantBoundaryViolation):
        EvidenceLink.create(
            link_id=UUID("00000000-0000-0000-0000-000000000901"),
            case=case,
            evidence=foreign_snapshot,
            requirement_id="shipment-observation",
            purpose=EvidencePurpose.FACT,
            gathered_at=NOW,
            freshness=FreshnessStatus.CURRENT,
        )


def test_temporal_conflicts_are_explicit_and_tenant_scoped() -> None:
    first = _evidence_snapshot(
        evidence_id=UUID("00000000-0000-0000-0000-000000000811"),
        digest="1" * 64,
    )
    same_authority_overlap = _evidence_snapshot(
        evidence_id=UUID("00000000-0000-0000-0000-000000000812"),
        digest="2" * 64,
        valid_from=NOW,
        valid_to=NOW + timedelta(hours=2),
    )
    cross_authority_overlap = _evidence_snapshot(
        evidence_id=UUID("00000000-0000-0000-0000-000000000813"),
        authority="shipment-source-secondary",
        digest="3" * 64,
        valid_from=NOW,
        valid_to=NOW + timedelta(hours=2),
    )
    non_overlapping = _evidence_snapshot(
        evidence_id=UUID("00000000-0000-0000-0000-000000000814"),
        digest="4" * 64,
        valid_from=NOW + timedelta(hours=2),
        valid_to=NOW + timedelta(hours=3),
    )
    foreign_tenant = _evidence_snapshot(
        evidence_id=UUID("00000000-0000-0000-0000-000000000815"),
        tenant_id=OTHER_TENANT_ID,
        digest="5" * 64,
    )

    conflicts = detect_temporal_conflicts(
        [first, same_authority_overlap, cross_authority_overlap, non_overlapping, foreign_tenant]
    )

    by_pair = {(conflict.left_id, conflict.right_id): conflict.kind for conflict in conflicts}
    assert by_pair[(first.id, same_authority_overlap.id)] is EvidenceConflictKind.AUTHORITY_OVERLAP
    assert by_pair[(first.id, cross_authority_overlap.id)] is EvidenceConflictKind.CONTENT_CONFLICT
    assert all(non_overlapping.id not in pair for pair in by_pair)
    assert all(foreign_tenant.id not in pair for pair in by_pair)


def test_repository_ports_are_tenant_scoped_and_append_only() -> None:
    assert isinstance(
        TenantContext(tenant_id=TENANT_ID, actor_id=ACTOR_ID, scopes=frozenset({"case:agent"})),
        TenantContext,
    )

    expected_methods = {
        SupportCaseRepository: {"get", "append", "list_events"},
        EvidenceRepository: {"get_snapshot", "append_snapshot", "append_link", "list_for_case"},
        ResolutionUnitOfWork: {"commit", "rollback"},
    }
    for repository, methods in expected_methods.items():
        assert methods.issubset(repository.__dict__)
        assert "update" not in repository.__dict__
        assert "delete" not in repository.__dict__

    for repository, method_name in (
        (SupportCaseRepository, "get"),
        (SupportCaseRepository, "append"),
        (EvidenceRepository, "get_snapshot"),
        (EvidenceRepository, "append_snapshot"),
    ):
        parameters = list(inspect.signature(getattr(repository, method_name)).parameters)
        assert parameters[:2] == ["self", "context"]


def test_domain_package_imports_only_stdlib_and_its_own_domain_types() -> None:
    offenders: list[str] = []
    for path in (PROJECT_ROOT / "resolution" / "domain").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                root = module.split(".", maxsplit=1)[0]
                if root not in sys.stdlib_module_names and not module.startswith(
                    "resolution.domain"
                ):
                    offenders.append(f"{path.name}:{module}")

    assert offenders == []
