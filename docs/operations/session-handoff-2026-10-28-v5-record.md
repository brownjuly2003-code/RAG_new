# Session handoff 2026-10-28 — V5 not adopted, the encoders' Amendment 1 read

Session of 2026-10-27 ≈ 14:20 – 2026-10-28 ≈ 04:00 UTC, the same session as the previous
handoff; all times UTC (the laptop's clock is EDT, the Mac's UTC+3). The previous handoff, whose
model and glossary still hold: [the widget read, V5 running](session-handoff-2026-10-27-v5-running.md).

## Read this first

- **Stage 3b is closed: V5 is not adopted** ([record](../evidence/answer-prompt-v5-record.md)).
  The table's first row, harm, holds on WixQA: bad 51 → 86 of 100, good 40 → 4. V4 stays in
  `agent/prompts.py`; stage 4 goes on with V4. Nothing in the product changed.
- **Three of V5's five judge plans do not count** — WixQA's M2, ConditionalQA's M1 and aircargo's:
  their retests fail the stability rule. The judge wavers on one field, the defect (8–11 of 15
  retests agree on it, against 14–15 on the answer and 15 on the context), and the defect it
  wavers on is V5's visible form: the quoted passages and the status line around the answer,
  graded «other» or «copied_context» in 75, 63 and 65 of V5's answers a base (V4: 0, 4, 3).
- **The encoders' Amendment 1 is read:** Part 1, Horizon guard base, in between — 7 of 17 caught,
  7 of 63 over-marked (`5ba14bd`); Part 2 `NOT_EVIDENCE` with nothing scored, because V5's aircargo
  plan does not count. Stage 3 stays at outcome C.
- **Nothing runs.** The V5 chain ended `CHAIN_DONE` at 23:44:50; the judge's last stream ended
  03:45:05; B's score ended 01:51:18. No judge, `claude -p` or Mac process of this session is
  left. The Mac is free for stage 4.
- **Nothing is pushed:** 23 commits after `origin/master` (`43009ac`) plus this file's. A push
  needs her word and the checks of the CI-parity memory note.

## What this session did

| UTC | What |
|---|---|
| 17:14 | `e078f95` — WixQA's two judge plans frozen; the judge's first stream (WixQA's bridge) |
| 20:15 | `2a9cc5c` — ConditionalQA's plans frozen |
| 20:38, 21:27 | `b67c457`, `0ef1705` — the week's pause at 0.95, then both windows to their cap, on her words |
| 22:29 | `1bcfd9e` — the whole judge at once on her word; the table decides, the step prints beside |
| ≈ 22:30–23:00 | the session stopped three plans on `v5_core.py`'s step — a deviation; `f0ead1f` records it, the plans resumed and were graded whole |
| 23:44 | V5's chain done: 300 answers, no path break |
| 23:46 | `6e7c02b` — aircargo's plan frozen, before its first grade |
| 23:51–01:51 | B's Part 1 on the Mac, alone (119 min against a forecast of 200) |
| 01:59 | `5ba14bd` — Part 1's records: B's loading check, rows and record |
| 03:45 | the judge's last plan done: 620 new requests, $175.71 |
| ≈ 03:50 | exports, `v5-core.json`, `v5-record.json`, Part 2's record, both artifact tests, the capsules, the status files; 152 focused tests passed on the Mac |

## Julia's words in this session (UTC)

- Status questions through the day («процесс идет по плану?», «как обстановка?», «процесс в
  норме?», «а судья уже работает?», «что с процессом?») — answered from the logs.
- ≈ 20:40 «этот проект очень важен, расходуем лимит под него» — the week's pause 0.70 → 0.95.
- ≈ 21:30 «тратить лимит можно до полного упора», then «а потом - после возобновления» — both
  windows to their cap, then on after the reset.
- ≈ 22:25 «можно запустить судью на весь объем - лимит есть» — all plans and bridges at once.
  The weekly window had dropped from 0.67 to 0 at 22:15 with its reset date unchanged
  (2026-10-31 21:00); at 03:10 it read 0.09. While the judge ran the week went 0.58 → 0.67, then
  0 → 0.09, this session's own use included.

## What the record found, for the message to Julia

- **Decision:** not adopted by row 1 on WixQA. ConditionalQA's and aircargo's harm are not read
  (their V5 plans do not count); their shares move the same way (bad 57 → 81, 17 → 89).
- **Why it failed:** V5 shows the user its whole three-part text, and the judge grades that
  scaffold as a defect, which makes any answer bad. The spec foresaw «copied_context» leaning
  against V5, not the scaffold itself.
- **What V5 did well, deciding nothing:** claims supported 90.5 → 94.7 % (WixQA) and
  79.2 → 88.5 % (ConditionalQA); wrong declines on WixQA 22 → 10. With the two format defects set
  aside after the grades, V5's bad share falls on both external bases (51 → 39, 57 → 46), its
  partial answers rise — more faithful, less complete.
- **But on aircargo, the product's corpus, V5 is worse even so** (bad 14 → 37 with the format
  aside): 11 answers in the wrong language, 10 repeating, 1 cut off at the token cap.
