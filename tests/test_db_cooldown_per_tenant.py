"""Phase A.2 — a database failure stops the tenant that had it, and no one else.

`api/app.py` used to keep one process-wide `_db_retry_after` deadline. Four
call sites set it — the session bootstrap, the `/api/ask` message write, the
history read and the session delete — and all four read it, so a single
tenant's failing query stopped session lookups and message writes for *every*
tenant for a minute. `audit_sol_23_08_2026.md` asks for that blast radius to
be partitioned; this is the partition.

Two properties are worth holding separately:

- **per-tenant**, so tenant B's request is unaffected by tenant A's outage.
  That is the behaviour change, and the reason the old global was a defect
  rather than a simplification;
- **bounded**, because the key is a tenant id from a JWT claim. A map keyed on
  an attacker-supplied string with no cap is a memory leak with an external
  trigger, so the cap is part of the contract and not an implementation
  detail.
"""

from __future__ import annotations

import asyncio
import importlib
import time
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.routers import conversation
from auth.jwt_handler import create_access_token

api_app = importlib.import_module("api.app")

TENANT_A = "tenant-a"
TENANT_B = "tenant-b"
SESSION_UUID = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")


def _auth(tenant: str, role: str = "agent") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token('u-' + tenant, role, tenant)}"}


def _cooldown(**kwargs: Any) -> Any:
    return api_app._TenantDbCooldown(**kwargs)


# --- the registry -----------------------------------------------------------


def test_a_failure_blocks_the_tenant_that_had_it_and_nobody_else() -> None:
    """The whole point of the change, at its smallest."""
    cooldown = _cooldown()

    cooldown.trip(TENANT_A)

    assert cooldown.blocked(TENANT_A) is True
    assert cooldown.blocked(TENANT_B) is False


def test_a_cooldown_ends_on_its_own() -> None:
    cooldown = _cooldown(duration_sec=0.05)

    cooldown.trip(TENANT_A)
    assert cooldown.blocked(TENANT_A) is True
    time.sleep(0.08)

    assert cooldown.blocked(TENANT_A) is False
    assert cooldown.tripped_tenants() == 0


def test_a_call_that_worked_clears_the_tenant() -> None:
    """Success is what ends a cooldown early; nothing else does."""
    cooldown = _cooldown()
    cooldown.trip(TENANT_A)

    cooldown.clear(TENANT_A)

    assert cooldown.blocked(TENANT_A) is False


def test_clearing_one_tenant_leaves_the_others_in_cooldown() -> None:
    cooldown = _cooldown()
    cooldown.trip(TENANT_A)
    cooldown.trip(TENANT_B)

    cooldown.clear(TENANT_A)

    assert cooldown.blocked(TENANT_A) is False
    assert cooldown.blocked(TENANT_B) is True


def test_the_map_never_grows_past_its_capacity() -> None:
    """The key comes from a JWT claim, so the bound is part of the contract."""
    cooldown = _cooldown(capacity=8)

    for index in range(200):
        cooldown.trip(f"tenant-{index}")

    assert cooldown.tripped_tenants() <= 8
    # The most recent tenants are the ones still remembered.
    assert cooldown.blocked("tenant-199") is True
    assert cooldown.blocked("tenant-0") is False


def test_a_full_map_drops_expired_entries_before_live_ones() -> None:
    """Eviction should cost nothing while anything in the map is already stale."""
    cooldown = _cooldown(capacity=2, duration_sec=0.05)
    cooldown.trip("stale-one")
    cooldown.trip("stale-two")
    time.sleep(0.08)

    cooldown.trip(TENANT_A, duration_sec=60.0)
    cooldown.trip(TENANT_B, duration_sec=60.0)

    assert cooldown.blocked(TENANT_A) is True
    assert cooldown.blocked(TENANT_B) is True


def test_a_long_forged_tenant_id_cannot_grow_the_key() -> None:
    """`sessions.tenant_id` is String(50): a longer id can never own a row."""
    cooldown = _cooldown()
    forged = "x" * 10_000

    cooldown.trip(forged)

    assert cooldown.blocked(forged) is True
    # Two ids sharing the first 64 characters share the cooldown. That is what
    # the bound costs, and it only ever costs a retry — never data.
    assert cooldown.blocked("x" * 64 + "-and-more") is True
    assert cooldown.blocked("y" * 10_000) is False


def test_a_missing_tenant_is_the_default_one() -> None:
    cooldown = _cooldown()

    cooldown.trip("")

    assert cooldown.blocked(None) is True
    assert cooldown.blocked("default") is True


def test_configure_takes_the_window_and_the_bound_from_settings() -> None:
    cooldown = _cooldown(duration_sec=60.0, capacity=512)
    for index in range(10):
        cooldown.trip(f"tenant-{index}")

    cooldown.configure(duration_sec=0.05, capacity=4)

    assert cooldown.tripped_tenants() == 4
    cooldown.trip(TENANT_A)
    time.sleep(0.08)
    assert cooldown.blocked(TENANT_A) is False


def test_the_app_starts_with_an_empty_cooldown() -> None:
    assert api_app._db_cooldown.tripped_tenants() == 0


# --- the message write ------------------------------------------------------


class _Result:
    def __init__(self, scalar: Any = None) -> None:
        self._scalar = scalar

    def scalar_one_or_none(self) -> Any:
        return self._scalar


