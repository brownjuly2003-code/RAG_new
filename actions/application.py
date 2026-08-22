from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from actions.domain import (
    ActionCommand,
    ActionCompensationRejected,
    ActionConfirmation,
    ActionConfirmationRejected,
    ActionConnectorIdentityMismatch,
    ActionConnectorRejected,
    ActionIdempotencyConflict,
    ActionManifest,
    ActionManifestMismatch,
    ActionOutboxEvent,
    ActionOutboxKind,
    ActionOutboxState,
    ActionPolicyDecision,
    ActionPolicyMismatch,
    ActionPolicyRequest,
    ActionPolicyResult,
    ActionPostconditionResult,
    ActionReceipt,
    ActionReceiptState,
    ActionRun,
    ActionRunState,
    ActionWorkItem,
    ConfirmationDecision,
    ConnectorResult,
    InvalidActionValue,
    PostconditionStatus,
    TransportOutcome,
    canonical_sha256,
    derive_action_digests,
)
from actions.ports import ActionConnector, ActionStore, PolicyDecisionPoint, PostconditionChecker


@dataclass(frozen=True, slots=True)
class _ActionBinding:
    manifest: ActionManifest
    connector: ActionConnector
    checker: PostconditionChecker


class ActionRegistry:
    """Process-local allowlist bound to exact durable manifest identities."""

    def __init__(self) -> None:
        self._bindings: dict[tuple[UUID, str, str], _ActionBinding] = {}

    def register(
        self,
        manifest: ActionManifest,
        *,
        connector: ActionConnector,
        checker: PostconditionChecker,
    ) -> None:
        key = (manifest.tenant_id, manifest.id, manifest.version)
        binding = _ActionBinding(manifest=manifest, connector=connector, checker=checker)
        existing = self._bindings.get(key)
        if existing is not None and existing != binding:
            raise ActionManifestMismatch("manifest identity is already registered differently")
        self._bindings[key] = binding

    def resolve(self, manifest: ActionManifest) -> _ActionBinding:
        binding = self._bindings.get((manifest.tenant_id, manifest.id, manifest.version))
        if binding is None or binding.manifest != manifest:
            raise ActionManifestMismatch("persisted manifest is not pinned in the action registry")
        return binding

    def canonicalize_input(
        self,
        manifest: ActionManifest,
        payload: dict[str, object],
    ) -> dict[str, object]:
        if set(payload) != set(manifest.input_fields):
            raise InvalidActionValue("action input fields do not match the pinned manifest")
        if manifest.action_id == "create_ticket":
            session_id = payload.get("session_id")
            summary = payload.get("summary")
            priority = payload.get("priority")
            if not isinstance(session_id, str) or not 1 <= len(session_id.strip()) <= 128:
                raise InvalidActionValue("ticket session_id is invalid")
            if not isinstance(summary, str) or not 1 <= len(summary.strip()) <= 2000:
                raise InvalidActionValue("ticket summary is invalid")
            if priority not in {"low", "normal", "high", "critical"}:
                raise InvalidActionValue("ticket priority is invalid")
            return {
                "priority": priority,
                "session_id": session_id.strip(),
                "summary": summary.strip(),
            }
        if manifest.action_id == "cancel_ticket":
            original_run_id = payload.get("original_run_id")
            source_ticket_id = payload.get("source_ticket_id")
            reason_code = payload.get("reason_code")
            try:
                UUID(str(original_run_id))
            except (TypeError, ValueError) as exc:
                raise InvalidActionValue("cancel original_run_id is invalid") from exc
            if not isinstance(source_ticket_id, str) or not source_ticket_id.strip():
                raise InvalidActionValue("cancel source_ticket_id is invalid")
            if not isinstance(reason_code, str) or not 1 <= len(reason_code.strip()) <= 128:
                raise InvalidActionValue("cancel reason_code is invalid")
            return {
                "original_run_id": str(original_run_id),
                "reason_code": reason_code.strip(),
                "source_ticket_id": source_ticket_id.strip(),
            }
        return dict(payload)