- **Cost:** $175.71 against a forecast of ≈ $116–130: a grade of a V5 answer cost $0.26–0.32, of
  a V4 answer $0.16–0.20, the answers being twice as long.

## Next actions

1. **Stage 4, step 0** ([`PLAN.md`](../../PLAN.md) stage 4): diagnostics before the levers,
   ≈ 1 h of the Mac, nothing changed — her word of 2026-10-25 («Давай попробуем») covers it.
   A short spec before the first request (the questions, what is read from the llama-server log,
   `vm_stat`, swap and RSS, the stop), by the chat-test rules of the memory note: the real path
   at production limits, one question first. Check the Mac is idle before it (other projects).
2. **A push** only on her word, after the whole Mac suite, mypy, bandit, pip-audit and DEP-01.
   On 2026-10-28 mypy and DEP-01 passed; pip-audit found 7 new advisories in `authlib` 1.7.0,
   fixed in 1.9.1 — raise the floor and refresh both locks first ([`BACKLOG.md`](../../BACKLOG.md)).
3. **Her word pending:** the widget's R1 and retry-budget fixes (§8.3, item 1); stage 4's
   self-evaluation badge, `ollama serve` settings and SLO (item 2).
4. **Not planned, an idea only:** V5's evidence kept from the user (the answer shown alone).
   The format-aside column hints at gains on the external bases but not on aircargo, where the
   language and repetition defects stay; it would be a new spec and her word.

Kept as they are: the stand `/Users/julia/RAG_new_chat_4f48fed` with its `v5/` runs (the
records' source); the judge's private folders `D:/RAG_new_stage2_private/v5/judge/`; the
helpers in `.tmp/v5/` (git-ignored). Never commit `demo/phase-e-raw.webm` or `reports/ask100/`
— not this session's.

## Glossary added

- **Readable key** — a key whose bridge and both sides' M1 plans count; only a readable key's
  harm is read by the table.
- **Format aside** — each side's M1 classes with «other» and «copied_context» set to none, every
  other field as graded: read after the grades, not registered, decides nothing.
- **Bridge** — V4's 15 retested requests of a key graded again in V5's window; it shows whether
  the judge moved on V4's answers.

## Lessons

- **A word that makes a step print-only binds every running action at once.** After 22:25 the
  step `v5_core.py` decided nothing, yet the session stopped three plans on its output. Before
  acting on a tool's verdict, re-read the latest rule for what that verdict may still do.
- **A prompt that changes what the user sees changes what the judge grades.** The judge's
  instructions were kept for the pairing with V4; the scaffold became the defect, and the judge
  wavered on it. A spec for a new visible form reads the judge's defect list against that form
  first, and says whether the form is shown at all.
- **A judge's cost is forecast from the answers it grades.** The forecast took V4's cost a grade;
  V5's answers were twice as long and a grade cost 1.7×.
- **Usage windows are read, not assumed:** the week dropped to 0 mid-run with its reset date
  unchanged. The probe between chunks saw it; a forecast would not have.
- **A watch re-armed near an end can miss the end:** B's `ALLDONE` came just before the re-armed
  Monitor started and counted as already seen; read the log itself when re-arming late.
