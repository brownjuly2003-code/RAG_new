from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import desc, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from actions.domain import (
    ActionConfirmation,
    ActionConfirmationRejected,
    ActionDomainError,
    ActionIdempotencyConflict,
    ActionManifest,
    ActionManifestMismatch,
    ActionOutboxEvent,
    ActionOutboxKind,
    ActionOutboxState,
    ActionPolicyDecision,
    ActionPostconditionResult,
    ActionRisk,
    ActionRun,
    ActionRunState,
    ActionWorkItem,
    ActionWorkUnavailable,
    ConfirmationDecision,
    ConnectorResult,
    TransportOutcome,
    canonical_json,
)
from db.models import (
    GovernedActionAttempt,
    GovernedActionConfirmation,
    GovernedActionKillSwitch,
    GovernedActionManifest,
    GovernedActionOutboxEvent,
    GovernedActionPostconditionResult,
    GovernedActionRun,
    GovernedPolicyDecision,
)

AsyncSessionFactory = Callable[[], AsyncSession]


async def set_action_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    if not isinstance(tenant_id, UUID) or tenant_id.int == 0:
        raise ActionDomainError("action tenant context must be a non-nil UUID")
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def _require_tenant(expected: UUID, actual: UUID) -> None:
    if expected != actual:
        raise ActionDomainError("action store context does not own value")


def _manifest_record_id(manifest: ActionManifest) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"rag-new:action-manifest:{manifest.tenant_id}:{manifest.id}:{manifest.version}",
    )


def _manifest_record(manifest: ActionManifest) -> GovernedActionManifest:
    return GovernedActionManifest(
        record_id=_manifest_record_id(manifest),
        tenant_id=manifest.tenant_id,
        manifest_id=manifest.id,
        version=manifest.version,
        connector_id=manifest.connector_id,
        action_id=manifest.action_id,
        schema_digest=manifest.schema_digest,
        risk=manifest.risk.value,
        required_scopes=list(manifest.required_scopes),
        input_fields=list(manifest.input_fields),
        timeout_seconds=manifest.timeout_seconds,
        confirmation_ttl_seconds=manifest.confirmation_ttl_seconds,
        postcondition_id=manifest.postcondition_id,
        postcondition_version=manifest.postcondition_version,
        compensation_manifest_id=manifest.compensation_manifest_id,
        max_reconciliation_attempts=manifest.max_reconciliation_attempts,
        recorded_at=manifest.recorded_at,
    )


def _manifest_domain(record: GovernedActionManifest) -> ActionManifest:
    return ActionManifest(
        tenant_id=record.tenant_id,
        id=record.manifest_id,
        version=record.version,
        connector_id=record.connector_id,
        action_id=record.action_id,
        schema_digest=record.schema_digest,
        risk=ActionRisk(record.risk),
        required_scopes=tuple(record.required_scopes),
        input_fields=tuple(record.input_fields),
        timeout_seconds=record.timeout_seconds,
        confirmation_ttl_seconds=record.confirmation_ttl_seconds,
        postcondition_id=record.postcondition_id,
        postcondition_version=record.postcondition_version,
        compensation_manifest_id=record.compensation_manifest_id,
        max_reconciliation_attempts=record.max_reconciliation_attempts,
        recorded_at=record.recorded_at,
    )


def _decision_record(decision: ActionPolicyDecision) -> GovernedPolicyDecision:
    return GovernedPolicyDecision(
        id=decision.id,
        tenant_id=decision.tenant_id,
        case_id=decision.case_id,
        action_digest=decision.action_digest,
        input_digest=decision.input_digest,
        evidence_digest=decision.evidence_digest,
        result=decision.result.value,
        reason_codes=list(decision.reason_codes),
        policy_adapter=decision.policy_adapter,
        policy_revision=decision.policy_revision,
        decided_at=decision.decided_at,
        expires_at=decision.expires_at,
    )


