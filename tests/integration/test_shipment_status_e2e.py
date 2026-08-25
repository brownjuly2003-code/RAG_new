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
  process).

The read-back matters. Between the observer and the Evidence tab that phase
A.3 will build sit `_state_to_dict`, `json.dumps`, PII redaction and SQLite.
An evidence bundle that survives the sink but not that trip would pass every
A.1 test and still leave A.3 with nothing to render.

The transport management system underneath is a fixture, so what these tests
prove is the wiring — not anything about air cargo. Every number that comes
out of this journey is fixture-sourced and has to say so.
"""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any

import pytest

pytestmark = pytest.mark.integration

_QUESTION = "What is the status of shipment AC-100001?"
_LEGACY_ANSWER = "Legacy pipeline answer, owned by the legacy pipeline."


class _Retriever:
    """The kernel gathers policy evidence through whatever the app has."""

    def get_relevant_documents(self, query: str) -> list[Any]:
        _ = query
        return []


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


@pytest.fixture
def wired_app(monkeypatch: pytest.MonkeyPatch, integration_api_app, integration_store):
    """Give `/api/ask` a legacy pipeline and a retriever, and hand back a switch.

    Returns a callable that turns the shadow on: it sets the journey list on
    the very settings object the router reads, which is the same attribute
    production reads from `RESOLUTION_SHADOW_JOURNEYS`.
    """

    def _install(*, open_trace: bool = True) -> Any:
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
        monkeypatch.setattr(integration_api_app, "_retriever", _Retriever(), raising=False)

        def _enable_shadow() -> None:
            settings = integration_api_app.get_settings()
            monkeypatch.setattr(
                settings, "resolution_shadow_journeys", ("shipment-status",), raising=False
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

    response = integration_client.post(
        "/api/ask",
        json={"question": _QUESTION},
        headers=integration_headers("acme", "admin"),
    )

    assert response.status_code == 200
    assert response.json()["answer"] == _LEGACY_ANSWER
    assert _count_shadow_steps(_isolated_trace_store) == 0


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


def test_a_shadow_that_raises_still_returns_the_legacy_answer(
    monkeypatch: pytest.MonkeyPatch,
    wired_app,
    integration_client,
    integration_headers,
    _isolated_trace_store,
) -> None:
    """The leash, over HTTP: a broken shadow may not turn 200 into 500."""
    from api.routers import conversation

    enable_shadow = wired_app()
    enable_shadow()

    def _explode(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("shadow blew up")

    monkeypatch.setattr(conversation, "_resolution_shadow_observers", _explode)

    response = integration_client.post(
        "/api/ask",
        json={"question": _QUESTION},
        headers=integration_headers("acme", "admin"),
    )

    assert response.status_code == 200
    assert response.json()["answer"] == _LEGACY_ANSWER
    assert _count_shadow_steps(_isolated_trace_store) == 0