class ActionGateway:
    """Governed durable action request, dispatch, reconciliation and checking."""

    def __init__(
        self,
        *,
        store: ActionStore,
        registry: ActionRegistry,
        policy: PolicyDecisionPoint,
        environment: str,
        clock: Callable[[], datetime] | None = None,
        lease_seconds: int = 30,
    ) -> None:
        if not environment or environment != environment.strip():
            raise InvalidActionValue("action environment must be non-empty trimmed text")
        if not 1 <= lease_seconds <= 3600:
            raise InvalidActionValue("action lease_seconds is outside 1..3600")
        self._store = store
        self._registry = registry
        self._policy = policy
        self._environment = environment
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lease_seconds = lease_seconds

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise InvalidActionValue("action clock must return timezone-aware timestamps")
        return value

    @staticmethod
    def _receipt(
        run: ActionRun,
        *,
        replayed: bool = False,
        reason_codes: tuple[str, ...] = (),
    ) -> ActionReceipt:
        return ActionReceipt(
            state=ActionReceiptState(run.state.value),
            action_digest=run.action_digest,
            reason_codes=reason_codes,
            run_id=run.id,
            confirmation_id=run.confirmation_id,
            outbox_event_id=run.outbox_event_id,
            remote_resource_id=run.remote_resource_id,
            replayed=replayed,
        )

    @staticmethod
    def _outbox(
        run_id: UUID,
        tenant_id: UUID,
        action_digest: str,
        *,
        sequence: int,
        kind: ActionOutboxKind,
        available_at: datetime,
    ) -> ActionOutboxEvent:
        return ActionOutboxEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            run_id=run_id,
            sequence=sequence,
            kind=kind,
            state=ActionOutboxState.PENDING,
            payload_digest=canonical_sha256(
                {
                    "run_id": str(run_id),
                    "action_digest": action_digest,
                    "sequence": sequence,
                    "kind": kind.value,
                }
            ),
            available_at=available_at,
        )

    @staticmethod
    def _system_denial(
        command: ActionCommand,
        *,
        action_digest: str,
        input_digest: str,
        reason_code: str,
        decided_at: datetime,
    ) -> ActionPolicyDecision:
        return ActionPolicyDecision(
            id=uuid4(),
            tenant_id=command.tenant_id,
            case_id=command.case_id,
            action_digest=action_digest,
            input_digest=input_digest,
            evidence_digest=command.evidence_digest,
            result=ActionPolicyResult.DENY,
            reason_codes=(reason_code,),
            policy_adapter="action-gateway",
            policy_revision="local-guard/1.0.0",
            decided_at=decided_at,
            expires_at=decided_at + timedelta(seconds=1),
        )

    @staticmethod
    def _validate_policy(
        request: ActionPolicyRequest,
        decision: ActionPolicyDecision,
        now: datetime,
    ) -> None:
        if (
            decision.tenant_id != request.tenant_id
            or decision.case_id != request.case_id
            or decision.action_digest != request.action_digest
            or decision.input_digest != request.input_digest
            or decision.evidence_digest != request.evidence_digest
            or decision.decided_at > now
            or decision.expires_at <= now
        ):
            raise ActionPolicyMismatch("PDP decision is not bound to the exact action request")

    async def request(self, command: ActionCommand) -> ActionReceipt:
        now = self._now()
        manifest = await self._store.get_manifest(
            command.tenant_id,
            command.manifest_id,
            command.manifest_version,
        )
        if manifest is None:
            raise ActionManifestMismatch("requested action manifest is not durably registered")
        self._registry.resolve(manifest)
        canonical_input = self._registry.canonicalize_input(manifest, command.input_payload)
        command = replace(command, input_payload=canonical_input)
        digests = derive_action_digests(manifest, command)

        existing = await self._store.find_run_by_operation_key(
            command.tenant_id,
            digests.operation_key_digest,
        )
        if existing is not None:
            if (
                existing.input_digest != digests.input_digest
                or existing.action_digest != digests.action_digest
            ):
                raise ActionIdempotencyConflict("logical operation key already owns another input")
            return self._receipt(existing, replayed=True)

        missing_scopes = set(manifest.required_scopes) - set(command.actor_scopes)
        killed = await self._store.is_killed(
            command.tenant_id,
            self._environment,
            manifest.connector_id,
            manifest.action_id,
            now,
        )
        guard_reason = (
            "ACTION_SCOPE_DENIED"
            if missing_scopes
            else "ACTION_KILL_SWITCH_ACTIVE"
            if killed
            else None
        )
        if guard_reason is not None:
            denial = self._system_denial(
                command,
                action_digest=digests.action_digest,
                input_digest=digests.input_digest,
                reason_code=guard_reason,
                decided_at=now,
            )
            await self._store.save_denial(denial)
            return ActionReceipt(
                state=ActionReceiptState.DENIED,
                action_digest=digests.action_digest,
                reason_codes=denial.reason_codes,
            )

        policy_request = ActionPolicyRequest(
            tenant_id=command.tenant_id,
            case_id=command.case_id,
            actor_id=command.actor_id,
            actor_scopes=command.actor_scopes,
            manifest_id=manifest.id,
            manifest_version=manifest.version,
            action_digest=digests.action_digest,
            input_digest=digests.input_digest,
            evidence_digest=command.evidence_digest,
            risk=manifest.risk,
            requested_at=command.requested_at,
        )
        decision = await self._policy.decide(policy_request)
        self._validate_policy(policy_request, decision, now)
        if decision.result is not ActionPolicyResult.ALLOW:
            await self._store.save_denial(decision)
            return ActionReceipt(
                state=ActionReceiptState.DENIED,
                action_digest=digests.action_digest,
                reason_codes=decision.reason_codes,
            )

        run_id = uuid4()
        confirmation_id = uuid4() if manifest.confirmation_ttl_seconds is not None else None
        outbox = (
            None
            if confirmation_id is not None
            else self._outbox(
                run_id,
                command.tenant_id,
                digests.action_digest,
                sequence=1,
                kind=ActionOutboxKind.DISPATCH,
                available_at=now,
            )
        )
        run = ActionRun(
            id=run_id,
            tenant_id=command.tenant_id,
            case_id=command.case_id,
            manifest_id=manifest.id,
            manifest_version=manifest.version,
            manifest_schema_digest=manifest.schema_digest,
            connector_id=manifest.connector_id,
            action_id=manifest.action_id,
            operation_key_digest=digests.operation_key_digest,
            input_digest=digests.input_digest,
            action_digest=digests.action_digest,
            evidence_digest=command.evidence_digest,
            policy_decision_id=decision.id,
            downstream_idempotency_key=f"action:{digests.operation_key_digest}",
            state=(
                ActionRunState.AWAITING_CONFIRMATION
                if confirmation_id is not None
                else ActionRunState.READY
            ),
            safe_input=command.input_payload,
            created_at=now,
            updated_at=now,
            confirmation_id=confirmation_id,
            outbox_event_id=None if outbox is None else outbox.id,
            compensation_of_run_id=command.compensation_of_run_id,
        )
        confirmation = (
            None
            if confirmation_id is None or manifest.confirmation_ttl_seconds is None
            else ActionConfirmation(
                id=confirmation_id,
                tenant_id=command.tenant_id,
                run_id=run_id,
                action_digest=digests.action_digest,
                actor_id=None,
                decision=ConfirmationDecision.PENDING,
                expires_at=now + timedelta(seconds=manifest.confirmation_ttl_seconds),
                created_at=now,
            )
        )
        stored, replayed = await self._store.create_or_replay(
            decision,
            run,
            confirmation,
            outbox,
        )
        return self._receipt(stored, replayed=replayed)

    async def confirm(
        self,
        *,
        tenant_id: UUID,
        confirmation_id: UUID,
        actor_id: str,
        action_digest: str,
        decision: ConfirmationDecision,
    ) -> ActionReceipt:
        if decision not in {ConfirmationDecision.APPROVED, ConfirmationDecision.DENIED}:
            raise ActionConfirmationRejected("confirmation decision must approve or deny")
        confirmation = await self._store.get_confirmation(tenant_id, confirmation_id)
        if confirmation is None:
            raise ActionConfirmationRejected("confirmation does not exist for this tenant")
        run = await self._store.get_run(tenant_id, confirmation.run_id)
        if run is None:
            raise ActionConfirmationRejected("confirmation run does not exist for this tenant")
        manifest = await self._store.get_manifest(tenant_id, run.manifest_id, run.manifest_version)
        if manifest is None:
            raise ActionManifestMismatch("confirmation manifest is unavailable")
        self._registry.resolve(manifest)
        now = self._now()
        if decision is ConfirmationDecision.APPROVED and await self._store.is_killed(
            tenant_id,
            self._environment,
            manifest.connector_id,
            manifest.action_id,
            now,
        ):
            raise ActionConfirmationRejected("action kill switch is active")
        outbox = (
            self._outbox(
                run.id,
                tenant_id,
                run.action_digest,
                sequence=1,
                kind=ActionOutboxKind.DISPATCH,
                available_at=now,
            )
            if decision is ConfirmationDecision.APPROVED
            else None
        )
        run = await self._store.decide_confirmation(
            tenant_id,
            confirmation_id,
            actor_id,
            action_digest,
            decision,
            now,
            outbox,
        )
        return self._receipt(run)

    async def _lease(self, tenant_id: UUID, event_id: UUID) -> ActionWorkItem:
        now = self._now()
        return await self._store.lease_event(
            tenant_id,
            event_id,
            uuid4().hex,
            now + timedelta(seconds=self._lease_seconds),
            now,
        )

    async def _unknown(
        self,
        work: ActionWorkItem,
        outcome: TransportOutcome,
    ) -> ActionReceipt:
        now = self._now()
        next_event = self._outbox(
            work.run.id,
            work.run.tenant_id,
            work.run.action_digest,
            sequence=work.event.sequence + 1,
            kind=ActionOutboxKind.RECONCILE,
            available_at=now,
        )
        run = await self._store.complete_event(
            work,
            transport_outcome=outcome,
            resulting_state=ActionRunState.OUTCOME_UNKNOWN,
            finished_at=now,
            connector_result=None,
            next_event=next_event,
        )
        return self._receipt(run)

    async def dispatch(self, tenant_id: UUID, event_id: UUID) -> ActionReceipt:
        work = await self._lease(tenant_id, event_id)
        binding = self._registry.resolve(work.manifest)
        now = self._now()
        if await self._store.is_killed(
            tenant_id,
            self._environment,
            work.manifest.connector_id,
            work.manifest.action_id,
            now,
        ):
            run = await self._store.complete_event(
                work,
                transport_outcome=TransportOutcome.REJECTED,
                resulting_state=ActionRunState.ESCALATED,
                finished_at=now,
                connector_result=None,
                next_event=None,
            )
            return self._receipt(run, reason_codes=("ACTION_KILL_SWITCH_ACTIVE",))
        try:
            result = await asyncio.wait_for(
                binding.connector.execute(work.manifest, work.run),
                timeout=work.manifest.timeout_seconds,
            )
            result.require_identity(work.manifest, work.run)
        except ActionConnectorRejected:
            run = await self._store.complete_event(
                work,
                transport_outcome=TransportOutcome.REJECTED,
                resulting_state=ActionRunState.FAILED,
                finished_at=self._now(),
                connector_result=None,
                next_event=None,
            )
            return self._receipt(run)
        except ActionConnectorIdentityMismatch:
            return await self._unknown(work, TransportOutcome.IDENTITY_MISMATCH)
        except (TimeoutError, asyncio.TimeoutError):
            return await self._unknown(work, TransportOutcome.TIMED_OUT)
        except Exception:
            return await self._unknown(work, TransportOutcome.UNAVAILABLE)

        run = await self._store.complete_event(
            work,
            transport_outcome=TransportOutcome.SUCCEEDED,
            resulting_state=ActionRunState.SUCCEEDED,
            finished_at=self._now(),
            connector_result=result,
            next_event=None,
        )
        return await self._check_postcondition(binding, run, result)

    async def _check_postcondition(
        self,
        binding: _ActionBinding,
        run: ActionRun,
        connector_result: ConnectorResult,
    ) -> ActionReceipt:
        now = self._now()
        try:
            result = await binding.checker.check(binding.manifest, run, connector_result, now)
            if (
                result.tenant_id != run.tenant_id
                or result.run_id != run.id
                or result.checker_id != binding.manifest.postcondition_id
                or result.checker_version != binding.manifest.postcondition_version
                or result.observation_digest != connector_result.response_digest
            ):
                raise ActionConnectorIdentityMismatch("postcondition result is not pinned")
        except Exception:
            result = ActionPostconditionResult(
                id=uuid4(),
                tenant_id=run.tenant_id,
                run_id=run.id,
                checker_id=binding.manifest.postcondition_id,
                checker_version=binding.manifest.postcondition_version,
                observation_digest=connector_result.response_digest,
                status=PostconditionStatus.UNKNOWN,
                reason_codes=("POSTCONDITION_UNAVAILABLE",),
                checked_at=now,
            )
        state = {
            PostconditionStatus.PASS: ActionRunState.POSTCONDITION_PASSED,
            PostconditionStatus.FAIL: ActionRunState.POSTCONDITION_FAILED,
            PostconditionStatus.UNKNOWN: ActionRunState.ESCALATED,
        }[result.status]
        run = await self._store.record_postcondition(run, result, state)
        return self._receipt(run, reason_codes=result.reason_codes)

    async def reconcile(self, tenant_id: UUID, event_id: UUID) -> ActionReceipt:
        work = await self._lease(tenant_id, event_id)
        binding = self._registry.resolve(work.manifest)
        try:
            result = await asyncio.wait_for(
                binding.connector.reconcile(work.manifest, work.run),
                timeout=work.manifest.timeout_seconds,
            )
        except (TimeoutError, asyncio.TimeoutError):
            result = None
        except Exception:
            result = None
        if result is None:
            now = self._now()
            exhausted = work.event.attempts >= work.manifest.max_reconciliation_attempts
            next_event = (
                None
                if exhausted
                else self._outbox(
                    work.run.id,
                    tenant_id,
                    work.run.action_digest,
                    sequence=work.event.sequence + 1,
                    kind=ActionOutboxKind.RECONCILE,
                    available_at=now,
                )
            )
            run = await self._store.complete_event(
                work,
                transport_outcome=TransportOutcome.NOT_FOUND,
                resulting_state=(
                    ActionRunState.ESCALATED if exhausted else ActionRunState.OUTCOME_UNKNOWN
                ),
                finished_at=now,
                connector_result=None,
                next_event=next_event,
            )
            return self._receipt(run)
        try:
            result.require_identity(work.manifest, work.run)
        except ActionConnectorIdentityMismatch:
            run = await self._store.complete_event(
                work,
                transport_outcome=TransportOutcome.IDENTITY_MISMATCH,
                resulting_state=ActionRunState.ESCALATED,
                finished_at=self._now(),
                connector_result=None,
                next_event=None,
            )
            return self._receipt(run)
        run = await self._store.complete_event(
            work,
            transport_outcome=TransportOutcome.SUCCEEDED,
            resulting_state=ActionRunState.SUCCEEDED,
            finished_at=self._now(),
            connector_result=result,
            next_event=None,
        )
        return await self._check_postcondition(binding, run, result)

    async def request_compensation(
        self,
        *,
        original_run_id: UUID,
        command: ActionCommand,
    ) -> ActionReceipt:
        original = await self._store.get_run(command.tenant_id, original_run_id)
        if original is None or command.compensation_of_run_id != original_run_id:
            raise ActionCompensationRejected("compensation is not linked to an owned action run")
        original_manifest = await self._store.get_manifest(
            command.tenant_id,
            original.manifest_id,
            original.manifest_version,
        )
        if (
            original_manifest is None
            or original_manifest.compensation_manifest_id != command.manifest_id
        ):
            raise ActionCompensationRejected("manifest is not the governed compensation action")
        return await self.request(command)


__all__ = ["ActionGateway", "ActionRegistry"]
