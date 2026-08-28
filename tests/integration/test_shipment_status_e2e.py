"""Phase A.5 — the shadow, proved through the endpoint instead of around it.

A.1 wired the shipment-status journey into `/api/ask` and held it with unit
tests that call `_run_resolution_shadows` directly. Under the slice rule in
`CLAUDE.md` that is preparation, not a slice: nothing here had yet observed
`/api/ask` itself change. These tests do, over real HTTP through the real
router:

- a shipment-status question posted to `/api/ask` leaves a `resolution_shadow`
  step in the trace the answer names, carrying the evidence bundle, read back
  out of the trace store rather than intercepted on the way in (A.5);
- the response body is byte-for-byte the same with the shadow off and on
  (A.4 at the HTTP level — A.1 held it only by object identity inside the
  process);
- the same run, opened through `GET /api/admin/traces/{id}/evidence`, is the
  join an operator reads in the Evidence tab (A.3).

The read-back matters. Between the observer and the Evidence tab that phase
A.3 will build sit `_state_to_dict`, `json.dumps`, PII redaction and SQLite.
An evidence bundle that survives the sink but not that trip would pass every
A.1 test and still leave A.3 with nothing to render.

The transport management system underneath is a fixture, so what these tests
prove is the wiring — not anything about air cargo. Every number that comes
out of this journey is fixture-sourced and has to say so.
"""

from __future__ import annotations

import asyncio
import sqlite3
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from api.routers.conversation import _persist_shadow_evidence as _REAL_PERSIST

pytestmark = pytest.mark.integration

_QUESTION = "What is the status of shipment AC-100001?"
_CLARIFICATION_QUESTION = "Какой статус груза?"
_LEGACY_ANSWER = "Legacy pipeline answer, owned by the legacy pipeline."


class _Retriever:
    """The kernel gathers policy evidence through whatever the app has.

    Empty by default, which is what the A.1/A.4/A.5 tests want: they are about
    the seam, and a journey that finds no policy still reaches the trace. The
    A.3 tests hand it a policy document, because a bundle with no policy has no
    claims either, and claims are what the Evidence tab is for.
    """

    def __init__(self, documents: Sequence[Any] = ()) -> None:
        self._documents = list(documents)

    def get_relevant_documents(self, query: str) -> list[Any]:
        _ = query
        return list(self._documents)


class _FakeSession:
    """Stands in for the legacy pipeline, not for the kernel.

    `start_trace` is called for real, so the shadow writes into a trace that
    exists and `get_trace_detail` can read it back the way the admin UI does.
    """

    def __init__(self, *, open_trace: bool) -> None:
        self._history: list[dict[str, str]] = []
        self._open_trace = open_trace

    @property
    def history(self) -> list[dict[str, str]]:
        return self._history

    def ask(
        self,
        question: str,
        trace_id: str | None = None,
        tenant_id: str = "default",
        **kwargs: Any,
    ) -> dict[str, Any]:
        _ = kwargs
        recorded_trace_id = ""
        if self._open_trace:
            from tracing import log_step, start_trace

            recorded_trace_id = start_trace(tenant_id=tenant_id, correlation_id=trace_id)
            log_step(recorded_trace_id, "generate", {"answer": _LEGACY_ANSWER})
        self._history.append({"role": "user", "content": question})
        self._history.append({"role": "assistant", "content": _LEGACY_ANSWER})
        return {
            "answer": _LEGACY_ANSWER,
            "quality_score": 90,
            "route": "auto",
            "graded_docs": [],
            "trace_id": recorded_trace_id,
        }


async def _fake_log_audit(**kwargs: Any) -> None:
    _ = kwargs


