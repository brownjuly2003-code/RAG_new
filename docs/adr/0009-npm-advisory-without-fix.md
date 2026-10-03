# ADR 0009 — An npm advisory with no fixed release: one dated exception, by advisory id

- Status: Accepted and implemented on 2026-10-03 (slice 0.1b, task T-74).
- Date: 2026-10-03
- Decided by: agent, under explicit delegation ("все решения на тебе"). Julia can
  overrule any of it; the reasoning is written out here so overruling is cheap.
- Related: [ADR 0008](0008-inherited-ci-red-disposition.md) (CI-RED-2, the same
  question for `pip-audit`), `docs-site/npm-audit-exceptions.json`,
  `docs-site/scripts/check-npm-audit.mjs`, `.github/workflows/docs-site.yml`,
  `docs/specs/plan_03_10_26.md` slice 0.1b

## Context

The Pages build (`docs-site.yml`) was red on `df1bf47` (run 37137697647) at the
step `Audit npm dependencies`. On 2026-10-03 `npm audit` reported three root
advisories:

| Package | Advisory | Severity | Vulnerable range | Fixed release |
|---|---|---|---|---|
| `dompurify` | GHSA-p98j-92pf-mc4p | low | `>=3.4.13 <=3.4.15` | 3.4.16 |
| `fast-uri` | GHSA-hrr3-gc8f-f4qj | moderate | `>=3.0.0 <3.1.8` | 3.1.8 |
| `http-cache-semantics` | GHSA-ch52-4w7c-c8xp (CVE-2026-93748) | high | `<=4.2.0` | none |

The first two have fixed releases and are simply upgraded: override floors,
guarded by `tests/test_npm_audit_floors.py`. The third has none. 4.2.0 is the
latest release of `http-cache-semantics`, and the GitHub advisory carries
`first_patched_version: null` (updated 2026-10-02). `astro` 7.2.8 and 7.3.5,
the newest, both depend on `http-cache-semantics ^4.2.0`, so through it npm
flags `astro`, `@astrojs/mdx`, `@astrojs/starlight` and `astro-expressive-code`
as high too. There is nothing to upgrade to.

The gate as it stood could not say "accepted, for now, for this advisory only".
The workflow step ran raw `npm audit --audit-level=high`, which cannot except
anything. The script behind `npm run audit:deps` keyed its exceptions by
*package* and failed unconditionally on any high finding. So the choice was
between a build that stays red until upstream ships a fix and an exception
mechanism that is honest.

## Decision

**ADR 0008's rule for `pip-audit` is extended to npm: where a fix exists, raise
the floor; where none exists, one dated exception for exactly that advisory.**

`npm run audit:deps` becomes the single fail-closed gate of the workflow step.
It works by advisory, not by package:

1. A root advisory (an object in `via`) is covered only by an exception that
   names its GHSA id, its package and the vulnerable range exactly as
   `npm audit` reports it. Two objects for one id and package that differ in
   range or severity are two root advisories, and each has to match.
2. A package flagged only through other packages (strings in `via`) gets no
   exception of its own. It is covered only when every root advisory it derives
   from is covered.
3. `critical` is never excepted.
4. An exception lives at most 31 days (`expires`), and an expired one stops
   applying. `added` and `expires` are real calendar dates, `added` not after
   `expires`. Renewal is a new dated line in the review log below.
5. An exception whose advisory the audit no longer reports fails the gate until
   it is removed.
6. A report the script cannot explain fails the gate: not `auditReportVersion`
   2, an npm error document, an entry or a `via` item of the wrong shape, an
   advisory with an unknown severity, a `via` naming a package with no entry,
   an entry with no `via`, an entry flagged above `info` with no advisory above
   `info` behind it.

The range in rule 1 is what makes the exception lift itself. When upstream
publishes a fix, the advisory's range stops being `<=4.2.0`, the exception no
longer matches, and the build is red until the dependency is upgraded and the
entry deleted. Nobody has to remember.

Reasoning:

- **Against staying red:** the argument of ADR 0008. This step is the docs
  site's only supply-chain alarm. Held red by a finding that cannot be acted
  on, it stops reporting the ones that can: `dompurify` and `fast-uri` were
  sitting behind the same red light.
- **Against an exception by package**, which is what the previous register
  schema offered: it would also cover every *future* advisory against
  `http-cache-semantics`, and the four packages flagged through it would each
  need an entry covering every future advisory against Astro itself. That is a
  blanket ignore with extra steps, which ADR 0008 condition 3 forbids.
- **Against keeping raw `npm audit --audit-level=high` beside the script:** it
  cannot except by id, so one unfixed high advisory keeps it red forever. The
  script takes over its job and is stricter wherever no exception applies: it
  fails on every severity above `info`, not only on high.

## Reachability

GHSA-ch52-4w7c-c8xp is CWE-524: a *shared* HTTP cache that honours `max-stale`
can hand one user's cached response to another. Whether that can happen here
was checked on 2026-10-03, not assumed:

- In the lock, `http-cache-semantics` has one installed copy (4.2.0) and one
  dependent, `astro`.
- In `astro/dist` (664 JavaScript files) exactly one module imports it:
  `assets/build/remote.js`. It builds a `CachePolicy` for a remote image
  fetched **during the build** and reads its time to live.
- The docs site is a static build. There is no server, no shared cache and no
  second user at any point; the cache in question lives on the build machine.
- The package is not shipped: the client bundles of a local build (13
  JavaScript files) contain neither the package name nor `CachePolicy`.

So the vulnerable behaviour has nothing to act on in this project. That is why
an exception is acceptable, and why it is still an exception rather than a
dismissal: the argument describes today's use of the package, and rules 1 and 4
force it to be re-read.

## Conditions, all mandatory

1. One entry per advisory id. Never an entry without an id, never an entry for
   a package that is flagged only through another package.
2. The entry names the vulnerable range; a changed range ends the exception.
3. `expires` is at most 31 days ahead. The gate and the unit suite
   (`tests/test_docs_site_npm_audit.py`) are both red from the day after: a
   forgotten review is a red build, not a silent pass.
4. The entry carries the reachability argument, an unfreeze condition and an
   owner.
5. It is listed in `CURRENT_STATE.md` as an accepted open risk.
6. The workflow step runs the gate with no `|| true` and no
   `continue-on-error`.

## Review log

- 2026-10-03 — entry added for GHSA-ch52-4w7c-c8xp, `expires` 2026-11-03.
  Review it together with the `pip-audit` ignores of ADR 0008 on 2026-10-24.
  If a fixed `http-cache-semantics` or an Astro release without the dependency
  exists, upgrade and delete the entry. Otherwise re-check the reachability
  facts above and add a dated line here with the new `expires`.

## Consequences

- The Pages build can be green while one high advisory is open, and it says so:
  every passing run prints the applied exception with its id and expiry.
- From 2026-11-04 the build and the unit suite are red until the entry is
  renewed or removed. That is intended.
- A second advisory against `http-cache-semantics`, or any advisory against
  Astro itself, still fails the gate.
