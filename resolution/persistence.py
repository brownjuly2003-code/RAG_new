"""Turn what a shadow observed into rows in the resolution tables.

Phase A.1b of plan_23_08_2026. A.1 and A.5 put the evidence bundle in the
trace, which makes it *visible*; this module makes it *queryable* — a
`support_cases` row with its `case_events`, the `evidence_snapshots` the
journey actually read, and the `case_evidence_links` that tie them to the
case. That is what the Evidence tab in A.3 reads, and what any later question
about "what did the system know when it said that" has to be answered from.

Two rules shape everything here.

**The case walks a real path.** The kernel's transition graph is not
decoration: `SupportCase.transition` rejects anything the contract does not
allow. So the terminal outcome is not written directly onto a fresh case —
the case is opened at `received` and stepped through the states the evidence
in the bundle actually justifies. A run that produced a source observation
passed through `evidence_gathering`; one that produced a policy decision
passed through `policy_pending`. If a bundle ever describes a path the graph
refuses, the write fails and nothing is recorded, which is the correct
outcome: a case history that never happened is worse than none.

**Nothing here may break the answer.** Every entry point is called from the
`/api/ask` shadow, which has already returned a legacy answer to somebody.
Failures are logged and swallowed by the caller; the functions below raise
freely so that the reason is visible in the log rather than silently coerced
into a half-written case.

Known limitation, deliberate: evidence snapshots are recorded with an
open-ended validity range and deduplicated by identity. A source that later
reports *different* content for the same logical key inside the same window
will be rejected by `ex_evidence_snapshots_temporal_identity` rather than
closing the previous range. Closing ranges is real bitemporal bookkeeping and
belongs with the source adapters, not with a shadow observer; the fixture TMS
is static, so nothing exercises it yet. Recorded in `BACKLOG.md`.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from resolution.application.shipment_status import (
    PolicyDecisionExport,
    ShipmentEvidenceExport,
    SourceObservationExport,
)
from resolution.contracts import TerminalOutcome
from resolution.domain.cases import CaseMutation, CaseStatus, SupportCase
from resolution.domain.evidence import (
    EVIDENCE_ENCRYPTION_PROFILE,
    EvidenceLink,
    EvidencePurpose,
    EvidenceSnapshot,
    EvidenceSourceType,
    EvidenceStorage,
    EvidenceVisibility,
    FreshnessStatus,
    ProtectedEvidenceReference,
)
from resolution.domain.values import ContractVersionRef, TenantContext, TimeRange

logger = logging.getLogger(__name__)

# The shadow is not a person and must not borrow one's identity. A fixed
# synthetic actor keeps every row it writes attributable to the observer
# rather than to whoever happened to ask the question.
SHADOW_ACTOR_ID = uuid5(NAMESPACE_URL, "rag-new:shadow-actor:resolution")
SHADOW_SCOPES = frozenset({"case:agent"})

SOURCE_REQUIREMENT_ID = "shipment-observation"
POLICY_REQUIREMENT_ID = "shipment-policy"

# Everything a shadow records is support-facing. The journey's own policy step
# decides what may be disclosed to a customer, and that decision is about the
# *answer*, not about the evidence row behind it; marking the row
# customer-safe because one policy said "allow" would bake a disclosure
# decision into storage where nothing re-checks it.
SHADOW_VISIBILITY = EvidenceVisibility.SUPPORT_ONLY
SHADOW_RETENTION_CLASS = "support-case-90d"
SHADOW_REDACTION_PROFILE = "customer-safe-v1"

_TERMINAL_STATUS: dict[TerminalOutcome, CaseStatus] = {
    TerminalOutcome.VERIFIED: CaseStatus.VERIFIED,
    TerminalOutcome.PARTIAL: CaseStatus.PARTIAL,
    TerminalOutcome.CLARIFICATION_REQUIRED: CaseStatus.CLARIFICATION_REQUIRED,
    TerminalOutcome.ESCALATED: CaseStatus.ESCALATED,
    TerminalOutcome.FAILED: CaseStatus.FAILED,
    TerminalOutcome.CANCELLED: CaseStatus.CANCELLED,
}


def shadow_tenant_id(tenant: str) -> UUID:
    """Map the runtime's string tenant onto the kernel's UUID tenant.

    The legacy runtime identifies tenants by name ("default", "acme"); the
    kernel's tables are keyed by UUID and enforce row-level security on it.
    Deterministic so that the same tenant is the same rows across restarts,
    and namespaced the same way the rest of the kernel derives ids.
    """
    if not tenant or tenant != tenant.strip():
        raise ValueError("tenant must be non-empty without surrounding whitespace")
    return uuid5(NAMESPACE_URL, f"rag-new:tenant:{tenant}")


def shadow_context(tenant: str) -> TenantContext:
    return TenantContext(
        tenant_id=shadow_tenant_id(tenant),
        actor_id=SHADOW_ACTOR_ID,
        scopes=SHADOW_SCOPES,
    )


def status_path(export: ShipmentEvidenceExport) -> tuple[CaseStatus, ...]:
    """The states this run passed through, each justified by the bundle.

    Not a guess: `source_observation` is present exactly when the journey
    reached the source, `policy` exactly when it reached the policy step, and
    a verified outcome is exactly when it compiled a response. The bundle
    records what happened, so the path can be read off it rather than invented.
    """
    terminal = _TERMINAL_STATUS[export.terminal_state]
    if terminal is CaseStatus.CLARIFICATION_REQUIRED:
        # The journey stopped before looking anything up — it could not tell
        # which shipment was meant.
        return (CaseStatus.ROUTED, terminal)
    path: list[CaseStatus] = [CaseStatus.ROUTED]
    if export.source_observation is not None:
        path.append(CaseStatus.EVIDENCE_GATHERING)
    if export.policy is not None:
        path.append(CaseStatus.POLICY_PENDING)
    if terminal in (CaseStatus.VERIFIED, CaseStatus.PARTIAL):
        path.append(CaseStatus.RESPONSE_COMPILING)
    path.append(terminal)
    return tuple(path)


def _reason_code(
    export: ShipmentEvidenceExport,
    status: CaseStatus,
    *,
    terminal: bool,
) -> str:
    """Only the terminal step carries the run's reason code.

    Stamping `EVIDENCE_STALE` onto the `routed` event as well would read as
    four separate findings instead of one, and the intermediate steps had no
    finding — they are simply where the journey went.
    """
    if terminal and export.reason_codes:
        return export.reason_codes[0]
    return f"SHADOW_{status.value.upper()}"


def case_mutations(
    export: ShipmentEvidenceExport,
    *,
    context: TenantContext,
    recorded_at: datetime,
) -> tuple[CaseMutation, ...]:
    """Open the case and step it to its terminal status.

    Each transition needs a strictly later `recorded_at` than the last, so the
    steps are spaced a microsecond apart off the run instant. That preserves
    the ordering without inventing durations the shadow never measured.
    """
    contract = ContractVersionRef(
        contract_id=export.contract.contract_id,
        version=export.contract.version,
        digest=export.contract.digest,
    )
    opened = SupportCase.open(
        case_id=export.case_id,
        tenant_id=context.tenant_id,
        contract=contract,
        correlation_id=export.correlation_id,
        event_id=_derived_id("case-event", export.case_id, "opened"),
        command_id=_derived_id("case-command", export.case_id, "opened"),
        actor_id=context.actor_id,
        occurred_at=recorded_at,
        recorded_at=recorded_at,
        effective_at=recorded_at,
    )
    mutations = [opened]
    case = opened.case
    path = status_path(export)
    for step, status in enumerate(path, start=1):
        moment = recorded_at + timedelta(microseconds=step)
        mutation = case.transition(
            to_status=status,
            expected_version=case.version,
            event_id=_derived_id("case-event", export.case_id, status.value),
            command_id=_derived_id("case-command", export.case_id, status.value),
            actor_id=context.actor_id,
            reason_code=_reason_code(export, status, terminal=step == len(path)),
            occurred_at=moment,
            recorded_at=moment,
        )
        mutations.append(mutation)
        case = mutation.case
    return tuple(mutations)


def _derived_id(kind: str, case_id: UUID, discriminator: str) -> UUID:
    """Deterministic ids so a replayed shadow writes the same rows, not new ones."""
    return uuid5(NAMESPACE_URL, f"rag-new:shadow-{kind}:{case_id}:{discriminator}")


def _reference(locator: str) -> ProtectedEvidenceReference:
    return ProtectedEvidenceReference(
        storage=EvidenceStorage.POSTGRES_ENCRYPTED,
        locator=locator,
        encryption_profile=EVIDENCE_ENCRYPTION_PROFILE,
        redaction_profile=SHADOW_REDACTION_PROFILE,
        retention_class=SHADOW_RETENTION_CLASS,
    )


def source_snapshot(
    observation: SourceObservationExport,
    *,
    tenant_id: UUID,
) -> EvidenceSnapshot:
    logical_key = f"shipment:{observation.shipment_id}:status"
    return EvidenceSnapshot(
        id=_evidence_id(tenant_id, logical_key, observation.content_digest),
        tenant_id=tenant_id,
        logical_key=logical_key,
        source_type=EvidenceSourceType.SOURCE_SYSTEM,
        source_id=observation.source_id,
        source_version=observation.source_version,
        content_digest=observation.content_digest,
        valid_range=TimeRange(start=observation.observed_at, end=None),
        recorded_at=observation.observed_at,
        # The authority is the system that reported it, which for the shadow
        # is the fixture TMS. It says so in its own id.
        authority=observation.source_id,
        applicability_key=f"shipment:{observation.shipment_id}",
        visibility=SHADOW_VISIBILITY,
        reference=_reference(f"evidence/{observation.shipment_id}/{observation.source_version}"),
    )


def policy_snapshot(
    policy: PolicyDecisionExport,
    *,
    tenant_id: UUID,
    shipment_id: str,
) -> EvidenceSnapshot:
    logical_key = f"shipment-policy:{shipment_id}:disclosure"
    return EvidenceSnapshot(
        id=_evidence_id(tenant_id, logical_key, policy.content_digest),
        tenant_id=tenant_id,
        logical_key=logical_key,
        source_type=EvidenceSourceType.KNOWLEDGE,
        source_id=policy.authority,
        source_version=policy.data_revision,
        content_digest=policy.content_digest,
        valid_range=TimeRange(start=policy.valid_from, end=policy.valid_to),
        recorded_at=policy.recorded_at,
        authority=policy.authority,
        applicability_key=f"shipment:{shipment_id}",
        visibility=SHADOW_VISIBILITY,
        reference=_reference(f"policy/{policy.authority}/{policy.data_revision}"),
    )


def _evidence_id(tenant_id: UUID, logical_key: str, content_digest: str) -> UUID:
    return uuid5(
        NAMESPACE_URL, f"rag-new:shadow-evidence:{tenant_id}:{logical_key}:{content_digest}"
    )


def evidence_for(
    export: ShipmentEvidenceExport,
    *,
    tenant_id: UUID,
) -> tuple[tuple[EvidenceSnapshot, str, EvidencePurpose], ...]:
    """Every snapshot the run gathered, with the requirement it satisfied."""
    gathered: list[tuple[EvidenceSnapshot, str, EvidencePurpose]] = []
    observation = export.source_observation
    if observation is not None:
        gathered.append(
            (
                source_snapshot(observation, tenant_id=tenant_id),
                SOURCE_REQUIREMENT_ID,
                EvidencePurpose.FACT,
            )
        )
    if export.policy is not None and observation is not None:
        gathered.append(
            (
                policy_snapshot(
                    export.policy,
                    tenant_id=tenant_id,
                    shipment_id=observation.shipment_id,
                ),
                POLICY_REQUIREMENT_ID,
                EvidencePurpose.POLICY,
            )
        )
    return tuple(gathered)


async def persist_shipment_shadow(
    session_factory: Any,
    export: ShipmentEvidenceExport,
    *,
    recorded_at: datetime | None = None,
) -> bool:
    """Write one shadow run's case and evidence. Returns False if already stored.

    Idempotent by construction: every id it writes is derived from the case,
    so a replay of the same correlation id finds the case already there and
    does nothing rather than opening a second one.
    """
    from resolution.adapters.postgres import PostgresResolutionUnitOfWork

    context = shadow_context(export.tenant_id)
    instant = recorded_at or datetime.now(UTC)
    mutations = case_mutations(export, context=context, recorded_at=instant)
    gathered = evidence_for(export, tenant_id=context.tenant_id)

    async with PostgresResolutionUnitOfWork(session_factory, context) as work:
        if await work.cases.get(context, export.case_id) is not None:
            logger.debug("shadow case %s already recorded, skipping", export.case_id)
            return False
        for mutation in mutations:
            await work.cases.append(context, mutation)
        case = mutations[-1].case
        for snapshot, requirement_id, purpose in gathered:
            if await work.evidence.get_snapshot(context, snapshot.id) is None:
                await work.evidence.append_snapshot(context, snapshot)
            await work.evidence.append_link(
                context,
                EvidenceLink.create(
                    link_id=_derived_id("evidence-link", export.case_id, requirement_id),
                    case=case,
                    evidence=snapshot,
                    requirement_id=requirement_id,
                    purpose=purpose,
                    gathered_at=snapshot.recorded_at,
                    freshness=FreshnessStatus.CURRENT,
                ),
            )
        await work.commit()
    return True


__all__ = [
    "POLICY_REQUIREMENT_ID",
    "SHADOW_ACTOR_ID",
    "SOURCE_REQUIREMENT_ID",
    "case_mutations",
    "evidence_for",
    "persist_shipment_shadow",
    "policy_snapshot",
    "shadow_context",
    "shadow_tenant_id",
    "source_snapshot",
    "status_path",
]
