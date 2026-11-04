"""Offline private journal API. Repository parsing imports issue no requests.

read_journal(root) retains every call directory, including damaged records. Bind the
returned records with bind_calls(records, {"key": ..., "case_id": ...}) BEFORE using
classify_call(record, configured_timeout). Nonempty stop reasons mean rule/code 2.
An empty journal alone never proves that a request needed no model call.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm.providers.base import ProviderUnavailable  # noqa: E402
from llm.providers.codex import DISABLED_FEATURES, _parse_answer  # noqa: E402
from scripts.chat_answer_judge import prompt_id, read_prompt  # noqa: E402

SCHEMA = "codex-capture-shim/1"
# Stage 5 transport vocabulary, narrowed to limits (network/timeouts are not limits).
# Consult ONLY messages on structured error / turn.failed events, never answer prose.
USAGE_LIMIT_PATTERNS = (r"usage.?limit", r"rate.?limit", r"\bquota\b")
EFFORTS = frozenset({"none", "minimal", "low", "medium", "high", "xhigh"})


class Refusal(ValueError):
    """A record or a frozen parsing contract cannot be interpreted unambiguously."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise Refusal(reason)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _json(raw: str) -> Any:
    def invalid(value: str) -> None:
        raise Refusal("nonfinite JSON number")

    return json.loads(raw, object_pairs_hook=_unique, parse_constant=invalid)


def utc(value: Any) -> datetime:
    _require(isinstance(value, str), "missing UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise Refusal("invalid UTC timestamp") from None
    _require(parsed.utcoffset() == timedelta(0), "timestamp must be UTC")
    return parsed


def read_answer_prompt(prompt: str) -> tuple[str, list[tuple[str, str]]]:
    _require(prompt_id(prompt) == "QA_PROMPT_V4", "answer prompt is not V4")
    return read_prompt(prompt)


@lru_cache(maxsize=1)
def _argv_prefix() -> tuple[str, ...]:
    return (
        "exec",
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "read-only",
        *(part for feature in DISABLED_FEATURES for part in ("--disable", feature)),
    )


def parse_argv(argv: Any) -> tuple[str, str]:
    """Only the current provider's exec grammar; no aliases, duplicates or overrides."""
    _require(
        isinstance(argv, list) and all(isinstance(v, str) for v in argv), "argv must be strings"
    )
    prefix = _argv_prefix()
    _require(tuple(argv[: len(prefix)]) == prefix, "unknown exec argv shape")
    tail = argv[len(prefix) :]
    _require(
        len(tail) == 7
        and tail[0] == "-m"
        and tail[2] == "-c"
        and tail[4] == "-C"
        and tail[6] == "-",
        "unknown model/effort argv shape",
    )
    model = tail[1]
    _require(
        bool(model.strip()) and model == model.strip() and not model.startswith("-"),
        "invalid model",
    )
    _require(bool(tail[5]), "missing exec cwd")
    key, separator, value = tail[3].partition("=")
    _require(key == "model_reasoning_effort" and separator == "=", "unknown effort configuration")
    effort = _json(value)
    _require(isinstance(effort, str) and effort in EFFORTS, "unknown effort")
    return model, effort


def unwrap(stdin: bytes, wrapper: bytes | None = None) -> str:
    if wrapper is None:
        wrapper = (ROOT / "llm/codex_wrapper.txt").read_bytes()
    _require(wrapper.count(b"{prompt}") == 1, "wrapper must contain one placeholder")
    prefix, suffix = wrapper.split(b"{prompt}")
    _require(bool(prefix) and bool(suffix), "wrapper must have fixed prefix and suffix")
    _require(
        len(stdin) >= len(prefix) + len(suffix)
        and stdin.startswith(prefix)
        and stdin.endswith(suffix),
        "wrapper prefix/suffix mismatch",
    )
    framed = stdin[len(prefix) : -len(suffix)].decode("utf-8")
    _require(framed.startswith("USER:\n"), "expected single USER framing")
    prompt = framed[len("USER:\n") :]
    _require(bool(prompt) and prompt == prompt.strip(), "content is not flatten_messages output")
    # A second role frame is indistinguishable from literal role-frame text inside
    # one message. Refuse that ambiguity instead of dropping or guessing messages.
    _require(
        re.search(
            r"(?m)^(?:USER|SYSTEM|DEVELOPER|ASSISTANT|TOOL|FUNCTION)(?: \([^\n]*\))?:\n", prompt
        )
        is None,
        "ambiguous additional message framing",
    )
    return prompt


@dataclass
class Output:
    text: str = ""
    completed: bool = False
    accepted: bool = False
    reason: str | None = None
    usage_limit: bool = False


def parse_stdout(stdout: bytes, exit_code: int = 0, model: str = "captured") -> Output:
    output = Output()
    try:
        response = _parse_answer(stdout, exit_code, model)
        output.text = response.text
        output.completed = True
        output.accepted = True
    except ProviderUnavailable as error:
        output.reason = error.reason
    # Failure diagnostics survive a truncated JSON/UTF-8 tail. This never changes
    # the provider gate above: inspect each complete event, then consult patterns
    # ONLY after its structured status is error/turn.failed.
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeError):
            break
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            break
        kind = event["type"]
        if kind not in {"error", "turn.failed"}:
            continue
        detail = event.get("error") if kind == "turn.failed" else event
        message = str(detail.get("message", "") if isinstance(detail, dict) else "")
        if any(re.search(pattern, message, re.IGNORECASE) for pattern in USAGE_LIMIT_PATTERNS):
            output.usage_limit = True
    return output


