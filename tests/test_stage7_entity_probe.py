"""reports/stage7/tools/entity_probe.py: the choice, the check, the stop rule, gate G2 and a run.

docs/specs/stage7-entity-probe.md. Synthetic fixtures only: the archive's chunks and the model's
outputs are made up, and the model is a fake Ollama on a local port, whose replies move the
probe's clock in exact fractions; pgrep, ps, the load average, the CI lock and the platform are
fakes too: no network, model or Mac service. The planted text, in every chunk, every output and
the runner's command line, must never reach a file or the log.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import math
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Callable, Iterator
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports" / "stage7" / "tools" / "entity_probe.py"
SPEC = ROOT / "docs" / "specs" / "stage7-entity-probe.md"
PLANTED = "PLANTED-текст"


def load(path: Path, name: str) -> Any:
    """A tool as a module of its own name; the sys.path a tool extends is given back."""
    saved = list(sys.path)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = saved
    return module


probe = load(TOOL, "stage7_entity_probe")
LINE = probe.DAY / probe.N_MULTIHOP
N = probe.N_MULTIHOP
MODEL = probe.MODEL
OWN = f"{os.getpid()}\n{os.getppid()}\n"  # pgrep's own match: the probe and its parent
STRANGER = max(os.getpid(), os.getppid()) + 1
RUNNER_PID = STRANGER + 10
OMIT: Any = object()  # a field the fake leaves out of its reply
REAL_TIMEOUT = 1.0  # a chat the test lets time out waits this long, not 900 s
STALL = 3.0
FILES = ("launch.json", "chunks.jsonl", "end.json")


# --- the choice and the order ------------------------------------------------------------------


def test_the_picks_are_evenly_spaced_from_the_first_chunk() -> None:
    chosen = probe.picks(N)
    assert chosen == [i * N // 100 for i in range(100)]
    assert (chosen[0], chosen[1], chosen[-1]) == (0, 112, 11_118)
    assert {b - a for a, b in zip(chosen, chosen[1:], strict=False)} == {112, 113}
    assert N - 1 not in chosen
    assert probe.picks(101) == list(range(100))
    assert probe.picks(250)[:4] == [0, 2, 5, 7]
    with pytest.raises(ValueError):
        probe.picks(100)


def test_every_tenth_runs_first_so_each_look_spans_the_list() -> None:
    order = probe.run_order()
    assert sorted(order) == list(range(100))
    assert order[:12] == [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 1, 11]
    for n in (*probe.CHECKPOINTS, 100):
        assert {pick // 10 for pick in order[:n]} == set(range(10)), n


# --- the output's check and its counts ---------------------------------------------------------

OUTPUTS = {
    '["Alpha Corp", "Beta"]': "ok",
    '  ```json\n["Alpha Corp"]\n```  ': "ok",
    "[]": "ok",
    '["Ёлка-2", "ёлка 2", "Gamma"]': "ok",
    "[" + ", ".join(f'"e{i}"' for i in range(12)) + "]": "ok",
    '["' + "x" * 128 + '"]': "ok",
    "": "empty",
    "   ": "empty",
    "Alpha, Beta": "not_json",
    '["Alpha"': "not_json",
    '{"entities": ["Alpha"]}': "schema",
    '"Alpha"': "schema",
    "[" + ", ".join(f'"e{i}"' for i in range(13)) + "]": "schema",
    '["' + "x" * 129 + '"]': "schema",
    '["Alpha", " "]': "schema",
    '["Alpha", 2]': "schema",
    '[["Alpha"]]': "schema",
}


def test_validity_is_the_cache_rule_with_its_reason() -> None:
    for output, reason in OUTPUTS.items():
        assert probe.validate(output)[0] == reason, output
    assert probe.validate(None) == ("empty", None)


def test_validity_and_keys_agree_with_the_product() -> None:
    """The product's own rule and normaliser, on outputs that touch none of its dictionaries."""
    from ingestion.entity_extraction import EXTRACT_SCHEMA, _entities
    from ingestion.entity_normalization import normalize_entities

    assert probe.SCHEMA == EXTRACT_SCHEMA
    for output in OUTPUTS:
        try:
            expected: list[str] | None = _entities(output)
        except ValueError:
            expected = None
        reason, values = probe.validate(output)
        assert (reason == "ok") == (expected is not None), output
        if values is not None:
            assert probe.keys(values) == expected == normalize_entities(values), output


def test_the_counts_are_the_loaders_keys_and_their_pairs() -> None:
    values = ["Apple Inc.", "apple inc", "Tim Cook", "Ёлка-2", "___", "a_b"]
    assert probe.keys(values) == ["apple inc", "tim cook", "ёлка 2", "a b"]
    assert probe.keys([f"Name {i}" for i in range(15)]) == [f"name {i}" for i in range(12)]
    assert math.comb(len(probe.keys(values)), 2) == 6


# --- the interval, the stop rule, G2 -----------------------------------------------------------


def test_the_t_quantiles_are_the_tables() -> None:
    table = {1: 12.7062, 9: 2.2622, 19: 2.0930, 30: 2.0423, 39: 2.0227, 69: 1.9949, 99: 1.9842}
    for df, value in table.items():
        assert abs(probe.t975(df) - value) < 5e-5, df


def test_the_t_quantiles_agree_with_scipy() -> None:
    stats = pytest.importorskip("scipy.stats")
    for df in range(1, 100):
        assert abs(probe.t975(df) - stats.t.ppf(0.975, df)) < 1e-9, df


def test_more_than_five_invalid_stop_the_run_at_once() -> None:
    seconds = [5.0] * 6
    assert probe.stop_at(seconds, [False] * 5 + [True]) is None
    assert probe.stop_at(seconds, [False] * 6) == "invalid"
    valid = [True, False] * 6
    assert probe.first_stop([5.0] * 12, valid) == ("invalid", 12)
    # At the same chunk the invalid outputs name the stop before the lower bound.
    assert probe.stop_at([20.0] * 10, [False] * 6 + [True] * 4) == "invalid"


def test_the_seconds_of_a_hundred_chunks_at_the_line_stop_the_run_at_once() -> None:
    assert probe.TOTAL * LINE == pytest.approx(769.2993, abs=1e-4)
    assert probe.stop_at([153.8] * 5, [True] * 5) is None
    assert probe.stop_at([153.9] * 5, [True] * 5) == "seconds"
    assert probe.first_stop([100.0] * 9, [True] * 9) == ("seconds", 8)
    # One chunk cut at the cap is past the 100's line alone, at one chunk as at 99.
    assert probe.stop_at([probe.CHUNK_CAP], [False]) == "seconds"
    assert probe.first_stop([5.0] * 98 + [probe.CHUNK_CAP], [True] * 98 + [False]) == (
        "seconds",
        99,
    )


def test_the_lower_bound_is_read_at_the_checkpoints_only() -> None:
    valid = [True] * 100
    assert probe.first_stop([7.694] * 100, valid) == ("lower", 10)
    assert probe.stop_at([7.694] * 9, valid[:9]) is None
    assert probe.first_stop([7.692] * 100, valid) is None
    # 7 and 9 in turn: the lower bound is 7.246 at 10, 7.520 at 20, 7.676 at 40, 7.760 at 70.
    alternating = [7.0 if i % 2 == 0 else 9.0 for i in range(100)]
    assert [round(probe.bounds(alternating[:n])[1], 3) for n in probe.CHECKPOINTS] == [
        7.246,
        7.520,
        7.676,
        7.760,
    ]
    assert probe.first_stop(alternating, valid) == ("lower", 70)
    for n in range(41, 70):
        assert probe.stop_at(alternating[:n], valid[:n]) is None, n


def test_the_rule_never_stops_the_hundredth() -> None:
    assert probe.stop_at([50.0] * 100, [False] * 100) is None
    assert probe.first_stop([5.0] * 100, [True] * 100) is None


def test_g2_at_its_edges() -> None:
    valid = [True] * 100
    assert probe.g2([LINE] * 100, valid)["verdict"] == "passed"
    assert probe.g2([7.692] * 100, valid)["verdict"] == "passed"
    assert probe.g2([7.694] * 100, valid)["failed_by"] == ["seconds"]
    spread = [5.0, 7.0] * 50
    upper = probe.g2(spread, valid)["upper_sec"]
    assert upper == pytest.approx(6.0 + 1.984217 * statistics_sd(spread) / 10, abs=1e-5)
    ninety_five = [True] * 95 + [False] * 5
    assert probe.g2([5.0] * 100, ninety_five)["verdict"] == "passed"
    ninety_four = [True] * 94 + [False] * 6
    assert probe.g2([5.0] * 100, ninety_four)["failed_by"] == ["valid"]
    assert probe.g2([8.0] * 100, ninety_four)["failed_by"] == ["seconds", "valid"]
    with pytest.raises(ValueError):
        probe.g2([5.0] * 99, valid[:99])


