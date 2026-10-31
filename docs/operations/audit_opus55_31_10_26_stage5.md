# Cold read: stage 5 draft (final package on the external bases), 2026-10-31

**Verdict: not ready to register.** One blocking defect: `prepare.py` refuses on the real ConditionalQA archives, so the baseline cannot be built. A fix has been checked on the real files and reproduces stage 7's committed per-question readings exactly. Four should-fix items in the spec text and command blocks also need correcting before registration.

Severity counts: **blocking 1, should fix 4, minor 5**.

- Snapshot: `D:/RAG_new_cx/snap-s5`. The manifest `D:/RAG_new_cx/briefs/snap-s5.manifest` matched on all 18 files before and after the work.
- Under review:
  - `docs/specs/stage5-final-external.md`
  - `reports/stage4-final/tools/external/*.py`
  - `tests/test_stage5_final_tools.py`
- Context read:
  - PLAN §4.3, §4.4 and «Этап 5»
  - T1–T4 in `briefs/s6c-brief.md`, plus `s6-brief.md` and `s6b-brief.md`
  - the item 6 spec and `reports/stage4-final/tools/*.py`
  - the frozen writers: `scripts/chat_answer_judge.py`, `reports/stage2/tools/{judge_export,retrieval_summary}.py`, `reports/answer-prompt-v4/tools/bridge_plan.py`, `evaluation/external_gold.py`
  - `reports/stage7/5e308fe/{record.json,rows.jsonl}`
- Method:
  - Laptop only. No Mac, no pytest, no model.
  - The real private files were read read-only.
  - Tool runs used the focused venv with `python -I -B -X utf8` and the cwd set to the snapshot root.
  - The snapshot has no `.git`, so `committed()` ran against a scratch `GIT_DIR` at `snap-s5/.tmp/cold/git`.
  - `prepare.py` refuses a config inside the repository, which is correct. So `inputs.json` with the spec's literal paths went to `D:/RAG_new_cx/cold-s5/inputs.json`.
  - Scratch files are only in `snap-s5/.tmp/cold/` and `D:/RAG_new_cx/cold-s5/`.
- Nothing below quotes question, answer, document or prompt text. Only ids, counts, field names and hashes appear.

---

## F1 — blocking — `prepare.py` refuses on real ConditionalQA V4 archives: `saved_point` misses table-header prefixes and refuses genuine repeats

**Where:**
- `reports/stage4-final/tools/external/sent_gold.py:57` builds `places` from `occurrences(body)` without stripping the table header.
- `sent_gold.py:70` needs every paragraph to occur exactly once (`all(len(s) == 1 ...)`).
- `sent_gold.py:72-77` refuses with "unplaceable or ambiguous".
- The spec states the rule at `stage5-final-external.md:222-227`.

**What is wrong:**
1. Continued tables are missed. When the chunker continues a table, it repeats the table's header rows at the start of the chunk. The frozen locator strips that prefix (`evaluation/external_gold.py:112,121`, `table_header.prefix(body, metadata)`), but `saved_point` does not. Such a paragraph has 0 occurrences in the source, so it is "unplaceable".
2. Genuine repeats are refused. A paragraph that really occurs twice in its source document is refused by the global-uniqueness rule. Stage 2's own rule never refuses this case. It places pieces in order inside the expansion's span (`reports/stage2/tools/retrieval_summary.py:130-145`, `find(needle, at, high)`).

**Evidence:**
- The real run `prepare.py --config D:/RAG_new_cx/cold-s5/inputs.json --private D:/RAG_new_stage5_private --out <scratch>` exits 1 after about 23 s with `NOT_EVIDENCE: historical sent excerpt unplaceable or ambiguous`. Presence/hash preflight, the MultiHop p2 gate and WixQA had all passed by then.
- A per-piece probe over the 100 CQA V4 prompts placed 409 pieces as unique, placed 99 by unique paragraphs, and refused 5 cases:
  - Continued tables, which occur exactly once after the prefix strip: `conditionalqa-train-1759`, `conditionalqa-train-1749`, `conditionalqa-train-1658`.
  - A visible paragraph that occurs twice in its own source: `conditionalqa-dev-53`, `conditionalqa-dev-34`.
