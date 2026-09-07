# Grok task: prepare safe C.1b resume and correct durable state

## Objective

Act immediately as the bounded write worker for `D:\RAG_new`.

1. Create a Mac-side resume wrapper at
   `D:\RAG_new\.grok-prompts\c1b-resume-run.sh` by adapting the existing
   `c1b-full-run.sh` contract.
2. Surgically correct only the current C.1b paragraph and date in
   `D:\RAG_new\CURRENT_STATE.md`: the prior full run is no longer active; it
   was independently observed with no matching process, no final report, and
   a valid checkpoint at run 1/3 with 12 completed cases and zero case errors.

Do not launch, resume, restart, kill, or otherwise touch the Mac benchmark in
this task. Do not do an architecture tour. Make the resume-wrapper edit first.

## Measured facts; do not invent beyond them

- Windows HEAD: `287b9c9`; branch is 25 commits ahead of `origin/master`.
- The benchmark worktree and checkpoint provenance code SHA are exactly
  `b8ecc8efb780d423a267595584ef0927ebb77cc5` and clean.
- Run id: `c1b-qwen3-8b-b8ecc8e`.
- Mac SSH alias: `deproject-mac`.
- Existing remote environment file:
  `/tmp/c1b-b8ecc8e-smoke.env`.
- Remote result directory resolved by that environment is
  `/tmp/rag-new-b8ecc8e.tdcVc2/results`.
- Current checkpoint:
  `c1b-qwen3-8b-b8ecc8e-checkpoint.json`, independently copied SHA-256
  `D2EABCF9F1243CD38A0396E10D9843CFAE6B8DD9D2160FF92CE1769BAD16FE72`.
- Independent Mac inspection at epoch `1788330811` observed:
  no matching process; report absent; checkpoint schema valid; one run,
  seed 42, 12 cases, no non-empty `error`; config 3 x 100 and `think: false`.
- Existing benchmark log ended after printing case 11/100. The checkpoint is
  authoritative because each case is atomically saved before its progress
  line is printed.
- `scripts/generator_benchmark.py` supports `--resume`, validates checkpoint
  run id/provenance/config, skips completed case ids, and saves after each new
  case. Do not change this source or its tests.
- Expected dataset SHA-256:
  `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720`.
- Expected contexts SHA-256:
  `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10`.
- Expected model digest:
  `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`,
  model `qwen3:8b`, quantization `Q4_K_M`.
- The interruption cause is not directly proven. Do not claim a cause.
- A complete result requires a measured report, 3 runs x 100 cases, zero
  failures, all generation/judge/NLI flags valid, exact provenance/config,
  then `FULL_VALIDATION_OK` and final `DONE` in the attached transcript.

## Resume wrapper contract

Create `c1b-resume-run.sh` with LF and UTF-8. It must:

- be a Bash script for the Mac only, with `set -euo pipefail`;
- source `/tmp/c1b-b8ecc8e-smoke.env` and use the exact constants from
  `.grok-prompts/c1b-full-run.sh`;
- preflight exact worktree SHA, clean tree, dataset hash, contexts hash,
  installed model digest/quantization, checkpoint present, final report
  absent, and no active process for this exact run id;
- validate the checkpoint's run id, provenance/config hashes and settings,
  unique completed case ids, zero non-empty `error`, and total completed case
  count strictly between 0 and 300; do not hard-code 12 as the allowed future
  resume count;
- invoke the same generator command and arguments as `c1b-full-run.sh`, adding
  only `--resume`, and wrap that generator process with Mac `caffeinate -dimsu`
  so the Mac does not sleep while the attached SSH invocation is alive;
- capture the entire wrapper stdout/stderr, including preflight, generator,
  post-run validation, `FULL_VALIDATION_OK`, and `DONE`, in a distinct append
  transcript named
  `$RESULTS_DIR/c1b-qwen3-8b-b8ecc8e-resume-transcript.log` while also keeping
  stdout attached; do not overwrite the old benchmark log;
- preserve and report the generator exit code; print `DONE` only after the
  full validation copied from the existing full-run wrapper succeeds;
- be designed for later transfer to a unique Mac `/tmp` path and invocation
  as one attached `ssh deproject-mac bash <remote-path>` command. Do not put
  SSH, scp, nohup, tmux, screen, launchd, or backgrounding inside the script.

The previous wrapper captured only generator output with `tee`, so its later
validation markers could not appear in that benchmark log. Correct this in
the resume wrapper by capturing the whole wrapper transcript.

## CURRENT_STATE.md edit contract

- Change `Last updated` to `2026-09-02`.
- Replace only the current C.1b paragraph.
- State concisely: smoke passed; the full run is interrupted, not evidence;
  exact worktree/config remain valid; no process and no report were observed;
  checkpoint is run 1/3 at 12/100 with zero case errors; do not start from
  scratch or launch a duplicate; resume only with `--resume` from that
  checkpoint in one attached SSH window; accept only independent report
  validation plus transcript markers `FULL_VALIDATION_OK` and `DONE`.
- Keep the file at or below 150 lines and 8 KiB.
- Do not change any other claim or section.

## Allowed writes

- `D:\RAG_new\.grok-prompts\c1b-resume-run.sh` (new file only)
- `D:\RAG_new\CURRENT_STATE.md` (only the bounded date/paragraph edit)

Do not edit the prompt file itself or any other file. Do not stage, commit, or
push. Do not run the remote wrapper.

## Protected baselines

- `CURRENT_STATE.md` pre-edit SHA-256:
  `5FFF8A30F504801AD845BA35E205A58C090C99B68F22A837EDCA3E43326B82EF`
- `scripts/generator_benchmark.py`:
  `7582EF4AD511681D981EEE5628BC6A06B04C3F1EA2D52ADB7D622081765A6CD5`
- `tests/test_generator_benchmark.py`:
  `D09B90DCEFB60AC8B6B9D6D88C2ED54E70691E8C3B232375BBC954FBD2BB7D91`
- `ROADMAP.md`:
  `9F83D07E2BF3282E7D9CDAE8EC6132371D646DCF261D6AFCEE301EDC613C83B0`
- `plan_23_08_2026.md`:
  `0226CD020BBF8F1C2CD341E586DCAEC6857ED4384DE5872F2230A654B0B7C47E`
- `.grok-prompts/c1b-full-run.sh`:
  `02034AD0D766BB3B637744F16A067F927D3E04E5F123F72D5E541ACFD54CCF6A`

All protected files except the explicitly bounded `CURRENT_STATE.md` edit
must retain their hashes.

## Local tool constraints

- Windows PowerShell 5.1 only.
- One shell command per tool call.
- Never invoke Bash, WSL, Docker, containers, or a VM on Windows.
- No command separators `;`, `&&`, `||`, no pipelines, no command
  substitution, no subshell batching, no `python -c`, no POSIX quoting in
  local commands.
- No remote command in this task.
- You may run only the focused local test
  `python -m pytest tests/test_generator_benchmark.py -q` if the sandbox
  permits it. Codex will independently run the required verification.

## Required report

Return the exact files changed, a concise explanation of wrapper preflight /
resume / transcript behavior, whether the focused test ran and its exact
exit/pass/fail summary, confirmation that no remote command ran, and any real
limitation. Do not claim the full benchmark resumed or completed.
