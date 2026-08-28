"""Phase A.3 — the Evidence tab, at the endpoint and on the page.

`tests/test_evidence_view.py` holds the join. These hold the two things around
it: that `GET /api/admin/traces/{trace_id}/evidence` is a tenant-scoped,
role-gated read that answers honestly for a trace with no journey, and that the
admin page actually carries the surface — the view switch, the export button
and the pane they drive.

The page assertions are deliberately about text a reader would see rather than
about a 200: a static file served successfully with the Evidence markup
missing is exactly the regression these are for.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from auth.jwt_handler import create_access_token
from resolution.persistence import POLICY_REQUIREMENT_ID, SOURCE_REQUIREMENT_ID

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TRACE_ID = "abc12345"
_STEP_TS = "2026-08-25T12:00:00+00:00"
_SOURCE_DIGEST = "a" * 64
_POLICY_DIGEST = "b" * 64


def _auth(tenant: str = "default", role: str = "admin") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token('u-' + tenant, role, tenant)}"}


def _shadow_trace() -> dict[str, Any]:
    return {
        "trace_id": _TRACE_ID,
        "started_at": "2026-08-25T11:59:58+00:00",
        "finished_at": _STEP_TS,
        "steps": [
            {
                "order": 1,
                "node": "resolution_shadow",
                "ts": _STEP_TS,
                "state": {
                    "journey": "shipment-status",
                    "reason_codes": ["shipment.status.known"],
                    "evidence": {
                        "mode": "shadow",
                        "tenant_id": "default",
                        "case_id": "11111111-2222-3333-4444-555555555555",
                        "case_version": 2,
                        "correlation_id": "66666666-7777-8888-9999-000000000000",
                        "terminal_state": "verified_resolution",
                        "reason_codes": ["shipment.status.known"],
                        "contract": {
                            "schema_identity": "resolution-contract/v0.1",
                            "contract_id": "aircargo.shipment-status",
                            "version": "0.1.0",
                            "digest": "c" * 64,
                        },
                        "source_observation": {
                            "shipment_id": "AC-100001",
                            "status": "in_transit",
                            "location": "Frankfurt",
                            "estimated_delivery": "2026-08-27",
                            "observed_at": "2026-08-25T11:30:00+00:00",
                            "source_id": "fixture-tms",
                            "source_version": "0.1.0",
                            "content_digest": _SOURCE_DIGEST,
                        },
                        "policy": {
                            "implementation_version": "1.2.0",
                            "data_revision": "2026-08-01",
                            "authority": "aircargo-policy",
                            "content_digest": _POLICY_DIGEST,
                            "decision": "disclose_status",
                            "recorded_at": "2026-08-20T09:00:00+00:00",
                            "valid_from": "2026-08-01T00:00:00+00:00",
                            "valid_to": None,
                        },
                        "claim_links": [
                            {
                                "claim_id": "status",
                                "text": "Shipment AC-100001 is in transit.",
                                "evidence_requirement_ids": [
                                    SOURCE_REQUIREMENT_ID,
                                    POLICY_REQUIREMENT_ID,
                                ],
                                "evidence_digests": [_SOURCE_DIGEST, _POLICY_DIGEST],
                            }
                        ],
                        "postcondition_versions": [],
                        "escalation_brief": None,
                    },
                },
            }
        ],
        "feedback": [],
    }


@pytest.fixture
def trace_store(monkeypatch: pytest.MonkeyPatch):
    """Stand in for the SQLite trace store, recording how it was called."""
    state: dict[str, Any] = {"trace": _shadow_trace(), "calls": []}

    def _get_trace_detail(trace_id: str, tenant_id: str | None = None):
        state["calls"].append((trace_id, tenant_id))
        return state["trace"]

    monkeypatch.setattr(
        "tracing.sqlite_trace.get_trace_detail", _get_trace_detail, raising=False
    )
    return state


# --- the endpoint -----------------------------------------------------------


def test_the_evidence_behind_an_answer_is_readable_over_http(
    trace_store, client_with_key: TestClient
) -> None:
    response = client_with_key.get(
        f"/api/admin/traces/{_TRACE_ID}/evidence", headers=_auth()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trace_id"] == _TRACE_ID
    (journey,) = body["journeys"]
    assert journey["contract"]["version"] == "0.1.0"
    assert journey["policy"]["detail"]["decision"] == "disclose_status"
    assert journey["terminal_state"] == "verified_resolution"
    # The join the raw trace cannot do: a claim next to the evidence under it,
    # with the age that evidence had when it was read.
    (claim,) = journey["claims"]
    assert [source["kind"] for source in claim["sources"]] == ["observation", "policy"]
    assert claim["sources"][0]["age_seconds"] == 1800.0
    assert journey["replay_receipt"]["source_digest"] == _SOURCE_DIGEST


def test_the_read_is_scoped_to_the_callers_tenant(
    trace_store, client_with_key: TestClient
) -> None:
    """A trace belongs to a tenant; the evidence in it does too."""
    client_with_key.get(f"/api/admin/traces/{_TRACE_ID}/evidence", headers=_auth("acme"))

    assert trace_store["calls"] == [(_TRACE_ID, "acme")]


def test_a_trace_that_ran_no_journey_answers_with_an_empty_list(
    trace_store, client_with_key: TestClient
) -> None:
    """The common case — the shadow is off by default — must not look like a failure."""
    trace_store["trace"] = {
        "trace_id": _TRACE_ID,
        "started_at": _STEP_TS,
        "steps": [{"order": 0, "node": "generate", "state": {}, "ts": _STEP_TS}],
        "feedback": [],
    }

    response = client_with_key.get(
        f"/api/admin/traces/{_TRACE_ID}/evidence", headers=_auth()
    )

    assert response.status_code == 200
    assert response.json()["journeys"] == []
    assert response.json()["shadow_status"] == "shadow_disabled"


def test_an_unknown_trace_is_a_404(monkeypatch, client_with_key: TestClient) -> None:
    monkeypatch.setattr(
        "tracing.sqlite_trace.get_trace_detail",
        lambda trace_id, tenant_id=None: None,
        raising=False,
    )

    response = client_with_key.get(
        f"/api/admin/traces/{_TRACE_ID}/evidence", headers=_auth()
    )

    assert response.status_code == 404


def test_a_malformed_trace_id_never_reaches_the_store(
    monkeypatch, client_with_key: TestClient
) -> None:
    def _unexpected(trace_id: str, tenant_id: str | None = None):
        raise AssertionError(f"trace lookup must not happen for invalid id: {trace_id}")

    monkeypatch.setattr("tracing.sqlite_trace.get_trace_detail", _unexpected, raising=False)

    response = client_with_key.get(
        "/api/admin/traces/'; DROP TABLE traces--/evidence", headers=_auth()
    )

    assert response.status_code in (400, 404)


def test_the_evidence_read_needs_a_role(trace_store, client_with_key: TestClient) -> None:
    response = client_with_key.get(f"/api/admin/traces/{_TRACE_ID}/evidence")

    assert response.status_code in (401, 403)
    assert trace_store["calls"] == []


# --- the surface on the page ------------------------------------------------


def test_the_admin_page_carries_the_evidence_view(client_with_key: TestClient) -> None:
    """A 200 on a static file proves nothing; the markup is what a reader gets."""
    page = client_with_key.get("/static/admin.html")

    assert page.status_code == 200
    assert 'id="btn-trace-evidence"' in page.text
    assert 'id="btn-export-evidence"' in page.text
    assert 'id="trace-evidence"' in page.text


def test_the_admin_script_fetches_and_renders_the_evidence() -> None:
    js = (PROJECT_ROOT / "static" / "admin.js").read_text(encoding="utf-8")

    assert '"/api/admin/traces/" + encodeURIComponent(traceId) + "/evidence"' in js
    # Every section A.3 owes a reviewer.
    for heading in (
        "Contract",
        "Outcome",
        "Policy decision",
        "Claims and the evidence behind them",
        "Postconditions",
        "Replay receipt",
    ):
        assert f'"{heading}"' in js, f"the Evidence view lost its {heading} section"
    # An evidence bundle carries source text; innerHTML would make a shipment
    # status an injection point.
    evidence_block = js.split("Phase A.3", 1)[1].split("btn-load-traces", 1)[0]
    assert ".innerHTML" not in evidence_block
    assert "application/json" in js and "link.download" in js
    for status_copy in (
        "Resolution shadow was disabled for this trace.",
        "This request did not enter the journey; no source or policy was called.",
        "The resolution producer failed before it could record evidence.",
    ):
        assert status_copy in js


def test_the_evidence_pane_has_styles_of_its_own() -> None:
    css = (PROJECT_ROOT / "static" / "admin.css").read_text(encoding="utf-8")

    assert ".evidence" in css
    assert "#trace-views button.selected" in css
