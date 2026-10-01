"""Contract tests for the separate Astra reference judgment."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from evaluation.blinded_judge import draw_human_sample, load_inputs
from scripts.p2_astra_reference import (
    COMPANION_ARGS,
    EFFORT,
    MODEL,
    find_job_record,
    parse_job_record,
    select_sample,
    verify_rollout,
)


def test_astra_uses_exact_preselected_human_sample() -> None:
    inputs = load_inputs()
    sample = select_sample(inputs)
    assert len(sample) == 10
    assert [case.case_id for case in sample] == [
        case.case_id
        for case in draw_human_sample(inputs.pools["H"].cases, inputs.pools["H"].ruler_per_case)
    ]
    assert all(case.pool == "H" for case in sample)


def test_companion_arguments_pin_astra_xhigh_without_write_modes() -> None:
    assert COMPANION_ARGS == ("--model", "gpt-6-astra", "--effort", "xhigh")
    assert MODEL == "gpt-6-astra"
    assert EFFORT == "xhigh"
    assert not {"--write", "--background", "--resume-last"}.intersection(COMPANION_ARGS)


def test_parse_job_record_accepts_completed_read_only_task() -> None:
    record = {
        "id": "task-muooj5wi-k7yep0",
        "kind": "task",
        "jobClass": "task",
        "workspaceRoot": r"C:\Users\uedom\.claude\scratch\astra-blind",
        "write": False,
        "createdAt": "2026-09-30T22:31:13.314Z",
        "status": "completed",
        "threadId": "01a0f471-8824-76c2-96bc-f6bd3046692d",
        "result": {
            "status": 0,
            "threadId": "01a0f471-8824-76c2-96bc-f6bd3046692d",
            "rawOutput": "OK",
        },
    }
    assert parse_job_record(record) == "OK"


@pytest.mark.parametrize(
    "change",
    [
        {"status": "running"},
        {"result": {"status": 1, "rawOutput": "OK"}},
        {"write": True},
        {"result": {"status": 0, "rawOutput": "  "}},
        {"threadId": None},
    ],
)
def test_parse_job_record_rejects_invalid_job_records(change: dict[str, object]) -> None:
    record: dict[str, object] = {
        "status": "completed",
        "write": False,
        "threadId": "thread-1",
        "result": {"status": 0, "rawOutput": "OK"},
    }
    record.update(change)
    with pytest.raises(ValueError):
        parse_job_record(record)


def _rollout(workspace: Path, *, model: str = MODEL, effort: str = EFFORT) -> str:
    session_id = "thread-1"
    entries = [
        {
            "type": "session_meta",
            "payload": {
                "id": session_id,
                "cwd": str(workspace),
                "cli_version": "0.1.0",
                "model_provider": "openai",
            },
        },
        {
            "type": "turn_context",
            "payload": {
                "cwd": str(workspace),
                "sandbox_policy": {"type": "read-only"},
                "model": model,
                "effort": effort,
            },
        },
        {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": 10,
                        "cached_input_tokens": 1,
                        "cache_write_input_tokens": 0,
                        "output_tokens": 5,
                        "reasoning_output_tokens": 2,
                        "total_tokens": 15,
                    }
                },
            },
        },
    ]
    return "".join(json.dumps(entry) + "\n" for entry in entries)


def _write_rollout(codex_home: Path, thread_id: str, contents: str) -> Path:
    path = codex_home / "sessions" / "2026" / "09" / "30" / f"rollout-time-{thread_id}.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(contents, encoding="utf-8")
    return path


def test_verify_rollout_accepts_expected_model_effort_sandbox_and_cwd(tmp_path: Path) -> None:
    workspace = tmp_path / "empty-workspace"
    workspace.mkdir()
    codex_home = tmp_path / "codex-home"
    path = _write_rollout(codex_home, "thread-1", _rollout(workspace))

    verified = verify_rollout(codex_home, "thread-1", workspace)

    assert verified["model"] == MODEL
    assert verified["effort"] == EFFORT
    assert verified["sandbox"] == "read-only"
    assert verified["codex_cli_version"] == "0.1.0"
    assert verified["rollout_file"] == path.name
    assert verified["total_tokens"] == 15


@pytest.mark.parametrize(
    "contents, message",
    [
        (_rollout(Path("C:/empty"), model="gpt-6-sonnet"), "model"),
        (_rollout(Path("C:/empty"), effort="high"), "effort"),
        (
            _rollout(Path("C:/empty")).replace('"type": "read-only"', '"type": "workspace-write"'),
            "sandbox",
        ),
        (_rollout(Path("C:/other")), "cwd"),
        (
            _rollout(Path("C:/empty")).replace('"type": "turn_context"', '"type": "other"'),
            "turn_context",
        ),
        (
            _rollout(Path("C:/empty")).replace(
                '"type": "turn_context"', '"type": "turn_context"', 1
            )
            + json.dumps(
                {
                    "type": "turn_context",
                    "payload": {
                        "cwd": "C:/empty",
                        "sandbox_policy": {"type": "read-only"},
                        "model": MODEL,
                        "effort": EFFORT,
                    },
                }
            )
            + "\n",
            "exactly one",
        ),
    ],
)
def test_verify_rollout_rejects_mismatched_context(
    tmp_path: Path, contents: str, message: str
) -> None:
    workspace = tmp_path / "empty-workspace"
    workspace.mkdir()
    codex_home = tmp_path / "codex-home"
    _write_rollout(codex_home, "thread-1", contents)
    with pytest.raises(ValueError, match=message):
        verify_rollout(codex_home, "thread-1", workspace)


def test_verify_rollout_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="rollout"):
        verify_rollout(tmp_path / "missing", "thread-1", tmp_path)


def test_find_job_record_selects_newest_record_for_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "empty"
    workspace.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    state = tmp_path / "state"
    jobs = state / "state" / "one" / "jobs"
    jobs.mkdir(parents=True)
    launch = datetime(2026, 9, 30, 22, 0, tzinfo=timezone.utc)
    records = [
        {"id": "older", "workspaceRoot": str(workspace), "createdAt": "2026-09-30T22:01:00Z"},
        {"id": "other", "workspaceRoot": str(other), "createdAt": "2026-09-30T22:09:00Z"},
        {"id": "newer", "workspaceRoot": str(workspace), "createdAt": "2026-09-30T22:05:00Z"},
    ]
    for index, record in enumerate(records):
        (jobs / f"{index}.json").write_text(json.dumps(record), encoding="utf-8")

    assert find_job_record(state, workspace, launch)["id"] == "newer"
