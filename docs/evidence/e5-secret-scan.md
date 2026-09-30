# E.5 — local pre-publication verification (2026-09-30)

Local verification covers the test tree committed at
`c81de7743f1f7805796d2e15133f50ea43dae879` and every locally reachable ref.
The Mac ran `236f7c1c1e97ae41f6303b46a535207ee1112f9e` plus the two exact test
files pinned below; that tree equals `c81de77`. This is publication preparation.
E.4/E.5 remain open for CI, the conditional checks listed below and publication.

## Scan and triage

- Gitleaks `8.30.1` was downloaded from its official release; the Windows
  archive matched the release SHA-256 checksum.
- `gitleaks git --log-opts='--all' --redact --no-banner .` scanned 1,082 commits
  and 27,510,724 bytes on `c81de77`, exiting 0 with no unallowlisted findings.
  The initial 2026-09-29 scan found 11 `generic-api-key` candidates.
- Review of each redacted match and its source context classified four as
  test fixture keys or idempotency values, five as documentation/template
  text, and two as local CI/migration test keys. The `.env.example` matches
  span an empty `GRACEKELLY_API_KEY` field and adjacent configuration fields;
  the historical Mistral command uses a three-character example value.
- [`.gitleaksignore`](../../.gitleaksignore) records only those 11 exact
  commit/path/rule/line fingerprints. It does not disable the generic rule.
  The initial rescan and the fresh `c81de77` scan both exited 0 with
  **no unallowlisted findings**.

## Local credential and file-path checks

- `git log --all --name-only --format=` yielded `.env.example` as the only
  environment-shaped or `TXT/` path. No `.env` or `D:/TXT` file was tracked in
  the reachable history; no local `.env` file existed at scan time.
- A local, uncommitted script read 124 `D:/TXT/*.txt` files without printing
  their contents. It extracted 32 credential-shaped values from assignments,
  known token prefixes, and credential-named files, then compared them in
  memory with 37,006,809 bytes from
  `git log --all --patch --root --format=`. **Zero exact matches** were found.

The credential check covers extracted values in text patches; it cannot prove
the absence of every possible secret format or data hidden only in binary blobs.

## Mac test provenance

- Intel iMac, macOS 13.7.8, Python 3.11.15; dependency overlays include
  `jsonschema 4.26.0`, `chromadb 1.5.9`, `langchain-chroma 1.1.0` and
  Playwright 1.58.0. Browser tooling uses Node 24.21.0, npm 11.19.0 and
  axe CLI 4.13.0. PostgreSQL is 16.15 (Homebrew).
- Corpus manifest: `evaluation/aircargo_corpus.manifest.json`, **201 documents**,
  SHA-256 `c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343`.
  The local corpus and the transferred Mac corpus both passed manifest verification.
- The runner checked the exact base commit, allowed only the following dirty
  test files and checked their SHA-256 before every run:

| File | SHA-256 |
|---|---|
| `tests/test_admin_trace_evidence.py` | `a4f250f1a58f90d93f8da8c3a4d659154c8fce8715df6f940f82beb155b54ac6` |
| `tests/test_p2_blinded_judge_artifact.py` | `e8087e27749005ec0154e785244ca1e8edac58588b07b5a88773f4989e8b0675` |

The admin assertion follows the shared detail/evidence path introduced by
`a4d5e63`; the browser regression checks the actual requests and rendered result.
P2 checks float metrics with `rel=1e-12, abs=1e-15` and exact keys, counts and
nested data. Its replay uses compensated sums to preserve the publication's
rank ties on Python 3.11. A diagnostic on the same grades found native
Python 3.11 tau 0.1572364137739849, native Python 3.14 tau 0.1561363268700062,
and compensated tau 0.1561363268700062 on both. The pinned evaluator and report
digests still pass; the published verdict is `RULER_DOES_NOT_TRACK`.

## Fresh verification results

The unit suite's attempt 3/5 passed after restoring the corpus and correcting
the two assertions. PostgreSQL attempt 1 failed at async connections because
the local admin DSN's `sslmode=disable` is not an asyncpg keyword. The runner
omitted that parameter only for localhost test connections; the original
failing action test then passed, followed by integration attempt 2/5. Each run
created a separate scratch database; tests created their own disposable databases.