def test_the_line_rounded_to_six_places_would_stop_the_run() -> None:
    """Why the rows and the rules keep the seconds unrounded."""
    valid = [True] * 100
    assert probe.first_stop([LINE] * 100, valid) is None
    assert probe.g2([LINE] * 100, valid)["verdict"] == "passed"
    assert round(LINE, 6) > LINE
    assert probe.first_stop([round(LINE, 6)] * 100, valid) == ("lower", 10)


def statistics_sd(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def lognormal_runs(ratio: float, cv: float, count: int) -> list[list[float]]:
    """`count` runs of 100 seeded lognormal seconds, unrounded, of mean `ratio` times the line."""
    rng = random.Random(20261028)
    sigma2 = math.log(1 + cv * cv)
    mu = math.log(ratio * LINE) - sigma2 / 2
    return [[rng.lognormvariate(mu, math.sqrt(sigma2)) for _ in range(100)] for _ in range(count)]


def test_the_looks_rarely_stop_a_run_whose_hundred_would_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The spec's simulation as it states it: below the line the lower bound stops almost
    nothing, no stop reverses what all 100 would read, far above it the first look stops, and at
    1.3 times the line the later looks end a run sooner than the look at 10 alone."""
    valid = [True] * 100

    def read(runs: list[list[float]]) -> list[tuple[Any, str]]:
        return [(probe.first_stop(s, valid), probe.g2(s, valid)["verdict"]) for s in runs]

    below, on = read(lognormal_runs(0.9, 0.6, 400)), read(lognormal_runs(1.0, 0.6, 400))
    assert sum(1 for stop, _ in below if stop and stop[0] == "lower") <= 4
    assert sum(1 for stop, _ in on if stop and stop[0] == "lower") <= 20
    assert all(verdict == "failed" for stop, verdict in below + on if stop)
    assert all(probe.first_stop(s, valid) == ("lower", 10) for s in lognormal_runs(2.6, 0.3, 200))
    slower = lognormal_runs(1.3, 0.6, 200)

    def mean_chunks() -> float:
        stops = [probe.first_stop(s, valid) for s in slower]
        assert all(stops)
        return sum(stop[1] for stop in stops) / len(stops)

    four = mean_chunks()
    monkeypatch.setattr(probe, "CHECKPOINTS", (10,))
    alone = mean_chunks()
    assert four < 50 and alone > 60


# --- pgrep -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "out", "count"),
    [
        (1, "", 0),
        (0, OWN, 0),
        (0, OWN + f"{STRANGER}\n", 1),
        (0, f"{STRANGER}\n{STRANGER + 1}\n", 2),
        (0, "12 x\n", None),
        (0, "٣\n", None),
        (2, "", None),
        (3, f"{STRANGER}\n", None),
    ],
)
def test_pgrep_counts_pids_besides_its_own_and_a_failure_is_none(
    monkeypatch: pytest.MonkeyPatch, code: int, out: str, count: int | None
) -> None:
    calls: list[list[str]] = []

    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, code, out, "")

    monkeypatch.setattr(probe, "_run", run)
    assert probe.processes(probe.OTHERS) == count
    assert calls == [["pgrep", "-f", probe.OTHERS]]


@pytest.mark.parametrize(
    "error", [subprocess.TimeoutExpired("pgrep", 30), FileNotFoundError("pgrep"), ValueError("x")]
)
def test_pgrep_that_cannot_run_is_none(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise error

    monkeypatch.setattr(probe, "_run", run)
    assert probe.processes(probe.IDLE) is None


# --- a fake Ollama, a fake Mac and a synthetic archive -----------------------------------------


def output_for(index: int) -> str:
    return json.dumps([f"{PLANTED} {index}", "Shared Name", "Другое имя"], ensure_ascii=False)


class Answer:
    """A chat's reply other than an ordinary one: a status and a raw body, a connection closed
    without a reply, or a stall in real time and no reply."""

    def __init__(
        self, raw: bytes = b"", status: int = 200, drop: bool = False, stall: float = 0.0
    ) -> None:
        self.raw, self.status, self.drop, self.stall = raw, status, drop, stall


def body_of(value: Any, status: int = 200) -> Answer:
    return Answer(json.dumps(value, ensure_ascii=False).encode("utf-8"), status)


class Fake:
    """Ollama's five routes the probe uses, and the Mac around them. A chat's reply is
    reply(number, chunk index): its seconds, added to the probe's clock, and its content, a
    string or an Answer; override(number) changes its other fields, load_override the load's
    (OMIT leaves one out).
    delay(path, chats so far) is the seconds a GET takes on the clock. pgrep(pattern, chats so
    far) is pgrep's exit code and output; ps reads runner_args for the runner's pid."""

    def __init__(self) -> None:
        self.reply: Callable[[int, int], tuple[float, str | Answer]] = lambda number, index: (
            5.0 + (index % 7) / 10,
            output_for(index),
        )
        self.pgrep: Callable[[str, int], tuple[int, str]] = lambda pattern, chats: self.found(
            pattern
        )
        self.runners = [RUNNER_PID]
        self.runner_args = (
            f"/usr/local/bin/llama-server --model /{PLANTED}/blobs/sha256-0 --port 60186"
            " --host 127.0.0.1 -c 4096 -np 1 --flash-attn -b 512"
        )
        self.ps_args: list[int] = []
        self.delay: Callable[[str, int], float] = lambda path, chats: 0.0
        self.override: Callable[[int], dict[str, Any]] = lambda number: {}
        self.load_override: dict[str, Any] = {}
        self.load_ns: Callable[[int], int] = lambda number: 2_000_000
        self.version = "0.33.2"
        self.loaded: list[str] = []
        self.others: list[str] = []
        self.digest = probe.MODEL_DIGEST
        self.digest_changes_after: int | None = None
        self.tags_fail_after: int | None = None
        self.ps_fail_at: int | None = None
        self.size_vram = 0
        self.context_length = 4096
        self.load_seconds = 31.0
        self.tags_seconds = 0.0
        self.ps_seconds = 0.0
        self.unload_polls: int | None = 0  # the looks after keep_alive 0 that still see it
        self.unload_requested = False
        self.polls = 0
        self.real_timeout_for: set[int] = set()
        self.chats: list[dict[str, Any]] = []
        self.generates: list[dict[str, Any]] = []
        self.patterns: list[str] = []
        self.timeouts: list[tuple[str, float]] = []
        self.clock = Fraction(0)
        self.mutex = threading.Lock()
        self.ci_lock = Path()
        self.url = ""

    def tick(self, seconds: float) -> None:
        with self.mutex:
            self.clock += Fraction(seconds)

    def found(self, pattern: str) -> tuple[int, str]:
        """pgrep on an idle Mac: its own match for the idle rule, the runner while the model is
        loaded, nothing else."""
        if pattern == probe.IDLE:
            return 0, OWN
        if pattern == probe.RUNNER and MODEL in self.loaded and self.runners:
            return 0, "".join(f"{pid}\n" for pid in self.runners)
        return 1, ""

    def ps(self) -> list[dict[str, Any]]:
        with self.mutex:
            self.clock += Fraction(self.ps_seconds)
            if self.unload_requested:
                self.polls += 1
                if self.unload_polls is not None and self.polls > self.unload_polls:
                    self.loaded = []
            names = self.loaded + self.others
        return [
            {
                "name": name,
                "model": name,
                "size": 3_400_000_000,
                "size_vram": self.size_vram,
                "digest": self.digest,
                "context_length": self.context_length,
            }
            for name in names
        ]


def handler_for(fake: Fake) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            pass

        def send(self, status: int, data: bytes) -> None:
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except OSError:
                pass  # the probe gave up on this request

        def answer(self, body: Any) -> None:
            self.send(200, json.dumps(body, ensure_ascii=False).encode("utf-8"))

        def do_GET(self) -> None:
            chats = len(fake.chats)
            fake.tick(fake.delay(self.path, chats))
            if self.path == "/api/version":
                self.answer({"version": fake.version})
            elif self.path == "/api/ps":
                if fake.ps_fail_at is not None and chats == fake.ps_fail_at:
                    self.send(500, b'{"error": "down"}')
                else:
                    self.answer({"models": fake.ps()})
            elif self.path == "/api/tags":
                fake.tick(fake.tags_seconds)
                if fake.tags_fail_after is not None and chats > fake.tags_fail_after:
                    self.send(500, b'{"error": "down"}')
                    return
                changed = fake.digest_changes_after
                digest = "f" * 64 if changed is not None and chats > changed else fake.digest
                self.answer({"models": [{"name": MODEL, "digest": digest}]})
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path == "/api/generate":
                fake.generates.append(body)
                if body.get("keep_alive") == 0:
                    with fake.mutex:
                        fake.unload_requested = True
                        if fake.unload_polls == 0:
                            fake.loaded = []
                    self.answer({"model": MODEL, "done": True, "done_reason": "unload"})
                else:
                    fake.tick(fake.load_seconds)
                    fake.loaded = [MODEL]
                    loaded = {
                        "model": MODEL,
                        "done": True,
                        "done_reason": "load",
                        "load_duration": int(fake.load_seconds * 1e9),
                    }
                    self.answer(changed(loaded, fake.load_override))
                return
            if self.path != "/api/chat":
                self.send_error(404)
                return
            with fake.mutex:
                number = len(fake.chats)
                fake.chats.append(body)
            match = re.search(r"chunk (\d+) body", body["messages"][0]["content"])
            assert match
            seconds, content = fake.reply(number, int(match.group(1)))
            fake.tick(seconds)
            if isinstance(content, Answer):
                if content.stall:
                    time.sleep(content.stall)
                if content.drop or content.stall:
                    self.close_connection = True
                else:
                    self.send(content.status, content.raw)
                return
            ns = int(seconds * 1e9)
            reply = {
                "model": MODEL,
                "message": {"role": "assistant", "content": content},
                "done": True,
                "done_reason": "stop",
                "total_duration": ns,
                "load_duration": fake.load_ns(number),
                "prompt_eval_count": 210,
                "prompt_eval_duration": ns // 3,
                "eval_count": 60,
                "eval_duration": ns - ns // 3,
            }
            self.answer(changed(reply, fake.override(number)))

    return Handler


def changed(reply: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """The reply with each change applied; OMIT leaves its field out."""
    for key, value in changes.items():
        if value is OMIT:
            reply.pop(key, None)
        else:
            reply[key] = value
    return reply


def run_for(fake: Fake) -> Callable[..., subprocess.CompletedProcess[str]]:
    """pgrep and ps as the probe calls them: each with a timeout, never raising on a code."""

    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert kwargs == {
            "capture_output": True,
            "text": True,
            "timeout": probe.CALL_CAP,
            "check": False,
        }
        if args[0] == "ps":
            assert args[:5] == ["ps", "-ww", "-o", "args=", "-p"] and len(args) == 6, args
            fake.ps_args.append(int(args[5]))
            if int(args[5]) in fake.runners and MODEL in fake.loaded:
                return subprocess.CompletedProcess(args, 0, fake.runner_args + "\n", "")
            return subprocess.CompletedProcess(args, 1, "", "")
        assert args[:2] == ["pgrep", "-f"] and len(args) == 3, args
        fake.patterns.append(args[2])
        code, out = fake.pgrep(args[2], len(fake.chats))
        return subprocess.CompletedProcess(args, code, out, "")

    return run


def chunk_text(index: int) -> str:
    return f"[{PLANTED} {index // 14} › part]\n{PLANTED} chunk {index} body, text {index % 14}."


@pytest.fixture(scope="module")
def archive(tmp_path_factory: pytest.TempPathFactory) -> Path:
    chunks = [
        {"page_content": chunk_text(i), "metadata": {"source": f"{PLANTED}-{i // 14}.md"}}
        for i in range(N)
    ]
    data = json.dumps(
        {"tenant_id": "ext_multihoprag", "chunks": chunks},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    path = tmp_path_factory.mktemp("archive") / "chunks.json.gz"
    path.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))
    return path


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, archive: Path, tmp_path: Path) -> Iterator[Fake]:
    state = Fake()
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(state))
    state.url = f"http://127.0.0.1:{server.server_address[1]}"
    state.ci_lock = tmp_path / "ci_local" / ".lock_ci-local"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    real = urllib.request.urlopen

    def opener(request: urllib.request.Request, timeout: float) -> Any:
        """The probe's timeout is recorded; a chat the test lets time out waits a second."""
        state.timeouts.append((request.selector, timeout))
        if request.selector == "/api/chat" and len(state.chats) in state.real_timeout_for:
            timeout = REAL_TIMEOUT
        return real(request, timeout=timeout)

    replaced: dict[str, Any] = {
        "ARCHIVE_SHA256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "OLLAMA": state.url,
        "LOCK": state.ci_lock,
        "_urlopen": opener,
        "_clock": lambda: state.clock,
        "_sleep": state.tick,
        "_run": run_for(state),
        "_loadavg": lambda: [0.5, 0.5, 0.5],
        "_swap_used_mib": lambda: 1024.0,
        "_system": lambda: "Darwin",
        "_machine": lambda: "x86_64",
    }
    for name, value in replaced.items():
        monkeypatch.setattr(probe, name, value)
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()


def run_probe(fake: Fake, archive: Path, run_dir: Path) -> int:
    return probe.main(["run", str(run_dir), "--archive", str(archive), "--ollama", fake.url])


def read_probe(run_dir: Path) -> dict[str, Any]:
    out = run_dir.parent / f"{run_dir.name}.probe.json"
    assert probe.main(["read", str(out), str(run_dir)]) == 0
    return json.loads(out.read_bytes().decode("utf-8"))


def rows_of(run_dir: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (run_dir / "chunks.jsonl").read_text("utf-8").splitlines()]


def end_of(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "end.json").read_bytes())


