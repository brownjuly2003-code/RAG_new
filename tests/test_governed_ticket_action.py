from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from actions.application import ActionGateway, ActionRegistry
from actions.domain import (
    ActionCommand,
    ActionCompensationRejected,
    ActionConfirmation,
    ActionConfirmationRejected,
    ActionIdempotencyConflict,
    ActionManifest,
    ActionOutboxEvent,
    ActionOutboxKind,
    ActionOutboxState,
    ActionPolicyDecision,
    ActionPolicyRequest,
    ActionPolicyResult,
    ActionPostconditionResult,
    ActionReceiptState,
    ActionRisk,
    ActionRun,
    ActionRunState,
    ActionWorkItem,
    ActionWorkUnavailable,
    ConfirmationDecision,
    ConnectorResult,
    PostconditionStatus,
    TransportOutcome,
)

TENANT_ID = UUID("80000000-0000-0000-0000-000000000001")
CASE_ID = UUID("81000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


class _Clock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self) -> datetime:
        return self.value


class _Policy:
    def __init__(self, *results: ActionPolicyResult) -> None:
        self._results = list(results) or [ActionPolicyResult.ALLOW]
        self.calls: list[ActionPolicyRequest] = []

    async def decide(self, request: ActionPolicyRequest) -> ActionPolicyDecision:
        self.calls.append(request)
        result = self._results.pop(0) if len(self._results) > 1 else self._results[0]
        return ActionPolicyDecision(
            id=uuid4(),
            tenant_id=request.tenant_id,
            case_id=request.case_id,
            action_digest=request.action_digest,
            input_digest=request.input_digest,
            evidence_digest=request.evidence_digest,
            result=result,
            reason_codes=("POLICY_ALLOW",)
            if result is ActionPolicyResult.ALLOW
            else ("POLICY_DENY",),
            policy_adapter="typed-local",
            policy_revision="ticket-policy/1.0.0",
            decided_at=NOW,
            expires_at=NOW + timedelta(minutes=10),
        )


class _Connector:
    def __init__(self) -> None:
        self.execute_calls = 0
        self.reconcile_calls = 0
        self.timeout = False
        self.result_factory: Callable[[ActionRun], ConnectorResult] = self._result
        self.reconcile_result: ConnectorResult | None = None

    @staticmethod
    def _result(run: ActionRun) -> ConnectorResult:
        return ConnectorResult(
            connector_id=run.connector_id,
            action_id=run.action_id,
            downstream_idempotency_key=run.downstream_idempotency_key,
            remote_operation_id=f"operation:{run.id}",
            remote_resource_id=f"ticket:{run.id}",
            response_digest="d" * 64,
            observed_at=NOW,
        )

    async def execute(self, manifest: ActionManifest, run: ActionRun) -> ConnectorResult:
        del manifest
        self.execute_calls += 1
        if self.timeout:
            raise TimeoutError("connector timed out after dispatch")
        return self.result_factory(run)

    async def reconcile(
        self,
        manifest: ActionManifest,
        run: ActionRun,
    ) -> ConnectorResult | None:
        del manifest
        self.reconcile_calls += 1
        return self.reconcile_result


class _Checker:
    def __init__(self, status: PostconditionStatus = PostconditionStatus.PASS) -> None:
        self.status = status
        self.calls = 0

    async def check(
        self,
        manifest: ActionManifest,
        run: ActionRun,
        result: ConnectorResult,
        checked_at: datetime,
    ) -> ActionPostconditionResult:
        self.calls += 1
        return ActionPostconditionResult(
            id=uuid4(),
            tenant_id=run.tenant_id,
            run_id=run.id,
            checker_id=manifest.postcondition_id,
            checker_version=manifest.postcondition_version,
            observation_digest=result.response_digest,
            status=self.status,
            reason_codes=(f"POSTCONDITION_{self.status.value.upper()}",),
            checked_at=checked_at,
        )


