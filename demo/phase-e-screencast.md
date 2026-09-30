# Phase E demo — recorded walkthrough

`phase-e-demo.mp4` is a three-minute, silent screencast with burned-in Russian
captions. It records a real `/api/ask` request, its trace ID, and the admin
Evidence view from an isolated local checkout. The long response wait and idle
screen time were cut; the waiting caption states this. The source recording is
kept locally as `phase-e-raw.webm`, and `render_phase_e.ps1` plus
`phase-e-captions.ass` describe the edit.

| Time | Recorded screen | Fact shown |
|---|---|---|
| 0:00–0:15 | Intro card | Measured retrieval result and explicit NO-SHIP verdict. |
| 0:15–0:45 | Live `/api/ask` page | Submit `What is the status of shipment AC-100001?`; waiting time shortened. |
| 0:45–1:43 | Answer and link | `The status of shipment AC-100001 is pending. [N/A]`; route `human`; trace ID `6d1fd33d-b2df-409e-9ee8-3df4f01a3f75`; open Evidence from the link. |
| 1:43–2:45 | Admin Evidence | `escalated`, `EVIDENCE_STALE`, handoff, `source: fail (source_stale)`, `policy: not_observed`. |
| 2:45–3:00 | Closing card | Retrieval numbers and NO-SHIP verdict. |

The shipment source is a fixture TMS observed on 2026-08-24; its data fail
the 300-second freshness check before policy evaluation. The shipment journey
is off by default. This is a recorded escalation, not a verified resolution,
and no real shipment-bound resolution quality has been measured. The card's
numbers come from
[`GR-3`](../docs/evidence/gr3-graph-lane-ab.md): hybrid 0.5067, graph G2 0.5487
on the 100-case pool; the graph lane failed its default-on gate. The 100
questions are agent-written over real documents.