def chat_timeouts(fake: Fake) -> set[float]:
    return {timeout for path, timeout in fake.timeouts if path == "/api/chat"}


def assert_private(paths: list[Path], log: str) -> None:
    escaped = json.dumps(PLANTED)[1:-1]
    for text in [log, *(path.read_bytes().decode("utf-8") for path in paths)]:
        for secret in (PLANTED, escaped, "текст", "Другое", "Shared Name", "Extract the key"):
            assert secret not in text


def assert_broken(run_dir: Path, reason: str) -> dict[str, Any]:
    """A broken run's end and its reading: NOT_EVIDENCE, the reason named."""
    end = end_of(run_dir)
    assert (end["status"], end["reason"], end["stop"]) == ("broken", reason, None)
    record = read_probe(run_dir)
    assert record["g2"] == {"verdict": probe.NOT_EVIDENCE}
    assert record["gate"]["end"] is False and f"the run is broken: {reason}" in record["notes"]
    return end


# --- runs --------------------------------------------------------------------------------------


def test_a_fast_run_passes_g2_after_all_100_and_records_no_text(
    fake: Fake, archive: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    chosen, order = probe.picks(N), probe.run_order()
    indices = [
        int(re.findall(r"chunk (\d+) body", chat["messages"][0]["content"])[0])
        for chat in fake.chats
    ]
    assert indices == [N - 1] + [chosen[pick] for pick in order]
    for chat, index in zip(fake.chats, indices, strict=True):
        assert chat == {
            "model": probe.MODEL,
            "messages": [{"role": "user", "content": probe.PROMPT.format(chunk=chunk_text(index))}],
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0, "seed": 42, "num_ctx": 4096},
            "format": probe.SCHEMA,
        }
    assert fake.generates == [
        {"model": probe.MODEL, "keep_alive": "30m", "options": probe.OPTIONS},
        {"model": probe.MODEL, "keep_alive": 0},
    ]
    assert fake.loaded == []
    # Every chat waits up to the product's 900 s, the load 300 s, any other request 30 s.
    assert chat_timeouts(fake) == {900}
    assert [timeout for path, timeout in fake.timeouts if path == "/api/generate"] == [300, 30]
    others = {path for path, _ in fake.timeouts} - {"/api/chat", "/api/generate"}
    assert {timeout for path, timeout in fake.timeouts if path in others} == {30}
    # The idle rule at the start, its own match aside, the runner after the load, then the
    # contention after every chunk.
    assert fake.patterns == [probe.IDLE, probe.RUNNER] + [probe.OTHERS] * 101
    assert fake.ps_args == [RUNNER_PID]
    rows = rows_of(run_dir)
    assert [row["position"] for row in rows] == list(range(101))
    assert {(row["others"], row["lock"], row["alone"], row["digest_ok"]) for row in rows} == {
        (0, False, True, True)
    }
    first = rows[1]
    assert (first["pick"], first["index"], first["valid"], first["reason"]) == (0, 0, True, "ok")
    assert (first["entities"], first["distinct"], first["pairs"]) == (3, 3, 3)
    assert first["content_sha256"] == hashlib.sha256(chunk_text(0).encode()).hexdigest()
    assert first["output_sha256"] == hashlib.sha256(output_for(0).encode()).hexdigest()
    assert first["sec"] == first["chat_sec"] == 5.0 and first["ollama"]["eval_count"] == 60
    launch = json.loads((run_dir / "launch.json").read_bytes())
    assert (launch["system"], launch["machine"], launch["ollama"], launch["ollama_version"]) == (
        "Darwin",
        "x86_64",
        fake.url,
        "0.33.2",
    )
    assert (launch["loadavg"], launch["others"], launch["lock"]) == ([0.5, 0.5, 0.5], 0, False)
    end = end_of(run_dir)
    assert (end["status"], end["reason"], end["stop"], end["n"]) == ("complete", None, None, 100)
    assert end["load"] == {
        "sec": 31.0,
        "load_duration": 31_000_000_000,
        "size": 3_400_000_000,
        "size_vram": 0,
        "context_length": 4096,
        "runners": 1,
        "runner_np": 1,
        "runner_c": 4096,
    }
    assert end["run_sec"] == pytest.approx(31 + sum(5.0 + (i % 7) / 10 for i in indices))
    assert end["unload_cap_sec"] == 60 and end["wall_sec"] >= end["run_sec"]
    assert end["ollama_models_end"] == [probe.MODEL] and end["ollama_models_after"] == []
    assert end["unload_sec"] == 0.0
    log = capsys.readouterr().out  # the run's log, before the reader prints its line
    assert log.splitlines()[-1] == "PROBE_DONE complete"
    record = read_probe(run_dir)
    assert record["gate"] == {"launch": True, "rows": True, "end": True, "clean": True}
    assert record["notes"] == []
    assert record["g2"]["verdict"] == "passed" and record["g2"]["valid"] == 100
    shown = record["printed_deciding_nothing"]
    assert shown["generated_tokens_per_sec"] == pytest.approx(
        60 / (shown["mean_sec"] * 2 / 3), rel=0.05
    )
    assert shown["projected_hours"]["multihoprag_at_mean"] == pytest.approx(
        N * shown["mean_sec"] / 3600, abs=0.051
    )
    assert shown["distinct_median"] == 3 and shown["pairs_median"] == 3
    log += capsys.readouterr().out
    assert_private([*run_dir.iterdir(), run_dir.parent / "e1.probe.json"], log)


