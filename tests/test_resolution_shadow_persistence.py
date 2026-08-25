"""What a shadow run becomes when it is written down.

Phase A.1b. The trip through Postgres is exercised by
`tests/integration/test_resolution_shadow_postgres.py`; everything here is the
part that decides *what* gets written, which is where the claims live:

- the case walks a path the kernel's own transition graph accepts, and the
  path is the one the evidence bundle justifies rather than a convenient one;
- the reason code the run produced lands on the terminal event and nowhere
  else;
- evidence snapshots carry the source's and the policy's own time, not the
  instant the shadow happened to read them;
- every id is derived, so replaying a run rewrites the same rows instead of
  opening a second case for the same question.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

import pytest

from resolution.application.shipment_status import (
    ClaimEvidenceLink,
    ContractIdentity,
    PolicyDecisionExport,
    ShipmentEvidenceExport,
    SourceObservationExport,
)
from resolution.contracts import TerminalOutcome
from resolution.domain.cases import ALLOWED_CASE_TRANSITIONS, CaseStatus
from resolution.domain.evidence import EvidencePurpose, EvidenceVisibility
from resolution.persistence import (
    POLICY_REQUIREMENT_ID,
    SOURCE_REQUIREMENT_ID,
    case_mutations,
    evidence_for,
    shadow_context,
    shadow_tenant_id,
    status_path,
)

_NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
_CASE_ID = uuid5(NAMESPACE_URL, "rag-new:test:case")
_CORRELATION_ID = uuid5(NAMESPACE_URL, "rag-new:test:correlation")

_CONTRACT = ContractIdentity(
    schema_identity="resolution-contract/v0.1",
    contract_id="aircargo.shipment-status",
    version="0.1.0",
    digest="a" * 64,
)


def _observation() -> SourceObservationExport:
    return SourceObservationExport(
        shipment_id="SHP-100001",
        status="in_transit",
        location="FRA",
        estimated_delivery="2026-08-27",
        observed_at=_NOW - timedelta(minutes=5),
        source_id="fixture-tms",
        source_version="fixture-v1",
        content_digest="b" * 64,
    )


def _policy() -> PolicyDecisionExport:
    return PolicyDecisionExport(
        implementation_version="typed-shipment-policy/v0.1",
        data_revision="policy-rev-7",
        authority="support-policy",
        content_digest="c" * 64,
        decision="allow",
        recorded_at=_NOW - timedelta(hours=2),
        valid_from=_NOW - timedelta(days=1),
        valid_to=None,
    )


def _export(
    *,
    terminal_state: TerminalOutcome = TerminalOutcome.VERIFIED,
    reason_codes: tuple[str, ...] = (),
    with_observation: bool = True,
    with_policy: bool = True,
) -> ShipmentEvidenceExport:
    observation = _observation() if with_observation else None
    return ShipmentEvidenceExport(
        mode="shadow",
        tenant_id="acme",
        case_id=_CASE_ID,
        case_version=1,
        correlation_id=_CORRELATION_ID,
        terminal_state=terminal_state,
        reason_codes=reason_codes,
        contract=_CONTRACT,
        source_observation=observation,
        policy=_policy() if with_policy else None,
        claim_links=(
            ClaimEvidenceLink(
                claim_id="shipment-status",
                text="Shipment SHP-100001 status is in_transit.",
                evidence_requirement_ids=("shipment-observation", "shipment-policy"),
                evidence_digests=("b" * 64, "c" * 64),
            ),
        ),
        postcondition_versions=(),
        escalation_brief=None,
    )


# --- the tenant mapping ------------------------------------------------------


def test_the_string_tenant_maps_onto_a_stable_uuid() -> None:
    """The rows have to be the same rows after a restart."""
    assert shadow_tenant_id("acme") == shadow_tenant_id("acme")
    assert shadow_tenant_id("acme") != shadow_tenant_id("default")


@pytest.mark.parametrize("tenant", ["", " ", " acme"])
def test_a_malformed_tenant_is_refused(tenant: str) -> None:
    with pytest.raises(ValueError):
        shadow_tenant_id(tenant)


def test_the_shadow_writes_as_itself_and_not_as_the_asker() -> None:
    context = shadow_context("acme")
    assert context.tenant_id == shadow_tenant_id("acme")
    assert context.actor_id == shadow_context("default").actor_id


# --- the path the case walks -------------------------------------------------


@pytest.mark.parametrize(
    ("terminal_state", "with_observation", "with_policy", "expected"),
    [
        (
            TerminalOutcome.CLARIFICATION_REQUIRED,
            False,
            False,
            (CaseStatus.ROUTED, CaseStatus.CLARIFICATION_REQUIRED),
        ),
        (
            TerminalOutcome.ESCALATED,
            False,
            False,
            (CaseStatus.ROUTED, CaseStatus.ESCALATED),
        ),
        (
            TerminalOutcome.ESCALATED,
            True,
            False,
            (CaseStatus.ROUTED, CaseStatus.EVIDENCE_GATHERING, CaseStatus.ESCALATED),
        ),
        (
            TerminalOutcome.ESCALATED,
            True,
            True,
            (
                CaseStatus.ROUTED,
                CaseStatus.EVIDENCE_GATHERING,
                CaseStatus.POLICY_PENDING,
                CaseStatus.ESCALATED,
            ),
        ),
        (
            TerminalOutcome.VERIFIED,
            True,
            True,
            (
                CaseStatus.ROUTED,
                CaseStatus.EVIDENCE_GATHERING,
                CaseStatus.POLICY_PENDING,
                CaseStatus.RESPONSE_COMPILING,
                CaseStatus.VERIFIED,
            ),
        ),
    ],
)
def test_the_path_is_the_one_the_bundle_justifies(
    terminal_state: TerminalOutcome,
    with_observation: bool,
    with_policy: bool,
    expected: tuple[CaseStatus, ...],
) -> None:
    """A run that never reached the policy step never passed through policy_pending."""
    export = _export(
        terminal_state=terminal_state,
        with_observation=with_observation,
        with_policy=with_policy,
    )
    assert status_path(export) == expected


@pytest.mark.parametrize(
    ("terminal_state", "with_observation", "with_policy"),
    [
        (TerminalOutcome.CLARIFICATION_REQUIRED, False, False),
        (TerminalOutcome.ESCALATED, False, False),
        (TerminalOutcome.ESCALATED, True, False),
        (TerminalOutcome.ESCALATED, True, True),
        (TerminalOutcome.VERIFIED, True, True),
    ],
)
def test_every_path_is_legal_under_the_kernels_own_transition_graph(
    terminal_state: TerminalOutcome,
    with_observation: bool,
    with_policy: bool,
) -> None:
    """The graph is the authority; this asserts against it rather than restating it."""
    export = _export(
        terminal_state=terminal_state,
        with_observation=with_observation,
        with_policy=with_policy,
    )
    current = CaseStatus.RECEIVED
    for status in status_path(export):
        assert status in ALLOWED_CASE_TRANSITIONS[current], (
            f"'{current}' -> '{status}' is not an allowed case transition"
        )
        current = status


def test_the_case_opens_received_and_ends_where_the_run_ended() -> None:
    export = _export(terminal_state=TerminalOutcome.VERIFIED)
    mutations = case_mutations(export, context=shadow_context("acme"), recorded_at=_NOW)

    assert mutations[0].case.status is CaseStatus.RECEIVED
    assert mutations[0].expected_version is None
    assert mutations[-1].case.status is CaseStatus.VERIFIED
    assert mutations[-1].case.id == _CASE_ID
    assert mutations[-1].case.correlation_id == _CORRELATION_ID
    # One event per state, versions advancing by exactly one.
    assert [mutation.case.version for mutation in mutations] == list(range(1, len(mutations) + 1))
    assert [event.sequence for event in (m.event for m in mutations)] == list(
        range(1, len(mutations) + 1)
    )


def test_the_run_reason_code_lands_on_the_terminal_event_only() -> None:
    """`EVIDENCE_STALE` is one finding, not one per step the journey took."""
    export = _export(
        terminal_state=TerminalOutcome.ESCALATED,
        reason_codes=("EVIDENCE_STALE",),
    )
    mutations = case_mutations(export, context=shadow_context("acme"), recorded_at=_NOW)
    reason_codes = [mutation.event.reason_code for mutation in mutations]

    assert reason_codes[-1] == "EVIDENCE_STALE"
    assert "EVIDENCE_STALE" not in reason_codes[:-1]


def test_case_time_advances_strictly() -> None:
    """The kernel refuses a transition that does not move the clock forward."""
    export = _export()
    mutations = case_mutations(export, context=shadow_context("acme"), recorded_at=_NOW)
    stamps = [mutation.case.updated_at for mutation in mutations]
    assert stamps == sorted(stamps)
    assert len(set(stamps)) == len(stamps)


def test_replaying_a_run_produces_the_same_ids() -> None:
    """A retried request must rewrite its case, not open a second one."""
    export = _export()
    first = case_mutations(export, context=shadow_context("acme"), recorded_at=_NOW)
    second = case_mutations(
        export, context=shadow_context("acme"), recorded_at=_NOW + timedelta(hours=3)
    )
    assert [m.event.id for m in first] == [m.event.id for m in second]


# --- the evidence ------------------------------------------------------------


def test_both_requirements_are_recorded_with_their_purposes() -> None:
    tenant_id = shadow_tenant_id("acme")
    gathered = evidence_for(_export(), tenant_id=tenant_id)

    assert [item[1] for item in gathered] == [SOURCE_REQUIREMENT_ID, POLICY_REQUIREMENT_ID]
    assert [item[2] for item in gathered] == [EvidencePurpose.FACT, EvidencePurpose.POLICY]


def test_snapshots_carry_the_evidence_own_time_not_the_run_instant() -> None:
    """A policy stamped with the moment it was read claims it became true then."""
    tenant_id = shadow_tenant_id("acme")
    observation, policy = (item[0] for item in evidence_for(_export(), tenant_id=tenant_id))

    assert observation.recorded_at == _observation().observed_at
    assert observation.valid_range.start == _observation().observed_at
    assert policy.recorded_at == _policy().recorded_at
    assert policy.valid_range.start == _policy().valid_from
    assert policy.valid_range.end is None


def test_snapshots_are_support_only() -> None:
    """Disclosure is a decision about the answer, not a property of the row."""
    tenant_id = shadow_tenant_id("acme")
    for snapshot, _, _ in evidence_for(_export(), tenant_id=tenant_id):
        assert snapshot.visibility is EvidenceVisibility.SUPPORT_ONLY


def test_snapshot_identity_follows_content() -> None:
    """Same observation, same row; changed content, a different one."""
    tenant_id = shadow_tenant_id("acme")
    first = evidence_for(_export(), tenant_id=tenant_id)[0][0]
    again = evidence_for(_export(), tenant_id=tenant_id)[0][0]
    assert first.id == again.id

    changed = _export()
    moved = SourceObservationExport(
        **{**vars_of(changed.source_observation), "content_digest": "d" * 64}
    )
    other = evidence_for(
        _replace_observation(changed, moved),
        tenant_id=tenant_id,
    )[0][0]
    assert other.id != first.id


def test_a_run_that_never_reached_the_source_records_no_evidence() -> None:
    gathered = evidence_for(
        _export(
            terminal_state=TerminalOutcome.CLARIFICATION_REQUIRED,
            with_observation=False,
            with_policy=False,
        ),
        tenant_id=shadow_tenant_id("acme"),
    )
    assert gathered == ()


def vars_of(observation: SourceObservationExport | None) -> dict[str, object]:
    assert observation is not None
    return {
        "shipment_id": observation.shipment_id,
        "status": observation.status,
        "location": observation.location,
        "estimated_delivery": observation.estimated_delivery,
        "observed_at": observation.observed_at,
        "source_id": observation.source_id,
        "source_version": observation.source_version,
        "content_digest": observation.content_digest,
    }


def _replace_observation(
    export: ShipmentEvidenceExport,
    observation: SourceObservationExport,
) -> ShipmentEvidenceExport:
    return ShipmentEvidenceExport(
        mode=export.mode,
        tenant_id=export.tenant_id,
        case_id=export.case_id,
        case_version=export.case_version,
        correlation_id=export.correlation_id,
        terminal_state=export.terminal_state,
        reason_codes=export.reason_codes,
        contract=export.contract,
        source_observation=observation,
        policy=export.policy,
        claim_links=export.claim_links,
        postcondition_versions=export.postcondition_versions,
        escalation_brief=export.escalation_brief,
    )
