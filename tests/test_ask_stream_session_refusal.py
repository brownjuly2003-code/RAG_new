"""Session refusals on the stream routes arrive before the first byte.

``_get_or_create_session`` refuses with 404 (a session of another tenant) and
503 (the session store is in cooldown and the caller's id cannot be verified).
Raised after the stream's first ``status`` event, the refusal found the
response already started: the client got a 200 stream that ended after
``status`` with neither ``error`` nor ``result`` — seen on the Mac on
2026-10-14 under swap. Each refusal must reach the client as the plain HTTP
error ``/api/ask`` returns, with no SSE body. (A malformed id never gets that
far: the request model rejects it with 422 before the route runs.)
"""

from __future__ import annotations

import importlib
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from auth.jwt_handler import create_access_token

api_app = importlib.import_module("api.app")

# A refusal after the response started is a server exception; the client's view
# of it (status 200, a cut stream) is what these tests must rule out.
CLIENT_RAISE_SERVER_EXCEPTIONS = False

TENANT_A = "tenant-a"
TENANT_B = "tenant-b"
SECRET_CONTENT = "SECRET-CROSS-TENANT-PAYLOAD-NEVER-LEAK"
STREAM_ROUTES = ("/api/ask/stream", "/api/chat/stream")


def _auth(tenant: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token('u-' + tenant, 'agent', tenant)}"}


def _assert_plain_refusal(response, status: int, detail: str) -> None:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/json"), response.headers
    assert "data:" not in response.text
    assert response.json()["detail"] == detail


class _OwnedSession:
    def __init__(self, tenant_id: str) -> None:
        self._tenant_id = tenant_id
        self._history = [{"role": "user", "content": SECRET_CONTENT}]
        self._max_history = 20


@pytest.mark.parametrize("route", STREAM_ROUTES)
def test_stream_cooldown_unverified_session_is_a_plain_503(client: TestClient, route: str) -> None:
    api_app._db_cooldown.trip(TENANT_A, duration_sec=3600.0)
    api_app._session_llm_state.clear()
    api_app._session_last_access.clear()
    cooldown_before = api_app._db_cooldown.retry_after(TENANT_A)
    supplied = uuid.uuid4()

    response = client.post(
        route,
        json={"question": "hello during outage", "session_id": str(supplied)},
        headers=_auth(TENANT_A),
    )

    _assert_plain_refusal(response, 503, "Session store temporarily unavailable")
    assert supplied.hex not in api_app._session_llm_state
    assert supplied.hex not in api_app._session_last_access
    assert api_app._db_cooldown.retry_after(TENANT_A) == cooldown_before


@pytest.mark.parametrize("route", STREAM_ROUTES)
def test_stream_session_of_another_tenant_is_a_plain_404(client: TestClient, route: str) -> None:
    api_app._db_cooldown.trip(TENANT_B, duration_sec=3600.0)
    owned = _OwnedSession(TENANT_A)
    session_hex = uuid.uuid4().hex
    api_app._session_llm_state[session_hex] = owned
    api_app._session_last_access[session_hex] = time.monotonic()

    response = client.post(
        route,
        json={"question": "hijack?", "session_id": session_hex},
        headers=_auth(TENANT_B),
    )

    _assert_plain_refusal(response, 404, "Session not found")
    assert SECRET_CONTENT not in response.text
    assert api_app._session_llm_state.get(session_hex) is owned
    assert owned._tenant_id == TENANT_A
