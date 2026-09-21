# C.3 — contract-shaped HTTP answers

2026-09-21 · Evidence class: **synthetic** · Rule (a), synchronous `/api/ask`.

The first C.3 step now replaces the inherited answer only when both
`RESOLUTION_SHADOW_JOURNEYS` and `RESOLUTION_RESPONSE_JOURNEYS` name
`shipment-status`. Both default to empty. The later [manual copilot slice](c3-copilot-contract-draft.md)
completes the second C.3 step. No production flag was enabled.

## Contract and observable behavior

The existing shipment contract `0.1.0` and its canonical digest are unchanged.
The new `shipment-status-response.json` is contract `0.2.0`, schema
`resolution-contract/v0.1`, with response shape `1.0.0`. Its canonical digest is
`4f0daf1c5410dfecec1d382e1fbb83f0d540a5337971c175b5c34220e31be31a`.

Ordered slots are status, location and estimated delivery. Each names its
claim and the shipment observation/policy evidence requirements. Unsupported
candidates are removed before compilation. No supported claim means escalation.
The endpoint projects only a complete VERIFIED shape from the pinned contract,
rechecking claim text and evidence digests; arbitrary producer response text
cannot become the answer.

Projected answers start `Fixture TMS. AI assistance.` Legacy citations,
sources, suggestions, actions and ticket state are cleared; quality score `0`
means unmeasured. Session history and persistence receive the projected answer.
Shadow evidence is collected and persisted once. Declined, stale, denied,
failed or tampered results retain the legacy answer. With projection disabled,
HTTP response bytes remain identical with the shadow off and on.

## Verification

GLM 5.3 supplied implementation with requested `xhigh`; the coordinating agent
reviewed patches, rejected incorrect attribute accesses and verified the corrected
result independently. Red tests preceded implementation: the enabled HTTP test
returned the legacy answer; 16 new unit cases failed on missing capabilities.

Mac checkout: `/Users/julia/RAG_new_c3_20260921`, baseline `19ebac5` plus this
slice's patch. Python: `/Users/julia/RAG_new_gr4_venv/bin/python`.

- `python -m pytest -q tests/test_resolution*.py tests/test_shipment*.py
  tests/test_session*.py tests/test_conversation_router.py
  tests/test_conversation_encoding.py tests/integration/test_shipment_status_e2e.py
  tests/integration/test_conversation.py` — **504 passed**.
- `python -m ruff check .` and
  `python -m resolution.contracts.schema --check` — exit 0.
- Both CI mypy commands (core paths and API/vector paths, `--no-incremental`)
  — exit 0, **138 + 31 source files**.
- `python -m pytest tests/integration/test_session_turns_e2e.py
  tests/integration/test_resolution_shadow_postgres.py -q -rs --tb=short`
  — **12 passed** against disposable databases on the existing Mac PostgreSQL
  at loopback port 55432. The test environment uses its async driver and the
  virtualenv PATH. This covers existing database integration; it does not claim
  a new PostgreSQL E2E combining the response flag with durable turns.

The new HTTP assertions cover answer content, trace evidence readback, contract
version, claim resolution, session history, one evidence persistence call and
off parity. Unit assertions reject altered claims, digests, contract identities,
policy decisions and terminal states. Existing schema/golden tests guard the
original contract identity. Mac logs: `RAG_new_c3_gate_0.log` through `_4.log`.

## Limits

This is fixture TMS evidence, with no real shipment connector or new quality
measurement. Legacy pipeline execution still precedes the deterministic answer.
Streaming and copilot drafts were unchanged in this first slice. GitHub Actions remains unavailable;
the checks above ran on the Mac. Windows ran no containers, VMs or full suite.
