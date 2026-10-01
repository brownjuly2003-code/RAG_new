# P2 — GPT-6-Astra xhigh reference grades on the blind human sample

Measured 2026-09-30 (late) under the [sample plan](../specs/p2-astra-reference-sample.md),
committed as `b0386e9` before the first corpus request. Astra graded all ten
selected H cases and all 50 documents. The
[ratings](../../reports/p2/astra-reference/ratings.json) and the
[human sample page](../../reports/p2/human-sample.html) use the same blind
D1–D5 document order in the table below. The saved `grades` field also retains
the original top-five order for comparison with the existing P2 judges and the
[Opus reference](p2-opus-reference-sample.md).

| Case | D1 | D2 | D3 | D4 | D5 |
|---|---:|---:|---:|---:|---:|
| aircargo-employment-contract-essential-terms | 1 | 3 | 1 | 2 | 3 |
| aircargo-breach-notification-required-fields | 1 | 0 | 3 | 1 | 0 |
| aircargo-trade-compliance-hold | 3 | 2 | 1 | 3 | 3 |
| aircargo-driver-job-documents | 3 | 1 | 2 | 2 | 1 |
| aircargo-dismissal-lawyer | 2 | 2 | 3 | 2 | 2 |
| aircargo-contract-termination-fields | 1 | 2 | 2 | 1 | 1 |
| aircargo-overtime-protected-categories | 1 | 1 | 1 | 3 | 1 |
| aircargo-sick-leave-required-fields | 1 | 2 | 3 | 1 | 2 |
| aircargo-matliab-check | 3 | 1 | 1 | 2 | 2 |
| aircargo-road-seal | 2 | 2 | 2 | 3 | 2 |

Grade counts (0/1/2/3) are **2/18/18/12**. Astra marked 30/50 documents
relevant (grade ≥2), and 9/10 cases contain a fully answering document. On
these same 50 units, quadratic-weighted κ is 0.8930 against Sonnet 5 (exact
agreement 42/50), 0.8824 against GLM 5.3 (42/50) and 0.9727 against Opus 5.5
(48/50). Astra and Opus differ on two units, each by one grade: D4 of
`aircargo-driver-job-documents` (Astra 2, Opus 1) and D5 of
`aircargo-sick-leave-required-fields` (Astra 2, Opus 1). These are descriptive
model-to-model comparisons; Julia's human grades are still pending, and
agreement between model families is not human validation.

## Provenance and checks

- H pool SHA-256 `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10`;
  human sample page SHA-256
  `1826759edf68c9e04dcb5bc7c90fa56d6e436234c8e25fcfb03df3db66f223ba`.
  Every case's exact blind request SHA-256 is in the ratings and raw store.
  The fixed P2 grading instruction SHA-256 is
  `7877c3845a742013e3c189e260ef506ba07dc65749fa3df8455a181a4dcedc33`;
  `build_request` was used unchanged.
- Collector `scripts/p2_astra_reference.py`, git blob
  `ce0a5d5a11574e68f1ac4511d339704801de9014`, committed together with this
  capsule. The collector was written by the MyFlow writer (Codex `cw`) after
  two GLM 5.3 direct failures; the session handoff records both attempts.
- Route: Codex CLI 0.159.2 through the companion `task` command on the
  owner's ChatGPT work profile, model `gpt-6-astra`, effort `xhigh`, provider
  `openai_retry5`, read-only sandbox, one fresh thread per case, working
  directory a fresh empty temporary directory outside the repository. The
  collector accepted a reply only after the thread's Codex rollout
  (`session_meta` + exactly one `turn_context`) reported that model, effort,
  sandbox and working directory; the rollout file name, job id and thread id
  of every case are in the raw store. Full arguments are in the
  [summary](../../reports/p2/astra-reference/summary.json).
- Threads (one per case, in sample order):
  `aircargo-employment-contract-essential-terms`
  `01a0f4ae-ab23-7a23-99b0-99cb960b1243`;
  `aircargo-breach-notification-required-fields`
  `01a0f4af-add1-7723-8a1a-36a66e7e546d`;
  `aircargo-trade-compliance-hold` `01a0f4b0-56b3-7640-b066-1a1f296e9745`;
  `aircargo-driver-job-documents` `01a0f4b1-0c61-7842-ac74-f714292eb017`;
  `aircargo-dismissal-lawyer` `01a0f4b1-d535-74d3-b778-bb58ba6567d2`;
  `aircargo-contract-termination-fields`
  `01a0f4b2-6b39-7b90-b0a7-056eac2f6466`;
  `aircargo-overtime-protected-categories`
  `01a0f4b3-05ea-7e03-8d28-ec08d2d04c83`;
  `aircargo-sick-leave-required-fields`
  `01a0f4b3-a9b8-7e51-a714-2d03f0a321e7`;
  `aircargo-matliab-check` `01a0f4b4-53fa-73f3-971c-f02792eb98fd`;
  `aircargo-road-seal` `01a0f4b5-0cd1-7341-9041-12a9ab242100`.
- Usage from the rollouts' last `token_count` event: 193,421 total tokens
  across the ten threads (18,757–19,669 per case), reasoning output 112–509
  tokens per case, 37–55 s per request; the summary was generated
  2026-09-30T23:45:36 UTC. No cost is reported: the work profile is a
  subscription route and the plan has no per-request price.
- [Raw reply store](../../reports/p2/astra-reference/replies.jsonl) SHA-256
  `6411f772c57629cb04118ba3e9892d1956b8c31db448229628fdf874458e5164`;
  ratings SHA-256 `9c49a997183f12203a6cbacdd78f9d029e5fcf2487280a73cb5b28650f45b7e3`;
  summary SHA-256 `95f6351ab27f84a89465ef2192ab00a29a55f0c12d4cbe004c192270fef4364d`.
  There are ten `graded` rows, zero missing or parse-failure rows, zero
  reused rows.
- `tests/test_p2_astra_reference_artifact.py` pins the store, reconstructs all
  grades from raw replies and blind shuffles, checks the 50 reasons, the
  summary, the D1–D5 ratings and this capsule's table, hashes, thread ids
  and κ lines. `tests/test_p2_astra_reference.py` covers sample selection,
  the pinned companion arguments, job-record parsing and rollout
  verification without the network.

## Limits

These are model reference grades, not human ground truth. They do not join the
pre-registered GLM/Sonnet P2 consensus, change its `RULER_DOES_NOT_TRACK`
verdict, change the calibration protocol of the development ruler, or change a
gate or retrieval default. The sample is ten cases selected across ruler
strata, not the full 100-case H pool. The raw store retains the response text,
thread and job ids, rollout file names and usage; the rollouts themselves live
in the owner's `CODEX_HOME` and are not in the repository, so the model,
effort and sandbox check can be replayed only there. The rollouts report
112–509 reasoning tokens per case, so `xhigh` did not turn into long
deliberation on these requests.
