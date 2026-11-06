"""Extract public cost tables from private captures and Codex logs (stdlib only).

Run with Python 3.11+, including python -I. No source text or source paths are
copied to outputs or diagnostics. Series and class labels must be lowercase
slugs of at most 32 characters; invalid labels abort before any output write.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any

USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "reasoning_output_tokens",
)
TOTAL_KEYS = (*USAGE_KEYS, "total_tokens")
EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "invalid"}
ROLES = ("helper", "answer", "other")
SLUG = re.compile(r"[a-z0-9_-]{1,32}")
MODEL = re.compile(r"[a-z0-9.\-]{1,40}")
LABEL = re.compile(r"[A-Za-z0-9 _.-]{1,40}")
ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z")
CAPTURE_COLUMNS = (
    "series",
    "base",
    "call",
    "start_utc",
    "duration_s",
    "model",
    "effort",
    "role",
    "exit_code",
    "completed",
    *USAGE_KEYS,
    "window_pct_before",
    "window_pct_after",
)
ROLLOUT_COLUMNS = (
    "class",
    "start_utc",
    "end_utc",
    "duration_s",
    "originator",
    "cli_version",
    "model",
    "effort",
    "turns",
    "responses",
    *TOTAL_KEYS,
    "window_pct_first",
    "window_pct_last",
    "window_resets_first",
    "window_resets_last",
    "in_stage5v_record",
)
HOUR_COLUMNS = (
    "hour_utc",
    "window_minutes",
    "used_pct_min",
    "used_pct_max",
    "resets_at_utc",
    "reached",
)
TIME_FIELDS = {
    "start_utc",
    "end_utc",
    "hour_utc",
    "resets_at_utc",
    "window_resets_first",
    "window_resets_last",
    "first_call_utc",
    "last_call_utc",
    "before_utc",
    "after_utc",
    "reached_hours",
}
PUBLIC_KEYS = {
    *CAPTURE_COLUMNS,
    *ROLLOUT_COLUMNS,
    *HOUR_COLUMNS,
    *TIME_FIELDS,
    *ROLES,
    "capture_series",
    "rollout_classes",
    "window",
    "calls_by_role",
    "completed_calls",
    "distinct_questions",
    "roles",
    "usage_sum",
    "usage_median",
    "duration_median_s",
    "duration_p90_s",
    "window_share",
    "before_pct",
    "after_pct",
    "difference_pct",
    "difference_per_question_pct",
    "reset_between",
    "upper_bound",
    "tasks",
    "token_sums",
}


def timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def iso(value: datetime | None) -> str:
    return value.isoformat().replace("+00:00", "Z") if value is not None else ""


def nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def counts(value: Any, keys: tuple[str, ...]) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {key: value[key] for key in keys if nonnegative_int(value.get(key))}


def matched(value: Any, pattern: re.Pattern[str], fallback: str = "") -> str:
    return value if isinstance(value, str) and pattern.fullmatch(value) else fallback


def effort(value: Any) -> str:
    return value if isinstance(value, str) and value in EFFORTS else "invalid"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def events(path: Path):
    # Decode one line at a time: damaged lines never discard later measurements.
    with path.open("rb") as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if isinstance(event, dict):
                yield event


def object_value(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def public_guard(value: Any, field: str = "") -> None:
    """Validate the complete in-memory outputs before creating the output dir."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key not in PUBLIC_KEYS:
                raise ValueError("invalid public field")
            public_guard(item, key)
        return
    if isinstance(value, list):
        for item in value:
            public_guard(item, field)
        return
    if value is None or type(value) in {int, bool}:
        return
    if type(value) is float and math.isfinite(value):
        return
    if not isinstance(value, str):
        raise ValueError("invalid public value")
    if any(marker in value.casefold() for marker in (":/", ":\\", "/users/", "users\\", "@")):
        raise ValueError("private marker in public value")
    if value == "":
        return
    valid = False
    if field in TIME_FIELDS:
        valid = bool(ISO.fullmatch(value) and timestamp(value) is not None)
    elif field in {"series", "base", "class"}:
        valid = bool(SLUG.fullmatch(value))
    elif field == "model":
        valid = bool(MODEL.fullmatch(value))
    elif field in {"originator", "cli_version"}:
        valid = bool(LABEL.fullmatch(value))
    elif field == "effort":
        valid = value in EFFORTS
    elif field == "role":
        valid = value in ROLES
    if not valid:
        raise ValueError("invalid public string")


