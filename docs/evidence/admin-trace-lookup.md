# Admin trace lookup (2026-09-29)

An operator can paste a known trace ID into the Traces tab or open
`/static/admin.html?trace_id=<id>`. The page requests that exact trace and its
Evidence view without requiring it to appear in the recent-traces list. The
existing list Details action uses the same requests and keeps its selected view.

## Verification

- `scripts/qa/test_admin_trace_lookup_ui.py` failed before the change because
  the Trace ID field did not exist, then passed after it. Real Chromium loads
  the checked-in admin HTML and JavaScript; fixture HTTP responses stand in for
  the authenticated admin API. It checks the manual and direct-link paths and
  the exact detail and evidence requests.
- `scripts/qa/test_graph_evidence_ui.py` passed after the change, covering the
  existing list Details action and Evidence rendering.
- `node --check static/admin.js` and `git diff --check` passed.

The browser checks prove UI wiring against fixture responses. They do not test
live authentication, the admin backend, or resolution quality. Those backend
contracts remain covered by their separate integration tests.