def test_a_slow_run_stops_as_g2_failed_at_the_first_look(
    fake: Fake, archive: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake.reply = lambda number, index: (20.0 + (index % 5) / 10, output_for(index))
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    log = capsys.readouterr().out  # the run's log, before the reader prints its line
    assert "look 10: mean" in log and log.splitlines()[-1] == "PROBE_DONE stopped lower at 10"
    assert len(rows_of(run_dir)) == 11
    end = end_of(run_dir)
    assert (end["status"], end["stop"]) == ("stopped", {"rule": "lower", "at": 10})
    record = read_probe(run_dir)
    assert record["g2"] == {"verdict": "failed", "failed_by": ["lower"], "stopped_at": 10}
    hours = record["printed_deciding_nothing"]["projected_hours"]
    assert hours["multihoprag_at_mean"] > 24 and hours["conditionalqa_wixqa_at_mean"] > 250
    log += capsys.readouterr().out
    assert_private([*run_dir.iterdir(), run_dir.parent / "e1.probe.json"], log)


def test_six_invalid_outputs_stop_the_run(fake: Fake, archive: Path, tmp_path: Path) -> None:
    fake.reply = lambda number, index: (
        5.0,
        f"{PLANTED} not an array" if number in (2, 4, 6, 8, 10, 12) else output_for(index),
    )
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    rows = rows_of(run_dir)
    assert [row["position"] for row in rows if not row["valid"]] == [2, 4, 6, 8, 10, 12]
    assert {row["reason"] for row in rows if not row["valid"]} == {"not_json"}
    assert rows[2]["entities"] is None and rows[2]["output_sha256"]
    assert read_probe(run_dir)["g2"]["failed_by"] == ["invalid"]
    assert_private([*run_dir.iterdir()], "")


# --- D1: the cap is the product's 900 s, and a cut ends the run --------------------------------


CUTS = [("timeout", 900.0), ("reply", 900.0), ("reply", 905.0)]


@pytest.mark.parametrize("position", [1, 10])
@pytest.mark.parametrize(("mode", "seconds"), CUTS)
def test_a_cut_chunk_keeps_its_seconds_and_ends_the_run_as_g2_failed(
    fake: Fake,
    archive: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mode: str,
    seconds: float,
    position: int,
) -> None:
    """A chat that reaches 900 s, by the socket's timeout or by a reply that comes at 900 s or
    later on the clock, is cut whatever came and keeps its measured seconds; they alone pass the
    100's 769.3 s, so the seconds rule stops the run there, and the reader reads it at one chunk
    as at ten."""
    if mode == "timeout":
        fake.real_timeout_for = {position}

    def reply(number: int, index: int) -> tuple[float, str | Answer]:
        if number != position:
            return 5.0, output_for(index)
        return seconds, Answer(stall=STALL) if mode == "timeout" else output_for(index)

    fake.reply = reply
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    rows = rows_of(run_dir)
    assert len(rows) == position + 1 and len(fake.chats) == position + 1
    cut = rows[position]
    assert (cut["status"], cut["reason"], cut["valid"], cut["sec"], cut["chat_sec"]) == (
        "cap",
        "cap",
        False,
        seconds,
        seconds,
    )
    assert (cut["output_sha256"], cut["output_chars"], cut["entities"], cut["ollama"]) == (
        None,
        None,
        None,
        None,
    )
    end = end_of(run_dir)
    assert (end["status"], end["reason"]) == ("stopped", None)
    assert end["stop"] == {"rule": "seconds", "at": position}
    assert end["unload_cap_sec"] == 1_200 and end["ollama_models_after"] == []
    assert capsys.readouterr().out.splitlines()[-1] == f"PROBE_DONE stopped seconds at {position}"
    record = read_probe(run_dir)
    assert record["gate"] == {"launch": True, "rows": True, "end": True, "clean": True}
    assert record["g2"] == {"verdict": "failed", "failed_by": ["seconds"], "stopped_at": position}
    shown = record["printed_deciding_nothing"]
    assert (shown["n"], shown["reasons"]["cap"], shown["max_sec"]) == (position, 1, seconds)
    assert (shown["mean_sec"] is None) is (position == 1)
    assert chat_timeouts(fake) == {probe.CHUNK_CAP}


@pytest.mark.parametrize(("mode", "seconds"), CUTS)
def test_a_cut_warm_up_breaks_the_run(
    fake: Fake, archive: Path, tmp_path: Path, mode: str, seconds: float
) -> None:
    if mode == "timeout":
        fake.real_timeout_for = {0}

    def reply(number: int, index: int) -> tuple[float, str | Answer]:
        if number != 0:
            return 5.0, output_for(index)
        return seconds, Answer(stall=STALL) if mode == "timeout" else output_for(index)

    fake.reply = reply
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 5
    rows = rows_of(run_dir)
    assert [(row["position"], row["status"], row["sec"]) for row in rows] == [(0, "cap", seconds)]
    assert len(fake.chats) == 1 and fake.loaded == []
    end = assert_broken(run_dir, "warmup_cap")
    assert end["n"] == 0 and end["unload_cap_sec"] == 1_200


@pytest.mark.parametrize("position", [12, 100])
def test_a_cut_that_is_the_sixth_invalid_or_the_hundredth(
    fake: Fake, archive: Path, tmp_path: Path, position: int
) -> None:
    """The cut's two exceptions to the seconds rule: as the sixth invalid output it is named by
    the invalid rule, read first; as the hundredth it ends the run complete, and G2 fails it on
    its seconds, a mean of 9 s at least."""

    def reply(number: int, index: int) -> tuple[float, str | Answer]:
        if number == position:
            return 900.0, output_for(index)
        bad = position == 12 and number in (2, 4, 6, 8, 10)
        return 5.0, f"{PLANTED} not an array" if bad else output_for(index)

    fake.reply = reply
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    assert rows_of(run_dir)[-1]["status"] == "cap" and len(fake.chats) == position + 1
    end = end_of(run_dir)
    record = read_probe(run_dir)
    assert all(record["gate"].values()) and end["unload_cap_sec"] == 1_200
    if position == 12:
        assert end["stop"] == {"rule": "invalid", "at": 12}
        assert record["g2"] == {"verdict": "failed", "failed_by": ["invalid"], "stopped_at": 12}
    else:
        assert (end["status"], end["stop"]) == ("complete", None)
        g2 = record["g2"]
        assert (g2["verdict"], g2["failed_by"], g2["valid"]) == ("failed", ["seconds"], 99)
        assert g2["mean_sec"] >= 9.0


# --- D2: the caps are wall-clock deadlines, read after every request ---------------------------


@pytest.mark.parametrize(
    ("case", "reason", "chats"),
    [
        ("the last request", "run_cap", 101),
        ("the load", "run_cap", 0),
        ("a slow load", "load_cap", 0),
    ],
)
def test_a_cap_passed_by_a_request_breaks_the_run(
    fake: Fake,
    archive: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    reason: str,
    chats: int,
) -> None:
    """The run's cap holds from its start to the end of its last request: 31 s of load and 101
    chats of 5 s pass 533.5 s on the last one, and 30 s on the load."""
    fake.reply = lambda number, index: (5.0, output_for(index))
    if case == "the last request":
        monkeypatch.setattr(probe, "RUN_CAP", 533.5)
    elif case == "the load":
        monkeypatch.setattr(probe, "RUN_CAP", 30.0)
    else:
        fake.load_seconds = 301.0
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 5
    assert len(fake.chats) == chats and fake.loaded == []
    end = assert_broken(run_dir, reason)
    assert end["n"] == max(chats - 1, 0)
    if case == "the last request":
        assert end["run_sec"] == 536.0 and len(rows_of(run_dir)) == 101
    elif case == "the load":
        assert end["run_sec"] == 31.0 and not (run_dir / "chunks.jsonl").exists()
    else:
        assert end["load"]["sec"] == 301.0 and end["run_sec"] is None


@pytest.mark.parametrize(
    ("case", "outcome"),
    [
        ("/api/version at the start", "refused"),
        ("/api/tags at the start", "refused"),
        ("/api/ps after the load", "ps_failed"),
        ("/api/tags after a chunk", "tags_failed"),
        ("/api/ps after a chunk", "contended"),
    ],
)
def test_a_request_that_reaches_its_30_s_on_the_clock_is_a_timeout(
    fake: Fake,
    archive: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    case: str,
    outcome: str,
) -> None:
    """urllib's timeout bounds each socket operation, not the request: a reply that comes 30 s
    after its request or later fails as one that never came, at the start, after the load and
    after a chunk (the fourth's checks run after the fifth chat)."""
    path, when = case.split(" ", 1)

    def delay(asked: str, chats: int) -> float:
        if asked != path:
            return 0.0
        if when == "at the start":
            due = not fake.generates
        elif when == "after the load":
            due = chats == 0 and MODEL in fake.loaded
        else:
            due = chats == 5
        return probe.CALL_CAP if due else 0.0

    fake.delay = delay
    run_dir = tmp_path / "runs" / "e1"
    code = run_probe(fake, archive, run_dir)
    if outcome == "refused":
        assert code == 3 and "refused: Ollama does not answer" in capsys.readouterr().err
        assert not fake.generates and not run_dir.exists()
    elif outcome == "contended":
        assert code == 0 and end_of(run_dir)["status"] == "complete"
        record = read_probe(run_dir)
        assert record["g2"] == {"verdict": probe.NOT_EVIDENCE}
        notes = [note for note in record["notes"] if "contended" in note]
        assert notes == ["row 4 contended: /api/ps failed"]
    else:
        assert code == 5
        assert assert_broken(run_dir, outcome)["n"] == (4 if outcome == "tags_failed" else 0)


# --- D3: a reply the product's client raises on breaks the run ---------------------------------

PROTOCOL: dict[str, tuple[Answer, str]] = {
    "not JSON": (Answer(f"<p>{PLANTED}</p>".encode()), "chat_not_json"),
    "not an object": (body_of([PLANTED]), "chat_not_object"),
    "an error": (body_of({"error": PLANTED}), "chat_error"),
    "no message": (body_of({"message": PLANTED, "done": True}), "chat_no_message"),
    "content not a string": (
        body_of({"message": {"role": "assistant", "content": 7}}),
        "chat_no_content",
    ),
    "content empty": (
        body_of({"message": {"role": "assistant", "content": ""}}),
        "chat_no_content",
    ),
    "HTTP 400": (body_of({"error": PLANTED}, 400), "chat_http_4xx"),
    "HTTP 500": (body_of({"error": PLANTED}, 500), "chat_transport"),
    "dropped": (Answer(drop=True), "chat_transport"),
    "a timeout short of the cap": (Answer(stall=STALL), "chat_transport"),
}


@pytest.mark.parametrize("case", list(PROTOCOL))
def test_a_reply_the_client_raises_on_breaks_the_run(
    fake: Fake, archive: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], case: str
) -> None:
    answer, reason = PROTOCOL[case]
    if answer.stall:
        fake.real_timeout_for = {3}
    fake.reply = lambda number, index: (5.0, answer if number == 3 else output_for(index))
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 5
    assert [row["position"] for row in rows_of(run_dir)] == [0, 1, 2]
    assert len(fake.chats) == 4 and fake.loaded == []
    log = capsys.readouterr().out
    assert log.splitlines()[-1] == f"PROBE_DONE broken {reason}"
    assert assert_broken(run_dir, reason)["n"] == 2
    log += capsys.readouterr().out
    assert_private([*run_dir.iterdir(), run_dir.parent / "e1.probe.json"], log)


