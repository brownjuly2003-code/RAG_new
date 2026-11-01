# Stage 8 runbook — RAG_new public with its whole history

Her word, 2026-11-01 20:26 UTC: «Да, сделать приватным. А текущую историю - в RAG_new и сделать
публичной». The old `RAG_Support_Assistant` has been private since ≈20:41. RAG_new already holds
its whole history (common root `fc5266a`). PLAN stage 8, «Правка 01.11, вечер», sets the
conditions. This file gives the order. Commands use absolute paths; the working directory does
not persist.

## 1. What becomes public

Every ref GitHub holds, not only `master`:
- `baseline/freeze-2026-08-23` and the tag `freeze-2026-08-23`;
- `wip/T-61-writer`, `wip/T-69-prep` and `wip/T-77-prep`. These are old backups with `.tmp`
  notes and MyFlow files. A deleted branch stays readable by SHA, so these branches are scanned
  too.

There are no pull requests, wiki is off and issues are on. Old Actions run logs become readable.

`origin/master` is `7caaf21`; the local commits after it reach GitHub only by the push in section 5, step 6.

## 2. Checks (laptop, light; nothing on the Mac)

Start with `mkdir -p D:/RAG_new/.tmp/stage8-scan` and `git -C D:/RAG_new fetch origin`.

**Secrets.** Gitleaks 8.30.1 is on the laptop ([2026-09-30 scan](../evidence/e5-secret-scan.md):
1,082 commits, 11 allowlisted fingerprints in `.gitleaksignore`). Run
`D:/RAG_new/.tmp/e5-scan/bin/gitleaks.exe git --log-opts="--all" --redact --no-banner --report-path D:/RAG_new/.tmp/stage8-scan/gitleaks.json D:/RAG_new`.

`--all` also reads local-only branches, so triage each finding by the refs in section 1. A real
key: she revokes it at its provider, and the switch waits for her word that it is revoked. The
history is not rewritten.

**External texts.** Write the scanner in `.tmp/stage8-scan/`.
1. Build 8-word shingles, casefolded and hashed to 64 bits, from:
   - aircargo's 201 `.md` in `D:/RAG_Support_Assistant/data/uploads/aircargo/`;
   - `D:/RAG_new_stage5_private/data/{wixqa,conditionalqa,multihoprag}/` and
     `D:/RAG_new_stage5_private/p2-multihoprag/` — the bases' own texts;
   - `D:/RAG_new_stage2_private` and `D:/RAG_new_stage5_private/2057ad0/runs` — answers,
     references and sent contexts.
2. List the objects GitHub will show, with paths:
   `git -C D:/RAG_new rev-list --objects master --remotes=origin --tags`.
3. Read each blob once with `git -C D:/RAG_new cat-file --batch`. Print the blob, its path and
   its hit count — never the text.
4. A hit is ≥ 3 distinct shingles from one source file in one blob. Report single-shingle
   blobs only as a count: single shingles match boilerplate.

**Personal data**, kinds and counts only; never print an address into a repository file:
- the two commit author addresses (1,390 commits and 1);
- an address in `docs-site/astro.config.mjs` (`email:`), which the site shows;
- at HEAD: `/Users/julia` in 304 files, `deproject-mac` in 109, the laptop's user name in
  `C:/Users/…` paths in 28, her surname in 8, LICENSE among them;
- her quoted words in the handoffs and audits;
- `evaluation/aircargo_corpus.manifest.json`, which names aircargo's 201 files (HR topics);
- the old Actions logs.

**Workflows.** List the secret names with `gh secret list -R brownjuly2003-code/RAG_new`
(names only). Name the schedules that start again:
- three Monday crons, at 06:00, 07:00 and 09:00 UTC;
- `weekly-report.yml`, which delivers outside.

The live gates pass provider keys only on a dispatch with `enable_live`. My default is
`gh workflow disable weekly-report.yml -R brownjuly2003-code/RAG_new` before the switch; the
test crons stay.

## 3. The report and her one question

One message: the scan's result, the personal list, the workflows and what the push carries. One
yes/no: «Публикуем?». A yes covers the push, deleting the three `wip/*` branches on GitHub, the
schedule default and the switch. Without her yes nothing below happens.

## 4. README and site (before the push)

**README.** It covers what the project is and what it runs on, the architecture, and the
methodology (judge, M1/M2/M3, "detected"). Each number comes with its record's path and date:
- items 6 and 7 on the package;
- stage 2's external bases, marked "before the package";
- stage 5, marked running until its record.

The name is «RAG assistant» (Q4 of 30.09).

**Site.** Links to `/RAG_Support_Assistant/` move to `/RAG_new/`
(`grep -rl 'RAG_Support_Assistant/' D:/RAG_new/docs-site`). One local commit.

## 5. Order after her «да»

1. A full `python C:/Users/uedom/.claude/scripts/ci_local.py --repo D:/RAG_new`, with PASS. It
   covers bandit, pip-audit and DEP-01, none run since `9b769f5`. It is a background job on the
   iMac: start it only when no Codex task runs and no V6 chain uses the Mac.
2. `git -C D:/RAG_new -c credential.helper='!gh auth git-credential' push origin --delete wip/T-61-writer wip/T-69-prep wip/T-77-prep`.
3. If chosen, `gh workflow disable weekly-report.yml -R brownjuly2003-code/RAG_new`.
4. `gh repo edit brownjuly2003-code/RAG_new --visibility public --accept-visibility-change-consequences`;
   check with `gh repo view brownjuly2003-code/RAG_new --json visibility`.
5. Pages: `gh api repos/brownjuly2003-code/RAG_new/pages`; on 404,
   `gh api -X POST repos/brownjuly2003-code/RAG_new/pages -f build_type=workflow`.
6. `git -C D:/RAG_new -c credential.helper='!gh auth git-credential' push origin master`.

   Pushing after the switch lets CI (free when public) and the site deploy run on this push.
   The deploy requires `visibility == 'public'`. If a run did not start:
   - `gh workflow run docs-site.yml -R brownjuly2003-code/RAG_new --ref master`;
   - `gh run rerun <id>` for CI, since `ci.yml` has no dispatch.
7. A line in PLAN, ROADMAP and CURRENT_STATE.

## 6. Every later push

Once RAG_new is public, every push is public at once. Before each one:
- run gitleaks with `--log-opts="origin/master..master"`;
- run the shingle scan over `git -C D:/RAG_new rev-list --objects origin/master..master`.

Each push still needs her word unless her «да» covers it. Never push a `wip/*` branch.
