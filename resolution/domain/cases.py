from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from resolution.domain.errors import CaseVersionConflict, InvalidCaseTransition, InvalidDomainValue
from resolution.domain.values import (
    ContractVersionRef,
    require_aware,
    require_text,
    require_uuid,
)

_REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")


class CaseStatus(StrEnum):
    RECEIVED = "received"
    ROUTED = "routed"
    CLARIFICATION_REQUIRED = "clarification_required"
    EVIDENCE_GATHERING = "evidence_gathering"
    POLICY_PENDING = "policy_pending"
    RESPONSE_COMPILING = "response_compiling"
    CONFIRMATION_REQUIRED = "confirmation_required"
    ACTION_PENDING = "action_pending"
    ACTION_RUNNING = "action_running"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    POSTCONDITION_PENDING = "postcondition_pending"
    VERIFIED = "verified"
    PARTIAL = "partial"
    ESCALATED = "escalated"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CaseEventType(StrEnum):
    OPENED = "case_opened"
    STATUS_CHANGED = "case_status_changed"


TERMINAL_CASE_STATUSES = frozenset(
    {
        CaseStatus.VERIFIED,
        CaseStatus.PARTIAL,
        CaseStatus.ESCALATED,
        CaseStatus.FAILED,
        CaseStatus.CANCELLED,
    }
)


def _with_failure(*statuses: CaseStatus) -> frozenset[CaseStatus]:
    return frozenset((*statuses, CaseStatus.FAILED))


ALLOWED_CASE_TRANSITIONS: Mapping[CaseStatus, frozenset[CaseStatus]] = MappingProxyType(
    {
        CaseStatus.RECEIVED: _with_failure(CaseStatus.ROUTED),
        CaseStatus.ROUTED: _with_failure(
            CaseStatus.CLARIFICATION_REQUIRED,
            CaseStatus.EVIDENCE_GATHERING,
            CaseStatus.ESCALATED,
        ),
        CaseStatus.CLARIFICATION_REQUIRED: _with_failure(
            CaseStatus.ROUTED,
            CaseStatus.CANCELLED,
        ),
        CaseStatus.EVIDENCE_GATHERING: _with_failure(
            CaseStatus.POLICY_PENDING,
            CaseStatus.CLARIFICATION_REQUIRED,
            CaseStatus.ESCALATED,
        ),
        CaseStatus.POLICY_PENDING: _with_failure(
            CaseStatus.RESPONSE_COMPILING,
            CaseStatus.CONFIRMATION_REQUIRED,
            CaseStatus.ACTION_PENDING,
            CaseStatus.ESCALATED,
        ),
        CaseStatus.CONFIRMATION_REQUIRED: _with_failure(
            CaseStatus.ACTION_PENDING,
            CaseStatus.CANCELLED,
        ),
        CaseStatus.ACTION_PENDING: _with_failure(
            CaseStatus.ACTION_RUNNING,
            CaseStatus.CANCELLED,
        ),
        CaseStatus.ACTION_RUNNING: _with_failure(
            CaseStatus.POSTCONDITION_PENDING,
            CaseStatus.RECONCILIATION_REQUIRED,
        ),
        CaseStatus.RECONCILIATION_REQUIRED: _with_failure(
            CaseStatus.POSTCONDITION_PENDING,
            CaseStatus.ESCALATED,
        ),
        CaseStatus.POSTCONDITION_PENDING: _with_failure(
            CaseStatus.RESPONSE_COMPILING,
            CaseStatus.PARTIAL,
            CaseStatus.ESCALATED,
        ),
        CaseStatus.RESPONSE_COMPILING: _with_failure(
            CaseStatus.VERIFIED,
            CaseStatus.PARTIAL,
            CaseStatus.ESCALATED,
        ),
        **{status: frozenset() for status in TERMINAL_CASE_STATUSES},
    }
)


@dataclass(frozen=True, slots=True)
class CaseEvent:
    id: UUID
    tenant_id: UUID
    case_id: UUID
    sequence: int
    case_version: int
    event_type: CaseEventType
    command_id: UUID
    actor_id: UUID
    correlation_id: UUID
    from_status: CaseStatus | None
    to_status: CaseStatus
    reason_code: str
    occurred_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        for label, value in (
            ("event_id", self.id),
            ("tenant_id", self.tenant_id),
            ("case_id", self.case_id),
            ("command_id", self.command_id),
            ("actor_id", self.actor_id),
            ("correlation_id", self.correlation_id),
        ):
            require_uuid(value, label)
        if self.sequence < 1 or self.case_version < 1:
            raise InvalidDomainValue("event sequence and case version must be positive")
        if self.sequence != self.case_version:
            raise InvalidDomainValue("event sequence must equal the resulting case version")
        require_aware(self.occurred_at, "event.occurred_at")
        require_aware(self.recorded_at, "event.recorded_at")
        if self.recorded_at < self.occurred_at:
            raise InvalidDomainValue("event.recorded_at cannot precede occurred_at")
        if _REASON_CODE_PATTERN.fullmatch(self.reason_code) is None:
            raise InvalidDomainValue("event.reason_code must be a bounded stable code")


