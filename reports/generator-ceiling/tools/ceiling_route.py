"""Closed rollout admission and the foreground companion transport."""

import ctypes
import json
import math
import os
import re
import subprocess
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import ceiling_common as c

# One registered allow-list. Any extension requires an amendment.
ALLOW = {
    "top": (
        "session_meta",
        "turn_context",
        "world_state",
        "token_usage_record",
        "response_item",
        "event_msg",
    ),
    "response": ("message", "reasoning", "additional_tools"),
    "role": ("developer", "user", "assistant"),
    "event": (
        "task_started",
        "task_complete",
        "token_count",
        "thread_settings_applied",
        "item_completed",
    ),
    "completed": ("UserMessage", "AgentMessage", "Reasoning"),
}
TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)


def normalized(path):
    return os.path.normcase(os.path.normpath(str(path)))


def gate(entries, cwd, thread_id):
    errors, contexts, metas, finals = [], [], [], []
    usage, timing = None, {}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("type") not in ALLOW["top"]:
            errors.append("top_kind")
            continue
        kind, payload = entry["type"], entry.get("payload")
        if not isinstance(payload, dict):
            errors.append("payload")
            continue
        if kind == "turn_context":
            contexts.append(payload)
        elif kind == "session_meta":
            metas.append(payload)
        elif kind == "response_item":
            if payload.get("type") not in ALLOW["response"]:
                errors.append("response_kind")
            elif payload["type"] == "message":
                if payload.get("role") not in ALLOW["role"]:
                    errors.append("message_role")
                if payload.get("role") == "assistant" and payload.get("phase") == "final_answer":
                    content = payload.get("content")
                    if not isinstance(content, list) or any(
                        not isinstance(v, dict)
                        or v.get("type") != "output_text"
                        or not isinstance(v.get("text"), str)
                        for v in content
                    ):
                        errors.append("final_content")
                    else:
                        finals.append("".join(v["text"] for v in content))
        elif kind == "event_msg":
            event = payload.get("type")
            if event not in ALLOW["event"]:
                errors.append("event_kind")
            elif event == "item_completed" and (
                not isinstance(payload.get("item"), dict)
                or payload["item"].get("type") not in ALLOW["completed"]
            ):
                errors.append("completed_kind")
            elif event == "token_count":
                current_usage = (
                    payload["info"].get("total_token_usage")
                    if isinstance(payload.get("info"), dict)
                    else None
                )
                if current_usage is not None:
                    usage = current_usage
            elif event == "task_complete":
                timing = {
                    name: payload.get(name) for name in ("duration_ms", "time_to_first_token_ms")
                }
    if len(contexts) != 1:
        errors.append("turn_count")
    else:
        context = contexts[0]
        for name, wanted in (("model", "gpt-6-astra"), ("effort", "xhigh")):
            if context.get(name) != wanted:
                errors.append(name)
        if (
            not isinstance(context.get("sandbox_policy"), dict)
            or context["sandbox_policy"].get("type") != "read-only"
        ):
            errors.append("sandbox")
        if normalized(context.get("cwd", "")) != normalized(cwd):
            errors.append("turn_cwd")
    if (
        len(metas) != 1
        or metas[0].get("id") != thread_id
        or normalized(metas[0].get("cwd", "")) != normalized(cwd)
    ):
        errors.append("session_meta")
    if not isinstance(usage, dict) or not usage:
        errors.append("token_usage")
    elif any(
        not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v < 0
        for v in usage.values()
    ):
        errors.append("token_usage")
    if len(finals) != 1 or not finals[0].strip():
        errors.append("final_count_or_empty")
    return {
        "passed": not errors,
        "reasons": sorted(set(errors)),
        "answer": finals[0] if len(finals) == 1 else "",
        "tokens": {name: (usage or {}).get(name) for name in TOKEN_FIELDS}
        if isinstance(usage, dict)
        else {},
        "timing": timing,
    }


def script(value):
    counts = {"LATIN": 0, "CYRILLIC": 0}
    for char in value:
        if unicodedata.category(char).startswith("L"):
            name = unicodedata.name(char, "")
            for key in counts:
                counts[key] += key in name
    winner = None if counts["LATIN"] == counts["CYRILLIC"] else max(counts, key=counts.get)
    return {"counts": counts, "script": winner}


