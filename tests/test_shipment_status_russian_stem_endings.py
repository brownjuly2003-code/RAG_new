"""Russian admission matching is stem + a finite ending set.

Closing design (T-08): not unbounded startswith, and not a hand-typed word
list. A Cyrillic token matches iff it equals stem+ending for some ending on
that entry. Shared ending tuples are named by part of speech. A missed
inflection is an accepted limitation; a false friend is a defect.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from resolution.application.shipment_status import (
    _ARRIVED_ENDINGS,
    _IMPERFECTIVE_VERB_ENDINGS,
    _MASC_HARD_NOUN_ENDINGS,
    _PAST_ACTIVE_ENDINGS,
    _PAST_TENSE_ENDINGS,
    _PRESENT_U_ENDINGS,
    _SHIPMENT_STATUS_RUSSIAN_ADMISSION_VOCABULARY,
    _TIE_NOUN_ENDINGS,
    ShipmentShadowRequest,
    ShipmentStatusShadowLoop,
    _russian_term_matches,
    _window_matches_stem_plus_endings,
)
from resolution.composition import load_shipment_contract
from resolution.contracts import TerminalOutcome

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
TENANT = "tenant-a"
CASE_ID = UUID("10000000-0000-0000-0000-000000000001")
CORRELATION_ID = UUID("20000000-0000-0000-0000-000000000001")
_SOURCE = Path(__file__).resolve().parent.parent / "resolution" / "application" / "shipment_status.py"

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
    ("question", "admitted"),
    (
        ("Грузы прибыли на терминал", True),
        ("Отследить отправку", True),
        ("Груз доставляется завтра", True),
        ("Отправка задерживается", True),
        ("Где моя отправка?", True),
        ("Где грузин?", False),
        ("грузчик уволился", False),
        ("прибыль груза", False),
        ("прибыли компании", False),
        ("груз холдинга", False),
        ("Which shipment tracker should I buy?", False),
        ("cargoгде status", True),
    ),
)
def test_closing_decision_table(question: str, admitted: bool) -> None:
    result = _loop().run(_request(question))
    if admitted:
        assert result.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
        assert result.reason_codes == ("SHIPMENT_ID_REQUIRED",)
        return
    assert result.terminal_state is TerminalOutcome.CANCELLED
    assert result.reason_codes == ("NOT_IN_JOURNEY",)


@pytest.mark.parametrize(
    "question",
    (
        "Как будет доставляться груз завтра?",
        "груз доставлялся",
        "грузы доставлялись",
        "доставляющий груз",
    ),
)
def test_delivering_stem_covers_reflexive_and_participle(question: str) -> None:
    signals = ShipmentStatusShadowLoop.admission_signals((question,))
    result = _loop().run(_request(question))

    assert signals.has_domain_noun is True
    assert signals.has_status_cue is True
    assert result.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert result.reason_codes == ("SHIPMENT_ID_REQUIRED",)


@pytest.mark.parametrize(
    "question",
    (
        "Что известно о прибытиях грузов?",
        "прибытиям груза",
        "прибытиями груза",
        "о прибытиях груза",
    ),
)
def test_arrival_stem_covers_oblique_plural(question: str) -> None:
    signals = ShipmentStatusShadowLoop.admission_signals((question,))
    result = _loop().run(_request(question))

    assert signals.has_domain_noun is True
    assert signals.has_status_cue is True
    assert result.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert result.reason_codes == ("SHIPMENT_ID_REQUIRED",)


def test_verified_gruz_concatenations() -> None:
    stem = "груз"
    endings = _MASC_HARD_NOUN_ENDINGS
    for word in ("груз", "груза", "грузы", "грузов"):
        assert any(word == stem + ending for ending in endings)
    for word in ("грузин", "грузчик", "груздь", "грузия"):
        assert all(word != stem + ending for ending in endings)


def test_verified_priby_concatenations() -> None:
    stem = "прибы"
    endings = _PAST_TENSE_ENDINGS + _TIE_NOUN_ENDINGS + ("вший",)
    for word in ("прибыл", "прибыла", "прибыли", "прибытие"):
        assert any(word == stem + ending for ending in endings)
    for word in ("прибыль", "прибыльный"):
        assert all(word != stem + ending for ending in endings)


def test_russian_matcher_is_not_startswith() -> None:
    matcher_src = inspect.getsource(_russian_term_matches)
    window_src = inspect.getsource(_window_matches_stem_plus_endings)
    assert "startswith" not in matcher_src
    assert "startswith" not in window_src


def test_hand_typed_form_sets_are_gone() -> None:
    source = _SOURCE.read_text(encoding="utf-8")
    for name in (
        "_CARGO_FORMS",
        "_AWB_FORMS",
        "_HOLD_FORMS",
        "_ARRIVE_FORMS",
        "_ARRIVED_FORMS",
        "_ARRIVING_FORMS",
        "_ARRIVAL_FORMS",
        "_DELIVER_FORMS",
        "_DELIVERED_FORMS",
        "_DELIVERING_FORMS",
        "_DELIVERY_FORMS",
    ):
        assert name not in source
    assert "prefix=True" not in source


def test_ending_tuples_are_shared_by_part_of_speech() -> None:
    assert _RUSSIAN_NOUNS["cargo"].endings is _MASC_HARD_NOUN_ENDINGS
    assert _RUSSIAN_CUES["hold"].endings is _MASC_HARD_NOUN_ENDINGS
    assert _RUSSIAN_CUES["status"].endings is _MASC_HARD_NOUN_ENDINGS
    assert _RUSSIAN_CUES["transit"].endings is _MASC_HARD_NOUN_ENDINGS
    assert _RUSSIAN_CUES["delivering"].endings is _IMPERFECTIVE_VERB_ENDINGS
    assert _RUSSIAN_CUES["arriving"].endings is _IMPERFECTIVE_VERB_ENDINGS
    assert _RUSSIAN_CUES["delaying"].endings is _IMPERFECTIVE_VERB_ENDINGS
    assert _RUSSIAN_CUES["holding"].endings is _IMPERFECTIVE_VERB_ENDINGS
    assert _RUSSIAN_CUES["arrival"].endings is _TIE_NOUN_ENDINGS
    assert _RUSSIAN_CUES["arrived"].endings is _ARRIVED_ENDINGS
    assert _ARRIVED_ENDINGS == _PAST_TENSE_ENDINGS + _PAST_ACTIVE_ENDINGS
    assert _RUSSIAN_CUES["arrive"].alts == (("прибуд", _PRESENT_U_ENDINGS),)


def test_every_entry_is_stem_plus_endings() -> None:
    for half in ("domain_nouns", "status_cues"):
        for english, term in _SHIPMENT_STATUS_RUSSIAN_ADMISSION_VOCABULARY[half].items():
            assert term.english == english
            assert term.stem
            assert term.endings
            citation_tokens = tuple(term.citation.split())
            stem_tokens = tuple(term.stem.split())
            assert citation_tokens[:-1] == stem_tokens[:-1]
            assert any(
                citation_tokens[-1] == stem_tokens[-1] + ending for ending in term.endings
            )


def test_english_t01_probes_are_unchanged() -> None:
    declined = _loop().run(_request("Which shipment tracker should I buy?"))
    admitted = _loop().run(_request("My cargo is being held at the airport."))

    assert declined.terminal_state is TerminalOutcome.CANCELLED
    assert declined.reason_codes == ("NOT_IN_JOURNEY",)
    assert admitted.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert admitted.reason_codes == ("SHIPMENT_ID_REQUIRED",)


def test_noun_or_cue_alone_still_declines() -> None:
    for question in ("груз", "отправка", "доставляется", "прибыли"):
        result = _loop().run(_request(question))
        assert result.terminal_state is TerminalOutcome.CANCELLED
        assert result.reason_codes == ("NOT_IN_JOURNEY",)
