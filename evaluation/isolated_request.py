"""One stateless request to the model of the session, and the record of what else it held.

Plan decision D12 gives the checks of the quality thread to one model, asked in requests that
share nothing with one another or with the session that planned them. The Claude Code CLI is
the route to that model, and a plain `claude -p` is not such a request: it also sends the
owner's instruction file, the output of the session hooks and the description of the account,
and it opens a memory directory (found by a probe on 2026-10-05; the label check of the pilot
and the P2 Opus reference collection had been sent with those arguments). Every later check
goes through this module:

- `--safe-mode` loads no instruction file, memory, hook, skill, plugin or MCP server;
- the process runs in one empty directory outside any repository, with no tools and no stored
  session;
- the reply is read from the event stream, every text block in order: the JSON envelope keeps
  the text of the last turn only and loses the head of a reply that was continued;
- the stream's own description of the session is checked and returned with the reply as the
  session record; a reply whose session loaded anything, named a built-in plugin or agent
  type outside the registered ones, or took a second turn, is refused.

Two blocks the CLI adds cannot be switched off under a subscription login and belong to the
route: the description of the account and the description of the environment (working
directory, platform, shell, OS, model name, knowledge cutoff, today's date).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evaluation.blinded_judge_clients import JudgeUnavailable, Reply

MODEL = "claude-opus-5-5"
EFFORT = "max"
ROUTE = "Claude Code CLI in safe mode, first-party provider"
SESSION = (
    "safe mode: no instruction file, memory, hook, skill, plugin or MCP server; no tools; "
    "an empty working directory; nothing stored; one turn"
)
DIRECTORY = "isolated-request"
# What a session may load besides the request; every list of a counted reply is empty.
LOADED = (
    "tools",
    "mcp_servers",
    "slash_commands",
    "skills",
    "memory_paths",
    "plugins",
    "hook_events",
)
# What the CLI builds in is named by every session and is no load of the owner's: its own
# plugins (path "builtin") and its agent types. These are the names of the probe that
# registered the route (CLI 2.1.289). A name outside them means the CLI builds in something
# the probe did not see, and no reply counts until the route is probed and registered again.
BUILTIN = {
    "plugins": ("cc-plugin-agents-md", "cc-plugin-plugin-authoring", "cc-plugin-telemetry"),
    "agents": ("Explore", "Plan", "claude", "general-purpose"),
}
COUNTERS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)
# The executable may be a batch file, and the command shell rewrites these inside an argument:
# the model would then read a system prompt other than the one whose SHA-256 is registered.
_SHELL = re.compile(r'["%^&|<>!\r\n]')


@dataclass(frozen=True)
class IsolatedReply(Reply):
    """A reply together with the record of the session that gave it."""

    session: dict[str, Any]


def arguments(system_prompt: str, *, model: str = MODEL, effort: str = EFFORT) -> tuple[str, ...]:
    """The command line of one request; the request text itself goes to standard input."""
    if not system_prompt.strip() or _SHELL.search(system_prompt):
        raise ValueError("the system prompt is empty or holds a character a shell rewrites")
    return (
        "-p",
        "--safe-mode",
        "--model",
        model,
        "--effort",
        effort,
        "--tools",
        "",
        "--permission-mode",
        "dontAsk",
        "--disable-slash-commands",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-hook-events",
        "--system-prompt",
        system_prompt,
    )


def settings(system_prompt: str, *, model: str = MODEL, effort: str = EFFORT) -> dict[str, str]:
    """What a plan or a judge version says of the route: names and a hash, never a path."""
    arguments(system_prompt, model=model, effort=effort)
    return {
        "model": model,
        "effort": effort,
        "tools": "none",
        "session": SESSION,
        "system_prompt_sha256": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
    }


def find_cli() -> str | None:
    return shutil.which("claude.cmd") or shutil.which("claude")


def working_directory() -> Path:
    """The one directory every request runs in: it holds nothing and no repository holds it."""
    directory = Path(tempfile.gettempdir()) / DIRECTORY
    directory.mkdir(exist_ok=True)
    if any(directory.iterdir()):
        raise JudgeUnavailable("cli_directory", "the request directory is not empty")
    return directory


def _events(raw: str) -> list[dict[str, Any]]:
    events = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            raise ValueError("Claude CLI did not return an event stream") from None
        if not isinstance(event, dict):
            raise ValueError("Claude CLI did not return an event stream")
        events.append(event)
    return events


def _names(value: Any) -> list[str]:
    """Names of what one list of the session description holds; the key of a path, not the path."""
    if value is None:
        return []
    if isinstance(value, Mapping):
        return sorted(str(key) for key in value)
    if not isinstance(value, list):
        raise ValueError("Claude CLI did not describe the session")
    return [str(item.get("name")) if isinstance(item, Mapping) else str(item) for item in value]


def _memory(value: Any) -> list[str]:
    """Kinds of memory the session opened: a path names the owner's account and is never kept."""
    if isinstance(value, Mapping):
        return sorted(str(key) for key in value)
    return ["memory"] if value else []


