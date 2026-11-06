"""Public cost extraction contracts, using only made-up local inputs."""

from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "reports/codex-usage/tools/codex_usage.py"
USAGE = {
    "input_tokens": 17,
    "output_tokens": 5,
    "cached_input_tokens": 11,
    "cache_write_input_tokens": 2,
    "reasoning_output_tokens": 3,
}
TEXT = "Neutral synthetic meadow text never belongs in statistics."
FILES = ("capture-calls.csv", "rollouts.csv", "window-hours.csv", "summary.json")


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value) + "\n").encode())


def stamp(time):
    return "2026-11-04T" + time + "Z"


def token(time, pct, *, reset="15:00:00", info=True, reached=None):
    return {
        "timestamp": stamp(time),
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {"total_token_usage": {**USAGE, "total_tokens": 22}} if info else None,
            "rate_limits": {
                "primary": {
                    "used_percent": pct,
                    "window_minutes": 300,
                    "resets_at": int(datetime.fromisoformat(stamp(reset)).timestamp()),
                },
                "rate_limit_reached_type": reached,
            },
        },
    }


def rollout(root, name, cwd, snapshots):
    path = root / "sessions/2026/11/04" / name
    events = [
        {
            "type": "session_meta",
            "payload": {
                "timestamp": stamp("09:45:00"),
                "cwd": cwd,
                "originator": "codex_cli",
                "cli_version": "0.166.0",
            },
        },
        *[
            {"type": "turn_context", "payload": {"model": model, "effort": effort}}
            for model, effort in [("gpt-6", "low"), ("gpt-6", "low"), ("gpt-5", "xhigh")]
        ],
        {"type": "token_usage_record", "payload": {"usage": USAGE}},
        *snapshots,
        {"timestamp": stamp("12:30:00"), "type": "response_item", "payload": {"text": TEXT}},
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"malformed\n".join((json.dumps(event) + "\n").encode() for event in events) + b"\xff\n[]\n"
    )
    return path


def call(root, folder, start, end, effort, *, active=None, usage=USAGE, model="gpt-6"):
    path = root / "captures" / folder
    put(
        path / "start.json",
        {
            "utc": stamp(start),
            "cwd": "C:/synthetic/private",
            "argv": ["exec", "-m", model, "-c", "model_reasoning_effort=" + json.dumps(effort)],
            "active_case": json.dumps(active) if active is not None else "malformed",
        },
    )
    if end:
        put(path / "end.json", {"utc": stamp(end), "exit_code": 0})
    completed = {"type": "turn.completed"}
    if usage is not None:
        completed["usage"] = {**usage, "note": TEXT, "bool": True}
    events = [
        {"type": "item.completed", "item": {"type": "agent_message", "text": TEXT}},
        completed,
    ]
    (path / "stdout.bin").write_bytes(
        b"broken\n" + b"".join((json.dumps(event) + "\n").encode() for event in events)
    )
    return path


@pytest.fixture
def tree(tmp_path):
    put(
        tmp_path / "classes.json",
        [
            {"prefix": "d:/synthetic/project", "class": "project"},
            {"prefix": "d:/", "class": "later"},
        ],
    )
    rollout(
        tmp_path, "rollout-listed.jsonl", "D:\\SYNTHETIC\\Project\\work", [token("10:10:00", 25)]
    )
    rollout(
        tmp_path,
        "rollout-unlisted.jsonl",
        "C:/synthetic/another",
        [token("09:50:00", 10), token("10:30:00", 40, info=False), token("12:00:00", 100)],
    )
    put(
        tmp_path / "arms/arm-a.json",
        {"rows": [{"attempts": [{"rollout_file": "C:\\synthetic\\rollout-listed.jsonl"}]}]},
    )
    active = {"key": "base-a", "attempt_id": "private-question-id", "case_id": "private-case-id"}
    call(tmp_path, "attempt-01/capture/calls/z", "10:00:00", "10:01:00", "low", active=active)
    call(tmp_path, "attempt-01/capture/calls/a", "10:00:30", "10:00:40", "low", active=active)
    call(tmp_path, "attempt-01/capture/calls/m", "10:02:00", "10:03:00", "xhigh", active=active)
    call(tmp_path, "capture/calls/killed", "11:30:00", None, "medium", usage=None)
    return tmp_path


