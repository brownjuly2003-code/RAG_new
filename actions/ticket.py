from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import select

from actions.domain import (
    ActionConnectorRejected,
    ActionManifest,
    ActionManifestMismatch,
    ActionPostconditionResult,
    ActionRisk,
    ActionRun,
    ConnectorResult,
    PostconditionStatus,
    canonical_sha256,
)

LEGACY_CREATE_TICKET_MANIFEST_ID = "support.create-ticket"
LEGACY_CREATE_TICKET_MANIFEST_VERSION = "1.0.0"
LEGACY_ESCALATION_CONNECTOR_ID = "legacy-escalation-postgres"
LEGACY_ESCALATION_CONNECTOR_VERSION = "1.0.0"
LEGACY_CREATE_TICKET_ACTION_ID = "create_ticket"


class _EscalationOutcome(Protocol):
    ticket_id: str | None
    durable: bool
    already_existed: bool


CreateEscalation = Callable[..., Awaitable[_EscalationOutcome]]


@dataclass(frozen=True, slots=True)
class LegacyEscalationTicketSnapshot:
    id: str
    tenant_id: str
    session_id: str
    summary: str
    source: str
    status: str
    idempotency_key: str


TicketLookup = Callable[[str], Awaitable[LegacyEscalationTicketSnapshot | None]]


def legacy_create_ticket_manifest(
    tenant_id: UUID,
    recorded_at: datetime,
) -> ActionManifest:
    input_fields = ("session_id", "summary", "priority")
    schema_digest = canonical_sha256(
        {
            "action_id": LEGACY_CREATE_TICKET_ACTION_ID,
            "connector_id": LEGACY_ESCALATION_CONNECTOR_ID,
            "connector_version": LEGACY_ESCALATION_CONNECTOR_VERSION,
            "input": {
                "priority": ["low", "normal", "high", "critical"],
                "session_id": {"max_length": 128, "type": "string"},
                "summary": {"max_length": 2000, "type": "string"},
            },
            "output": {"source_ticket_id": "uuid"},
        }
    )
    return ActionManifest(
        tenant_id=tenant_id,
        id=LEGACY_CREATE_TICKET_MANIFEST_ID,
        version=LEGACY_CREATE_TICKET_MANIFEST_VERSION,
        connector_id=LEGACY_ESCALATION_CONNECTOR_ID,
        action_id=LEGACY_CREATE_TICKET_ACTION_ID,
        schema_digest=schema_digest,
        risk=ActionRisk.REVERSIBLE_WRITE,
        required_scopes=("ticket:create",),
        input_fields=input_fields,
        timeout_seconds=10,
        confirmation_ttl_seconds=300,
        postcondition_id="legacy-ticket-state",
        postcondition_version="1.0.0",
        compensation_manifest_id="support.cancel-ticket",
        max_reconciliation_attempts=2,
        recorded_at=recorded_at,
    )


async def _default_create_escalation(**kwargs: object) -> _EscalationOutcome:
    from services.escalation import create_escalation

    return cast(_EscalationOutcome, await create_escalation(**kwargs))


async def _default_ticket_lookup(
    idempotency_key: str,
) -> LegacyEscalationTicketSnapshot | None:
    from db.engine import async_session
    from db.models import EscalatedTicket

    async with async_session() as session:
        record = await session.scalar(
            select(EscalatedTicket).where(EscalatedTicket.idempotency_key == idempotency_key)
        )
        if record is None:
            return None
        return LegacyEscalationTicketSnapshot(
            id=str(record.id),
            tenant_id=record.tenant_id,
            session_id=record.session_id,
            summary=record.user_question,
            source=record.source or "",
            status=record.status,
            idempotency_key=record.idempotency_key or "",
        )


def _ticket_input(run: ActionRun) -> tuple[str, str, str]:
    session_id = run.safe_input.get("session_id")
    summary = run.safe_input.get("summary")
    priority = run.safe_input.get("priority")
    if (
        not isinstance(session_id, str)
        or not session_id
        or not isinstance(summary, str)
        or not summary
        or priority not in {"low", "normal", "high", "critical"}
    ):
        raise ActionManifestMismatch("ticket run input does not match the pinned schema")
    return session_id, summary, str(priority)


def _require_binding(manifest: ActionManifest, run: ActionRun) -> None:
    if (
        manifest.tenant_id != run.tenant_id
        or manifest.id != LEGACY_CREATE_TICKET_MANIFEST_ID
        or manifest.version != LEGACY_CREATE_TICKET_MANIFEST_VERSION
        or manifest.connector_id != LEGACY_ESCALATION_CONNECTOR_ID
        or manifest.action_id != LEGACY_CREATE_TICKET_ACTION_ID
        or run.manifest_id != manifest.id
        or run.manifest_version != manifest.version
        or run.manifest_schema_digest != manifest.schema_digest
        or run.connector_id != manifest.connector_id
        or run.action_id != manifest.action_id
    ):
        raise ActionManifestMismatch("legacy ticket connector binding is not exact")