class _MemoryStore:
    def __init__(self, *manifests: ActionManifest) -> None:
        self.manifests = {(item.tenant_id, item.id, item.version): item for item in manifests}
        self.killed = False
        self.decisions: list[ActionPolicyDecision] = []
        self.runs: dict[UUID, ActionRun] = {}
        self.runs_by_operation: dict[tuple[UUID, str], UUID] = {}
        self.confirmations: dict[UUID, ActionConfirmation] = {}
        self.outbox: dict[UUID, ActionOutboxEvent] = {}
        self.attempts = []
        self.postconditions: list[ActionPostconditionResult] = []

    async def get_manifest(
        self,
        tenant_id: UUID,
        manifest_id: str,
        version: str,
    ) -> ActionManifest | None:
        return self.manifests.get((tenant_id, manifest_id, version))

    async def is_killed(
        self,
        tenant_id: UUID,
        environment: str,
        connector_id: str,
        action_id: str,
        at: datetime,
    ) -> bool:
        del tenant_id, environment, connector_id, action_id, at
        return self.killed

    async def save_denial(self, decision: ActionPolicyDecision) -> None:
        self.decisions.append(decision)

    async def create_or_replay(
        self,
        decision: ActionPolicyDecision,
        run: ActionRun,
        confirmation: ActionConfirmation | None,
        outbox: ActionOutboxEvent | None,
    ) -> tuple[ActionRun, bool]:
        identity = (run.tenant_id, run.operation_key_digest)
        existing_id = self.runs_by_operation.get(identity)
        if existing_id is not None:
            existing = self.runs[existing_id]
            if (
                existing.input_digest != run.input_digest
                or existing.action_digest != run.action_digest
            ):
                raise ActionIdempotencyConflict("logical operation key already owns another input")
            return existing, True
        self.decisions.append(decision)
        self.runs[run.id] = run
        self.runs_by_operation[identity] = run.id
        if confirmation is not None:
            self.confirmations[confirmation.id] = confirmation
        if outbox is not None:
            self.outbox[outbox.id] = outbox
        return run, False

    async def get_run(self, tenant_id: UUID, run_id: UUID) -> ActionRun | None:
        run = self.runs.get(run_id)
        return run if run is not None and run.tenant_id == tenant_id else None

    async def find_run_by_operation_key(
        self,
        tenant_id: UUID,
        operation_key_digest: str,
    ) -> ActionRun | None:
        run_id = self.runs_by_operation.get((tenant_id, operation_key_digest))
        return None if run_id is None else self.runs[run_id]

    async def get_confirmation(
        self,
        tenant_id: UUID,
        confirmation_id: UUID,
    ) -> ActionConfirmation | None:
        confirmation = self.confirmations.get(confirmation_id)
        return (
            confirmation
            if confirmation is not None and confirmation.tenant_id == tenant_id
            else None
        )

    async def decide_confirmation(
        self,
        tenant_id: UUID,
        confirmation_id: UUID,
        actor_id: str,
        action_digest: str,
        decision: ConfirmationDecision,
        decided_at: datetime,
        outbox: ActionOutboxEvent | None,
    ) -> ActionRun:
        confirmation = self.confirmations[confirmation_id]
        run = self.runs[confirmation.run_id]
        if confirmation.tenant_id != tenant_id or confirmation.action_digest != action_digest:
            raise ActionConfirmationRejected("confirmation is not bound to this action")
        if confirmation.decision is not ConfirmationDecision.PENDING:
            raise ActionConfirmationRejected("confirmation was already decided")
        if decided_at >= confirmation.expires_at:
            raise ActionConfirmationRejected("confirmation expired")
        self.confirmations[confirmation_id] = replace(
            confirmation,
            actor_id=actor_id,
            decision=decision,
            decided_at=decided_at,
        )
        state = (
            ActionRunState.READY
            if decision is ConfirmationDecision.APPROVED
            else ActionRunState.CANCELLED
        )
        run = replace(
            run,
            state=state,
            outbox_event_id=None if outbox is None else outbox.id,
            updated_at=decided_at,
        )
        self.runs[run.id] = run
        if outbox is not None:
            self.outbox[outbox.id] = outbox
        return run

    async def lease_event(
        self,
        tenant_id: UUID,
        event_id: UUID,
        lease_token: str,
        lease_expires_at: datetime,
        leased_at: datetime,
    ) -> ActionWorkItem:
        event = self.outbox[event_id]
        run = self.runs[event.run_id]
        if event.tenant_id != tenant_id or event.state is not ActionOutboxState.PENDING:
            raise ActionWorkUnavailable("outbox event is not claimable")
        expected = {
            ActionOutboxKind.DISPATCH: ActionRunState.READY,
            ActionOutboxKind.RECONCILE: ActionRunState.OUTCOME_UNKNOWN,
        }[event.kind]
        if run.state is not expected:
            raise ActionWorkUnavailable("action run is not claimable")
        next_state = {
            ActionOutboxKind.DISPATCH: ActionRunState.DISPATCHED,
            ActionOutboxKind.RECONCILE: ActionRunState.RECONCILING,
        }[event.kind]
        event = replace(
            event,
            state=ActionOutboxState.LEASED,
            lease_token=lease_token,
            lease_expires_at=lease_expires_at,
            attempts=event.attempts + 1,
        )
        run = replace(
            run,
            state=next_state,
            attempt_count=run.attempt_count + 1,
            lease_token=lease_token,
            lease_expires_at=lease_expires_at,
            updated_at=leased_at,
        )
        self.outbox[event.id] = event
        self.runs[run.id] = run
        return ActionWorkItem(
            run=run,
            manifest=self.manifests[(tenant_id, run.manifest_id, run.manifest_version)],
            event=event,
            attempt_number=run.attempt_count,
            lease_token=lease_token,
            started_at=leased_at,
        )

    async def complete_event(
        self,
        work: ActionWorkItem,
        *,
        transport_outcome: TransportOutcome,
        resulting_state: ActionRunState,
        finished_at: datetime,
        connector_result: ConnectorResult | None,
        next_event: ActionOutboxEvent | None,
    ) -> ActionRun:
        event = self.outbox[work.event.id]
        if event.lease_token != work.lease_token:
            raise ActionWorkUnavailable("outbox lease was lost")
        self.outbox[event.id] = replace(
            event,
            state=ActionOutboxState.DELIVERED,
            delivered_at=finished_at,
            lease_token=None,
            lease_expires_at=None,
        )
        run = self.runs[work.run.id]
        run = replace(
            run,
            state=resulting_state,
            lease_token=None,
            lease_expires_at=None,
            remote_operation_id=(
                run.remote_operation_id
                if connector_result is None
                else connector_result.remote_operation_id
            ),
            remote_resource_id=(
                run.remote_resource_id
                if connector_result is None
                else connector_result.remote_resource_id
            ),
            result_digest=(
                run.result_digest if connector_result is None else connector_result.response_digest
            ),
            outbox_event_id=None if next_event is None else next_event.id,
            updated_at=finished_at,
        )
        self.runs[run.id] = run
        self.attempts.append((work, transport_outcome, connector_result))
        if next_event is not None:
            self.outbox[next_event.id] = next_event
        return run

    async def record_postcondition(
        self,
        run: ActionRun,
        result: ActionPostconditionResult,
        resulting_state: ActionRunState,
    ) -> ActionRun:
        self.postconditions.append(result)
        run = replace(run, state=resulting_state, updated_at=result.checked_at)
        self.runs[run.id] = run
        return run


