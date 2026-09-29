# P2 — Opus 5.5 max reference grades on the blind human sample

Measured 2026-09-29 under the [sample plan](../specs/p2-opus-reference-sample.md),
committed before the first corpus request. Opus graded all ten selected H cases
and all 50 documents. The [ratings](../../reports/p2/opus-reference/ratings.json)
and [human sample page](../../reports/p2/human-sample.html) use the same blind
D1–D5 document order in the table below. The saved `grades` field also retains
the original top-five order for comparison with existing P2 judges.

| Case | D1 | D2 | D3 | D4 | D5 |
|---|---:|---:|---:|---:|---:|
| aircargo-employment-contract-essential-terms | 1 | 3 | 1 | 2 | 3 |
| aircargo-breach-notification-required-fields | 1 | 0 | 3 | 1 | 0 |
| aircargo-trade-compliance-hold | 3 | 2 | 1 | 3 | 3 |
| aircargo-driver-job-documents | 3 | 1 | 2 | 1 | 1 |
| aircargo-dismissal-lawyer | 2 | 2 | 3 | 2 | 2 |
| aircargo-contract-termination-fields | 1 | 2 | 2 | 1 | 1 |
| aircargo-overtime-protected-categories | 1 | 1 | 1 | 3 | 1 |
| aircargo-sick-leave-required-fields | 1 | 2 | 3 | 1 | 1 |
| aircargo-matliab-check | 3 | 1 | 1 | 2 | 2 |
| aircargo-road-seal | 2 | 2 | 2 | 3 | 2 |

Grade counts (0/1/2/3) are **2/20/16/12**. Opus marked 28/50 documents
relevant (grade ≥2), and 9/10 cases contain a fully answering document. On
these same 50 units, quadratic-weighted κ is 0.8950 against Sonnet 5 and
0.9133 against GLM 5.3. These are descriptive model-to-model comparisons;
Julia's human grades are still pending.

## Provenance and checks

- H pool SHA-256 `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10`;
  human sample page SHA-256
  `1826759edf68c9e04dcb5bc7c90fa56d6e436234c8e25fcfb03df3db66f223ba`.
  Every case's exact blind request SHA-256 is in the ratings and raw store.
- Collector code commit `9229a35be6f1c07911e606ab9eb13202e16e7344`;
  collector script git blob `61dd3197d468758ce5480c45abd5bc2de5a3acc7`.
  The fixed P2 grading instruction SHA-256 is
  `7877c3845a742013e3c189e260ef506ba07dc65749fa3df8455a181a4dcedc33`.
- Claude Code CLI 2.1.283, `claude-opus-5-5`, `--effort max`, first-party
  Claude Max route, no model fallback, no tools, one fresh session per case.
  Each CLI response passed an exact canonical-model and provider check.
  Full arguments are in the [summary](../../reports/p2/opus-reference/summary.json).
- [Raw reply store](../../reports/p2/opus-reference/replies.jsonl) SHA-256
  `f17b1b973249365ba51a5e0c476024e7933de698ffeb2cf29b32ea1ff1aa3a8f`;
  ratings SHA-256 `1332b3213be5ec3e4d6b75fd93563a78298b006023e97576a910b5caddc14681`;
  summary SHA-256 `d785df2672b7cb24398b15a3be6695f9d498003ed773ce22b564544d606ac04d`.
  There are ten `graded` rows, zero missing or parse-failure rows.
- `tests/test_p2_opus_reference_artifact.py` pins the store, reconstructs all
  grades from raw replies and blind shuffles, checks the 50 reasons, and checks
  the summary and D1–D5 ratings. The collector tests cover sample selection,
  model validation, and CLI flags.

## Limits

These are model reference grades, not human ground truth. They do not join the
pre-registered GLM/Sonnet P2 consensus, change its `RULER_DOES_NOT_TRACK`
verdict, or change a gate or retrieval default. The sample is ten cases selected
across ruler strata, not the full 100-case H pool. The raw reply store retains
the response text, reported model id and usage; it does not retain the full
outer CLI envelope. The collector verified that envelope before accepting each
reply, but its provider field cannot be independently replayed from the store.
