# Multi-replica session consistency SLA

## Goal

Choose the durable same-session concurrency contract that unblocks REL-03
without changing runtime behavior in this slice.

## Tasks

- [x] Measure the current boundary: history and mutation version are process-local, while PostgreSQL messages have no session version.
- [x] Check primary references for HTTP preconditions, PostgreSQL concurrency, and stale-writer fencing.
- [x] Record the accepted consistency, availability, latency, and failure contract in ADR 0006.
- [x] Add ADR 0006 to the architecture decision index and name the first implementation slice.
- [x] Verify local links, source URLs, whitespace, and the scoped diff.

## Done when

- [x] REL-03 has an explicit owner-approved design and measurable promotion criteria.
- [x] The document distinguishes this decision from implementation and live multi-replica evidence.

## Notes

This is a design-only atomic slice. It must not add a migration, change the API,
run live services, or claim REL-03 complete.
