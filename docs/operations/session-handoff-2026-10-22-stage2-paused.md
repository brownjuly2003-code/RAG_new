# Session handoff — 2026-10-22 — stage 2 paused after WixQA batch 4

**Do not restart the Mac measurements.** Julia requested freeing the Mac, then explicitly
allowed the current batch to finish. This supersedes the earlier reservation through all
three external bases. Resume only when she makes the Mac available again.

Read with [current state](../../CURRENT_STATE.md), [the plan](../../PLAN.md) stage 2 and the
[registered measurement spec](../specs/stage2-four-corpora.md). This is the current handoff;
`.tmp/stage2/HANDOFF_20261021.md` is a local operational copy.

## Completed and preserved

| External base | Completed answers | Completed batches | Next |
|---|---:|---|---|
| ConditionalQA | 100/100 | b01–b10 | grading pending |
| WixQA | 40/100 | b01–b04 | b05–b10 |
| MultiHop-RAG | 0/100 | none | b01 and its gates, then b02–b10 |

All **140 answers** belong to 14 complete batches with runner exit 0 and no path breaks.
Queue shutdown was confirmed at **2026-10-22 10:47:13 UTC** (06:47 Toronto).
No answer in those batches needs repeating. Technical integrity is not a quality verdict.

Earlier work remains valid: 100 aircargo answers and their existing judge record in
`reports/stage2/5e308fe/`; all 415 retrieval questions are published in
[the retrieval baseline](../evidence/stage2-retrieval-baseline.md). Local commits `7208ed2`
and `4fe4aaf` record the baseline and previous state. No push was authorized.

## Where to recover the results

- Windows: `D:/RAG_new_stage2_private/p4/pause-20261022/`.
- Mac copy: `/Users/julia/RAG_new_stage2_pause_20261022/`.
- Original run directories remain under the frozen stand's `chatlive/runs/`.
- `checkpoint.json` records counts, completed labels, the code SHA, the reason for the
  pause and the next batch. `RESUME.md` gives the continuation boundary.
- ConditionalQA summaries include retrieval parity. WixQA has a partial answer summary.
  `private-raw-runs.tar` preserves answers, prompts, traces, resource logs and the run tools.
- `manifest.json` covers 13 exported files; `raw-manifest.json` covers 668 archive members.
  Both levels of SHA-256 verification passed locally, including all 140 case files.
  The archive is 46,786,560 bytes. Preserve these copies; do not regenerate over them.

Raw content stays outside the Git repository. The answer snapshot has not yet been
published as a sanitized immutable evidence record with derivation tests.

## Why some status files say failed

The registered driver stopped on `STOP file before batch 5` and returned exit 1. The old
controller propagated that as `failed`; it does not mean batch 4 failed or answers were lost.
The snapshot's explicit status is `paused_by_user`. Local capture status is `verified` in
`.tmp/stage2/pause-20261022.status.json`; its terminal marker was `LOCAL_PAUSE_COMPLETE exit 0`.
Original queue log/status: `.tmp/stage2/remaining-20261021.{log,status.json}`.

At shutdown, Ollama held no models, ports 8002/55433 were free, and the recorded measurement
processes had exited. The Windows worker, attached SSH and keep-awake companion exited;
the companion recorded `RELEASED`. Other projects and the shared Ollama server were untouched.

## Frozen stand and safe continuation

- Stand: `/Users/julia/RAG_new_chat_5e308fe/chatlive/`.
- Product code: `5e308fe48cca0955c3007057a574a425f71e2a6a`.
- Index root: `/Users/julia/RAG_new_external_s1`, generation `e5e135a`.
- Stop markers remain at `/Users/julia/RAG_new_stage2_control_20261021/STOP` and
  `/Users/julia/RAG_new_chat_5e308fe/chatlive/runs/p4-wixqa.stop`.

After renewed Mac availability, reconcile the checkpoint against existing runs, verify the
frozen stand and perform the spec's idle check: load5 below 2, no competing measurements,
no loaded Ollama model and ports 8002/55433 free. Never modify the product, prompts or the
registered measurement drivers while continuing this baseline.

Do not restart `continue_20261021.py`: it refuses existing state and batches. Retire that
controller; preserve its records. Clear the WixQA stop marker only for an authorized resume.
The next invocation of the unchanged driver, attached over SSH, is:

```text
sh /Users/julia/RAG_new_chat_5e308fe/chatlive/stage2.sh answers p4 wixqa /Users/julia/RAG_new_external_s1 5 10
```

Then run MultiHop-RAG b01, inspect its first answer and first five as they arrive, validate
the completed batch, and only then run b02–b10. Use the existing observer and registered
checks. Do not overwrite or repeat the 14 completed batches. No sync or tests during runs.
After collection, export the registered summaries and parity, preserve raw runs privately,
and publish new sanitized immutable records with provenance/derivation checks.

## Remaining boundaries

Claude is unavailable. No new judge calls were made and no replacement judge is authorized.
Stage 2 remains open; do not move to product changes in later stages on these partial results.
Mac measurements and tests remain paused while Julia uses the machine.

Local helper scripts in `.tmp/stage2/`: `pause_snapshot_20261022.py`,
`finish_pause_20261022.ps1`, `verify_pause_20261022.py`. They are operational artifacts;
the first two must not be rerun over existing exports. Preserve unrelated untracked
`demo/phase-e-raw.webm` and `reports/ask100/`.

The stop and capture were verified directly. Documentation changes are saved locally,
without a new commit or push. The required `test_docs_hygiene.py`, `test_docs_quality.py`
and `test_docs_publication.py` must run through the Mac gate when the Mac is available;
they were not run for this documentation update because the owner reclaimed the machine.
