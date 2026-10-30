"""Stage 4, item 5a, its n-gram lever (docs/specs/stage4-step5a-ngram-decoding.md): the call as
Ollama's runner makes it, the runner read from ps, the inputs, the blocks on a stand-in Mac, their
gate, the series' stops, and the frozen reading of fidelity, equality, speed and outcome."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import re
import subprocess
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from llm.role_params import default_role_params

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/stage4-step5a-ngram/tools/ngram_decode.py"
STEP4B = ROOT / "reports/stage4-step4b/d1ef9e5/record.json"


def _load():
    spec = importlib.util.spec_from_file_location("ngram_decode", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ngram_decode"] = module
    spec.loader.exec_module(module)
    return module


nd = _load()
wt = nd.wt
QUIET = {
    "foreign": [],
    "others_cpu": 12.5,
    "models": [],
    "llama_servers": 1,
    "load1": 1.5,
    "swap_mb": 2000.0,
}
HELD = {**QUIET, "models": [nd.MODEL]}
BINARY = "/Users/julia/RAG_new_tools_ollama_v0.33.2/llama-server"
GGUF = "/Users/julia/.ollama/models/blobs/sha256-" + "a" * 64
ARGS = ["--model", GGUF, "--host", "127.0.0.1", "--no-webui", "-c", "4096", "-np", "1"]
# Ollama draws a new media marker for every runner it starts.
MARKER = "<__ollama_media_" + "1" * 32 + "__>"
RUNNER = {
    "binary": BINARY,
    "args": ARGS,
    "model": GGUF,
    "env": {
        "DYLD_LIBRARY_PATH": "/Users/julia/RAG_new_tools_ollama_v0.33.2",
        "LLAMA_MEDIA_MARKER": MARKER,
    },
}
SHOWN = 'repeat_penalty 1\nstop "<|im_start|>"\nstop "<|im_end|>"\ntemperature 0.7\ntop_k 20\ntop_p 0.8\n'


def _restarted(**env):
    """The runner as Ollama starts it again: the same, but for a new media marker."""
    marker = "<__ollama_media_" + "2" * 32 + "__>"
    return {**RUNNER, "env": {**RUNNER["env"], "LLAMA_MEDIA_MARKER": marker, **env}}


def make_inputs(out):
    """inputs.json in miniature: the warm-up and the thirteen, each its own flat and rendered
    prompt, the thirteen with step 4b's count of their prompt tokens."""
    calls = []
    for i, case_id in enumerate(("warm-up", *nd.CASES)):
        flat = f"question {case_id}"
        rendered = f"<|im_start|>user\n{flat}<|im_end|>\n<|im_start|>assistant\n"
        call = {
            "case_id": case_id,
            "flat": flat,
            "flat_sha256": nd.digest(flat),
            "rendered": rendered,
            "rendered_sha256": nd.digest(rendered),
        }
        if i:
            call["step4b_prompt_tokens"] = 2400 + i
        calls.append(call)
    facts = {
        "schema": nd.SCHEMA,
        "spec": nd.SPEC,
        "code_sha": "c" * 40,
        "step4b_inputs": {"path": "inputs.json", "sha256": nd.STEP4B_INPUTS_SHA256},
        "model": nd.MODEL,
        "digest": nd.DIGEST,
        "ollama_version": nd.OLLAMA_VERSION,
        "show": {"parameters": SHOWN, "template_sha256": "f" * 64, "details": {}},
        "options": nd.options_of({"parameters": SHOWN}),
        "runner": {**RUNNER, "binary_sha256": "b" * 64, "version": "version: 1 (d222767c7)"},
        "gguf": {"path": GGUF, "bytes": 2_500_000_000, "sha256": "a" * 64},
        "warm_up": calls[0],
        "cases": calls[1:],
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "inputs.json").write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")
    return facts


class Stand:
    """The Mac in miniature: Ollama, the direct server and ps answer by the test's rules - an
    arm's text and decode milliseconds for a question; both count step 4b's prompt tokens for a
    question, 2,400 for the warm-up, unless `ollama_extra` adds some to Ollama's count; Ollama's
    runner comes back with a new media marker."""

    def __init__(self, monkeypatch, facts, text=None, ms=None):
        self.text = text or (lambda arm, case_id: f"answer to {case_id}")
        self.ms = ms or (lambda arm, case_id: 14400.0 if arm == "ngram" else 19200.0)
        calls = [facts["warm_up"], *facts["cases"]]
        self.rendered = {c["rendered"]: c["case_id"] for c in calls}
        self.flat = {c["flat"]: c["case_id"] for c in calls}
        self.tokens = {c["case_id"]: c.get("step4b_prompt_tokens", 2400) for c in calls}
        self.ollama_extra = {}
        self.arm, self.bodies, self.flats, self.started, self.stopped = None, [], [], 0, 0
        self.fail_at = None
        stand = self

        class Server:
            def __init__(self, facts, arm, log):
                self.arm, self.process = arm, SimpleNamespace(pid=4242)

            def start(self):
                stand.started += 1

            def rss_mib(self):
                return 2900.0

            def stop(self):
                stand.stopped += 1

        for name, value in {
            "Server": Server,
            "stand": lambda facts: [],
            "sample": lambda own: dict(HELD if self.arm == "ollama" else QUIET),
            "direct": self.direct,
            "through_ollama": self.through_ollama,
            "runner": _restarted,
            "pids_of": lambda *names: set(),
        }.items():
            monkeypatch.setattr(nd, name, value)
        monkeypatch.setattr(wt, "unload", lambda: {"unload_sec": 1.5})
        monkeypatch.setattr(wt, "machine", lambda: {"cores": 4})

    def direct(self, body, timeout=None):
        self.bodies.append(body)
        case_id = self.rendered[body["prompt"]]
        if case_id == self.fail_at:
            raise RuntimeError("the stream ended without its last event")
        text, ms = self.text(self.arm, case_id), self.ms(self.arm, case_id)
        cache = 0 if case_id == "warm-up" else 30
        timings = {
            "cache_n": cache,
            "prompt_n": self.tokens[case_id] - cache,
            "prompt_ms": 57600.0,
            "predicted_n": 90,
            "predicted_ms": ms,
            "draft_n": None,
            "draft_n_accepted": None,
        }
        if self.arm == "ngram":
            timings.update(draft_n=40, draft_n_accepted=30)
        return {
            "text": text,
            "text_sha256": nd.digest(text),
            "wall_sec": round(57.6 + ms / 1000, 3),
            "first_sec": 57.7,
            "stop_type": "eos",
            "truncated": False,
            "tokens_predicted": 90,
            "tokens_evaluated": self.tokens[case_id],
            "timings": timings,
            "settings": {"seed": nd.SEED},
        }

    def through_ollama(self, prompt, timeout=None):
        self.flats.append(prompt)
        case_id = self.flat[prompt]
        text = self.text("ollama", case_id)
        counters = dict.fromkeys(wt.COUNTERS, 1)
        counters.update(
            prompt_eval_count=self.tokens[case_id] + self.ollama_extra.get(case_id, 0),
            eval_count=90,
        )
        return {
            "text": text,
            "text_sha256": nd.digest(text),
            "wall_sec": 80.0,
            "first_sec": 58.0,
            "done_reason": "stop",
            "counters": counters,
        }

    def block(self, number, out):
        self.arm = nd.SCHEDULE[number]
        return nd.block(number, out)


def _blocks(tmp_path, monkeypatch, **rules):
    out = tmp_path / "out"
    facts = make_inputs(out)
    (out / "blocks").mkdir()
    return out, facts, Stand(monkeypatch, facts, **rules)


def _rewrite(path, how):
    lines = nd.lines_of(path)
    how(lines)
    path.write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines), encoding="utf-8"
    )


class Reply(io.BytesIO):
    """A stand-in HTTP reply: its lines, its status."""

    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# --- the call ---