@dataclass
class CallRecord:
    folder: Path
    start: dict[str, Any] | None = None
    spawned: dict[str, Any] | None = None
    end: dict[str, Any] | None = None
    driver_end: dict[str, Any] | None = None
    missing_end: bool = True
    started: datetime | None = None
    process_started: datetime | None = None
    last_heartbeat: datetime | None = None
    finished: datetime | None = None
    model: str | None = None
    effort: str | None = None
    prompt: str | None = None
    kind: str = "auxiliary"
    output: Output = field(default_factory=Output)
    errors: list[str] = field(default_factory=list)
    driver_errors: list[str] = field(default_factory=list)
    stop_reasons: list[str] = field(default_factory=list)

    @property
    def open(self) -> bool:
        return self.start is not None and self.missing_end


def _record(
    call: CallRecord, name: str, *, required: bool = False, errors: list[str] | None = None
) -> dict[str, Any] | None:
    errors = call.errors if errors is None else errors
    path = call.folder / name
    try:
        value = _json(path.read_bytes().decode("utf-8"))
        _require(isinstance(value, dict), "record must be an object")
        return value
    except FileNotFoundError:
        if required:
            errors.append("missing " + name)
    except (OSError, UnicodeError, ValueError):
        errors.append("invalid " + name)
    return None


def _bytes(call: CallRecord, name: str, *, required: bool) -> bytes | None:
    try:
        return (call.folder / name).read_bytes()
    except FileNotFoundError:
        if required:
            call.errors.append("missing " + name)
    except OSError:
        call.errors.append("unreadable " + name)
    return None


