"""Russian stem+endings must keep the ordinary air-cargo paradigm.

A finite ending set covers inflections (F-T-08-4: прибыли; ж/д in
отследить) without admitting derived false friends.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from resolution.application.shipment_status import (
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


def test_translation_rejects_a_stem_with_a_double_space() -> None:
    with pytest.raises(ValueError, match="stem tokens must use single spaces"):
        RussianAdmissionTranslation(
            english="air waybill",
            citation="авиа накладная",
            stem="авиа  накладн",
            endings=("ая",),
        )


def test_past_plural_pribyli_admits_when_paired_with_cargo() -> None:
    question = "Грузы прибыли."
    signals = ShipmentStatusShadowLoop.admission_signals((question,))
    result = _loop().run(_request(question))

    assert signals.has_domain_noun is True
    assert signals.has_status_cue is True
    assert result.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert result.reason_codes == ("SHIPMENT_ID_REQUIRED",)


def test_pribyl_profit_with_cargo_still_declines() -> None:
    question = "Прибыль груза."
    signals = ShipmentStatusShadowLoop.admission_signals((question,))
    result = _loop().run(_request(question))

    assert signals.has_domain_noun is True
    assert signals.has_status_cue is False
    assert result.terminal_state is TerminalOutcome.CANCELLED
    assert result.reason_codes == ("NOT_IN_JOURNEY",)


def test_pribyli_without_a_domain_noun_still_declines() -> None:
    # прибыли is also genitive of прибыль; the noun-plus-cue rule keeps this out.
    question = "прибыли компании"
    signals = ShipmentStatusShadowLoop.admission_signals((question,))
    result = _loop().run(_request(question))

    assert signals.has_domain_noun is False
    assert result.terminal_state is TerminalOutcome.CANCELLED
    assert result.reason_codes == ("NOT_IN_JOURNEY",)


def test_arrived_forms_include_pribyli_and_exclude_pribyl_profit() -> None:
    arrived = _RUSSIAN_CUES["arrived"]

    assert arrived.stem == "прибы"
    assert "ли" in arrived.endings
    assert "ль" not in arrived.endings
    assert "прибыли" in arrived.forms
    assert "прибыль" not in arrived.forms
    assert "прибыльный" not in arrived.forms


@pytest.mark.parametrize(
    "question",
    (
        "груз прибыл",
        "отправка прибыла",
        "груз прибыло",
        "грузы прибыли",
        "когда прибудет груз",
        "грузы прибудут",
        "прибытие груза",
        "прибытия груза",
        "прибывший груз",
        "прибывающий груз",
    ),
)
def test_ordinary_arrive_forms_admit_when_paired(question: str) -> None:
    signals = ShipmentStatusShadowLoop.admission_signals((question,))
    result = _loop().run(_request(question))

    assert signals.has_domain_noun is True
    assert signals.has_status_cue is True
    assert result.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert result.reason_codes == ("SHIPMENT_ID_REQUIRED",)


@pytest.mark.parametrize(
    "question",
    (
        "Отследить отправку",
        "отследить отправку",
        "отследи груз",
        "отследите груз",
        "отслеживать груз",
        "отслеживание груза",
        "отслеживания груза",
        "груз отслежен",
    ),
)
def test_track_zh_d_alternation_admits_when_paired(question: str) -> None:
    signals = ShipmentStatusShadowLoop.admission_signals((question,))
    result = _loop().run(_request(question))

    assert signals.has_domain_noun is True
    assert signals.has_status_cue is True
    assert result.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert result.reason_codes == ("SHIPMENT_ID_REQUIRED",)


def test_track_stem_covers_zh_and_d_alternation() -> None:
    track = _RUSSIAN_CUES["track"]
    tracked = _RUSSIAN_CUES["tracked"]
    tracking = _RUSSIAN_CUES["tracking"]

    assert track.stem == "отслежива"
    assert tracking.stem == "отслежива"
    assert tracked.stem == "отслежен"
    assert any(alt_stem == "отслед" for alt_stem, _alt_endings in track.alts)
    assert any(track.stem + ending == "отслеживать" for ending in track.endings)
    assert any(track.stem + ending == "отслеживание" for ending in track.endings)
    assert any(
        alt_stem + ending == "отследить"
        for alt_stem, alt_endings in track.alts
        for ending in alt_endings
    )
    assert any(
        alt_stem + ending == "отследи"
        for alt_stem, alt_endings in track.alts
        for ending in alt_endings
    )
    assert any(
        alt_stem + ending == "отследите"
        for alt_stem, alt_endings in track.alts
        for ending in alt_endings
    )
    assert any(tracking.stem + ending == "отслеживания" for ending in tracking.endings)
    assert any(tracked.stem + ending == "отслежен" for ending in tracked.endings)


@pytest.mark.parametrize(
    "question",
    (
        "груз доставляется",
        "грузы доставляются",
        "доставляемый груз",
        "доставьте груз",
        "доставивший груз",
    ),
)
def test_ordinary_deliver_forms_admit_when_paired(question: str) -> None:
    signals = ShipmentStatusShadowLoop.admission_signals((question,))
    result = _loop().run(_request(question))

    assert signals.has_domain_noun is True
    assert signals.has_status_cue is True
    assert result.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert result.reason_codes == ("SHIPMENT_ID_REQUIRED",)


@pytest.mark.parametrize(
    "question",
    (
        "Прибыль груза.",
        "Где грузин?",
        "груздь статус",
        "грузчик статус",
        "груз холдинга",
        "доставать груз",
        "грузовик статус",
        "холдер груза",
    ),
)
def test_false_friends_that_forced_explicit_lists_still_decline(question: str) -> None:
    result = _loop().run(_request(question))

    assert result.terminal_state is TerminalOutcome.CANCELLED
    assert result.reason_codes == ("NOT_IN_JOURNEY",)


def test_cargo_hold_arrive_stem_endings_exclude_false_friends() -> None:
    for term in (
        _RUSSIAN_NOUNS["cargo"],
        _RUSSIAN_CUES["hold"],
        _RUSSIAN_CUES["arrive"],
        _RUSSIAN_CUES["arrived"],
        _RUSSIAN_CUES["arriving"],
        _RUSSIAN_CUES["arrival"],
        _RUSSIAN_CUES["deliver"],
        _RUSSIAN_CUES["delivered"],
        _RUSSIAN_CUES["delivering"],
        _RUSSIAN_CUES["delivery"],
    ):
        assert term.stem
        assert term.endings
        assert "грузин" not in term.forms
        assert "прибыль" not in term.forms
        assert "холдинг" not in term.forms
        assert "доставать" not in term.forms