def language(question, answer):
    first, second = script(question), script(answer)
    return {
        "question_script": first,
        "answer_script": second,
        "match": first["script"] is not None and first["script"] == second["script"],
    }


def rollout_gate(raw, cwd, thread_id, job):
    """The same admission at collection and freeze, including malformed evidence."""
    try:
        result = gate(
            [json.loads(line.decode("utf-8")) for line in raw.split(b"\n") if line], cwd, thread_id
        )
    except (ValueError, TypeError, AttributeError):
        result = {
            "passed": False,
            "reasons": ["malformed_rollout"],
            "answer": "",
            "tokens": {},
            "timing": {},
        }
    if job.get("write") is not False:
        result["passed"] = False
        result["reasons"].append("job_write")
    return result


def process_tree(snapshot, cwd, tracked=()):
    """Select only roots naming the unique cwd, then creation-ordered descendants."""
    by_id = {p["pid"]: p for p in snapshot}
    selected = {
        p["pid"]
        for p in snapshot
        if str(cwd) in (p.get("command") or "") or any(same_process(p, old) for old in tracked)
    }
    depth = dict.fromkeys(selected, 0)
    changed = True
    while changed:
        changed = False
        for proc in snapshot:
            parent = by_id.get(proc["parent"])
            if (
                parent
                and parent["pid"] in selected
                and proc["pid"] not in selected
                and proc["created"] >= parent["created"]
            ):
                selected.add(proc["pid"])
                depth[proc["pid"]] = depth[parent["pid"]] + 1
                changed = True
    return [
        by_id[p]
        for p in sorted(selected, key=lambda p: (depth[p], by_id[p]["created"]), reverse=True)
    ]


def process_snapshot():
    """Keep CIM's DMTF precision alongside its FILETIME conversion."""
    c.require(os.name == "nt", "live companion cleanup requires Windows")
    command = "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); Add-Type -AssemblyName System.Management; ConvertTo-Json -Compress -InputObject @(Get-CimInstance Win32_Process | ForEach-Object { @{pid=[int]$_.ProcessId; parent=[int]$_.ParentProcessId; created=$_.CreationDate.ToFileTimeUtc(); created_dmtf=[System.Management.ManagementDateTimeConverter]::ToDmtfDateTime($_.CreationDate); command=$_.CommandLine} })"
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        timeout=30,
        check=True,
    )
    return json.loads(result.stdout.decode("utf-8-sig"))


def creation_quantum(proc):
    # DMTF defines the snapshot's fractional-second precision (six digits for
    # CIM datetime). Do not infer it from coincidental trailing zeroes in ticks:
    # doing so could widen the identity window and admit a reused PID.
    match = re.fullmatch(r"\d{14}\.(\d{1,7})[+-]\d{3}", proc["created_dmtf"])
    c.require(match is not None, "snapshot creation precision unavailable")
    return 10 ** (7 - len(match[1]))  # FILETIME has 10^7 ticks per second.


def process_kernel():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
    kernel.GetProcessTimes.argtypes = (
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    )
    kernel.TerminateProcess.argtypes = (ctypes.c_void_p, ctypes.c_uint)
    kernel.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    return kernel


class CleanupFailed(ValueError):
    def __init__(self, tree, stopped=0):
        super().__init__("owned process survived cleanup")
        self.tree = tree
        self.stopped = stopped


def same_process(first, second):
    quantum = max(creation_quantum(first), creation_quantum(second))
    return (
        first["pid"] == second["pid"]
        and first["created"] // quantum == second["created"] // quantum
    )