@dataclass(frozen=True)
class Snapshot:
    time: datetime
    used: float
    minutes: int
    reset: datetime
    reached: bool


def snapshot(payload: dict, time: datetime | None) -> Snapshot | None:
    limits = object_value(payload.get("rate_limits"))
    primary = object_value(limits.get("primary"))
    used, minutes, reset = (primary.get(k) for k in ("used_percent", "window_minutes", "resets_at"))
    if (
        time is None
        or type(used) not in {int, float}
        or not math.isfinite(used)
        or used < 0
        or not nonnegative_int(minutes)
        or minutes == 0
        or type(reset) not in {int, float}
    ):
        return None
    try:
        reset_time = datetime.fromtimestamp(reset, timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    return Snapshot(
        time,
        float(used),
        minutes,
        reset_time,
        limits.get("rate_limit_reached_type") is not None or used >= 100,
    )


class Windows:
    def __init__(self, snapshots: list[Snapshot]):
        # Stable ties use sorted source-file order, then line order.
        self.snapshots = sorted(snapshots, key=lambda s: s.time)
        self.times = [s.time for s in self.snapshots]

    def nearest(
        self, time: datetime | None, *, before: bool, bounded: bool = True
    ) -> Snapshot | None:
        if time is None:
            return None
        index = bisect_right(self.times, time) - 1 if before else bisect_left(self.times, time)
        if not 0 <= index < len(self.snapshots):
            return None
        result = self.snapshots[index]
        if bounded and abs(result.time - time) > timedelta(minutes=30):
            return None
        return result

    def share(self, start: datetime, end: datetime, questions: int) -> dict:
        before = self.nearest(start, before=True, bounded=False)
        after = self.nearest(end, before=False, bounded=False)
        reset = False
        difference = None
        if before is not None and after is not None:
            between = self.snapshots[
                bisect_left(self.times, before.time) : bisect_right(self.times, after.time)
            ]
            reset = any(
                b.reset > a.reset or b.used < a.used
                for a, b in zip(between, between[1:], strict=False)
            )
            if not reset:
                difference = after.used - before.used
        return {
            "before_utc": iso(before.time) if before else None,
            "after_utc": iso(after.time) if after else None,
            "before_pct": before.used if before else None,
            "after_pct": after.used if after else None,
            "difference_pct": difference,
            "difference_per_question_pct": difference / questions
            if difference is not None and questions
            else None,
            "reset_between": reset,
            "upper_bound": True,
        }


def stage5v_names(root: Path) -> set[str]:
    names = set()
    for path in sorted(root.glob("arm-*.json")):
        for row in object_value(read_json(path)).get("rows", []):
            for attempt in object_value(row).get("attempts", []):
                value = object_value(attempt).get("rollout_file")
                if isinstance(value, str):
                    names.add(value.replace("\\", "/").rsplit("/", 1)[-1])
    return names


def load_classes(path: Path) -> list[tuple[str, str]]:
    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError("invalid classes")
    result = []
    for row in data:
        row = object_value(row)
        prefix, name = row.get("prefix"), row.get("class")
        if not isinstance(prefix, str) or not prefix or not isinstance(name, str) or not name:
            raise ValueError("invalid class entry")
        public_guard({"class": name})
        result.append((prefix.replace("\\", "/").casefold(), name))
    return result


def most_frequent(values: Counter[str]) -> str:
    return min(values, key=lambda key: (-values[key], key)) if values else "invalid"


def read_rollouts(
    root: Path, classes: list[tuple[str, str]], recorded: set[str]
) -> tuple[list[dict], Windows]:
    rows, all_snapshots = [], []
    for path in sorted(root.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/rollout-*.jsonl")):
        meta = None
        end = None
        models, efforts = Counter(), Counter()
        turns = responses = 0
        usage = {}
        snapshots = []
        for event in events(path):
            kind = event.get("type")
            payload = object_value(event.get("payload"))
            time = timestamp(event.get("timestamp"))
            if time is not None:
                end = time
            if kind == "session_meta" and meta is None:
                meta = {
                    key: payload.get(key)
                    for key in ("cwd", "originator", "cli_version", "timestamp")
                }
                if timestamp(meta["timestamp"]) is None:
                    meta["timestamp"] = iso(time)
                if end is None:
                    end = timestamp(meta["timestamp"])
            elif kind == "turn_context":
                turns += 1
                models[matched(payload.get("model"), MODEL, "invalid")] += 1
                efforts[effort(payload.get("effort"))] += 1
            elif kind == "token_usage_record":
                responses += 1
            elif kind == "event_msg" and payload.get("type") == "token_count":
                total = object_value(payload.get("info")).get("total_token_usage")
                if isinstance(total, dict):
                    usage = counts(total, TOTAL_KEYS)
                point = snapshot(payload, time)
                if point is not None:
                    snapshots.append(point)
        all_snapshots.extend(snapshots)
        cwd = (meta or {}).get("cwd")
        normalized = cwd.replace("\\", "/").casefold() if isinstance(cwd, str) else ""
        task_class = next((name for prefix, name in classes if normalized.startswith(prefix)), None)
        if task_class is None:
            continue
        start = timestamp(meta["timestamp"])
        if start is None or end is None or end < start:
            raise ValueError("invalid listed task times")
        snapshots.sort(key=lambda s: s.time)
        first, last = (snapshots[0], snapshots[-1]) if snapshots else (None, None)
        rows.append(
            {
                "class": task_class,
                "start_utc": iso(start),
                "end_utc": iso(end),
                "duration_s": (end - start).total_seconds(),
                "originator": matched(meta.get("originator"), LABEL),
                "cli_version": matched(meta.get("cli_version"), LABEL),
                "model": most_frequent(models),
                "effort": most_frequent(efforts),
                "turns": turns,
                "responses": responses,
                **{key: usage.get(key) for key in TOTAL_KEYS},
                "window_pct_first": first.used if first else None,
                "window_pct_last": last.used if last else None,
                "window_resets_first": iso(first.reset) if first else "",
                "window_resets_last": iso(last.reset) if last else "",
                "in_stage5v_record": path.name in recorded,
            }
        )
    rows.sort(key=lambda row: (row["class"], row["start_utc"], row["end_utc"]))
    return rows, Windows(all_snapshots)


@dataclass
class Capture:
    row: dict
    start: datetime
    end: datetime | None
    question: str | None


def profile(argv: Any) -> tuple[str, str]:
    model, reasoning = "invalid", "invalid"
    if not isinstance(argv, list) or not all(isinstance(arg, str) for arg in argv):
        return model, reasoning
    for flag, value in zip(argv, argv[1:], strict=False):
        if flag == "-m":
            model = matched(value, MODEL, "invalid")
        elif flag == "-c" and value.startswith("model_reasoning_effort="):
            try:
                reasoning = effort(json.loads(value.split("=", 1)[1]))
            except ValueError:
                reasoning = "invalid"
    return model, reasoning


def read_captures(root: Path, windows: Windows) -> list[Capture]:
    folders = sorted(
        [*root.glob("attempt-[0-9][0-9]/capture/calls/*"), *root.glob("capture/calls/*")]
    )
    calls = []
    for folder in folders:
        if not folder.is_dir():
            continue
        data = object_value(read_json(folder / "start.json"))
        start = timestamp(data.get("utc"))
        end_path = folder / "end.json"
        ended = object_value(read_json(end_path)) if end_path.exists() else {}
        end = timestamp(ended.get("utc"))
        if start is None or (end_path.exists() and (end is None or end < start)):
            raise ValueError("invalid call times")
        try:
            active = object_value(json.loads(data.get("active_case") or "{}"))
        except (TypeError, ValueError):
            active = {}
        fallback = (
            folder.parents[2].name
            if folder.parents[1].name == "capture"
            and re.fullmatch(r"attempt-\d{2}", folder.parents[2].name)
            else "capture"
        )
        series = active.get("series") or fallback
        if not isinstance(series, str):
            raise ValueError("invalid series")
        model, reasoning = profile(data.get("argv"))
        completed, usage = False, {}
        stdout = folder / "stdout.bin"
        if stdout.exists():
            for event in events(stdout):
                if event.get("type") == "turn.completed":
                    completed = True
                    usage = counts(event.get("usage"), USAGE_KEYS)
        before = windows.nearest(start, before=True)
        after = windows.nearest(end, before=False)
        row = {
            "series": series,
            "base": matched(active.get("key"), SLUG),
            "call": 0,
            "start_utc": iso(start),
            "duration_s": (end - start).total_seconds() if end else None,
            "model": model,
            "effort": reasoning,
            "role": {"low": "helper", "xhigh": "answer"}.get(reasoning, "other"),
            "exit_code": ended.get("exit_code") if type(ended.get("exit_code")) is int else None,
            "completed": completed,
            **{key: usage.get(key) for key in USAGE_KEYS},
            "window_pct_before": before.used if before else None,
            "window_pct_after": after.used if after else None,
        }
        question = active.get("attempt_id")
        calls.append(
            Capture(row, start, end, question if isinstance(question, str) and question else None)
        )
    calls.sort(key=lambda call: (call.row["series"], call.start))
    indices = Counter()
    for call in calls:
        indices[call.row["series"]] += 1
        call.row["call"] = indices[call.row["series"]]
    return calls


def window_hours(windows: Windows) -> list[dict]:
    grouped = defaultdict(list)
    for point in windows.snapshots:
        grouped[point.time.replace(minute=0, second=0, microsecond=0)].append(point)
    return [
        {
            "hour_utc": iso(hour),
            "window_minutes": points[-1].minutes,
            "used_pct_min": min(p.used for p in points),
            "used_pct_max": max(p.used for p in points),
            "resets_at_utc": iso(points[-1].reset),
            "reached": any(p.reached for p in points),
        }
        for hour, points in sorted(grouped.items())
    ]


def duration_stats(rows: list[dict]) -> dict:
    durations = sorted(r["duration_s"] for r in rows if r["duration_s"] is not None)
    return {
        "duration_median_s": median(durations) if durations else None,
        "duration_p90_s": durations[math.ceil(len(durations) * 0.9) - 1] if durations else None,
    }


def token_sums(rows: list[dict], keys: tuple[str, ...]) -> dict:
    return {key: sum(r[key] for r in rows if r[key] is not None) for key in keys}


def summarize(
    calls: list[Capture], rollouts: list[dict], windows: Windows, hours: list[dict]
) -> dict:
    series = defaultdict(list)
    for call in calls:
        series[call.row["series"]].append(call)
    capture_summary = []
    for name, group in sorted(series.items()):
        roles = {}
        calls_by_role = {}
        for role in ROLES:
            rows = [c.row for c in group if c.row["role"] == role]
            calls_by_role[role] = len(rows)
            roles[role] = {
                "usage_sum": token_sums(rows, USAGE_KEYS),
                "usage_median": {
                    key: median(values)
                    if (values := [r[key] for r in rows if r[key] is not None])
                    else None
                    for key in USAGE_KEYS
                },
                **duration_stats(rows),
            }
        questions = len({c.question for c in group if c.question is not None})
        start, end = min(c.start for c in group), max(c.end or c.start for c in group)
        capture_summary.append(
            {
                "series": name,
                "calls_by_role": calls_by_role,
                "completed_calls": sum(c.row["completed"] for c in group),
                "roles": roles,
                "first_call_utc": iso(start),
                "last_call_utc": iso(end),
                "distinct_questions": questions,
                "window_share": windows.share(start, end, questions),
            }
        )
    classes = defaultdict(list)
    for row in rollouts:
        classes[row["class"]].append(row)
    return {
        "capture_series": capture_summary,
        "rollout_classes": [
            {
                "class": name,
                "tasks": len(rows),
                "turns": sum(r["turns"] for r in rows),
                "responses": sum(r["responses"] for r in rows),
                "token_sums": token_sums(rows, TOTAL_KEYS),
                **duration_stats(rows),
            }
            for name, rows in sorted(classes.items())
        ],
        "window": {
            "window_minutes": sorted({p.minutes for p in windows.snapshots}),
            "reached_hours": [h["hour_utc"] for h in hours if h["reached"]],
        },
    }


def csv_bytes(columns: tuple[str, ...], rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: ""
                if value is None
                else str(value).lower()
                if type(value) is bool
                else f"{value:.3f}"
                if type(value) is float
                else value
                for key, value in row.items()
            }
        )
    return stream.getvalue().encode("utf-8")


def fixed_json(value: Any, level: int = 0) -> str:
    """JSON numbers use three decimal places; integer counters stay integers."""
    if isinstance(value, dict):
        parts = [
            json.dumps(key) + ": " + fixed_json(value[key], level + 1) for key in sorted(value)
        ]
        opening, closing = "{", "}"
    elif isinstance(value, list):
        parts = [fixed_json(item, level + 1) for item in value]
        opening, closing = "[", "]"
    else:
        return (
            f"{value:.3f}"
            if type(value) is float
            else json.dumps(value, ensure_ascii=False, allow_nan=False)
        )
    if not parts:
        return opening + closing
    return (
        opening
        + "\n"
        + ",\n".join("  " * (level + 1) + part for part in parts)
        + "\n"
        + "  " * level
        + closing
    )


def extract(args: argparse.Namespace) -> dict[str, int]:
    if not all(path.is_dir() for path in (args.capture_root, args.sessions, args.stage5v_arms)):
        raise ValueError("missing input directory")
    classes = load_classes(args.classes)
    rollouts, windows = read_rollouts(args.sessions, classes, stage5v_names(args.stage5v_arms))
    calls = read_captures(args.capture_root, windows)
    hours = window_hours(windows)
    summary = summarize(calls, rollouts, windows, hours)
    tables = {
        "capture-calls.csv": (CAPTURE_COLUMNS, [c.row for c in calls]),
        "rollouts.csv": (ROLLOUT_COLUMNS, rollouts),
        "window-hours.csv": (HOUR_COLUMNS, hours),
    }
    # Validate every table AND the summary before serializing or touching --out.
    for _, rows in tables.values():
        public_guard(rows)
    public_guard(summary)
    outputs = {name: csv_bytes(columns, rows) for name, (columns, rows) in tables.items()}
    outputs["summary.json"] = (fixed_json(summary) + "\n").encode("utf-8")
    args.out.mkdir(parents=True, exist_ok=True)
    for name, raw in sorted(outputs.items()):
        (args.out / name).write_bytes(raw)
    return {**{name: len(rows) for name, (_, rows) in tables.items()}, "summary.json": 1}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("capture-root", "sessions", "classes", "stage5v-arms", "out"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args()
    try:
        sizes = extract(args)
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        # Never print exceptions containing private paths, JSON fragments or text.
        print("usage extraction refused", file=sys.stderr)
        return 1
    for name, size in sorted(sizes.items()):
        print(name, size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