def _unregistered(builtin: Any) -> list[str]:
    """Kinds of built-in that name something outside the registered ones; all, if unreadable."""
    if not isinstance(builtin, Mapping) or set(builtin) != set(BUILTIN):
        return sorted(BUILTIN)
    return sorted(
        kind
        for kind, names in builtin.items()
        if not isinstance(names, list) or not set(map(str, names)) <= set(BUILTIN[kind])
    )


def _session(events: list[dict[str, Any]], model: str) -> dict[str, Any]:
    """Read the session description and what ran beside the request; names only."""
    described = [
        event for event in events if (event.get("type"), event.get("subtype")) == ("system", "init")
    ]
    if len(described) != 1:
        raise ValueError("Claude CLI did not describe the session")
    init = described[0]
    version = init.get("claude_code_version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Claude CLI did not describe the session")
    if init.get("model") != model:
        raise ValueError("Claude CLI used a different model")
    if init.get("output_style") not in (None, "default"):
        raise ValueError("Claude CLI used an output style")
    plugins = init.get("plugins")
    for key in ("tools", "mcp_servers", "slash_commands", "skills"):
        if not isinstance(init.get(key), list):
            raise ValueError("Claude CLI did not describe the session")
    if not isinstance(plugins, list) or not all(isinstance(plugin, Mapping) for plugin in plugins):
        raise ValueError("Claude CLI did not describe the session")
    loaded = {
        "tools": _names(init["tools"]),
        "mcp_servers": _names(init["mcp_servers"]),
        "slash_commands": _names(init["slash_commands"]),
        "skills": _names(init["skills"]),
        "memory_paths": _memory(init.get("memory_paths")),
        "plugins": _names([plugin for plugin in plugins if plugin.get("path") != "builtin"]),
        "hook_events": [
            str(event.get("hook_name") or event.get("subtype"))
            for event in events
            if event.get("type") == "system" and str(event.get("subtype")).startswith("hook")
        ],
    }
    return {
        "cli_version": version.strip(),
        "model": model,
        "loaded": loaded,
        "builtin": {
            "plugins": _names([plugin for plugin in plugins if plugin.get("path") == "builtin"]),
            "agents": _names(init.get("agents")),
        },
    }


def _text(events: list[dict[str, Any]], model: str) -> tuple[str, int]:
    """Join every text block of every assistant message in order; count the messages."""
    messages: dict[str, list[str]] = {}
    for event in events:
        if event.get("type") != "assistant":
            continue
        message = event.get("message")
        if not isinstance(message, Mapping) or not isinstance(message.get("content"), list):
            raise ValueError("Claude CLI returned an unreadable message")
        if message.get("model") != model:
            raise ValueError("Claude CLI used a different model")
        if event.get("parent_tool_use_id") is not None:
            raise ValueError("Claude CLI returned a message of another agent")
        parts = messages.setdefault(str(message.get("id")), [])
        for block in message["content"]:
            kind = block.get("type") if isinstance(block, Mapping) else None
            if kind == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
            elif kind not in ("thinking", "redacted_thinking"):
                raise ValueError("Claude CLI returned a block that is not text")
    return "\n".join("".join(parts) for parts in messages.values()), len(messages)


def check_record(record: Any) -> None:
    """Refuse the record of a session that loaded anything or did not answer in one turn."""
    if not isinstance(record, Mapping):
        raise ValueError("a reply has no session record")
    loaded = record.get("loaded")
    version = record.get("cli_version")
    if (
        not isinstance(version, str)
        or not version
        or not isinstance(record.get("model"), str)
        or not isinstance(loaded, Mapping)
        or set(loaded) != set(LOADED)
        or any(value != [] for value in loaded.values())
        or _unregistered(record.get("builtin"))
        or record.get("turns") != 1
    ):
        raise ValueError("a session record is not that of a clean session of one turn")