def test_the_schedule_is_ollama_then_abba_of_the_direct_server_and_the_arms_differ_by_one_flag():
    assert nd.SCHEDULE == {0: "ollama", 1: "base", 2: "ngram", 3: "ngram", 4: "base"}
    assert nd.ARMS == {"base": (), "ngram": ("--spec-type", "ngram-simple")}
    for arm, blocks in nd.REPEATS.items():
        assert [n for n, a in nd.SCHEDULE.items() if a == arm] == [int(n) for n in sorted(blocks)]
    assert sorted(nd.PAIRS) == sorted(
        (b, g) for b in nd.REPEATS["base"] for g in nd.REPEATS["ngram"]
    )
    facts = {"warm_up": {"case_id": "warm-up"}, "cases": [{"case_id": c} for c in nd.CASES]}
    assert [c["case_id"] for c in nd.calls_of(facts, "ollama")] == ["warm-up", *nd.CASES[:3]]
    for arm in ("base", "ngram"):
        assert [c["case_id"] for c in nd.calls_of(facts, arm)] == ["warm-up", *nd.CASES]


def test_the_questions_model_and_inputs_are_step_4bs_and_the_request_the_chats_with_a_seed():
    record = json.loads(STEP4B.read_text(encoding="utf-8"))
    assert nd.STEP4B_RECORD == STEP4B
    assert nd.STEP4B_INPUTS_SHA256 == record["inputs"]["sha256"]
    assert nd.CASES == tuple(c["case_id"] for c in record["inputs"]["cases"])
    assert len(nd.CASES) == 13 and nd.WINDOW == 4096
    assert all(str(nd.WINDOW) in c["prompts"] for c in record["inputs"]["cases"])
    assert (nd.MODEL, nd.DIGEST, nd.OLLAMA_VERSION) == tuple(
        record["model"][k] for k in ("name", "digest", "ollama_version")
    )
    generate = default_role_params()["generate"]
    assert nd.REQUEST == {
        "num_ctx": 4096,
        "num_predict": generate["max_tokens"],
        "temperature": generate["temperature"],
        "seed": nd.SEED,
    }
    body = nd.product_body("the prompt")
    assert sorted(body) == ["format", "model", "options", "prompt", "stream", "think"]
    assert (body["format"], body["model"], body["stream"], body["think"]) == (
        "",
        nd.MODEL,
        True,
        False,
    )
    assert body["options"] == nd.REQUEST and body["options"] is not nd.REQUEST


def test_the_models_parameters_go_over_ollamas_defaults_and_the_request_over_both():
    assert nd.parameters(SHOWN) == {
        "repeat_penalty": 1.0,
        "stop": ["<|im_start|>", "<|im_end|>"],
        "temperature": 0.7,
        "top_k": 20,
        "top_p": 0.8,
    }
    options = nd.options_of({"parameters": SHOWN})
    assert (options["temperature"], options["top_k"], options["top_p"]) == (0.2, 20, 0.8)
    assert (options["seed"], options["num_predict"], options["num_ctx"]) == (1030, 1024, 4096)
    assert (options["repeat_last_n"], options["typical_p"], options["min_p"]) == (64, 1.0, 0.0)
    assert isinstance(options["top_k"], int) and isinstance(options["repeat_penalty"], float)
    assert nd.options_of({}) == {**nd.DEFAULTS, **nd.REQUEST}
    assert nd.DEFAULTS["stop"] == []


def test_the_completion_body_is_the_one_ollamas_runner_posts_with_gos_omitempty():
    options = nd.options_of({"parameters": SHOWN})
    assert nd.completion_body(options, "the prompt") == {
        "prompt": "the prompt",
        "stream": True,
        "cache_prompt": True,
        "n_predict": 1024,
        "n_keep": 4,
        "temperature": 0.2,
        "top_k": 20,
        "top_p": 0.8,
        "min_p": 0.0,
        "stop": ["<|im_start|>", "<|im_end|>"],
        "repeat_penalty": 1.0,
        "repeat_last_n": 64,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "typical_p": 1.0,
        "seed": 1030,
    }
    bare = {**options, "num_predict": -1, "stop": [], "typical_p": 0.0, "num_keep": 0}
    open_ended = nd.completion_body(bare, "p")
    assert open_ended["n_predict"] == 40960
    assert not {"stop", "typical_p", "n_keep"} & set(open_ended)
    assert nd.completion_body({**options, "num_predict": 50000}, "p")["n_predict"] == 40960
    assert "n_predict" not in nd.completion_body({**options, "num_predict": 0}, "p")


def _sse(events):
    return b"".join(b"data: " + json.dumps(e).encode("utf-8") + b"\n\n" for e in events)


def test_the_direct_call_reads_the_servers_stream_as_ollamas_runner_reads_it(monkeypatch):
    last = {
        "content": "",
        "stop": True,
        "stop_type": "eos",
        "truncated": False,
        "tokens_predicted": 3,
        "tokens_evaluated": 120,
        "timings": {
            "cache_n": 100,
            "prompt_n": 20,
            "prompt_ms": 400.0,
            "predicted_n": 3,
            "predicted_ms": 600.0,
            "predicted_per_second": 5.0,
        },
        "generation_settings": {"seed": 1030},
    }
    events = [{"content": "Испыт", "stop": False}, {"content": "ание.", "stop": False}, last]
    sent = []

    def opener(request, timeout):
        sent.append((request.full_url, json.loads(request.data), timeout))
        return Reply(_sse(events))

    monkeypatch.setattr(nd.OPENER, "open", opener)
    got = nd.direct({"prompt": "p"})
    assert sent == [(f"http://127.0.0.1:{nd.PORT}/completion", {"prompt": "p"}, nd.QUESTION_LIMIT)]
    assert got["text"] == "Испытание." and got["text_sha256"] == nd.digest("Испытание.")
    assert (got["stop_type"], got["truncated"], got["tokens_evaluated"]) == ("eos", False, 120)
    assert got["timings"] == {
        "cache_n": 100,
        "prompt_n": 20,
        "prompt_ms": 400.0,
        "predicted_n": 3,
        "predicted_ms": 600.0,
        "draft_n": None,
        "draft_n_accepted": None,
    }
    assert got["settings"] == {"seed": 1030} and got["first_sec"] is not None
    for broken in ([{"error": {"message": "x"}}], events[:2]):
        monkeypatch.setattr(nd.OPENER, "open", lambda request, timeout, b=broken: Reply(_sse(b)))
        with pytest.raises(RuntimeError):
            nd.direct({"prompt": "p"})


def test_the_call_through_ollama_is_the_chats_and_keeps_ollamas_counters(monkeypatch):
    lines = [
        {"response": "Да", "done": False},
        {"response": ".", "done": False},
        {"response": "", "done": True, "done_reason": "stop", **dict.fromkeys(wt.COUNTERS, 7)},
    ]
    sent = []

    def opener(request, timeout):
        sent.append((request.full_url, json.loads(request.data)))
        return Reply(b"".join(json.dumps(x).encode("utf-8") + b"\n" for x in lines))

    monkeypatch.setattr(nd.OPENER, "open", opener)
    got = nd.through_ollama("the flat prompt")
    assert sent == [(wt.OLLAMA + "/api/generate", nd.product_body("the flat prompt"))]
    assert got["text"] == "Да." and got["done_reason"] == "stop"
    assert got["counters"] == dict.fromkeys(wt.COUNTERS, 7)


# --- the stand ---

PS = "\n".join(
    [
        "  501 /Users/julia/RAG_new_tools_ollama_v0.33.2/ollama serve",
        f"  777 {BINARY} --model {GGUF} --port 51234 --host 127.0.0.1 --no-webui -c 4096 -np 1",
        "  900 /usr/bin/python3 notes.py llama-server",
    ]
)


