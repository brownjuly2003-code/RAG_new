# Stage 2 resume — 2026-10-22

Julia released the Mac and requested continuing the test; Claude remains unavailable.
This supersedes the pause restriction in the [earlier handoff](session-handoff-2026-10-22-stage2-paused.md).
The original checkpoint is historical and must not be edited to authorize this resume.

## Scope and queue

- Preserve the 140 completed answers: ConditionalQA b01–b10, WixQA b01–b04.
- Continue WixQA b05–b10; then MultiHop-RAG b01 alone, with the registered first-one and
  first-five checks; b02–b10 only after that batch passes its gates.
- 160 remaining answers, registered forecast 64,960 s (18.0 h); if started around 11:15
  Toronto on October 22, forecast end around 05:18 on October 23. This is not a deadline.
- No product, prompt, model, index or registered driver change. Code:
  `5e308fe48cca0955c3007057a574a425f71e2a6a`; stand
  `/Users/julia/RAG_new_chat_5e308fe/chatlive`; indexes `/Users/julia/RAG_new_external_s1`.
- Claude grading stays pending. Collection is not an answer-quality verdict or stage closure.

## Controller and preservation

- Local operational folder: `.tmp/stage2/resume-20261022/`.
- Worker log/status: `remaining-20261022.{log,status.json}` in that folder; these are the
  authoritative live status, including SSH PID, completion or failure. Read them before
  doing anything on the Mac. No sync or tests while the series is running.
- Remote controller: `/Users/julia/RAG_new_stage2_resume_20261022/resume_20261022.py`;
  state and preflight receipt beside it. It imports the prior controller's checked gates
  and phase runner and uses a byte-identical copy of its observer.
- The worker keeps SSH attached until completion, uses `caffeinate -i` on the Mac, keeps
  Windows awake only for its lifetime, and records `ATTACHED_ALL_BASES_COMPLETE exit N`.
- Resume refuses missing, extra or partial batches, and verifies the paused originals,
  frozen Git blobs, index metadata and registered case order before moving the WixQA stop
  marker to the new controller folder. The old controller and its `STOP` remain retired.
- Summaries/parity and raw archive go to a **new** private directory on completion:
  `/Users/julia/RAG_new_stage2_external_resume_20261022/`, then
  `D:/RAG_new_stage2_private/p4/resume-20261022/`. Downloaded files are hash-checked.
- Failed phases are not retried automatically. Inspect the driver and supervisor logs;
  use the registered [failure rules](../specs/stage2-four-corpora.md#outcomes-and-what-julia-is-told).

## Stop and recovery

The controller checks its own `STOP` on observer output (at most 60 s apart), propagates
it to the active registered driver's stop file, and prevents the next phase. To request
a stop after the current batch:

```text
ssh deproject-mac touch /Users/julia/RAG_new_stage2_resume_20261022/STOP
```

Immediate stop and cleanup follow the [registered runbook](../specs/stage2-four-corpora.md#running-it).
Do not restart either controller over an existing state. Reconcile completed runs first.
The earlier checkpoint remains in `D:/RAG_new_stage2_private/p4/pause-20261022/` and on the Mac.

## Verification and next boundary

Before measurement: resume boundary tests (4) and original first-batch gates (6) passed on
the Mac. The new tests first failed because the resume module did not exist, then passed.
The readiness check found load5 0.99, no competing measurements, no loaded model, ports
8002/55433 free. All 23 documentation checks passed through the Mac gate before live
collection; the local operational folder keeps the verification and launcher receipts.

After collection: inspect completion markers, verify all 300 registered answers and parity,
then publish sanitized immutable records with derivation tests. Raw answers remain private.
No push authorized. Preserve unrelated `demo/phase-e-raw.webm` and `reports/ask100/`.