@dataclass(frozen=True, slots=True)
class SupportCase:
    id: UUID
    tenant_id: UUID
    contract: ContractVersionRef
    correlation_id: UUID
    status: CaseStatus
    version: int
    opened_at: datetime
    effective_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        require_uuid(self.id, "case_id")
        require_uuid(self.tenant_id, "tenant_id")
        require_uuid(self.correlation_id, "correlation_id")
        if self.version < 1:
            raise InvalidDomainValue("case version must be positive")
        require_aware(self.opened_at, "case.opened_at")
        require_aware(self.effective_at, "case.effective_at")
        require_aware(self.updated_at, "case.updated_at")
        if self.updated_at < self.opened_at:
            raise InvalidDomainValue("case.updated_at cannot precede opened_at")

    @classmethod
    def open(
        cls,
        *,
        case_id: UUID,
        tenant_id: UUID,
        contract: ContractVersionRef,
        correlation_id: UUID,
        event_id: UUID,
        command_id: UUID,
        actor_id: UUID,
        occurred_at: datetime,
        recorded_at: datetime,
        effective_at: datetime,
    ) -> CaseMutation:
        case = cls(
            id=case_id,
            tenant_id=tenant_id,
            contract=contract,
            correlation_id=correlation_id,
            status=CaseStatus.RECEIVED,
            version=1,
            opened_at=occurred_at,
            effective_at=effective_at,
            updated_at=recorded_at,
        )
        event = CaseEvent(
            id=event_id,
            tenant_id=tenant_id,
            case_id=case_id,
            sequence=1,
            case_version=1,
            event_type=CaseEventType.OPENED,
            command_id=command_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            from_status=None,
            to_status=CaseStatus.RECEIVED,
            reason_code="CASE_OPENED",
            occurred_at=occurred_at,
            recorded_at=recorded_at,
        )
        return CaseMutation(case=case, event=event, expected_version=None)

    def transition(
        self,
        *,
        to_status: CaseStatus,
        expected_version: int,
        event_id: UUID,
        command_id: UUID,
        actor_id: UUID,
        reason_code: str,
        occurred_at: datetime,
        recorded_at: datetime,
    ) -> CaseMutation:
        if expected_version != self.version:
            raise CaseVersionConflict(
                expected_version=expected_version,
                actual_version=self.version,
            )
        if self.status in TERMINAL_CASE_STATUSES:
            raise InvalidCaseTransition(f"terminal case '{self.status}' cannot transition")
        if to_status not in ALLOWED_CASE_TRANSITIONS[self.status]:
            raise InvalidCaseTransition(
                f"case transition '{self.status}' -> '{to_status}' is not allowed"
            )
        require_aware(occurred_at, "transition.occurred_at")
        require_aware(recorded_at, "transition.recorded_at")
        if recorded_at < occurred_at:
            raise InvalidDomainValue("transition.recorded_at cannot precede occurred_at")
        if recorded_at <= self.updated_at:
            raise InvalidDomainValue("transition.recorded_at must advance case time")
        require_text(reason_code, "transition.reason_code", max_length=64)

        next_version = self.version + 1
        event = CaseEvent(
            id=event_id,
            tenant_id=self.tenant_id,
            case_id=self.id,
            sequence=next_version,
            case_version=next_version,
            event_type=CaseEventType.STATUS_CHANGED,
            command_id=command_id,
            actor_id=actor_id,
            correlation_id=self.correlation_id,
            from_status=self.status,
            to_status=to_status,
            reason_code=reason_code,
            occurred_at=occurred_at,
            recorded_at=recorded_at,
        )
        next_case = replace(
            self,
            status=to_status,
            version=next_version,
            updated_at=recorded_at,
        )
        return CaseMutation(
            case=next_case,
            event=event,
            expected_version=self.version,
        )


@dataclass(frozen=True, slots=True)
class CaseMutation:
    case: SupportCase
    event: CaseEvent
    expected_version: int | None

    def __post_init__(self) -> None:
        if self.case.id != self.event.case_id or self.case.tenant_id != self.event.tenant_id:
            raise InvalidDomainValue("case mutation event ownership does not match the case")
        if self.case.version != self.event.case_version:
            raise InvalidDomainValue("case mutation event version does not match the case")
        if self.expected_version is None:
            if self.case.version != 1 or self.event.event_type is not CaseEventType.OPENED:
                raise InvalidDomainValue("only a version-one open mutation has no expected version")
        elif self.case.version != self.expected_version + 1:
            raise InvalidDomainValue("case mutation must advance expected version exactly once")


__all__ = [
    "ALLOWED_CASE_TRANSITIONS",
    "TERMINAL_CASE_STATUSES",
    "CaseEvent",
    "CaseEventType",
    "CaseMutation",
    "CaseStatus",
    "SupportCase",
]
