"""The resolution kernel finally has a production caller -- on a leash.

Audit 2026-08-24, FIN-01: seven slices of resolution kernel had been built and
proven only against their own tests, because no module under api/ or agent/
imported resolution, knowledge, actions or services.session. /api/ask had not
changed since the fork. Phase A of plan_23_08_2026 wires the shipment-status
journey in as a read-only shadow.

The contract of a shadow is narrow, and these tests are what hold it: it
observes, it records, and it can never change or break the answer.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class _Response:
    """Stand-in for AskResponse: object identity is what the assertions check."""

    def __init__(self, answer: str = "legacy answer") -> None:
        self.answer = answer


class _Retriever:
    def get_relevant_documents(self, query: str) -> list[Any]:
        return []


def _settings(journeys: tuple[str, ...]) -> Any:
    return SimpleNamespace(resolution_shadow_journeys=journeys)


def _app_stub(journeys: tuple[str, ...], retriever: Any = None) -> Any:
    return SimpleNamespace(
        get_settings=lambda: _settings(journeys),
        _retriever=retriever if retriever is not None else _Retriever(),
    )


@pytest.fixture(autouse=True)
def _reset_observer_cache() -> Any:
    from api.routers import conversation

    conversation._shadow_observers = {}
    conversation._shadow_observers_key = None
    yield
    conversation._shadow_observers = {}
    conversation._shadow_observers_key = None


# --- the flag ---------------------------------------------------------------


def test_shadow_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RESOLUTION_SHADOW_JOURNEYS", raising=False)
    from config.settings import Settings

    assert Settings().resolution_shadow_journeys == ()


def test_flag_parses_and_deduplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESOLUTION_SHADOW_JOURNEYS", " shipment-status , shipment-status ")
    from config.settings import Settings

    assert Settings().resolution_shadow_journeys == ("shipment-status",)


def test_unknown_journey_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    """A typo must not look like a working shadow.

    The shadow is invisible by design -- it changes no response -- so a silent
    no-op on a misspelled journey is indistinguishable from a running one.
    """
    monkeypatch.setenv("RESOLUTION_SHADOW_JOURNEYS", "shipment_status")
    from config.settings import Settings

    with pytest.raises(ValueError, match="unknown journeys"):
        Settings()


def test_clarification_response_is_off_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RESOLUTION_CLARIFICATION_JOURNEYS", raising=False)
    from config.settings import Settings

    assert Settings().resolution_clarification_journeys == ()


def test_clarification_flag_parses_and_deduplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "RESOLUTION_CLARIFICATION_JOURNEYS",
        " shipment-status , shipment-status ",
    )
    from config.settings import Settings

    assert Settings().resolution_clarification_journeys == ("shipment-status",)


def test_unknown_clarification_journey_fails_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RESOLUTION_CLARIFICATION_JOURNEYS", "shipment_status")
    from config.settings import Settings

    with pytest.raises(ValueError, match="unknown journeys"):
        Settings()


# --- the legacy response is never touched -----------------------------------


def test_response_object_is_returned_unchanged_when_the_shadow_is_off() -> None:
    from api.routers import conversation

    original = _Response()
    returned = conversation._run_resolution_shadows(
        response=original,
        tenant_id="default",
        session_id="s1",
        correlation_id="c1",
        question="Where is AC-100001?",
    )
    assert returned is original


def test_response_object_is_returned_unchanged_when_the_shadow_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.routers import conversation

    recorded: list[Any] = []
    monkeypatch.setattr(conversation, "_app_module", lambda: _app_stub(("shipment-status",)))
    monkeypatch.setattr(conversation, "_record_shadow_evidence", recorded.append)

    original = _Response()
    returned = conversation._run_resolution_shadows(
        response=original,
        tenant_id="default",
        session_id="s1",
        correlation_id="c1",
        question="Where is shipment AC-100001?",
    )

    assert returned is original
    assert returned.answer == "legacy answer"


def test_a_shadow_that_raises_cannot_break_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point of a shadow: it may fail, the request may not."""
    from api.routers import conversation

    def _explode(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("shadow blew up")

    monkeypatch.setattr(conversation, "_app_module", lambda: _app_stub(("shipment-status",)))
    monkeypatch.setattr(conversation, "_resolution_shadow_observers", _explode)

    original = _Response()
    returned = conversation._run_resolution_shadows(
        response=original,
        tenant_id="default",
        session_id="s1",
        correlation_id="c1",
        question="Where is AC-100001?",
    )
    assert returned is original


def test_missing_retriever_is_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Before the vector store is initialised there is nothing to gather from."""
    from api.routers import conversation

    app = SimpleNamespace(
        get_settings=lambda: _settings(("shipment-status",)), _retriever=None
    )
    monkeypatch.setattr(conversation, "_app_module", lambda: app)

    original = _Response()
    assert (
        conversation._run_resolution_shadows(
            response=original,
            tenant_id="default",
            session_id="s1",
            correlation_id="c1",
            question="q",
        )
        is original
    )


# --- the shadow actually observes -------------------------------------------


def test_shadow_records_an_evidence_bundle_for_a_known_shipment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.routers import conversation

    recorded: list[Any] = []
    monkeypatch.setattr(conversation, "_app_module", lambda: _app_stub(("shipment-status",)))
    monkeypatch.setattr(conversation, "_record_shadow_evidence", recorded.append)

    conversation._run_resolution_shadows(
        response=_Response(),
        tenant_id="default",
        session_id="s1",
        correlation_id="c1",
        question="What is the status of shipment AC-100001?",
    )

    assert len(recorded) == 1, "the shadow did not run"
    export = recorded[0].evidence_export
    assert export.contract.contract_id == "aircargo.shipment-status"
    assert export.contract.version == "0.1.0"
    assert export.tenant_id == "default"
    # Serialisable, because it has to survive the trip into the trace.
    json.dumps(export.as_dict())


def test_clarification_result_is_collected_even_without_a_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Response ownership may not depend on the trace store being available."""
    from api.routers import conversation
    from resolution.contracts import TerminalOutcome

    collected: list[Any] = []
    monkeypatch.setattr(conversation, "_app_module", lambda: _app_stub(("shipment-status",)))

    conversation._run_resolution_shadows(
        response=_Response(),
        tenant_id="default",
        session_id="s1",
        correlation_id="",
        question="Какой статус груза?",
        trace_id="",
        collect=collected,
    )

    assert len(collected) == 1
    assert collected[0].terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
    assert collected[0].reason_codes == ("SHIPMENT_ID_REQUIRED",)
    assert "shipment id" in collected[0].response_text.casefold()
    assert "ai assistance" in collected[0].response_text.casefold()


def test_observers_are_built_once_and_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.routers import conversation

    retriever = _Retriever()
    monkeypatch.setattr(conversation, "_record_shadow_evidence", lambda result: None)

    first = conversation._resolution_shadow_observers(("shipment-status",), retriever)
    second = conversation._resolution_shadow_observers(("shipment-status",), retriever)
    assert first is second


def test_a_new_retriever_rebuilds_the_observers() -> None:
    """The app swaps its retriever on reindex; a stale one gathers from a stale index."""
    from api.routers import conversation

    first = conversation._resolution_shadow_observers(("shipment-status",), _Retriever())
    second = conversation._resolution_shadow_observers(("shipment-status",), _Retriever())
    assert first is not second


# --- what ships with the package --------------------------------------------


def test_the_packaged_contract_matches_the_digest_the_loop_pins() -> None:
    """A contract edited without a version bump changes what the shadow measures."""
    from resolution.application.shipment_status import _SHIPMENT_CONTRACT_DIGEST
    from resolution.composition import load_shipment_contract
    from resolution.contracts.serialization import contract_digest

    assert contract_digest(load_shipment_contract()) == _SHIPMENT_CONTRACT_DIGEST


def test_the_packaged_contract_matches_the_test_corpus_copy() -> None:
    from resolution.composition import SHIPMENT_CONTRACT_PATH

    fixture = (
        PROJECT_ROOT
        / "tests"
        / "fixtures"
        / "resolution_contracts"
        / "v0.1"
        / "valid"
        / "shipment-status.json"
    )
    assert SHIPMENT_CONTRACT_PATH.read_bytes() == fixture.read_bytes()


def test_fixture_shipments_load_and_say_what_they_are() -> None:
    from resolution.composition import SHIPMENT_FIXTURE_PATH, load_shipment_fixtures

    fixtures = load_shipment_fixtures()
    assert fixtures, "the fixture TMS is empty"
    for fixture in fixtures:
        assert fixture.observed_at.tzinfo is not None

    payload = json.loads(SHIPMENT_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert "NOT a real transport management system" in payload["_comment"], (
        "the fixture asset must say what it is; numbers derived from it are "
        "fixture-sourced and every published figure has to say so"
    )


def test_evidence_lands_in_the_trace_the_answer_owns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Evidence tab has to be reachable from the answer it explains.

    The kernel mints its own case and correlation UUIDs. Logging the bundle
    under those would file it in a trace nobody can reach from the response,
    so the legacy trace id wins and the kernel identity rides inside the
    payload.
    """
    from api.routers import conversation

    logged: list[tuple[str, str, dict[str, Any]]] = []
    monkeypatch.setattr(
        "tracing.log_step",
        lambda trace_id, node, state: logged.append((trace_id, node, state)),
    )
    monkeypatch.setattr(conversation, "_app_module", lambda: _app_stub(("shipment-status",)))

    conversation._run_resolution_shadows(
        response=_Response(),
        tenant_id="default",
        session_id="s1",
        correlation_id="corr-1",
        question="What is the status of shipment AC-100001?",
        trace_id="trace-legacy-42",
    )

    assert logged, "no evidence reached the trace"
    trace_id, node, state = logged[0]
    assert trace_id == "trace-legacy-42"
    assert node == "resolution_shadow"
    assert state["kernel_correlation_id"] != trace_id
    assert state["evidence"]["contract"]["contract_id"] == "aircargo.shipment-status"


def test_trace_id_falls_back_to_the_correlation_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.routers import conversation

    logged: list[str] = []
    monkeypatch.setattr(
        "tracing.log_step", lambda trace_id, node, state: logged.append(trace_id)
    )
    monkeypatch.setattr(conversation, "_app_module", lambda: _app_stub(("shipment-status",)))

    conversation._run_resolution_shadows(
        response=_Response(),
        tenant_id="default",
        session_id="s1",
        correlation_id="corr-only",
        question="What is the status of shipment AC-100001?",
    )

    assert logged == ["corr-only"]
