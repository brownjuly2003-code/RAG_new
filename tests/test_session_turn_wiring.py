"""Phase A.2 -- `/api/ask` borrows the session for a turn, and gives it back.

Until this slice `services/session.py` was the other half of finding FIN-01:
a durable turn lifecycle, tested against real Postgres, with no caller. The
endpoint wrote its message pair on a best-effort path that could lose it, and
two requests on one session raced each other into an interleaved history.

These tests hold the wiring decisions without a database — first at the
router's helpers, then through `/api/ask` itself with the service faked. What
`admit_turn`, `commit_turn` and `abort_turn` actually guarantee is asserted
against real Postgres in `tests/integration/test_session_service_postgres.py`,
and the endpoint driving them for real, rows and all, is
`tests/integration/test_session_turns_e2e.py`.

Two of the decisions here are worth stating out loud, because both are places
where an obvious implementation is wrong:

- the turn id is derived from the request, not handed in by the client. An
  `Idempotency-Key` header contract is durable-HTTP work, frozen in
  `ROADMAP.md`;
- the turn id includes the question. A key covering only (tenant, session,
  version) would deadlock a session after an aborted turn: the retry of a
  *different* question would collide with the dead turn's id and be refused
  forever, because the version that would have freed it never moved.
"""

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from api.routers import conversation
from services.session import (
    SessionNotFound,
    SessionTurnActive,
    SessionTurnIdempotencyConflict,
    SessionTurnSnapshot,
    SessionVersionConflict,
    TurnAdmissionOutcome,
    TurnStatus,
)

api_app = importlib.import_module("api.app")

# One endpoint test drives the handler into a raise; a 500 response is what
# the caller would see, and what the test needs to assert on.
CLIENT_RAISE_SERVER_EXCEPTIONS = False

_TENANT = "acme"
_SESSION_ID = "3f1c9c2e5b7d4a8fae2d6b0c19f43a77"
_QUESTION = "Where is shipment AC-100001?"