def test_the_runner_is_ollamas_llama_server_without_its_port_and_with_its_library_environment(
    monkeypatch,
):
    command = PS.splitlines()[1].split(None, 1)[1]
    environment = (
        "PATH=/usr/bin HOME=/Users/julia OLLAMA_HOST=127.0.0.1 SSH_CLIENT=10.0.0.2 52000 22 "
        "DYLD_LIBRARY_PATH=/Users/julia/RAG_new_tools_ollama_v0.33.2 LLAMA_ARG_THREADS=4 "
        f"LLAMA_MEDIA_MARKER={MARKER} SECRET_TOKEN=x"
    )
    shown = {"listing": PS, "env": f"{command} {environment}\n"}

    def run(argv, **kwargs):
        if argv[:2] == ["ps", "-axww"]:
            return SimpleNamespace(stdout=shown["listing"])
        assert argv[:3] == ["ps", "-E", "-ww"] and argv[-1] == "777"
        return SimpleNamespace(stdout=shown["env"])

    monkeypatch.setattr(nd.subprocess, "run", run)
    assert nd.runner() == {
        "binary": BINARY,
        "args": ARGS,
        "model": GGUF,
        "env": {
            "DYLD_LIBRARY_PATH": "/Users/julia/RAG_new_tools_ollama_v0.33.2",
            "LLAMA_ARG_THREADS": "4",
            "LLAMA_MEDIA_MARKER": MARKER,
        },
    }
    # A space in a variable the tool keeps would cut its value; elsewhere it is no matter.
    shown["env"] = f"{command} DYLD_LIBRARY_PATH=/Users/julia/my tools LLAMA_ARG_THREADS=4\n"
    with pytest.raises(SystemExit, match="DYLD_LIBRARY_PATH holds a space"):
        nd.runner()
    shown["env"] = f"{BINARY} --other {environment}\n"
    with pytest.raises(SystemExit, match="environment"):
        nd.runner()
    shown["listing"] = PS + f"\n  778 {command}"
    with pytest.raises(SystemExit, match="2 llama-server processes"):
        nd.runner()
    shown["listing"] = PS + f"\n  4242 {BINARY} --model {GGUF} --port {nd.PORT} --spec-type x"
    assert nd.servers_on_port() == [4242]


def test_the_stand_is_no_config_the_runners_binary_and_model_ollamas_version_and_a_free_port(
    tmp_path, monkeypatch
):
    binary, gguf = tmp_path / "llama-server", tmp_path / "model.gguf"
    binary.write_bytes(b"binary")
    gguf.write_bytes(b"model")
    facts = {
        "runner": {"binary": str(binary), "binary_sha256": nd.sha256(binary)},
        "gguf": {"path": str(gguf), "bytes": 5},
    }
    answers = {
        "/api/version": {"version": nd.OLLAMA_VERSION},
        "/api/tags": {"models": [{"name": nd.MODEL, "digest": nd.DIGEST}]},
    }
    monkeypatch.setattr(wt, "LLAMA_CONFIG", tmp_path / "config.ini")
    monkeypatch.setattr(wt, "ollama", lambda path, payload=None, timeout=30.0: answers[path])
    monkeypatch.setattr(nd, "port_taken", lambda: False)
    assert nd.stand(facts) == []
    (tmp_path / "config.ini").touch()
    binary.write_bytes(b"another")
    gguf.write_bytes(b"models")
    answers["/api/version"] = {"version": "0.34.0"}
    answers["/api/tags"] = {"models": [{"name": nd.MODEL, "digest": "0" * 64}]}
    monkeypatch.setattr(nd, "port_taken", lambda: True)
    assert nd.stand(facts) == [
        "llama.cpp's config.ini exists",
        "another llama-server",
        "another model file",
        "Ollama 0.34.0",
        "another model under the name",
        f"port {nd.PORT} taken",
    ]


def test_a_sample_leaves_out_the_blocks_own_processes_and_disturbed_reads_the_arm(monkeypatch):
    listing = "  101  400.0\n  102    0.0\n  200   30.5\n  201   12.0\n"
    monkeypatch.setattr(nd.subprocess, "run", lambda argv, **kw: SimpleNamespace(stdout=listing))
    monkeypatch.setattr(wt, "foreign", lambda: [])
    monkeypatch.setattr(wt, "models", lambda: [])
    monkeypatch.setattr(wt, "llama_servers", lambda: 1)
    monkeypatch.setattr(wt, "swap_used_mb", lambda: 2000.0)
    monkeypatch.setattr(nd.os, "getloadavg", lambda: (1.5, 1.4, 1.3))
    got = nd.sample({101, 102})
    assert got == {**QUIET, "others_cpu": 42.5}
    assert not nd.disturbed(got, "base") and nd.disturbed(got, "ollama")
    assert not nd.disturbed({**got, "models": [nd.MODEL]}, "ollama")
    for change in (
        {"foreign": ["pytest"]},
        {"others_cpu": 100.5},
        {"llama_servers": 2},
        {"models": [nd.MODEL]},
    ):
        assert nd.disturbed({**got, **change}, "ngram"), change
    assert nd.disturbed({**HELD, "llama_servers": 0}, "ollama")
    # The blocks' own command lines are not what step 0's rule finds.
    for line in (
        f"{TOOL} block 2 /Users/julia/RAG_new_s4p5a_ngram_runs",
        " ".join([BINARY, *ARGS]),
    ):
        assert re.search(wt.FOREIGN, line) is None, line


def _raises(error):
    def call(*args, **kwargs):
        raise error

    return call


def test_a_sample_ollama_or_ps_did_not_answer_names_its_error_and_is_disturbed(monkeypatch):
    listing = "  101  400.0\n  200   30.5\n"
    monkeypatch.setattr(nd.subprocess, "run", lambda argv, **kw: SimpleNamespace(stdout=listing))
    monkeypatch.setattr(wt, "foreign", lambda: [])
    monkeypatch.setattr(wt, "swap_used_mb", lambda: 2000.0)
    monkeypatch.setattr(nd.os, "getloadavg", lambda: (1.5, 1.4, 1.3))
    for where, error in (
        ("models", ConnectionRefusedError()),
        ("models", ValueError("not JSON")),
        ("llama_servers", subprocess.CalledProcessError(1, ["ps"])),
    ):
        monkeypatch.setattr(wt, "models", lambda: [])
        monkeypatch.setattr(wt, "llama_servers", lambda: 1)
        monkeypatch.setattr(wt, where, _raises(error))
        got = nd.sample({101})
        assert got["error"] == type(error).__name__ and got["others_cpu"] == 30.5, where
        for arm in ("ollama", "base", "ngram"):
            assert nd.disturbed(got, arm), (where, arm)
    monkeypatch.setattr(wt, "llama_servers", lambda: 1)
    monkeypatch.setattr(nd.subprocess, "run", _raises(subprocess.TimeoutExpired(["ps"], 20)))
    got = nd.sample({101})
    assert got == {**dict.fromkeys(QUIET), "error": "TimeoutExpired"}
    assert nd.disturbed(got, "base")


