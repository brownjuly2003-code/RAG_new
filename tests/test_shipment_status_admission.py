from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from resolution.application.shipment_status import (
    ShipmentShadowRequest,
    ShipmentStatusShadowLoop,
)
from resolution.composition import build_shipment_status_observer, load_shipment_contract
from resolution.contracts import TerminalOutcome

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
TENANT = "tenant-a"
CASE_ID = UUID("10000000-0000-0000-0000-000000000001")
CORRELATION_ID = UUID("20000000-0000-0000-0000-000000000001")


class _NeverCalledSource:
    def lookup(self, **_kwargs: object) -> None:
        raise AssertionError("a declined request must not look up a shipment")


class _NeverCalledPolicy:
    def gather(self, **_kwargs: object) -> tuple[object, ...]:
        raise AssertionError("a declined request must not gather a policy")


class _NeverCalledRetriever:
    def get_relevant_documents(self, _query: str) -> list[object]:
        raise AssertionError("a declined request must not retrieve policy evidence")


def _request(*messages: str) -> ShipmentShadowRequest:
    return ShipmentShadowRequest(
        tenant_id=TENANT,
        case_id=CASE_ID,
        correlation_id=CORRELATION_ID,
        messages=messages,
        effective_at=NOW,
        observed_at=NOW,
    )


def _loop() -> ShipmentStatusShadowLoop:
    return ShipmentStatusShadowLoop(
        contract=load_shipment_contract(),
        source=_NeverCalledSource(),
        policy=_NeverCalledPolicy(),
    )


def test_non_shipment_request_is_declined_and_the_observer_records_nothing() -> None:
    request = _request("What time does the warehouse close?")
    result = _loop().run(request)
    recorded = []
    observer = build_shipment_status_observer(
        retriever=_NeverCalledRetriever(),
        sink=recorded.append,
    )

    assert result.terminal_state is TerminalOutcome.CANCELLED
    assert result.reason_codes == ("NOT_IN_JOURNEY",)
    assert observer(request) is None
    assert recorded == []


def test_shipment_status_request_without_reference_still_requires_an_id() -> None:
    result = _loop().run(_request("What is the shipment status?"))

    assert result.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert result.reason_codes == ("SHIPMENT_ID_REQUIRED",)


@pytest.mark.parametrize(
    "question",
    (
        "My cargo is being held at the airport.",
        "Where are my shipments?",
        "Is my shipment delayed?",
    ),
)
def test_inflected_shipment_status_requests_without_reference_require_an_id(
    question: str,
) -> None:
    result = _loop().run(_request(question))

    assert result.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert result.reason_codes == ("SHIPMENT_ID_REQUIRED",)


@pytest.mark.parametrize(
    "question",
    (
        "Which shipment tracker should I buy?",
        "Was my email delivered?",
        "How do I create an air waybill?",
    ),
)
def test_non_status_lookalikes_are_declined(question: str) -> None:
    result = _loop().run(_request(question))

    assert result.terminal_state is TerminalOutcome.CANCELLED
    assert result.reason_codes == ("NOT_IN_JOURNEY",)


def test_shipment_specific_phrase_cannot_cross_message_boundaries() -> None:
    result = _loop().run(_request("I have a question about customs", "Hold on while I find it."))

    assert result.terminal_state is TerminalOutcome.CANCELLED
    assert result.reason_codes == ("NOT_IN_JOURNEY",)


@pytest.mark.parametrize(
    "question",
    (
        "How do I create an air waybill?",
        "What customs documents does my cargo need?",
        "What is the status of my refund?",
        "Which location is open?",
        "Was my email delivered?",
        "I need to book a shipment",
        "What are the lithium battery rules?",
    ),
)
def test_non_status_requests_with_generic_admission_terms_are_declined(question: str) -> None:
    result = _loop().run(_request(question))

    assert result.terminal_state is TerminalOutcome.CANCELLED
    assert result.reason_codes == ("NOT_IN_JOURNEY",)


@pytest.mark.parametrize(
    "question",
    (
        "Has my shipment been delayed?",
        "Where is my shipment?",
        "What is the shipment status?",
        "My cargo is stuck in customs hold",
        "Shipment SHP-",
    ),
)
def test_in_journey_request_without_reference_requires_an_id(question: str) -> None:
    result = _loop().run(_request(question))

    assert ShipmentStatusShadowLoop._is_admitted((question,)) is True
    assert result.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert result.reason_codes == ("SHIPMENT_ID_REQUIRED",)


@pytest.mark.parametrize(
    ("question", "terminal_state", "reason_code"),
    (
        (
            "What are the statuses of my shipments?",
            TerminalOutcome.CLARIFICATION_REQUIRED,
            "SHIPMENT_ID_REQUIRED",
        ),
        (
            "Which locations has my cargo passed?",
            TerminalOutcome.CLARIFICATION_REQUIRED,
            "SHIPMENT_ID_REQUIRED",
        ),
        (
            "What are the etas for my shipments?",
            TerminalOutcome.CLARIFICATION_REQUIRED,
            "SHIPMENT_ID_REQUIRED",
        ),
        (
            "Can I bring my bicycle on the bus while in transit?",
            TerminalOutcome.CANCELLED,
            "NOT_IN_JOURNEY",
        ),
        (
            "What is the estimated delivery time for my pizza?",
            TerminalOutcome.CANCELLED,
            "NOT_IN_JOURNEY",
        ),
        (
            "Which shipment tracker should I buy?",
            TerminalOutcome.CANCELLED,
            "NOT_IN_JOURNEY",
        ),
        (
            "What is the shipment deliverable?",
            TerminalOutcome.CANCELLED,
            "NOT_IN_JOURNEY",
        ),
        (
            "My cargo is being held at the airport.",
            TerminalOutcome.CLARIFICATION_REQUIRED,
            "SHIPMENT_ID_REQUIRED",
        ),
        (
            "Is my cargo still in transit?",
            TerminalOutcome.CLARIFICATION_REQUIRED,
            "SHIPMENT_ID_REQUIRED",
        ),
    ),
)
def test_admission_lexical_regressions(
    question: str,
    terminal_state: TerminalOutcome,
    reason_code: str,
) -> None:
    result = _loop().run(_request(question))

    assert result.terminal_state is terminal_state
    assert result.reason_codes == (reason_code,)