def test_only_a_string_the_client_returns_reaches_the_check(
    fake: Fake, archive: Path, tmp_path: Path
) -> None:
    fake.reply = lambda number, index: (5.0, " \n " if number == 3 else output_for(index))
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    row = rows_of(run_dir)[3]
    assert (row["status"], row["reason"], row["valid"], row["output_chars"]) == (
        "ok",
        "empty",
        False,
        3,
    )
    record = read_probe(run_dir)
    assert all(record["gate"].values()) and record["g2"]["verdict"] == "passed"


NOT_COUNTS = ["x", -1, None, 1.5, True, 2**63]


@pytest.mark.parametrize("value", NOT_COUNTS)
@pytest.mark.parametrize("key", ["load_duration", "eval_count"])
def test_a_counter_that_is_not_a_count_breaks_the_run(
    fake: Fake, archive: Path, tmp_path: Path, key: str, value: Any
) -> None:
    """A counter Ollama sends is an int from 0 to INT64 (a null is sent, not left out): one that
    is not could hide a reload, so the run breaks on it and its row is not written."""
    fake.override = lambda number: {key: value} if number == 3 else {}
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 5
    assert [row["position"] for row in rows_of(run_dir)] == [0, 1, 2]
    assert len(fake.chats) == 4 and fake.loaded == []
    assert assert_broken(run_dir, "counters")["n"] == 2


@pytest.mark.parametrize("value", NOT_COUNTS)
def test_a_load_duration_that_is_not_a_count_breaks_the_run_before_the_warm_up(
    fake: Fake, archive: Path, tmp_path: Path, value: Any
) -> None:
    fake.load_override = {"load_duration": value}
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 5
    assert not fake.chats and not (run_dir / "chunks.jsonl").exists() and fake.loaded == []
    end = assert_broken(run_dir, "counters")
    assert (end["load"]["sec"], end["load"]["load_duration"], end["n"]) == (31.0, None, 0)


def test_counters_ollama_leaves_out_are_none_and_pass(
    fake: Fake, archive: Path, tmp_path: Path
) -> None:
    """Ollama's counters are omitempty: one left out is None in the row and reads as 0."""
    fake.load_override = {"load_duration": OMIT}
    fake.override = lambda number: {"load_duration": OMIT, "prompt_eval_count": OMIT}
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    rows = rows_of(run_dir)
    assert {
        (row["ollama"]["load_duration"], row["ollama"]["prompt_eval_count"]) for row in rows
    } == {(None, None)}
    assert {row["ollama"]["eval_count"] for row in rows} == {60}
    assert end_of(run_dir)["load"]["load_duration"] is None
    record = read_probe(run_dir)
    assert all(record["gate"].values()) and record["g2"]["verdict"] == "passed"
    shown = record["printed_deciding_nothing"]
    assert shown["prompt_eval_count_median"] is None and shown["reloads"] == 0


# --- D4: the seconds are the product's call, its digest check under the same timer -------------


def test_the_seconds_hold_the_digest_check_and_not_the_contention_checks(
    fake: Fake, archive: Path, tmp_path: Path
) -> None:
    fake.tags_seconds, fake.ps_seconds = 0.25, 0.5
    fake.reply = lambda number, index: (5.0, output_for(index))
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    assert {row["sec"] for row in rows_of(run_dir)} == {5.25}
    record = read_probe(run_dir)
    assert all(record["gate"].values()) and record["g2"]["verdict"] == "passed"


@pytest.mark.parametrize(("case", "reason"), [("changed", "digest"), ("failed", "tags_failed")])
def test_a_digest_change_or_a_failed_lookup_breaks_the_run(
    fake: Fake, archive: Path, tmp_path: Path, case: str, reason: str
) -> None:
    if case == "changed":
        fake.digest_changes_after = 4
    else:
        fake.tags_fail_after = 4
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 5
    assert rows_of(run_dir)[-1]["digest_ok"] is (False if case == "changed" else None)
    assert fake.loaded == []
    assert assert_broken(run_dir, reason)["n"] == 4


# --- D5: the stand is in the gate --------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"), [("size_vram", 3_000_000_000), ("context_length", 2048)]
)
def test_a_stand_other_than_the_registered_breaks_the_run_before_the_warm_up(
    fake: Fake, archive: Path, tmp_path: Path, field: str, value: int
) -> None:
    setattr(fake, field, value)
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 5
    assert not fake.chats and not (run_dir / "chunks.jsonl").exists()
    assert fake.generates[-1] == {"model": MODEL, "keep_alive": 0} and fake.loaded == []
    end = assert_broken(run_dir, "stand")
    assert end["load"][field] == value and end["n"] == 0


RUNNER_FLAGS = {
    "two slots": "-c 8192 -np 2",
    "a wider context": "-c 8192 -np 1",
    "no -np": "-c 4096",
    "two -np": "-c 4096 -np 1 -np 1",
    "a -np not an integer": "-c 4096 -np one",
}