class LegacyEscalationTicketConnector:
    """Pinned adapter over the existing durable escalation-ticket insert."""

    def __init__(
        self,
        *,
        create_escalation: CreateEscalation = _default_create_escalation,
        lookup: TicketLookup = _default_ticket_lookup,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._create_escalation = create_escalation
        self._lookup = lookup
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def service_idempotency_key(run: ActionRun) -> str:
        return canonical_sha256(
            {
                "connector_id": LEGACY_ESCALATION_CONNECTOR_ID,
                "connector_version": LEGACY_ESCALATION_CONNECTOR_VERSION,
                "downstream_idempotency_key": run.downstream_idempotency_key,
            }
        )

    @staticmethod
    def priority_source(priority: str) -> str:
        return f"governed_action_{priority}"

    @staticmethod
    def _response_digest(run: ActionRun, ticket_id: str) -> str:
        session_id, summary, priority = _ticket_input(run)
        return canonical_sha256(
            {
                "connector_id": LEGACY_ESCALATION_CONNECTOR_ID,
                "connector_version": LEGACY_ESCALATION_CONNECTOR_VERSION,
                "priority": priority,
                "remote_resource_id": ticket_id,
                "session_id": session_id,
                "source": LegacyEscalationTicketConnector.priority_source(priority),
                "summary": summary,
                "tenant_id": str(run.tenant_id),
            }
        )

    def result_from_snapshot(
        self,
        manifest: ActionManifest,
        run: ActionRun,
        snapshot: LegacyEscalationTicketSnapshot,
    ) -> ConnectorResult:
        _require_binding(manifest, run)
        return ConnectorResult(
            connector_id=manifest.connector_id,
            action_id=manifest.action_id,
            downstream_idempotency_key=run.downstream_idempotency_key,
            remote_operation_id=snapshot.id,
            remote_resource_id=snapshot.id,
            response_digest=self._response_digest(run, snapshot.id),
            observed_at=self._clock(),
        )

    async def execute(self, manifest: ActionManifest, run: ActionRun) -> ConnectorResult:
        _require_binding(manifest, run)
        session_id, summary, priority = _ticket_input(run)
        outcome = await self._create_escalation(
            tenant_id=str(run.tenant_id),
            session_id=session_id,
            question=summary,
            source=self.priority_source(priority),
            reason="governed_action_create_ticket",
            trace_id=str(run.id),
            deliver_inbox=False,
            idempotency_key=self.service_idempotency_key(run),
        )
        if not outcome.durable or outcome.ticket_id is None:
            raise ActionConnectorRejected("legacy escalation did not persist a durable ticket")
        try:
            UUID(outcome.ticket_id)
        except (TypeError, ValueError) as exc:
            raise ActionConnectorRejected(
                "legacy escalation returned an invalid ticket id"
            ) from exc
        snapshot = LegacyEscalationTicketSnapshot(
            id=outcome.ticket_id,
            tenant_id=str(run.tenant_id),
            session_id=session_id,
            summary=summary,
            source=self.priority_source(priority),
            status="open",
            idempotency_key=self.service_idempotency_key(run),
        )
        return self.result_from_snapshot(manifest, run, snapshot)

    async def reconcile(
        self,
        manifest: ActionManifest,
        run: ActionRun,
    ) -> ConnectorResult | None:
        _require_binding(manifest, run)
        snapshot = await self._lookup(self.service_idempotency_key(run))
        if snapshot is None:
            return None
        return self.result_from_snapshot(manifest, run, snapshot)


class LegacyTicketPostconditionChecker:
    def __init__(self, *, lookup: TicketLookup = _default_ticket_lookup) -> None:
        self._lookup = lookup

    async def check(
        self,
        manifest: ActionManifest,
        run: ActionRun,
        result: ConnectorResult,
        checked_at: datetime,
    ) -> ActionPostconditionResult:
        _require_binding(manifest, run)
        session_id, summary, priority = _ticket_input(run)
        snapshot = await self._lookup(LegacyEscalationTicketConnector.service_idempotency_key(run))
        expected_source = LegacyEscalationTicketConnector.priority_source(priority)
        if snapshot is None:
            status = PostconditionStatus.UNKNOWN
            reason_codes = ("TICKET_POSTCONDITION_UNAVAILABLE",)
        elif (
            snapshot.id != result.remote_resource_id
            or snapshot.tenant_id != str(run.tenant_id)
            or snapshot.session_id != session_id
            or snapshot.summary != summary
            or snapshot.source != expected_source
            or snapshot.status != "open"
            or snapshot.idempotency_key
            != LegacyEscalationTicketConnector.service_idempotency_key(run)
        ):
            status = PostconditionStatus.FAIL
            reason_codes = ("TICKET_POSTCONDITION_MISMATCH",)
        else:
            status = PostconditionStatus.PASS
            reason_codes = ("TICKET_POSTCONDITION_PASS",)
        return ActionPostconditionResult(
            id=uuid4(),
            tenant_id=run.tenant_id,
            run_id=run.id,
            checker_id=manifest.postcondition_id,
            checker_version=manifest.postcondition_version,
            observation_digest=result.response_digest,
            status=status,
            reason_codes=reason_codes,
            checked_at=checked_at,
        )


__all__ = [
    "LEGACY_CREATE_TICKET_MANIFEST_ID",
    "LEGACY_CREATE_TICKET_MANIFEST_VERSION",
    "LEGACY_ESCALATION_CONNECTOR_ID",
    "LEGACY_ESCALATION_CONNECTOR_VERSION",
    "LegacyEscalationTicketConnector",
    "LegacyEscalationTicketSnapshot",
    "LegacyTicketPostconditionChecker",
    "legacy_create_ticket_manifest",
]