- I relaxed only `saved_point` in a probe (`.tmp/cold/probe_v4m3.py conditionalqa relaxed`):
  - it strips `table_header.prefix` as `locate_chunks` does;
  - it lists every placement of an ambiguous piece and requires the gold reading to be the same for all of them.
- Result: gold_n 80 and hits 60. `stage7_H_old_hits` is 60, `prompt_sha_mismatch_vs_stage7` is 0, and the per-question hit and fraction differences are both empty. The probe applied 3 table-prefix strips and enumerated 1 ambiguous piece, with 0 variant readings.
- With this relaxation alone, the whole `prepare.py` runs end to end (see "Checked and found right").

**Fix:**
- In `saved_point`, try `body[table_header.prefix(body, seed_metadata):]` for each seed's metadata, exactly as `external_gold.locate_chunks` does. Do this both for whole pieces and for the paragraph fallback.
- For more than one placement, enumerate the alternatives (cap the product) and accept the piece only if `read_gold`'s hit and fraction are the same for every alternative. Refuse only when the reading changes.
- Update the spec at 222-227 to say this. "Ambiguous" then means "ambiguous in its reading", not "repeated text".
- Add the two synthetic regression fixtures from F9 and the stage 7 per-question gate from F3.

## F2 — should fix — the laptop `tar --force-local` fails in PowerShell

**Where:** `stage5-final-external.md:368`, `Checked tar --force-local -xf "$RunPrivate/$Base.tar.gz" -C "$RunPrivate/runs"`. The instruction comes from T3's premise "on Windows `tar` needs `--force-local`".

**What is wrong:**
- In a normal PowerShell session, `tar` is `C:\Windows\system32\tar.exe` (bsdtar 3.8.9). Bsdtar does not know `--force-local` and exits non-zero, so `Checked` throws.
- The premise holds only for GNU tar, the one Git Bash puts first on PATH.
- The block stops at the first base's extract, after a roughly 10-hour Mac run. Nothing is lost, but the registered command cannot run as written.

**Evidence:** `D:/RAG_new_cx/cold-s5/ps_tar.ps1` and `ps_tar2.ps1` under `powershell -NoProfile` (PS 5.1.26100):

| Command | Result |
|---|---|
| fresh-session `(Get-Command tar).Source` | `C:\Windows\system32\tar.exe` |
| bsdtar `--force-local -xf` | `Option --force-local is not supported`, FAILED |
| bsdtar plain `-xf D:/... -C D:/...` | exit 0, all files out |
| Git's GNU tar (`C:\Program Files\Git\usr\bin\tar.exe`) `--force-local -xf` | OK |

**Fix:** In the PowerShell block, call `& "$env:SystemRoot/System32/tar.exe" -xf ...` without `--force-local`. Bsdtar has no `host:path` parsing. Alternatively, name Git's GNU tar by its full path and keep the flag. Correct T3's sentence in the brief history so it is not carried forward.

## F3 — should fix — "V4's sent M3 is not published" is not true in effect; the old side is not gated against the committed stage 7 per-question values

**Where:** `stage5-final-external.md:216-219`. `prepare.py` and `sent_gold.py` have no comparison with `reports/stage7/5e308fe/rows.jsonl`.

**What is wrong:**
- Stage 7's committed parity shows that its `H_old` arm under V4's prompt reproduces V4's saved prompts byte for byte on all 300 questions. `record.json` gives `parity.v4_byte_equal` 300 of `v4_saved` 300.
- Its `rows.jsonl` holds each question's `H_old.points.sent` hit and fraction, computed by stage 2's exact `retrieval_summary.coverage` rule.
- So V4's sent M3 is already committed per question: WixQA 68/100 and ConditionalQA 60/80, which is the advisory's "128 of 180".
- The spec ignores this check, which would have caught F1. It also tells the reader not to expect 68/60, but V4's sent values are exactly 68 and 60.

**Evidence:**
- Draft code on WixQA, unpatched: 68/100, with per-question hits and fractions identical to stage 7 `H_old`.
- CQA with the F1 relaxation: identical per question, 60/80.
- All V4 prompt hashes equal stage 7's `H_old.prompt.sha256`, with 0 mismatches. The ids are public. The rows hold no text.

