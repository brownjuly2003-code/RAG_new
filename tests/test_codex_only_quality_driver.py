"""Synthetic driver contracts, to be executed on macOS/Linux by the session.

No real CLI, product, database or external corpus is used. Native Windows checks
are deliberately a separate, opt-in laptop command.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess  # nosec B404 # Local synthetic Git repositories only.
import sys
import threading
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reports/codex-only-quality/tools"))

import quality_driver as driver  # noqa: E402
import stand_runtime as sr  # noqa: E402

cv = driver.cv


def put(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else cv.encoded(value))
    return path


def make_call(
    capture: Path,
    number: int,
    *,
    effort="xhigh",
    scenario="ok",
    active=None,
    offset=0.0,
    probe=False,
    model="gpt-6-astra",
) -> str:
    journal = driver.instruments(ROOT)[3]
    from llm.providers.codex import DISABLED_FEATURES

    if active is None:
        active = cv.read(capture / "active_case.json")
    folder = capture / "calls" / f"synthetic-{number:05d}"
    folder.mkdir(parents=True)
    question = "Synthetic question about a shipment?"
    prompt = (
        "Reply with exactly OK."
        if probe
        else "CONTEXT:\n[1 | source=synthetic]\nA synthetic fact.\n--------------------\n\nQUESTION:\n"
        + question
        + "\n\nWhen you rely on a fact, cite [1] for the first document in the context list, exactly."
    )
    if effort == "low":
        prompt = "A synthetic auxiliary instruction."
    stdin = (
        (ROOT / "llm/codex_wrapper.txt")
        .read_bytes()
        .replace(b"{prompt}", ("USER:\n" + prompt).encode())
    )
    output = [
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "OK" if probe else "Synthetic answer."},
        },
        {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
    ]
    if scenario == "usage":
        output = [{"type": "turn.failed", "error": {"message": "usage limit"}}]
    if scenario == "refusal":
        output.insert(0, {"type": "item.completed", "item": {"type": "command_execution"}})
    raw = b"".join(json.dumps(e).encode() + b"\n" for e in output)
    stamp = (
        datetime.now(timezone.utc).replace(microsecond=0)
        - timedelta(seconds=300)
        + timedelta(seconds=offset)
    )
    end = stamp + timedelta(seconds=0.25)
    argv = [
        "exec",
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "read-only",
        *(x for f in DISABLED_FEATURES for x in ("--disable", f)),
        "-m",
        model,
        "-c",
        "model_reasoning_effort=" + json.dumps(effort),
        "-C",
        "C:/synthetic",
        "-",
    ]
    put(folder / "stdin.bin", stdin)
    put(folder / "stdout.bin", raw)
    put(folder / "stderr.bin", b"")
    put(
        folder / "start.json",
        {
            "schema": journal.SCHEMA,
            "utc": stamp.isoformat(),
            "process_start_utc": stamp.isoformat(),
            "shim_pid": 10000 + number * 2,
            "command_line_tail": " exec ... -",
            "argv": argv,
            "cwd": "C:/synthetic",
            "stdin_length": len(stdin),
            "stdin_sha256": cv.digest(stdin),
            "active_case": json.dumps(active),
            "real_exe": "C:/synthetic/codex.exe",
            "real_exe_size": 10,
            "real_exe_mtime_utc": stamp.isoformat(),
            "environment_names": ["PATH"],
        },
    )
    put(folder / "spawned.json", {"child_pid": 10001 + number * 2, "utc": stamp.isoformat()})
    heartbeat = stamp + timedelta(seconds=178 if scenario == "timeout" else 0)
    put(folder / "alive.log", (heartbeat.isoformat() + "\n").encode())
    if scenario not in {"timeout", "drain"}:
        put(
            folder / "end.json",
            {
                "utc": end.isoformat(),
                "exit_code": 1 if scenario == "exit" else 0,
                "capture_ok": True,
                "stdout_length": len(raw),
                "stdout_sha256": cv.digest(raw),
                "stderr_length": 0,
                "stderr_sha256": cv.digest(b""),
            },
        )
    return folder.name


class FakeSystem:
    def __init__(self):
        self.processes: list[sr.Process] = []
        self.stopped: list[int] = []
        self.pair = (100.0, 100.0)
        self.sleep: list[bool] = []
        self.sleep_ok = True
        self.owners: list[int] = []

    def snapshot(self):
        return self.processes.copy()

    def alive(self, process):
        return any(p.pid == process.pid and p.created == process.created for p in self.processes)

    def terminate(self, process):
        if not self.alive(process):
            return False
        self.processes = [p for p in self.processes if p.pid != process.pid]
        self.owners = [pid for pid in self.owners if pid != process.pid]
        self.stopped.append(process.pid)
        return True

    def clock_pair(self):
        return self.pair

    def inhibit(self, enabled):
        self.sleep.append(enabled)
        return self.sleep_ok

    def listeners(self, port):
        return self.owners.copy()

    def launch(self, argv, cwd, log):
        parent = sr.Process(100 + len(self.stopped), 1, "python.exe", 1000 + len(self.stopped))
        child = sr.Process(
            parent.pid + 1, parent.pid, "python.exe", parent.created + 1, "python -m uvicorn"
        )
        self.processes.extend([parent, child])
        self.owners = [child.pid]
        return parent


class FakeRuntime(sr.Runtime):
    def __init__(self, config, folder, fixture):
        self.fixture = fixture
        super().__init__(config, folder, fixture.system, sr.HTTP(fixture.server.server_port))

    def preflight(self):
        pass  # The synthetic HTTP server intentionally owns its ephemeral port.

    def ensure(self, key):
        if self.stand and self.stand["key"] == key:
            return self.stand.get("cold", False)
        if self.stand:
            self.stop()
        self.stand = {"key": key, "cold": True, "processes": []}
        sr.atomic(self.path, self.stand)
        self.fixture.starts.append(key)
        return True

    def stop(self):
        if self.stand:
            self.fixture.stops.append(self.stand["key"])
        self.fixture.draining = False
        super().stop()

    def call_gone(self, call):
        return not self.fixture.draining

    def tickets(self, key, session_id):
        return {
            "count": 1,
            "rows": [{"id": "secret-ticket-id", "delivery_state": "pending", "status": "open"}],
        }

    def probe(self, key, path, ceiling):
        self.fixture.counter += 1
        if self.fixture.probe_scenario != "no_call":
            make_call(
                Path(self.config["capture_root"]),
                self.fixture.counter,
                probe=True,
                scenario=self.fixture.probe_scenario,
                model=self.fixture.models["xhigh"],
            )
        return {
            "result": {
                "text": self.fixture.probe_text,
                "provider": "codex",
                "model": self.fixture.models["xhigh"],
            },
            "error": "probe_worker_error"
            if self.fixture.probe_scenario == "worker_error"
            else None,
            "http_status": None,
            "elapsed_s": 0.1,
            "dispatch_utc": sr.utc(),
            "result_utc": sr.utc(),
        }


@pytest.fixture
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Siblings even when pytest's basetemp is inside the real checkout.
    repo = tmp_path / "repo"
    repo.mkdir()
    real_instruments = driver.instruments
    monkeypatch.setattr(driver, "instruments", lambda repo: real_instruments(ROOT))
    folder = tmp_path / "private"
    capture = folder / "capture"
    (capture / "calls").mkdir(parents=True)
    config: dict[str, Any] = {
        "capture_root": str(capture),
        "cw_home": str(folder / "cw"),
        "stands": {},
        "release": {"python": sys.executable, "root": str(folder / "release")},
    }
    for name in ("agent/graph.py", "api/routers/conversation.py"):
        put(Path(config["release"]["root"]) / name, (ROOT / name).read_bytes())
    put(folder / "cw/AGENTS.md", b"Synthetic rules.\n")
    packages = {
        key: [
            {"case_id": f"{key}-{i:03d}", "question": "Synthetic question about a shipment?"}
            for i in range(100)
        ]
        for key in cv.KEYS
    }
    orders = {key: [r["case_id"] for r in rows] for key, rows in packages.items()}
    providers = {
        "fast": {"provider": "codex", "model": "gpt-6-astra", "effort": "low", "timeout_sec": 60},
        "strong": {"provider": "codex", "model": "gpt-6-astra", "effort": "low", "timeout_sec": 60},
        "answer": {
            "provider": "codex",
            "model": "gpt-6-astra",
            "effort": "xhigh",
            "timeout_sec": 180,
        },
    }
    registration = {
        "providers": {k: providers for k in cv.KEYS},
        "graph_bound": {
            k: {
                "ceiling_sec": 420,
                "reachable": [{"target": "fast", "maximum": 2}, {"target": "answer", "maximum": 1}],
            }
            for k in cv.KEYS
        },
    }
    fixture = SimpleNamespace(
        config=config,
        registration=registration,
        private=folder,
        capture=capture,
        packages=packages,
        orders=orders,
        system=FakeSystem(),
        starts=[],
        stops=[],
        scenario="ok",
        counter=0,
        posts=[],
        logins=0,
        probe_text="OK",
        probe_scenario="ok",
        models={"low": "gpt-6-astra", "xhigh": "gpt-6-astra"},
        result_fields={},
        draining=False,
        reply="Synthetic answer about a shipment.",
        runtimes=[],
    )
    for key in cv.KEYS:
        auth = put(
            folder / f"{key}-auth.json",
            {"admin_username": "synthetic-admin", "admin_password": "synthetic-secret"},  # nosec B105 # Synthetic localhost test credentials.
        )
        config["stands"][key] = {
            "auth_file": str(auth),
            "tenant": "aircargo" if key == "aircargo" else "ext_" + key,
        }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, value, content="application/json", status=200):
            raw = value if isinstance(value, bytes) else json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", content)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self.send({"ready": True})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path == "/api/auth/login":
                fixture.logins += 1
                assert body == {"username": "synthetic-admin", "password": "synthetic-secret"}  # nosec B105 # Synthetic localhost test credentials.
                self.send({"access_token": "synthetic-token"})  # nosec B105 # Synthetic token accepted only by this fixture.
                return
            assert self.path == "/api/ask/stream"
            assert set(body) == {"question"}
            assert self.headers["Authorization"] == "Bearer synthetic-token"
            fixture.posts.append(body)
            scenario = fixture.scenario
            if scenario == "hung":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                time.sleep(0.3)
                return
            if scenario in {"http_error", "broken", "missing_result"}:
                raw = (
                    b"broken stream\n"
                    if scenario != "missing_result"
                    else b'data: {"type":"token","token":"synthetic"}\n\n'
                )
                self.send(raw, "text/event-stream", 503 if scenario == "http_error" else 200)
                return
            if scenario not in {"human", "outage"}:
                efforts = (
                    ["low", "low", "xhigh"] if scenario in {"ok", "overlap", "many"} else ["xhigh"]
                )
                if scenario == "many":
                    efforts.insert(0, "low")
                for index, effort in enumerate(efforts):
                    fixture.counter += 1
                    make_call(
                        capture,
                        fixture.counter,
                        effort=effort,
                        scenario=scenario,
                        offset=0 if scenario == "overlap" else index,
                        model=fixture.models[effort],
                    )
            if scenario == "drain":
                fixture.draining = True
            result = {
                "type": "result",
                "answer": fixture.reply,
                "route": "human" if scenario in {"human", "outage"} else "auto",
                "sources": [{"source": "synthetic"}],
                "citations": [],
                "session_id": "secret-session-id",
                "trace_id": "secret-trace-id",
                "answer_provider": "codex",
                "answer_model": "gpt-6-astra",
                "quality_score": None,
            }
            if scenario in {"usage", "refusal", "outage"}:
                result.update(
                    answer=cv.constant(
                        Path(config["release"]["root"]) / "agent/graph.py",
                        "_GENERATION_PROVIDER_FAILURE_ANSWER",
                    ),
                    answer_provider=None,
                )
            result.update(fixture.result_fields)
            self.send(("data: " + json.dumps(result) + "\n\n").encode(), "text/event-stream")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    fixture.server = server
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(driver, "admit_chunk", lambda args, repo: (config, registration))
    monkeypatch.setattr(driver, "load_packages", lambda repo, config: (packages, orders))

    def args(command="run", **kwargs):
        return SimpleNamespace(
            command=command,
            private=folder,
            records=tmp_path / "public",
            series="synthetic",
            config=folder / "config.json",
            budget=kwargs.pop("budget", 1080),
            key=kwargs.pop("key", "wixqa"),
            step=kwargs.pop("step", 1),
            resume_infrastructure=kwargs.pop("resume_infrastructure", False),
            **kwargs,
        )

    def factory(config, target):
        runtime = FakeRuntime(config, target, fixture)
        fixture.runtimes.append(runtime)
        return runtime

    def chunk(command="run", **kwargs):
        options = args(command, **kwargs)
        return driver.Chunk(
            options,
            repo,
            config,
            registration,
            factory(config, folder / options.series),
            time.monotonic(),
        )

    fixture.args, fixture.factory, fixture.chunk = args, factory, chunk
    fixture.run = lambda command="run", **kw: driver.request_chunk(
        args(command, **kw), repo=repo, runtime_factory=factory
    )
    fixture.state = lambda: cv.read(folder / "synthetic/state.json")
    yield fixture
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def ready_run(rig):
    chunk = rig.chunk()
    chunk.state.update(probe=True, pilot_passed=True, pilot_step=20)
    chunk.save()
    return chunk


def test_probe_accept_reject_and_no_repeat(rig):
    assert rig.run("probe") == 0
    assert rig.state()["probe"] is True
    assert rig.run("probe") == 0
    assert rig.counter == 1
    assert not rig.starts


def test_probe_reject(rig):
    rig.probe_text = "wrong"
    assert rig.run("probe") == 2
    assert rig.run("probe") == 2
    assert rig.counter == 1


@pytest.mark.parametrize("scenario", ["no_call", "worker_error", "exit", "timeout", "refusal"])
def test_probe_infrastructure_is_resumable(rig, scenario):
    rig.probe_scenario = scenario
    assert rig.run("probe") == 5
    assert rig.state()["cases"]["probe:probe"]["status"] == "pending"
    assert all(s["code"] == 5 for s in rig.state()["stops"])
    rig.probe_scenario = "ok"
    assert rig.run("probe") == 5
    assert rig.run("probe", resume_infrastructure=True) == 0
    assert rig.state()["probe"] and rig.state()["resumes"]


def test_probe_resume_flag_cannot_resolve_rule_stop(rig):
    args = driver.parser().parse_args(
        [
            "probe",
            "--config",
            "unused",
            "--private",
            "unused",
            "--records",
            "unused",
            "--series",
            "synthetic",
            "--resume-infrastructure",
        ]
    )
    assert args.resume_infrastructure
    rig.probe_text = "wrong"
    assert rig.run("probe") == 2
    assert rig.run("probe", resume_infrastructure=True) == 2
    assert not rig.state()["resumes"]


def test_redundant_probe_preserves_warm_stand(rig):
    chunk = ready_run(rig)
    chunk.runtime.ensure("wixqa")
    assert rig.run("probe") == 0
    assert not rig.stops
    assert not rig.posts


@pytest.mark.parametrize("code", [2, 3, 5])
def test_refused_chunk_records_agents_observation(rig, code):
    chunk = ready_run(rig)
    if code == 3:
        chunk.state["retry_at"] = (datetime.now(timezone.utc) + timedelta(seconds=300)).isoformat()
    else:
        driver.add_stop(chunk.state, code, "synthetic_stop")
    chunk.save()
    assert rig.run() == code
    put(Path(rig.config["cw_home"]) / "AGENTS.md", b"Changed synthetic rules.\n")
    assert rig.run() == code
    observations = rig.state()["chunks"]
    assert len(observations) == 2 and observations[-1]["changed"]
    assert observations[-1]["sleep_suspend_events"] == []
    assert not rig.posts


def test_watch_stop_survives_outcome_replay(rig, monkeypatch):
    chunk = ready_run(rig)

    def stopped(*args):
        raise sr.Stop(2, "outside_codex")

    monkeypatch.setattr(chunk.runtime, "ask", stopped)
    with pytest.raises(sr.Stop) as failure:
        chunk.one("wixqa", rig.packages["wixqa"][0], False)
    assert failure.value.code == 2
    chunk.state = driver.initial_state(rig.registration)
    chunk.recover()
    assert driver.state_gate(chunk.state, True) == 2
    assert any(s["reason"] == "outside_codex" for s in chunk.state["stops"])


def test_drain_includes_calls_created_while_waiting(rig, monkeypatch):
    chunk = rig.chunk()
    put(rig.capture / "active_case.json", {"key": "wixqa", "case_id": "synthetic"})
    make_call(rig.capture, 1, effort="low")
    names = chunk.names()
    visited = []

    def gone(call):
        visited.append(call.folder.name)
        if len(visited) == 1:
            make_call(rig.capture, 2, effort="low", offset=1)
            return False
        return True

    monkeypatch.setattr(chunk.runtime, "call_gone", gone)
    chunk.drain(names, before=set())
    assert len(names) == 2 and names == set(visited)


def test_pilot_selection_and_step_order(rig):
    chunk = rig.chunk("pilot", step=5)
    assert chunk.selected == driver.instruments(ROOT)[2].pilot(rig.packages)
    assert [k for k, _ in chunk.selected] == ["wixqa"] * 7 + ["conditionalqa"] * 7 + [
        "aircargo"
    ] * 6
    chunk.state["probe"] = True
    with pytest.raises(cv.Refusal, match="earlier"):
        chunk.work()
    assert not rig.posts


def test_language_mismatch_fails_pilot(rig):
    rig.reply = "Это синтетический ответ о доставке груза."
    chunk = rig.chunk("pilot")
    chunk.state["probe"] = True
    chunk.save()
    assert rig.run("pilot") == 2
    assert any(s["reason"] == "pilot_failed" for s in rig.state()["stops"])


@pytest.mark.parametrize(
    "scenario,classification",
    [
        ("ok", "accepted"),
        ("human", "infrastructure"),
        ("timeout", "product_failure"),
        ("exit", "infrastructure"),
        ("refusal", "counted_out"),
    ],
)
def test_attempt_classes(rig, scenario, classification):
    rig.scenario = scenario
    chunk = ready_run(rig)
    if scenario == "refusal":
        with pytest.raises(sr.Stop) as stopped:
            chunk.one("wixqa", rig.packages["wixqa"][0], False)
        assert stopped.value.code == 3
    else:
        chunk.one("wixqa", rig.packages["wixqa"][0], False)
    row = chunk.state["cases"]["wixqa:wixqa-000"]
    attempt = row["attempts"][0]
    assert attempt["classification"] == classification
    assert row["status"] == ("pending" if classification == "infrastructure" else classification)
    if scenario == "ok":
        assert [c["effort"] for c in attempt["calls"]] == ["low", "low", "xhigh"]
        assert attempt["answer_prompt_sha256"]
    if scenario == "human":
        assert not attempt["audited_absence"] and not attempt["calls"]
    if scenario == "timeout":
        assert list(rig.capture.glob("calls/*/end.driver.json"))


@pytest.mark.parametrize("provider", [None, "codex"])
def test_outage_without_calls_has_backoff_from_release_text(rig, provider):
    graph = Path(rig.config["release"]["root"]) / "agent/graph.py"
    put(graph, b'_GENERATION_PROVIDER_FAILURE_ANSWER = "Synthetic pinned release outage"\n')
    rig.scenario = "outage"
    rig.result_fields = {"answer_provider": provider}
    chunk = ready_run(rig)
    with pytest.raises(sr.Stop) as stopped:
        chunk.one("wixqa", rig.packages["wixqa"][0], False)
    assert stopped.value.code == 3
    attempt = chunk.state["cases"]["wixqa:wixqa-000"]["attempts"][0]
    assert attempt["classification"] == "infrastructure" and not attempt["audited_absence"]
    assert datetime.fromisoformat(attempt["retry_at"]) == (
        datetime.fromisoformat(attempt["result_utc"]) + timedelta(seconds=300)
    )


def test_product_timeout_with_failure_text_is_terminal_with_backoff(rig):
    failure = cv.constant(
        Path(rig.config["release"]["root"]) / "agent/graph.py",
        "_GENERATION_PROVIDER_FAILURE_ANSWER",
    )
    rig.scenario = "timeout"
    rig.result_fields = {"answer": failure, "answer_provider": None, "route": "human"}
    chunk = ready_run(rig)
    with pytest.raises(sr.Stop) as stopped:
        chunk.one("wixqa", rig.packages["wixqa"][0], False)
    assert stopped.value.code == 3
    row = chunk.state["cases"]["wixqa:wixqa-000"]
    attempt = row["attempts"][0]
    assert attempt["classification"] == row["status"] == "product_failure"
    assert datetime.fromisoformat(attempt["retry_at"]) == (
        datetime.fromisoformat(attempt["result_utc"]) + timedelta(seconds=300)
    )


def test_reviewed_early_handover_contract_is_source_pinned():
    driver.review_handover_sources(ROOT)
    # The current graph always reaches generate even with zero/one document.
    assert not driver.EARLY_HANDOVER_PATHS
    assert set(driver.EARLY_HANDOVER_REVIEW) == {"no_context", "fewer_than_two_documents"}


@pytest.mark.parametrize("name", ["agent/graph.py", "api/routers/conversation.py"])
def test_handover_source_change_requires_review(rig, name):
    release = Path(rig.config["release"]["root"])
    path = release / name
    put(path, path.read_bytes() + b"\n# Changed contract\n")
    with pytest.raises(cv.Refusal, match="handover"):
        driver.review_handover_sources(release)


def test_audited_absence_requires_an_explicit_reviewed_path(rig, monkeypatch):
    # Synthetic future contract exercises the allowlist, not an invented product path.
    fields = {
        "answer_source": "graph",
        "generation_source": "graph_only",
        "graph_nodes": ["synthetic_early_handover"],
        "answer_provider": None,
    }
    monkeypatch.setattr(driver, "EARLY_HANDOVER_PATHS", {"synthetic": fields})
    rig.scenario = "human"
    rig.result_fields = fields
    chunk = ready_run(rig)
    chunk.one("wixqa", rig.packages["wixqa"][0], False)
    attempt = chunk.state["cases"]["wixqa:wixqa-000"]["attempts"][0]
    assert attempt["classification"] == "accepted" and attempt["audited_absence"]
    assert attempt["early_handover"] == "synthetic"
    assert attempt["result"]["graph_nodes"] == fields["graph_nodes"]


@pytest.mark.parametrize("count", [0, 1])
def test_no_context_or_one_document_does_not_prove_early_handover(rig, count):
    rig.scenario = "human"
    rig.result_fields = {
        "sources": [{}] * count,
        "answer_source": "graph",
        "generation_source": "graph_only",
        "graph_nodes": ["retrieve", "grade_docs", "generate", "evaluate", "route_or_retry"],
        "answer_provider": None,
    }
    chunk = ready_run(rig)
    chunk.one("wixqa", rig.packages["wixqa"][0], False)
    attempt = chunk.state["cases"]["wixqa:wixqa-000"]["attempts"][0]
    assert attempt["classification"] == "infrastructure" and not attempt["audited_absence"]


@pytest.mark.parametrize("effort", ["low", "xhigh"])
def test_wrong_model_per_target_is_rule_stop(rig, effort):
    rig.models[effort] = "wrong-target-model"
    chunk = ready_run(rig)
    with pytest.raises(sr.Stop) as stopped:
        chunk.one("wixqa", rig.packages["wixqa"][0], False)
    assert stopped.value.code == 2


@pytest.mark.parametrize("target", ["fast", "strong"])
def test_models_are_taken_from_registered_targets(rig, target):
    providers = rig.registration["providers"]["wixqa"]
    providers["fast"]["model"] = "registered-fast"
    providers["strong"]["model"] = "registered-strong"
    providers["answer"]["model"] = "registered-answer"
    rig.models = {"low": providers[target]["model"], "xhigh": "registered-answer"}
    assert rig.run("probe") == 0
    chunk = ready_run(rig)
    chunk.one("wixqa", rig.packages["wixqa"][0], False)
    assert chunk.state["cases"]["wixqa:wixqa-000"]["status"] == "accepted"


def test_usage_backoff_survives_restart(rig):
    rig.scenario = "usage"
    chunk = ready_run(rig)
    with pytest.raises(sr.Stop) as stopped:
        chunk.one("wixqa", rig.packages["wixqa"][0], False)
    assert stopped.value.code == 3
    assert chunk.state["retry_at"]
    assert rig.run() == 3
    assert len(rig.posts) == 1
    assert rig.state()["cases"]["wixqa:wixqa-000"]["status"] == "pending"


def test_three_infrastructure_attempts_across_questions(rig):
    rig.scenario = "exit"
    chunk = ready_run(rig)
    chunk.one("wixqa", rig.packages["wixqa"][0], False)
    chunk.one("wixqa", rig.packages["wixqa"][1], False)
    with pytest.raises(sr.Stop) as stopped:
        chunk.one("conditionalqa", rig.packages["conditionalqa"][0], False)
    assert stopped.value.code == 5
    assert chunk.state["infrastructure_streak"] == 3


@pytest.mark.parametrize("scenario", ["overlap", "many"])
def test_capture_rule_stops(rig, scenario):
    rig.scenario = scenario
    chunk = ready_run(rig)
    with pytest.raises(sr.Stop) as stopped:
        chunk.one("wixqa", rig.packages["wixqa"][0], False)
    assert stopped.value.code == 2


def test_call_outside_question_refuses_before_post(rig):
    make_call(rig.capture, 1, active={"key": "wixqa", "case_id": "outside"})
    chunk = ready_run(rig)
    with pytest.raises(sr.Stop, match="call_outside_question"):
        chunk.one("wixqa", rig.packages["wixqa"][0], False)
    assert not rig.posts


def test_hung_stand_and_drain_timeout(rig):
    rig.scenario = "hung"
    chunk = ready_run(rig)
    chunk.ceiling_override = 0.05
    with pytest.raises(sr.Stop) as stopped:
        chunk.one("wixqa", rig.packages["wixqa"][0], False)
    assert stopped.value.code == 5
    assert not chunk.runtime.stand
    assert rig.stops == ["wixqa"]


def test_drain_timeout_writes_driver_end(rig):
    rig.scenario = "drain"
    chunk = ready_run(rig)
    chunk.drain_seconds = 0.01
    with pytest.raises(sr.Stop) as stopped:
        chunk.one("wixqa", rig.packages["wixqa"][0], False)
    assert stopped.value.code == 5
    assert list(rig.capture.glob("calls/*/end.driver.json"))
    assert not chunk.runtime.stand


def test_budget_leaves_stand_and_key_switch_stops(rig):
    chunk = ready_run(rig)
    chunk.one("wixqa", rig.packages["wixqa"][0], False)
    chunk.args.budget = 1
    with pytest.raises(sr.Stop) as stopped:
        chunk.one("wixqa", rig.packages["wixqa"][1], False)
    assert stopped.value.code == 3
    assert chunk.runtime.stand["key"] == "wixqa"
    chunk.args.budget = 1080
    chunk.one("aircargo", rig.packages["aircargo"][0], False)
    assert rig.stops == ["wixqa"]


def test_restart_skips_terminal_and_replays_outcome_once(rig):
    chunk = ready_run(rig)
    before = copy.deepcopy(chunk.state)
    chunk.one("wixqa", rig.packages["wixqa"][0], False)
    original = copy.deepcopy(chunk.state)
    sr.atomic(chunk.folder / "state.json", before)  # Crash after outcome, before state replace.
    restarted = rig.chunk()
    restarted.recover()
    restarted.one("wixqa", rig.packages["wixqa"][0], False)
    restarted.recover()
    assert restarted.state["cases"] == original["cases"]
    assert restarted.state["remaining_seconds"] == original["remaining_seconds"]
    assert len(rig.posts) == 1


@pytest.mark.parametrize(
    "pilot,field,limit", [(True, "pilot_seconds", 3600), (False, "remaining_seconds", 50400)]
)
def test_clock_persists_and_refuses_full_ceiling(rig, pilot, field, limit):
    chunk = ready_run(rig)
    chunk.state[field] = limit - 419
    chunk.save()
    restarted = rig.chunk()
    with pytest.raises(sr.Stop, match="request_clock_limit") as stopped:
        restarted.one("wixqa", rig.packages["wixqa"][0], pilot)
    assert stopped.value.code == 2
    assert not rig.posts


def test_public_records_are_hash_only(rig):
    chunk = ready_run(rig)
    chunk.one("wixqa", rig.packages["wixqa"][0], False)
    chunk.public_records()
    for path in chunk.public.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "Synthetic question" not in text
        assert "Synthetic answer" not in text
        assert "secret-session-id" not in text and "secret-ticket-id" not in text
        assert str(rig.private) not in text
        driver.instruments(ROOT)[0].public_guard(json.loads(text))


@pytest.mark.parametrize("scenario", ["http_error", "broken", "missing_result"])
def test_transport_failures_stay_pending(rig, scenario):
    rig.scenario = scenario
    chunk = ready_run(rig)
    chunk.one("wixqa", rig.packages["wixqa"][0], False)
    row = chunk.state["cases"]["wixqa:wixqa-000"]
    assert row["status"] == "pending"
    assert row["attempts"][0]["classification"] == "infrastructure"


def test_persisted_stops_and_resume():
    state = driver.initial_state({})
    driver.add_stop(state, 5, "failure")
    assert driver.state_gate(state, False) == 5
    assert driver.state_gate(state, True) == 0
    assert len(state["resumes"]) == 1 and state["stops"][0]["resolved"]
    driver.add_stop(state, 5, "new_failure")
    driver.add_stop(state, 2, "rule")
    assert driver.state_gate(state, True) == 2
    assert not state["stops"][1].get("resolved")


@pytest.mark.parametrize("event,code", [("ollama", 2), ("suspend", 5), ("product", 2)])
def test_native_watch_with_fake(event, code, tmp_path):
    system = FakeSystem()
    system.processes = [sr.Process(10, 1, "codex.exe", 100)]  # Pre-existing: never killed.
    watch = sr.Watch(system, tmp_path / "processes.jsonl", lambda: [])
    watch.tick()
    watch.check()
    if event == "suspend":
        system.pair = (140, 102)
    else:
        image = {"codex": "codex.exe", "ollama": "ollama-runner.exe", "product": "python.exe"}[
            event
        ]
        system.processes.append(
            sr.Process(
                11, 1, image, 101, "python deploy/windows/start.py" if event == "product" else ""
            )
        )
    watch.tick()
    with pytest.raises(sr.Stop) as stopped:
        watch.check()
    assert stopped.value.code == code
    assert not system.stopped


def test_outside_codex_is_recorded_once_not_stopped(tmp_path):
    # Amended after attempt-03: another session's Codex never passes the shim.
    system = FakeSystem()
    system.processes = [sr.Process(10, 1, "codex.exe", 100)]  # Pre-existing: baseline.
    watch = sr.Watch(system, tmp_path / "processes.jsonl", lambda: [])
    watch.tick()
    system.processes.append(sr.Process(11, 1, "codex.exe", 101))
    watch.tick()
    watch.tick()
    watch.check()
    events = [e for e in watch.events if e["kind"] == "outside_codex"]
    assert [(e["pid"], e["created"]) for e in events] == [(11, 101)]
    assert not system.stopped


@pytest.mark.parametrize("ender", ["shim", "driver", None])
def test_finished_shim_does_not_claim_a_later_orphan_of_its_reused_pid(rig, ender):
    # attempt-03: an exited process reused shim PID 42; its live orphan made drain time out.
    start, finished = "2026-11-04T15:00:00.0000000Z", "2026-11-04T15:01:00.0000000Z"
    runtime = sr.Runtime(rig.config, rig.private / "native", rig.system)
    orphan = sr.Process(77, 42, "sh.exe", sr.filetime("2026-11-04T18:00:00.0000000Z"))
    child = sr.Process(78, 42, "codex.exe", sr.filetime("2026-11-04T15:00:01.0000000Z"))
    rig.system.processes = [orphan]
    call = SimpleNamespace(
        start={"shim_pid": 42, "process_start_utc": start},
        process_started=True,
        spawned=None,
        end={"utc": finished} if ender == "shim" else None,
        driver_end={"verified_exit_utc": finished} if ender == "driver" else None,
    )
    assert runtime.call_gone(call) is (ender is not None)
    rig.system.processes = [orphan, child]  # A real child outliving its shim stays live.
    assert not runtime.call_gone(call)


@pytest.mark.parametrize("event", ["ollama", "product", "listener"])
def test_initial_process_conditions_refuse_without_state_stop(rig, event):
    ready_run(rig)
    if event == "listener":
        rig.system.owners = [42]
    else:
        rig.system.processes = [
            sr.Process(
                42,
                1,
                "ollama.exe" if event == "ollama" else "python.exe",
                100,
                "python D:/foreign/deploy/windows/start.py",
            )
        ]
    assert rig.run() == 1
    state = rig.state()
    assert not state["stops"] and not rig.posts
    observation = state["chunks"][-1]
    assert observation["exit_code"] == 1 and observation["refusal_reason"]
    assert observation["ollama_observations"] == (1 if event == "ollama" else 0)


def test_unrelated_uvicorn_is_ignored(tmp_path):
    system = FakeSystem()
    system.processes = [sr.Process(42, 1, "python.exe", 100, "python -m uvicorn other.app:app")]
    watch = sr.Watch(system, tmp_path / "processes.jsonl", lambda: [])
    watch.tick()
    watch.check()
    system.processes.append(replace(system.processes[0], pid=43, created=101))
    watch.tick()
    watch.check()


def test_listener_appearing_after_initial_snapshot_is_rule_stop(tmp_path):
    system = FakeSystem()
    watch = sr.Watch(system, tmp_path / "processes.jsonl", lambda: [])
    watch.tick()
    system.owners = [42]
    watch.tick()
    with pytest.raises(sr.Stop) as stopped:
        watch.check()
    assert stopped.value.code == 2


def test_redirector_tree_listener_and_retained_stand(rig, monkeypatch):
    runtime = sr.Runtime(rig.config, rig.private / "native", rig.system)
    parent = sr.Process(100, 1, "python.exe", 1000)
    child = sr.Process(101, 100, "python.exe", 1001)
    redirector = sr.Process(102, 101, "python.exe", 1002)
    listener = sr.Process(103, 102, "python.exe", 1003)
    rig.system.processes = [parent, child, redirector, listener]
    rig.system.owners = [listener.pid]
    runtime.stand = {"key": "wixqa", "cold": False, "processes": [parent.record()]}
    monkeypatch.setattr(sr, "port_taken", lambda port: True)
    monkeypatch.setattr(runtime.http, "ready", lambda: True)
    runtime.preflight()
    assert runtime.ensure("wixqa") is False
    assert runtime.roots() == [parent]
    assert runtime.stand["processes"] == [parent.record(), listener.record()]
    runtime.stop()
    assert rig.system.stopped == [103, 102, 101, 100]


def test_foreign_listener_refuses_even_with_recorded_launcher(rig, monkeypatch):
    runtime = sr.Runtime(rig.config, rig.private / "native", rig.system)
    parent = sr.Process(100, 1, "python.exe", 1000)
    rig.system.processes = [parent, sr.Process(103, 1, "python.exe", 1003)]
    rig.system.owners = [103]
    runtime.stand = {"key": "wixqa", "processes": [parent.record()]}
    monkeypatch.setattr(sr, "port_taken", lambda port: True)
    with pytest.raises(sr.Stop) as stopped:
        runtime.preflight()
    assert stopped.value.code == 1
    assert not rig.system.stopped


def test_listener_ancestry_combines_observed_and_fresh_snapshot(rig, monkeypatch):
    runtime = sr.Runtime(rig.config, rig.private / "native", rig.system)
    launcher = sr.Process(100, 1, "python.exe", 1000)
    intermediate = sr.Process(101, 100, "python.exe", 1001)
    listener = sr.Process(102, 101, "python.exe", 1002)
    runtime.stand = {"key": "wixqa", "processes": [launcher.record()]}
    runtime.watch.observed[(intermediate.pid, intermediate.created)] = intermediate
    rig.system.processes = [launcher, listener]
    rig.system.owners = [listener.pid]
    monkeypatch.setattr(sr, "port_taken", lambda port: True)
    runtime.preflight()
    assert runtime.listener_processes() == [listener]


def test_listener_with_reused_launcher_pid_is_not_owned(rig, monkeypatch):
    runtime = sr.Runtime(rig.config, rig.private / "native", rig.system)
    launcher = sr.Process(100, 1, "python.exe", 1000)
    runtime.stand = {"key": "wixqa", "processes": [launcher.record()]}
    rig.system.processes = [
        replace(launcher, created=2000),
        sr.Process(101, 100, "python.exe", 2001),
    ]
    rig.system.owners = [101]
    monkeypatch.setattr(sr, "port_taken", lambda port: True)
    with pytest.raises(sr.Stop) as stopped:
        runtime.preflight()
    assert stopped.value.code == 1


@pytest.mark.parametrize("multiple", [False, True])
def test_ensure_records_descendant_listener_or_infrastructure(rig, monkeypatch, multiple):
    runtime = sr.Runtime(rig.config, rig.private / "native", rig.system)
    rig.config["stands"]["wixqa"].update(app=str(rig.private / "app"), env="synthetic.env")
    launch = rig.system.launch

    def redirected(argv, cwd, log):
        parent = launch(argv, cwd, log)
        rig.system.processes.append(sr.Process(102, 100 if multiple else 101, "python.exe", 1002))
        rig.system.owners = [102]
        return parent

    monkeypatch.setattr(rig.system, "launch", redirected)
    monkeypatch.setattr(sr, "port_taken", lambda port: bool(rig.system.processes))
    monkeypatch.setattr(runtime.http, "ready", lambda: True)
    if multiple:
        with pytest.raises(sr.Stop) as stopped:
            runtime.ensure("wixqa")
        assert stopped.value.code == 5
    else:
        assert runtime.ensure("wixqa")
        assert [p["pid"] for p in runtime.stand["processes"]] == [100, 102]


@pytest.mark.parametrize("ticks", [0, -1, 1, -10000, 10000, 10001])
def test_shim_identity_tolerates_only_one_millisecond(rig, ticks):
    stamp = "2026-11-04T10:00:00.1234567Z"
    created = sr.filetime(stamp)
    runtime = sr.Runtime(rig.config, rig.private / "native", rig.system)
    rig.system.processes = [sr.Process(42, 1, "capture_shim.exe", created + ticks)]
    call = SimpleNamespace(
        start={"shim_pid": 42, "process_start_utc": stamp}, process_started=True, spawned=None
    )
    assert runtime.call_gone(call) is (abs(ticks) > 10000)
    differences = [e for e in runtime.watch.events if e["kind"] == "shim_creation_delta"]
    assert bool(differences) is (0 < abs(ticks) <= 10000)
    if differences:
        assert differences[0]["delta_ticks"] == ticks


def test_shim_uses_live_snapshot_before_historical_timestamp(rig):
    stamp = "2026-11-04T10:00:00.1234567Z"
    created = sr.filetime(stamp)
    runtime = sr.Runtime(rig.config, rig.private / "native", rig.system)
    old = sr.Process(42, 1, "capture_shim.exe", created)
    runtime.watch.observed[(42, created)] = old
    rig.system.processes = [replace(old, created=created + 1)]
    call = SimpleNamespace(
        start={"shim_pid": 42, "process_start_utc": stamp}, process_started=True, spawned=None
    )
    assert not runtime.call_gone(call)


def test_shim_filetime_preserves_seventh_fractional_digit():
    assert sr.filetime("1601-01-01T00:00:00.0000001Z") == 1
    assert (
        sr.filetime("2026-11-04T10:00:00.1234567Z") - sr.filetime("2026-11-04T10:00:00.1234560Z")
        == 7
    )


def test_verified_tree_leaf_first_and_reused_pid():
    system = FakeSystem()
    parent = sr.Process(1, 0, "python.exe", 100)
    child = sr.Process(2, 1, "python.exe", 101)
    grandchild = sr.Process(3, 2, "codex.exe", 102)
    unrelated = sr.Process(4, 1, "codex.exe", 99)
    system.processes = [parent, child, grandchild, unrelated]
    assert not system.terminate(replace(parent, created=1))
    assert sr.stop_tree(system, [parent]) == [3, 2, 1]
    assert system.processes == [unrelated]


def test_reused_root_does_not_claim_new_children():
    system = FakeSystem()
    old = sr.Process(1, 0, "python.exe", 100)
    system.processes = [replace(old, created=200), sr.Process(2, 1, "python.exe", 201)]
    assert sr.stop_tree(system, [old]) == []
    assert len(system.processes) == 2


def test_ollama_is_observed_not_terminated():
    system = FakeSystem()
    parent = sr.Process(1, 0, "python.exe", 100)
    ollama = sr.Process(2, 1, "ollama.exe", 101)
    system.processes = [parent, ollama]
    assert sr.stop_tree(system, [parent]) == [1]
    assert system.processes == [ollama]


def test_unknown_listener_and_sleep_failure(rig, monkeypatch):
    runtime = sr.Runtime(
        rig.config, rig.private / "synthetic", rig.system, sr.HTTP(rig.server.server_port)
    )
    with pytest.raises(sr.Stop) as refused:
        runtime.preflight()
    assert refused.value.code == 1
    rig.system.sleep_ok = False
    with pytest.raises(sr.Stop) as failed:
        runtime.begin()
    assert failed.value.code == 5


def test_counted_out_includes_product_failure(rig):
    chunk = ready_run(rig)
    rig.scenario = "timeout"
    for i in range(5):
        chunk.one("wixqa", rig.packages["wixqa"][i], False)
    with pytest.raises(sr.Stop) as stopped:
        chunk.one("wixqa", rig.packages["wixqa"][5], False)
    assert stopped.value.code == 2
    assert any(s["reason"] == "counted_out_limit" for s in chunk.state["stops"])


def test_resume_pending_pilot_before_nonpilot(rig):
    chunk = rig.chunk("pilot", step=1)
    chunk.state.update(probe=True, pilot_target=1)
    driver.add_stop(chunk.state, 5, "diagnose_first")
    chunk.save()
    assert rig.run("run", key="wixqa") == 5
    assert not rig.posts
    assert rig.run("run", key="wixqa", resume_infrastructure=True) == 0
    state = rig.state()
    assert state["pilot_step"] == 1 and not state["pilot_passed"]
    assert len(rig.posts) == 1
    assert state["resumes"]


def test_full_pilot_uses_fixed_forecast_and_retains_cases(rig):
    chunk = rig.chunk("pilot", step=20)
    chunk.state.update(probe=True, pilot_step=5)
    assert chunk.work() == 0
    assert chunk.state["pilot_passed"]
    assert "forecast" not in chunk.state
    assert len(rig.posts) == 20
    assert rig.starts == list(cv.KEYS)
    assert rig.stops == list(cv.KEYS[:2])


def test_passed_pilot_keeps_stand_between_same_key_steps(rig):
    chunk = rig.chunk("pilot")
    chunk.state["probe"] = True
    chunk.save()
    assert rig.run("pilot", step=1) == 0
    assert rig.run("pilot", step=5) == 0
    assert rig.starts == ["wixqa"] and not rig.stops
    assert len(rig.posts) == 5
    assert rig.run("pilot", step=20) == 0
    assert rig.starts == list(cv.KEYS) and rig.stops == list(cv.KEYS[:2])


def test_completed_run_stops_its_stand(rig):
    chunk = ready_run(rig)
    for cid in rig.orders["wixqa"][:-1]:
        chunk.state["cases"]["wixqa:" + cid] = {
            "key": "wixqa",
            "case_id": cid,
            "status": "accepted",
            "attempts": [],
        }
    chunk.save()
    assert rig.run() == 0
    assert rig.stops == ["wixqa"]


@pytest.fixture
def admission(tmp_path, monkeypatch):
    repo, private = tmp_path / "repo", tmp_path / "private"
    repo.mkdir()
    records = repo / "reports/codex-only-quality"
    config = {
        "copy_receipt": str(put(private / "copy.json", {})),
        "private_data_root": str(private / "data"),
        "stands": {},
        "artifacts": {},
        "release": {"commit": "a" * 40, "root": str(private / "release")},
    }
    for name in ("agent/graph.py", "api/routers/conversation.py"):
        put(private / "release" / name, (ROOT / name).read_bytes())
    artifacts = {}
    for label in (
        "shim_executable",
        "shim_config",
        "codex_executable",
        *("env_" + k for k in cv.KEYS),
    ):
        path = put(private / label, b"synthetic\n")
        artifacts[label] = {"path_sha256": cv.digest(str(path.resolve())), "sha256": cv.sha(path)}
        if label.startswith("env_"):
            key = label[4:]
            config["stands"][key] = {"env": str(path), "app": str(private / key / "app")}
        else:
            config["artifacts"][label] = str(path)
    config_path = put(private / "config.json", config)
    spec = put(repo / driver.SPEC, b"Status: **registered before the first request**\n")
    registration = {
        "pending": [],
        "request_ready": True,
        "series": "synthetic",
        "files": {driver.SPEC: cv.sha(spec)},
        "config_sha256": cv.sha(config_path),
        "private_root_sha256": cv.digest(str(private.resolve())),
        "copy_receipt_sha256": cv.sha(Path(config["copy_receipt"])),
        "stage5_references": {k: "b" * 64 for k in cv.KEYS[:2]},
        "release": {"commit": "a" * 40},
        "private_artifacts": artifacts,
    }
    target = put(records / "synthetic/registration.json", registration)
    git = shutil.which("git")
    assert git

    def git_run(*args):
        return subprocess.run([git, *args], cwd=repo, capture_output=True, check=True).stdout  # nosec B603 # Local synthetic Git argv.

    git_run("init")
    git_run("config", "user.email", "synthetic@example.invalid")
    git_run("config", "user.name", "Synthetic")
    git_run(
        "add",
        "docs/specs/codex-only-quality.md",
        "reports/codex-only-quality/synthetic/registration.json",
    )
    git_run("commit", "-m", "Synthetic admission fixture")
    real_git = driver.git_bytes

    def stand_git(path, *args):
        if path == repo:
            return real_git(path, *args)
        return (
            b"a" * 40
            if args == ("rev-parse", "HEAD")
            else b"HEAD"
            if args[0] == "rev-parse"
            else b""
        )

    monkeypatch.setattr(driver, "git_bytes", stand_git)
    monkeypatch.setattr(driver, "validate_runtime_config", lambda *args: None)
    logical = {"passed": True, "collection": {"passed": True, "count": 1}}
    monkeypatch.setattr(
        cv,
        "admit_receipt",
        lambda *args, **kwargs: {
            "logical": {k: logical for k in cv.KEYS},
            "stage5_references": registration["stage5_references"],
        },
    )
    monkeypatch.setattr(cv, "logical_metadata", lambda *args: ({"passed": True}, []))
    monkeypatch.setattr(cv, "check_collection", lambda *args: {"passed": True, "count": 1})
    args = SimpleNamespace(
        budget=1080, series="synthetic", config=config_path, records=records, private=private
    )
    return SimpleNamespace(
        repo=repo, args=args, registration=registration, target=target, git=git_run, spec=spec
    )


def test_clean_admission(admission):
    assert driver.admit_chunk(admission.args, admission.repo)[1]["request_ready"]


@pytest.mark.parametrize("failure", ["uncommitted", "pending", "hash", "budget", "artifact"])
def test_admission_refusals(admission, failure):
    f = admission
    if failure == "budget":
        f.args.budget = 1081
    elif failure == "hash":
        put(f.spec, b"changed\n")
    elif failure == "artifact":
        put(f.args.private / "shim_executable", b"changed\n")
    else:
        f.registration["pending"] = ["missing.py"] if failure == "pending" else []
        f.registration["extra"] = True
        put(f.target, f.registration)
        if failure == "pending":
            f.git("add", "reports/codex-only-quality/synthetic/registration.json")
            f.git("commit", "-m", "Pending fixture")
    with pytest.raises(cv.Refusal):
        driver.admit_chunk(f.args, f.repo)


def test_request_budget_refuses_before_runtime():
    args = driver.parser().parse_args(
        [
            "probe",
            "--config",
            "missing",
            "--private",
            "missing",
            "--records",
            "missing",
            "--series",
            "synthetic",
            "--budget",
            "1081",
        ]
    )
    assert driver.request_chunk(args) == 1  # nosec B101 # Pytest contract assertion.


@pytest.mark.parametrize("key", cv.KEYS)
def test_stand_database_is_accepted_by_the_deployment_helper(key):
    from deploy.windows import prepare_postgres

    name = driver.stand_database("attempt-01", key)
    assert name == "codex_quality_attempt_01_" + key
    assert prepare_postgres.database_name(name) == name


def test_python_exiting_during_its_command_read_is_skipped_live_one_refuses():
    def unreadable():
        raise sr.Stop(5, "python_command_unreadable")

    assert sr.command_or_exit(lambda: "python -m pytest", lambda: True) == "python -m pytest"
    # An outside session's short-lived python exited between OpenProcess and the read.
    assert sr.command_or_exit(unreadable, lambda: False) is None
    with pytest.raises(sr.Stop) as error:
        sr.command_or_exit(unreadable, lambda: True)
    assert (error.value.code, error.value.reason) == (5, "python_command_unreadable")


def test_stat_cache_reuses_unchanged_hashes_and_rehashes_changed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "tree"
    put(root / "a.txt", b"first\n")
    put(root / "sub" / "b.txt", b"second\n")
    full = cv.tree_files(root)
    hashed: list[str] = []
    original = cv.sha

    def counting(path: Path) -> str:
        hashed.append(path.name)
        return original(path)

    monkeypatch.setattr(cv, "sha", counting)
    cache = tmp_path / "series" / "stat-cache.json"
    for _ in range(2):  # Registration hashes in full every time and seeds the cache.
        hashed.clear()
        with driver.stat_cache(cache, reuse=False):
            assert cv.tree_files(root) == full
        assert sorted(hashed) == ["a.txt", "b.txt"] and cv.sha is counting
    hashed.clear()
    with driver.stat_cache(cache, reuse=True):
        assert cv.tree_files(root) == full
    assert hashed == []
    info = (root / "a.txt").stat()
    (root / "a.txt").write_bytes(b"FIRST\n")  # Same size: the new mtime alone forces a hash.
    os.utime(root / "a.txt", ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000))
    with driver.stat_cache(cache, reuse=True):
        changed = cv.tree_files(root)
    assert hashed == ["a.txt"]
    assert changed != full and changed == cv.tree_files(root)
    # A refusal inside saves nothing and restores copy_verify's own hash.
    other = tmp_path / "other" / "stat-cache.json"
    with pytest.raises(cv.Refusal), driver.stat_cache(other, reuse=True):
        cv.tree_files(root)
        cv.require(False, "refused")
    assert not other.exists() and cv.sha is counting
