"""CLI boundary acceptance, isolation, deadlines and subscription accounting."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from llm.providers.base import ProviderUnavailable, flatten_messages
from llm.providers.codex import CodexProvider, _parse_answer
from tests._fake_codex import ANSWER, FIXTURES
from tests._fake_codex import fake_codex as fake_codex

MESSAGES = [{"role": "user", "content": "Question with {prompt} and Unicode: café."}]
WRAPPER_HASH = "583b49ac747123ce24e17d200f3deb70c82117f9f0e295c1dc6db3df311086af"
# Independent command contract, intentionally not imported from the implementation.
DISABLED = (
    "shell_tool unified_exec apps auth_elicitation browser_annotation_api browser_use "
    "browser_use_external browser_use_full_cdp_access "
    "computer_use goals hooks image_generation in_app_browser in_app_chat in_app_dictation "
    "in_app_local_automation in_app_voice incremental_tools multi_agent plugin_discovery_prefetch "
    "plugin_sharing plugins prediction_preserve_parent_tools remote_plugin shell_snapshot "
    "skill_mcp_dependency_install skill_search sleep_tool tool_call_mcp_elicitation "
    "tool_suggest unified_exec_tty view_image workspace_dependencies write_stdin_approval"
).split()


def provider(fake, **kwargs):
    return CodexProvider(binary=str(fake.binary), **kwargs)


@pytest.mark.parametrize("missing", [False, True])
def test_usage_metadata_keeps_all_nonnegative_integers(missing):
    usage = {
        "input_tokens": 17,
        "output_tokens": 5,
        "cached_input_tokens": 11,
        "cache_write_input_tokens": 2,
        "reasoning_output_tokens": 3,
        "future_tokens": 0,
    }
    complete = {"type": "turn.completed"}
    if not missing:
        complete["usage"] = {
            **usage,
            "text": "Synthetic diagnostic",
            "fraction": 1.5,
            "flag": True,
            "negative": -1,
            "null": None,
        }
    raw = "\n".join(
        json.dumps(event)
        for event in (
            {"type": "item.completed", "item": {"type": "agent_message", "text": "OK"}},
            complete,
        )
    ).encode()
    result = _parse_answer(raw, 0, "synthetic")
    assert result.metadata == {"usage": {} if missing else usage}
    assert (result.input_tokens, result.output_tokens) == ((0, 0) if missing else (17, 5))


@pytest.mark.parametrize("key", ["input_tokens", "output_tokens"])
@pytest.mark.parametrize("value", [True, -1, 1.5, "1", None])
def test_required_usage_validation_is_unchanged(key, value):
    events = [
        {"type": "item.completed", "item": {"type": "agent_message", "text": "OK"}},
        {"type": "turn.completed", "usage": {key: value}},
    ]
    with pytest.raises(ProviderUnavailable, match="^codex_json$"):
        _parse_answer("\n".join(map(json.dumps, events)).encode(), 0, "synthetic")


def test_wrapper_pin():
    root = Path(__file__).resolve().parents[1]
    for relative in ("llm/codex_wrapper.txt", "reports/generator-ceiling/tools/wrapper.txt"):
        content = (root / relative).read_bytes()
        assert hashlib.sha256(content).hexdigest() == WRAPPER_HASH
        assert content.count(b"{prompt}") == 1


def test_exact_request_isolation_and_usage(fake_codex, monkeypatch, tmp_path):
    home = tmp_path / "service-home"
    home.mkdir()
    private_environment = {
        "DATABASE_URL": "never-forward-database",
        "OPENAI_API_KEY": "never-forward-auth",
        "EXTRA_SECRET": "never-forward-extra",
    }
    for key, value in {
        **private_environment,
        "CODEX_HOME": "inherited-home",
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TMPDIR": str(tmp_path),
    }.items():
        monkeypatch.setenv(key, value)
    result = provider(fake_codex, codex_home=str(home)).generate(MESSAGES)
    assert (result.text, result.provider, result.model) == (ANSWER, "codex", "gpt-6-astra")
    assert (result.input_tokens, result.output_tokens, result.cost_usd) == (17852, 5, 0.0)
    (record,) = fake_codex.records()
    cwd = record["cwd"]
    expected = [
        "exec",
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "read-only",
    ]
    for feature in DISABLED:
        expected += ["--disable", feature]
    expected += ["-m", "gpt-6-astra", "-c", 'model_reasoning_effort="xhigh"', "-C", cwd, "-"]
    argv = list(record["argv"])
    # macOS getcwd() canonicalizes /var to /private/var; both name the same directory.
    cwd_index = argv.index("-C") + 1
    assert Path(argv[cwd_index]).resolve() == Path(cwd).resolve()
    argv[cwd_index] = cwd
    assert argv == expected
    wrapper = (Path(__file__).resolve().parents[1] / "llm/codex_wrapper.txt").read_bytes()
    assert record["stdin"].encode() == wrapper.replace(
        b"{prompt}", flatten_messages(MESSAGES).encode(), 1
    )
    assert private_environment.keys().isdisjoint(record["environment"])
    # POSIX sh may add PWD, SHLVL and _; macOS may add __CF_USER_TEXT_ENCODING.
    assert set(record["environment"]) <= {
        "PATH",
        "HOME",
        "CODEX_HOME",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        "PWD",
        "SHLVL",
        "_",
        "__CF_USER_TEXT_ENCODING",
    }
    assert record["environment"]["CODEX_HOME"] == str(home)
    assert record["contents"] == [] and record["pgid"] == record["pid"]
    assert not Path(cwd).exists()


def test_inherited_home_and_last_message(fake_codex, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", "/fixture/inherited")
    fake_codex.configure(fixture="messages")
    result = provider(fake_codex).generate(MESSAGES)
    assert result.text == "The environment blocked the command; no file was read."
    assert result.output_tokens == 88
    assert fake_codex.records()[0]["environment"]["CODEX_HOME"] == "/fixture/inherited"


def test_windows_measured_warning_free_stream_and_flags(fake_codex):
    # Task 17b fact 2: CLI 0.166.0 succeeds with exactly these four events.
    fake_codex.configure(
        events=[
            {"type": "thread.started", "thread_id": "fixture-thread"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": ANSWER}},
            {"type": "turn.completed"},
        ]
    )
    assert provider(fake_codex).generate(MESSAGES).text == ANSWER
    argv = fake_codex.records()[0]["argv"]
    assert "code_mode_host" not in argv
    assert "code_mode_interrupt" not in argv


def test_windows_measured_host_warning_still_rejects(fake_codex):
    fake_codex.configure(
        events=[
            {"type": "thread.started", "thread_id": "fixture-thread"},
            {
                "type": "item.completed",
                "item": {
                    "type": "error",
                    "message": "Code Mode is unavailable because code-mode host is disabled.",
                },
            },
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": ANSWER}},
            {"type": "turn.completed"},
        ]
    )
    with pytest.raises(ProviderUnavailable, match="^codex_tool_use$"):
        provider(fake_codex).generate(MESSAGES)


@pytest.mark.parametrize(
    "kind",
    [
        "command_execution",
        "file_change",
        "mcp_tool_call",
        "web_search",
        "todo_list",
        "unknown",
        "error",
    ],
)
@pytest.mark.parametrize("event_type", ["item.started", "item.updated", "item.completed"])
def test_any_non_text_item_rejects_even_with_success(fake_codex, kind, event_type):
    events = [
        json.loads(line)
        for line in (FIXTURES / "ok.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    events.insert(2, {"type": event_type, "item": {"type": kind, "text": "private-answer"}})
    fake_codex.configure(events=events)
    with pytest.raises(ProviderUnavailable, match="^codex_tool_use$"):
        provider(fake_codex).generate(MESSAGES)


@pytest.mark.parametrize(
    "events,exit_code,reason",
    [
        (
            [{"type": "turn.failed", "error": {"message": "private failure"}}],
            0,
            "codex_turn_failed",
        ),
        ([{"type": "error", "message": "private error"}], 0, "codex_error"),
        (
            [{"type": "turn.failed", "error": {"message": "You've reached your usage limit"}}],
            1,
            "codex_usage_limit",
        ),
        (
            [
                {"type": "turn.completed"},
                {"type": "item.completed", "item": {"type": "agent_message", "text": "  "}},
            ],
            0,
            "codex_empty",
        ),
        ([{"type": "turn.completed"}], 7, "codex_exit"),
        ([], 0, "codex_incomplete"),
        (
            [{"type": "item.completed", "item": {"type": "agent_message", "text": "private"}}],
            0,
            "codex_incomplete",
        ),
    ],
)
def test_rejections_are_short_and_private(fake_codex, events, exit_code, reason):
    fake_codex.configure(events=events, exit_code=exit_code)
    with pytest.raises(ProviderUnavailable) as caught:
        provider(fake_codex).generate(MESSAGES)
    assert str(caught.value) == caught.value.reason == reason
    assert not Path(fake_codex.records()[0]["cwd"]).exists()


def test_real_failure_shape(fake_codex):
    fake_codex.configure(fixture="bad", exit_code=1)
    with pytest.raises(ProviderUnavailable, match="^codex_turn_failed$"):
        provider(fake_codex).generate(MESSAGES)


def test_reasoning_item_is_allowed(fake_codex):
    events = [
        json.loads(line)
        for line in (FIXTURES / "ok.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    events.insert(2, {"type": "item.completed", "item": {"type": "reasoning", "text": "private"}})
    fake_codex.configure(events=events)
    assert provider(fake_codex).generate(MESSAGES).text == ANSWER


def test_wrapper_io_failure_is_private_and_releases_slot(fake_codex, monkeypatch):
    from llm.providers import codex

    monkeypatch.setattr(codex, "_WRAPPER", fake_codex.root / "private-missing-path")
    llm = provider(fake_codex)
    with pytest.raises(ProviderUnavailable, match="^codex_io$"):
        llm.generate(MESSAGES)
    assert llm._slots.acquire(blocking=False)
    llm._slots.release()
    assert fake_codex.records() == []


def test_missing_binary(tmp_path):
    with pytest.raises(ProviderUnavailable, match="^codex_missing_binary$"):
        CodexProvider(binary=str(tmp_path / "absent")).generate(MESSAGES)


def test_timeout_kills_group_and_removes_directory(fake_codex):
    fake_codex.configure(delay=30, child=True)
    started = time.monotonic()
    with pytest.raises(ProviderUnavailable, match="^codex_timeout$"):
        provider(fake_codex, timeout_sec=1.5).generate(MESSAGES)
    assert time.monotonic() - started < 3
    (record,) = fake_codex.records()
    assert "child_pid" in record
    assert not Path(record["cwd"]).exists()
    time.sleep(3.1)
    assert not (fake_codex.root / "child-survived").exists()


@pytest.mark.parametrize("limit", [1, 2])
def test_concurrency_is_bounded(fake_codex, limit):
    fake_codex.configure(delay=0.3)
    llm = provider(fake_codex, max_concurrent_calls=limit, timeout_sec=10)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(r.text == ANSWER for r in pool.map(lambda _: llm.generate(MESSAGES), range(4)))
    changes = sorted(
        (r[k], delta) for r in fake_codex.records() for k, delta in (("started", 1), ("ended", -1))
    )
    active = peak = 0
    for _, delta in changes:
        active += delta
        peak = max(peak, active)
    assert peak == limit and active == 0


def test_queue_wait_counts_against_timeout(fake_codex):
    llm = provider(fake_codex, timeout_sec=0.1)
    assert llm._slots.acquire()
    try:
        with pytest.raises(ProviderUnavailable, match="^codex_timeout$"):
            llm.generate(MESSAGES)
    finally:
        llm._slots.release()
    assert fake_codex.records() == []


def test_stream_yields_one_complete_answer(fake_codex):
    async def collect():
        return [part async for part in provider(fake_codex).generate_stream(MESSAGES)]

    assert asyncio.run(collect()) == [ANSWER]
