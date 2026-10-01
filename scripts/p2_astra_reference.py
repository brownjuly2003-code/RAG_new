#!/usr/bin/env python3
"""Request GPT-6-Astra reference grades for P2's ten-case blind human sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation import blinded_judge as p2  # noqa: E402
from evaluation.blinded_judge_clients import JudgeUnavailable, Reply  # noqa: E402

MODEL = "gpt-6-astra"
EFFORT = "xhigh"
JUDGE = "astra-xhigh"
COMPANION = Path(
    "C:/Users/uedom/.claude/plugins/cache/openai-codex/codex/1.0.4/scripts/codex-companion.mjs"
)
CODEX_HOME = Path(os.environ.get("P2_ASTRA_CODEX_HOME", r"C:\Users\uedom\.codex-work"))
STATE_ROOT = PROJECT_ROOT / ".tmp/cx-work-state"
COMPANION_ARGS = ("--model", MODEL, "--effort", EFFORT)
OUT_DIR = PROJECT_ROOT / "reports/p2/astra-reference"
TASK_TIMEOUT_S = 900
TOKEN_USAGE_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)


def select_sample(inputs: p2.Inputs) -> list[p2.Case]:
    pool = inputs.pools["H"]
    return p2.draw_human_sample(pool.cases, pool.ruler_per_case)


def parse_job_record(record: dict[str, Any]) -> str:
    if record.get("status") != "completed":
        raise ValueError("Codex companion job did not complete")
    if record.get("write") is not False:
        raise ValueError("Codex companion job was not read-only")
    thread_id = record.get("threadId")
    if not isinstance(thread_id, str) or not thread_id.strip():
        raise ValueError("Codex companion job has no threadId")
    result = record.get("result")
    if not isinstance(result, dict) or result.get("status") != 0:
        raise ValueError("Codex companion job result was not successful")
    raw_output = result.get("rawOutput")
    if not isinstance(raw_output, str) or not raw_output.strip():
        raise ValueError("Codex companion job returned empty rawOutput")
    return raw_output


def _normalised_path(path: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def find_job_record(state_root: Path, workspace: Path, not_before: datetime) -> dict[str, Any]:
    matches: list[tuple[datetime, dict[str, Any]]] = []
    for path in state_root.glob("state/*/jobs/*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict):
                continue
            if _normalised_path(record.get("workspaceRoot", "")) != _normalised_path(workspace):
                continue
            created_at = datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00"))
            if created_at >= not_before:
                matches.append((created_at, record))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    if not matches:
        raise ValueError("No recent Codex companion job record found for workspace")
    return max(matches, key=lambda item: item[0])[1]


def verify_rollout(codex_home: Path, thread_id: str, workspace: Path) -> dict[str, Any]:
    rollouts = list((codex_home / "sessions").rglob(f"rollout-*-{thread_id}.jsonl"))
    if not rollouts:
        raise ValueError("Codex rollout file is missing")
    rollout = max(rollouts, key=lambda path: path.stat().st_mtime_ns)
    session_meta: dict[str, Any] | None = None
    turn_contexts: list[dict[str, Any]] = []
    last_usage: dict[str, Any] | None = None
    try:
        with rollout.open(encoding="utf-8") as stream:
            for line in stream:
                entry = json.loads(line)
                if not isinstance(entry, dict):
                    continue
                payload = entry.get("payload")
                if not isinstance(payload, dict):
                    continue
                if entry.get("type") == "session_meta" and payload.get("id") == thread_id:
                    session_meta = payload
                elif entry.get("type") == "turn_context":
                    turn_contexts.append(payload)
                elif entry.get("type") == "event_msg" and payload.get("type") == "token_count":
                    info = payload.get("info")
                    usage = info.get("total_token_usage") if isinstance(info, dict) else None
                    if isinstance(usage, dict):
                        last_usage = usage
    except (OSError, ValueError) as exc:
        raise ValueError("Codex rollout file is unreadable or invalid") from exc

    if len(turn_contexts) != 1:
        raise ValueError("Codex rollout must contain exactly one turn_context")
    context = turn_contexts[0]
    if context.get("model") != MODEL:
        raise ValueError("Codex rollout used a different model")
    if context.get("effort") != EFFORT:
        raise ValueError("Codex rollout used a different effort")
    sandbox_policy = context.get("sandbox_policy")
    if not isinstance(sandbox_policy, dict) or sandbox_policy.get("type") != "read-only":
        raise ValueError("Codex rollout sandbox is not read-only")
    expected_cwd = _normalised_path(workspace)
    if _normalised_path(context.get("cwd", "")) != expected_cwd:
        raise ValueError("Codex rollout turn_context cwd does not match workspace")
    if session_meta is None:
        raise ValueError("Codex rollout session_meta is missing")
    if _normalised_path(session_meta.get("cwd", "")) != expected_cwd:
        raise ValueError("Codex rollout session_meta cwd does not match workspace")
    if last_usage is None:
        raise ValueError("Codex rollout token usage is missing")
    return {
        "model": MODEL,
        "effort": EFFORT,
        "sandbox": "read-only",
        "cwd": str(workspace),
        "codex_cli_version": session_meta.get("cli_version"),
        "model_provider": session_meta.get("model_provider"),
        "rollout_file": rollout.name,
        **{field: last_usage.get(field) for field in TOKEN_USAGE_FIELDS},
    }


class AstraCompanionClient:
    def __init__(
        self,
        node_executable: str,
        total: int,
        *,
        codex_home: Path = CODEX_HOME,
        state_root: Path = STATE_ROOT,
    ) -> None:
        self.node_executable = node_executable
        self.total = total
        self.codex_home = codex_home
        self.state_root = state_root
        self.called = 0

    def grade(self, request_text: str) -> Reply:
        self.called += 1
        print(f"Astra request {self.called}/{self.total} started", flush=True)
        start = time.monotonic()
        workspace = Path(tempfile.mkdtemp(prefix="p2-astra-blind-"))
        request_path = workspace / "request.md"
        try:
            request_path.write_text(request_text, encoding="utf-8", newline="\n")
            launched_at = datetime.now(timezone.utc)
            environment = os.environ.copy()
            environment.pop("CODEX_COMPANION_APP_SERVER_ENDPOINT", None)
            environment["CODEX_HOME"] = str(self.codex_home)
            environment["CLAUDE_PLUGIN_DATA"] = str(self.state_root)
            try:
                process = subprocess.run(
                    [
                        self.node_executable,
                        str(COMPANION),
                        "task",
                        *COMPANION_ARGS,
                        "--cwd",
                        str(workspace),
                        "--prompt-file",
                        str(request_path),
                    ],
                    cwd=workspace,
                    env=environment,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=TASK_TIMEOUT_S,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise JudgeUnavailable(
                    "companion_timeout", "Codex companion task timed out"
                ) from exc
            if process.returncode != 0:
                raise JudgeUnavailable(
                    "companion_exit", f"Codex companion exited with {process.returncode}"
                )
            try:
                record = find_job_record(self.state_root, workspace, launched_at)
                raw_text = parse_job_record(record)
            except ValueError as exc:
                raise JudgeUnavailable("companion_record", str(exc)) from exc
            thread_id = record["threadId"]
            try:
                verification = verify_rollout(self.codex_home, thread_id, workspace)
            except ValueError as exc:
                raise JudgeUnavailable("rollout", str(exc)) from exc
            print(f"Astra request {self.called}/{self.total} returned", flush=True)
            return Reply(
                raw_text,
                MODEL,
                {
                    **verification,
                    "thread_id": thread_id,
                    "job_id": record.get("id"),
                    "effort": EFFORT,
                },
                time.monotonic() - start,
            )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temp.replace(path)


def write_summary(sample: Sequence[p2.Case], store_path: Path, out_dir: Path) -> dict[str, Any]:
    stored = p2.read_store(store_path)
    graded = {
        (row["pool"], row["case_id"], row["request_sha256"]): row
        for row in stored
        if row.get("status") == "graded"
    }
    ratings: list[dict[str, Any]] = []
    graded_rows: list[dict[str, Any]] = []
    for case in sample:
        request = p2.build_request(case)
        row = graded.get((case.pool, case.case_id, request.sha256))
        if row is None:
            continue
        if (
            row.get("judge") != JUDGE
            or row.get("model") != MODEL
            or len(row.get("grades", [])) != 5
        ):
            raise ValueError(f"invalid Astra rating for {case.case_id}")
        presented = p2.parse_grades(row["raw_text"], tuple(f"D{index}" for index in range(1, 6)))
        usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
        ratings.append(
            {
                "pool": case.pool,
                "case_id": case.case_id,
                "request_sha256": request.sha256,
                "model": row["model"],
                "grades": row["grades"],
                "presented_grades": [presented[f"D{index}"] for index in range(1, 6)],
                "raw_text": row["raw_text"],
                "thread_id": usage.get("thread_id"),
            }
        )
        graded_rows.append(row)
    distribution = dict(
        sorted(Counter(grade for row in ratings for grade in row["grades"]).items())
    )
    summary = {
        "schema_version": "p2-astra-reference/v1",
        "model": MODEL,
        "effort": EFFORT,
        "judge": JUDGE,
        "route": "Codex companion task, ChatGPT work profile, direct runtime, read-only sandbox, empty temporary cwd",
        "companion_arguments": list(COMPANION_ARGS),
        "codex_cli_version": next(
            (
                row.get("usage", {}).get("codex_cli_version")
                for row in graded_rows
                if isinstance(row.get("usage"), dict)
            ),
            None,
        ),
        "instruction_sha256": p2.INSTRUCTION_SHA256,
        "sample_cases": len(sample),
        "graded_cases": len(ratings),
        "graded_documents": len(ratings) * 5,
        "complete": len(ratings) == len(sample),
        "ratings_order": "grades use original top-five order; presented_grades use blind D1-D5 order",
        "grade_distribution": distribution,
        "reported_cost_usd": None,
        "total_tokens": sum(
            row.get("usage", {}).get("total_tokens", 0)
            for row in graded_rows
            if isinstance(row.get("usage"), dict)
        ),
        "reply_store_sha256": hashlib.sha256(store_path.read_bytes()).hexdigest()
        if store_path.is_file()
        else None,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "boundary": "Model reference only; not human grades or the registered P2 verdict.",
    }
    _write_json(out_dir / "ratings.json", ratings)
    _write_json(out_dir / "summary.json", summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--codex-home", type=Path, default=CODEX_HOME)
    parser.add_argument("--state-root", type=Path, default=STATE_ROOT)
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("limit must be positive")
    executable = shutil.which("node")
    if executable is None:
        parser.error("node is not installed")
    inputs = p2.load_inputs()
    sample = select_sample(inputs)
    store_path = args.out_dir / "replies.jsonl"
    result = p2.run_judge(
        JUDGE,
        AstraCompanionClient(
            executable,
            len(sample),
            codex_home=args.codex_home,
            state_root=args.state_root,
        ),
        sample,
        store_path,
        control_precision=inputs.control_precision,
        limit=args.limit,
    )
    summary = write_summary(sample, store_path, args.out_dir)
    print(
        json.dumps(
            {
                "run": result,
                "graded_cases": summary["graded_cases"],
                "complete": summary["complete"],
            }
        ),
        flush=True,
    )
    return (
        0
        if (
            result["status"] == "available"
            and result["missing"] == 0
            and (summary["complete"] or args.limit is not None)
        )
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
