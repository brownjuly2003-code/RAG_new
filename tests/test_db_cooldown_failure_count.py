"""Stage 6, item 3: one slow database call no longer closes a tenant's store.

PLAN.md: «запись дольше 2 с закрывает его на 60 с с ответом 503. При свопе и
после перезапуска это срабатывает.» Every database call on the session paths
runs under `db_persist_timeout_sec` (2 s). On the 8 GB Mac a call that waits
on swap, or on a cold connection after a restart, outlasts it, and each such
tail used to start the tenant's 60-s cooldown at once. During the cooldown the
database is not asked, and every caller-supplied session id that is not in
this process's memory gets 503 "Session store temporarily unavailable". After
a restart that memory is empty, so the 503 meets every returning visitor.

The fix counts. `record_failure` starts the cooldown after
`DB_COOLDOWN_FAILURE_THRESHOLD` (3) failures with no success between them.
What the guard protects is kept and pinned here:

- a call that fails still refuses an unverified caller-supplied id with 503;
- a store that keeps failing is still closed, and once the window runs out,
  one more failure closes it again at once;
- `trip` still closes at once, and the default object still closes on one
  failure, so phase A.2's per-tenant tests hold unchanged.
"""

from __future__ import annotations

import asyncio
import importlib
import time
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from api.routers import conversation

api_app = importlib.import_module("api.app")

TENANT_A = "tenant-a"
TENANT_B = "tenant-b"
SESSION_UUID = uuid.UUID("cccccccc-dddd-eeee-ffff-000000000003")

# Read by conftest's `client` fixture: the startup must take the threshold
# from settings, not from the getattr default.
CLIENT_SETTINGS_OVERRIDES = {"db_cooldown_failure_threshold": 2}


def _cooldown(**kwargs: Any) -> Any:
    return api_app._TenantDbCooldown(**kwargs)


# --- the count ---------------------------------------------------------------


def test_failures_below_the_threshold_leave_the_store_open() -> None:
    cooldown = _cooldown(failure_threshold=3)

    assert cooldown.record_failure(TENANT_A) is False
    assert cooldown.record_failure(TENANT_A) is False
    assert cooldown.blocked(TENANT_A) is False
    assert cooldown.tripped_tenants() == 0

    assert cooldown.record_failure(TENANT_A) is True
    assert cooldown.blocked(TENANT_A) is True


def test_a_success_between_failures_starts_the_count_again() -> None:
    cooldown = _cooldown(failure_threshold=3)
    cooldown.record_failure(TENANT_A)
    cooldown.record_failure(TENANT_A)

    cooldown.clear(TENANT_A)
    cooldown.record_failure(TENANT_A)
    cooldown.record_failure(TENANT_A)

    assert cooldown.blocked(TENANT_A) is False


def test_after_the_window_the_next_failure_closes_the_store_at_once() -> None:
    """A store still failing after the window is not given three more tries."""
    cooldown = _cooldown(duration_sec=0.05, failure_threshold=3)
    for _ in range(3):
        cooldown.record_failure(TENANT_A)
    time.sleep(0.08)
    assert cooldown.blocked(TENANT_A) is False

    assert cooldown.record_failure(TENANT_A) is True
    assert cooldown.blocked(TENANT_A) is True


def test_the_count_is_kept_per_tenant() -> None:
    cooldown = _cooldown(failure_threshold=2)
    cooldown.record_failure(TENANT_A)
    cooldown.record_failure(TENANT_B)

    cooldown.record_failure(TENANT_A)

    assert cooldown.blocked(TENANT_A) is True
    assert cooldown.blocked(TENANT_B) is False


def test_trip_and_the_default_object_still_close_on_one_failure() -> None:
    """Phase A.2's tests build the default object and expect one failure to block."""
    counted = _cooldown(failure_threshold=3)
    counted.trip(TENANT_A)
    assert counted.blocked(TENANT_A) is True

    default = _cooldown()
    assert default.record_failure(TENANT_A) is True
    assert default.blocked(TENANT_A) is True


def test_reset_forgets_the_counts() -> None:
    cooldown = _cooldown(failure_threshold=2)
    cooldown.record_failure(TENANT_A)

    cooldown.reset()
    cooldown.record_failure(TENANT_A)

    assert cooldown.blocked(TENANT_A) is False


def test_the_counts_are_bounded_like_the_deadlines() -> None:
    """Tenant ids come from a JWT claim, so the count map has the same cap."""
    cooldown = _cooldown(capacity=2, failure_threshold=2)
    cooldown.record_failure("tenant-1")
    cooldown.record_failure("tenant-2")
    cooldown.record_failure("tenant-3")  # drops tenant-1's count, the oldest

    assert cooldown.record_failure("tenant-1") is False
    assert cooldown.record_failure("tenant-3") is True