def test_idle_wants_no_foreign_process_no_model_no_llama_server_no_lock_and_a_low_load(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(wt, "CI_LOCK", tmp_path / "lock")
    monkeypatch.setattr(nd, "IDLE_LIMIT", 0)
    monkeypatch.setattr(nd.os, "getloadavg", lambda: (1.6, 1.9, 1.7))
    free = {**QUIET, "llama_servers": 0}
    for change, want in [
        ({}, True),
        ({"foreign": ["pytest"]}, False),
        ({"models": [nd.MODEL]}, False),
        ({"llama_servers": 1}, False),
        ({"others_cpu": 100.1}, False),
        ({"others_cpu": 100.0}, True),
        ({"error": "ConnectionRefusedError"}, False),
    ]:
        monkeypatch.setattr(nd, "sample", lambda own, c=change: {**free, **c})
        assert nd.idle(True, set()) is want, change
    monkeypatch.setattr(nd, "sample", lambda own: dict(free))
    monkeypatch.setattr(nd.os, "getloadavg", lambda: (1.6, 2.0, 1.7))
    assert nd.idle(True, set()) is False and nd.idle(False, set()) is True
    (tmp_path / "lock").touch()
    assert nd.idle(False, set()) is False


class Process:
    """A stand-in server process: running until stopped, or deaf to SIGTERM."""

    def __init__(self, argv, deaf=False, code=None, **kwargs):
        self.argv, self.deaf, self.returncode, self.pid = argv, deaf, code, 4242
        self.signals = []

    def poll(self):
        return self.returncode

    def send_signal(self, number):
        self.signals.append(number)
        if not self.deaf:
            self.returncode = -number

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired(self.argv, timeout)
        return self.returncode

    def kill(self):
        self.returncode = -9


def test_the_direct_server_is_the_runners_binary_arguments_and_environment_with_the_arms_flag(
    tmp_path, monkeypatch
):
    base = nd.Server({"runner": RUNNER}, "base", tmp_path / "server.log")
    ngram = nd.Server({"runner": RUNNER}, "ngram", tmp_path / "server.log")
    assert base.command == [BINARY, *ARGS, "--port", str(nd.PORT)]
    assert ngram.command == [*base.command, "--spec-type", "ngram-simple"]
    assert ngram.env == {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(Path.home()),
        "LC_ALL": "C",
        **RUNNER["env"],
    }
    started = []
    monkeypatch.setattr(
        nd.subprocess, "Popen", lambda argv, **kw: started.append(kw) or Process(argv)
    )
    monkeypatch.setattr(nd.OPENER, "open", lambda url, timeout: Reply(b"{}"))
    ngram.start()
    assert started[0]["env"] == ngram.env and ngram.process.argv == ngram.command
    ngram.stop()
    assert ngram.process.signals == [nd.signal.SIGTERM]
    deaf = nd.Server({"runner": RUNNER}, "base", tmp_path / "server.log")
    deaf.process = Process(deaf.command, deaf=True)
    deaf.stop()
    assert deaf.process.returncode == -9
    monkeypatch.setattr(nd.subprocess, "Popen", lambda argv, **kw: Process(argv, code=1))
    with pytest.raises(RuntimeError, match="exited 1"):
        base.start()


def test_a_server_not_ready_within_its_limit_fails_its_start(tmp_path, monkeypatch):
    def refused(url, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(nd.subprocess, "Popen", lambda argv, **kw: Process(argv))
    monkeypatch.setattr(nd.OPENER, "open", refused)
    monkeypatch.setattr(nd, "START_LIMIT", 0.05)
    monkeypatch.setattr(nd, "HEALTH_POLL", 0.01)
    with pytest.raises(RuntimeError, match="not ready in time"):
        nd.Server({"runner": RUNNER}, "base", tmp_path / "server.log").start()


# --- the inputs ---


def _budget(fitted):
    """A stand-in for step 4's prompt_budget: the flat prompt is the question's, marked."""
    module = types.ModuleType("prompt_budget")
    module.code_prompt = lambda: "V4"

    @contextlib.contextmanager
    def answer_prompt(template):
        fitted.append(template)
        yield

    module.answer_prompt = answer_prompt
    module.fit = lambda window, question, plain: (f"flat {question} {window}", None)
    return module


def _inputs_stand(tmp_path, monkeypatch, cases=nd.CASES):
    stored = {
        "cases": [
            {
                "case_id": c,
                "question": f"q {c}",
                "plain": [f"doc {c}"],
                "prompts": {"4096": {"sha256": nd.digest(f"flat q {c} 4096")}},
            }
            for c in cases
        ]
    }
    step4b = tmp_path / "step4b-inputs.json"
    step4b.write_text(json.dumps(stored), encoding="utf-8")
    monkeypatch.setattr(nd, "STEP4B_INPUTS_SHA256", nd.sha256(step4b))
    fitted, rendered = [], []
    monkeypatch.setitem(sys.modules, "prompt_budget", _budget(fitted))
    monkeypatch.setattr(sys, "path", list(sys.path))
    blob = tmp_path / "blobs" / f"sha256-{hashlib.sha256(b'gguf').hexdigest()}"
    blob.parent.mkdir()
    blob.write_bytes(b"gguf")
    binary = tmp_path / "llama-server"
    binary.write_bytes(b"binary")
    env = {"DYLD_LIBRARY_PATH": str(tmp_path), "LLAMA_MEDIA_MARKER": MARKER}
    run = {"binary": str(binary), "args": ["--model", str(blob)], "model": str(blob), "env": env}
    show = {
        "parameters": SHOWN,
        "template": "{{ .Prompt }}",
        "details": {"f": "gguf"},
        "modelfile": 'FROM /x\nTEMPLATE "{{ .Prompt }}"\nPARAMETER top_k 20\n',
    }
    versions = []

    def ollama(path, payload=None, timeout=30.0):
        if path == "/api/show":
            return show
        if path == "/api/generate":
            rendered.append(payload)
            return {"_debug_info": {"rendered_template": f"<r>{payload['prompt']}</r>"}}
        assert path == "/api/version"
        return {"version": nd.OLLAMA_VERSION}

    def version(argv, **kw):
        versions.append((argv, kw.get("env")))
        return SimpleNamespace(stdout="", stderr="version: 1 (d222767c7)\n", returncode=0)

    monkeypatch.setattr(wt, "ollama", ollama)
    monkeypatch.setattr(wt, "LLAMA_CONFIG", tmp_path / "config.ini")
    monkeypatch.setattr(wt, "models", lambda: [])
    monkeypatch.setattr(wt, "llama_servers", lambda: 0)
    monkeypatch.setattr(wt, "loaded", lambda: {"digest": nd.DIGEST})
    monkeypatch.setattr(wt, "unload", lambda: {"unload_sec": 2.0})
    # A clean worktree at HEAD c...c.
    monkeypatch.setattr(wt, "git", lambda *args: "" if args[0] == "status" else "c" * 40)
    monkeypatch.setattr(nd, "runner", lambda: dict(run))
    monkeypatch.setattr(nd.subprocess, "run", version)
    return step4b, run, blob, fitted, rendered, show, versions


def test_the_inputs_rebuild_step_4bs_prompts_render_each_through_ollama_and_read_its_runner(
    tmp_path, monkeypatch, capsys
):
    step4b, run, blob, fitted, rendered, show, versions = _inputs_stand(tmp_path, monkeypatch)
    out = tmp_path / "out"
    assert nd.inputs(step4b, out) == 0
    got = json.loads((out / "inputs.json").read_text(encoding="utf-8"))
    calls = [got["warm_up"], *got["cases"]]
    assert [c["case_id"] for c in calls] == ["warm-up", *nd.CASES] and fitted == ["V4"]
    assert got["warm_up"]["flat"] == nd.WARM_UP
    assert got["cases"][0]["flat"] == f"flat q {nd.CASES[0]} 4096"
    assert [p["prompt"] for p in rendered] == [c["flat"] for c in calls]
    assert all(
        p == {**nd.product_body(p["prompt"], stream=False), "_debug_render_only": True}
        for p in rendered
    )
    for call in calls:
        assert call["rendered"] == f"<r>{call['flat']}</r>"
        assert call["rendered_sha256"] == nd.digest(call["rendered"])
        assert call["flat_sha256"] == nd.digest(call["flat"])
    # Each question carries Ollama's count of its prompt in step 4b's record; the warm-up none.
    record = json.loads(STEP4B.read_text(encoding="utf-8"))
    counted = {pair["case_id"]: pair["w4096_answer_prompt_tokens"] for pair in record["pairs"]}
    assert [c.get("step4b_prompt_tokens") for c in calls] == [None, *map(counted.get, nd.CASES)]
    assert all(counted[c] for c in nd.CASES)
    assert got["options"] == nd.options_of({"parameters": SHOWN})
    assert (got["show"]["renderer"], got["show"]["parser"]) == (None, None)
    assert got["runner"] == {
        "binary": run["binary"],
        "binary_sha256": nd.sha256(Path(run["binary"])),
        "version": "version: 1 (d222767c7)",
        "args": run["args"],
        "env": run["env"],
    }
    # The version is read with the runner's environment, as the direct servers start.
    assert versions == [([run["binary"], "--version"], nd.server_env(run))]
    assert got["gguf"] == {"path": str(blob), "bytes": 4, "sha256": blob.name[len("sha256-") :]}
    assert (got["code_sha"], got["unload"], got["spec"]) == ("c" * 40, {"unload_sec": 2.0}, nd.SPEC)
    assert got["tool_sha256"] == nd.sha256(TOOL)
    printed = capsys.readouterr().out.splitlines()
    assert printed[1] == "environment: DYLD_LIBRARY_PATH LLAMA_MEDIA_MARKER"


def test_the_inputs_refuse_other_inputs_another_prompt_a_loaded_model_or_a_misnamed_file(
    tmp_path, monkeypatch
):
    step4b, run, blob, fitted, rendered, show, versions = _inputs_stand(tmp_path, monkeypatch)
    out = tmp_path / "out"
    monkeypatch.setattr(wt, "models", lambda: [nd.MODEL])
    with pytest.raises(SystemExit, match="before the inputs"):
        nd.inputs(step4b, out)
    monkeypatch.setattr(wt, "models", lambda: [])
    # A renderer or a parser, by /api/show's field or by the Modelfile's line.
    show["parser"] = "qwen3"
    with pytest.raises(SystemExit, match="a renderer or a parser"):
        nd.inputs(step4b, out)
    del show["parser"]
    modelfile = show["modelfile"]
    show["modelfile"] += "RENDERER qwen3-coder\n"
    with pytest.raises(SystemExit, match="a renderer or a parser"):
        nd.inputs(step4b, out)
    assert nd.handlers_of(show) == {"renderer": "qwen3-coder", "parser": None}
    show["modelfile"] = modelfile
    monkeypatch.setattr(nd, "runner", lambda: {**run, "env": {"LLAMA_MEDIA_MARKER": MARKER}})
    with pytest.raises(SystemExit, match="no DYLD_LIBRARY_PATH"):
        nd.inputs(step4b, out)
    monkeypatch.setattr(nd, "runner", lambda: dict(run))
    monkeypatch.setattr(
        nd.subprocess,
        "run",
        lambda argv, **kw: SimpleNamespace(stdout="", stderr="dyld: abort\n", returncode=-6),
    )
    with pytest.raises(SystemExit, match="exits -6 on --version"):
        nd.inputs(step4b, out)
    moved = blob.with_name("sha256-" + "0" * 64)
    blob.rename(moved)
    monkeypatch.setattr(nd, "runner", lambda: {**run, "model": str(moved)})
    with pytest.raises(SystemExit, match="not the one its name says"):
        nd.inputs(step4b, out)
    stored = json.loads(step4b.read_text(encoding="utf-8"))
    stored["cases"][4]["prompts"]["4096"]["sha256"] = "0" * 64
    step4b.write_text(json.dumps(stored), encoding="utf-8")
    monkeypatch.setattr(nd, "STEP4B_INPUTS_SHA256", nd.sha256(step4b))
    with pytest.raises(SystemExit, match=f"{nd.CASES[4]}: not step 4b's prompt at 4096"):
        nd.inputs(step4b, out)
    monkeypatch.setattr(nd, "STEP4B_INPUTS_SHA256", "0" * 64)
    with pytest.raises(SystemExit, match="not step 4b's inputs"):
        nd.inputs(step4b, out)
    assert not (out / "inputs.json").exists()


def test_the_inputs_refuse_a_worktree_that_is_not_clean(tmp_path, monkeypatch):
    step4b, run, blob, fitted, rendered, show, versions = _inputs_stand(tmp_path, monkeypatch)
    monkeypatch.setattr(wt, "git", lambda *args: "?? notes.txt" if args[0] == "status" else "c")
    with pytest.raises(SystemExit, match="the worktree is not clean"):
        nd.inputs(step4b, tmp_path / "out")
    assert (fitted, rendered) == ([], [])


# --- the blocks ---


def test_a_direct_block_starts_its_server_sends_every_call_rendered_and_its_gate_passes(
    tmp_path, monkeypatch
):
    out, facts, stand = _blocks(tmp_path, monkeypatch)
    assert stand.block(2, out) == 0
    path = out / "blocks" / "02.jsonl"
    lines = nd.lines_of(path)
    head, body, end = lines[0], lines[1:-1], lines[-1]
    assert (head["block"], head["arm"], head["stand"], head["machine"]) == (
        2,
        "ngram",
        [],
        {"cores": 4},
    )
    assert head["tool_sha256"] == nd.sha256(TOOL)
    assert head["inputs_sha256"] == nd.sha256(out / "inputs.json")
    assert [x["case_id"] for x in body] == ["warm-up", *nd.CASES]
    assert stand.bodies == [
        nd.completion_body(facts["options"], c["rendered"]) for c in nd.calls_of(facts, "ngram")
    ]
    assert [x["sent_sha256"] for x in body] == [
        c["rendered_sha256"] for c in nd.calls_of(facts, "ngram")
    ]
    assert body[3]["before"] == QUIET and body[3]["after"] == QUIET
    assert end["done"] and end["load_sec"] >= 0
    assert (end["rss_after_load_mib"], end["rss_max_after_calls_mib"]) == (2900.0, 2900.0)
    assert (stand.started, stand.stopped) == (1, 1)
    assert nd.check(2, path, facts, out) == []
    assert not (out / "blocks" / "02.partial.jsonl").exists()


def test_block_zero_sends_the_warm_up_and_three_through_ollama_holds_its_runner_and_unloads(
    tmp_path, monkeypatch
):
    out, facts, stand = _blocks(tmp_path, monkeypatch)
    assert stand.block(0, out) == 0
    path = out / "blocks" / "00.jsonl"
    lines = nd.lines_of(path)
    body, end = lines[1:-1], lines[-1]
    assert [x["case_id"] for x in body] == ["warm-up", *nd.CASES[:3]]
    assert stand.flats == [c["flat"] for c in nd.calls_of(facts, "ollama")]
    assert stand.bodies == [] and stand.started == 0
    assert end["runner"] == _restarted() and end["runner_differs"] == []
    assert end["unload"] == {"unload_sec": 1.5}
    assert nd.check(0, path, facts, out) == []
    monkeypatch.setattr(nd, "runner", lambda: {**_restarted(), "args": [*ARGS, "-t", "2"]})
    path.unlink()
    assert stand.block(0, out) == 0
    assert nd.check(0, path, facts, out) == ["Ollama's runner not the one the inputs read: args"]
    _rewrite(path, lambda lines: lines[-1].pop("runner_differs"))
    assert nd.check(0, path, facts, out) == [
        "Ollama's runner not the one the inputs read: not read"
    ]


@pytest.mark.parametrize(
    ("env", "reasons"),
    [
        ({"LLAMA_MEDIA_MARKER": "<__ollama_media_" + "3" * 32 + "__>"}, []),
        (
            {"DYLD_LIBRARY_PATH": "/opt/other"},
            ["Ollama's runner not the one the inputs read: env DYLD_LIBRARY_PATH"],
        ),
    ],
)
def test_block_zeros_runner_may_differ_from_the_inputs_one_only_by_its_media_marker(
    tmp_path, monkeypatch, env, reasons
):
    out, facts, stand = _blocks(tmp_path, monkeypatch)
    monkeypatch.setattr(nd, "runner", lambda: _restarted(**env))
    assert stand.block(0, out) == 0
    path = out / "blocks" / "00.jsonl"
    end = nd.lines_of(path)[-1]
    assert end["runner"] == _restarted(**env)
    assert end["runner"]["env"]["LLAMA_MEDIA_MARKER"] != MARKER
    assert nd.check(0, path, facts, out) == reasons


def test_a_stand_not_the_registered_one_stops_the_block_before_any_call(tmp_path, monkeypatch):
    out, facts, stand = _blocks(tmp_path, monkeypatch)
    monkeypatch.setattr(nd, "stand", lambda facts: ["Ollama 0.34.0"])
    assert stand.block(1, out) == nd.EXIT["stand"]
    lines = nd.lines_of(out / "blocks" / "01.partial.jsonl")
    assert len(lines) == 1 and lines[0]["stand"] == ["Ollama 0.34.0"]
    assert (stand.bodies, stand.started) == ([], 0)


def test_a_call_that_fails_still_stops_the_blocks_server(tmp_path, monkeypatch):
    out, facts, stand = _blocks(tmp_path, monkeypatch)
    stand.fail_at = nd.CASES[2]
    with pytest.raises(RuntimeError):
        stand.block(1, out)
    assert (stand.started, stand.stopped) == (1, 1)
    assert not (out / "blocks" / "01.jsonl").exists()


@pytest.mark.parametrize(
    ("how", "reason"),
    [
        (lambda lines: lines[0].update(block=2), "not the schedule's block"),
        (lambda lines: lines[0].update(tool_sha256="0" * 64), "another tool"),
        (lambda lines: lines[0].update(stand=["Ollama 0.34.0"]), "the stand: Ollama 0.34.0"),
        (lambda lines: lines.pop(3), "not the schedule's calls"),
        (lambda lines: lines.pop(-1), "no end line"),
        (lambda lines: lines[2].update(text="changed"), "no text or not its SHA-256"),
        (lambda lines: lines[2].update(sent_sha256="0" * 64), "another prompt"),
        (lambda lines: lines[2].update(truncated=True), "not a finished call"),
        (lambda lines: lines[2].update(stop_type=None), "not a finished call"),
        (lambda lines: lines[2]["timings"].update(predicted_n=0), "no decode timings"),
        (lambda lines: lines[2].update(tokens_evaluated=1), "the prompt's tokens do not add up"),
        (
            lambda lines: (
                lines[2].update(tokens_evaluated=2500),
                lines[2]["timings"].update(prompt_n=2470),
            ),
            "2500 prompt tokens, not step 4b's 2401",
        ),
    ],
)
def test_the_gate_refuses_another_block_a_missing_call_or_an_unfinished_one(
    tmp_path, monkeypatch, how, reason
):
    out, facts, stand = _blocks(tmp_path, monkeypatch)
    stand.block(1, out)
    path = out / "blocks" / "01.jsonl"
    _rewrite(path, how)
    assert any(r.endswith(reason) for r in nd.check(1, path, facts, out)), reason


def test_the_gate_reads_the_prompt_a_direct_call_sent_and_its_tokens_against_step_4bs(
    tmp_path, monkeypatch
):
    out, facts, stand = _blocks(tmp_path, monkeypatch)
    wrong, other = facts["cases"][2], facts["cases"][3]
    body_of = nd.completion_body

    def swapped(options, prompt):
        return body_of(options, other["rendered"] if prompt == wrong["rendered"] else prompt)

    monkeypatch.setattr(nd, "completion_body", swapped)
    assert stand.block(1, out) == 0
    assert nd.check(1, out / "blocks" / "01.jsonl", facts, out) == [
        f"{wrong['case_id']}: another prompt",
        f"{wrong['case_id']}: {other['step4b_prompt_tokens']} prompt tokens, not step 4b's "
        f"{wrong['step4b_prompt_tokens']}",
    ]


@pytest.mark.parametrize(
    ("how", "reason"),
    [
        (lambda lines: lines[2].update(done_reason=None), "not a finished call"),
        (lambda lines: lines[2]["counters"].update(eval_count=0), "not a finished call"),
        (lambda lines: lines[2].update(sent_sha256="0" * 64), "another prompt"),
    ],
)
def test_the_gate_refuses_an_ollama_call_unfinished_or_on_another_prompt(
    tmp_path, monkeypatch, how, reason
):
    out, facts, stand = _blocks(tmp_path, monkeypatch)
    stand.block(0, out)
    path = out / "blocks" / "00.jsonl"
    _rewrite(path, how)
    assert nd.check(0, path, facts, out) == [f"{nd.CASES[0]}: {reason}"]


@pytest.mark.parametrize("change", ["none", "text", "prompt tokens", "answer tokens"])
def test_fidelity_holds_on_ollamas_text_and_token_counts_on_the_warm_up_and_three(
    tmp_path, monkeypatch, change
):
    rules = {}
    if change == "text":
        rules["text"] = lambda arm, c: "иначе" if arm == "ollama" and c == nd.CASES[2] else "ответ"
    out, facts, stand = _blocks(tmp_path, monkeypatch, **rules)
    if change == "prompt tokens":
        stand.ollama_extra[nd.CASES[2]] = 1
    stand.block(0, out)
    stand.block(1, out)
    if change == "answer tokens":
        _rewrite(
            out / "blocks" / "00.jsonl", lambda lines: lines[4]["counters"].update(eval_count=91)
        )
    got = nd.fidelity(out / "blocks" / "00.jsonl", out / "blocks" / "01.jsonl")
    assert [c["case_id"] for c in got["calls"]] == ["warm-up", *nd.CASES[:3]]
    assert got["reading"] == ("holds" if change == "none" else "fails")
    assert got["calls"][0] == {
        "case_id": "warm-up",
        "same_text": True,
        "prompt_tokens": [2400, 2400],
        "answer_tokens": [90, 90],
    }


# --- the series ---


def _series(tmp_path, monkeypatch, **rules):
    out, facts, stand = _blocks(tmp_path, monkeypatch, **rules)
    monkeypatch.setattr(nd, "idle", lambda first, own: True)
    monkeypatch.setattr(nd, "launch", lambda number, out: stand.block(number, out))
    monkeypatch.setattr(wt, "git", lambda *args: "")
    return out, facts, stand


def _log(out):
    return (out / "series.log").read_text(encoding="utf-8")


def test_the_series_runs_block_zero_then_abba_and_resumes_at_the_first_without_a_file(
    tmp_path, monkeypatch
):
    out, facts, stand = _series(tmp_path, monkeypatch)
    (out / "stop").touch()
    assert nd.series(out, 4) == nd.EXIT["stop"]
    (out / "stop").unlink()
    assert nd.series(out, 1) == 0
    assert sorted(p.name for p in (out / "blocks").glob("*.jsonl")) == ["00.jsonl", "01.jsonl"]
    assert _log(out).rstrip().endswith("blocks to 1 done") and "SERIES_DONE" not in _log(out)
    assert nd.series(out, 4) == 0
    assert sorted(p.name for p in (out / "blocks").glob("*.jsonl")) == [
        f"{n:02d}.jsonl" for n in range(5)
    ]
    log = _log(out)
    assert [x.split(" ", 1)[1] for x in log.splitlines() if "attempt" in x] == [
        "block 0 ollama, attempt 1",
        "block 1 base, attempt 1",
        "block 2 ngram, attempt 1",
        "block 3 ngram, attempt 1",
        "block 4 base, attempt 1",
    ]
    assert log.rstrip().endswith("SERIES_DONE") and (stand.started, stand.stopped) == (4, 4)
    assert nd.series(out, 4) == 0
    assert json.loads((out / "series.json").read_text(encoding="utf-8"))["attempts"] == {
        str(n): 1 for n in range(5)
    }
    _rewrite(out / "blocks" / "03.jsonl", lambda lines: lines.pop(4))
    assert nd.series(out, 4) == nd.EXIT["gate"]
    assert "block 3 kept but failing: not the schedule's calls" in _log(out)


@pytest.mark.parametrize("change", ["text", "prompt tokens"])
def test_block_one_off_ollamas_answers_stops_the_series_on_every_start(
    tmp_path, monkeypatch, change
):
    rules = {}
    if change == "text":
        rules["text"] = lambda arm, c: "иначе" if arm == "ollama" and c == nd.CASES[2] else "ответ"
    out, facts, stand = _series(tmp_path, monkeypatch, **rules)
    if change == "prompt tokens":
        stand.ollama_extra[nd.CASES[2]] = 1
    assert nd.series(out, 4) == nd.EXIT["fidelity"]
    assert (out / "blocks" / "01.jsonl").exists()
    assert not (out / "blocks" / "02.jsonl").exists()
    assert nd.series(out, 4) == nd.EXIT["fidelity"]
    assert _log(out).count("block 1 fidelity") == 2


def test_a_block_that_ends_on_an_error_is_tried_again_once_and_then_ends_the_series(
    tmp_path, monkeypatch
):
    # A stream error, a socket timeout or a server not ready in time ends the block's process
    # with exit 1 and its traceback in blocks.out: the series reads it as 8, twice as 9.
    out, facts, stand = _series(tmp_path, monkeypatch)

    def launch(number, out):
        stand.fail_at = nd.CASES[2] if number == 2 else None
        try:
            return stand.block(number, out)
        except RuntimeError:
            return 1

    monkeypatch.setattr(nd, "launch", launch)
    assert nd.series(out, 4) == nd.EXIT["gate"]
    assert nd.series(out, 4) == nd.EXIT["gate"]
    assert nd.series(out, 4) == nd.EXIT["twice"]
    assert "block 2 failed: exit 1" in _log(out) and "block 2 failed twice" in _log(out)
    assert sorted(p.name for p in (out / "rejected").iterdir()) == [
        "02-1-02.partial.jsonl",
        "02-2-02.partial.jsonl",
    ]


def test_a_sample_ollama_or_ps_did_not_answer_marks_its_question_disturbed_not_the_block(
    tmp_path, monkeypatch
):
    out, facts, stand = _series(tmp_path, monkeypatch)
    quiet, taken = nd.sample, []

    def sample(own):
        # The sixth sample of block 2, after its second question's call, finds Ollama down.
        taken.append(stand.arm)
        if taken.count("ngram") == 6:
            return {**dict.fromkeys(QUIET), "error": "ConnectionRefusedError"}
        return quiet(own)

    monkeypatch.setattr(nd, "sample", sample)
    assert nd.series(out, 4) == 0
    assert nd.read(out, tmp_path / "record") == 0
    record = json.loads((tmp_path / "record" / "record.json").read_text(encoding="utf-8"))
    assert record["readings"]["speed"]["disturbed"] == [nd.CASES[1]]
    assert record["readings"]["speed"]["readable"] == 12
    assert (record["blocks"]["2"]["sample_errors"], record["blocks"]["2"]["disturbed"]) == (1, 1)
    assert record["blocks"]["2"]["others_cpu_max"] == QUIET["others_cpu"]
    assert record["blocks"]["3"]["sample_errors"] == 0 and record["attempts"]["2"] == 1


@pytest.mark.parametrize("code", [5, 6])
def test_a_slow_block_or_a_wrong_stand_keep_their_exit_and_the_partial_file_is_put_aside(
    tmp_path, monkeypatch, code
):
    out, facts, stand = _series(tmp_path, monkeypatch)

    def launch(number, out):
        (out / "blocks" / f"{number:02d}.partial.jsonl").write_text("{}\n", encoding="utf-8")
        return code

    monkeypatch.setattr(nd, "launch", launch)
    assert nd.series(out, 4) == code
    assert [p.name for p in (out / "rejected").iterdir()] == ["00-1-00.partial.jsonl"]


def test_a_block_file_failing_its_gate_is_put_aside(tmp_path, monkeypatch):
    out, facts, stand = _series(tmp_path, monkeypatch)

    def launch(number, out):
        stand.block(number, out)
        _rewrite(out / "blocks" / f"{number:02d}.jsonl", lambda lines: lines.pop(2))
        return 0

    monkeypatch.setattr(nd, "launch", launch)
    assert nd.series(out, 4) == nd.EXIT["gate"]
    assert not (out / "blocks" / "00.jsonl").exists()
    assert [p.name for p in (out / "rejected").iterdir()] == ["00-1-00.jsonl"]
    assert "block 0 failed: not the schedule's calls" in _log(out)


def test_the_mac_not_idle_within_the_hour_or_another_tool_ends_the_series(tmp_path, monkeypatch):
    out, facts, stand = _series(tmp_path, monkeypatch)
    monkeypatch.setattr(nd, "idle", lambda first, own: False)
    assert nd.series(out, 4) == nd.EXIT["idle"]
    assert "the Mac not idle within an hour" in _log(out)
    assert not (out / "series.json").exists()
    (out / "series.json").write_text(
        json.dumps({"tool_sha256": "0" * 64, "attempts": {}}), encoding="utf-8"
    )
    assert nd.series(out, 4) == nd.EXIT["stand"]
    assert "another tool started this series" in _log(out)


def test_a_worktree_not_clean_at_the_start_or_before_a_block_ends_the_series(tmp_path, monkeypatch):
    out, facts, stand = _series(tmp_path, monkeypatch)
    # A file appears in the worktree once block 1 is written.
    monkeypatch.setattr(
        wt, "git", lambda *args: "?? notes.txt" if (out / "blocks" / "01.jsonl").exists() else ""
    )
    assert nd.series(out, 4) == nd.EXIT["stand"]
    assert sorted(p.name for p in (out / "blocks").glob("*.jsonl")) == ["00.jsonl", "01.jsonl"]
    assert _log(out).rstrip().endswith("the worktree is not clean")
    assert nd.series(out, 4) == nd.EXIT["stand"]
    attempts = json.loads((out / "series.json").read_text(encoding="utf-8"))["attempts"]
    assert attempts == {"0": 1, "1": 1}


class Hung:
    """A stand-in block process that never ends unless it is killed."""

    last = None

    def __init__(self, command, **kwargs):
        self.command, self.returncode = command, None
        Hung.last = self

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9

    def wait(self):
        return self.returncode


@pytest.mark.parametrize("number", [0, 2])
def test_launch_kills_a_stalled_block_its_direct_server_and_for_block_zero_ollamas_model(
    tmp_path, monkeypatch, number
):
    out = tmp_path / "out"
    (out / "blocks").mkdir(parents=True)
    killed, unloaded = [], []
    monkeypatch.setattr(nd.subprocess, "Popen", Hung)
    monkeypatch.setattr(nd, "POLL", 0.01)
    monkeypatch.setattr(nd, "START_LIMIT", 0.05)
    monkeypatch.setattr(nd, "servers_on_port", lambda: [4242])
    monkeypatch.setattr(nd.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr(wt, "unload", lambda: unloaded.append(True) or {})
    started = time.monotonic()
    assert nd.launch(number, out) == nd.EXIT["slow"]
    assert time.monotonic() - started < 30
    assert Hung.last.returncode == -9
    assert Hung.last.command[1:] == ["-u", str(TOOL), "block", str(number), str(out)]
    assert killed == [(4242, nd.signal.SIGTERM)]
    assert unloaded == ([True] if number == 0 else [])


def test_launch_returns_the_blocks_own_exit(tmp_path, monkeypatch):
    class Ended(Hung):
        def __init__(self, command, **kwargs):
            super().__init__(command, **kwargs)
            self.returncode = 6

    (tmp_path / "blocks").mkdir()
    monkeypatch.setattr(nd.subprocess, "Popen", Ended)
    assert nd.launch(3, tmp_path) == 6


# --- the reading ---


def _row(case_id, base_ms, ngram_ms, disturbed=False, texts=None):
    blocks = {}
    for number in ("1", "2", "3", "4"):
        ngram = nd.SCHEDULE[int(number)] == "ngram"
        ms = ngram_ms if ngram else base_ms
        blocks[number] = {
            "text_sha256": nd.digest((texts or {}).get(number, "a")),
            "predicted_n": 90,
            "predicted_ms": ms,
            "wall_sec": round(57.6 + ms / 1000, 3),
            "draft_n": 40 if ngram else 0,
            "draft_n_accepted": 30 if ngram else 0,
        }
    return {"case_id": case_id, "blocks": blocks, "disturbed": disturbed}


def test_speed_sets_each_arms_two_blocks_of_ms_a_token_against_the_others_by_the_sign_test():
    rows = [_row(c, 19200.0, 14400.0) for c in nd.CASES[:11]]
    rows += [_row(c, 19200.0, 21600.0) for c in nd.CASES[11:]]
    got = nd.speed(rows)
    assert (got["questions"], got["readable"], got["faster"], got["slower"]) == (13, 13, 11, 2)
    assert got["p"] == round(wt.sign_p(11, 2), 6) == 0.022461 and got["reading"] == "faster"
    assert got["base_ms_per_token_median"] == round(19200 / 90, 3)
    assert got["ngram_ms_per_token_median"] == round(14400 / 90, 3)
    assert got["saved_decode_sec_median"] == 4.8 and got["ratio_median"] == round(4 / 3, 3)
    assert (got["base_wall_sec_median"], got["ngram_wall_sec_median"]) == (76.8, 72.0)
    ten = [_row(c, 19200.0, 14400.0) for c in nd.CASES[:10]]
    ten += [_row(c, 19200.0, 21600.0) for c in nd.CASES[10:]]
    assert nd.speed(ten)["reading"] == "no detected difference"
    slow = [_row(c, 19200.0, 21600.0) for c in nd.CASES[:11]]
    slow += [_row(c, 19200.0, 14400.0) for c in nd.CASES[11:]]
    assert nd.speed(slow)["reading"] == "slower"
    few = [_row(c, 19200.0, 14400.0, disturbed=i < 4) for i, c in enumerate(nd.CASES)]
    got = nd.speed(few)
    assert (got["readable"], got["reading"]) == (9, nd.NOT_EVIDENCE)
    assert got["disturbed"] == list(nd.CASES[:4])


def test_speed_reads_ten_readable_questions_and_counts_a_tie_on_neither_side():
    ten = [_row(c, 19200.0, 14400.0, disturbed=i >= 10) for i, c in enumerate(nd.CASES)]
    got = nd.speed(ten)
    assert (got["readable"], got["faster"], got["slower"]) == (10, 10, 0)
    assert got["p"] == round(wt.sign_p(10, 0), 6) and got["reading"] == "faster"
    # Four ties: on neither side, p is 9 of 9 untied (0.0039), not 9 of 13 (0.27).
    ties = [_row(c, 19200.0, 14400.0) for c in nd.CASES[:9]]
    ties += [_row(c, 19200.0, 19200.0) for c in nd.CASES[9:]]
    got = nd.speed(ties)
    assert (got["readable"], got["faster"], got["slower"]) == (13, 9, 0)
    assert got["faster"] + got["slower"] < got["readable"]
    assert got["p"] == round(wt.sign_p(9, 0), 6) == 0.003906 and got["reading"] == "faster"


def test_equality_wants_the_base_to_repeat_itself_and_reads_every_base_ngram_pair():
    same = [_row(c, 1.0, 1.0) for c in nd.CASES]
    assert nd.equality(same) == {
        "questions": 13,
        "repeat": {"base": 13, "ngram": 13},
        "pairs": {"1-2": 13, "4-3": 13, "1-3": 13, "4-2": 13},
        "reading": "byte-equal",
    }
    drift = [*same[:12], _row(nd.CASES[12], 1.0, 1.0, texts={"4": "b"})]
    assert nd.equality(drift)["reading"] == nd.NOT_EVIDENCE
    differ = [*same[:12], _row(nd.CASES[12], 1.0, 1.0, texts={"2": "b", "3": "b"})]
    got = nd.equality(differ)
    assert got["repeat"] == {"base": 13, "ngram": 13} and got["reading"] == "differ"
    assert got["pairs"] == {"1-2": 12, "4-3": 12, "1-3": 12, "4-2": 12}


def test_acceptance_sums_each_ngram_blocks_drafted_and_accepted_tokens():
    got = nd.acceptance([_row(c, 1.0, 1.0) for c in nd.CASES])
    assert got == {n: {"draft_n": 520, "draft_n_accepted": 390, "rate": 0.75} for n in ("2", "3")}
    rows = [_row(c, 1.0, 1.0) for c in nd.CASES]
    for row in rows:
        row["blocks"]["3"].update(draft_n=0, draft_n_accepted=0)
    assert nd.acceptance(rows)["3"] == {"draft_n": 0, "draft_n_accepted": 0, "rate": None}


@pytest.mark.parametrize(
    ("fidelity", "pace", "same", "want"),
    [
        ("fails", "faster", "byte-equal", "NOT_EVIDENCE"),
        ("holds", "NOT_EVIDENCE", "byte-equal", "NOT_EVIDENCE"),
        ("holds", "no detected difference", "byte-equal", "not faster"),
        ("holds", "slower", "byte-equal", "not faster"),
        ("holds", "faster", "NOT_EVIDENCE", "NOT_EVIDENCE"),
        ("holds", "faster", "byte-equal", "faster and byte-equal"),
        ("holds", "faster", "differ", "faster, answers differ"),
    ],
)
def test_the_outcome_wants_fidelity_then_speed_then_reads_the_bytes(fidelity, pace, same, want):
    readings = {
        "fidelity": {"reading": fidelity},
        "speed": {"reading": pace},
        "equality": {"reading": same},
    }
    assert nd.outcome(readings) == want


def test_the_read_writes_numbers_and_hashes_and_no_text_of_a_prompt_or_an_answer(
    tmp_path, monkeypatch
):
    first = nd.CASES[0]
    out, facts, stand = _series(
        tmp_path,
        monkeypatch,
        text=lambda arm, c: f"answer to {c}" + (" ещё" if arm == "ngram" and c == first else ""),
    )
    assert nd.series(out, 4) == 0
    target = tmp_path / "record"
    assert nd.read(out, target) == 0
    record = json.loads((target / "record.json").read_text(encoding="utf-8"))
    rows = nd.lines_of(target / "rows.jsonl")
    assert record["outcome"] == "faster, answers differ"
    readings = record["readings"]
    assert readings["fidelity"]["reading"] == "holds"
    assert readings["equality"]["pairs"] == {"1-2": 12, "4-3": 12, "1-3": 12, "4-2": 12}
    assert readings["speed"]["faster"] == 13 and readings["speed"]["reading"] == "faster"
    assert readings["acceptance"]["2"]["rate"] == 0.75
    assert [r["case_id"] for r in rows] == list(nd.CASES)
    assert rows[0]["first_difference"] == dict.fromkeys(
        ("1-2", "4-3", "1-3", "4-2"), len(f"answer to {first}")
    )
    assert rows[1]["first_difference"] == {}
    assert set(rows[0]["ollama"]) == {"text_sha256", "done_reason", "wall_sec", *wt.COUNTERS}
    assert "ollama" in rows[2] and "ollama" not in rows[3]
    assert rows[0]["blocks"]["2"]["draft_n_accepted"] == 30
    assert record["attempts"] == {str(n): 1 for n in range(5)} and record["rejected"] == []
    assert record["inputs"]["calls"][0] == {
        k: facts["warm_up"][k] for k in ("case_id", "flat_sha256", "rendered_sha256")
    }
    assert record["blocks"]["2"]["settings"] == {"seed": nd.SEED}
    assert record["blocks"]["0"]["unload_sec"] == 1.5
    written = (target / "record.json").read_text(encoding="utf-8")
    written += (target / "rows.jsonl").read_text(encoding="utf-8")
    assert "answer to" not in written and "question " not in written


def test_a_series_stopped_by_fidelity_reads_blocks_zero_and_one_only_as_not_evidence(
    tmp_path, monkeypatch
):
    out, facts, stand = _series(
        tmp_path,
        monkeypatch,
        text=lambda arm, c: "иначе" if arm == "ollama" and c == nd.CASES[1] else "ответ",
    )
    assert nd.series(out, 4) == nd.EXIT["fidelity"]
    target = tmp_path / "record"
    assert nd.read(out, target) == 0
    record = json.loads((target / "record.json").read_text(encoding="utf-8"))
    assert record["outcome"] == nd.NOT_EVIDENCE
    assert sorted(record["readings"]) == ["fidelity"] and sorted(record["blocks"]) == ["0", "1"]
    calls = record["readings"]["fidelity"]["calls"]
    assert [c["same_text"] for c in calls] == [True, True, False, True]
    assert (target / "rows.jsonl").read_text(encoding="utf-8") == ""


def test_the_read_refuses_a_series_neither_done_nor_stopped_by_fidelity(tmp_path, monkeypatch):
    out, facts, stand = _series(tmp_path, monkeypatch)
    assert nd.series(out, 2) == 0
    with pytest.raises(SystemExit, match="block 3: no file"):
        nd.read(out, tmp_path / "record")


# --- the spec ---


def test_the_tool_measures_what_the_spec_registers():
    spec = (ROOT / nd.SPEC).read_text(encoding="utf-8")
    for phrase in ("registered before the first request", "Forecast, written before the first"):
        assert phrase in spec, phrase
    assert (nd.SEED, nd.FIDELITY, nd.MIN_READABLE, nd.ALPHA, nd.PORT) == (1030, 3, 10, 0.05, 18093)
    limits = (nd.START_LIMIT, nd.QUESTION_LIMIT, nd.IDLE_LIMIT, nd.BUSY, nd.LOAD_LIMIT)
    assert limits == (300, 900, 3600, 100.0, 2.0)
    assert nd.EXIT == {
        "stop": 3,
        "idle": 4,
        "slow": 5,
        "stand": 6,
        "fidelity": 7,
        "gate": 8,
        "twice": 9,
    }
    listed = dict(re.findall(r"- `([^`]+)` `([0-9a-f]{64})`", spec))
    for name in (
        "reports/stage4-step5a-ngram/tools/ngram_decode.py",
        "tests/test_stage4_step5a_ngram_tools.py",
    ):
        assert listed[name] == hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), name
