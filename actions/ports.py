from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from actions.domain import (
    ActionConfirmation,
    ActionManifest,
    ActionOutboxEvent,
    ActionPolicyDecision,
    ActionPolicyRequest,
    ActionPostconditionResult,
    ActionRun,
    ActionRunState,
    ActionWorkItem,
    ConfirmationDecision,
    ConnectorResult,
    TransportOutcome,
)


class PolicyDecisionPoint(Protocol):
    async def decide(self, request: ActionPolicyRequest) -> ActionPolicyDecision: ...


class ActionConnector(Protocol):
    async def execute(self, manifest: ActionManifest, run: ActionRun) -> ConnectorResult: ...

    async def reconcile(
        self,
        manifest: ActionManifest,
        run: ActionRun,
    ) -> ConnectorResult | None: ...


class PostconditionChecker(Protocol):
    async def check(
        self,
        manifest: ActionManifest,
        run: ActionRun,
        result: ConnectorResult,
        checked_at: datetime,
    ) -> ActionPostconditionResult: ...


class ActionStore(Protocol):
    async def get_manifest(
        self,
        tenant_id: UUID,
        manifest_id: str,
        version: str,
    ) -> ActionManifest | None: ...

    async def is_killed(
        self,
        tenant_id: UUID,
        environment: str,
        connector_id: str,
        action_id: str,
        at: datetime,
    ) -> bool: ...

    async def find_run_by_operation_key(
        self,
        tenant_id: UUID,
        operation_key_digest: str,
    ) -> ActionRun | None: ...

    async def save_denial(self, decision: ActionPolicyDecision) -> None: ...

    async def create_or_replay(
        self,
        decision: ActionPolicyDecision,
        run: ActionRun,
        confirmation: ActionConfirmation | None,
        outbox: ActionOutboxEvent | None,
    ) -> tuple[ActionRun, bool]: ...

    async def get_run(self, tenant_id: UUID, run_id: UUID) -> ActionRun | None: ...

    async def get_confirmation(
        self,
        tenant_id: UUID,
        confirmation_id: UUID,
    ) -> ActionConfirmation | None: ...

    async def decide_confirmation(
        self,
        tenant_id: UUID,
        confirmation_id: UUID,
        actor_id: str,
        action_digest: str,
        decision: ConfirmationDecision,
        decided_at: datetime,
        outbox: ActionOutboxEvent | None,
    ) -> ActionRun: ...

    async def lease_event(
        self,
        tenant_id: UUID,
        event_id: UUID,
        lease_token: str,
        lease_expires_at: datetime,
        leased_at: datetime,
    ) -> ActionWorkItem: ...

    async def complete_event(
        self,
        work: ActionWorkItem,
        *,
        transport_outcome: TransportOutcome,
        resulting_state: ActionRunState,
        finished_at: datetime,
        connector_result: ConnectorResult | None,
        next_event: ActionOutboxEvent | None,
    ) -> ActionRun: ...

    async def record_postcondition(
        self,
        run: ActionRun,
        result: ActionPostconditionResult,
        resulting_state: ActionRunState,
    ) -> ActionRun: ...


__all__ = ["ActionConnector", "ActionStore", "PolicyDecisionPoint", "PostconditionChecker"]