def _digest(call: CallRecord, name: str, raw: bytes | None, record: Mapping[str, Any]) -> None:
    length = record.get(name + "_length")
    digest = record.get(name + "_sha256")
    if (
        type(length) is not int
        or length < 0
        or not isinstance(digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        or raw is None
        or len(raw) != length
        or hashlib.sha256(raw).hexdigest() != digest
    ):
        call.errors.append(name + " length/SHA-256 mismatch")


def read_heartbeats(path: Path) -> list[datetime]:
    """Read LF-terminated UTC stamps; a killed writer may leave an incomplete tail."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return []
    stamps: list[datetime] = []
    for line in raw.split(b"\n")[:-1]:
        stamp = utc(line.decode("utf-8"))
        _require(not stamps or stamp >= stamps[-1], "heartbeat times out of order")
        stamps.append(stamp)
    return stamps


def read_call(folder: Path) -> CallRecord:
    call = CallRecord(Path(folder))
    call.start = _record(call, "start.json", required=True)
    call.spawned = _record(call, "spawned.json")
    call.end = _record(call, "end.json")
    call.missing_end = not (call.folder / "end.json").exists()
    call.driver_end = _record(call, "end.driver.json", errors=call.driver_errors)
    try:
        heartbeats = read_heartbeats(call.folder / "alive.log")
        call.last_heartbeat = heartbeats[-1] if heartbeats else None
    except (OSError, ValueError) as error:
        call.errors.append("invalid alive.log: " + str(error))
    stdin = _bytes(call, "stdin.bin", required=True)
    streams_required = call.spawned is not None or not call.missing_end
    stdout = _bytes(call, "stdout.bin", required=streams_required)
    stderr = _bytes(call, "stderr.bin", required=streams_required)
    if call.start is not None:
        start = call.start
        try:
            _require(start.get("schema") == SCHEMA, "unknown start schema")
            call.started = utc(start.get("utc"))
            _require(
                type(start.get("shim_pid")) is int and start["shim_pid"] > 0, "invalid shim pid"
            )
            call.process_started = utc(start.get("process_start_utc"))
            _require(call.process_started <= call.started, "invalid process start")
            for key in ("command_line_tail", "cwd", "real_exe"):
                _require(isinstance(start.get(key), str), "invalid " + key)
            _require(
                type(start.get("real_exe_size")) is int and start["real_exe_size"] > 0,
                "invalid exe size",
            )
            utc(start.get("real_exe_mtime_utc"))
            names = start.get("environment_names")
            _require(
                isinstance(names, list) and all(isinstance(v, str) and "=" not in v for v in names),
                "invalid environment names",
            )
        except (ValueError, TypeError) as error:
            call.errors.append(str(error))
        _digest(call, "stdin", stdin, start)
        try:
            call.model, call.effort = parse_argv(start.get("argv"))
            _require(start["argv"][-2] == start.get("cwd"), "argv cwd mismatch")
        except (ValueError, TypeError) as error:
            call.stop_reasons.append("argv: " + str(error))
    if stdin is not None:
        try:
            call.prompt = unwrap(stdin)
        except (ValueError, UnicodeError) as error:
            call.stop_reasons.append("unwrap: " + str(error))
    if call.effort == "xhigh" and call.prompt is not None:
        try:
            read_answer_prompt(call.prompt)
            call.kind = "answer"
        except (ValueError, IndexError):
            pass  # Non-V4, malformed V4 and the data-free probe are auxiliaries.
    try:
        if call.spawned is not None:
            child = call.spawned.get("child_pid")
            _require(type(child) is int and child > 0, "invalid child pid")
            spawned_at = utc(call.spawned.get("utc"))
            _require(call.started is not None and spawned_at >= call.started, "invalid spawn time")
        if call.end is not None:
            call.finished = utc(call.end.get("utc"))
            _require(type(call.end.get("exit_code")) is int, "invalid exit code")
            _require(type(call.end.get("capture_ok")) is bool, "invalid capture_ok")
            _digest(call, "stdout", stdout, call.end)
            _digest(call, "stderr", stderr, call.end)
        if call.finished is not None:
            _require(call.started is not None and call.finished >= call.started, "end before start")
            if call.spawned is not None:
                _require(call.finished >= utc(call.spawned.get("utc")), "end before spawn")
    except (ValueError, TypeError) as error:
        call.errors.append(str(error))
        call.finished = None
    try:
        if call.driver_end is not None:
            driver = call.driver_end
            _require(call.missing_end, "driver end beside shim end")
            _require(
                set(driver) == {"schema", "writer", "missing_end", "verified_exit_utc", "reason"}
                and driver["schema"] == "codex-capture-driver-end/1"
                and driver["writer"] == "driver"
                and driver["missing_end"] is True
                and isinstance(driver["reason"], str)
                and bool(driver["reason"].strip()),
                "invalid driver end",
            )
            finished = utc(driver["verified_exit_utc"])
            _require(call.started is not None and finished >= call.started, "end before start")
            if call.spawned is not None:
                _require(finished >= utc(call.spawned.get("utc")), "end before spawn")
            call.finished = finished
    except (ValueError, TypeError) as error:
        call.driver_errors.append(str(error))
    exit_code = call.end.get("exit_code", 0) if call.end else 0
    call.output = parse_stdout(stdout or b"", exit_code, call.model or "captured")
    return call


def read_journal(root: Path) -> list[CallRecord]:
    """Missing/unreadable calls directory refuses; no directory is silently discarded."""
    calls = Path(root) / "calls"
    _require(calls.is_dir(), "missing calls directory")
    records = []
    for folder in sorted(calls.iterdir()):
        _require(folder.is_dir() and not folder.is_symlink(), "unexpected calls entry")
        records.append(read_call(folder))
    return records


def _case(value: Any) -> tuple[str, str]:
    _require(isinstance(value, dict), "active case must be an object")
    _require(
        all(
            isinstance(value.get(key), str) and bool(value[key].strip())
            for key in ("key", "case_id")
        ),
        "active case needs key and case_id",
    )
    return value["key"], value["case_id"]


def bind_calls(calls: Sequence[CallRecord], expected_case: Mapping[str, Any]) -> list[str]:
    """Return all explicit rule stops; retain every record and never repair attribution."""
    expected = _case(dict(expected_case))
    stops: list[str] = []
    for call in calls:
        stops.extend(call.folder.name + ": " + reason for reason in call.stop_reasons)
        stops.extend(call.folder.name + ": " + reason for reason in call.driver_errors)
        try:
            active = call.start.get("active_case") if call.start else None
            if not isinstance(active, str):
                raise Refusal("missing active case")
            _require(_case(_json(active)) == expected, "unexpected active case")
        except (ValueError, TypeError) as error:
            stops.append(call.folder.name + ": unbound: " + str(error))
        if call.started is None:
            stops.append(call.folder.name + ": unknown start interval")
    for index, left in enumerate(calls):
        for right in calls[index + 1 :]:
            if left.started is None or right.started is None:
                continue
            if (left.finished is None or right.started <= left.finished) and (
                right.finished is None or left.started <= right.finished
            ):
                stops.append("overlap: " + left.folder.name + " / " + right.folder.name)
    return stops


def classify_call(call: CallRecord | None, timeout_seconds: float) -> str:
    """Bind first. usage_limit is infrastructure, product_timeout is terminal bad."""
    _require(math.isfinite(timeout_seconds) and timeout_seconds > 0, "timeout must be positive")
    if call is None:
        return "infrastructure"
    if call.output.usage_limit:
        return "usage_limit"
    if call.errors or call.stop_reasons or call.start is None:
        return "infrastructure"
    if call.open:
        last_alive = call.last_heartbeat or call.started
        if (
            call.spawned is not None
            and call.process_started is not None
            and last_alive is not None
            and (last_alive - call.process_started).total_seconds() >= timeout_seconds - 5
        ):
            return "product_timeout"
        return "infrastructure"
    if (
        call.spawned is None
        or call.end is None
        or call.end["exit_code"] != 0
        or call.end["capture_ok"] is not True
        or not call.output.accepted
    ):
        return "infrastructure"
    return "ok"


def write_driver_end(folder: Path, verified_exit_utc: str, reason: str) -> Path:
    """Caller MUST have verified process exit. This function never probes or kills PIDs.

    Exclusive, fsynced append; it preserves missing end.json and invents neither
    output nor status. The driver must serialize writes with its journal drain.
    """
    folder = Path(folder)
    _require(not (folder / "end.json").exists(), "shim end already exists")
    start = _json((folder / "start.json").read_bytes().decode("utf-8"))
    _require(isinstance(start, dict) and start.get("schema") == SCHEMA, "missing shim start")
    _require(utc(verified_exit_utc) >= utc(start.get("utc")), "verified exit before start")
    _require(isinstance(reason, str) and bool(reason.strip()), "driver reason is required")
    value = {
        "schema": "codex-capture-driver-end/1",
        "writer": "driver",
        "missing_end": True,
        "verified_exit_utc": verified_exit_utc,
        "reason": reason,
    }
    path = folder / "end.driver.json"
    raw = (json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    if os.name == "posix":
        descriptor = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    return path