def _manifest(
    *,
    manifest_id: str = "support.create-ticket",
    action_id: str = "create_ticket",
    compensation_manifest_id: str | None = "support.cancel-ticket",
) -> ActionManifest:
    input_fields = (
        ("original_run_id", "source_ticket_id", "reason_code")
        if action_id == "cancel_ticket"
        else ("session_id", "summary", "priority")
    )
    return ActionManifest(
        tenant_id=TENANT_ID,
        id=manifest_id,
        version="1.0.0",
        connector_id="legacy-escalation",
        action_id=action_id,
        schema_digest="a" * 64,
        risk=ActionRisk.REVERSIBLE_WRITE,
        required_scopes=(f"ticket:{'cancel' if action_id == 'cancel_ticket' else 'create'}",),
        timeout_seconds=10,
        confirmation_ttl_seconds=300,
        postcondition_id="ticket-state",
        postcondition_version="1.0.0",
        compensation_manifest_id=compensation_manifest_id,
        max_reconciliation_attempts=2,
        recorded_at=NOW,
        input_fields=input_fields,
    )


def _command(
    manifest: ActionManifest,
    *,
    summary: str = "Shipment status requires an operator",
    logical_operation_key: str = "shipment:SHP-100:ticket",
    compensation_of_run_id: UUID | None = None,
) -> ActionCommand:
    input_payload: dict[str, object]
    if manifest.action_id == "cancel_ticket":
        input_payload = {
            "original_run_id": str(compensation_of_run_id or uuid4()),
            "source_ticket_id": "ticket:existing",
            "reason_code": "operator_requested",
        }
    else:
        input_payload = {
            "session_id": "session-SHP-100",
            "summary": summary,
            "priority": "high",
        }
    return ActionCommand(
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        contract_id="aircargo.shipment-status",
        contract_version="0.1.0",
        contract_digest="b" * 64,
        step_id="escalate-create-ticket",
        manifest_id=manifest.id,
        manifest_version=manifest.version,
        manifest_schema_digest=manifest.schema_digest,
        actor_id="agent@example.test",
        actor_scopes=manifest.required_scopes,
        logical_operation_key=logical_operation_key,
        input_payload=input_payload,
        evidence_digest="c" * 64,
        correlation_id=UUID("82000000-0000-0000-0000-000000000001"),
        requested_at=NOW,
        compensation_of_run_id=compensation_of_run_id,
    )