@pytest.fixture(autouse=True)
def _isolated_trace_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Point the trace store at a per-test SQLite file.

    `_base_trace` builds its schema at import time against the path settings
    named then, so the tables have to be created again after the redirect.
    """
    from tracing import _base_trace

    database_path = tmp_path / "traces-e2e.db"
    monkeypatch.setattr(_base_trace, "_get_db_path", lambda: database_path)
    _base_trace._init_db()
    return database_path


@pytest.fixture(autouse=True)
def _reset_shadow_observer_cache():
    """The observer cache is module state; two tests must not share one."""
    from api.routers import conversation

    conversation._shadow_observers = {}
    conversation._shadow_observers_key = None
    yield
    conversation._shadow_observers = {}
    conversation._shadow_observers_key = None


@pytest.fixture(autouse=True)
def persisted(monkeypatch: pytest.MonkeyPatch) -> list:
    """Capture what the router hands to A.1b persistence instead of writing it.

    These tests are about the endpoint and the trace. What the resolution
    tables receive is asserted against real Postgres in
    `test_resolution_shadow_postgres.py`; leaving the write live here would
    make every test in this file depend on a reachable database, which is
    exactly the coupling the shadow is supposed not to introduce.
    """
    from api.routers import conversation

    recorded: list = []

    async def _record(results: list) -> None:
        recorded.extend(results)

    monkeypatch.setattr(conversation, "_persist_shadow_evidence", _record)
    return recorded


@pytest.fixture
def wired_app(monkeypatch: pytest.MonkeyPatch, integration_api_app, integration_store):
    """Give `/api/ask` a legacy pipeline and a retriever, and hand back a switch.

    Returns a callable that turns the shadow on: it sets the journey list on
    the very settings object the router reads, which is the same attribute
    production reads from `RESOLUTION_SHADOW_JOURNEYS`.
    """

    def _install(
        *,
        open_trace: bool = True,
        policy_documents: Sequence[Any] = (),
        shipment_fixtures: Sequence[Any] | None = None,
    ) -> Any:
        async def _fake_get_or_create_session(session_id: str | None, tenant_id: str = "default"):
            normalized = session_id or uuid.uuid4().hex
            key = (tenant_id, normalized)
            sessions = integration_store["sessions"]
            if key not in sessions:
                sessions[key] = _FakeSession(open_trace=open_trace)
            integration_api_app._sessions[normalized] = sessions[key]
            return normalized, sessions[key]

        monkeypatch.setattr(
            integration_api_app, "_get_or_create_session", _fake_get_or_create_session
        )
        monkeypatch.setattr(integration_api_app, "log_audit", _fake_log_audit)
        monkeypatch.setattr(
            integration_api_app,
            "_retriever",
            _Retriever(policy_documents),
            raising=False,
        )
        if shipment_fixtures is not None:
            # The contract gives a shipment observation a 300-second freshness
            # window, and the fixture TMS that ships with the package is dated
            # 2026-08-24. A journey run today against it escalates as
            # EVIDENCE_STALE before it ever reaches a policy -- correct, and
            # useless for testing what a completed journey looks like. Handing
            # it an observation as recent as the question is what a real TMS
            # would have; it changes nothing about the code under test.
            monkeypatch.setattr(
                "resolution.composition.load_shipment_fixtures",
                lambda path=None: tuple(shipment_fixtures),
            )

        def _enable_shadow(*, clarification: bool = False) -> None:
            settings = integration_api_app.get_settings()
            monkeypatch.setattr(
                settings, "resolution_shadow_journeys", ("shipment-status",), raising=False
            )
            if clarification:
                monkeypatch.setattr(
                    settings,
                    "resolution_clarification_journeys",
                    ("shipment-status",),
                    raising=False,
                )

        return _enable_shadow

    return _install


def _shadow_steps(database_path, trace_id: str) -> list[dict[str, Any]]:
    from tracing._base_trace import get_trace_detail

    detail = get_trace_detail(trace_id)
    assert detail is not None, f"trace {trace_id} is not in the store at {database_path}"
    return [step for step in detail["steps"] if step["node"] == "resolution_shadow"]


def _count_shadow_steps(database_path) -> int:
    connection = sqlite3.connect(database_path)
    try:
        return int(
            connection.execute(
                "SELECT count(*) FROM trace_steps WHERE node_name = 'resolution_shadow'"
            ).fetchone()[0]
        )
    finally:
        connection.close()


def test_a_shipment_question_leaves_an_evidence_bundle_in_the_trace(
    wired_app,
    integration_client,
    integration_headers,
    _isolated_trace_store,
) -> None:
    """A.5: `/api/ask` observably changed, and the change is durable."""
    enable_shadow = wired_app()
    enable_shadow()

    response = integration_client.post(
        "/api/ask",
        json={"question": _QUESTION},
        headers=integration_headers("acme", "admin"),
    )

    assert response.status_code == 200
    body = response.json()
    # The shadow observes; the legacy pipeline still owns the answer.
    assert body["answer"] == _LEGACY_ANSWER
    assert body["route"] == "auto"
    trace_id = body["trace_id"]
    assert trace_id, "the legacy answer named no trace, so nothing could attach to it"

    steps = _shadow_steps(_isolated_trace_store, trace_id)
    assert len(steps) == 1, "the shadow did not reach the trace the answer names"
    state = steps[0]["state"]

    assert state["journey"] == "shipment-status"
    evidence = state["evidence"]
    assert evidence["contract"]["contract_id"] == "aircargo.shipment-status"
    assert evidence["contract"]["version"] == "0.1.0"
    # The kernel's own identity rides inside the payload; the trace stays the
    # one the caller was handed, which is what makes the bundle reachable.
    assert state["kernel_correlation_id"] != trace_id
    assert state["case_id"]
    assert state["terminal_state"]
    # Recorded for comparison only. The shadow's answer is never returned.
    assert state["shadow_response_text"] != body["answer"]


def test_the_legacy_answer_is_untouched_when_the_shadow_is_off(
    wired_app,
    integration_client,
    integration_headers,
    _isolated_trace_store,
) -> None:
    """Off by default, end to end: no journey named, no step written."""
    wired_app()

    headers = integration_headers("acme", "admin")
    response = integration_client.post(
        "/api/ask",
        json={"question": _QUESTION},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["answer"] == _LEGACY_ANSWER
    assert _count_shadow_steps(_isolated_trace_store) == 0
    view = _evidence_for(integration_client, headers, response.json()["trace_id"])
    assert view["shadow_status"] == "shadow_disabled"
    assert view["journeys"] == []


def test_the_response_body_is_byte_identical_with_the_shadow_off_and_on(
    wired_app,
    integration_client,
    integration_headers,
    _isolated_trace_store,
) -> None:
    """A.4 at the HTTP level.

    A.1 held this by object identity inside the process, which says nothing
    about what serialisation produces. The legacy pipeline is pinned to a
    fixed session id and an empty trace id here so that the whole body is
    deterministic and the comparison can be a byte comparison rather than a
    field-by-field one with exemptions.
    """
    enable_shadow = wired_app(open_trace=False)
    # Fixed rather than random: the id is echoed in the body, so a fresh one
    # per request would make a byte comparison impossible. The endpoint
    # requires a well-formed UUID.
    session_id = "3f1c9c2e5b7d4a8fae2d6b0c19f43a77"
    payload = {"question": _QUESTION, "session_id": session_id}
    headers = integration_headers("acme", "admin")

    without_shadow = integration_client.post("/api/ask", json=payload, headers=headers)
    assert _count_shadow_steps(_isolated_trace_store) == 0

    enable_shadow()
    with_shadow = integration_client.post("/api/ask", json=payload, headers=headers)

    assert without_shadow.status_code == with_shadow.status_code == 200
    assert with_shadow.content == without_shadow.content
    # Without this the test would also pass with the shadow silently disabled,
    # which is the failure mode a shadow is most prone to.
    assert _count_shadow_steps(_isolated_trace_store) == 1


def test_clarification_flag_off_keeps_a_no_id_response_byte_identical(
    wired_app,
    integration_client,
    integration_headers,
) -> None:
    enable_shadow = wired_app(open_trace=False)
    session_id = "4f1c9c2e5b7d4a8fae2d6b0c19f43a77"
    payload = {"question": _CLARIFICATION_QUESTION, "session_id": session_id}
    headers = integration_headers("acme", "admin")

    without_shadow = integration_client.post("/api/ask", json=payload, headers=headers)
    enable_shadow()
    with_shadow = integration_client.post("/api/ask", json=payload, headers=headers)

    assert without_shadow.status_code == with_shadow.status_code == 200
    assert with_shadow.content == without_shadow.content


def test_clarification_flag_returns_the_contract_ask_and_updates_session_history(
    wired_app,
    integration_api_app,
    integration_store,
    integration_client,
    integration_headers,
) -> None:
    """T-03: an admitted no-id request gets the kernel's honest next question."""
    from resolution.composition import load_shipment_contract

    enable_shadow = wired_app(open_trace=False)
    enable_shadow(clarification=True)
    session_id = "5f1c9c2e5b7d4a8fae2d6b0c19f43a77"

    response = integration_client.post(
        "/api/ask",
        json={"question": _CLARIFICATION_QUESTION, "session_id": session_id},
        headers=integration_headers("acme", "admin"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] != _LEGACY_ANSWER
    assert "shipment id" in body["answer"].casefold()
    disclosure = load_shipment_contract().disclosure.id.replace("-", " ")
    assert disclosure.casefold() in body["answer"].casefold()
    assert body["route"] == "clarification_required"
    assert body["quality_score"] == 0
    assert body["sources"] == []
    assert body["citations"] == []
    assert body["session_id"] == session_id
    assert body["trace_id"] == ""
    assert body["cached"] is False

    session = integration_store["sessions"][("acme", session_id)]
    assert session.history[-1] == {"role": "assistant", "content": body["answer"]}
    assert integration_api_app._sessions[session_id] is session


def test_clarification_flag_leaves_a_declined_request_on_the_legacy_path(
    wired_app,
    integration_client,
    integration_headers,
    persisted,
) -> None:
    enable_shadow = wired_app()
    enable_shadow(clarification=True)
    headers = integration_headers("acme", "admin")

    response = integration_client.post(
        "/api/ask",
        json={"question": "Как оформить авианакладную?"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["answer"] == _LEGACY_ANSWER
    assert response.json()["route"] == "auto"
    view = _evidence_for(integration_client, headers, response.json()["trace_id"])
    assert view["shadow_status"] == "journey_declined"
    (journey,) = view["journeys"]
    assert journey["outcome"] == "journey_declined"
    assert journey["terminal_state"] == "cancelled"
    assert journey["reason_codes"] == ["NOT_IN_JOURNEY"]
    assert journey["observation"] is None
    assert journey["policy"] is None
    assert persisted == []


@pytest.mark.parametrize("failure_layer", ("loop", "composition"))
def test_a_shadow_that_raises_still_returns_the_legacy_answer(
    monkeypatch: pytest.MonkeyPatch,
    wired_app,
    integration_client,
    integration_headers,
    _isolated_trace_store,
    failure_layer: str,
) -> None:
    """A producer failure is visible but may not turn the legacy 200 into a 500."""
    enable_shadow = wired_app()
    enable_shadow(clarification=True)
    headers = integration_headers("acme", "admin")

    def _explode(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("shadow blew up")

    if failure_layer == "loop":
        monkeypatch.setattr(
            "resolution.application.shipment_status.ShipmentStatusShadowLoop.run",
            _explode,
        )
    else:
        from api.routers import conversation

        monkeypatch.setattr(conversation, "_resolution_shadow_observers", _explode)

    response = integration_client.post(
        "/api/ask",
        json={"question": _QUESTION},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["answer"] == _LEGACY_ANSWER
    view = _evidence_for(integration_client, headers, response.json()["trace_id"])
    assert view["shadow_status"] == "producer_failure"
    (journey,) = view["journeys"]
    assert journey["outcome"] == "producer_failure"
    assert journey["terminal_state"] == ""
    assert journey["reason_codes"] == []
    assert "error" not in journey


# --- phase A.1b: the same run, on its way to the resolution tables -----------


def test_the_run_that_reached_the_trace_is_handed_to_persistence(
    wired_app,
    integration_client,
    integration_headers,
    persisted,
) -> None:
    """A.1b's wiring: the endpoint offers the observation to the tables too.

    `run_legacy_ask_shadow` returns the legacy response rather than the
    observation, so the result reaching persistence at all is a claim worth
    holding — it travels out of the sink through a context variable, and a
    reset in the wrong place would silently empty it.
    """
    enable_shadow = wired_app()
    enable_shadow()

    response = integration_client.post(
        "/api/ask",
        json={"question": _QUESTION},
        headers=integration_headers("acme", "admin"),
    )

    assert response.status_code == 200
    assert len(persisted) == 1
    export = persisted[0].evidence_export
    assert export.contract.contract_id == "aircargo.shipment-status"
    assert export.tenant_id == "acme"


def test_nothing_is_handed_to_persistence_when_the_shadow_is_off(
    wired_app,
    integration_client,
    integration_headers,
    persisted,
) -> None:
    wired_app()

    response = integration_client.post(
        "/api/ask",
        json={"question": _QUESTION},
        headers=integration_headers("acme", "admin"),
    )

    assert response.status_code == 200
    assert persisted == []


def test_a_database_that_never_answers_does_not_hang_the_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    wired_app,
    integration_client,
    integration_headers,
) -> None:
    """The regression this slice actually caused, before the write was bounded.

    Connecting to an absent database does not fail fast, it hangs. The first
    wiring of A.1b awaited it unbounded, and every request running a shadow
    hung with it — a shadow taking the answer down, which is the one thing it
    may never do.
    """
    from api.routers import conversation

    async def _never_answers(*args: Any, **kwargs: Any) -> bool:
        await asyncio.sleep(30)
        return True

    monkeypatch.setattr("resolution.persistence.persist_shipment_shadow", _never_answers)
    monkeypatch.setattr(conversation, "_SHADOW_PERSIST_TIMEOUT_SECONDS", 0.05)
    # Put the real writer back: the autouse fixture swaps in a recorder, and a
    # recorder cannot hang.
    monkeypatch.setattr(conversation, "_persist_shadow_evidence", _REAL_PERSIST)

    enable_shadow = wired_app()
    enable_shadow()

    response = integration_client.post(
        "/api/ask",
        json={"question": _QUESTION},
        headers=integration_headers("acme", "admin"),
    )

    assert response.status_code == 200
    assert response.json()["answer"] == _LEGACY_ANSWER


# --- phase A.3: the same run, read back through the Evidence endpoint --------
#
# These run a journey that *completes*, which the tests above deliberately do
# not: they use the fixture TMS's own tenant, hand the retriever a policy
# document and give the fixture an observation as recent as the question. All
# three are needed because the contract puts a 300-second freshness window on
# a shipment observation and requires exactly one policy, so anything else
# escalates before a single claim is compiled — and claims are what an
# Evidence tab is for.

_POLICY_TENANT = "default"
_SHIPMENT_ID = "AC-100001"


def _recent_evidence() -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    """A fixture observation and a policy document, both current right now."""
    from resolution.adapters.shipment_status import ShipmentFixture

    now = datetime.now(UTC)
    fixtures = (
        ShipmentFixture(
            tenant_id=_POLICY_TENANT,
            shipment_id=_SHIPMENT_ID,
            status="in_transit",
            location="FRA",
            estimated_delivery="2026-08-27",
            observed_at=now - timedelta(seconds=30),
            source_version="e2e-fixture-0.1",
        ),
    )
    documents = (
        {
            "page_content": "Shipment status may be disclosed to the requesting party.",
            "metadata": {
                "tenant_id": _POLICY_TENANT,
                "authority": "logistics-policy-primary",
                "policy_revision": "2026-08-01",
                "recorded_at": (now - timedelta(seconds=60)).isoformat(),
                "valid_from": (now - timedelta(days=30)).isoformat(),
                "valid_to": None,
                "status_disclosure_allowed": True,
                "content_digest": "0" * 64,
            },
        },
    )
    return fixtures, documents


def _evidence_for(client, headers, trace_id: str) -> dict[str, Any]:
    response = client.get(f"/api/admin/traces/{trace_id}/evidence", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _ask_and_open_evidence(wired_app, client, headers, *, shadow: bool = True):
    fixtures, documents = _recent_evidence()
    enable_shadow = wired_app(policy_documents=documents, shipment_fixtures=fixtures)
    if shadow:
        enable_shadow()
    answer = client.post("/api/ask", json={"question": _QUESTION}, headers=headers)
    assert answer.status_code == 200
    trace_id = answer.json()["trace_id"]
    assert trace_id, "the answer named no trace, so there is nothing to open"
    return _evidence_for(client, headers, trace_id), trace_id


def test_a_real_question_produces_an_evidence_view_an_operator_can_read(
    wired_app,
    integration_client,
    integration_headers,
    _isolated_trace_store,
) -> None:
    """A.3 end to end: ask, then open the Evidence tab on the answer's trace.

    The tab is not handed the bundle — it goes and gets it, by the trace id
    the caller was given, through the same endpoint the browser calls. What
    comes back is the join: the contract that ran, the decision the policy
    made, and each claim next to the evidence under it with the age that
    evidence had when it was read.
    """
    headers = integration_headers(_POLICY_TENANT, "admin")

    view, trace_id = _ask_and_open_evidence(wired_app, integration_client, headers)

    assert view["trace_id"] == trace_id
    assert view["shadow_status"] == "journey_recorded"
    (journey,) = view["journeys"]
    assert journey["outcome"] == "journey_recorded"
    assert journey["journey"] == "shipment-status"
    assert journey["contract"]["contract_id"] == "aircargo.shipment-status"
    assert journey["contract"]["version"] == "0.1.0"
    assert journey["terminal_state"] == "verified"

    # The policy decision, carrying the policy's own time rather than the run's.
    assert journey["policy"] is not None
    assert journey["policy"]["source_id"] == "logistics-policy-primary"
    assert journey["policy"]["source_version"] == "2026-08-01"
    assert journey["policy"]["age_seconds"] >= 0.0

    # Freshness against the observation's own timestamp. The TMS is a
    # stand-in, so this says the join works and nothing about air cargo.
    assert journey["observation"] is not None
    assert journey["observation"]["source_id"] == "shipment-source-primary"
    assert journey["observation"]["label"].startswith(_SHIPMENT_ID)
    assert 0.0 <= journey["observation"]["age_seconds"] <= 300.0

    # The replay receipt is the claim "this is reproducible", made checkable.
    receipt = journey["replay_receipt"]
    assert receipt["case_id"] and receipt["correlation_id"]
    assert receipt["contract_digest"] and receipt["source_digest"]
    assert receipt["policy_digest"] == "0" * 64


def test_every_claim_the_run_made_names_the_evidence_under_it(
    wired_app,
    integration_client,
    integration_headers,
    _isolated_trace_store,
) -> None:
    """The tab's reason to exist: no claim rendered as supported by nothing.

    A claim citing evidence the bundle does not carry is reported as
    unresolved rather than dropped, so this asserts the real journey produces
    none of those — and that everything it does cite resolves to evidence
    whose digest matches the one the claim names.
    """
    headers = integration_headers(_POLICY_TENANT, "admin")

    view, _ = _ask_and_open_evidence(wired_app, integration_client, headers)

    (journey,) = view["journeys"]
    assert journey["claims"], "the run made no claims, so there is nothing to justify"
    for claim in journey["claims"]:
        assert claim["unresolved"] == [], (
            f"claim {claim['claim_id']} cites evidence the bundle does not carry"
        )
        assert claim["sources"], f"claim {claim['claim_id']} rests on nothing"
        assert {source["kind"] for source in claim["sources"]} == {"observation", "policy"}
        for source in claim["sources"]:
            assert source["digest"], "evidence without a digest cannot be replayed"
            assert source["digest_matches"] is True


def test_a_trace_from_a_question_with_the_shadow_off_has_no_journeys(
    wired_app,
    integration_client,
    integration_headers,
    _isolated_trace_store,
) -> None:
    """Off by default, all the way to the tab: an empty panel, not an error."""
    headers = integration_headers(_POLICY_TENANT, "admin")

    view, _ = _ask_and_open_evidence(
        wired_app, integration_client, headers, shadow=False
    )

    assert view["journeys"] == []
