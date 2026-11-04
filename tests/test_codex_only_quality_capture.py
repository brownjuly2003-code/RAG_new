"""Synthetic/offline contracts; native checks live in shim_check.py."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports/codex-only-quality/tools"


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


journal = load("capture_journal")
builder = load("build_shim")
CASE = {"key": "wixqa", "case_id": "test-01"}
START = "2026-11-04T12:00:00.0000000Z"
V4 = (
    "CONTEXT:\n[1 | source=source-a]\nDocument text.\n--------------------\n\nQUESTION:\nFee?"
    "\n\nWhen you rely on a fact, cite [1] for the first document in the context list, exactly."
)


def wrapped(prompt=V4):
    return (
        (ROOT / "llm/codex_wrapper.txt")
        .read_bytes()
        .replace(b"{prompt}", ("USER:\n" + prompt).encode("utf-8"), 1)
    )


def argv(effort="xhigh"):
    from llm.providers.codex import DISABLED_FEATURES

    return [
        "exec",
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "read-only",
        *(part for feature in DISABLED_FEATURES for part in ("--disable", feature)),
        "-m",
        "gpt-6-astra",
        "-c",
        "model_reasoning_effort=" + json.dumps(effort),
        "-C",
        "C:/private/cwd",
        "-",
    ]


def jsonl(*events):
    return ("\n".join(json.dumps(event) for event in events) + "\n").encode()


def answer(text="The answer [1]."):
    return {"type": "item.completed", "item": {"type": "agent_message", "text": text}}


COMPLETE = {"type": "turn.completed", "usage": {"input_tokens": 17, "output_tokens": 5}}


def write_json(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8"))


def digest_fields(name, raw):
    return {name + "_length": len(raw), name + "_sha256": hashlib.sha256(raw).hexdigest()}


@pytest.fixture
def call_folder(tmp_path):
    def make(
        name="call-1",
        *,
        effort="xhigh",
        prompt=V4,
        stdin=None,
        output=None,
        spawned=True,
        end=True,
        exit_code=0,
        capture_ok=True,
        active=CASE,
        started=START,
        process_started=None,
        finished="2026-11-04T12:00:01Z",
        heartbeats=None,
    ):
        folder = tmp_path / "calls" / name
        folder.mkdir(parents=True)
        stdin = wrapped(prompt) if stdin is None else stdin
        output = jsonl(answer(), COMPLETE) if output is None else output
        (folder / "stdin.bin").write_bytes(stdin)
        (folder / "stdout.bin").write_bytes(output)
        (folder / "stderr.bin").write_bytes(b"diagnostic\n")
        write_json(
            folder / "start.json",
            {
                "schema": journal.SCHEMA,
                "utc": started,
                "shim_pid": 100,
                "process_start_utc": process_started or started,
                "command_line_tail": " exec ... -",
                "argv": argv(effort),
                "cwd": "C:/private/cwd",
                **digest_fields("stdin", stdin),
                "active_case": json.dumps(active) if active is not None else None,
                "real_exe": "C:/native/codex.exe",
                "real_exe_size": 1000,
                "real_exe_mtime_utc": START,
                "environment_names": ["PATH", "SystemRoot"],
            },
        )
        if spawned:
            write_json(folder / "spawned.json", {"child_pid": 101, "utc": started})
        if heartbeats is not None:
            (folder / "alive.log").write_bytes(heartbeats)
        if end:
            write_json(
                folder / "end.json",
                {
                    "utc": finished,
                    "exit_code": exit_code,
                    "capture_ok": capture_ok,
                    **digest_fields("stdout", output),
                    **digest_fields("stderr", b"diagnostic\n"),
                },
            )
        return folder

    return make


def test_valid_capture_and_all_directories_retained(call_folder, tmp_path):
    call_folder()
    (tmp_path / "calls/broken").mkdir()
    calls = journal.read_journal(tmp_path)
    assert len(calls) == 2
    good = next(call for call in calls if call.folder.name == "call-1")
    assert good.errors == [] and not good.open
    assert good.model == "gpt-6-astra" and good.effort == "xhigh" and good.kind == "answer"
    assert good.prompt == V4
    assert good.output.text == "The answer [1]." and good.output.completed
    assert journal.bind_calls([good], CASE) == []
    assert journal.classify_call(good, 180) == "ok"
    bad = next(call for call in calls if call.folder.name == "broken")
    assert journal.classify_call(bad, 180) == "infrastructure"
    assert any("unbound" in reason for reason in journal.bind_calls(calls, CASE))


def test_missing_journal_and_missing_call_are_not_success(tmp_path):
    with pytest.raises(ValueError, match="missing calls"):
        journal.read_journal(tmp_path)
    assert journal.classify_call(None, 180) == "infrastructure"


@pytest.mark.parametrize(
    "effort,prompt,kind",
    [
        ("xhigh", V4, "answer"),
        ("low", V4, "auxiliary"),
        ("medium", V4, "auxiliary"),
        ("xhigh", "Reply with exactly OK.", "auxiliary"),
        ("xhigh", V4.replace("[1 |", "[2 |"), "auxiliary"),
        (
            "xhigh",
            V4.replace(
                "[1] for the first document in the context list,", "add [N] right after it,"
            ),
            "auxiliary",
        ),
    ],
)
def test_answer_identification_is_xhigh_and_parsed_v4(call_folder, effort, prompt, kind):
    call = journal.read_call(call_folder(effort=effort, prompt=prompt))
    assert call.kind == kind and call.effort == effort


def test_unwrap_is_byte_exact_preserves_inner_markers_and_unicode():
    prompt = "Question: caf\u00e9?\n{prompt}\nPROMPT>>>\nLiteral text."
    assert journal.unwrap(wrapped(prompt)) == prompt
    assert journal.read_answer_prompt(V4) == ("Fee?", [("source-a", "Document text.")])
    assert journal.read_answer_prompt(
        V4.replace("[1 | source=source-a]\nDocument text.", "[]")
    ) == ("Fee?", [])


def test_real_product_v4_and_flatten_messages_round_trip():
    from llm.providers.base import flatten_messages

    tree = ast.parse((ROOT / "agent/prompts.py").read_text(encoding="utf-8"))
    registry = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "PROMPT_REGISTRY"
    )
    prompt = registry["qa"]["text"].format(context_block="[]", question="Question?")
    framed = flatten_messages([{"role": "user", "content": prompt}])
    stdin = (ROOT / "llm/codex_wrapper.txt").read_bytes().replace(b"{prompt}", framed.encode(), 1)
    assert journal.unwrap(stdin) == prompt.strip()
    assert journal.read_answer_prompt(journal.unwrap(stdin)) == ("Question?", [])


@pytest.mark.parametrize(
    "transform",
    [
        lambda value: b"x" + value,
        lambda value: value + b"x",
        lambda value: value[:-1],
        lambda value: value.replace(b"<<<PROMPT\n", b"<<<PROMPT\r\n"),
        lambda value: value.replace(b"USER:\n", b"SYSTEM:\n"),
        lambda value: value.replace(b"USER:\n", b"USER (name):\n"),
        lambda value: value.replace(b"USER:\n", b"USER:\r\n"),
        lambda value: value.replace(b"USER:\n", b"USER:\n "),
        lambda value: value.replace(b"Fee?", b"\xff"),
        lambda value: value.replace(b"Fee?", b"Fee?\n\nASSISTANT:\nanother message"),
        lambda value: value.replace(b"Fee?", b"Fee?\nUSER (name):\nanother message"),
    ],
)
def test_unwrap_refuses_mismatches_and_ambiguous_frames(transform):
    with pytest.raises((ValueError, UnicodeError)):
        journal.unwrap(transform(wrapped()))


@pytest.mark.parametrize("wrapper", [b"fixed", b"{prompt}", b"x{prompt}y{prompt}z", b"x{prompt}"])
def test_unwrap_refuses_changed_wrapper_contract(wrapper):
    with pytest.raises(ValueError):
        journal.unwrap(wrapped(), wrapper)


@pytest.mark.parametrize("prompt", ["", " leading", "trailing\n"])
def test_unwrap_refuses_content_flatten_messages_would_remove(prompt):
    with pytest.raises(ValueError, match="flatten_messages"):
        journal.unwrap(wrapped(prompt))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda a: [*a, "extra"],
        lambda a: a[1:],
        lambda a: ["--help"],
        lambda a: [*a[:-7], "--model", *a[-6:]],
        lambda a: [*a[:-4], 'model_reasoning_effort="unknown"', *a[-3:]],
        lambda a: [*a[:-4], "model_reasoning_effort=low", *a[-3:]],
        lambda a: [*a[:-4], "model_reasoning_effort=4", *a[-3:]],
        lambda a: [*a[:-4], 'other="low"', *a[-3:]],
        lambda a: [*a[:-6], "", *a[-5:]],
        lambda a: None,
    ],
)
def test_argv_refuses_unknown_shapes(mutate):
    with pytest.raises(ValueError):
        journal.parse_argv(mutate(argv()))


def test_argv_and_wrapper_refusals_surface_as_stops(call_folder):
    folder = call_folder(stdin=b"unwrapped")
    start = json.loads((folder / "start.json").read_bytes())
    start["argv"].append("--override")
    write_json(folder / "start.json", start)
    reasons = journal.bind_calls([journal.read_call(folder)], CASE)
    assert any("argv:" in reason for reason in reasons)
    assert any("unwrap:" in reason for reason in reasons)


@pytest.mark.parametrize("field,value", [("exit_code", 4), ("capture_ok", False)])
def test_nonzero_exit_and_capture_failure_are_infrastructure(call_folder, field, value):
    call = journal.read_call(call_folder(**{field: value}))
    assert journal.classify_call(call, 180) == "infrastructure"


@pytest.mark.parametrize(
    "name", ["start.json", "spawned.json", "stdin.bin", "stdout.bin", "stderr.bin"]
)
def test_missing_records_cannot_be_ok(call_folder, name):
    folder = call_folder()
    (folder / name).unlink()
    call = journal.read_call(folder)
    assert journal.classify_call(call, 180) == "infrastructure"
    if name == "spawned.json":
        assert call.spawned is None


@pytest.mark.parametrize("name", ["start.json", "spawned.json", "end.json"])
def test_malformed_records_cannot_be_ok(call_folder, name):
    folder = call_folder()
    (folder / name).write_bytes(b"{truncated")
    call = journal.read_call(folder)
    assert journal.classify_call(call, 180) == "infrastructure"
    assert call.errors
    if name == "end.json":
        assert not call.missing_end  # Corruption is not a timeout.


@pytest.mark.parametrize("name", ["stdin.bin", "stdout.bin", "stderr.bin"])
def test_hash_mismatch_is_infrastructure(call_folder, name):
    folder = call_folder()
    path = folder / name
    path.write_bytes(path.read_bytes() + b"x")
    call = journal.read_call(folder)
    assert any("SHA-256 mismatch" in reason for reason in call.errors)
    assert journal.classify_call(call, 180) == "infrastructure"


@pytest.mark.parametrize(
    "spawned,seconds,expected",
    [
        (True, 175, "product_timeout"),
        (True, 176, "product_timeout"),
        (True, 174.999999, "infrastructure"),
        (True, 5, "infrastructure"),
        (False, 175, "infrastructure"),
    ],
)
def test_open_calls_use_heartbeats_not_driver_observation(call_folder, spawned, seconds, expected):
    heartbeat = (journal.utc(START) + timedelta(seconds=seconds)).isoformat()
    folder = call_folder(
        end=False, spawned=spawned, heartbeats=(START + "\n" + heartbeat + "\n").encode()
    )
    before = journal.read_call(folder)
    assert before.open and journal.classify_call(before, 180) == expected
    journal.write_driver_end(folder, "2026-11-04T12:04:00Z", "late drain observation")
    call = journal.read_call(folder)
    assert call.open and call.missing_end and call.end is None
    assert journal.classify_call(call, 180) == expected


@pytest.mark.parametrize("heartbeats", [None, b"", b"2026-11-04T12:05:00.993"])
@pytest.mark.parametrize("seconds,expected", [(0, "infrastructure"), (55, "product_timeout")])
def test_no_complete_heartbeat_uses_start_minus_process_start(
    call_folder, heartbeats, seconds, expected
):
    process_start = (journal.utc(START) - timedelta(seconds=seconds)).isoformat()
    folder = call_folder(end=False, process_started=process_start, heartbeats=heartbeats)
    journal.write_driver_end(folder, "2026-11-04T12:01:10Z", "late drain observation")
    assert journal.classify_call(journal.read_call(folder), 60) == expected


def test_timeout_elapsed_starts_at_shim_process_start(call_folder):
    folder = call_folder(
        end=False,
        process_started="2026-11-04T11:59:58.9930914Z",
        started="2026-11-04T12:00:00.9930914Z",
        heartbeats=b"2026-11-04T12:00:53.9930914Z\n",
    )
    assert journal.classify_call(journal.read_call(folder), 60) == "product_timeout"


@pytest.mark.parametrize("seconds,expected", [(5, "infrastructure"), (55, "product_timeout")])
@pytest.mark.parametrize("tail", [b"2026-11-04T12:01:00Z", b"broken\xff"])
def test_incomplete_last_heartbeat_is_ignored(call_folder, seconds, expected, tail):
    heartbeat = (journal.utc(START) + timedelta(seconds=seconds)).isoformat()
    folder = call_folder(end=False, heartbeats=(heartbeat + "\n").encode() + tail)
    call = journal.read_call(folder)
    assert call.errors == []
    assert journal.classify_call(call, 60) == expected


@pytest.mark.parametrize(
    "heartbeats",
    [
        b"2026-11-04T12:00:55Z\nbad\n",
        b"2026-11-04T12:00:55Z\n\xff\n",
        b"2026-11-04T12:00:55Z\n\n",
        b"2026-11-04T12:00:55Z\n2026-11-04T12:00:54Z\n",
        b"2026-11-04T12:00:55\n",
        b"2026-11-04T12:00:55+01:00\n",
    ],
)
def test_malformed_or_out_of_order_complete_heartbeat_refuses(call_folder, heartbeats):
    call = journal.read_call(call_folder(end=False, heartbeats=heartbeats))
    assert any("alive.log" in reason for reason in call.errors)
    assert journal.classify_call(call, 60) == "infrastructure"


def test_seven_fractional_digits_from_all_shim_records(call_folder):
    start = "2026-11-04T09:17:02.9930914Z"
    spawned = "2026-11-04T09:17:03.9930914Z"
    heartbeat = "2026-11-04T09:17:04.9930914Z"
    end = "2026-11-04T09:17:05.9930914Z"
    folder = call_folder(started=start, finished=end, heartbeats=(heartbeat + "\n").encode())
    write_json(folder / "spawned.json", {"child_pid": 101, "utc": spawned})
    call = journal.read_call(folder)
    assert call.errors == [] and journal.classify_call(call, 60) == "ok"
    assert call.started == datetime(2026, 11, 4, 9, 17, 2, 993091, timezone.utc)
    assert journal.utc(call.start["process_start_utc"]) == call.started
    assert journal.utc(call.spawned["utc"]) == call.started + timedelta(seconds=1)
    assert call.last_heartbeat == call.started + timedelta(seconds=2)
    assert call.finished == call.started + timedelta(seconds=3)


def test_driver_end_preserves_bytes_missing_end_and_no_fabricated_status(call_folder):
    folder = call_folder(end=False)
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    path = journal.write_driver_end(folder, "2026-11-04T12:03:00Z", "verified exit")
    record = json.loads(path.read_bytes())
    assert record["writer"] == "driver" and record["missing_end"] is True
    assert set(record) == {"schema", "writer", "missing_end", "verified_exit_utc", "reason"}
    assert not (folder / "end.json").exists()
    assert all((folder / name).read_bytes() == raw for name, raw in before.items())
    assert b"\r" not in path.read_bytes()
    with pytest.raises(FileExistsError):
        journal.write_driver_end(folder, "2026-11-04T12:04:00Z", "cannot replace evidence")
    assert path.read_bytes() == (json.dumps(record, ensure_ascii=False) + "\n").encode()


def test_driver_end_refuses_closed_call(call_folder):
    folder = call_folder()
    with pytest.raises(ValueError, match="already exists"):
        journal.write_driver_end(folder, "2026-11-04T12:03:00Z", "verified exit")
    assert not (folder / "end.driver.json").exists()


@pytest.mark.parametrize(
    "timestamp,reason",
    [
        ("2026-11-04T11:59:59Z", "exit"),
        ("2026-11-04T12:03:00", "exit"),
        ("2026-11-04T12:03:00+01:00", "exit"),
        ("bad", "exit"),
        ("2026-11-04T12:03:00Z", ""),
    ],
)
def test_driver_end_refuses_invalid_proof(call_folder, timestamp, reason):
    folder = call_folder(end=False)
    with pytest.raises(ValueError):
        journal.write_driver_end(folder, timestamp, reason)
    assert not (folder / "end.driver.json").exists()


@pytest.mark.parametrize(
    "active", [None, "not an object", {}, {"key": "wixqa"}, {"key": "wixqa", "case_id": "other"}]
)
def test_unbound_and_unexpected_cases_are_rule_stops(call_folder, active):
    calls = [journal.read_call(call_folder(active=active))]
    assert any("unbound" in reason for reason in journal.bind_calls(calls, CASE))


@pytest.mark.parametrize("raw", ["{broken", '{"key":"wixqa","case_id":"a","case_id":"test-01"}'])
def test_malformed_and_duplicate_case_keys_are_stops(call_folder, raw):
    folder = call_folder()
    start = json.loads((folder / "start.json").read_bytes())
    start["active_case"] = raw
    write_json(folder / "start.json", start)
    assert any(
        "unbound" in reason for reason in journal.bind_calls([journal.read_call(folder)], CASE)
    )


@pytest.mark.parametrize(
    "open_left,start_right,overlap",
    [
        (False, "2026-11-04T12:00:00.5Z", True),
        (False, "2026-11-04T12:00:01Z", True),
        (False, "2026-11-04T12:00:02Z", False),
        (True, "2026-11-04T12:00:02Z", True),
    ],
)
def test_closed_and_open_intervals_overlap(call_folder, open_left, start_right, overlap):
    left = journal.read_call(call_folder("left", end=not open_left))
    right = journal.read_call(
        call_folder("right", started=start_right, finished="2026-11-04T12:00:03Z")
    )
    reasons = journal.bind_calls([right, left], CASE)
    assert any("overlap:" in reason for reason in reasons) is overlap


def test_driver_end_bounds_interval_without_closing_call(call_folder):
    left = call_folder("left", end=False)
    journal.write_driver_end(left, "2026-11-04T12:03:00Z", "verified exit")
    right = call_folder("right", started="2026-11-04T12:03:01Z", finished="2026-11-04T12:03:02Z")
    calls = [journal.read_call(left), journal.read_call(right)]
    assert journal.bind_calls(calls, CASE) == [] and calls[0].open


@pytest.mark.parametrize("end,expected", [(False, "product_timeout"), (True, "ok")])
def test_malformed_driver_end_is_bookkeeping_error_only(call_folder, end, expected):
    folder = call_folder(
        end=end, finished="2026-11-04T12:01:00Z", heartbeats=b"2026-11-04T12:00:55Z\n"
    )
    (folder / "end.driver.json").write_bytes(b"{truncated")
    call = journal.read_call(folder)
    assert call.driver_errors == ["invalid end.driver.json"] and call.errors == []
    assert journal.classify_call(call, 60) == expected
    assert any("end.driver.json" in reason for reason in journal.bind_calls([call], CASE))


@pytest.mark.parametrize("name", ["stdout.bin", "stderr.bin"])
def test_missing_stream_is_infrastructure_even_after_timeout(call_folder, name):
    folder = call_folder(end=False, heartbeats=b"2026-11-04T12:03:00Z\n")
    (folder / name).unlink()
    journal.write_driver_end(folder, "2026-11-04T12:03:00Z", "verified exit")
    assert journal.classify_call(journal.read_call(folder), 180) == "infrastructure"


@pytest.mark.parametrize("kind", ["error", "turn.failed"])
@pytest.mark.parametrize(
    "message",
    [
        "You've hit your usage limit",
        "usage_limit exceeded",
        "RATE LIMIT reached",
        "Insufficient quota",
    ],
)
def test_structured_usage_limit_beats_timeout_and_exit(call_folder, kind, message):
    detail = {"message": message}
    event = {"type": kind, **({"error": detail} if kind == "turn.failed" else detail)}
    folder = call_folder(end=False, output=jsonl(event), heartbeats=b"2026-11-04T12:03:00Z\n")
    journal.write_driver_end(folder, "2026-11-04T12:03:00Z", "verified exit")
    assert journal.classify_call(journal.read_call(folder), 180) == "usage_limit"
    output = journal.parse_stdout(jsonl(event), 7)
    assert output.usage_limit and not output.accepted


def test_usage_limit_in_answer_or_unstructured_text_is_not_marker(call_folder):
    call = journal.read_call(call_folder(output=jsonl(answer("The usage limit is 10."), COMPLETE)))
    assert journal.classify_call(call, 180) == "ok" and not call.output.usage_limit
    for raw in (b"usage limit reached", jsonl({"type": "notice", "message": "usage limit"})):
        assert not journal.parse_stdout(raw).usage_limit


@pytest.mark.parametrize("tail", [b'{"type":', b"\xff"])
def test_truncated_tail_retains_already_structured_limit(call_folder, tail):
    output = jsonl({"type": "error", "message": "usage limit"}) + tail
    call = journal.read_call(call_folder(output=output))
    assert journal.classify_call(call, 180) == "usage_limit"


@pytest.mark.parametrize(
    "raw,exit_code",
    [
        (jsonl(answer("  old  "), answer(" final "), COMPLETE), 0),
        (
            jsonl(
                {"type": "item.updated", "item": {"type": "agent_message", "text": "updated"}},
                COMPLETE,
            ),
            0,
        ),
        (jsonl(answer(), COMPLETE), 1),
        (jsonl(answer()), 0),
        (jsonl(COMPLETE), 0),
        (jsonl(answer(" "), COMPLETE), 0),
        (jsonl({"type": "error", "message": "connection failed"}, answer(), COMPLETE), 0),
        (jsonl({"type": "turn.failed", "error": {"message": "failed"}}, answer(), COMPLETE), 0),
        (
            jsonl(
                {"type": "item.completed", "item": {"type": "command_execution"}},
                answer(),
                COMPLETE,
            ),
            0,
        ),
        (jsonl({"type": "item.completed", "item": None}), 0),
        (jsonl({"type": "item.completed", "item": {"type": "agent_message", "text": 3}}), 0),
        (jsonl(answer(), {"type": "turn.completed", "usage": {"input_tokens": True}}), 0),
        (jsonl(answer(), {"type": "turn.completed", "usage": {"output_tokens": -1}}), 0),
        (jsonl(answer(), {"type": "turn.completed", "usage": "bad"}), 0),
        (b"\xff", 0),
        (b"[]\n", 0),
        (b'{"type":2}\n', 0),
        (jsonl(answer(), COMPLETE) + b"malformed\n", 0),
        (jsonl({"type": "item.started", "item": {"type": "reasoning"}}, answer(), COMPLETE), 0),
    ],
)
def test_stdout_gate_matches_actual_provider_function(raw, exit_code):
    from llm.providers.base import ProviderUnavailable
    from llm.providers.codex import _parse_answer

    observed = journal.parse_stdout(raw, exit_code)
    try:
        expected = _parse_answer(raw, exit_code, "captured")
    except ProviderUnavailable as error:
        assert not observed.accepted and observed.reason == error.reason
        assert observed.text == "" and not observed.completed
    else:
        assert observed.accepted and observed.completed
        assert observed.text == expected.text


def test_reader_imports_real_parsers_without_dynamic_execution():
    from llm.providers.base import ProviderUnavailable
    from llm.providers.codex import DISABLED_FEATURES, _parse_answer
    from scripts.chat_answer_judge import prompt_id, read_prompt

    tree = ast.parse((TOOLS / "capture_journal.py").read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names & {"ast", "exec", "compile"}
    assert journal._parse_answer is _parse_answer
    assert journal.ProviderUnavailable is ProviderUnavailable
    assert journal.DISABLED_FEATURES is DISABLED_FEATURES
    assert journal.prompt_id is prompt_id and journal.read_prompt is read_prompt


def test_native_shim_csharp5_and_capture_before_spawn_contract():
    source = (TOOLS / "shim/CaptureShim.cs").read_text(encoding="utf-8")
    for forbidden in ('$"', "?.", "nameof", "=>"):
        assert forbidden not in source
    assert 'args[0] == "--configure"' in source
    assert 'options["--real-exe"]' in source and 'options["--capture-root"]' in source
    assert "File.Replace(temporary, config, null)" in source
    assert "FileMode.CreateNew" in source and "CreateDirectoryW(folder" in source
    assert "FileOptions.WriteThrough" in source and "Flush(true)" in source
    eof = source.index("Console.OpenStandardInput().CopyTo(bytes)")
    stdin = source.index('WriteBytes(Path.Combine(folder, "stdin.bin")')
    start = source.index('WriteJson(Path.Combine(folder, "start.json")')
    refusal = source.index('Fail("capture preflight", error); return 1;')
    spawn = source.index("if (!child.Start())")
    spawned = source.index('WriteJson(Path.Combine(folder, "spawned.json")')
    feed = source.index("child.StandardInput.BaseStream.Write")
    assert eof < stdin < start < refusal < spawn < spawned < feed
    assert "new ProcessStartInfo(real, tail)" in source
    assert "Environment.CommandLine" in source and "return raw.Substring(i)" in source
    assert "UseShellExecute = false" in source and "CreateNoWindow = true" in source
    assert "entry.Value" not in source
    assert "return captureFailed == 0 ? child.ExitCode : 1" in source
    assert '"capture_ok", captureFailed == 0' in source


def test_builder_refuses_non_windows_without_spawning(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(builder.sys, "platform", "darwin")
    monkeypatch.setattr(builder.subprocess, "run", lambda *a, **kw: pytest.fail("spawned compiler"))
    target = tmp_path / "capture.exe"
    assert builder.main(["--out", str(target)]) == 1
    assert "requires Windows" in capsys.readouterr().err
    assert not target.exists()


def test_builder_source_uses_legacy_compiler_and_exact_exe_hash():
    source = (TOOLS / "build_shim.py").read_text(encoding="utf-8")
    for flag in ("/langversion:5", "/target:exe", "/optimize+", "/warnaserror+"):
        assert flag in source
    assert "/deterministic" not in source
    assert '"exe_sha256": sha256(out)' in source