@pytest.mark.parametrize(
    ("case", "field", "value"),
    [
        ("two slots", "runner_np", 2),
        ("a wider context", "runner_c", 8192),
        ("no -np", "runner_np", None),
        ("two -np", "runner_np", None),
        ("a -np not an integer", "runner_np", None),
        ("two runners", "runners", 2),
        ("no runner", "runners", 0),
        ("pgrep fails", "runners", None),
        ("ps fails", "runner_np", None),
    ],
)
def test_a_runner_other_than_one_with_one_slot_breaks_the_run_before_the_warm_up(
    fake: Fake, archive: Path, tmp_path: Path, case: str, field: str, value: int | None
) -> None:
    """context_length in /api/ps is num_ctx whatever the slots: the runner's own -np and -c show
    them, read by ps and kept as integers only."""
    if case in RUNNER_FLAGS:
        fake.runner_args = (
            f"/usr/local/bin/llama-server --model /{PLANTED}/blobs/sha256-0"
            f" {RUNNER_FLAGS[case]} --flash-attn"
        )
    elif case == "two runners":
        fake.runners = [RUNNER_PID, RUNNER_PID + 1]
    elif case == "no runner":
        fake.runners = []
    elif case == "pgrep fails":
        fake.pgrep = lambda pattern, chats: (
            (2, "") if pattern == probe.RUNNER else fake.found(pattern)
        )
    else:
        fake.runners = [RUNNER_PID + 1]
        fake.pgrep = lambda pattern, chats: (
            (0, f"{RUNNER_PID}\n") if pattern == probe.RUNNER else fake.found(pattern)
        )
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 5
    assert not fake.chats and fake.loaded == []
    end = assert_broken(run_dir, "stand")
    assert end["load"][field] == value and end["n"] == 0
    assert fake.ps_args == ([] if field == "runners" else [RUNNER_PID])
    assert PLANTED not in (run_dir / "end.json").read_text("utf-8")


@pytest.mark.parametrize(
    ("case", "note"),
    [
        ("version", "launch: ollama_version is not the registered value"),
        ("system", "launch: system is not the registered value"),
        ("machine", "launch: machine is not the registered value"),
        ("endpoint", "launch: ollama is not the registered value"),
        ("missing", "launch: keys other than the registered ones"),
    ],
)
def test_the_gate_requires_the_registered_stand(
    fake: Fake,
    archive: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    note: str,
) -> None:
    """The gate's second line behind the refusal at the start: a launch.json whose stand is not
    the registered one reads as NOT_EVIDENCE."""
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    launch = json.loads((run_dir / "launch.json").read_bytes())
    edits = {
        "version": ("ollama_version", "0.33.1"),
        "system": ("system", "Linux"),
        "machine": ("machine", "arm64"),
    }
    if case in edits:
        key, value = edits[case]
        assert launch[key] != value
        launch[key] = value
    elif case == "endpoint":
        monkeypatch.setattr(probe, "OLLAMA", "http://127.0.0.1:11434")
    else:
        del launch["machine"]
    (run_dir / "launch.json").write_bytes(json.dumps(launch).encode())
    record = read_probe(run_dir)
    assert record["gate"]["launch"] is False and record["g2"] == {"verdict": probe.NOT_EVIDENCE}
    assert note in record["notes"]
    assert record["printed_deciding_nothing"]["loadavg"]["launch"] is None


# --- D6: the idle rule at the start, contention after every chunk ------------------------------

REFUSALS = {
    "exists": "exists",
    "endpoint": "the endpoint is not the registered one",
    "system": "the system is not the registered one",
    "machine": "the machine is not the registered one",
    "archive": "the archive is not the registered one",
    "down": "Ollama does not answer",
    "version": "Ollama's version is not the registered one",
    "loaded": "a model is loaded in Ollama",
    "digest": "the model is absent or its digest is not the registered one",
    "absent": "the model is absent or its digest is not the registered one",
    "load5": "the 5-minute load is not below 2",
    "no load average": "the 5-minute load is not below 2",
    "pgrep finds": "pgrep finds another measurement or job",
    "pgrep fails": "pgrep finds another measurement or job",
    "lock": "the CI lock is held",
}
BEFORE_ANY_REQUEST = ("exists", "endpoint", "system", "machine", "archive")


@pytest.mark.parametrize(("case", "why"), list(REFUSALS.items()))
def test_a_refused_run_writes_nothing(
    fake: Fake,
    archive: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    case: str,
    why: str,
) -> None:
    """Each refusal at the start names its reason, exits 3 and writes nothing; a wrong endpoint,
    system or machine is refused before any request."""
    run_dir = tmp_path / "runs" / "e1"
    url = fake.url
    if case == "exists":
        run_dir.mkdir(parents=True)
    elif case == "endpoint":
        url = fake.url.replace("127.0.0.1", "localhost")  # the same server by another name
    elif case == "system":
        monkeypatch.setattr(probe, "_system", lambda: "Linux")
    elif case == "machine":
        monkeypatch.setattr(probe, "_machine", lambda: "arm64")
    elif case == "archive":
        monkeypatch.setattr(probe, "ARCHIVE_SHA256", "0" * 64)
    elif case == "version":
        fake.version = "0.33.1"
    elif case == "loaded":
        fake.others = ["another-model:7b"]
    elif case == "digest":
        fake.digest = "e" * 64
    elif case == "absent":
        monkeypatch.setattr(probe, "MODEL", "qwen3:missing")
    elif case == "load5":
        monkeypatch.setattr(probe, "_loadavg", lambda: [0.1, 2.0, 0.1])
    elif case == "no load average":
        monkeypatch.setattr(probe, "_loadavg", lambda: None)
    elif case == "pgrep finds":
        fake.pgrep = lambda pattern, chats: (0, OWN + f"{STRANGER}\n")
    elif case == "pgrep fails":
        fake.pgrep = lambda pattern, chats: (2, "")
    elif case == "lock":
        fake.ci_lock.parent.mkdir(parents=True)
        fake.ci_lock.write_bytes(b"")
    else:
        with socket.socket() as closed:
            closed.bind(("127.0.0.1", 0))
            url = f"http://127.0.0.1:{closed.getsockname()[1]}"
        monkeypatch.setattr(probe, "OLLAMA", url)  # the registered endpoint, and nothing there
    assert probe.main(["run", str(run_dir), "--archive", str(archive), "--ollama", url]) == 3
    err = capsys.readouterr().err
    assert err.startswith("refused: ") and why in err
    assert not fake.chats and not fake.generates
    assert (not run_dir.exists()) or not any(run_dir.iterdir())
    if case in BEFORE_ANY_REQUEST:
        assert fake.timeouts == []
    if case.startswith("pgrep"):
        assert fake.patterns == [probe.IDLE]


@pytest.mark.parametrize("row", [0, 50])
@pytest.mark.parametrize(
    ("case", "why"),
    [
        ("pgrep finds", "other processes"),
        ("pgrep fails", "pgrep failed"),
        ("lock", "the CI lock"),
        ("ps fails", "/api/ps failed"),
        ("another model", "not this model alone"),
        ("reload", "a reload"),
    ],
)
def test_contention_after_a_chunk_makes_the_run_not_evidence(
    fake: Fake, archive: Path, tmp_path: Path, case: str, why: str, row: int
) -> None:
    """A row's checks run after its chat (row 50's after the 51st): one contended row is enough,
    the warm-up's included, for a job seen after it may have run into the first measured chunk;
    the run goes on, for the gate decides."""
    default, after = fake.pgrep, row + 1
    if case == "pgrep finds":
        fake.pgrep = lambda pattern, chats: (
            (0, f"{STRANGER}\n") if chats == after else default(pattern, chats)
        )
    elif case == "pgrep fails":
        fake.pgrep = lambda pattern, chats: (2, "") if chats == after else default(pattern, chats)
    elif case == "ps fails":
        fake.ps_fail_at = after
    elif case == "reload":
        fake.load_ns = lambda number: 31_000_000_000 if number == row else 2_000_000
    else:

        def reply(number: int, index: int) -> tuple[float, str | Answer]:
            if case == "lock" and number == row:
                fake.ci_lock.parent.mkdir(parents=True)
                fake.ci_lock.write_bytes(b"")
            elif case == "lock" and number == after:
                fake.ci_lock.unlink()
            elif case == "another model":
                fake.others = ["another-model:7b"] if number == row else []
            return 5.0, output_for(index)

        fake.reply = reply
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    assert end_of(run_dir)["status"] == "complete" and len(rows_of(run_dir)) == 101
    record = read_probe(run_dir)
    assert record["gate"] == {"launch": True, "rows": True, "end": True, "clean": False}
    assert record["g2"] == {"verdict": probe.NOT_EVIDENCE}
    notes = [note for note in record["notes"] if "contended" in note]
    assert notes == [f"row {row} contended: {why}"]


def test_another_model_at_the_end_makes_the_run_not_evidence(
    fake: Fake, archive: Path, tmp_path: Path
) -> None:
    def reply(number: int, index: int) -> tuple[float, str | Answer]:
        if number == 50:
            fake.others = ["another-model:7b"]
        return 5.0, output_for(index)

    fake.reply = reply
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    end = end_of(run_dir)
    assert end["status"] == "complete"
    assert end["ollama_models_end"] == [MODEL, "another-model:7b"]
    assert end["ollama_models_after"] == ["another-model:7b"]
    record = read_probe(run_dir)
    assert record["gate"] == {"launch": True, "rows": True, "end": False, "clean": False}
    assert record["g2"] == {"verdict": probe.NOT_EVIDENCE}
    assert "the models in Ollama at the end were not this one alone" in record["notes"]


