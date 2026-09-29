# E.5 — local history secret scan (2026-09-29)

This is the secret-scan part of the pre-publication gate, run against local
`master` at `029f0b6` and every locally reachable ref. It does not close E.5:
the full suite, final CI result, and publication checks are separate gates.

## Scan and triage

- Gitleaks `8.30.1` was downloaded from its official release; the Windows
  archive matched the release SHA-256 checksum.
- `gitleaks git --log-opts='--all' --redact --no-banner .` scanned 1,076 commits
  and about 27.47 MB. The first run found 11 `generic-api-key` candidates.
- Review of each redacted match and its source context classified four as
  test fixture keys or idempotency values, five as documentation/template
  text, and two as local CI/migration test keys. The `.env.example` matches
  span an empty `GRACEKELLY_API_KEY` field and adjacent configuration fields;
  the historical Mistral command uses a three-character example value.
- [`.gitleaksignore`](../../.gitleaksignore) records only those 11 exact
  commit/path/rule/line fingerprints. It does not disable the generic rule.
  The second full-history scan exited 0 with **no unallowlisted findings**.

## Local credential and file-path checks

- `git log --all --name-only --format=` yielded `.env.example` as the only
  environment-shaped or `TXT/` path. No `.env` or `D:/TXT` file was tracked in
  the reachable history; no local `.env` file existed at scan time.
- A local, uncommitted script read 124 `D:/TXT/*.txt` files without printing
  their contents. It extracted 32 credential-shaped values from assignments,
  known token prefixes, and credential-named files, then compared them in
  memory with 36,924,322 bytes from
  `git log --all --patch --root --format=`. **Zero exact matches** were found.

The last check covers extracted values in text patches; it cannot prove the
absence of every possible secret format or data hidden only in binary blobs.
Rerun the scan on the final publication commit and all refs before making the
repository public. Keep raw keys and unredacted scan reports out of Git.
