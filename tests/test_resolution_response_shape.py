from __future__ import annotations

import copy
from dataclasses import replace
from datetime import timedelta

import pytest
from pydantic import ValidationError

from resolution.adapters.shipment_status import (
    FixtureShipmentSource,
    LegacyRetrievalPolicyAdapter,
    ShipmentFixture,
)
from resolution.application.shipment_status import (
    ClaimCandidate,
    ShipmentShadowRequest,
    ShipmentStatusShadowLoop,
)
from resolution.contracts import ResolutionContract, TerminalOutcome
from tests.test_shipment_status_shadow import (
    CASE_ID,
    CORRELATION_ID,
    NOW,
    TENANT,
    _policy_document,
    _Retriever,
)


def _run(candidates=()):
    from resolution.composition import load_shipment_response_contract

    loop = ShipmentStatusShadowLoop(
        contract=load_shipment_response_contract(),
        source=FixtureShipmentSource(fixtures=(ShipmentFixture(
            tenant_id=TENANT, shipment_id="SHP-100", status="in_transit",
            location="Toronto", estimated_delivery="2026-09-03",
            observed_at=NOW - timedelta(seconds=30), source_version="fixture-c3",
        ),)),
        policy=LegacyRetrievalPolicyAdapter(_Retriever((_policy_document(),))),
    )
    return loop.run(ShipmentShadowRequest(
        tenant_id=TENANT, case_id=CASE_ID, correlation_id=CORRELATION_ID,
        messages=("Status SHP-100?",), effective_at=NOW, observed_at=NOW,
        candidate_claims=candidates,
    ))


@pytest.mark.parametrize("raw,expected", [
    ("", ()), (" shipment-status , shipment-status ", ("shipment-status",)),
])
def test_response_allowlist_is_explicit(monkeypatch, raw, expected):
    from config.settings import Settings

    monkeypatch.setenv("RESOLUTION_RESPONSE_JOURNEYS", raw)
    assert Settings().resolution_response_journeys == expected


def test_response_allowlist_rejects_typo(monkeypatch):
    from config.settings import Settings

    monkeypatch.setenv("RESOLUTION_RESPONSE_JOURNEYS", "shipment_status")
    with pytest.raises(ValueError, match="unknown journeys"):
        Settings()


@pytest.mark.parametrize("mutation", ["duplicate", "mapping", "evidence", "empty", "version"])
def test_response_shape_rejects_invalid_bindings(mutation):
    from resolution.composition import load_shipment_response_contract

    payload = load_shipment_response_contract().model_dump(mode="json")
    shape = payload["response_shape"]
    if mutation == "duplicate":
        shape["fields"][1] = copy.deepcopy(shape["fields"][0])
    elif mutation == "mapping":
        shape["fields"][0]["claim_id"] = "estimated-delivery"
    elif mutation == "evidence":
        shape["fields"][0]["evidence_requirement_ids"] = ["unknown"]
    elif mutation == "empty":
        shape["fields"] = []
    else:
        shape["version"] = "9.0.0"
    with pytest.raises(ValidationError):
        ResolutionContract.model_validate(payload)


def test_response_shape_removes_unsupported_candidates_and_preserves_evidence():
    valid = ClaimCandidate("shipment-status", "Shipment SHP-100 status is in_transit.",
                           ("shipment-observation", "shipment-policy"))
    invented = ClaimCandidate("insurance", "Fully insured.", ())
    forged = ClaimCandidate("shipment-location", "Last reported location is Mars.",
                            ("shipment-observation", "shipment-policy"))
    result = _run((invented, forged, valid))
    assert result.terminal_state is TerminalOutcome.VERIFIED
    assert result.response_text == "Fixture TMS. AI assistance. " + valid.text
    export = result.evidence_export
    assert [link.claim_id for link in export.claim_links] == [valid.claim_id]
    assert export.claim_links[0].evidence_digests == (
        export.source_observation.content_digest, export.policy.content_digest,
    )


def test_no_supported_fields_cannot_be_verified():
    result = _run((ClaimCandidate("insurance", "Fully insured.", ()),))
    assert result.terminal_state is TerminalOutcome.ESCALATED
    assert result.reason_codes == ("UNSUPPORTED_CLAIM",)
    assert result.evidence_export.claim_links == ()


@pytest.mark.parametrize("tamper", ["text", "digest", "contract", "policy", "terminal"])
def test_projection_rejects_tampered_evidence(tamper):
    from api.routers.conversation import AskResponse, _project_resolution_response

    result = _run()
    export = result.evidence_export
    if tamper in {"text", "digest"}:
        link = export.claim_links[0]
        link = (replace(link, text="Fully insured.") if tamper == "text"
                else replace(link, evidence_digests=("0" * 64, "1" * 64)))
        export = replace(export, claim_links=(link, *export.claim_links[1:]))
    elif tamper == "contract":
        export = replace(export, contract=replace(export.contract, digest="0" * 64))
    elif tamper == "policy":
        export = replace(export, policy=replace(export.policy, decision="deny"))
    else:
        export = replace(export, terminal_state=TerminalOutcome.ESCALATED)
    result = replace(result, evidence_export=export)
    legacy = AskResponse(answer="legacy")
    assert _project_resolution_response(
        response=legacy, results=[result], journeys=("shipment-status",),
    ) is legacy


def test_projection_renders_evidence_instead_of_arbitrary_response_text():
    from api.routers.conversation import AskResponse, _project_resolution_response

    result = replace(_run(), response_text="Fully insured.")
    response = _project_resolution_response(
        response=AskResponse(answer="legacy"), results=[result], journeys=("shipment-status",),
    )
    assert response.route == "verified"
    assert "Fully insured" not in response.answer
    assert response.answer.startswith("Fixture TMS. AI assistance. Shipment SHP-100")