# --- D7: the rows, the end and the unload ------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "polls", "waited", "bound", "gone"),
    [
        ("goes later", 4, 3, 60, 3.0),
        ("a late reply", 3, 77, 60, 77.0),
        ("stays", 61, 60, 60, None),
        ("stays after a cut", 1_201, 1_200, 1_200, None),
    ],
)
def test_the_unload_wait_ends_when_the_model_goes_or_at_its_bound(
    fake: Fake,
    archive: Path,
    tmp_path: Path,
    case: str,
    polls: int,
    waited: int,
    bound: int,
    gone: float | None,
) -> None:
    """A look once a second until one shows the model gone or the bound has passed; a look
    that shows it gone after the bound (25 s a look: 25, 51, 77) does not pass the gate."""
    fake.unload_polls = {"goes later": 3, "a late reply": 2}.get(case)
    if case == "a late reply":
        fake.delay = lambda path, chats: (
            25.0 if path == "/api/ps" and fake.unload_requested else 0.0
        )
    if case == "stays after a cut":
        fake.reply = lambda number, index: (905.0 if number == 1 else 5.0, output_for(index))
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    end = end_of(run_dir)
    assert fake.polls == polls and end["unload_cap_sec"] == bound and end["unload_sec"] == gone
    assert end["wall_sec"] - end["run_sec"] == pytest.approx(waited)
    record = read_probe(run_dir)
    assert record["printed_deciding_nothing"]["unload_sec"] == gone
    if case == "goes later":
        assert end["ollama_models_after"] == [] and all(record["gate"].values())
        return
    assert record["gate"]["end"] is False and record["g2"] == {"verdict": probe.NOT_EVIDENCE}
    if case == "a late reply":
        assert end["ollama_models_after"] == []
        assert "no reply within the unload's bound showed the model gone" in record["notes"]
    else:
        assert end["ollama_models_after"] == [MODEL]
        assert "a model was still in Ollama after the unload" in record["notes"]
        assert "no reply within the unload's bound showed the model gone" not in record["notes"]


NESTED = b"[" * 100_000 + b"]" * 100_000 + b"\n"
ROW_VALUES: list[tuple[str, Any]] = [
    ("sec", math.nan),
    ("sec", -1.0),
    ("sec", "5"),
    ("sec", True),
    ("sec", 10**30),
    ("chat_sec", math.nan),
    ("chat_sec", None),
    ("chat_sec", 900.0),
    ("status", "broken"),
    ("status", "cap"),
    ("reason", PLANTED),
    ("reason", "cap"),
    ("valid", 1),
    ("content_sha256", "ab"),
    ("output_sha256", "A" * 64),
    ("output_chars", -1),
    ("output_chars", 1.5),
    ("entities", "3"),
    ("pairs", 4),
    ("ollama", None),
    ("others", -1),
    ("others", "x"),
    ("lock", "no"),
    ("alone", 1),
    ("digest_ok", "yes"),
    ("position", 3.0),
    ("pick", True),
    ("index", -1),
]
LAUNCH_VALUES: list[tuple[str, Any]] = [
    ("loadavg", [0.5, 2.5, 0.5]),
    ("loadavg", "high"),
    ("loadavg", [math.nan] * 3),
    ("swap_used_mib", "x"),
    ("swap_used_mib", -1.0),
    ("started", "yesterday"),
    ("python", 3),
    ("others", 1),
    ("lock", True),
    ("ollama_version", "0.33.1"),
    ("archive", 7),
    ("model_digest", PLANTED),
    ("ollama_models_before", [MODEL]),
]
END_VALUES: list[tuple[str, Any]] = [
    ("status", "done"),
    ("reason", "run_cap"),
    ("reason", PLANTED),
    ("stop", {"rule": "lower", "at": 10}),
    ("n", 99),
    ("n", 100.0),
    ("ended", 5),
    ("run_sec", 3_001.0),
    ("run_sec", None),
    ("run_sec", math.inf),
    ("wall_sec", 1.0),
    ("unload_cap_sec", 1_200),
    ("unload_sec", 61.0),
    ("unload_sec", None),
    ("unload_sec", -1.0),
    ("unload_sec", "x"),
    ("ollama_models_end", None),
    ("ollama_models_after", [PLANTED]),
    ("ollama_models_after", [MODEL]),
    ("loadavg", [1, 2]),
    ("swap_used_mib", math.nan),
]
LOAD_VALUES: list[tuple[str, Any]] = [
    ("size_vram", 1),
    ("context_length", 2048),
    ("sec", 301.0),
    ("sec", 300.0),
    ("sec", None),
    ("load_duration", -1),
    ("size", "big"),
    ("runners", 2),
    ("runners", None),
    ("runner_np", 2),
    ("runner_np", None),
    ("runner_c", 8192),
    ("runner_c", "4096"),
]


def as_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8")


def malformed(
    launch: dict[str, Any], rows: list[dict[str, Any]], end: dict[str, Any]
) -> dict[str, dict[str, bytes | None]]:
    """Each case's files that differ from a clean run's: bytes, or None for a file removed."""

    def with_row(row: Any, position: int = 3) -> bytes:
        return b"".join(as_json(row if i == position else item) for i, item in enumerate(rows))

    cases: dict[str, dict[str, bytes | None]] = {}
    row = rows[3]
    for key, value in ROW_VALUES:
        cases[f"row {key} {value!r}"] = {"chunks.jsonl": with_row({**row, key: value})}
    inf = with_row({**row, "sec": "INF"}).replace(b'"INF"', b"1e400")
    counters = {**row["ollama"], "eval_count": -1}
    cut = {
        **dict.fromkeys(("entities", "distinct", "pairs", "output_sha256", "output_chars")),
        "ollama": None,
        "status": "cap",
        "reason": "cap",
        "valid": False,
        "sec": 950.0,
        "chat_sec": 950.0,
    }
    longer = {**end, "run_sec": end["run_sec"] + 950.0, "wall_sec": end["wall_sec"] + 950.0}
    cases |= {
        "row cut short of 900 s": {"chunks.jsonl": with_row({**row, **cut, "chat_sec": 899.0})},
        "row cut with counters": {
            "chunks.jsonl": with_row({**row, **cut, "ollama": row["ollama"]})
        },
        "row chat_sec past sec": {"chunks.jsonl": with_row({**row, "chat_sec": row["sec"] + 1.0})},
        "row sec 1e400": {"chunks.jsonl": inf},
        "row ollama negative": {"chunks.jsonl": with_row({**row, "ollama": counters})},
        "row ollama keys": {"chunks.jsonl": with_row({**row, "ollama": {"eval_count": 60}})},
        "row extra key": {"chunks.jsonl": with_row({**row, "host": PLANTED})},
        "row missing key": {
            "chunks.jsonl": with_row({k: v for k, v in row.items() if k != "lock"})
        },
        "row a list": {"chunks.jsonl": with_row([PLANTED])},
        "warm-up cut": {
            "chunks.jsonl": with_row({**rows[0], **cut}, 0),
            "end.json": as_json(longer),
        },
        "a 102nd row": {"chunks.jsonl": with_row(row) + as_json(rows[-1])},
        "a torn last line": {"chunks.jsonl": with_row(row)[:-1]},
        "rows not UTF-8": {"chunks.jsonl": b"\xff\xfe\n"},
        "rows nested": {"chunks.jsonl": b"".join(as_json(item) for item in rows[:3]) + NESTED},
        "rows empty": {"chunks.jsonl": b""},
        "rows missing": {"chunks.jsonl": None},
    }
    for key, value in LAUNCH_VALUES:
        cases[f"launch {key} {value!r}"] = {"launch.json": as_json({**launch, key: value})}
    cases |= {
        "launch extra key": {"launch.json": as_json({**launch, "host": PLANTED})},
        "launch missing key": {
            "launch.json": as_json({k: v for k, v in launch.items() if k != "lock"})
        },
        "launch caps": {
            "launch.json": as_json({**launch, "caps_sec": {**launch["caps_sec"], "chunk": 180}})
        },
        "launch a list": {"launch.json": as_json([PLANTED])},
        "launch not UTF-8": {"launch.json": b"\xff"},
        "launch nested": {"launch.json": NESTED},
    }
    for key, value in END_VALUES:
        cases[f"end {key} {value!r}"] = {"end.json": as_json({**end, key: value})}
    for key, value in LOAD_VALUES:
        load = {**end["load"], key: value}
        cases[f"end load {key} {value!r}"] = {"end.json": as_json({**end, "load": load})}
    cases |= {
        "end load missing key": {
            "end.json": as_json(
                {**end, "load": {k: v for k, v in end["load"].items() if k != "size_vram"}}
            )
        },
        "end run_sec at its cap": {
            "end.json": as_json({**end, "run_sec": probe.RUN_CAP, "wall_sec": probe.RUN_CAP})
        },
        "end extra key": {"end.json": as_json({**end, "host": PLANTED})},
        "end a list": {"end.json": as_json([PLANTED])},
        "end nested": {"end.json": NESTED},
        "end missing": {"end.json": None},
    }
    return cases