def _run_record(run: ActionRun) -> GovernedActionRun:
    return GovernedActionRun(
        id=run.id,
        tenant_id=run.tenant_id,
        case_id=run.case_id,
        manifest_id=run.manifest_id,
        manifest_version=run.manifest_version,
        manifest_schema_digest=run.manifest_schema_digest,
        connector_id=run.connector_id,
        action_id=run.action_id,
        operation_key_digest=run.operation_key_digest,
        input_digest=run.input_digest,
        action_digest=run.action_digest,
        evidence_digest=run.evidence_digest,
        policy_decision_id=run.policy_decision_id,
        downstream_idempotency_key=run.downstream_idempotency_key,
        state=run.state.value,
        input_payload=canonical_json(run.safe_input),
        created_at=run.created_at,
        updated_at=run.updated_at,
        attempt_count=run.attempt_count,
        confirmation_id=run.confirmation_id,
        outbox_event_id=run.outbox_event_id,
        lease_token=run.lease_token,
        lease_expires_at=run.lease_expires_at,
        remote_operation_id=run.remote_operation_id,
        remote_resource_id=run.remote_resource_id,
        result_digest=run.result_digest,
        compensation_of_run_id=run.compensation_of_run_id,
    )


def _run_domain(record: GovernedActionRun) -> ActionRun:
    try:
        safe_input = json.loads(record.input_payload)
    except (TypeError, ValueError) as exc:
        raise ActionDomainError("stored action input is not valid JSON") from exc
    if not isinstance(safe_input, dict):
        raise ActionDomainError("stored action input is not a JSON object")
    return ActionRun(
        id=record.id,
        tenant_id=record.tenant_id,
        case_id=record.case_id,
        manifest_id=record.manifest_id,
        manifest_version=record.manifest_version,
        manifest_schema_digest=record.manifest_schema_digest,
        connector_id=record.connector_id,
        action_id=record.action_id,
        operation_key_digest=record.operation_key_digest,
        input_digest=record.input_digest,
        action_digest=record.action_digest,
        evidence_digest=record.evidence_digest,
        policy_decision_id=record.policy_decision_id,
        downstream_idempotency_key=record.downstream_idempotency_key,
        state=ActionRunState(record.state),
        safe_input=cast(dict[str, object], safe_input),
        created_at=record.created_at,
        updated_at=record.updated_at,
        attempt_count=record.attempt_count,
        confirmation_id=record.confirmation_id,
        outbox_event_id=record.outbox_event_id,
        lease_token=record.lease_token,
        lease_expires_at=record.lease_expires_at,
        remote_operation_id=record.remote_operation_id,
        remote_resource_id=record.remote_resource_id,
        result_digest=record.result_digest,
        compensation_of_run_id=record.compensation_of_run_id,
    )


def _confirmation_record(value: ActionConfirmation) -> GovernedActionConfirmation:
    return GovernedActionConfirmation(
        id=value.id,
        tenant_id=value.tenant_id,
        run_id=value.run_id,
        action_digest=value.action_digest,
        actor_id=value.actor_id,
        decision=value.decision.value,
        expires_at=value.expires_at,
        created_at=value.created_at,
        decided_at=value.decided_at,
    )


def _confirmation_domain(record: GovernedActionConfirmation) -> ActionConfirmation:
    return ActionConfirmation(
        id=record.id,
        tenant_id=record.tenant_id,
        run_id=record.run_id,
        action_digest=record.action_digest,
        actor_id=record.actor_id,
        decision=ConfirmationDecision(record.decision),
        expires_at=record.expires_at,
        created_at=record.created_at,
        decided_at=record.decided_at,
    )


def _outbox_record(value: ActionOutboxEvent) -> GovernedActionOutboxEvent:
    return GovernedActionOutboxEvent(
        id=value.id,
        tenant_id=value.tenant_id,
        run_id=value.run_id,
        sequence=value.sequence,
        kind=value.kind.value,
        state=value.state.value,
        payload_digest=value.payload_digest,
        available_at=value.available_at,
        attempts=value.attempts,
        lease_token=value.lease_token,
        lease_expires_at=value.lease_expires_at,
        delivered_at=value.delivered_at,
    )


def _outbox_domain(record: GovernedActionOutboxEvent) -> ActionOutboxEvent:
    return ActionOutboxEvent(
        id=record.id,
        tenant_id=record.tenant_id,
        run_id=record.run_id,
        sequence=record.sequence,
        kind=ActionOutboxKind(record.kind),
        state=ActionOutboxState(record.state),
        payload_digest=record.payload_digest,
        available_at=record.available_at,
        attempts=record.attempts,
        lease_token=record.lease_token,
        lease_expires_at=record.lease_expires_at,
        delivered_at=record.delivered_at,
    )