def test_configure_sets_the_threshold_and_keeps_it_when_left_out() -> None:
    cooldown = _cooldown()
    cooldown.configure(duration_sec=60.0, capacity=512, failure_threshold=3)
    cooldown.configure(duration_sec=60.0, capacity=512)

    cooldown.record_failure(TENANT_A)
    cooldown.record_failure(TENANT_A)
    assert cooldown.blocked(TENANT_A) is False
    cooldown.record_failure(TENANT_A)
    assert cooldown.blocked(TENANT_A) is True


def test_a_threshold_below_one_means_one() -> None:
    cooldown = _cooldown()
    cooldown.configure(duration_sec=60.0, capacity=512, failure_threshold=0)

    assert cooldown.record_failure(TENANT_A) is True


# --- the setting and the startup ---------------------------------------------


def test_the_setting_defaults_to_three_and_reads_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from config.settings import Settings

    monkeypatch.delenv("DB_COOLDOWN_FAILURE_THRESHOLD", raising=False)
    assert Settings().db_cooldown_failure_threshold == 3

    monkeypatch.setenv("DB_COOLDOWN_FAILURE_THRESHOLD", "1")
    assert Settings().db_cooldown_failure_threshold == 1


@pytest.fixture
def own_cooldown(monkeypatch: pytest.MonkeyPatch) -> Any:
    """A cooldown of this test's own, swapped in before the app starts."""
    cooldown = _cooldown()
    monkeypatch.setattr(api_app, "_db_cooldown", cooldown)
    return cooldown


def test_the_app_takes_the_threshold_from_settings_at_startup(own_cooldown, client) -> None:
    _ = client
    assert api_app._db_cooldown is own_cooldown

    assert own_cooldown.record_failure(TENANT_A) is False
    assert own_cooldown.record_failure(TENANT_A) is True


# --- the call sites, against a store slower than the timeout ----------------


class _SlowDb:
    """A session store that answers nothing within the timeout."""

    def __init__(self, state: dict[str, int]) -> None:
        self.state = state

    async def __aenter__(self) -> _SlowDb:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def execute(self, statement: Any) -> Any:
        _ = statement
        self.state["executes"] = self.state.get("executes", 0) + 1
        await asyncio.sleep(1.0)
        raise AssertionError("the timeout should have fired first")

    def add(self, record: Any) -> None:
        raise AssertionError(f"nothing is written past a failed lookup: {record!r}")

    async def commit(self) -> None:
        raise AssertionError("nothing is committed past a failed lookup")


@pytest.fixture
def slow_store(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    state: dict[str, int] = {}
    cooldown = _cooldown(failure_threshold=3)
    settings = SimpleNamespace(db_persist_timeout_sec=0.05)

    monkeypatch.setattr("db.engine.async_session", lambda: _SlowDb(state))
    monkeypatch.setattr(api_app, "_db_cooldown", cooldown)
    monkeypatch.setattr(api_app, "get_settings", lambda: settings)
    monkeypatch.setattr(
        conversation,
        "_app_module",
        lambda: SimpleNamespace(_db_cooldown=cooldown, get_settings=lambda: settings),
    )
    return SimpleNamespace(state=state, cooldown=cooldown)


def _supplied_id_refusal(tenant: str) -> HTTPException:
    """A caller-supplied session id this process has never seen."""
    with pytest.raises(HTTPException) as refused:
        asyncio.run(api_app._get_or_create_session(str(uuid.uuid4()), tenant))
    return refused.value


def test_a_slow_lookup_still_refuses_the_unverified_id_but_leaves_the_store_open(
    slow_store,
) -> None:
    refusal = _supplied_id_refusal(TENANT_A)

    assert (refusal.status_code, refusal.detail) == (503, "Session store temporarily unavailable")
    assert slow_store.state["executes"] == 1
    assert slow_store.cooldown.blocked(TENANT_A) is False

    # The next visitor is not refused unasked: the store is tried again.
    assert _supplied_id_refusal(TENANT_A).status_code == 503
    assert slow_store.state["executes"] == 2


def test_a_store_that_stays_slow_is_closed_after_the_threshold(slow_store) -> None:
    for _ in range(3):
        assert _supplied_id_refusal(TENANT_A).status_code == 503
    assert slow_store.cooldown.blocked(TENANT_A) is True

    assert _supplied_id_refusal(TENANT_A).status_code == 503
    assert slow_store.state["executes"] == 3, "a closed store is not asked"
    assert slow_store.cooldown.blocked(TENANT_B) is False


def test_a_slow_answer_write_leaves_the_store_open(slow_store) -> None:
    asyncio.run(
        conversation._persist_ask_messages(
            session_id=str(SESSION_UUID),
            tenant_id=TENANT_A,
            question="user-q",
            answer="assistant-a",
            path="test",
        )
    )

    assert slow_store.state["executes"] == 1
    assert slow_store.cooldown.blocked(TENANT_A) is False
