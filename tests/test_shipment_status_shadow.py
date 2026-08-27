from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from knowledge.application import (
    APPROVED_KNOWLEDGE_SOURCE_ID,
    KnowledgeRetrievalAllowlist,
)
from resolution.adapters.shipment_status import (
    FixtureShipmentSource,
    LegacyRetrievalPolicyAdapter,
    ShipmentFixture,
)
from resolution.application.shipment_status import (
    ClaimCandidate,
    ShipmentShadowRequest,
    ShipmentStatusShadowLoop,
    run_legacy_ask_shadow,
)
from resolution.contracts import ResolutionContract, TerminalOutcome

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
TENANT = "tenant-a"
OTHER_TENANT = "tenant-b"
CASE_ID = UUID("10000000-0000-0000-0000-000000000001")
CORRELATION_ID = UUID("20000000-0000-0000-0000-000000000001")
CONTRACT_DIGEST = "5d4d069f317df0c18f9e132b6fdbf9649bd6136808b2dc14507a0f2b10c99e38"


class _Retriever:
    def __init__(self, documents: tuple[dict[str, object], ...]) -> None:
        self.documents = documents
        self.queries: list[str] = []

    def get_relevant_documents(self, query: str) -> list[dict[str, object]]:
        self.queries.append(query)
        return list(self.documents)


def _contract() -> ResolutionContract:
    path = (
        Path(__file__).parent
        / "fixtures"
        / "resolution_contracts"
        / "v0.1"
        / "valid"
        / "shipment-status.json"
    )
    return ResolutionContract.model_validate_json(path.read_text(encoding="utf-8"))


def _policy_document(
    *,
    tenant_id: str = TENANT,
    allowed: bool = True,
    revision: str = "policy-2026.09-r1",
    recorded_at: datetime = NOW - timedelta(minutes=5),
    digest: str = "c" * 64,
) -> dict[str, object]:
    return {
        "page_content": "Shipment status disclosure policy fixture.",
        "metadata": {
            "tenant_id": tenant_id,
            "authority": "logistics-policy-primary",
            "policy_revision": revision,
            "recorded_at": recorded_at.isoformat(),
            "valid_from": (NOW - timedelta(days=30)).isoformat(),
            "valid_to": (NOW + timedelta(days=30)).isoformat(),
            "status_disclosure_allowed": allowed,
            "content_digest": digest,
        },
    }


@dataclass(frozen=True)
class Scenario:
    name: str
    mode: str
    messages: tuple[str, ...]
    expected: TerminalOutcome
    expected_reason: str | None = None


