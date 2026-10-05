"""The route of every single-model check: one stateless request and its session record."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from evaluation import isolated_request as isolated
from evaluation.blinded_judge_clients import JudgeUnavailable, Reply

OPUS = "claude-opus-5-5"
PROMPT = "Use only the supplied text and return the requested JSON object."
THINKING = {"type": "thinking", "thinking": "", "signature": "HIDDEN_SIGNATURE"}
BUILTIN = {"name": "cc-plugin-telemetry", "path": "builtin", "source": "HIDDEN_SOURCE"}


def init(**changes: Any) -> dict[str, Any]:
    return {
        "type": "system",
        "subtype": "init",
        "cwd": "HIDDEN_DIRECTORY",
        "session_id": "HIDDEN_SESSION",
        "tools": [],
        "mcp_servers": [],
        "model": OPUS,
        "permissionMode": "dontAsk",
        "slash_commands": [],
        "apiKeySource": "none",
        "claude_code_version": "9.9.9",
        "agents": ["claude", "Plan"],
        "skills": [],
        "plugins": [BUILTIN],
        **changes,
    }


def text(value: str) -> dict[str, str]:
    return {"type": "text", "text": value}


def said(
    *blocks: dict[str, Any], model: str = OPUS, message: str = "msg_1", **changes: Any
) -> dict:
    return {
        "type": "assistant",
        "message": {"model": model, "id": message, "role": "assistant", "content": list(blocks)},
        "parent_tool_use_id": None,
        **changes,
    }


def result(**changes: Any) -> dict[str, Any]:
    return {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "terminal_reason": "completed",
        "stop_reason": "end_turn",
        "num_turns": 1,
        "result": "the reply",
        "usage": {
            "input_tokens": 2,
            "cache_creation_input_tokens": 597,
            "cache_read_input_tokens": 1,
            "output_tokens": 795,
            "output_tokens_details": {"thinking_tokens": 534},
            "service_tier": "HIDDEN_TIER",
            "iterations": [],
        },
        "total_cost_usd": 0.02,
        "modelUsage": {OPUS: {"canonicalModel": OPUS, "provider": "firstParty"}},
        "session_id": "HIDDEN_SESSION",
        **changes,
    }


def stream(*events: dict[str, Any]) -> str:
    return "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n"


NOISE = (
    {"type": "system", "subtype": "thinking_tokens", "estimated_tokens": 50},
    {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}},
)


def clean(**changes: Any) -> str:
    return stream(
        init(), NOISE[0], said(THINKING), said(text("the reply")), NOISE[1], result(**changes)
    )


def test_a_clean_session_gives_the_text_the_counters_and_the_record() -> None:
    parsed = isolated.parse_stream(clean())
    assert parsed["text"] == "the reply" and parsed["model"] == OPUS
    assert parsed["usage"] == {
        "input_tokens": 2,
        "output_tokens": 795,
        "cache_creation_input_tokens": 597,
        "cache_read_input_tokens": 1,
        "thinking_tokens": 534,
        "total_cost_usd": 0.02,
    }
    record = parsed["session"]
    assert record == {
        "cli_version": "9.9.9",
        "model": OPUS,
        "loaded": {kind: [] for kind in isolated.LOADED},
        "builtin": {"plugins": ["cc-plugin-telemetry"], "agents": ["claude", "Plan"]},
        "turns": 1,
        "context_tokens": 600,
    }
    isolated.check_record(record)
    assert "HIDDEN" not in json.dumps(parsed)


def test_text_blocks_of_one_message_are_joined_in_the_order_they_came() -> None:
    raw = stream(
        init(), said(THINKING), said(text("the ")), said(THINKING), said(text("reply")), result()
    )
    assert isolated.parse_stream(raw)["text"] == "the reply"
    spaced = stream(init(), said(text("the\n\n")), said(text("reply")), result(result="the reply"))
    assert isolated.parse_stream(spaced)["text"] == "the\n\nreply"


@pytest.mark.parametrize(
    "events,reason",
    [
        ((said(text("the reply")), result()), "did not describe the session"),
        ((init(), init(), said(text("the reply")), result()), "did not describe the session"),
        ((init(claude_code_version=" "), said(text("the reply")), result()), "did not describe"),
        ((init(tools=None), said(text("the reply")), result()), "did not describe the session"),
        ((init(plugins=["telemetry"]), said(text("the reply")), result()), "did not describe"),
        ((init(model="claude-sonnet-5-5"), said(text("the reply")), result()), "different model"),
        ((init(tools=["Read"]), said(text("the reply")), result()), "loaded more .*: tools"),
        (
            (
                init(mcp_servers=[{"name": "HIDDEN", "status": "connected"}]),
                said(text("x")),
                result(),
            ),
            "loaded more .*: mcp_servers",
        ),
        ((init(slash_commands=["review"]), said(text("x")), result()), ": slash_commands"),
        ((init(skills=["HIDDEN"]), said(text("the reply")), result()), "loaded more .*: skills"),
        (
            (init(memory_paths={"auto": "C:/HIDDEN/memory"}), said(text("the reply")), result()),
            "loaded more .*: memory_paths",
        ),
        ((init(memory_paths=["C:/HIDDEN"]), said(text("the reply")), result()), ": memory_paths"),
        (
            (
                init(plugins=[BUILTIN, {"name": "HIDDEN", "path": "C:/HIDDEN"}]),
                said(text("x")),
                result(),
            ),
            "loaded more .*: plugins",
        ),
        (
            (
                {"type": "system", "subtype": "hook_started", "hook_name": "SessionStart:startup"},
                init(),
                said(text("the reply")),
                result(),
            ),
            "loaded more .*: hook_events",
        ),
        (
            (init(skills=["a"], tools=["b"]), said(text("the reply")), result()),
            "loaded more than the request: skills, tools",
        ),
        (
            (init(agents=["claude", "HIDDEN"]), said(text("the reply")), result()),
            "built-in outside the registered ones: agents",
        ),
        (
            (
                init(plugins=[BUILTIN, {"name": "HIDDEN", "path": "builtin"}]),
                said(text("x")),
                result(),
            ),
            "built-in outside the registered ones: plugins",
        ),
        ((init(output_style="HIDDEN"), said(text("the reply")), result()), "an output style"),
        ((init(), said(text("the reply"))), "did not finish the session"),
        ((init(), said(text("the reply")), result(), result()), "did not finish the session"),
        ((init(), said(text("the reply")), result(is_error=True)), "returned an error"),
        ((init(), said(text("the reply")), result(terminal_reason="max_turns")), "not complete"),
        ((init(), said(text("the reply")), result(stop_reason="max_tokens")), "did not complete"),
        (
            (init(), said(text("the reply")), result(modelUsage={"claude-sonnet-5-5": {}})),
            "different model",
        ),
        (
            (
                init(),
                said(text("the reply")),
                result(modelUsage={OPUS: {"canonicalModel": OPUS}, "claude-haiku-4-5": {}}),
            ),
            "different model",
        ),
        (
            (
                init(),
                said(text("the reply")),
                result(
                    modelUsage={OPUS: {"canonicalModel": "claude-opus-5", "provider": "firstParty"}}
                ),
            ),
            "did not confirm the requested model",
        ),
        (
            (
                init(),
                said(text("the reply")),
                result(modelUsage={OPUS: {"canonicalModel": OPUS, "provider": "bedrock"}}),
            ),
            "first-party provider",
        ),
        ((init(), said(text("the reply"), model="claude-sonnet-5-5"), result()), "different model"),
        ((init(), said(text("the reply"), parent_tool_use_id="HIDDEN"), result()), "another agent"),
        (
            (init(), said({"type": "tool_use", "name": "Read", "input": {}}), result()),
            "a block that is not text",
        ),
        ((init(), {"type": "assistant", "message": "HIDDEN"}, result()), "unreadable message"),
        ((init(), said(THINKING), result()), "returned no reply"),
        ((init(), said(text("  ")), result(result="  ")), "returned no reply"),
        ((init(), said(text("another reply")), result(result="the reply")), "returned no reply"),
        ((init(), said(text("the reply")), result(result=None)), "returned no reply"),
        ((init(), said(text("the reply")), result(num_turns="1")), "returned no reply"),
        ((init(), said(text("the reply")), result(num_turns=2)), "did not answer in one turn"),
        (
            (init(), said(text("the ")), said(text("reply"), message="msg_2"), result()),
            "did not answer in one turn",
        ),
        (
            (init(), said(text("the reply")), {"type": "user", "message": "HIDDEN"}, result()),
            "did not answer in one turn",
        ),
    ],
)
def test_a_reply_the_route_does_not_vouch_for_is_refused(events: tuple, reason: str) -> None:
    with pytest.raises(ValueError, match=reason) as error:
        isolated.parse_stream(stream(*events))
    assert "HIDDEN" not in str(error.value)


@pytest.mark.parametrize("raw", ["not json\n", '["a list"]\n', clean() + "trailing words\n"])
def test_a_stream_that_is_not_events_is_refused(raw: str) -> None:
    with pytest.raises(ValueError, match="did not return an event stream"):
        isolated.parse_stream(raw)


def test_a_continued_reply_is_joined_only_as_a_reading_aid() -> None:
    raw = stream(
        init(),
        said(text("the head,"), message="msg_1"),
        {"type": "user", "message": "HIDDEN"},
        said(text("the tail"), message="msg_2"),
        result(num_turns=2, result="the tail"),
    )
    with pytest.raises(ValueError, match="did not answer in one turn"):
        isolated.parse_stream(raw)
    joined = isolated.parse_stream(raw, single_turn=False)
    assert joined["text"] == "the head,\nthe tail" and joined["session"]["turns"] == 2
    with pytest.raises(ValueError, match="clean session of one turn"):
        isolated.check_record(joined["session"])


def test_the_default_output_style_and_the_registered_built_ins_are_the_route() -> None:
    plugins = [{"name": name, "path": "builtin"} for name in isolated.BUILTIN["plugins"]]
    events = (
        init(output_style="default", plugins=plugins, agents=list(isolated.BUILTIN["agents"])),
        said(text("the reply")),
        result(),
    )
    record = isolated.parse_stream(stream(*events))["session"]
    assert record["builtin"] == {kind: list(names) for kind, names in isolated.BUILTIN.items()}
    isolated.check_record(record)


def test_stored_record_counts_only_when_nothing_was_loaded() -> None:
    record = isolated.parse_stream(clean())["session"]
    isolated.check_record(json.loads(json.dumps(record)))
    for broken in (
        None,
        "record",
        {**record, "cli_version": ""},
        {**record, "model": None},
        {**record, "turns": 2},
        {**record, "loaded": {**record["loaded"], "skills": ["one"]}},
        {**record, "loaded": {kind: [] for kind in isolated.LOADED[:-1]}},
        {key: value for key, value in record.items() if key != "loaded"},
        {**record, "builtin": {**record["builtin"], "agents": ["claude", "reviewer"]}},
        {**record, "builtin": {"plugins": []}},
        {key: value for key, value in record.items() if key != "builtin"},
    ):
        with pytest.raises(ValueError, match="session record"):
            isolated.check_record(broken)


def test_command_line_is_a_safe_mode_request_with_no_tools_and_no_stored_session() -> None:
    command = isolated.arguments(PROMPT)
    assert command[:2] == ("-p", "--safe-mode") and command[-2:] == ("--system-prompt", PROMPT)
    assert command[command.index("--model") + 1] == OPUS
    assert command[command.index("--effort") + 1] == "max"
    assert command[command.index("--tools") + 1] == ""
    assert command[command.index("--output-format") + 1] == "stream-json"
    for flag in (
        "--no-session-persistence",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--include-hook-events",
        "--verbose",
    ):
        assert flag in command
    assert "--resume" not in command and "--continue" not in command
    assert isolated.settings(PROMPT) == {
        "model": OPUS,
        "effort": "max",
        "tools": "none",
        "session": isolated.SESSION,
        "system_prompt_sha256": hashlib.sha256(PROMPT.encode("utf-8")).hexdigest(),
    }
    assert "safe mode" in isolated.ROUTE and "safe mode" in isolated.SESSION


@pytest.mark.parametrize(
    "prompt", ["", "  ", 'say "yes"', "100% sure", "a & b", "two\nlines", "now!"]
)
def test_system_prompt_a_shell_would_rewrite_is_refused(prompt: str) -> None:
    with pytest.raises(ValueError, match="system prompt"):
        isolated.arguments(prompt)
    with pytest.raises(ValueError, match="system prompt"):
        isolated.settings(prompt)


@pytest.fixture
def temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(isolated.tempfile, "gettempdir", lambda: str(tmp_path))
    return tmp_path


def test_send_runs_one_process_in_the_empty_directory_with_the_request_on_stdin(
    temp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def run(command: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
        calls.append((command, options))
        return subprocess.CompletedProcess(command, 0, stdout=clean(), stderr="")

    monkeypatch.setattr(isolated.subprocess, "run", run)
    reply = isolated.send("HIDDEN_CLI", PROMPT, "the request", timeout_s=5)
    again = isolated.send("HIDDEN_CLI", PROMPT, "the request", timeout_s=5)
    assert isinstance(reply, isolated.IsolatedReply) and isinstance(reply, Reply)
    assert reply.text == again.text == "the reply" and reply.model == OPUS
    assert reply.usage["output_tokens"] == 795 and reply.elapsed_s >= 0
    isolated.check_record(reply.session)
    (command, options), _ = calls
    assert command == ["HIDDEN_CLI", *isolated.arguments(PROMPT)]
    assert options["input"] == "the request" and options["timeout"] == 5
    assert options["cwd"] == temp / isolated.DIRECTORY and not any(options["cwd"].iterdir())
    assert "the request" not in command


def test_send_does_not_start_in_a_directory_that_holds_anything(
    temp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (temp / isolated.DIRECTORY).mkdir()
    (temp / isolated.DIRECTORY / "CLAUDE.md").write_text("HIDDEN", encoding="utf-8")
    monkeypatch.setattr(isolated.subprocess, "run", lambda *a, **k: pytest.fail("a request left"))
    with pytest.raises(JudgeUnavailable) as error:
        isolated.send("HIDDEN_CLI", PROMPT, "the request", timeout_s=5)
    assert error.value.code == "cli_directory"


@pytest.mark.parametrize(
    "outcome,code",
    [
        (subprocess.TimeoutExpired("claude", 5), "cli_timeout"),
        (OSError("HIDDEN"), "cli_missing"),
        (subprocess.CompletedProcess([], 3, stdout=clean(), stderr="HIDDEN"), "cli_exit"),
        (subprocess.CompletedProcess([], 0, stdout="not json", stderr=""), "cli_response"),
        (
            subprocess.CompletedProcess(
                [], 0, stdout=stream(init(skills=["HIDDEN"]), said(text("x")), result()), stderr=""
            ),
            "cli_response",
        ),
    ],
)
def test_send_reports_a_failure_as_an_unavailable_route(
    temp: Path, monkeypatch: pytest.MonkeyPatch, outcome: Any, code: str
) -> None:
    def run(command: list[str], **options: Any) -> Any:
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(isolated.subprocess, "run", run)
    with pytest.raises(JudgeUnavailable) as error:
        isolated.send("HIDDEN_CLI", PROMPT, "the request", timeout_s=5)
    assert error.value.code == code and "HIDDEN" not in str(error.value)