**Fix:**
- In `prepare.py`, after computing the old WixQA/CQA sent points, require per-question equality of hit and fraction (to 6 decimals) and of the prompt hash with `rows.jsonl`'s `H_old` for that base. Refuse on any difference.
- Pin `rows.jsonl` and `record.json` by hash in the baseline.
- Rewrite 216-219: V4's sent M3 is not in V4's own record, but stage 7's parity-checked `H_old` gives it (68/100 and 60/80). The tool recomputes it from the saved prompts and must match.
- This changes nothing in the decision rule.

## F4 — should fix — the command blocks run hours apart but depend on each other's variables; `STAGE5_SHA` is taken from a moving HEAD

**Where:**
- Block 2 is `stage5-final-external.md:318-333`. It uses `$Private`, `$Item6Sha` and `$Tools` from block 1, which ran before registration.
- Block 4 (`:363-379`) and block 5 (`:385-387`) use `$Remote`, `$RunPrivate`, `$Record`, `$Config`, `$Tools`, `$Baseline` and `$Stage5Sha`.
- Block 4 first runs about 10 h after block 2, and block 5 more than a day later.
- `:319` reads `$Stage5Sha = (git rev-parse HEAD)`.

**What is wrong:**
- In a fresh PowerShell session, `$Private` is empty. Then `New-Item "$RunPrivate/runs"` (`:324`) creates `\<seven>\runs` at the drive root before `merge-base` refuses on the empty `$Item6Sha`.
- Block 4 would run `ssh` with `/runs/<base>.complete` and write receipts under `/plans-<base>.json`.
- `STAGE5_SHA` is "HEAD at the time block 2 runs". If anything is committed between registration and the end of item 7 (item 7's own evidence commit is likely), that commit becomes STAGE5_SHA. The allow-list would pass it, but STAGE5_SHA would no longer be the registering commit the record names.

**Fix:**
- Start every block with one literal preamble: `$Private`, `$Old`, `$Tools`, `$Baseline`, `$Config`, and `$Item6Sha` with the 40-character literal.
- In blocks 4 and 5, read `$Stage5Sha` from `D:/RAG_new_stage5_private/STAGE5_SHA` (written by block 2) and derive `$Short`, `$RunPrivate`, `$Record` and `$Remote` from it.
- In block 2, set `$Stage5Sha` to the registering commit and check that it is an ancestor of HEAD, instead of using HEAD itself. One way is a literal filled in by the registration's follow-up commit. Another is `git log -1 --format=%H -- reports/stage4-final/stage5/baseline.json`.
- Optionally, check that `$Private` is non-empty before the first `New-Item`.

## F5 — should fix — the spec has no MDE, which PLAN §4.4 requires before the first request

**Where:** The whole spec. A search for "MDE", "detectable" or "power" finds nothing. The item 6 spec has one (`stage4-item6-final-aircargo.md:185`).

**What is wrong:** PLAN §4.4: «До первого запроса короткая спека этапа записывает … чтение результата и MDE». Without the MDE, a "holds" reading has no stated resolution.

**Fix:** Add the line in item 6's form, MDE ≈ `2.8 sqrt(d/n)`:

| Reading | n | MDE at discordance 0.1 / 0.2 / 0.3, percentage points |
|---|---:|---|
| Pooled deciding M1 bad | 200 | 6.3 / 8.9 / 10.8 |
| Per primary base | 100 | 9 / 13 / 15 |
| CQA M3 | 80 | 9.9 / 14.0 / 17.1 |
| MultiHop M3 | 70 | 10.6 / 15.0 / 18.3 |

Smaller changes remain unresolved.

## F6 — minor — the T1 allow-list admits changes to the answer harness item 6 ran

**Where:** `protocol.py:60-66`, called at `execute.py:38` and `reading.py:241`.

**What is wrong:**
- `reports/**` is allowed as T1 decided. That prefix also covers the harness item 6 used: `reports/stage4-final/tools/{api,run,record,runner,stand}.py` and stage 2's `reports/stage2/tools/live_api.py`.
- A post-ITEM6 edit to these files passes the diff gate. It is only printed in `changed_paths`.
- The settings gate (`record.effective`) catches setting changes, but it lives in the same allowed tree.

**Fix:**
- Inside `reports/**`, refuse changes to the item-6 harness files: the top-level `reports/stage4-final/tools/*.py` and the stage 1, stage 2 and step 0 files they import. Stage 5's new `external/` folder stays allowed.
- Alternatively, print a separate `harness_changed` list and have the reader report NOT_EVIDENCE if it is non-empty without a named spec amendment.

## F7 — minor — one empty new answer makes a whole base NOT_EVIDENCE at plan freeze; the frozen judge counts it as bad

**Where:**
- `grading.py:95-97,102` requires exactly 115 messages per M1/M2 plan and 245 per base.
- `chat_answer_judge.py:369-375` gives an empty answer no message.
- `chat_answer_judge.py:598` and `judge_export.py:253-270` count it as bad, "empty_answer" or "wrong".
- `record.py:35-52` (`case_gate`) never checks that the answer text is non-empty.

**What is wrong:**
- A whitespace-only or empty answer with a valid first token passes the Mac gate, so the `.complete` marker is written.
- At freeze the plan then holds 114 messages, and the whole base refuses ungraded. This surfaces many hours later, and it turns a quality signal (bad) into NOT_EVIDENCE.
- V4's 300 published answers had 0 empty answers (minimum 10 characters), so the risk is low.

**Fix:** Pick one and state it in the spec:
1. Add a non-empty-text check to `case_gate`, so the base fails on the Mac before its marker.
2. Accept `(100 − empty) + 15` requests and let the frozen judge read empty answers as bad, as stage 2 and V4 do.

## F8 — minor — `data/<base>/` is not "only" the six entries: the copies hold macOS AppleDouble `._*` files

**Where:** `stage5-final-external.md:277-280` and T3.

**Evidence:** This is a read-only listing.
- Each base has 5 `._*` entries at the top level (`._cases.jsonl`, `._chunks.json.gz`, `._corpus`, and so on) and `._index-receipt.json` in `index/`.
- `corpus/` holds one `._` file per corpus file: 6,221 for WixQA, 652 for CQA and 609 for MultiHop, which is half of `corpus/`'s entries.
- They did not trip `prepare.py`, which passes with the F1 relaxation. Any future glob over `corpus/` or `data/<base>/` would see them.

**Fix:** Correct the sentence. Either make the preflight explicitly ignore `._*` and test that, or recopy without them. The recopy is for the orchestrator to decide; these roots are read-only for the tools.

## F9 — minor — the tests pass while the real path refuses

**Where:** `tests/test_stage5_final_tools.py`. It has 32 tests.

**What is wrong:**
- The `saved_point` tests use clean synthetic text: no continued-table chunk, no paragraph repeated in its source, no AppleDouble files. So F1 passes the suite.
- The reading and grading tests replace `check_receipt`, `admitted`, `product_diff`, `series_gate`, `answers` and `paired` with stubs (around `:778-802` and `:597-614`). They prove the plumbing, not the real exports.
- `execute` is tested with `batch`, `wait_idle`, `corpus` and `questions` stubbed (`:394-428`, `:474-478`).
- None of this can catch a real-data mismatch. This review did not run pytest.

**Fix:**
- Add two synthetic fixtures that reproduce F1's shapes:
  - a table split across chunks, with the header repeated by `table_header`;
  - one paragraph present twice in a source.
- Assert that both are placed, and that a repeat whose alternatives change the reading refuses.
- Add a test that the F3 stage 7 gate refuses a one-question difference.
- The real-file confirmation stays a laptop pre-registration step, recorded in the commit.

## F10 — minor — the "use a new OUT" rerun has no command

**Where:** `stage5-final-external.md:346-347` (`OUT=$P/runs`, `git clone --bare ... "$P/source.git"` under `set -e`) and `:366` (`$Remote/runs`).

**What is wrong:**
- `execute.py` correctly refuses an existing OUT.
- The spec says "use a new OUT", but OUT is fixed in two blocks.
- On a rerun the zsh block also dies at `git clone` because `source.git` already exists.

**Fix:** Make OUT a named variable with a run suffix in both blocks, and write `test -d "$P/source.git" || git clone --bare ...`.

---

## Checked and found right

- **Adapters against real files.** With F1's relaxation as the only change, `prepare.py` on the spec's literal paths ran end to end.
  - It passed presence/hash preflight, `historical()` on all 300 V4/V3 answers, `references()` against `judge_export.reference_rows`, `judge_record` for M1/M2 against the committed exports, `source_gate`, the GOLD_N check and the ceiling check.
  - The baseline is 250,081 bytes with 25 public pins and no private path strings, and it passes `without_text`.
  - `old_judges` hold plan, verdict and reference hashes, withheld, prompt_id, route, salt and instructions.
  - The adapters follow `chat_answer_judge.read_prompt`/`run_answers` and `build_plan`, `judge_export`, `bridge_plan.main`, and `retrieval_summary.Excerpted`.
- **The old side reproduces the published numbers.**
  - MultiHop p2 gate: 10/70, the same per question and against the combined record, which also holds MultiHop M2 as NOT_EVIDENCE.
  - WixQA old sent: 68/100. CQA: 60/80 (after F1).
  - None is at a ceiling.
- **The new-side reader works without torch.**
  - Stage 7's `arms.Replay` builds on the laptop without torch or sentence_transformers.
  - `SentGold.one` on p2-multihoprag's recorded expansions plus prompt-parsed documents reproduces 10/70 per question, with 0 cut-flag differences, 0 trailing-whitespace expansions and 0 errors.
- **Bridges.** `bridge_plan.main` on the real old M1 plans (V4 WixQA/CQA, V3 MultiHop) gives, per base:
  - 30 items, 15 copies with a message, 15 valid seed lines and 15 pending;
  - plan hashes `db88932e…`, `582de363…` and `85ec5f83…`.
  - That makes 115 + 115 + 15 = 245 per base and **735** in total.
- **Times and forecast.** Times and forecasts equal the spec table exactly:

  | Base | median / p90 / max `total_sec` | first / rest / batch / base, s |
  |---|---|---|
  | WixQA | 301.14 / 470.632 / 795.978 | 480 / 330 / 3,570 / 35,700 |
  | CQA | 249.309 / 339.314 / 397.595 | 360 / 270 / 2,910 / 29,100 |
  | MultiHop | 274.965 / 341.262 / 418.456 | 360 / 300 / 3,180 / 31,800 |

- **Arithmetic recomputed.**
  - 26.83 h; stop 80.50 h; the 3× batch/base values.
  - Idle waits 30 × 1,800 s = 15 h.
  - Cost $130.46–208.30 at the rounded rates. Unrounded, the low end is $130.44, which is immaterial.
  - Laptop 24.50–26.54 h, serial 51.33–53.38 h, pipelined 35.00–36.46 h.
  - Plan 14,950/44,850 s, bridge 1,950/5,850 s.
  - PLAN's 300 × 200–350 s ≈ 17–30 h range contains the forecast.
- **T1.**
  - Full 40-character SHAs, resolved with `rev-parse`.
  - `diff --no-renames -z` against the decided allow-list, in the driver (`execute.py:38`) and the reader (`reading.py:241`).
  - A HEAD-only `git bundle` followed by `git clone --bare` keeps both commits and gives a working `rev-parse`/`diff`. Tested locally with git 2.50.
- **T2.**
  - Atomic `<base>.complete` (`execute.py:107-109`).
  - A base failure is caught and later bases run (`:111`); SIGTERM is handled.
  - Per-base receipts are committed before grading, and grade/export refuse an uncommitted, changed or other-base receipt.
  - The reader keeps earlier bases after a later failure (`reading.py:263`).
  - The pooled reading needs both WixQA and CQA (`reading.py:118-120`).
- **T3.** Literal private paths; no `read -r` or `Read-Host`; `output_gate` protects the historical roots and `data/`. The `--force-local` is wrong only for PowerShell (F2).
- **T4.** The cited stage 7 numbers equal `record.json`'s `package_advisory`:
  - 128→125/180, p 0.375;
  - MultiHop 9→4/70, p 0.0625;
  - 137→129/250, p 0.0215, loss;
  - expanded 141→137, p 0.289.
- **PowerShell mechanics** (PS 5.1):
  - `Checked` passes `--name` arguments unchanged.
  - `$Entry.plans` sees the later `bridge` key, because the hashtable is shared by reference.
  - `"$Base.jsonl"`, `"$Base-m1"` and `-f "{0:00}"` expand correctly.
  - The grade-then-export-then-throw loop keeps a stopped plan's export.
- **Reading rules.**
  - `v4_record.paired` is reused unchanged; "detected" means both intervals exclude zero on the same side.
  - M3 is read in both directions, with a fall counted as harm only if detected.
  - The pooled 200 pairs alone decide.
  - Every missing-admission path is NOT_EVIDENCE.
  - The stop is at 3× forecast at batch, base and series level.
  - The judge stability rule matches V4's.

## Private inputs untouched

Listing hash (paths, sizes, mtimes), before = after:

| Root | Files | sha256 |
|---|---:|---|
| `D:/RAG_new_stage2_private` | 2340 | `07ca0fe7ea20a10314dabf6e43363e17e63de59af0d3033a64eede06ff65a393` |
| `D:/RAG_new_stage5_private` | 15102 | `ab57abe61c7cfdda8550ebc17992a6e130efb428c85dbb3593f1d317740dc22f` |

Both roots are **equal**.

## Disposition, 2026-10-31

Each finding was applied before registration, in the package copy's commits `4b46d0e` and
`54be8a4` (the executor's report names the lines). The orchestrator ran block 1 on the real
private files afterwards: exit 0 in 32 s, old sent M3 WixQA 68 of 100, ConditionalQA 60 of 80,
MultiHop-RAG 10 of 70, the stage 7 per-question gate passed, the private listings unchanged.

- **F1** — `saved_point` strips the repeated table header as `locate_chunks` does, for whole
  pieces and the paragraph fallback, after an exact placement fails; a repeated piece is placed
  by every alternative (at most 256 combinations) and accepted only if the reading is the same
  for all; a reading that changes refuses. Fixtures: a continued table, a paragraph twice in a
  source, a repeat whose readings differ.
- **F2** — every PowerShell extraction calls Windows' own `tar.exe` without `--force-local`;
  the premise came from the orchestrator's brief and held only for Git Bash's GNU tar.
- **F3** — `prepare.py` requires, per question, WixQA's and ConditionalQA's old sent point to
  equal stage 7's `H_old` in `reports/stage7/5e308fe/rows.jsonl` (prompt hash, gold flag, hit,
  fraction to six decimals) and pins that file and `record.json` in the baseline; the spec says
  where V4's sent M3 is published. MultiHop-RAG keeps its p2/p4 gate.
- **F4** — every command block opens with the same literal preamble; ITEM6_SHA is the literal
  `138f3b3`; STAGE5_SHA is the commit that added the baseline, checked as an ancestor of HEAD,
  written to a file in block 2 and read from it in blocks 4 and 5. The stand is raised from a
  detached worktree of STAGE5_SHA, since item 6's `raise_stand.py` requires the commit to be
  the checkout's HEAD (found by the orchestrator after this read).
- **F5** — the spec carries the MDE in item 6's form, at the four sizes this read computed.
- **F6** — a changed `*.py` anywhere under `reports/` outside stage 5's own `external/` refuses,
  in the driver and the reader alike; data, records and documents stay allowed.
- **F7** — an empty answer is a bad answer, as in stage 2 and V4: the plan holds the judge's
  own messages and up to 15 retests, the frozen export grades the empties bad, the record
  counts them; 735 requests stays the forecast for none.
- **F8** — the 7,500 AppleDouble files were removed from the orchestrator's copy; the preflight
  refuses any file under `data/<base>/` outside the layout and the manifest's corpus list.
- **F9** — the fixtures above, the 256 cap, and F3's gate refusing a one-question difference.
- **F10** — a run label (`runs`, then `runs-r2`, …) names OUT, its log and pid on the Mac and
  the laptop's copy; the bare clone runs only when absent; the spec says how a rerun starts.