SCENARIOS = (
    Scenario("happy-single", "happy", ("Status SHP-100?",), TerminalOutcome.VERIFIED),
    Scenario(
        "happy-two-turn",
        "happy",
        ("Where is my cargo?", "The shipment is SHP-100"),
        TerminalOutcome.VERIFIED,
    ),
    Scenario(
        "happy-three-turn",
        "happy",
        ("Hello", "I need an update", "SHP-100"),
        TerminalOutcome.VERIFIED,
    ),
    Scenario("happy-lowercase", "happy", ("status shp-100",), TerminalOutcome.VERIFIED),
    Scenario("happy-surrounded", "happy", ("(SHP-100), please",), TerminalOutcome.VERIFIED),
    Scenario(
        "happy-repeat",
        "happy",
        ("SHP-100", "Any change for SHP-100?"),
        TerminalOutcome.VERIFIED,
    ),
    Scenario(
        "missing-empty-context",
        "missing",
        ("Where is my shipment?",),
        TerminalOutcome.CLARIFICATION_REQUIRED,
        "SHIPMENT_ID_REQUIRED",
    ),
    Scenario(
        "declined-two-turn",
        "missing",
        ("Hello", "Please check it"),
        TerminalOutcome.CANCELLED,
        "NOT_IN_JOURNEY",
    ),
    Scenario(
        "missing-partial-token",
        "missing",
        ("Shipment SHP-",),
        TerminalOutcome.CLARIFICATION_REQUIRED,
        "SHIPMENT_ID_REQUIRED",
    ),
    Scenario(
        "declined-whitespace",
        "missing",
        ("   ",),
        TerminalOutcome.CANCELLED,
        "NOT_IN_JOURNEY",
    ),
    Scenario(
        "unknown-single",
        "unknown",
        ("SHP-404",),
        TerminalOutcome.ESCALATED,
        "SOURCE_UNAVAILABLE",
    ),
    Scenario(
        "unknown-follow-up",
        "unknown",
        ("Please locate this", "SHP-404"),
        TerminalOutcome.ESCALATED,
        "SOURCE_UNAVAILABLE",
    ),
    Scenario(
        "unknown-newest-id",
        "unknown",
        ("SHP-100", "Correction: SHP-404"),
        TerminalOutcome.ESCALATED,
        "SOURCE_UNAVAILABLE",
    ),
    Scenario(
        "stale-source-boundary",
        "stale_source",
        ("SHP-100",),
        TerminalOutcome.ESCALATED,
        "EVIDENCE_STALE",
    ),
    Scenario(
        "stale-source-follow-up",
        "stale_source",
        ("Check cargo", "SHP-100"),
        TerminalOutcome.ESCALATED,
        "EVIDENCE_STALE",
    ),
    Scenario(
        "stale-source-repeat",
        "stale_source",
        ("SHP-100", "SHP-100"),
        TerminalOutcome.ESCALATED,
        "EVIDENCE_STALE",
    ),
    Scenario(
        "policy-conflict-two-docs",
        "policy_conflict",
        ("SHP-100",),
        TerminalOutcome.ESCALATED,
        "EVIDENCE_CONFLICT",
    ),
    Scenario(
        "policy-conflict-follow-up",
        "policy_conflict",
        ("Need status", "SHP-100"),
        TerminalOutcome.ESCALATED,
        "EVIDENCE_CONFLICT",
    ),
    Scenario(
        "policy-conflict-repeat",
        "policy_conflict",
        ("SHP-100", "Please retry"),
        TerminalOutcome.ESCALATED,
        "EVIDENCE_CONFLICT",
    ),
    Scenario(
        "wrong-tenant-single",
        "wrong_tenant",
        ("SHP-100",),
        TerminalOutcome.ESCALATED,
        "SOURCE_UNAVAILABLE",
    ),
    Scenario(
        "wrong-tenant-follow-up",
        "wrong_tenant",
        ("Find it", "SHP-100"),
        TerminalOutcome.ESCALATED,
        "SOURCE_UNAVAILABLE",
    ),
    Scenario(
        "wrong-tenant-repeat",
        "wrong_tenant",
        ("SHP-100", "Status again"),
        TerminalOutcome.ESCALATED,
        "SOURCE_UNAVAILABLE",
    ),
    Scenario(
        "provider-timeout-single",
        "timeout",
        ("SHP-TIMEOUT",),
        TerminalOutcome.ESCALATED,
        "SOURCE_UNAVAILABLE",
    ),
    Scenario(
        "provider-timeout-follow-up",
        "timeout",
        ("Check", "SHP-TIMEOUT"),
        TerminalOutcome.ESCALATED,
        "SOURCE_UNAVAILABLE",
    ),
    Scenario(
        "retrieval-empty-single",
        "retrieval_empty",
        ("SHP-100",),
        TerminalOutcome.ESCALATED,
        "SOURCE_UNAVAILABLE",
    ),
    Scenario(
        "retrieval-empty-follow-up",
        "retrieval_empty",
        ("Need status", "SHP-100"),
        TerminalOutcome.ESCALATED,
        "SOURCE_UNAVAILABLE",
    ),
    Scenario(
        "unsupported-claim-single",
        "unsupported_claim",
        ("SHP-100",),
        TerminalOutcome.ESCALATED,
        "UNSUPPORTED_CLAIM",
    ),
    Scenario(
        "unsupported-claim-follow-up",
        "unsupported_claim",
        ("Check", "SHP-100"),
        TerminalOutcome.ESCALATED,
        "UNSUPPORTED_CLAIM",
    ),
    Scenario(
        "policy-denied",
        "policy_denied",
        ("SHP-100",),
        TerminalOutcome.ESCALATED,
        "POLICY_DENIED",
    ),
    Scenario(
        "stale-policy",
        "stale_policy",
        ("SHP-100",),
        TerminalOutcome.ESCALATED,
        "EVIDENCE_STALE",
    ),
)


def _loop_for(scenario: Scenario) -> ShipmentStatusShadowLoop:
    observed_at = NOW - timedelta(minutes=1)
    fixture_tenant = TENANT
    timeout_ids: frozenset[str] = frozenset()
    documents: tuple[dict[str, object], ...] = (_policy_document(),)
    if scenario.mode == "stale_source":
        observed_at = NOW - timedelta(seconds=301)
    elif scenario.mode == "wrong_tenant":
        fixture_tenant = OTHER_TENANT
    elif scenario.mode == "timeout":
        timeout_ids = frozenset({"SHP-TIMEOUT"})
    elif scenario.mode == "retrieval_empty":
        documents = ()
    elif scenario.mode == "policy_conflict":
        documents = (
            _policy_document(digest="c" * 64, allowed=True),
            _policy_document(digest="d" * 64, allowed=False, revision="policy-2026.09-r2"),
        )
    elif scenario.mode == "policy_denied":
        documents = (_policy_document(allowed=False),)
    elif scenario.mode == "stale_policy":
        documents = (_policy_document(recorded_at=NOW - timedelta(seconds=86401)),)

    source = FixtureShipmentSource(
        fixtures=(
            ShipmentFixture(
                tenant_id=fixture_tenant,
                shipment_id="SHP-100",
                status="in_transit",
                location="Toronto",
                estimated_delivery="2026-09-03",
                observed_at=observed_at,
                source_version="fixture-2026.09-r1",
            ),
        ),
        timeout_shipment_ids=timeout_ids,
    )
    policy = LegacyRetrievalPolicyAdapter(_Retriever(documents))
    return ShipmentStatusShadowLoop(contract=_contract(), source=source, policy=policy)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.name)
