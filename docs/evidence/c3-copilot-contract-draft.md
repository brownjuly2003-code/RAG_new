# C.3 — contract-shaped manual copilot drafts

2026-09-21 · Evidence class: **synthetic** · Baseline: `6e8b805`.

Manual `POST /api/escalate` now fills `ai_draft` with the same validated
shipment-status response shape as `/api/ask`, only when both existing
`RESOLUTION_SHADOW_JOURNEYS` and `RESOLUTION_RESPONSE_JOURNEYS` enable the
journey. Both remain off by default. The operator reads that draft through
`GET /api/agent/tickets/{id}`; the existing copilot UI uses that field.

The handler gathers fresh evidence for the authenticated tenant, question,
session and request correlation. It reuses the existing shadow runner,
contract projection and bounded evidence persistence. It adds no second
validator, contract, model call or setting. The contract and digest are those
of the [HTTP slice](c3-contract-shaped-response.md).

The customer still receives the escalation outcome. Ticket creation,
delivery state and idempotency inputs are unchanged. Stale, denied, declined,
failed, missing-ID, empty-question and foreign-tenant inputs retain the legacy
draft. A failed durable ticket insert still returns HTTP 500.

## Verification

GLM 5.3 supplied the handler patch via direct API with requested `xhigh`,
confirmed model `glm-5.3` and `stop_reason=end_turn`. The coordinator reviewed
it, replaced session-based correlation with the current request ID, and wrote
independent acceptance tests. A larger request timed out; a separate test
request exhausted its token budget without text. Neither result was applied.

Mac checkout: `/Users/julia/RAG_new_c3_copilot_20260921`, exported baseline
`6e8b805` plus the scoped patch. Interpreter:
`/Users/julia/RAG_new_gr4_venv/bin/python`.

- Before implementation, `python -m pytest -q
  tests/integration/test_shipment_status_e2e.py -k copilot`: **1 failed,
  10 passed**. The failing assertion saw the generic draft instead of the
  exact contract answer. Log: `RAG_new_c3_copilot_red_final.log`.
- After implementation: **555 passed**, covering resolution, shipment,
  sessions, conversation, escalation services/error paths, agent endpoints,
  HTTP integration and documentation hygiene. This includes 12 new copilot
  cases. Command list: `RAG_new_c3_copilot_gates.sh`; results:
  `RAG_new_c3_copilot_gate_3.log` on the Mac.
- `python -m ruff check .`: exit 0. Both CI strict mypy commands:
  **138 + 31 source files**, exit 0 (`gate_0.log` through `gate_2.log`).

## Limits

Tests exercise real HTTP routing and the fixture journey; ticket storage and
delivery use test doubles, and resolution persistence is captured at its seam.
Agent detail readback proves the API contract, not a new PostgreSQL round trip
or browser interaction. Evidence is fixture-sourced, with no quality metric
improvement claimed. Automatic/error/email drafts and streaming are unchanged.
GitHub Actions was unavailable; checks ran on Mac, without Windows containers.
