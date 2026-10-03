# C.1b Qwen3 8B Mac smoke

## Objective

Act immediately as the write-capable/execution worker for `D:\RAG_new`.
Prepare the exact current source on `deproject-mac`, run one end-to-end
`qwen3:8b` benchmark smoke there with Ollama thinking explicitly disabled,
and record the verified smoke state concisely in `CURRENT_STATE.md`.

Do not do an architecture tour. Start with the focused test or the exact
remote preparation needed for the smoke.

## Known state and non-inventable facts

- Windows workspace: `D:\RAG_new`.
- Git was clean before this prompt was added; HEAD is
  `b8ecc8efb780d423a267595584ef0927ebb77cc5`.
- `b8ecc8e` adds the required `--no-think` support. The benchmark source of
  the measured baseline was `c06bdf5721b434eff32dcf5b9991221d5b2a15f8`.
- Mac SSH alias: `deproject-mac` (`julia@192.168.1.133`).
- Existing isolated Mac worktree:
  `/tmp/rag-new-c06bdf5.WLtg39/worktree`, clean at `c06bdf5` before this task.
  Preserve it and all completed C.1a artifacts.
- Reusable cached contexts:
  `/tmp/rag-new-c06bdf5.WLtg39/worktree/.tmp/ab_candidates_phase2_C.json`,
  required SHA-256
  `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10`.
- Dataset required SHA-256:
  `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720`.
- Required model: `qwen3:8b`, expected digest
  `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`,
  Q4_K_M. Do not pull or substitute a model.
- The smoke is operational validation and must remain `not_evidence`; it is
  not a published Phase-C result.
- Full run id is reserved as `c1b-qwen3-8b-b8ecc8e`; do not launch that full
  3 x 100 run in this task.

## Execution contract

1. Run the focused benchmark tests against the Windows HEAD:
   `python -m pytest tests/test_generator_benchmark.py -q`.
2. Confirm there is no active `c1b-qwen3-8b-b8ecc8e` process on the Mac.
3. Transfer exact Git object `b8ecc8e` to the Mac without pushing. Prefer a
   scoped Git bundle plus `scp`, then create a new isolated clean worktree at
   the exact SHA. Do not mutate the old worktree or the old Mac clone.
4. Reuse the cached contexts in the new worktree only after verifying their
   SHA-256. Verify the tracked dataset SHA-256 too.
5. Verify the installed Ollama tag/digest before generation. Do not run Docker,
   WSL, a VM, or any container on Windows. The model workload must run only on
   the Mac.
6. Run exactly one case and one seed through the real generator + LLM judge +
   pinned NLI checker using `scripts/generator_benchmark.py`. Match the C.1a
   contract: model `qwen3:8b`, `--runs 1`, `--max-cases 1`, context chars 6000,
   seed base 42, temperature 0, num_ctx 4096, num_predict 384, NLI batch size 4,
   and explicit `--no-think`. Use run id
   `c1b-qwen3-8b-b8ecc8e-smoke`. Do not use `--skip-nli`.
7. Require exit code 0, one valid generation, one valid judge result, NLI
   output, zero failed calls/errors, provenance code SHA `b8ecc8e...`, clean
   code tree, expected model digest, expected dataset/context hashes, and
   recorded `ollama_think: false` plus `config.think: false`.
8. If and only if all checks pass, surgically replace the obsolete sentence
   in `CURRENT_STATE.md` that says there was no smoke. Record that the one-case
   smoke passed, is `not_evidence`, used exact SHA `b8ecc8e`, had thinking off,
   and that no full C.1b process was launched. Keep the file at most 150 lines
   and 8 KiB. Do not change roadmap/plan/evidence claims.
9. If any check fails, do not update `CURRENT_STATE.md` and do not retry the
   same command unchanged. Report the exact failure and leave the full run
   unstarted.

For the remote operation, use one attached SSH invocation per bounded command
and make the final smoke invocation print an explicit `DONE` only after the
benchmark exits. Do not poll logs or process state. A generated remote script
may be copied with `scp` and invoked as `ssh deproject-mac bash <path>` to keep
quoting bounded.

Local command tool calls must use Windows PowerShell 5.1 syntax, one shell
command per tool call. Do not use `;`, `&&`, `||`, pipelines, `python -c`,
POSIX quoting in local commands, WSL, or Docker. Keep non-ASCII text out of
shell literals. Preserve LF and UTF-8.

## Allowed and protected files

Allowed local source/state edit:

- `D:\RAG_new\CURRENT_STATE.md` only, and only the bounded factual replacement
  in step 8.

Control/transport artifacts may be created only under
`D:\RAG_new\.grok-prompts\` and remote `/tmp/`.

Protected local hashes from preflight; they must remain unchanged:

- `scripts/generator_benchmark.py`:
  `7582ef4ad511681d981eee5628bc6a06b04c3f1ea2d52adb7d622081765a6cd5`
- `tests/test_generator_benchmark.py`:
  `d09b90dcefb60ac8b6b9d6d88c2ed54e70691e8c3b232375bbc954fbd2bb7d91`
- `ROADMAP.md`:
  `9f83d07e2bf3282e7d9cdae8ec6132371d646dcf261d6afcee301edc613c83b0`
- `plan_23_08_2026.md`:
  `0226cd020bbf8f1c2cd341e586dcaec6857ed4384de5872f2230a654b0b7c47e`

Do not edit any other tracked file, do not commit, and do not push.

## Required report

Return:

- focused test command, exit code, pass/fail count;
- Mac worktree path and exact SHA/clean status;
- verified dataset, contexts, and model digests;
- smoke command arguments (no secrets), exit code, duration, generation/judge/
  NLI/error counts, evidence class, and thinking fields;
- whether `CURRENT_STATE.md` changed;
- final `git status --short` and protected-file hash comparison;
- explicit confirmation that the full run was not launched and no Docker/WSL
  was used on Windows.
