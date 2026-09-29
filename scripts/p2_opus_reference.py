#!/usr/bin/env python3
"""Request Opus reference grades for P2's ten-case blind human sample."""

from __future__ import annotations

import argparse
import hashlib
import json
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

MODEL = "claude-opus-5-5"
SYSTEM_PROMPT = (
    "You are an independent document relevance judge. Use only the supplied text, "
    "grade each document on its own, and return only the requested JSON object."
)
CLI_ARGS = (
    "-p",
    "--model",
    MODEL,
    "--effort",
    "max",
    "--tools",
    "",
    "--permission-mode",
    "dontAsk",
    "--disable-slash-commands",
    "--strict-mcp-config",
    "--no-session-persistence",
    "--output-format",
    "json",
    "--system-prompt",
    SYSTEM_PROMPT,
)
OUT_DIR = PROJECT_ROOT / "reports/p2/opus-reference"


def select_sample(inputs: p2.Inputs) -> list[p2.Case]:
    pool = inputs.pools["H"]
    return p2.draw_human_sample(pool.cases, pool.ruler_per_case)


def parse_cli_envelope(raw_json: str) -> dict[str, Any]:
    try:
        data = json.loads(raw_json)
    except ValueError as exc:
        raise ValueError("Claude CLI did not return JSON") from exc
    if not isinstance(data, dict) or data.get("is_error") is not False:
        raise ValueError("Claude CLI returned an error")
    if data.get("terminal_reason") != "completed":
        raise ValueError("Claude CLI did not complete")
    model_usage = data.get("modelUsage")
    if not isinstance(model_usage, dict) or set(model_usage) != {MODEL}:
        raise ValueError("Claude CLI used a different model")
    reported = model_usage[MODEL]
    if not isinstance(reported, dict) or reported.get("canonicalModel") != MODEL:
        raise ValueError("Claude CLI did not confirm the requested model")
    if reported.get("provider") != "firstParty":
        raise ValueError("Claude CLI did not use the first-party provider")
    result = data.get("result")
    if not isinstance(result, str) or not result.strip():
        raise ValueError("Claude CLI returned no judgment")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    return {
        "result": result,
        "model": MODEL,
        "usage": {**usage, "total_cost_usd": data.get("total_cost_usd")},
    }


class OpusCliClient:
    def __init__(self, executable: str, total: int) -> None:
        self.executable = executable
        self.total = total
        self.called = 0

    def grade(self, request_text: str) -> Reply:
        self.called += 1
        print(f"Opus request {self.called}/{self.total} started", flush=True)
        start = time.monotonic()
        try:
            process = subprocess.run(
                [self.executable, *CLI_ARGS],
                input=request_text,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=tempfile.gettempdir(),
                timeout=300,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise JudgeUnavailable("cli_timeout", "Claude CLI request timed out") from exc
        if process.returncode != 0:
            raise JudgeUnavailable("cli_exit", f"Claude CLI exited with {process.returncode}")
        try:
            envelope = parse_cli_envelope(process.stdout)
        except ValueError as exc:
            raise JudgeUnavailable("cli_response", str(exc)) from exc
        print(f"Opus request {self.called}/{self.total} returned", flush=True)
        return Reply(
            envelope["result"],
            envelope["model"],
            envelope["usage"],
            time.monotonic() - start,
        )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temp.replace(path)


def write_summary(
    sample: Sequence[p2.Case], store_path: Path, out_dir: Path, cli_version: str
) -> dict[str, Any]:
    stored = p2.read_store(store_path)
    graded = {
        (row["pool"], row["case_id"], row["request_sha256"]): row
        for row in stored
        if row.get("status") == "graded"
    }
    ratings: list[dict[str, Any]] = []
    for case in sample:
        request = p2.build_request(case)
        row = graded.get((case.pool, case.case_id, request.sha256))
        if row is None:
            continue
        if row.get("model") != MODEL or len(row.get("grades", [])) != 5:
            raise ValueError(f"invalid Opus rating for {case.case_id}")
        presented = p2.parse_grades(row["raw_text"], tuple(f"D{index}" for index in range(1, 6)))
        ratings.append(
            {
                "pool": case.pool,
                "case_id": case.case_id,
                "request_sha256": request.sha256,
                "model": row["model"],
                "grades": row["grades"],
                "presented_grades": [presented[f"D{index}"] for index in range(1, 6)],
                "raw_text": row["raw_text"],
            }
        )
    distribution = dict(
        sorted(Counter(grade for row in ratings for grade in row["grades"]).items())
    )
    costs = [
        row.get("usage", {}).get("total_cost_usd") for row in stored if row.get("model") == MODEL
    ]
    summary = {
        "schema_version": "p2-opus-reference/v1",
        "model": MODEL,
        "effort": "max",
        "route": "Claude Code CLI, firstParty claude.ai Max",
        "cli_version": cli_version,
        "cli_arguments": list(CLI_ARGS),
        "instruction_sha256": p2.INSTRUCTION_SHA256,
        "sample_cases": len(sample),
        "graded_cases": len(ratings),
        "graded_documents": len(ratings) * 5,
        "complete": len(ratings) == len(sample),
        "ratings_order": "grades use original top-five order; presented_grades use blind D1-D5 order",
        "grade_distribution": distribution,
        "reported_cost_usd": round(
            sum(float(cost) for cost in costs if isinstance(cost, (int, float))), 6
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
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("limit must be positive")
    executable = shutil.which("claude.cmd") or shutil.which("claude")
    if executable is None:
        parser.error("Claude CLI is not installed")
    cli_version = subprocess.run(
        [executable, "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=tempfile.gettempdir(),
        timeout=30,
        check=True,
    ).stdout.strip()
    inputs = p2.load_inputs()
    sample = select_sample(inputs)
    store_path = args.out_dir / "replies.jsonl"
    result = p2.run_judge(
        "opus-5.5-max",
        OpusCliClient(executable, len(sample)),
        sample,
        store_path,
        control_precision=inputs.control_precision,
        limit=args.limit,
    )
    summary = write_summary(sample, store_path, args.out_dir, cli_version)
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