def test_a_malformed_field_anywhere_reads_as_not_evidence_without_an_exception(
    fake: Fake, archive: Path, tmp_path: Path
) -> None:
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    assert probe.read(run_dir)["g2"]["verdict"] == "passed"
    launch = json.loads((run_dir / "launch.json").read_bytes())
    end = end_of(run_dir)
    cases = malformed(launch, rows_of(run_dir), end)
    assert len(cases) > 70
    for number, (name, files) in enumerate(cases.items()):
        case_dir = tmp_path / "cases" / f"c{number}"
        shutil.copytree(run_dir, case_dir)
        for file, data in files.items():
            if data is None:
                (case_dir / file).unlink()
            else:
                (case_dir / file).write_bytes(data)
        record = probe.read(case_dir)
        assert record["g2"] == {"verdict": probe.NOT_EVIDENCE}, name
        assert record["notes"] and not all(record["gate"].values()), name
        text = json.dumps(record, ensure_ascii=False, allow_nan=False)
        assert PLANTED not in text, name


def test_the_reader_refuses_an_existing_out_and_reads_a_changed_run_as_not_evidence(
    fake: Fake, archive: Path, tmp_path: Path
) -> None:
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    out = tmp_path / "taken.json"
    out.write_bytes(b"{}\n")
    assert probe.main(["read", str(out), str(run_dir)]) == 2
    assert out.read_bytes() == b"{}\n"
    lines = (run_dir / "chunks.jsonl").read_bytes().splitlines(keepends=True)
    (run_dir / "chunks.jsonl").write_bytes(b"".join(lines[:-1]))
    record = read_probe(run_dir)
    assert record["gate"]["end"] is False and record["g2"] == {"verdict": probe.NOT_EVIDENCE}
    (run_dir / "chunks.jsonl").write_bytes(b"".join(lines))
    launch = json.loads((run_dir / "launch.json").read_bytes())
    launch["prompt_sha256"] = "0" * 64
    (run_dir / "launch.json").write_bytes(json.dumps(launch).encode())
    (run_dir.parent / "e1.probe.json").unlink()
    record = read_probe(run_dir)
    assert record["gate"]["launch"] is False and record["g2"] == {"verdict": probe.NOT_EVIDENCE}
    assert "launch: prompt_sha256 is not the registered value" in record["notes"]


@pytest.mark.parametrize("case", ["the load", "the warm-up", "the hundredth", "the run"])
def test_spans_the_run_could_not_hold_read_as_not_evidence(
    fake: Fake, archive: Path, tmp_path: Path, case: str
) -> None:
    """The load and the rows are spans of the run, one after another on one clock: 100 s more in
    one of them, or 1 s less in the run, is not evidence, though every field is well formed and
    no stop rule is met."""
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    rows, end = rows_of(run_dir), end_of(run_dir)
    assert math.fsum([end["load"]["sec"], *(row["sec"] for row in rows)]) == end["run_sec"]
    if case == "the load":
        end["load"]["sec"] += 100.0
    elif case == "the run":
        end["run_sec"] -= 1.0
    else:
        rows[0 if case == "the warm-up" else 100]["sec"] += 100.0
    (run_dir / "chunks.jsonl").write_bytes(b"".join(as_json(row) for row in rows))
    (run_dir / "end.json").write_bytes(as_json(end))
    record = read_probe(run_dir)
    assert record["gate"] == {"launch": True, "rows": True, "end": False, "clean": True}
    assert record["g2"] == {"verdict": probe.NOT_EVIDENCE}
    assert record["notes"] == [
        "end.json does not agree with the rows, the stop rule, the stand, the seconds or the caps"
    ]


# --- D8: unrounded seconds through the record --------------------------------------------------


def test_chunks_exactly_on_the_line_pass_through_the_record(
    fake: Fake, archive: Path, tmp_path: Path
) -> None:
    fake.reply = lambda number, index: (LINE, output_for(index))
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    assert {row["sec"] for row in rows_of(run_dir)} == {LINE}
    end = end_of(run_dir)
    assert (end["status"], end["stop"], end["n"]) == ("complete", None, 100)
    record = read_probe(run_dir)
    assert record["gate"] == {"launch": True, "rows": True, "end": True, "clean": True}
    assert record["g2"]["verdict"] == "passed" and record["g2"]["failed_by"] == []
    assert record["g2"]["upper_sec"] == round(LINE, 6)


# Nine chunks whose exact sum, 769.2992609740896 s, is the largest the seconds rule lets pass.
FSUM_EDGE = [81.443, 81.178, 83.085, 88.161, 81.807, 85.816, 86.389, 83.724, 97.69626097408963]


def test_the_seconds_rule_sums_exactly_where_a_running_sum_would_stop_early(
    fake: Fake, archive: Path, tmp_path: Path
) -> None:
    """Summed left to right, the nine round one step past the line and would stop the run at 9;
    summed exactly, they pass, and the tenth stops it."""
    running = 0.0
    for value in FSUM_EDGE:
        running += value
    assert N * math.fsum(FSUM_EDGE) <= probe.TOTAL * probe.DAY < N * running
    fake.reply = lambda number, index: (
        FSUM_EDGE[number - 1] if 1 <= number <= 9 else 5.0,
        output_for(index),
    )
    run_dir = tmp_path / "runs" / "e1"
    assert run_probe(fake, archive, run_dir) == 0
    assert [row["sec"] for row in rows_of(run_dir)[1:10]] == FSUM_EDGE
    end = end_of(run_dir)
    assert (end["status"], end["stop"], end["n"]) == ("stopped", {"rule": "seconds", "at": 10}, 10)
    record = read_probe(run_dir)
    assert all(record["gate"].values())
    assert record["g2"] == {"verdict": "failed", "failed_by": ["seconds"], "stopped_at": 10}


# --- the spec ----------------------------------------------------------------------------------


def test_the_spec_names_the_tool_and_freezes_the_values() -> None:
    """The spec names the SHA-256 of the tool and of this test, and a later change shows here
    (a marked error fix updates it); the frozen values and phrases stand as it states them."""
    spec = SPEC.read_text("utf-8")
    assert "registered before the first request" in spec
    named = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    assert sorted(named) == [
        "reports/stage7/tools/entity_probe.py",
        "tests/test_stage7_entity_probe.py",
    ]
    for path, digest in named.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    assert (probe.TOTAL, probe.CHECKPOINTS, probe.MIN_VALID, probe.MAX_INVALID) == (
        100,
        (10, 20, 40, 70),
        95,
        5,
    )
    assert (probe.N_MULTIHOP, probe.N_OTHER, probe.DAY) == (11_231, 51_349, 86_400)
    assert (probe.CHUNK_CAP, probe.LOAD_CAP, probe.RUN_CAP, probe.CALL_CAP) == (900, 300, 3_000, 30)
    assert (probe.UNLOAD_CAP, probe.UNLOAD_CUT_CAP, probe.RELOAD_NS) == (60, 1_200, 10**9)
    assert (probe.OLLAMA, probe.OLLAMA_VERSION, probe.SYSTEM, probe.MACHINE) == (
        "http://127.0.0.1:11434",
        "0.33.2",
        "Darwin",
        "x86_64",
    )
    assert probe.OPTIONS == {"temperature": 0, "seed": 42, "num_ctx": 4096}
    assert (probe.KEEP_ALIVE, probe.MODEL, probe.TENANT) == (
        "30m",
        "qwen3:4b-instruct-2507-q4_K_M",
        "ext_multihoprag",
    )
    assert probe.ARCHIVE == "/Users/julia/RAG_new_external_s1/multihoprag/chunks.json.gz"
    assert probe.LOCK == Path.home() / "ci_local" / ".lock_ci-local"
    assert probe.PROMPT_SHA256 == hashlib.sha256(probe.PROMPT.encode("utf-8")).hexdigest()
    for value in (
        probe.MODEL_DIGEST,
        probe.ARCHIVE_SHA256,
        probe.PROMPT_SHA256,
        probe.FORMAT_SHA256,
        probe.ARCHIVE,
        probe.OLLAMA,
        probe.IDLE,
        probe.OTHERS,
        probe.RUNNER,
    ):
        assert value in spec, value
    assert probe.SLOTS == 1 and "`-np 1`" in spec and "`-c 4096`" in spec
    for line in probe.PROMPT.split("\n"):
        assert not line or f"    {line}\n" in spec, line
    phrases = (
        "86,400 / 11,231 = 7.693 s",
        "11,231 × the upper bound",
        "fewer than 95 of the 100",
        "more than 5 invalid",
        "10, 20, 40 and 70",
        "769.3 s",
        "only after all 100",
        "900 s",
        "300 s",
        "3,000 s",
        "2,870 s",
        "60 s",
        "1,200 s",
        "`/api/chat`",
        "`num_ctx` 4096",
        "never a chunk's text",
        "published either way",
        "seed 20261028",
    )
    for phrase in phrases:
        assert phrase in spec, phrase