class _Db:
    """A database that is down for some tenants and up for the rest.

    Which tenant a statement belongs to is read off its bound parameters,
    which is the only signal a session factory actually has.
    """

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state

    async def __aenter__(self) -> _Db:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    @staticmethod
    def _tenant_of(statement: Any) -> str | None:
        try:
            params = dict(statement.compile().params)
        except Exception:
            return None
        for key, value in params.items():
            if "tenant" in str(key).lower():
                return str(value)
        return None

    async def execute(self, statement: Any) -> _Result:
        tenant = self._tenant_of(statement)
        self.state.setdefault("selects", []).append(tenant)
        if tenant in self.state["broken"]:
            raise RuntimeError(f"database is unreachable for {tenant}")
        return _Result(scalar=SESSION_UUID)

    def add(self, record: Any) -> None:
        self.state.setdefault("written", []).append((record.tenant_id, record.role))

    async def commit(self) -> None:
        self.state["commits"] = self.state.get("commits", 0) + 1


@pytest.fixture
def writes(monkeypatch: pytest.MonkeyPatch):
    """`_persist_ask_messages` against a database with a per-tenant outage."""
    state: dict[str, Any] = {"broken": set()}
    cooldown = _cooldown()

    monkeypatch.setattr("db.engine.async_session", lambda: _Db(state))
    monkeypatch.setattr(
        conversation,
        "_app_module",
        lambda: SimpleNamespace(
            _db_cooldown=cooldown,
            get_settings=lambda: SimpleNamespace(db_persist_timeout_sec=2.0),
        ),
    )
    return SimpleNamespace(state=state, cooldown=cooldown)


def _persist(tenant: str) -> None:
    asyncio.run(
        conversation._persist_ask_messages(
            session_id=str(SESSION_UUID),
            tenant_id=tenant,
            question="user-q",
            answer="assistant-a",
            path="test",
        )
    )


def test_a_failed_write_puts_only_that_tenant_in_cooldown(writes) -> None:
    writes.state["broken"] = {TENANT_A}

    _persist(TENANT_A)

    assert writes.cooldown.blocked(TENANT_A) is True
    assert writes.cooldown.blocked(TENANT_B) is False
    assert writes.state.get("written") is None


def test_one_tenants_outage_does_not_stop_another_tenants_write(writes) -> None:
    """The regression the global deadline caused, stated as a test.

    Before this change the second call returned without touching the database
    at all: the breaker it consulted had been opened by a tenant it has
    nothing to do with.
    """
    writes.state["broken"] = {TENANT_A}
    _persist(TENANT_A)

    _persist(TENANT_B)

    assert writes.state["written"] == [(TENANT_B, "user"), (TENANT_B, "assistant")]
    assert writes.state["commits"] == 1


def test_a_tenant_in_cooldown_is_skipped_without_touching_the_database(writes) -> None:
    writes.cooldown.trip(TENANT_A)

    _persist(TENANT_A)

    assert writes.state.get("selects") is None


def test_a_write_that_worked_ends_the_tenants_cooldown(writes) -> None:
    writes.state["broken"] = {TENANT_A}
    _persist(TENANT_A)
    writes.state["broken"] = set()
    # The cooldown would otherwise skip the retry; a real one waits it out.
    writes.cooldown.clear(TENANT_A)

    _persist(TENANT_A)

    assert writes.cooldown.blocked(TENANT_A) is False
    assert writes.state["written"] == [(TENANT_A, "user"), (TENANT_A, "assistant")]


# --- through /api/ask -------------------------------------------------------


@pytest.fixture
def ask_client(monkeypatch: pytest.MonkeyPatch, client: TestClient):
    """`/api/ask` with the session bootstrap stubbed and the writer live.

    Only the message write reaches the fake database here: what the bootstrap
    does with one is TEN-01's subject, and leaving it live would make this
    test about two cooldown call sites at once.
    """
    state: dict[str, Any] = {"broken": {TENANT_A}}

    async def _get_or_create_session(session_id: str | None = None, tenant_id: str = "default"):
        return (session_id or SESSION_UUID.hex), {"history": [], "tenant_id": tenant_id}

    async def _log_audit(**kwargs: Any) -> None:
        _ = kwargs

    monkeypatch.setattr("db.engine.async_session", lambda: _Db(state))
    monkeypatch.setattr(api_app, "_get_or_create_session", _get_or_create_session)
    monkeypatch.setattr(api_app, "log_audit", _log_audit)
    monkeypatch.setattr(api_app, "_db_cooldown", _cooldown())
    return SimpleNamespace(client=client, state=state)


def test_one_tenants_outage_does_not_cost_another_tenant_its_history(ask_client) -> None:
    """Observable at the endpoint: B's answer is still written down while A's is not."""
    first = ask_client.client.post(
        "/api/ask", json={"question": "hello"}, headers=_auth(TENANT_A)
    )
    second = ask_client.client.post(
        "/api/ask", json={"question": "hello"}, headers=_auth(TENANT_B)
    )

    # The outage is invisible to both callers; that part has not changed.
    assert first.status_code == second.status_code == 200
    assert api_app._db_cooldown.blocked(TENANT_A) is True
    assert api_app._db_cooldown.blocked(TENANT_B) is False
    assert ask_client.state["written"] == [(TENANT_B, "user"), (TENANT_B, "assistant")]
