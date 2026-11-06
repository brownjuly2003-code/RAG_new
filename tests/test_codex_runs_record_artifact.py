"""Bind the public Codex runs capsule to its outputs, without reading private sources."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPSULE = ROOT / "docs/evidence/codex-runs-record.md"
PUBLIC = ROOT / "reports/codex-usage"
TOOL = PUBLIC / "tools/codex_usage.py"
OUTPUTS = ("capture-calls.csv", "rollouts.csv", "window-hours.csv", "summary.json")
TOKENS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


def _read(path):
    raw = path.read_bytes()
    assert b"\r" not in raw, path
    assert raw.endswith(b"\n"), path
    assert not raw.startswith(b"\xef\xbb\xbf"), path
    return raw, raw.decode("utf-8")


def _tables(text):
    tables = {}
    section = None
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:]
        if line.startswith("|"):
            assert section is not None
            cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                continue
            tables.setdefault(section, []).append(cells)
    return tables


def _check_table(tables, section, header, expected):
    actual = tables.pop(section)
    assert actual[0] == header
    assert len(actual[1:]) == len(expected), section
    for cells, values in zip(actual[1:], expected, strict=True):
        assert len(cells) == len(values), (section, cells)
        for cell, value in zip(cells, values, strict=True):
            if value is None:
                assert cell == "—", (section, cells)
            elif isinstance(value, bool):
                assert cell == str(value).lower(), (section, cells)
            elif isinstance(value, (int, Decimal)):
                assert Decimal(cell) == value, (section, cells)
            else:
                assert cell == value, (section, cells)


def _csv_value(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def test_codex_runs_record_hashes_rows_privacy_and_lf():
    _, capsule = _read(CAPSULE)
    table = _tables(capsule)["Files"]
    assert table[0] == ["File", "SHA-256", "Data rows"]
    named = {row[0]: row[1:] for row in table[1:]}
    paths = [TOOL, *(PUBLIC / name for name in OUTPUTS)]
    assert len(table[1:]) == len(paths)
    assert set(named) == {path.relative_to(ROOT).as_posix() for path in paths}

    spec = importlib.util.spec_from_file_location("codex_runs_record_usage_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    columns = {
        "capture-calls.csv": module.CAPTURE_COLUMNS,
        "rollouts.csv": module.ROLLOUT_COLUMNS,
        "window-hours.csv": module.HOUR_COLUMNS,
    }
    for path in paths:
        raw, text = _read(path)
        digest, count = named[path.relative_to(ROOT).as_posix()]
        assert hashlib.sha256(raw).hexdigest() == digest, path
        if path == TOOL:
            assert count == "—"
            continue
        assert not any(marker in text.casefold() for marker in (":/", ":\\", "users", "@"))
        if path.suffix == ".csv":
            reader = csv.DictReader(io.StringIO(text, newline=""))
            assert reader.fieldnames == list(columns[path.name])
            rows = list(reader)
            assert all(set(row) == set(reader.fieldnames) for row in rows)
            assert len(rows) == int(count), path
            value = [{key: _csv_value(cell) for key, cell in row.items()} for row in rows]
        else:
            assert count == "—"
            value = json.loads(text)
        module.public_guard(value)


def test_codex_runs_record_tables_equal_summary():
    _, capsule = _read(CAPSULE)
    summary = json.loads(_read(PUBLIC / "summary.json")[1], parse_float=Decimal)
    tables = _tables(capsule)
    tables.pop("Files")  # Digests and CSV row counts are checked against the files above.
    captures = summary["capture_series"]
    _check_table(
        tables,
        "Capture calls",
        ["Series", "Questions", "Helper", "Answer", "Other", "Completed"],
        [
            [
                row["series"],
                row["distinct_questions"],
                *(row["calls_by_role"][role] for role in ("helper", "answer", "other")),
                row["completed_calls"],
            ]
            for row in captures
        ],
    )
    _check_table(
        tables,
        "Capture tokens and durations",
        [
            "Series",
            "Role",
            "Input",
            "Cached input",
            "Cache write",
            "Output",
            "Reasoning",
            "Median s",
            "P90 s",
        ],
        [
            [
                row["series"],
                role,
                *(stats["usage_sum"][key] for key in TOKENS),
                stats["duration_median_s"],
                stats["duration_p90_s"],
            ]
            for row in captures
            for role in ("helper", "answer", "other")
            for stats in [row["roles"][role]]
        ],
    )
    _check_table(
        tables,
        "Capture window share — upper bound",
        [
            "Series",
            "Before %",
            "After %",
            "Difference pp",
            "Per question pp",
            "Reset",
            "Upper bound",
        ],
        [
            [
                row["series"],
                *(
                    row["window_share"][key]
                    for key in (
                        "before_pct",
                        "after_pct",
                        "difference_pct",
                        "difference_per_question_pct",
                        "reset_between",
                        "upper_bound",
                    )
                ),
            ]
            for row in captures
        ],
    )
    _check_table(
        tables,
        "Rollout classes",
        [
            "Class",
            "Tasks",
            "Turns",
            "Responses",
            "Input",
            "Cached input",
            "Cache write",
            "Output",
            "Reasoning",
            "Total",
            "Median s",
            "P90 s",
        ],
        [
            [
                row["class"],
                row["tasks"],
                row["turns"],
                row["responses"],
                *(row["token_sums"][key] for key in (*TOKENS, "total_tokens")),
                row["duration_median_s"],
                row["duration_p90_s"],
            ]
            for row in summary["rollout_classes"]
        ],
    )
    _check_table(
        tables,
        "Window lengths seen",
        ["Minutes"],
        [[value] for value in summary["window"]["window_minutes"]],
    )
    _check_table(
        tables,
        "Hours the window was reached",
        ["Hour UTC"],
        [[value] for value in summary["window"]["reached_hours"]],
    )
    assert not tables, "Every capsule table must be checked"
