"""The 100-case judge's `run`, with the user's plugins off and the route's refusal reasons kept.

The judge's own `run_plan` writes every row, through the same isolated sender as
`scripts/generator_answer_judge.py run`. Two additions, both outside the rows:
- each request also carries `--settings no-user-plugins.json` (beside this file), which
  disables the two plugins of the Claude CLI's user configuration; one of them, installed
  at 2026-10-15 12:05:00 UTC, loaded into the `--safe-mode` session, and the route refused
  the reply (docs/specs/small-generator-screening.md, amendment of the extension);
- the message of a refused reply, which its row reduces to a code, is appended to
  `refusals.log` in the run's directory.

Usage, from any directory: PYTHONPATH=D:/RAG_new python run100_logged.py LIMIT
"""

import json
import sys
import time
from pathlib import Path

from evaluation import isolated_request as isolated
from evaluation.blinded_judge_clients import JudgeUnavailable
from scripts import generator_answer_judge as judge

OUT = Path("D:/RAG_new/.tmp/genscreen-judge-100")
OVERRIDE = Path(__file__).resolve().with_name("no-user-plugins.json").as_posix()
route_arguments = isolated.arguments


def arguments(system_prompt: str, **options: str) -> tuple[str, ...]:
    return (*route_arguments(system_prompt, **options), "--settings", OVERRIDE)


isolated.arguments = arguments
inner = judge._isolated_sender(judge.CLI_TIMEOUT_S)


def send(system_prompt: str, message: str):
    try:
        return inner(system_prompt, message)
    except JudgeUnavailable as exc:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with (OUT / "refusals.log").open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {exc.code}: {exc.message}\n")
        raise


plan = json.loads((OUT / "plan.json").read_text(encoding="utf-8"))
try:
    graded = judge.run_plan(plan, OUT, send, limit=int(sys.argv[1]))
except JudgeUnavailable as exc:
    print(f"stopped: the route refused a reply ({exc.code}: {exc.message})")
    raise SystemExit(2) from None
print(f"{graded} requests graded")
