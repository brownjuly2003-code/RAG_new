# Phase E demo — recording sheet

This is the recording plan and closing card for E.2, not the completed
three-minute screencast. Record against a running product with its real
`/api/ask`, trace store and admin Evidence endpoint. The shipment source in
this journey is the documented fixture TMS. Its observations are dated
2026-08-24, so today they fail the 300-second freshness check before policy
evaluation; the honest live story is the recorded escalation.

| Time | Screen | What to show |
|---|---|---|
| 0:00–0:15 | `phase-e-card.html` | Measured retrieval result and the explicit NO-SHIP verdict; no resolution-quality claim. |
| 0:15–1:05 | Chat | Ask `What is the status of shipment AC-100001?`; show the answer and its trace ID without calling the answer a verified resolution. |
| 1:05–2:30 | Admin Evidence | Open `/static/admin.html?trace_id=<id>` from that answer. Show the recorded stale-source reason and escalation handoff. Keep three 12–15-second hero shots: answer, evidence status, handoff. |
| 2:30–2:45 | Chat and admin | State that the shipment source is a fixture, the journey is off by default, and no real resolution quality is measured. |
| 2:45–3:00 | `phase-e-card.html` | Hold the closing card separately for editing. |

Before recording, verify the exact ask returns a nonempty trace ID and the
admin Evidence request for that ID returns the same journey with
`EVIDENCE_STALE`; adjust the script to the observed result if the fixture
changes. Keep credentials and local configuration out of the capture. The
card's numbers come from
[`GR-3`](../docs/evidence/gr3-graph-lane-ab.md): hybrid 0.5067, graph G2 0.5487
on the 100-case pool; the graph lane failed its default-on gate. The 100
questions are agent-written over real documents, and no real shipment-bound
resolution quality has been measured.