class PostgresActionStore:
    """Tenant-bound transactional persistence for governed action execution."""

    def __init__(self, session_factory: AsyncSessionFactory, tenant_id: UUID) -> None:
        if not isinstance(tenant_id, UUID) or tenant_id.int == 0:
            raise ActionDomainError("action store tenant must be a non-nil UUID")
        self._session_factory = session_factory
        self._tenant_id = tenant_id

    def _require_context(self, tenant_id: UUID) -> None:
        _require_tenant(self._tenant_id, tenant_id)

    async def append_manifest(self, manifest: ActionManifest) -> None:
        self._require_context(manifest.tenant_id)
        async with self._session_factory() as session:
            await set_action_tenant_context(session, self._tenant_id)
            existing = await session.scalar(
                select(GovernedActionManifest).where(
                    GovernedActionManifest.tenant_id == self._tenant_id,
                    GovernedActionManifest.manifest_id == manifest.id,
                    GovernedActionManifest.version == manifest.version,
                )
            )
            if existing is not None:
                if _manifest_domain(existing) != manifest:
                    raise ActionManifestMismatch("manifest identity is already bound differently")
                return
            session.add(_manifest_record(manifest))
            await session.commit()

    async def get_manifest(
        self,
        tenant_id: UUID,
        manifest_id: str,
        version: str,
    ) -> ActionManifest | None:
        self._require_context(tenant_id)
        async with self._session_factory() as session:
            await set_action_tenant_context(session, tenant_id)
            record = await session.scalar(
                select(GovernedActionManifest).where(
                    GovernedActionManifest.tenant_id == tenant_id,
                    GovernedActionManifest.manifest_id == manifest_id,
                    GovernedActionManifest.version == version,
                )
            )
            return None if record is None else _manifest_domain(record)

    async def is_killed(
        self,
        tenant_id: UUID,
        environment: str,
        connector_id: str,
        action_id: str,
        at: datetime,
    ) -> bool:
        self._require_context(tenant_id)
        async with self._session_factory() as session:
            await set_action_tenant_context(session, tenant_id)
            records = (
                await session.scalars(
                    select(GovernedActionKillSwitch)
                    .where(
                        GovernedActionKillSwitch.tenant_id == tenant_id,
                        GovernedActionKillSwitch.environment.in_((environment, "*")),
                        GovernedActionKillSwitch.connector_id.in_((connector_id, "*")),
                        GovernedActionKillSwitch.action_id.in_((action_id, "*")),
                        GovernedActionKillSwitch.recorded_at <= at,
                    )
                    .order_by(desc(GovernedActionKillSwitch.version))
                )
            ).all()
            latest_by_scope: dict[tuple[str, str, str], GovernedActionKillSwitch] = {}
            for record in records:
                scope = (record.environment, record.connector_id, record.action_id)
                latest_by_scope.setdefault(scope, record)
            return any(record.active for record in latest_by_scope.values())

    async def find_run_by_operation_key(
        self,
        tenant_id: UUID,
        operation_key_digest: str,
    ) -> ActionRun | None:
        self._require_context(tenant_id)
        async with self._session_factory() as session:
            await set_action_tenant_context(session, tenant_id)
            record = await session.scalar(
                select(GovernedActionRun).where(
                    GovernedActionRun.tenant_id == tenant_id,
                    GovernedActionRun.operation_key_digest == operation_key_digest,
                )
            )
            return None if record is None else _run_domain(record)

    async def save_denial(self, decision: ActionPolicyDecision) -> None:
        self._require_context(decision.tenant_id)
        async with self._session_factory() as session:
            await set_action_tenant_context(session, decision.tenant_id)
            session.add(_decision_record(decision))
            await session.commit()

    @staticmethod
    def _replay_or_conflict(existing: ActionRun, proposed: ActionRun) -> ActionRun:
        if (
            existing.input_digest != proposed.input_digest
            or existing.action_digest != proposed.action_digest
        ):
            raise ActionIdempotencyConflict(
                "logical operation key already owns another action input"
            )
        return existing

    async def create_or_replay(
        self,
        decision: ActionPolicyDecision,
        run: ActionRun,
        confirmation: ActionConfirmation | None,
        outbox: ActionOutboxEvent | None,
    ) -> tuple[ActionRun, bool]:
        self._require_context(run.tenant_id)
        _require_tenant(run.tenant_id, decision.tenant_id)
        if decision.id != run.policy_decision_id:
            raise ActionDomainError("action run is not bound to its policy decision")
        if confirmation is not None:
            _require_tenant(run.tenant_id, confirmation.tenant_id)
            if confirmation.run_id != run.id or confirmation.id != run.confirmation_id:
                raise ActionDomainError("confirmation is not bound to the action run")
        if outbox is not None:
            _require_tenant(run.tenant_id, outbox.tenant_id)
            if outbox.run_id != run.id or outbox.id != run.outbox_event_id:
                raise ActionDomainError("outbox event is not bound to the action run")

        async with self._session_factory() as session:
            await set_action_tenant_context(session, run.tenant_id)
            existing_record = await session.scalar(
                select(GovernedActionRun).where(
                    GovernedActionRun.tenant_id == run.tenant_id,
                    GovernedActionRun.operation_key_digest == run.operation_key_digest,
                )
            )
            if existing_record is not None:
                return self._replay_or_conflict(_run_domain(existing_record), run), True
            try:
                session.add(_decision_record(decision))
                await session.flush()
                run_record = _run_record(run)
                session.add(run_record)
                await session.flush()
                if confirmation is not None:
                    session.add(_confirmation_record(confirmation))
                if outbox is not None:
                    session.add(_outbox_record(outbox))
                await session.flush()
                stored = _run_domain(run_record)
                await session.commit()
                return stored, False
            except IntegrityError:
                await session.rollback()
                await set_action_tenant_context(session, run.tenant_id)
                existing_record = await session.scalar(
                    select(GovernedActionRun).where(
                        GovernedActionRun.tenant_id == run.tenant_id,
                        GovernedActionRun.operation_key_digest == run.operation_key_digest,
                    )
                )
                if existing_record is None:
                    raise
                return self._replay_or_conflict(_run_domain(existing_record), run), True

    async def get_run(self, tenant_id: UUID, run_id: UUID) -> ActionRun | None:
        self._require_context(tenant_id)
        async with self._session_factory() as session:
            await set_action_tenant_context(session, tenant_id)
            record = await session.scalar(
                select(GovernedActionRun).where(
                    GovernedActionRun.tenant_id == tenant_id,
                    GovernedActionRun.id == run_id,
                )
            )
            return None if record is None else _run_domain(record)

    async def get_confirmation(
        self,
        tenant_id: UUID,
        confirmation_id: UUID,
    ) -> ActionConfirmation | None:
        self._require_context(tenant_id)
        async with self._session_factory() as session:
            await set_action_tenant_context(session, tenant_id)
            record = await session.scalar(
                select(GovernedActionConfirmation).where(
                    GovernedActionConfirmation.tenant_id == tenant_id,
                    GovernedActionConfirmation.id == confirmation_id,
                )
            )
            return None if record is None else _confirmation_domain(record)

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
        self._require_context(tenant_id)
        async with self._session_factory() as session:
            await set_action_tenant_context(session, tenant_id)
            confirmation_record = await session.scalar(
                select(GovernedActionConfirmation)
                .where(
                    GovernedActionConfirmation.tenant_id == tenant_id,
                    GovernedActionConfirmation.id == confirmation_id,
                )
                .with_for_update()
            )
            if confirmation_record is None:
                raise ActionConfirmationRejected("confirmation does not exist for this tenant")
            run_record = await session.scalar(
                select(GovernedActionRun)
                .where(
                    GovernedActionRun.tenant_id == tenant_id,
                    GovernedActionRun.id == confirmation_record.run_id,
                )
                .with_for_update()
            )
            if run_record is None:
                raise ActionConfirmationRejected("confirmation run does not exist")
            if (
                confirmation_record.action_digest != action_digest
                or run_record.action_digest != action_digest
            ):
                raise ActionConfirmationRejected("confirmation is not bound to this action")
            if confirmation_record.decision != ConfirmationDecision.PENDING.value:
                raise ActionConfirmationRejected("confirmation was already decided")
            if decided_at >= confirmation_record.expires_at:
                confirmation_record.decision = ConfirmationDecision.EXPIRED.value
                confirmation_record.decided_at = decided_at
                run_record.state = ActionRunState.EXPIRED.value
                run_record.updated_at = decided_at
                await session.commit()
                raise ActionConfirmationRejected("confirmation expired")
            if decision is ConfirmationDecision.APPROVED:
                if outbox is None or outbox.run_id != run_record.id:
                    raise ActionConfirmationRejected("approval requires its exact dispatch event")
                _require_tenant(tenant_id, outbox.tenant_id)
                session.add(_outbox_record(outbox))
                run_record.state = ActionRunState.READY.value
                run_record.outbox_event_id = outbox.id
            elif decision is ConfirmationDecision.DENIED:
                if outbox is not None:
                    raise ActionConfirmationRejected("denial cannot enqueue connector work")
                run_record.state = ActionRunState.CANCELLED.value
            else:
                raise ActionConfirmationRejected("confirmation must approve or deny")
            confirmation_record.actor_id = actor_id
            confirmation_record.decision = decision.value
            confirmation_record.decided_at = decided_at
            run_record.updated_at = decided_at
            await session.flush()
            stored = _run_domain(run_record)
            await session.commit()
            return stored

    async def lease_event(
        self,
        tenant_id: UUID,
        event_id: UUID,
        lease_token: str,
        lease_expires_at: datetime,
        leased_at: datetime,
    ) -> ActionWorkItem:
        self._require_context(tenant_id)
        async with self._session_factory() as session:
            await set_action_tenant_context(session, tenant_id)
            event_record = await session.scalar(
                select(GovernedActionOutboxEvent)
                .where(
                    GovernedActionOutboxEvent.tenant_id == tenant_id,
                    GovernedActionOutboxEvent.id == event_id,
                )
                .with_for_update()
            )
            if (
                event_record is None
                or event_record.state != ActionOutboxState.PENDING.value
                or event_record.available_at > leased_at
            ):
                raise ActionWorkUnavailable("action outbox event is not claimable")
            run_record = await session.scalar(
                select(GovernedActionRun)
                .where(
                    GovernedActionRun.tenant_id == tenant_id,
                    GovernedActionRun.id == event_record.run_id,
                )
                .with_for_update()
            )
            if run_record is None or run_record.outbox_event_id != event_record.id:
                raise ActionWorkUnavailable("action run does not own this outbox event")
            expected_state = {
                ActionOutboxKind.DISPATCH.value: ActionRunState.READY,
                ActionOutboxKind.RECONCILE.value: ActionRunState.OUTCOME_UNKNOWN,
            }[event_record.kind]
            resulting_state = {
                ActionOutboxKind.DISPATCH.value: ActionRunState.DISPATCHED,
                ActionOutboxKind.RECONCILE.value: ActionRunState.RECONCILING,
            }[event_record.kind]
            if run_record.state != expected_state.value:
                raise ActionWorkUnavailable("action run is not claimable")
            manifest_record = await session.scalar(
                select(GovernedActionManifest).where(
                    GovernedActionManifest.tenant_id == tenant_id,
                    GovernedActionManifest.manifest_id == run_record.manifest_id,
                    GovernedActionManifest.version == run_record.manifest_version,
                )
            )
            if manifest_record is None:
                raise ActionManifestMismatch("action manifest disappeared before dispatch")

            event_record.state = ActionOutboxState.LEASED.value
            event_record.attempts += 1
            event_record.lease_token = lease_token
            event_record.lease_expires_at = lease_expires_at
            run_record.state = resulting_state.value
            run_record.attempt_count += 1
            run_record.lease_token = lease_token
            run_record.lease_expires_at = lease_expires_at
            run_record.updated_at = leased_at
            session.add(
                GovernedActionAttempt(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    run_id=run_record.id,
                    attempt_number=run_record.attempt_count,
                    kind=event_record.kind,
                    request_digest=event_record.payload_digest,
                    started_at=leased_at,
                    finished_at=None,
                    transport_outcome=None,
                    response_digest=None,
                    remote_operation_id=None,
                    remote_resource_id=None,
                )
            )
            await session.flush()
            work = ActionWorkItem(
                run=_run_domain(run_record),
                manifest=_manifest_domain(manifest_record),
                event=_outbox_domain(event_record),
                attempt_number=run_record.attempt_count,
                lease_token=lease_token,
                started_at=leased_at,
            )
            await session.commit()
            return work

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
        self._require_context(work.run.tenant_id)
        if connector_result is not None:
            connector_result.require_identity(work.manifest, work.run)
        if next_event is not None:
            _require_tenant(work.run.tenant_id, next_event.tenant_id)
            if next_event.run_id != work.run.id:
                raise ActionWorkUnavailable("next outbox event is not bound to this run")

        async with self._session_factory() as session:
            await set_action_tenant_context(session, work.run.tenant_id)
            event_record = await session.scalar(
                select(GovernedActionOutboxEvent)
                .where(
                    GovernedActionOutboxEvent.tenant_id == work.run.tenant_id,
                    GovernedActionOutboxEvent.id == work.event.id,
                )
                .with_for_update()
            )
            run_record = await session.scalar(
                select(GovernedActionRun)
                .where(
                    GovernedActionRun.tenant_id == work.run.tenant_id,
                    GovernedActionRun.id == work.run.id,
                )
                .with_for_update()
            )
            attempt_record = await session.scalar(
                select(GovernedActionAttempt)
                .where(
                    GovernedActionAttempt.tenant_id == work.run.tenant_id,
                    GovernedActionAttempt.run_id == work.run.id,
                    GovernedActionAttempt.attempt_number == work.attempt_number,
                )
                .with_for_update()
            )
            expected_run_state = {
                ActionOutboxKind.DISPATCH: ActionRunState.DISPATCHED,
                ActionOutboxKind.RECONCILE: ActionRunState.RECONCILING,
            }[work.event.kind]
            if (
                event_record is None
                or run_record is None
                or attempt_record is None
                or event_record.state != ActionOutboxState.LEASED.value
                or event_record.lease_token != work.lease_token
                or run_record.lease_token != work.lease_token
                or run_record.state != expected_run_state.value
                or attempt_record.finished_at is not None
            ):
                raise ActionWorkUnavailable("action work lease is stale or already completed")

            event_record.state = ActionOutboxState.DELIVERED.value
            event_record.lease_token = None
            event_record.lease_expires_at = None
            event_record.delivered_at = finished_at
            attempt_record.finished_at = finished_at
            attempt_record.transport_outcome = transport_outcome.value
            attempt_record.response_digest = (
                None if connector_result is None else connector_result.response_digest
            )
            attempt_record.remote_operation_id = (
                None if connector_result is None else connector_result.remote_operation_id
            )
            attempt_record.remote_resource_id = (
                None if connector_result is None else connector_result.remote_resource_id
            )
            run_record.state = resulting_state.value
            run_record.updated_at = finished_at
            run_record.lease_token = None
            run_record.lease_expires_at = None
            if connector_result is not None:
                run_record.remote_operation_id = connector_result.remote_operation_id
                run_record.remote_resource_id = connector_result.remote_resource_id
                run_record.result_digest = connector_result.response_digest
            if next_event is None:
                run_record.outbox_event_id = None
            else:
                if next_event.sequence != event_record.sequence + 1:
                    raise ActionWorkUnavailable("next outbox sequence is not monotonic")
                session.add(_outbox_record(next_event))
                run_record.outbox_event_id = next_event.id
            await session.flush()
            stored = _run_domain(run_record)
            await session.commit()
            return stored

    async def record_postcondition(
        self,
        run: ActionRun,
        result: ActionPostconditionResult,
        resulting_state: ActionRunState,
    ) -> ActionRun:
        self._require_context(run.tenant_id)
        _require_tenant(run.tenant_id, result.tenant_id)
        if result.run_id != run.id:
            raise ActionWorkUnavailable("postcondition is not bound to the action run")
        if resulting_state not in {
            ActionRunState.POSTCONDITION_PASSED,
            ActionRunState.POSTCONDITION_FAILED,
            ActionRunState.ESCALATED,
        }:
            raise ActionWorkUnavailable("invalid postcondition terminal state")
        async with self._session_factory() as session:
            await set_action_tenant_context(session, run.tenant_id)
            run_record = await session.scalar(
                select(GovernedActionRun)
                .where(
                    GovernedActionRun.tenant_id == run.tenant_id,
                    GovernedActionRun.id == run.id,
                )
                .with_for_update()
            )
            if run_record is None or run_record.state != ActionRunState.SUCCEEDED.value:
                raise ActionWorkUnavailable("action run is not awaiting its postcondition")
            session.add(
                GovernedActionPostconditionResult(
                    id=result.id,
                    tenant_id=result.tenant_id,
                    run_id=result.run_id,
                    checker_id=result.checker_id,
                    checker_version=result.checker_version,
                    observation_digest=result.observation_digest,
                    status=result.status.value,
                    reason_codes=list(result.reason_codes),
                    checked_at=result.checked_at,
                )
            )
            run_record.state = resulting_state.value
            run_record.updated_at = result.checked_at
            run_record.outbox_event_id = None
            await session.flush()
            stored = _run_domain(run_record)
            await session.commit()
            return stored


__all__ = ["PostgresActionStore", "set_action_tenant_context"]