def _gateway(
    store: _MemoryStore,
    policy: _Policy,
    manifest: ActionManifest,
    connector: _Connector,
    checker: _Checker,
    clock: _Clock,
    *extra_bindings: tuple[ActionManifest, _Connector, _Checker],
) -> ActionGateway:
    registry = ActionRegistry()
    registry.register(manifest, connector=connector, checker=checker)
    for extra_manifest, extra_connector, extra_checker in extra_bindings:
        registry.register(extra_manifest, connector=extra_connector, checker=extra_checker)
    return ActionGateway(
        store=store,
        registry=registry,
        policy=policy,
        environment="test",
        clock=clock,
    )


@pytest.mark.asyncio
async def test_policy_denial_and_kill_switch_never_call_connector() -> None:
    manifest = _manifest()
    connector = _Connector()
    checker = _Checker()
    clock = _Clock()
    denied_store = _MemoryStore(manifest)
    denied_policy = _Policy(ActionPolicyResult.DENY)
    denied_gateway = _gateway(denied_store, denied_policy, manifest, connector, checker, clock)

    denied = await denied_gateway.request(_command(manifest))

    assert denied.state is ActionReceiptState.DENIED
    assert denied.run_id is None
    assert not denied_store.runs
    assert connector.execute_calls == 0

    killed_store = _MemoryStore(manifest)
    killed_store.killed = True
    allowed_policy = _Policy(ActionPolicyResult.ALLOW)
    killed_gateway = _gateway(killed_store, allowed_policy, manifest, connector, checker, clock)

    killed = await killed_gateway.request(_command(manifest))

    assert killed.state is ActionReceiptState.DENIED
    assert killed.reason_codes == ("ACTION_KILL_SWITCH_ACTIVE",)
    assert not allowed_policy.calls
    assert connector.execute_calls == 0


@pytest.mark.asyncio
async def test_same_operation_and_input_replays_while_changed_input_conflicts() -> None:
    manifest = _manifest()
    store = _MemoryStore(manifest)
    gateway = _gateway(store, _Policy(), manifest, _Connector(), _Checker(), _Clock())

    first = await gateway.request(_command(manifest))
    replay = await gateway.request(_command(manifest))

    assert first.run_id == replay.run_id
    assert first.replayed is False
    assert replay.replayed is True
    assert len(store.runs) == 1
    with pytest.raises(ActionIdempotencyConflict):
        await gateway.request(_command(manifest, summary="Different canonical input"))
    assert len(store.runs) == 1


@pytest.mark.asyncio
async def test_confirmation_is_exact_single_use_and_expires_without_outbox() -> None:
    manifest = _manifest()
    store = _MemoryStore(manifest)
    clock = _Clock()
    gateway = _gateway(store, _Policy(), manifest, _Connector(), _Checker(), clock)
    receipt = await gateway.request(_command(manifest))
    assert receipt.state is ActionReceiptState.AWAITING_CONFIRMATION
    assert receipt.confirmation_id is not None
    assert receipt.outbox_event_id is None

    with pytest.raises(ActionConfirmationRejected):
        await gateway.confirm(
            tenant_id=TENANT_ID,
            confirmation_id=receipt.confirmation_id,
            actor_id="owner@example.test",
            action_digest="f" * 64,
            decision=ConfirmationDecision.APPROVED,
        )

    clock.value = NOW + timedelta(minutes=6)
    with pytest.raises(ActionConfirmationRejected):
        await gateway.confirm(
            tenant_id=TENANT_ID,
            confirmation_id=receipt.confirmation_id,
            actor_id="owner@example.test",
            action_digest=receipt.action_digest,
            decision=ConfirmationDecision.APPROVED,
        )
    assert not store.outbox


