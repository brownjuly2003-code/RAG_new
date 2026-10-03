# Grok task: inspect the active C.1b Mac benchmark

## Objective

Immediately inspect the already-running `c1b-qwen3-8b-b8ecc8e` benchmark on
the SSH host `deproject-mac`. Do not start, restart, resume, stop, or otherwise
modify the benchmark. This is one bounded status/harvest operation, not an
architecture review.

If the run has completed, copy its report, log, and checkpoint (when present)
only into the allowed local temporary directory for independent Codex
verification. If it is still active, report one current snapshot and stop.

## Known facts and non-inventable contract

- Windows workspace: `D:\RAG_new`
- SSH alias: `deproject-mac`
- Remote result directory:
  `/tmp/rag-new-b8ecc8e.tdcVc2/results`
- Run id: `c1b-qwen3-8b-b8ecc8e`
- Expected report:
  `c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json`
- Expected checkpoint: `c1b-qwen3-8b-b8ecc8e-checkpoint.json`
- Expected log: `c1b-qwen3-8b-b8ecc8e.log`
- Expected code SHA: `b8ecc8efb780d423a267595584ef0927ebb77cc5`
- Expected dataset SHA-256:
  `3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720`
- Expected contexts SHA-256:
  `91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10`
- Expected model digest:
  `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`
- A completed run is not accepted unless the log has both
  `FULL_VALIDATION_OK` and a final `DONE` marker and the report has 3 runs,
  exactly 100 cases per run, zero failed cases, and 300 valid rows.
- Last durable observation said the run was active at run 1/3, case 9/100.
  Treat that only as stale context and measure one fresh snapshot.

## Allowed local writes

- `D:\RAG_new\.tmp\c1b-inspection\inspect_c1b.py`
- `D:\RAG_new\.tmp\c1b-inspection\c1b-qwen3-8b-b8ecc8e-phase-c-generator-benchmark.json`
- `D:\RAG_new\.tmp\c1b-inspection\c1b-qwen3-8b-b8ecc8e-checkpoint.json`
- `D:\RAG_new\.tmp\c1b-inspection\c1b-qwen3-8b-b8ecc8e.log`

Create `inspect_c1b.py` as the first action. It must use Python standard
library only and, when run on the Mac, print a bounded snapshot: matching
processes, file existence and sizes, checkpoint progress that can be derived
without guessing, report run/case/failure counts when present, presence of
the two required log markers, at most the last 25 log lines, and a final
literal `DONE` marker. Do not print environment variables or secrets.

Copy that script to a unique `/tmp/c1b-inspect-grok-20260902-01.py` path on
the Mac with `scp`, then execute it with exactly one attached `ssh` invocation.
Do not poll, sleep, tail-follow, or issue repeated status commands. Copy result
artifacts back only when they exist; never alter the remote originals.

## Protected files and paths

Do not edit, delete, stage, commit, or overwrite any tracked repository file,
anything under `D:\RAG_new\.grok-prompts`, or any remote benchmark/worktree
file. The workspace already has user-owned dirty state.

Protected SHA-256 baselines:

- `CURRENT_STATE.md` =
  `5FFF8A30F504801AD845BA35E205A58C090C99B68F22A837EDCA3E43326B82EF`
- `.grok-prompts/c1b-full-run.sh` =
  `02034AD0D766BB3B637744F16A067F927D3E04E5F123F72D5E541ACFD54CCF6A`
- `.grok-prompts/c1b-qwen3-smoke-passed.json` =
  `F9DD1728603320F16B105A8F5C2C1C7C1F30D3C828C4FF5D43B5B456C134F1A1`
- `.grok-prompts/c1b-setup-worktree.sh` =
  `A5DA35682FAE769CBEFED27AC43A73860400ADCB323EC2674B867ADA63A914CC`
- `.grok-prompts/c1b-smoke-run.sh` =
  `49A5EF5E10ADFE03CDE6B17A08811A35FC7FF834945BA9D2A258F65F2499296A`
- `.grok-prompts/previous-c1b-smoke-failed.json` =
  `648C21A0503EC00862C95944950F0C59493B4F55320B4B3B46087F6E4DB39879`
- `.grok-prompts/c1b-b8ecc8e.bundle` =
  `680D91A7862B9F02DDC118F9396528764D7034125C62C7C3769C081D59A97841`
- `.grok-prompts/c1b-qwen3-mac-smoke-20260901.md` =
  `309D480B86C59BE5F318E072B2BA6F017B75CB47A8CD11FC814728257286B9BE`

## Shell and safety constraints

- Use Windows PowerShell 5.1 for local commands.
- One shell command per tool call.
- Do not invoke `bash`, WSL, Docker, or any local container runtime on Windows.
- Do not use command separators `;`, `&&`, or `||`, and do not use pipelines.
- Do not use `python -c` or POSIX quoting locally.
- Mac-side Python is allowed only through the copied script file.
- Do not expose credentials, SSH configuration, or environment values.
- Do not use Git write operations and do not commit or push.

## Required report

Return:

1. Whether the benchmark process is active, completed, or absent/interrupted.
2. Exact checkpoint progress supported by the observed JSON/log, with no guess.
3. Presence/absence and sizes of report, checkpoint, and log.
4. Whether both `FULL_VALIDATION_OK` and final `DONE` were observed.
5. Any copied local artifact paths.
6. Every local file created or changed.
7. Any blocker or anomaly, including the exact bounded evidence needed for a
   safe resume; do not perform that resume.
