from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from resolution.application.shipment_status import (
    _SHIPMENT_STATUS_RUSSIAN_ADMISSION_VOCABULARY,
    ShipmentShadowRequest,
    ShipmentStatusShadowLoop,
)
from resolution.composition import load_shipment_contract
from resolution.contracts import TerminalOutcome

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
TENANT = "tenant-a"
CASE_ID = UUID("10000000-0000-0000-0000-000000000001")
CORRELATION_ID = UUID("20000000-0000-0000-0000-000000000001")

_RUSSIAN_NOUNS = _SHIPMENT_STATUS_RUSSIAN_ADMISSION_VOCABULARY["domain_nouns"]
_RUSSIAN_CUES = _SHIPMENT_STATUS_RUSSIAN_ADMISSION_VOCABULARY["status_cues"]


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


@pytest.mark.parametrize(
    "question",
    (
        "Где грузин?",
        "груздь статус",
        "грузчик статус",
        "прибыль груза",
        "груз холдинга",
    ),
)
def test_out_of_domain_prefix_friends_are_declined(question: str) -> None:
    result = _loop().run(_request(question))

    assert result.terminal_state is TerminalOutcome.CANCELLED
    assert result.reason_codes == ("NOT_IN_JOURNEY",)


def test_gruzin_and_gruzd_and_gruzchik_are_not_domain_nouns() -> None:
    for question in ("Где грузин?", "груздь статус", "грузчик статус"):
        signals = ShipmentStatusShadowLoop.admission_signals((question,))
        assert signals.has_domain_noun is False


def test_pribyl_is_not_a_status_cue() -> None:
    signals = ShipmentStatusShadowLoop.admission_signals(("прибыль груза",))

    assert signals.has_domain_noun is True
    assert signals.has_status_cue is False


def test_holding_is_not_a_status_cue() -> None:
    signals = ShipmentStatusShadowLoop.admission_signals(("груз холдинга",))

    assert signals.has_domain_noun is True
    assert signals.has_status_cue is False


def test_unsafe_translations_use_stem_plus_endings_not_prefix() -> None:
    for term in (
        _RUSSIAN_NOUNS["cargo"],
        _RUSSIAN_CUES["hold"],
        _RUSSIAN_CUES["arrive"],
        _RUSSIAN_CUES["arrived"],
        _RUSSIAN_CUES["arriving"],
        _RUSSIAN_CUES["arrival"],
    ):
        assert term.stem
        assert term.endings
        assert term.citation in term.forms
        assert "грузин" not in term.forms
        assert "груздь" not in term.forms
        assert "грузчик" not in term.forms
        assert "прибыль" not in term.forms
        assert "холдинг" not in term.forms
        assert "холдинга" not in term.forms


def test_mixed_script_latin_runs_still_match_the_english_vocabulary() -> None:
    # T-01 tokenised with [a-z0-9]+, so "cargoгде status" was cargo + status.
    question = "cargoгде status"
    signals = ShipmentStatusShadowLoop.admission_signals((question,))
    result = _loop().run(_request(question))

    assert signals.has_domain_noun is True
    assert signals.has_status_cue is True
    assert result.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert result.reason_codes == ("SHIPMENT_ID_REQUIRED",)


def test_transit_stem_does_not_prefix_transistor() -> None:
    transit = _RUSSIAN_CUES["transit"]

    assert transit.stem == "транзит"
    assert not "транзистор".startswith(transit.stem)

    signals = ShipmentStatusShadowLoop.admission_signals(("транзистор груз",))
    result = _loop().run(_request("транзистор груз"))

    assert signals.has_domain_noun is True
    assert signals.has_status_cue is False
    assert result.terminal_state is TerminalOutcome.CANCELLED
    assert result.reason_codes == ("NOT_IN_JOURNEY",)


@pytest.mark.parametrize(
    "question",
    (
        "Где моя отправка?",
        "Статус груза задержан",
        "My cargo is being held at the airport.",
    ),
)
def test_in_domain_pairs_still_admit(question: str) -> None:
    result = _loop().run(_request(question))

    assert result.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert result.reason_codes == ("SHIPMENT_ID_REQUIRED",)


def test_english_tracker_probe_still_declines() -> None:
    result = _loop().run(_request("Which shipment tracker should I buy?"))

    assert result.terminal_state is TerminalOutcome.CANCELLED
    assert result.reason_codes == ("NOT_IN_JOURNEY",)
