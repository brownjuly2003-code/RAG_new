from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from resolution.application.shipment_status import (
    _SHIPMENT_STATUS_ADMISSION_VOCABULARY,
    _SHIPMENT_STATUS_RUSSIAN_ADMISSION_VOCABULARY,
    RussianAdmissionTranslation,
    ShipmentShadowRequest,
    ShipmentStatusShadowLoop,
)
from resolution.composition import load_shipment_contract
from resolution.contracts import TerminalOutcome

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
TENANT = "tenant-a"
CASE_ID = UUID("10000000-0000-0000-0000-000000000001")
CORRELATION_ID = UUID("20000000-0000-0000-0000-000000000001")

_ENGLISH_DOMAIN_NOUNS = _SHIPMENT_STATUS_ADMISSION_VOCABULARY["domain_nouns"]
_ENGLISH_STATUS_CUES = _SHIPMENT_STATUS_ADMISSION_VOCABULARY["status_cues"]
_RUSSIAN_DOMAIN_NOUNS = _SHIPMENT_STATUS_RUSSIAN_ADMISSION_VOCABULARY["domain_nouns"]
_RUSSIAN_STATUS_CUES = _SHIPMENT_STATUS_RUSSIAN_ADMISSION_VOCABULARY["status_cues"]
_PARTNER_NOUN = _RUSSIAN_DOMAIN_NOUNS["cargo"].citation
_PARTNER_CUE = _RUSSIAN_STATUS_CUES["status"].citation


class _NeverCalledSource:
    def lookup(self, **_kwargs: object) -> None:
        raise AssertionError("a declined request must not look up a shipment")


class _NeverCalledPolicy:
    def gather(self, **_kwargs: object) -> tuple[object, ...]:
        raise AssertionError("a declined request must not gather a policy")


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


def _paired_question(term: RussianAdmissionTranslation, half: str) -> str:
    if half == "domain_nouns":
        return f"{term.citation} {_PARTNER_CUE}"
    return f"{_PARTNER_NOUN} {term.citation}"


def _russian_terms(half: str) -> tuple[tuple[str, RussianAdmissionTranslation], ...]:
    return tuple(_SHIPMENT_STATUS_RUSSIAN_ADMISSION_VOCABULARY[half].items())


@pytest.mark.parametrize(("english", "term"), _russian_terms("domain_nouns"))
def test_each_russian_noun_admits_when_paired_with_a_status_cue(
    english: str, term: RussianAdmissionTranslation
) -> None:
    assert english == term.english
    result = _loop().run(_request(_paired_question(term, "domain_nouns")))

    assert result.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert result.reason_codes == ("SHIPMENT_ID_REQUIRED",)


@pytest.mark.parametrize(("english", "term"), _russian_terms("status_cues"))
def test_each_russian_cue_admits_when_paired_with_a_domain_noun(
    english: str, term: RussianAdmissionTranslation
) -> None:
    assert english == term.english
    result = _loop().run(_request(_paired_question(term, "status_cues")))

    assert result.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert result.reason_codes == ("SHIPMENT_ID_REQUIRED",)


@pytest.mark.parametrize(("english", "term"), _russian_terms("domain_nouns"))
def test_russian_noun_does_not_admit_alone(english: str, term: RussianAdmissionTranslation) -> None:
    result = _loop().run(_request(term.citation))

    assert english == term.english
    assert result.terminal_state is TerminalOutcome.CANCELLED
    assert result.reason_codes == ("NOT_IN_JOURNEY",)


@pytest.mark.parametrize(("english", "term"), _russian_terms("status_cues"))
def test_russian_cue_does_not_admit_alone(english: str, term: RussianAdmissionTranslation) -> None:
    result = _loop().run(_request(term.citation))

    assert english == term.english
    assert result.terminal_state is TerminalOutcome.CANCELLED
    assert result.reason_codes == ("NOT_IN_JOURNEY",)


@pytest.mark.parametrize(
    "question",
    (
        "отправки задержан",
        "отправку задерживается",
        "отправкой доставлен",
        "груз доставлена",
        "отслеживание груза",
        "прибытие груза",
    ),
)
def test_documented_russian_stems_match_the_listed_inflected_forms(question: str) -> None:
    result = _loop().run(_request(question))

    assert result.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert result.reason_codes == ("SHIPMENT_ID_REQUIRED",)


def test_english_t01_probes_are_unchanged() -> None:
    declined = _loop().run(_request("Which shipment tracker should I buy?"))
    admitted = _loop().run(_request("My cargo is being held at the airport."))

    assert declined.terminal_state is TerminalOutcome.CANCELLED
    assert declined.reason_codes == ("NOT_IN_JOURNEY",)
    assert admitted.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert admitted.reason_codes == ("SHIPMENT_ID_REQUIRED",)


def test_russian_vocabulary_is_a_translation_of_the_english_vocabulary() -> None:
    assert set(_RUSSIAN_DOMAIN_NOUNS) == set(_ENGLISH_DOMAIN_NOUNS)
    assert set(_RUSSIAN_STATUS_CUES) == set(_ENGLISH_STATUS_CUES)
    assert set(_RUSSIAN_DOMAIN_NOUNS).isdisjoint(_RUSSIAN_STATUS_CUES)
    for english, term in {**_RUSSIAN_DOMAIN_NOUNS, **_RUSSIAN_STATUS_CUES}.items():
        assert term.english == english
        assert term.stem
        assert term.endings
        citation_tokens = tuple(term.citation.split())
        stem_tokens = tuple(term.stem.split())
        assert citation_tokens[:-1] == stem_tokens[:-1]
        assert any(
            citation_tokens[-1] == stem_tokens[-1] + ending for ending in term.endings
        )
        assert term.citation in term.forms


def test_air_waybill_russian_forms_do_not_admit_without_a_status_cue() -> None:
    air_waybill = _RUSSIAN_DOMAIN_NOUNS["air waybill"].citation
    awb = _RUSSIAN_DOMAIN_NOUNS["awb"].citation

    for question in (air_waybill, awb, f"как оформить {air_waybill}", f"как создать {awb}"):
        result = _loop().run(_request(question))
        assert result.terminal_state is TerminalOutcome.CANCELLED
        assert result.reason_codes == ("NOT_IN_JOURNEY",)