def test_deterministic_shipment_status_scenarios_have_explicit_terminal_state(
    scenario: Scenario,
) -> None:
    candidates = ()
    if scenario.mode == "unsupported_claim":
        candidates = (
            ClaimCandidate(
                claim_id="insurance",
                text="The shipment is fully insured.",
                evidence_requirement_ids=(),
            ),
        )
    result = _loop_for(scenario).run(
        ShipmentShadowRequest(
            tenant_id=TENANT,
            case_id=CASE_ID,
            correlation_id=CORRELATION_ID,
            messages=scenario.messages,
            effective_at=NOW,
            observed_at=NOW,
            candidate_claims=candidates,
        )
    )

    assert result.terminal_state is scenario.expected
    assert result.evidence_export.terminal_state is scenario.expected
    assert result.evidence_export.case_id == CASE_ID
    assert result.evidence_export.case_version >= 1
    if scenario.expected_reason is not None:
        assert scenario.expected_reason in result.reason_codes


def test_verified_export_pins_all_required_identities_and_claim_links() -> None:
    result = _loop_for(SCENARIOS[0]).run(
        ShipmentShadowRequest(
            tenant_id=TENANT,
            case_id=CASE_ID,
            correlation_id=CORRELATION_ID,
            messages=("SHP-100",),
            effective_at=NOW,
            observed_at=NOW,
        )
    )
    export = result.evidence_export

    assert result.terminal_state is TerminalOutcome.VERIFIED
    assert export.contract.schema_identity == "resolution-contract/v0.1"
    assert export.contract.contract_id == "aircargo.shipment-status"
    assert export.contract.version == "0.1.0"
    assert export.contract.digest == CONTRACT_DIGEST
    assert export.source_observation is not None
    assert export.source_observation.source_version == "fixture-2026.09-r1"
    assert export.policy is not None
    assert export.policy.implementation_version == "typed-shipment-policy/v0.1"
    assert export.policy.data_revision == "policy-2026.09-r1"
    assert export.claim_links
    assert all(link.evidence_digests for link in export.claim_links)
    assert export.postcondition_versions
    assert export.postcondition_versions[0].version == "0.1.0"
    assert export.escalation_brief is None
    json.dumps(export.as_dict(), sort_keys=True)


def test_escalation_export_contains_complete_contract_handoff_brief() -> None:
    scenario = next(item for item in SCENARIOS if item.mode == "timeout")
    export = (
        _loop_for(scenario)
        .run(
            ShipmentShadowRequest(
                tenant_id=TENANT,
                case_id=CASE_ID,
                correlation_id=CORRELATION_ID,
                messages=scenario.messages,
                effective_at=NOW,
                observed_at=NOW,
            )
        )
        .evidence_export
    )

    assert export.escalation_brief is not None
    assert set(export.escalation_brief.as_dict()) == {
        "case_id",
        "contract_version",
        "evidence_summary",
        "reason_codes",
    }
    assert export.escalation_brief.reason_codes == ("SOURCE_UNAVAILABLE",)


def test_fixture_source_and_retrieval_adapter_do_not_cross_tenant_boundary() -> None:
    source = FixtureShipmentSource(
        fixtures=(
            ShipmentFixture(
                tenant_id=OTHER_TENANT,
                shipment_id="SHP-100",
                status="delivered",
                location="Montreal",
                estimated_delivery="2026-09-01",
                observed_at=NOW,
                source_version="fixture-private",
            ),
        )
    )
    retriever = _Retriever((_policy_document(tenant_id=OTHER_TENANT),))
    policy = LegacyRetrievalPolicyAdapter(retriever)

    assert source.lookup(tenant_id=TENANT, shipment_id="SHP-100", timeout_seconds=5) is None
    assert policy.gather(tenant_id=TENANT, shipment_id="SHP-100", effective_at=NOW) == ()