def cleanup(cwd, *, snapshot=None, kernel=None, tracked=()):
    """Terminate creation-verified handles, then prove the owned tree is gone."""
    snapshot = snapshot or process_snapshot
    current = snapshot()
    # A surviving child can lose its parent and never mention cwd itself.
    # Retain the original creation-bound tree for the next cleanup attempt.
    selected = process_tree(current, cwd, tracked)
    kernel = kernel if kernel is not None else process_kernel()
    stopped = 0
    deadline = time.monotonic() + 20
    for proc in selected:
        handle = kernel.OpenProcess(0x100001 | 0x1000, False, proc["pid"])
        if not handle:
            # An already exited process is fine; access refusal is not.
            c.require(ctypes.get_last_error() in (0, 87), "owned process inaccessible")
            continue
        try:
            times = [ctypes.c_ulonglong() for _ in range(4)]
            c.require(
                kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)),
                "process creation time unavailable",
            )
            quantum = creation_quantum(proc)
            if times[0].value // quantum != proc["created"] // quantum:
                continue  # PID reused; this is no longer the built tree.
            if kernel.WaitForSingleObject(handle, 0) == 0:
                continue
            c.require(kernel.TerminateProcess(handle, 1), "owned process termination failed")
            remaining = max(0, int((deadline - time.monotonic()) * 1000))
            if kernel.WaitForSingleObject(handle, remaining) != 0:
                raise TimeoutError("owned process stop timed out")
            stopped += 1
        finally:
            kernel.CloseHandle(handle)
    by_id = {proc["pid"]: proc for proc in selected}
    for proc in snapshot():
        previous = by_id.get(proc["pid"])
        if str(cwd) in (proc.get("command") or "") or (previous and same_process(previous, proc)):
            raise CleanupFailed(selected, stopped)
    return stopped


def rollout_complete(raw):
    """An unfinished last JSONL row or absent completion can still be in flight."""
    lines = [line for line in raw.split(b"\n") if line]
    complete = False
    for index, line in enumerate(lines):
        try:
            entry = json.loads(line.decode("utf-8"))
        except ValueError:
            # A malformed interior row is a permanent route failure.
            return index < len(lines) - 1
        if isinstance(entry, dict) and entry.get("type") == "event_msg":
            payload = entry.get("payload")
            if isinstance(payload, dict) and payload.get("type") == "task_complete":
                complete = True
    return complete


def infrastructure_message(record):
    # Inspect transport diagnostics, never model prose (which may discuss networks).
    fields = [record.get(k) for k in ("error", "message", "statusMessage")]
    nested = record.get("result")
    fields += [nested.get(k) for k in ("error", "stderr")] if isinstance(nested, dict) else []
    return bool(
        re.search(
            r"usage.?limit|rate.?limit|network|connection|quota|timed? out",
            json.dumps(fields),
            re.I,
        )
    )


def cleanup_failure(result, exc):
    result.update(
        kind="infrastructure",
        reason="cleanup_timeout"
        if isinstance(exc, (TimeoutError, subprocess.TimeoutExpired))
        else "cleanup_failure",
        cleanup_failed=True,
    )
    if isinstance(exc, CleanupFailed):
        result["cleanup_tree"] = exc.tree
        result["processes_stopped"] = result.get("processes_stopped", 0) + exc.stopped


