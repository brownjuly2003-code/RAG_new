from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from actions.domain import ActionRun, ActionRunState, PostconditionStatus
from actions.ticket import (
    LegacyEscalationTicketConnector,
    LegacyEscalationTicketSnapshot,
    LegacyTicketPostconditionChecker,
    legacy_create_ticket_manifest,
)

_NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
_TENANT_ID = UUID("84000000-0000-0000-0000-000000000001")


@dataclass(frozen=True)
class _Outcome:
    ticket_id: str | None
    durable: bool
    already_existed: bool


def _run() -> ActionRun:
    manifest = legacy_create_ticket_manifest(_TENANT_ID, _NOW)
    return ActionRun(
        id=uuid4(),
        tenant_id=_TENANT_ID,
        case_id=uuid4(),
        manifest_id=manifest.id,
        manifest_version=manifest.version,
        manifest_schema_digest=manifest.schema_digest,
        connector_id=manifest.connector_id,
        action_id=manifest.action_id,
        operation_key_digest="1" * 64,
        input_digest="2" * 64,
        action_digest="3" * 64,
        evidence_digest="4" * 64,
        policy_decision_id=uuid4(),
        downstream_idempotency_key=f"action:{'5' * 64}",
        state=ActionRunState.DISPATCHED,
        safe_input={
            "session_id": "session-SHP-100",
            "summary": "Shipment status requires an operator",
            "priority": "high",
        },
        created_at=_NOW,
        updated_at=_NOW,
    )


@pytest.mark.asyncio
async def test_legacy_connector_persists_exact_ticket_input_without_inbox_delivery() -> None:
    captured: dict[str, object] = {}
    ticket_id = str(uuid4())

    async def create_escalation(**kwargs: object) -> _Outcome:
        captured.update(kwargs)
        return _Outcome(ticket_id=ticket_id, durable=True, already_existed=False)

    async def unused_lookup(_idempotency_key: str) -> LegacyEscalationTicketSnapshot | None:
        raise AssertionError("execute must not perform reconciliation lookup")

    manifest = legacy_create_ticket_manifest(_TENANT_ID, _NOW)
    run = _run()
    connector = LegacyEscalationTicketConnector(
        create_escalation=create_escalation,
        lookup=unused_lookup,
        clock=lambda: _NOW,
    )

    result = await connector.execute(manifest, run)

    assert captured == {
        "tenant_id": str(_TENANT_ID),
        "session_id": "session-SHP-100",
        "question": "Shipment status requires an operator",
        "source": "governed_action_high",
        "reason": "governed_action_create_ticket",
        "trace_id": str(run.id),
        "deliver_inbox": False,
        "idempotency_key": connector.service_idempotency_key(run),
    }
    assert len(str(captured["idempotency_key"])) == 64
    assert result.connector_id == manifest.connector_id
    assert result.action_id == manifest.action_id
    assert result.downstream_idempotency_key == run.downstream_idempotency_key
    assert result.remote_operation_id == ticket_id
    assert result.remote_resource_id == ticket_id


@pytest.mark.asyncio
async def test_reconciliation_queries_durable_identity_without_second_create() -> None:
    run = _run()
    manifest = legacy_create_ticket_manifest(_TENANT_ID, _NOW)
    calls: list[str] = []

    async def create_escalation(**_kwargs: object) -> _Outcome:
        raise AssertionError("reconciliation must never create a second ticket")

    async def lookup(idempotency_key: str) -> LegacyEscalationTicketSnapshot | None:
        calls.append(idempotency_key)
        return LegacyEscalationTicketSnapshot(
            id=str(uuid4()),
            tenant_id=str(_TENANT_ID),
            session_id=str(run.safe_input["session_id"]),
            summary=str(run.safe_input["summary"]),
            source="governed_action_high",
            status="open",
            idempotency_key=idempotency_key,
        )

    connector = LegacyEscalationTicketConnector(
        create_escalation=create_escalation,
        lookup=lookup,
        clock=lambda: _NOW,
    )

    result = await connector.reconcile(manifest, run)

    assert result is not None
    assert calls == [connector.service_idempotency_key(run)]
    result.require_identity(manifest, run)


@pytest.mark.asyncio
async def test_postcondition_checks_exact_legacy_ticket_identity_and_priority_source() -> None:
    run = replace(_run(), state=ActionRunState.SUCCEEDED)
    manifest = legacy_create_ticket_manifest(_TENANT_ID, _NOW)
    snapshot = LegacyEscalationTicketSnapshot(
        id=str(uuid4()),
        tenant_id=str(_TENANT_ID),
        session_id=str(run.safe_input["session_id"]),
        summary=str(run.safe_input["summary"]),
        source="governed_action_high",
        status="open",
        idempotency_key=LegacyEscalationTicketConnector.service_idempotency_key(run),
    )

    async def lookup(_idempotency_key: str) -> LegacyEscalationTicketSnapshot | None:
        return snapshot

    connector = LegacyEscalationTicketConnector(lookup=lookup, clock=lambda: _NOW)
    connector_result = connector.result_from_snapshot(manifest, run, snapshot)
    checker = LegacyTicketPostconditionChecker(lookup=lookup)

    passed = await checker.check(manifest, run, connector_result, _NOW)
    assert passed.status is PostconditionStatus.PASS
    assert passed.observation_digest == connector_result.response_digest

    async def tampered_lookup(_idempotency_key: str) -> LegacyEscalationTicketSnapshot | None:
        return replace(snapshot, source="governed_action_low")

    failed = await LegacyTicketPostconditionChecker(lookup=tampered_lookup).check(
        manifest,
        run,
        connector_result,
        _NOW,
    )
    assert failed.status is PostconditionStatus.FAIL
    assert failed.reason_codes == ("TICKET_POSTCONDITION_MISMATCH",)