| Check | Result |
|---|---|
| Full unit suite, excluding `tests/integration`, with coverage | **3,763 passed, 16 skipped**, exit 0; 499.53 s; coverage **77.78%**, required 72% |
| `tests/integration` against PostgreSQL | **93 passed, 1 skipped**, exit 0; 60.52 s |
| Three original failing test files | **15 passed**, exit 0; 16.32 s |
| `scripts/qa/test_admin_trace_lookup_ui.py` in Chromium | **1 passed**, exit 0; 5.47 s; ID entry and direct link, exact detail/evidence requests |
| P2 replay alone on Windows Python 3.14.6, `--noconftest` | **3 passed**, exit 0; 22.96 s |
| Ruff on the two changed test files | **All checks passed**, exit 0 |

Commands, run from the pinned tree with the configured Mac environment:

```text
python -m pytest tests/ -q -p no:cacheprovider -ra --tb=short --timeout=240 --timeout-method=thread --ignore=tests/integration --cov --cov-report=term
python -m pytest tests/integration -q -p no:cacheprovider -ra --tb=short --timeout=240 --timeout-method=thread
python -m pytest tests/test_admin_trace_evidence.py tests/test_gr_multihop_cases.py tests/test_p2_blinded_judge_artifact.py -q -p no:cacheprovider -ra --tb=short --timeout=240 --timeout-method=thread
python -m pytest scripts/qa/test_admin_trace_lookup_ui.py -q -p no:cacheprovider -ra --tb=short --timeout=240 --timeout-method=thread
python scripts/corpus_manifest.py verify --manifest evaluation/aircargo_corpus.manifest.json
```

Redacted local logs are retained under the ignored `.tmp/e5-scan/`, including
`mac-unit-236f7c1-3.log`, `integration-2.log`, `ui-check-1.log` and
`focused-green-compensated.log`. The configured runner and dependency overlays
are local verification aids.

## Conditional checks completed separately

Follow-up source: `813398c01c829127cafbdcc2fdc91e0d74022d72` plus
`scripts/autopilot.ps1` SHA-256
`6f47d55cf2200c0b19782fc9c1d64e14ab7a5e20381b543a19bba1b6d8315662`.
The original full-suite counts above are unchanged; these are separate checks.

- Windows Python 3.14.6, PowerShell 5.1.26100.9444: **9 passed**, exit 0,
  54.63 s. Attempt 1 failed the planner-timeout case (8 passed, 1 failed):
  loading the child PowerShell profile took 4,349 ms against a 1 s timeout;
  startup without the profile took 236 ms. GLM 5.3 (direct Responses, `xhigh`)
  supplied the `-NoProfile` launch change; attempt 2 passed every existing test.
- Mac Python 3.11.15: **5 passed**, exit 0, 2.76 s, attempt 1: three `age`
  encryption/restore tests and both previously skipped pinned-pool checks.
  `age` v1.3.2 was installed only in the verification tools directory; its
  official `darwin-amd64` release asset digest matched SHA-256
  `1d1e4bc66e1427edad7739ae7616157de0e79db8b6d2a1497d7d9925fb06a539`.
  The restored pool was byte-identical: 7,692,098 bytes, SHA-256
  `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10`.

Both checks disabled plugin autoload and used the standard pytest fixtures:

```text
python -m pytest tests/test_autopilot_runner.py --noconftest -q -p no:cacheprovider -ra --tb=short
python -m pytest tests/test_backup_snapshot_encryption.py tests/test_restore_verify_encryption.py tests/test_section_coherence_arm.py::test_no_pool_candidate_carries_the_page_marker_at_all tests/test_section_coherence_arm.py::test_the_parser_agrees_with_the_pool_on_every_candidate --noconftest -q -p no:cacheprovider -ra --tb=short
```

Logs: Windows `.tmp/e5-scan/windows-autopilot-20260930-2.log`; Mac
`/Users/julia/RAG_new_e5_conditional_813398c_20260930/.tmp/conditional-1.log`.
This closes conditional verification gaps, not a new product or quality slice.

## Remaining gates

- Of the original 16 unit skips, the nine Windows, three `age` and two
  pinned-pool checks passed separately above. The child-only Chroma restart
  entry is intentional; its parent ran. The Docker restore check and the
  integration `test_regression_eval_live.py` remain unrun: the Mac lacks the
  Python Docker module, and `docker info` exited 1 because its configured
  Colima daemon socket does not exist. Both suites report the existing
  Starlette/AnyIO deprecation warning.
- GitHub Actions is unavailable until early October 2026. The CI matrix,
  security/build gates and Pages deployment have not been rerun for this tree.
- The repository remains private; the prepared **RAG assistant** site at
  `/RAG_new/`, public links and proof-pack still need publication verification.
- Scan the evidence commit and all refs after committing this record, then
  repeat on the final publication commit if it differs. Keep raw keys and
  unredacted scan reports out of Git; reports stay in `.tmp/e5-scan/`.