class CompanionClient:
    """P2's companion route with an empty cwd, retained files and stricter admission."""

    def __init__(self, companion, codex_home, state_root, node="node"):
        self.companion, self.codex_home, self.state_root = map(
            Path, (companion, codex_home, state_root)
        )
        self.node = node
        self.precedent = c.load("scripts/p2_astra_reference.py", "ceiling_astra_precedent")
        # Reuse its client configuration; its grade() puts a prompt inside cwd and
        # deletes evidence, so the 5v transport must override that lifecycle.
        self.route = self.precedent.AstraCompanionClient(
            node, 300, codex_home=self.codex_home, state_root=self.state_root
        )

    def collect(self, folder, started, *, returncode=0, timed_out=False, elapsed=0):
        cwd = folder / "cwd"
        result = {
            "kind": "infrastructure",
            "reason": "companion_exit",
            "elapsed_s": elapsed,
            "timeout": timed_out,
            "processes_stopped": 0,
        }
        try:
            record = self.precedent.find_job_record(
                self.state_root, cwd, datetime.fromisoformat(started)
            )
            c.write(folder / "job.json", record)
            result.update(job_id=record.get("id"), thread_id=record.get("threadId"))
            thread = record.get("threadId")
            c.require(
                isinstance(thread, str) and re.fullmatch(r"[A-Za-z0-9-]+", thread), "missing thread"
            )
            rollouts = list((self.codex_home / "sessions").rglob(f"rollout-*-{thread}.jsonl"))
            c.require(len(rollouts) == 1, "rollout missing or ambiguous")
            raw = rollouts[0].read_bytes()
            for _ in range(4):
                if rollout_complete(raw):
                    break
                time.sleep(2.5)
                raw = rollouts[0].read_bytes()
            (folder / "rollout.jsonl").write_bytes(raw)
            result.update(rollout_file=rollouts[0].name, rollout_sha256=c.digest(raw))
            job_result = record.get("result")
            c.require(isinstance(job_result, dict), "job result missing")
            raw_output = job_result.get("rawOutput", "")
            c.require(isinstance(raw_output, str), "rawOutput type")
            result["raw_output_sha256"] = c.digest(raw_output)
            admitted = rollout_gate(raw, cwd, thread, record)
            result.update(
                gate=admitted,
                raw_output_mismatch=c.digest(admitted["answer"]) != c.digest(raw_output),
            )
            if (
                timed_out
                or returncode != 0
                or record.get("status") != "completed"
                or job_result.get("status") != 0
            ):
                diagnostics = {
                    "error": (folder / "stderr.bin").read_bytes().decode("utf-8", errors="replace")
                    if (folder / "stderr.bin").exists()
                    else ""
                }
                result["infrastructure_message"] = infrastructure_message(
                    record
                ) or infrastructure_message(diagnostics)
                result["reason"] = "task_timeout" if timed_out else "transport"
            elif not rollout_complete(raw):
                result["reason"] = "incomplete_rollout"
            else:
                if admitted["passed"]:
                    # Independently retain P2's model/effort/cwd/usage check.
                    try:
                        self.precedent.verify_rollout(self.codex_home, thread, cwd)
                        if raw_output.strip():
                            self.precedent.parse_job_record(record)
                    except ValueError as exc:
                        raise ValueError("precedent verification refused") from exc
                result.update(
                    kind="accepted" if admitted["passed"] else "route_failure",
                    reason="route_pass" if admitted["passed"] else "route_gate",
                    gate=admitted,
                    raw_output_mismatch=c.digest(admitted["answer"]) != c.digest(raw_output),
                )
        except (OSError, ValueError, KeyError, TypeError):
            result["reason"] = "record_or_rollout"
        finally:
            try:
                result["processes_stopped"] = cleanup(cwd)
            except (Exception, SystemExit) as exc:
                cleanup_failure(result, exc)
        c.write(folder / "outcome.json", result)
        return result

    def run(self, folder, timeout):
        launch = c.read(folder / "launch.json")
        cwd = folder / "cwd"
        c.require(cwd.is_dir() and not list(cwd.iterdir()), "attempt cwd is not empty")
        environment = os.environ.copy()
        environment.pop("CODEX_COMPANION_APP_SERVER_ENDPOINT", None)
        environment.update(CODEX_HOME=str(self.codex_home), CLAUDE_PLUGIN_DATA=str(self.state_root))
        start = time.monotonic()
        timed_out, returncode = False, -1
        try:
            with (
                (folder / "stdout.bin").open("wb") as stdout,
                (folder / "stderr.bin").open("wb") as stderr,
            ):
                process = subprocess.Popen(
                    [
                        self.node,
                        str(self.companion),
                        "task",
                        "--model",
                        "gpt-6-astra",
                        "--effort",
                        "xhigh",
                        "--cwd",
                        str(cwd),
                        "--prompt-file",
                        str(folder / "request/prompt.txt"),
                    ],
                    cwd=cwd,
                    env=environment,
                    stdout=stdout,
                    stderr=stderr,
                )
                # Keep the parent alive on timeout until cleanup builds its tree.
                returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        except OSError:
            pass
        transport = {
            "returncode": returncode,
            "timed_out": timed_out,
            "elapsed": time.monotonic() - start,
        }
        c.write(folder / "transport.json", transport)
        return self.collect(folder, launch["started"], **transport)

    def recover(self, folder):
        launch = c.read(folder / "launch.json")
        transport = (
            c.read(folder / "transport.json") if (folder / "transport.json").exists() else None
        )
        if transport is None:
            # No durable exit status: infrastructure, never silently accept a crashed call.
            # Wall time across a restart/sleep is not measured task time.
            transport = {
                "returncode": -1,
                "elapsed": 0,
                "timed_out": False,
            }
        # Never start a second task while an interrupted task/broker may remain.
        try:
            stopped = cleanup(folder / "cwd")
        except (Exception, SystemExit) as exc:
            result = {
                "elapsed_s": transport["elapsed"],
                "timeout": transport["timed_out"],
                "processes_stopped": 0,
            }
            cleanup_failure(result, exc)
            c.write(folder / "outcome.json", result)
            return result
        result = self.collect(folder, launch["started"], **transport)
        result["processes_stopped"] += stopped
        c.write(folder / "outcome.json", result)
        return result