def test_retrieval_adapter_applies_projection_version_allowlist_before_policy_mapping() -> None:
    tenant_id = UUID("90000000-0000-0000-0000-000000000001")
    allowed_version_id = UUID("91000000-0000-0000-0000-000000000001")
    projection_digest = "e" * 64
    allowlist = KnowledgeRetrievalAllowlist(
        tenant_id=tenant_id,
        active_collection="rag_docs_policy_v1",
        manifest_generation=1,
        projection_digest=projection_digest,
        knowledge_source_id=APPROVED_KNOWLEDGE_SOURCE_ID,
        versions=((allowed_version_id, "c" * 64),),
    )
    allowed = _policy_document(tenant_id=str(tenant_id), digest="c" * 64)
    allowed_metadata = allowed["metadata"]
    assert isinstance(allowed_metadata, dict)
    allowed_metadata.update(
        {
            "knowledge_version_id": str(allowed_version_id),
            "knowledge_content_digest": "c" * 64,
            "knowledge_projection_digest": projection_digest,
            "knowledge_source_id": APPROVED_KNOWLEDGE_SOURCE_ID,
        }
    )
    stale = _policy_document(
        tenant_id=str(tenant_id),
        digest="d" * 64,
        revision="policy-stale",
    )
    stale_metadata = stale["metadata"]
    assert isinstance(stale_metadata, dict)
    stale_metadata.update(
        {
            "knowledge_version_id": str(UUID("91000000-0000-0000-0000-000000000002")),
            "knowledge_content_digest": "d" * 64,
            "knowledge_projection_digest": projection_digest,
            "knowledge_source_id": APPROVED_KNOWLEDGE_SOURCE_ID,
        }
    )
    policy = LegacyRetrievalPolicyAdapter(
        _Retriever((stale, allowed)),
        knowledge_allowlist=allowlist,
    )

    evidence = policy.gather(
        tenant_id=str(tenant_id),
        shipment_id="SHP-100",
        effective_at=NOW,
    )

    assert len(evidence) == 1
    assert evidence[0].data_revision == "policy-2026.09-r1"
    assert evidence[0].content_digest == "c" * 64


def test_retrieval_allowlist_bounds_raw_candidates_and_denies_tenant_before_lookup() -> None:
    tenant_id = UUID("90000000-0000-0000-0000-000000000001")
    allowed_version_id = UUID("91000000-0000-0000-0000-000000000001")
    allowlist = KnowledgeRetrievalAllowlist(
        tenant_id=tenant_id,
        active_collection="rag_docs_policy_v1",
        manifest_generation=1,
        projection_digest="e" * 64,
        knowledge_source_id=APPROVED_KNOWLEDGE_SOURCE_ID,
        versions=((allowed_version_id, "c" * 64),),
    )

    class _BoundedRetriever:
        calls = 0

        def get_relevant_documents(self, _query: str):
            self.calls += 1

            def _documents():
                yield _policy_document(tenant_id=str(tenant_id), digest="d" * 64)
                raise AssertionError("adapter consumed beyond max_candidates")

            return _documents()

    retriever = _BoundedRetriever()
    policy = LegacyRetrievalPolicyAdapter(
        retriever,
        max_candidates=1,
        knowledge_allowlist=allowlist,
    )

    assert (
        policy.gather(
            tenant_id=str(tenant_id),
            shipment_id="SHP-100",
            effective_at=NOW,
        )
        == ()
    )
    assert retriever.calls == 1
    assert (
        policy.gather(
            tenant_id=str(UUID("90000000-0000-0000-0000-000000000002")),
            shipment_id="SHP-100",
            effective_at=NOW,
        )
        == ()
    )
    assert retriever.calls == 1


def test_legacy_ask_shadow_hook_returns_the_exact_response_and_swallows_failure() -> None:
    response = object()

    def _failing_observer(_request: ShipmentShadowRequest) -> None:
        raise RuntimeError("fixture observer failed")

    returned = run_legacy_ask_shadow(
        response=response,
        tenant_id=TENANT,
        session_id="session-1",
        correlation_id="trace-1",
        question="SHP-100",
        observer=_failing_observer,
    )

    assert returned is response


def test_contract_binding_rejects_unpinned_contract_identity() -> None:
    payload = _contract().model_dump(mode="json", by_alias=True)
    payload["version"] = "0.1.1"
    contract = ResolutionContract.model_validate(payload)
    source = FixtureShipmentSource(fixtures=())
    policy = LegacyRetrievalPolicyAdapter(_Retriever(()))

    with pytest.raises(ValueError, match="pinned shipment-status contract"):
        ShipmentStatusShadowLoop(contract=contract, source=source, policy=policy)