def run(root, *, out="out"):
    return subprocess.run(
        [
            sys.executable,
            "-I",
            str(TOOL),
            "--capture-root",
            str(root / "captures"),
            "--sessions",
            str(root / "sessions"),
            "--classes",
            str(root / "classes.json"),
            "--stage5v-arms",
            str(root / "arms"),
            "--out",
            str(root / out),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def rows(root, name):
    with (root / "out" / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_tables_and_byte_identical_rerun(tree):
    result = run(tree)
    assert result.returncode == 0, result.stderr
    calls = rows(tree, "capture-calls.csv")
    assert len(calls) == 4
    assert [r["call"] for r in calls[:3]] == ["1", "2", "3"]
    assert [r["role"] for r in calls] == ["helper", "helper", "answer", "other"]
    assert all(r["completed"] == "true" for r in calls)
    for row in calls[:3]:
        assert {k: int(row[k]) for k in USAGE} == USAGE
        assert row["window_pct_before"] == "10.000"
        assert row["window_pct_after"] == "25.000"
        assert row["base"] == "base-a"
    assert calls[0]["duration_s"] == "60.000"
    killed = calls[-1]
    assert killed["series"] == "capture" and killed["base"] == ""
    assert all(
        killed[k] == ""
        for k in (*USAGE, "duration_s", "exit_code", "window_pct_before", "window_pct_after")
    )
    tasks = rows(tree, "rollouts.csv")
    assert len(tasks) == 1 and tasks[0]["class"] == "project"
    assert tasks[0]["model"] == "gpt-6" and tasks[0]["effort"] == "low"
    assert tasks[0]["turns"] == "3" and tasks[0]["responses"] == "1"
    assert tasks[0]["in_stage5v_record"] == "true"
    assert tasks[0]["end_utc"] == stamp("12:30:00")
    assert {k: int(tasks[0][k]) for k in USAGE} == USAGE
    assert tasks[0]["total_tokens"] == "22"
    hours = rows(tree, "window-hours.csv")
    assert len(hours) == 3
    assert [r["used_pct_max"] for r in hours] == ["10.000", "40.000", "100.000"]
    assert hours[-1]["reached"] == "true"
    data = {name: (tree / "out" / name).read_bytes() for name in FILES}
    for raw in data.values():
        assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
        for secret in (
            TEXT,
            "private-question-id",
            "private-case-id",
            "synthetic/private",
            "rollout-unlisted",
            "cwd",
            "argv",
        ):
            assert secret.encode() not in raw
    assert run(tree).returncode == 0
    assert data == {name: (tree / "out" / name).read_bytes() for name in FILES}
    assert sorted(line.split()[0] for line in result.stdout.splitlines()) == sorted(FILES)
    assert all(line.split()[1].isdigit() for line in result.stdout.splitlines())


def test_summary_totals_percentiles_and_window_share(tree):
    assert run(tree).returncode == 0
    summary = json.loads((tree / "out/summary.json").read_bytes())
    series = summary["capture_series"][0]
    assert series["series"] == "attempt-01"
    assert series["calls_by_role"] == {"helper": 2, "answer": 1, "other": 0}
    assert series["completed_calls"] == 3 and series["distinct_questions"] == 1
    assert series["roles"]["helper"]["usage_sum"] == {k: v * 2 for k, v in USAGE.items()}
    assert series["roles"]["helper"]["usage_median"] == USAGE
    assert series["roles"]["helper"]["duration_median_s"] == 35
    assert series["roles"]["helper"]["duration_p90_s"] == 60
    share = series["window_share"]
    assert share["before_utc"] == stamp("09:50:00")
    assert share["after_utc"] == stamp("10:10:00")
    assert share["difference_pct"] == share["difference_per_question_pct"] == 15
    assert share["upper_bound"] and not share["reset_between"]
    assert summary["rollout_classes"][0]["token_sums"] == {**USAGE, "total_tokens": 22}
    assert summary["window"] == {"window_minutes": [300], "reached_hours": [stamp("12:00:00")]}
    # No 30-minute cutoff in the aggregate window share.
    assert summary["capture_series"][1]["window_share"]["before_utc"] == stamp("10:30:00")


@pytest.mark.parametrize("pct,reset", [(30, "16:00:00"), (5, "15:00:00")])
def test_window_reset_inside_bracketing_snapshots(tree, pct, reset):
    rollout(tree, "rollout-reset.jsonl", "C:/unlisted", [token("10:00:10", pct, reset=reset)])
    assert run(tree).returncode == 0
    summary = json.loads((tree / "out/summary.json").read_bytes())
    share = summary["capture_series"][0]["window_share"]
    assert share["reset_between"] is True
    assert share["difference_pct"] is None and share["difference_per_question_pct"] is None


@pytest.mark.parametrize("unsafe", ["C:/private", "name@example", "Users\\private"])
@pytest.mark.parametrize("field", ["series", "class"])
def test_guard_refuses_before_any_write(tree, unsafe, field):
    if field == "series":
        path = tree / "captures/attempt-01/capture/calls/z/start.json"
        data = json.loads(path.read_bytes())
        active = json.loads(data["active_case"])
        active["series"] = unsafe
        data["active_case"] = json.dumps(active)
        put(path, data)
    else:
        put(tree / "classes.json", [{"prefix": "d:/", "class": unsafe}])
    assert run(tree).returncode != 0
    assert not (tree / "out").exists()
    (tree / "out").mkdir()
    for name in FILES:
        (tree / "out" / name).write_bytes(b"previous\n")
    assert run(tree).returncode != 0
    assert all((tree / "out" / name).read_bytes() == b"previous\n" for name in FILES)


def test_invalid_labels_missing_usage_and_snapshot_boundary(tree):
    call(
        tree,
        "capture/calls/extra",
        "11:00:00",
        "11:30:00",
        "unknown",
        model="C:/private",
        active={"key": "name@example", "series": "latest"},
        usage={"input_tokens": True, "output_tokens": -1, "cached_input_tokens": 1.5},
    )
    assert run(tree).returncode == 0
    row = next(r for r in rows(tree, "capture-calls.csv") if r["series"] == "latest")
    assert row["model"] == row["effort"] == "invalid" and row["base"] == ""
    assert row["role"] == "other" and all(row[k] == "" for k in USAGE)
    assert row["window_pct_before"] == "40.000" and row["window_pct_after"] == "100.000"


def test_null_info_preserves_last_usage_and_reached_marker(tree):
    rollout(
        tree,
        "rollout-listed.jsonl",
        "D:/synthetic/project",
        [token("10:10:00", 25), token("10:20:00", 30, info=False, reached="synthetic limit")],
    )
    assert run(tree).returncode == 0
    row = rows(tree, "rollouts.csv")[0]
    assert row["total_tokens"] == "22" and row["window_pct_last"] == "30.000"
    assert rows(tree, "window-hours.csv")[1]["reached"] == "true"


def test_incomplete_call_and_after_snapshot_outside_thirty_minutes(tree):
    path = call(
        tree,
        "capture/calls/incomplete",
        "11:00:00",
        "11:29:59",
        "high",
        active={"series": "incomplete"},
    )
    (path / "stdout.bin").write_bytes(
        (json.dumps({"type": "item.completed", "item": {"text": TEXT}}) + "\n").encode()
    )
    assert run(tree).returncode == 0
    row = next(r for r in rows(tree, "capture-calls.csv") if r["series"] == "incomplete")
    assert row["completed"] == "false" and row["window_pct_after"] == ""
    assert row["window_pct_before"] == "40.000"
    assert all(row[key] == "" for key in USAGE)
    summary = json.loads((tree / "out/summary.json").read_bytes())
    series = next(s for s in summary["capture_series"] if s["series"] == "incomplete")
    assert series["window_share"]["difference_per_question_pct"] is None
    assert series["distinct_questions"] == series["completed_calls"] == 0


def test_guard_rejects_nonfinite_and_unknown_fields():
    spec = importlib.util.spec_from_file_location("codex_usage_tool", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for value in (
        {"duration_s": float("nan")},
        {"text": TEXT},
        {"model": "name@example"},
        {"series": "C:/private"},
    ):
        with pytest.raises(ValueError):
            module.public_guard(value)