@pytest.mark.asyncio
async def test_timeout_reconciles_same_identity_and_postcondition_without_second_create() -> None:
    manifest = _manifest()
    store = _MemoryStore(manifest)
    connector = _Connector()
    connector.timeout = True
    checker = _Checker()
    clock = _Clock()
    gateway = _gateway(store, _Policy(), manifest, connector, checker, clock)
    requested = await gateway.request(_command(manifest))
    assert requested.confirmation_id is not None
    ready = await gateway.confirm(
        tenant_id=TENANT_ID,
        confirmation_id=requested.confirmation_id,
        actor_id="owner@example.test",
        action_digest=requested.action_digest,
        decision=ConfirmationDecision.APPROVED,
    )
    assert ready.outbox_event_id is not None

    unknown = await gateway.dispatch(TENANT_ID, ready.outbox_event_id)

    assert unknown.state is ActionReceiptState.OUTCOME_UNKNOWN
    assert unknown.outbox_event_id is not None
    assert connector.execute_calls == 1
    with pytest.raises(ActionWorkUnavailable):
        await gateway.dispatch(TENANT_ID, ready.outbox_event_id)
    connector.reconcile_result = ConnectorResult(
        connector_id=manifest.connector_id,
        action_id=manifest.action_id,
        downstream_idempotency_key=store.runs[requested.run_id].downstream_idempotency_key,
        remote_operation_id="operation:existing",
        remote_resource_id="ticket:existing",
        response_digest="e" * 64,
        observed_at=NOW,
    )

    reconciled = await gateway.reconcile(TENANT_ID, unknown.outbox_event_id)

    assert reconciled.state is ActionReceiptState.POSTCONDITION_PASSED
    assert connector.execute_calls == 1
    assert connector.reconcile_calls == 1
    assert checker.calls == 1
    assert len(store.runs) == 1


@pytest.mark.asyncio
async def test_untrusted_connector_identity_cannot_become_success() -> None:
    manifest = _manifest()
    store = _MemoryStore(manifest)
    connector = _Connector()
    connector.result_factory = lambda run: replace(
        _Connector._result(run),
        downstream_idempotency_key="wrong-key",
    )
    checker = _Checker()
    gateway = _gateway(store, _Policy(), manifest, connector, checker, _Clock())
    requested = await gateway.request(_command(manifest))
    assert requested.confirmation_id is not None
    ready = await gateway.confirm(
        tenant_id=TENANT_ID,
        confirmation_id=requested.confirmation_id,
        actor_id="owner@example.test",
        action_digest=requested.action_digest,
        decision=ConfirmationDecision.APPROVED,
    )
    assert ready.outbox_event_id is not None

    result = await gateway.dispatch(TENANT_ID, ready.outbox_event_id)

    assert result.state is ActionReceiptState.OUTCOME_UNKNOWN
    assert checker.calls == 0
    assert connector.execute_calls == 1


@pytest.mark.asyncio
async def test_compensation_requires_its_own_policy_and_confirmation() -> None:
    create_manifest = _manifest()
    cancel_manifest = _manifest(
        manifest_id="support.cancel-ticket",
        action_id="cancel_ticket",
        compensation_manifest_id=None,
    )
    store = _MemoryStore(create_manifest, cancel_manifest)
    create_connector = _Connector()
    cancel_connector = _Connector()
    policy = _Policy(ActionPolicyResult.ALLOW, ActionPolicyResult.DENY)
    gateway = _gateway(
        store,
        policy,
        create_manifest,
        create_connector,
        _Checker(),
        _Clock(),
        (cancel_manifest, cancel_connector, _Checker()),
    )
    original = await gateway.request(_command(create_manifest))
    assert original.run_id is not None

    denied = await gateway.request_compensation(
        original_run_id=original.run_id,
        command=_command(
            cancel_manifest,
            logical_operation_key="shipment:SHP-100:cancel-ticket",
            compensation_of_run_id=original.run_id,
        ),
    )

    assert denied.state is ActionReceiptState.DENIED
    assert cancel_connector.execute_calls == 0
    assert len(store.runs) == 1
    with pytest.raises(ActionCompensationRejected):
        await gateway.request_compensation(
            original_run_id=uuid4(),
            command=_command(
                cancel_manifest,
                logical_operation_key="shipment:SHP-100:other-cancel",
            ),
        )