def _settings(**overrides: Any) -> Any:
    base = {
        "session_durable_turns": True,
        "db_persist_timeout_sec": 2.0,
        "request_timeout_sec": 30.0,
        "session_turn_deadline_margin_sec": 15.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _reset_service_cache() -> Any:
    conversation._session_turn_service = None
    yield
    conversation._session_turn_service = None


@pytest.fixture
def app_settings(monkeypatch: pytest.MonkeyPatch):
    """Point the router's settings lookup at a namespace the test owns."""

    def _install(**overrides: Any) -> Any:
        settings = _settings(**overrides)
        monkeypatch.setattr(
            conversation,
            "_app_module",
            lambda: SimpleNamespace(get_settings=lambda: settings),
        )
        return settings

    return _install


def _snapshot(
    *,
    status: TurnStatus = TurnStatus.RUNNING,
    turn_id: str = "ask-" + "a" * 64,
    turn_epoch: int = 1,
) -> SessionTurnSnapshot:
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    return SessionTurnSnapshot(
        tenant_id=_TENANT,
        turn_id=turn_id,
        session_id=UUID(_SESSION_ID),
        request_digest="b" * 64,
        expected_version=0,
        turn_epoch=turn_epoch,
        status=status,
        admitted_at=now,
        deadline_at=now + timedelta(seconds=45),
        terminal_at=None if status is TurnStatus.RUNNING else now,
        result_digest=None,
        committed_version=None,
    )


class _Service:
    """Records what the router asked for; raises what the test wants."""

    def __init__(
        self,
        *,
        version: int | Exception = 0,
        admit: Any = None,
        commit: Any = None,
        abort: Any = None,
    ) -> None:
        self._version = version
        self._admit = admit if admit is not None else TurnAdmissionOutcome(
            turn=_snapshot(), admitted=True
        )
        self._commit = commit
        self._abort = abort
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def current_version(self, **kwargs: Any) -> int:
        self.calls.append(("current_version", kwargs))
        if isinstance(self._version, Exception):
            raise self._version
        return self._version

    async def admit_turn(self, **kwargs: Any) -> Any:
        self.calls.append(("admit_turn", kwargs))
        if isinstance(self._admit, Exception):
            raise self._admit
        if callable(self._admit):
            return self._admit(**kwargs)
        return self._admit

    async def commit_turn(self, **kwargs: Any) -> Any:
        self.calls.append(("commit_turn", kwargs))
        if isinstance(self._commit, Exception):
            raise self._commit
        return self._commit

    async def abort_turn(self, **kwargs: Any) -> Any:
        self.calls.append(("abort_turn", kwargs))
        if isinstance(self._abort, Exception):
            raise self._abort
        return self._abort

    def named(self, name: str) -> list[dict[str, Any]]:
        return [payload for call, payload in self.calls if call == name]


def _install_service(monkeypatch: pytest.MonkeyPatch, service: Any) -> Any:
    monkeypatch.setattr(conversation, "_durable_turn_service", lambda: service)
    return service


async def _admit(**overrides: Any) -> Any:
    payload = {
        "tenant_id": _TENANT,
        "session_id": _SESSION_ID,
        "question": _QUESTION,
        "confirm": False,
    }
    payload.update(overrides)
    return await conversation._admit_durable_turn(**payload)


# --- the flag ---------------------------------------------------------------


def test_durable_turns_are_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SESSION_DURABLE_TURNS", raising=False)
    from config.settings import Settings

    assert Settings().session_durable_turns is False


def test_the_flag_turns_them_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_DURABLE_TURNS", "TRUE")
    from config.settings import Settings

    assert Settings().session_durable_turns is True


def test_the_flag_off_never_reaches_the_service(
    monkeypatch: pytest.MonkeyPatch, app_settings
) -> None:
    app_settings(session_durable_turns=False)
    service = _install_service(monkeypatch, _Service())

    assert asyncio.run(_admit()) is None
    assert service.calls == []


# --- turn identity ----------------------------------------------------------


def _identity(**overrides: Any) -> tuple[str, str]:
    payload = {
        "tenant_id": _TENANT,
        "session_id": _SESSION_ID,
        "expected_version": 0,
        "question": _QUESTION,
        "confirm": False,
    }
    payload.update(overrides)
    return conversation._durable_turn_identity(**payload)


def test_identical_requests_get_one_turn_id() -> None:
    assert _identity() == _identity()


def test_the_digest_is_a_sha256_and_the_id_fits_the_column() -> None:
    turn_id, digest = _identity()
    assert len(digest) == 64 and int(digest, 16) >= 0
    # `services.session` caps turn_id at 128 characters and forbids
    # surrounding whitespace; a violation would only surface at runtime.
    assert len(turn_id) <= 128
    assert turn_id.strip() == turn_id


@pytest.mark.parametrize(
    "override",
    [
        {"question": "Where is shipment AC-100002?"},
        {"tenant_id": "other-tenant"},
        {"session_id": uuid4().hex},
        {"confirm": True},
    ],
)
def test_a_different_request_gets_a_different_turn(override: dict[str, Any]) -> None:
    baseline_id, baseline_digest = _identity()
    other_id, other_digest = _identity(**override)
    assert other_id != baseline_id
    assert other_digest != baseline_digest


def test_the_same_question_at_a_new_version_is_a_new_turn() -> None:
    """This is what stops one committed turn from swallowing every repeat.

    The digest is the request; the id is the request bound to the version it
    extends. Committing moves the version, so asking the same thing again is a
    turn of its own rather than a collision with a terminal one.
    """
    first_id, first_digest = _identity(expected_version=0)
    second_id, second_digest = _identity(expected_version=1)
    assert first_id != second_id
    assert first_digest == second_digest


# --- admission --------------------------------------------------------------


def test_an_admitted_turn_carries_its_fencing_token(
    monkeypatch: pytest.MonkeyPatch, app_settings
) -> None:
    app_settings()
    service = _install_service(
        monkeypatch,
        _Service(version=3, admit=TurnAdmissionOutcome(turn=_snapshot(turn_epoch=4), admitted=True)),
    )

    turn = asyncio.run(_admit())

    assert turn is not None
    assert turn.turn_epoch == 4
    assert turn.session_id == UUID(_SESSION_ID)
    assert turn.settled is False
    admitted = service.named("admit_turn")[0]
    assert admitted["expected_version"] == 3
    assert admitted["deadline_at"].tzinfo is not None
    # request_timeout_sec + session_turn_deadline_margin_sec, not one of them.
    assert admitted["turn_id"], "the router admitted a turn without an identity"


def test_a_turn_already_running_in_the_session_is_a_503(
    monkeypatch: pytest.MonkeyPatch, app_settings
) -> None:
    """The behaviour change this slice is for.

    Before A.2 the second request ran too, and the two answers interleaved
    into one history with no way to tell afterwards which pair belonged to
    which question.
    """
    app_settings()
    _install_service(monkeypatch, _Service(admit=SessionTurnActive("ask-other")))

    with pytest.raises(HTTPException) as raised:
        asyncio.run(_admit())

    assert raised.value.status_code == 503


def test_a_duplicate_of_a_request_still_running_is_a_503(
    monkeypatch: pytest.MonkeyPatch, app_settings
) -> None:
    """Idempotent admission: the retry joins nothing, it is turned away.

    `admit_turn` hands back the running turn rather than raising, because the
    id is the same one. Answering it a second time is exactly what must not
    happen.
    """
    app_settings()
    _install_service(
        monkeypatch,
        _Service(admit=TurnAdmissionOutcome(turn=_snapshot(), admitted=False)),
    )

    with pytest.raises(HTTPException) as raised:
        asyncio.run(_admit())

    assert raised.value.status_code == 503


def test_a_version_that_moved_under_the_request_is_a_503(
    monkeypatch: pytest.MonkeyPatch, app_settings
) -> None:
    app_settings()
    _install_service(
        monkeypatch,
        _Service(admit=SessionVersionConflict(expected_version=0, actual_version=1)),
    )

    with pytest.raises(HTTPException) as raised:
        asyncio.run(_admit())

    assert raised.value.status_code == 503


@pytest.mark.parametrize("status", [TurnStatus.COMMITTED, TurnStatus.ABORTED, TurnStatus.EXPIRED])
def test_a_request_whose_turn_already_ended_is_answered_without_one(
    monkeypatch: pytest.MonkeyPatch, app_settings, status: TurnStatus
) -> None:
    """Replaying a stored response body is REL-03D, and REL-03D is frozen.

    So the honest move is to answer again on the path that predates durable
    turns, rather than invent a body out of a digest.
    """
    app_settings()
    _install_service(
        monkeypatch,
        _Service(admit=TurnAdmissionOutcome(turn=_snapshot(status=status), admitted=False)),
    )

    assert asyncio.run(_admit()) is None


@pytest.mark.parametrize(
    "failure",
    [
        SessionNotFound("session was not found for tenant"),
        SessionTurnIdempotencyConflict("bound elsewhere"),
        RuntimeError("connection refused"),
    ],
)
def test_a_database_problem_answers_the_question_anyway(
    monkeypatch: pytest.MonkeyPatch, app_settings, failure: Exception
) -> None:
    """A flag that is off in production may not fail the request when it is on.

    None here means "answer on the pre-A.2 path", which is the same answer the
    caller would have got yesterday.
    """
    app_settings()
    _install_service(monkeypatch, _Service(admit=failure))

    assert asyncio.run(_admit()) is None


def test_a_database_that_never_answers_does_not_hold_the_request(
    monkeypatch: pytest.MonkeyPatch, app_settings
) -> None:
    """The A.1b lesson, applied before it could be relearned.

    Connecting to an absent database hangs rather than failing fast. Wiring
    the resolution write in without a bound hung `/api/ask` outright; this
    bound is why the same mistake cannot repeat here.
    """
    app_settings(db_persist_timeout_sec=0.05)

    class _Hangs(_Service):
        async def admit_turn(self, **kwargs: Any) -> Any:
            self.calls.append(("admit_turn", kwargs))
            await asyncio.sleep(30)

    _install_service(monkeypatch, _Hangs())

    async def _run() -> Any:
        return await asyncio.wait_for(_admit(), timeout=5)

    assert asyncio.run(_run()) is None


def test_a_malformed_session_id_never_reaches_the_database(
    monkeypatch: pytest.MonkeyPatch, app_settings
) -> None:
    app_settings()
    service = _install_service(monkeypatch, _Service())

    assert asyncio.run(_admit(session_id="not-a-uuid")) is None
    assert service.calls == []


# --- commit and abort -------------------------------------------------------


def _turn(service: Any) -> Any:
    return conversation._DurableTurn(
        service=service,
        tenant_id=_TENANT,
        session_id=UUID(_SESSION_ID),
        turn_id="ask-" + "a" * 64,
        turn_epoch=1,
        request_digest="b" * 64,
    )


def test_commit_writes_the_pair_through_the_turn(
    monkeypatch: pytest.MonkeyPatch, app_settings
) -> None:
    app_settings()
    service = _Service()
    turn = _turn(service)

    committed = asyncio.run(
        conversation._commit_durable_turn(turn, question=_QUESTION, answer="the answer")
    )

    assert committed is True
    assert turn.settled is True
    payload = service.named("commit_turn")[0]
    assert payload["user_content"] == _QUESTION
    assert payload["assistant_content"] == "the answer"
    assert payload["turn_epoch"] == 1


def test_an_empty_answer_aborts_instead_of_committing(
    monkeypatch: pytest.MonkeyPatch, app_settings
) -> None:
    """`commit_turn` refuses an empty side of the pair, and is right to.

    A turn with nothing to say has nothing to make durable; leaving it RUNNING
    would hold the session until its deadline for no reason.
    """
    app_settings()
    service = _Service()
    turn = _turn(service)

    committed = asyncio.run(conversation._commit_durable_turn(turn, question=_QUESTION, answer=""))

    assert committed is False
    assert service.named("commit_turn") == []
    assert service.named("abort_turn") != []


def test_a_failed_commit_does_not_fall_back_to_the_best_effort_write(
    monkeypatch: pytest.MonkeyPatch, app_settings
) -> None:
    """One turn may not write its pair twice.

    False tells `/api/ask` the pair is not durable. It does not tell it to try
    the other writer: a commit that timed out may still have landed, and the
    duplicate would be indistinguishable from a real second turn.
    """
    app_settings()
    service = _Service(commit=RuntimeError("connection reset"))
    turn = _turn(service)

    committed = asyncio.run(
        conversation._commit_durable_turn(turn, question=_QUESTION, answer="the answer")
    )

    assert committed is False
    assert turn.settled is True


def test_a_settled_turn_is_never_aborted_twice(
    monkeypatch: pytest.MonkeyPatch, app_settings
) -> None:
    app_settings()
    service = _Service()
    turn = _turn(service)
    asyncio.run(conversation._commit_durable_turn(turn, question=_QUESTION, answer="answer"))

    asyncio.run(conversation._settle_durable_turn([turn]))

    assert service.named("abort_turn") == []


def test_a_turn_left_running_is_aborted_on_the_way_out(
    monkeypatch: pytest.MonkeyPatch, app_settings
) -> None:
    """The handler can leave through a raise; the session may not stay held."""
    app_settings()
    service = _Service()
    turn = _turn(service)

    asyncio.run(conversation._settle_durable_turn([turn]))

    assert service.named("abort_turn") != []
    assert turn.settled is True


def test_an_abort_that_fails_is_left_to_the_deadline(
    monkeypatch: pytest.MonkeyPatch, app_settings
) -> None:
    """`admit_turn` expires a turn past its deadline, so this is only a shortcut."""
    app_settings()
    service = _Service(abort=RuntimeError("connection refused"))
    turn = _turn(service)

    asyncio.run(conversation._settle_durable_turn([turn]))

    assert turn.settled is True


# --- the endpoint, over HTTP ------------------------------------------------
#
# The tests above call the router's helpers. These go through `/api/ask`, so
# they hold the things only the endpoint can get wrong: that admission happens
# on the request path at all, that a refusal becomes a 503 response rather than
# a traceback, that the best-effort writer is skipped exactly when the turn
# owns the write, and that the turn is given back when the handler leaves
# through a raise.
#
# There is still no database here. What the turn does to real rows is
# `tests/integration/test_session_turns_e2e.py`.


@pytest.fixture
def endpoint(monkeypatch: pytest.MonkeyPatch, client):
    """`/api/ask` with no pipeline behind it and no database under it.

    The session bootstrap is replaced rather than driven: what it does with a
    database is TEN-01's subject, and leaving it live here would make every
    assertion below wait on a connection that is not there.
    """
    persisted: list[dict[str, Any]] = []

    async def _get_or_create_session(session_id: str | None = None, tenant_id: str = "default"):
        return (session_id or _SESSION_ID), {"history": [], "tenant_id": tenant_id}

    async def _log_audit(**kwargs: Any) -> None:
        _ = kwargs

    async def _persist_ask_messages(**kwargs: Any) -> None:
        persisted.append(kwargs)

    monkeypatch.setattr(api_app, "_get_or_create_session", _get_or_create_session)
    monkeypatch.setattr(api_app, "log_audit", _log_audit)
    monkeypatch.setattr(conversation, "_persist_ask_messages", _persist_ask_messages)
    return SimpleNamespace(
        client=client,
        persisted=persisted,
        settings=api_app.get_settings(),
    )


def _post_ask(endpoint: Any, question: str = _QUESTION):
    return endpoint.client.post("/api/ask", json={"question": question})


def test_the_turn_writes_the_pair_and_the_best_effort_path_stands_down(
    monkeypatch: pytest.MonkeyPatch, endpoint
) -> None:
    """The durable path owns the write; two writers for one turn is the bug."""
    monkeypatch.setattr(endpoint.settings, "session_durable_turns", True, raising=False)
    service = _install_service(monkeypatch, _Service())

    response = _post_ask(endpoint)

    assert response.status_code == 200
    answer = response.json()["answer"]
    committed = service.named("commit_turn")
    assert len(committed) == 1
    assert committed[0]["user_content"] == _QUESTION
    assert committed[0]["assistant_content"] == answer
    assert committed[0]["tenant_id"] == service.named("admit_turn")[0]["tenant_id"]
    assert endpoint.persisted == [], "the pair was written twice for one turn"
    assert service.named("abort_turn") == []


def test_a_session_already_answering_is_a_503_response(
    monkeypatch: pytest.MonkeyPatch, endpoint
) -> None:
    """The refusal reaches the caller as a status, not as a traceback."""
    monkeypatch.setattr(endpoint.settings, "session_durable_turns", True, raising=False)
    _install_service(monkeypatch, _Service(admit=SessionTurnActive("ask-other")))

    response = _post_ask(endpoint)

    assert response.status_code == 503
    assert endpoint.persisted == [], "a refused request still wrote to the history"


def test_with_the_flag_off_the_endpoint_writes_the_way_it_always_did(
    monkeypatch: pytest.MonkeyPatch, endpoint
) -> None:
    """Off by default means the pre-A.2 endpoint, down to which writer ran."""
    service = _install_service(monkeypatch, _Service())

    response = _post_ask(endpoint)

    assert response.status_code == 200
    assert service.calls == []
    assert len(endpoint.persisted) == 1
    assert endpoint.persisted[0]["question"] == _QUESTION
    assert endpoint.persisted[0]["answer"] == response.json()["answer"]


def test_a_request_that_dies_before_its_answer_gives_the_turn_back(
    monkeypatch: pytest.MonkeyPatch, endpoint
) -> None:
    """Whatever the handler leaves through, the session does not stay held.

    The cache-key step is the first thing after admission that can raise, so
    it is what stands in here for any failure between admission and answer.
    """
    monkeypatch.setattr(endpoint.settings, "session_durable_turns", True, raising=False)
    monkeypatch.setattr(endpoint.settings, "llm_cache_enabled", True, raising=False)

    def _explode(*args: Any, **kwargs: Any) -> str:
        raise RuntimeError("the request died before it had an answer")

    monkeypatch.setattr(api_app, "_cache_key", _explode)
    service = _install_service(monkeypatch, _Service())

    response = _post_ask(endpoint)

    assert response.status_code == 500
    assert service.named("commit_turn") == []
    aborted = service.named("abort_turn")
    assert len(aborted) == 1
    assert aborted[0]["turn_epoch"] == 1
    assert endpoint.persisted == []