def parse_stream(raw: str, model: str = MODEL, *, single_turn: bool = True) -> dict[str, Any]:
    """Read the event stream of one request; refuse any reply the route does not vouch for.

    Returned: `text`, `model`, `usage` and `session`. With `single_turn` unset a continued
    reply is joined across its turns; such a reply is a reading aid and never evidence.
    """
    events = _events(raw)
    record = _session(events, model)
    held = sorted(kind for kind, names in record["loaded"].items() if names)
    if held:
        raise ValueError(f"the session loaded more than the request: {', '.join(held)}")
    unknown = _unregistered(record["builtin"])
    if unknown:
        raise ValueError(
            f"the session names a built-in outside the registered ones: {', '.join(unknown)}"
        )
    finished = [event for event in events if event.get("type") == "result"]
    if len(finished) != 1:
        raise ValueError("Claude CLI did not finish the session")
    result = finished[0]
    if result.get("is_error") is not False:
        raise ValueError("Claude CLI returned an error")
    if result.get("terminal_reason") != "completed" or result.get("stop_reason") != "end_turn":
        raise ValueError("Claude CLI did not complete")
    model_usage = result.get("modelUsage")
    if not isinstance(model_usage, Mapping) or set(model_usage) != {model}:
        raise ValueError("Claude CLI used a different model")
    reported = model_usage[model]
    if not isinstance(reported, Mapping) or reported.get("canonicalModel") != model:
        raise ValueError("Claude CLI did not confirm the requested model")
    if reported.get("provider") != "firstParty":
        raise ValueError("Claude CLI did not use the first-party provider")
    text, messages = _text(events, model)
    turns = result.get("num_turns")
    if type(turns) is not int or turns < 1 or messages < 1:
        raise ValueError("Claude CLI returned no reply")
    injected = any(event.get("type") == "user" for event in events)
    if single_turn and (turns != 1 or messages != 1 or injected):
        raise ValueError("Claude CLI did not answer in one turn")
    # The envelope's own copy of the last turn must close the joined text, spacing aside.
    last = result.get("result")
    if (
        not isinstance(last, str)
        or not last.strip()
        or not "".join(text.split()).endswith("".join(last.split()))
    ):
        raise ValueError("Claude CLI returned no reply")
    counted = result.get("usage")
    if not isinstance(counted, Mapping):
        counted = {}
    usage: dict[str, Any] = {
        field: counted[field] for field in COUNTERS if type(counted.get(field)) is int
    }
    details = counted.get("output_tokens_details")
    if isinstance(details, Mapping) and type(details.get("thinking_tokens")) is int:
        usage["thinking_tokens"] = details["thinking_tokens"]
    if type(result.get("total_cost_usd")) in (int, float):
        usage["total_cost_usd"] = result["total_cost_usd"]
    record["turns"] = turns
    # Everything the model was sent, in tokens: the request, the system prompt and the two
    # blocks the CLI adds. Beside the request's length it shows that nothing else rode along.
    record["context_tokens"] = sum(
        usage.get(field, 0)
        for field in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    )
    return {"text": text, "model": model, "usage": usage, "session": record}


def send(
    executable: str,
    system_prompt: str,
    message: str,
    *,
    timeout_s: float,
    model: str = MODEL,
    effort: str = EFFORT,
    single_turn: bool = True,
) -> IsolatedReply:
    """Send one request in a new process and return its reply with the session record."""
    command = [executable, *arguments(system_prompt, model=model, effort=effort)]
    directory = working_directory()
    start = time.monotonic()
    try:
        process = subprocess.run(
            command,
            input=message,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=directory,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise JudgeUnavailable("cli_timeout", "Claude CLI request timed out") from None
    except OSError:
        raise JudgeUnavailable("cli_missing", "Claude CLI did not start") from None
    if process.returncode != 0:
        raise JudgeUnavailable("cli_exit", f"Claude CLI exited with {process.returncode}")
    try:
        parsed = parse_stream(process.stdout, model, single_turn=single_turn)
    except ValueError as exc:
        raise JudgeUnavailable("cli_response", str(exc)) from None
    return IsolatedReply(
        parsed["text"],
        parsed["model"],
        parsed["usage"],
        time.monotonic() - start,
        parsed["session"],
    )
