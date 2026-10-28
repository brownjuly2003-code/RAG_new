"""reports/stage4-step1/tools: the driver copies' marked changes, their arms, the reader's pairs.

docs/specs/stage4-step1-rerank-memory.md. Synthetic fixtures only: every number, path and text in
them is made up. The run files copy the shapes V4's drivers write (launch.json and the case files
by live_supervisor.py and live_runner.py, stages.jsonl by reports/stage2/tools/live_api.py) and
the lines of step 0's sampler. No network, Ollama, API, database or model: the copies are
imported with their requests and processes replaced by fakes.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import types
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "stage4-step1" / "tools"
ORIGINALS = ROOT / "reports" / "stage1" / "tools"
SAMPLER = ROOT / "reports" / "stage4-step0" / "tools" / "step0_sampler.py"
LIVE_API = ROOT / "reports" / "stage2" / "tools" / "live_api.py"
CURATED = ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
SPEC = ROOT / "docs" / "specs" / "stage4-step1-rerank-memory.md"
BEGIN, END, MARK = "# stage4-step1: begin", "# stage4-step1: end", "  # stage4-step1"
# The original lines a copy replaces by marked ones, each once in its original.
REPLACED = {
    "live_runner.py": (),
    "live_supervisor.py": (
        'DEPLOYMENT = {"RAG_DEVICE"}',
        '    assert set(extra) <= DEPLOYMENT | {"MODEL"} | TARGET',
    ),
}
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
PLANTED = "PLANTED-текст"


def load(path: Path, name: str) -> Any:
    """A tool as a module of its own name; the sys.path a copy extends is given back."""
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


reader = load(TOOLS / "step1_reader.py", "stage4_step1_reader")
supervisor = load(TOOLS / "live_supervisor.py", "stage4_step1_live_supervisor")


# --- the copies: marked lines only ------------------------------------------------------------


def unmarked(lines: list[str]) -> tuple[list[str], int]:
    """The lines outside the marked blocks and without the end-of-line mark; the marked count."""
    kept: list[str] = []
    marked = 0
    inside = False
    for line in lines:
        if line.strip() == BEGIN:
            assert not inside, "a block begins inside a block"
            inside = True
        if inside or line.rstrip().endswith(MARK):
            marked += 1
            if line.strip() == END:
                inside = False
            continue
        assert line.strip() != END, "a block ends that never began"
        kept.append(line)
    assert not inside, "a block never ends"
    return kept, marked


@pytest.mark.parametrize("name", sorted(REPLACED))
def test_each_copy_is_v4s_driver_but_for_its_marked_lines(name: str) -> None:
    data = (TOOLS / name).read_bytes()
    assert b"\r" not in data
    copy = data.decode("utf-8").split("\n")
    expected = (ORIGINALS / name).read_text("utf-8").split("\n")
    for line in REPLACED[name]:
        assert expected.count(line) == 1, line
        expected.remove(line)
    kept, marked = unmarked(copy)
    assert kept == expected
    assert marked > len(REPLACED[name])
    header = copy[copy.index(BEGIN) : copy.index(END)]
    assert "# fmt: off" in header
    assert "docs/specs/stage4-step1-rerank-memory.md" in "\n".join(header)


# --- the supervisor: ARM and RAG_RETRIEVAL_TOP_K ---------------------------------------------


@pytest.fixture
def stand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The supervisor's folders in tmp_path; both ports taken and Ollama unreachable, so it
    writes launch.json, starts nothing and stops."""
    here = tmp_path / "ws" / "step1"
    here.mkdir(parents=True)
    (here.parent / "CODE_SHA").write_text(reader.CODE_SHA + "\n", "utf-8")
    monkeypatch.setattr(supervisor, "HERE", here)
    monkeypatch.setattr(supervisor, "WS", here.parent)
    monkeypatch.setattr(supervisor, "RUNTIME", tmp_path / "no-runtime")
    monkeypatch.setattr(supervisor, "PY", str(tmp_path / "no-python"))
    monkeypatch.setattr(supervisor, "port_free", lambda port: False)

    def no_ollama(*args: Any, **kwargs: Any) -> Any:
        raise OSError("no Ollama in a test")

    monkeypatch.setattr(supervisor, "ollama", no_ollama)
    return here


def supervise(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["live_supervisor.py", *args])
    return supervisor.main()


def test_the_supervisor_keeps_the_arms_for_the_runner_and_k_as_a_deployment_setting(
    stand: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cases = "aircargo-dismissal-order,aircargo-leave-sources"
    extra = "TENANT=aircargo,ARM=BA,RAG_RETRIEVAL_TOP_K=14"
    assert supervise(monkeypatch, "s1-baba", "prod", cases, "1965/1320", extra) == 2
    launch = json.loads((stand / "runs" / "s1-baba" / "launch.json").read_text("utf-8"))
    assert launch["arm"] == "BA" and launch["model"] == MODEL
    assert launch["overrides"]["RAG_RETRIEVAL_TOP_K"] == "14"
    assert "ARM" not in launch["overrides"]
    assert launch["status"] == "failed"
    assert launch["error"].startswith("RuntimeError: port 8002 is taken")
    assert "LIVE_DONE s1-baba failed exit 2" in capsys.readouterr().out
    # without the two names it writes what the original writes
    assert supervise(monkeypatch, "s1-plain", "floor", cases, "100") == 2
    plain = json.loads((stand / "runs" / "s1-plain" / "launch.json").read_text("utf-8"))
    assert "arm" not in plain and "RAG_RETRIEVAL_TOP_K" not in plain["overrides"]


@pytest.mark.parametrize(
    ("mode", "extra"),
    [
        ("prod", "ARM=BX"),  # a letter neither A nor B
        ("prod", "ARM=ba"),
        ("prod", "ARM="),
        ("prod", "ARM=BAB"),  # three letters for two cases
        ("prod", "ARM=B"),
        ("dump", "ARM=BA"),  # no runner, so no arm
        ("retrieval", "ARM=BA"),
        ("prod", "RAG_RETRIEVAL_TOP_K=0"),
        ("prod", "RAG_RETRIEVAL_TOP_K=100"),
        ("prod", "RAG_RERANK_TOP_K=3"),  # not a deployment setting
    ],
)
def test_the_supervisor_refuses_a_bad_arm_or_k_before_it_writes_anything(
    stand: Path, monkeypatch: pytest.MonkeyPatch, mode: str, extra: str
) -> None:
    with pytest.raises(AssertionError):
        supervise(monkeypatch, "s1-bad", mode, "case-1,case-2", "100", extra)
    assert not (stand / "runs").exists()


# --- the runner: the arm's action before each question ---------------------------------------


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    (tmp_path / "run").mkdir()
    monkeypatch.setenv("CHAT_RUN_DIR", str(tmp_path / "run"))
    monkeypatch.delenv("CHAT_CASES_FILE", raising=False)
    monkeypatch.delenv("CHAT_TENANT", raising=False)
    return load(TOOLS / "live_runner.py", "stage4_step1_live_runner")


def ps(*names: str) -> dict[str, Any]:
    return {"models": [{"name": name, "model": name} for name in names]}


def fake_ollama(
    monkeypatch: pytest.MonkeyPatch, runner: Any, replies: dict[str, list[Any]]
) -> list[tuple[str, Any]]:
    """Ollama's replies by path, and under "ps" ps's counts of llama-server processes (none
    unless given), each in turn, the last one repeated; the calls made."""
    calls: list[tuple[str, Any]] = []

    def reply(key: str) -> Any:
        queue = replies.setdefault(key, [0]) if key == "ps" else replies[key]
        value = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(value, Exception):
            raise value
        return value

    def ollama(path: str, payload: Any = None, timeout: float = 10) -> Any:
        calls.append((path, payload))
        return reply(path)

    def llama_servers() -> Any:
        calls.append(("ps", None))
        return reply("ps")

    monkeypatch.setattr(runner, "ollama", ollama)
    monkeypatch.setattr(runner, "llama_servers", llama_servers)
    monkeypatch.setattr(runner, "POLL_SEC", 0)
    return calls


def test_arm_a_renews_the_resident_model_and_unloads_nothing(
    runner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = fake_ollama(monkeypatch, runner, {"/api/ps": [ps(MODEL)], "/api/generate": [{}]})
    action = runner.arm_action("A", MODEL)
    assert "error" not in action and "llama_servers" not in action
    assert (action["arm"], action["polls"]) == ("A", 0)
    assert (action["ps_before"], action["ps_after"]) == ([MODEL], [MODEL])
    assert [payload for path, payload in calls if path == "/api/generate"] == [
        {"model": MODEL, "keep_alive": "30m"}
    ]
    assert ("ps", None) not in calls
    assert action["sec"] >= 0 and action["done_monotonic"] > 0


def test_arm_b_unloads_and_waits_until_neither_ollama_nor_ps_lists_the_model(
    runner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    # /api/ps empty at the second poll, the process gone at the third
    replies = {"/api/ps": [ps(MODEL), ps(MODEL), ps()], "/api/generate": [{}], "ps": [1, 1, 0]}
    calls = fake_ollama(monkeypatch, runner, replies)
    action = runner.arm_action("B", MODEL)
    assert "error" not in action
    assert (action["polls"], action["ps_before"], action["ps_after"]) == (3, [MODEL], [])
    assert action["llama_servers"] == 0
    assert [payload for path, payload in calls if path == "/api/generate"] == [
        {"model": MODEL, "keep_alive": 0}
    ]


def test_arm_b_sends_no_unload_when_nothing_is_resident(
    runner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = fake_ollama(monkeypatch, runner, {"/api/ps": [ps()]})
    action = runner.arm_action("B", MODEL)
    assert "error" not in action and action["polls"] == 1
    assert [path for path, _ in calls] == ["/api/ps", "/api/ps", "ps"]


def test_llama_servers_counts_the_processes_the_sampler_lists(
    runner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    listing = (
        "  101  2048 /Applications/Ollama.app/Contents/Resources/llama-server\n"
        "  102   512 /usr/bin/python3\n"
        "  103   256 /opt/x/llama-server-other\n"
        "  104   128 llama-server\n"
        "  not a row\n"
    )
    seen: list[Any] = []

    def run(args: Any, **kwargs: Any) -> Any:
        seen.append((tuple(args), kwargs.get("check")))
        return types.SimpleNamespace(stdout=listing)

    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner.llama_servers() == 2
    assert seen == [(runner.PS, True)]
    sampler = load(SAMPLER, "stage4_step1_sampler")
    assert runner.PS == sampler.PS
    assert len(sampler.parse_ps(listing)) == 2


@pytest.mark.parametrize(
    ("arm", "replies", "error"),
    [
        ("B", {"/api/ps": [ps(MODEL, "other:1b")]}, "RuntimeError: Ollama holds another model"),
        ("B", {"/api/ps": [ps(MODEL)], "/api/generate": [{}]}, "TimeoutError: a model or a"),
        # Ollama empty, the process still listed
        ("B", {"/api/ps": [ps(MODEL), ps()], "/api/generate": [{}], "ps": [1]}, "TimeoutError"),
        ("B", {"/api/ps": [ps()], "ps": [OSError("no ps")]}, "OSError: no ps"),
        ("A", {"/api/ps": [OSError("refused")]}, "OSError: refused"),
        ("B", {"/api/ps": [ps(MODEL)], "/api/generate": [OSError("refused")]}, "OSError"),
    ],
)
def test_a_failed_action_says_so_and_never_unloads_another_model(
    runner: Any, monkeypatch: pytest.MonkeyPatch, arm: str, replies: Any, error: str
) -> None:
    calls = fake_ollama(monkeypatch, runner, replies)
    monkeypatch.setattr(runner, "UNLOAD_LIMIT_SEC", -1)
    action = runner.arm_action(arm, MODEL)
    assert action["error"].startswith(error)
    assert all(payload.get("model") == MODEL for path, payload in calls if payload)
    assert action["sec"] >= 0


@pytest.fixture
def series(runner: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """runner.main() over two questions with its token, ask, drain and action replaced: the
    calls in their order."""
    events: list[Any] = []
    auth = types.ModuleType("auth")
    jwt = types.ModuleType("auth.jwt_handler")
    jwt.create_access_token = lambda *args, **kwargs: "token"  # type: ignore[attr-defined]
    auth.jwt_handler = jwt  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "auth", auth)
    monkeypatch.setitem(sys.modules, "auth.jwt_handler", jwt)
    questions = tmp_path / "cases.jsonl"
    rows = [{"case_id": f"c-{n}", "query": f"{PLANTED} {n}"} for n in (1, 2)]
    questions.write_text("".join(json.dumps(row) + "\n" for row in rows), "utf-8")
    monkeypatch.setattr(runner, "CASES", questions)

    def ask(question: str, cap_sec: float, token: str) -> dict[str, Any]:
        events.append(("ask", question, cap_sec))
        result = {"at": 2.0, "type": "result", "route": "auto"}
        return {"events": [result], "answer": "a", "tokens": 3, "result_sec": 2.0, "total_sec": 2.5}

    def action(arm: str, model: str) -> dict[str, Any]:
        events.append(("action", arm, model))
        return {"arm": arm, "polls": 0, "sec": 0.1}

    monkeypatch.setattr(runner, "ask", ask)
    monkeypatch.setattr(runner, "drain", lambda: 0.5)
    monkeypatch.setattr(runner, "arm_action", action)
    monkeypatch.setattr(sys, "argv", ["live_runner.py", "c-1,c-2", "100/50"])
    return events


def launch_for(tmp_path: Path, launch: dict[str, Any]) -> None:
    (tmp_path / "run" / "launch.json").write_text(json.dumps(launch), "utf-8")


def saved_cases(tmp_path: Path) -> list[dict[str, Any]]:
    paths = sorted((tmp_path / "run" / "cases").glob("*.json"))
    return [json.loads(path.read_text("utf-8")) for path in paths]


def test_the_runner_acts_before_each_question_in_its_registered_order(
    runner: Any, series: list[Any], tmp_path: Path
) -> None:
    launch_for(tmp_path, {"arm": "BA", "model": MODEL})
    assert runner.main() == 0
    assert series == [
        ("action", "B", MODEL),
        ("ask", f"{PLANTED} 1", 100.0),
        ("action", "A", MODEL),
        ("ask", f"{PLANTED} 2", 50.0),
    ]
    assert [case["arm_action"]["arm"] for case in saved_cases(tmp_path)] == ["B", "A"]


def test_without_arms_the_runner_runs_as_the_original(
    runner: Any, series: list[Any], tmp_path: Path
) -> None:
    launch_for(tmp_path, {"model": MODEL})
    assert runner.main() == 0
    assert [event[0] for event in series] == ["ask", "ask"]
    assert all("arm_action" not in case for case in saved_cases(tmp_path))


def test_a_failed_action_stops_the_series_before_its_question(
    runner: Any,
    series: list[Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    launch_for(tmp_path, {"arm": "BA", "model": MODEL})
    failed = {"arm": "B", "polls": 1, "error": "TimeoutError: x", "sec": 120.0}
    monkeypatch.setattr(runner, "arm_action", lambda arm, model: failed)
    assert runner.main() == 6
    assert series == [] and saved_cases(tmp_path) == []
    assert "STOP arm: case c-1" in capsys.readouterr().out
    launch_for(tmp_path, {"arm": "B", "model": MODEL})
    with pytest.raises(AssertionError):
        runner.main()


# --- the reader: synthetic runs --------------------------------------------------------------

DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
VM_KEYS = (
    "free",
    "active",
    "inactive",
    "speculative",
    "wired",
    "purgeable",
    "compressor_stored",
    "compressor_occupied",
    *reader.COUNTERS,
)


def plan(case_id: str, arm: str, rerank: float, **more: Any) -> dict[str, Any]:
    """One question of a run: its arm and seconds. B's answer call loads the model: its first
    chunk 50 s later than A's."""
    row = {"case_id": case_id, "arm": arm, "rerank": rerank, "vector": 10.0}
    row.update(first_chunk=55.0 if arm == "B" else 5.0, action_sec=1.5 if arm == "B" else 0.05)
    row.update(more)
    return row


def reader_stand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """$T on the Mac: the reader beside step 0's sampler, V4's live_api.py and the copies."""
    folder = tmp_path / "step1"
    (folder / "runs").mkdir(parents=True)
    for path in (SAMPLER, LIVE_API, *(TOOLS / name for name in sorted(REPLACED))):
        (folder / path.name).write_bytes(path.read_bytes())
    (folder / "step1_reader.py").write_bytes((TOOLS / "step1_reader.py").read_bytes())
    monkeypatch.setattr(reader, "HERE", folder)
    return folder


def write_run(
    folder: Path,
    label: str,
    plans: list[dict[str, Any]],
    *,
    base: float,
    launch: dict[str, Any] | None = None,
    pid: int = 100,
) -> list[str]:
    """A run's directory and its sampler's file, as the drivers and step 0's sampler write
    them; the reader's --run pair."""
    run = folder / "runs" / label
    (run / "cases").mkdir(parents=True)
    stages: list[dict[str, Any]] = []
    changes: list[tuple[float, int | None]] = [(base - 100.0, pid)]
    a_reranks: list[tuple[float, float]] = []
    ends: list[float] = []

    def span(stage: str, start: float, end: float, thread: int, **fields: Any) -> None:
        stages.append({"stage": stage, "event": "start", "monotonic": start, "thread": thread})
        if stage in (reader.STREAM, reader.GENERATE):
            stages[-1].update(prompt_file=f"001-{PLANTED}.txt", prompt_est_tokens=2300)
            stages[-1]["max_tokens"] = 512
        row = {"stage": stage, "event": "end", "monotonic": end, "thread": thread}
        row.update(wall_sec=end - start, **fields)
        stages.append(row)

    for index, item in enumerate(plans, start=1):
        t0 = base + 1000.0 * (index - 1)
        vector, rerank, first = item["vector"], item["rerank"], item["first_chunk"]
        span(reader.BUILD, t0 + 0.2, t0 + 0.28, 7)
        ret_start = t0 + 0.5
        span(reader.VECTOR, t0 + 0.6, t0 + 0.6 + vector, 7, docs=20)
        rr_start = t0 + 1.0 + vector
        rr_end = rr_start + rerank
        if item.get("unfinished"):  # a question still running: its retrieval has no end
            stages.append({"stage": reader.RETRIEVAL, "event": "start", "monotonic": ret_start})
            continue
        pool = [[f"{PLANTED}-{n}.md", n, 0.01 * n] for n in range(item.get("pool_from", 0), 30)]
        stages.append({"stage": reader.POOL, "event": "start", "monotonic": rr_end - 0.05})
        stages[-1]["thread"] = 7
        stages.append(
            {"stage": reader.POOL, "event": "end", "monotonic": rr_end - 0.05, "thread": 7}
        )
        stages[-1].update(reranker_ok=True, rerank_k=5, pool=pool)
        span(reader.RERANK, rr_start, rr_end, 7, reranker_ok=True, docs=5, sources=[PLANTED])
        ret_end = rr_end + 0.2
        path = {"kind": "hybrid", "rerank_status": "ok", "retrieved_contexts": 30}
        path.update(candidates={"vector": 20, "bm25": 20, "merged": 30}, retained_contexts=5)
        path["timings_ms"] = {"pools": vector * 1000, "rerank": rerank * 1000}
        stages.append({"stage": reader.RETRIEVAL, "event": "start", "monotonic": ret_start})
        stages[-1]["thread"] = 7
        stages.append({"stage": reader.RETRIEVAL, "event": "end", "monotonic": ret_end})
        stages[-1].update(thread=7, wall_sec=ret_end - ret_start, docs=5, path=path)
        stages[-1]["sources"] = [PLANTED]
        answer = ret_end + 0.5
        error = f"ReadTimeout: {PLANTED}" if item.get("stream_error") else None
        span(reader.STREAM, answer, answer + first + 60.0, 9, first_chunk_sec=first, error=error)
        span(reader.GENERATE, answer + first + 60.5, answer + first + 100.5, 9, output_chars=40)
        span(reader.GENERATE, answer + first + 101.0, answer + first + 111.0, 9, output_chars=90)
        total = item.get("total", round(answer + first + 111.5 - t0, 3))
        ends.append(t0 + total)
        if item["arm"] == "B":
            gone = ret_start + 20.0 if item.get("linger") else t0 - 1.0
            pid += 1
            changes += [(gone, None), (answer, pid)]
        else:
            a_reranks.append((rr_start, rr_end))
            if item.get("restart"):  # another llama-server mid-retrieval
                pid += 1
                changes.append((rr_start, pid))
        before, after = ([MODEL], [MODEL]) if item["arm"] == "A" else ([MODEL], [])
        action = {"arm": item["arm"], "polls": 0 if item["arm"] == "A" else 3}
        action.update(ps_before=before, ps_after=after, sec=item["action_sec"])
        if item["arm"] == "B":
            action["llama_servers"] = item.get("llama_servers", 0)
        action["done_monotonic"] = t0 - 0.2
        if item.get("action_error"):
            action["error"] = f"RuntimeError: {PLANTED}"
        result = {"at": total - 0.1, "type": "result", "route": "auto", "answer": PLANTED}
        case = {"case_id": item["case_id"], "question": f"{PLANTED} question", "events": []}
        case["events"] += [{"at": 1.0, "type": "sources", "items": [PLANTED]}, result]
        case.update(answer=f"{PLANTED} answer", t0_monotonic=t0, http_status=200, tokens=120)
        case.update(first_token_sec=round(answer + first - t0, 3), result_sec=total - 0.1)
        case.update(last_token_sec=round(answer + first + 59.0 - t0, 3), total_sec=total)
        case.update(arm_action=action, drain_sec=0.4, started="2026-10-28T10:00:00+00:00")
        if not item.get("no_case"):
            name = f"{index:02d}-{item['case_id']}.json"
            (run / "cases" / name).write_text(json.dumps(case, ensure_ascii=False), "utf-8")
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in stages)
    (run / "stages.jsonl").write_text(text, "utf-8")
    settings = {"retrieval_top_k": 20, "rerank_top_k": 5, "rag_device": "cpu"}
    effective = {"settings": settings, "code": {"workspace": "/x"}, "all": {"note": PLANTED}}
    (run / "effective_settings.json").write_text(json.dumps(effective, ensure_ascii=False), "utf-8")
    arms = "".join(item["arm"] for item in plans)
    record = {"label": label, "mode": "prod", "cases": [item["case_id"] for item in plans]}
    record.update(client_cap_sec="1965/1320", code_sha=reader.CODE_SHA, model=MODEL, arm=arms)
    record.update(overrides={"RAG_DEVICE": "cpu", "REQUEST_TIMEOUT_SEC": "3600"})
    record.update(model_digest=DIGEST, tenant="aircargo", status="complete", runner_exit=0)
    record.update(ollama_models_before=[], ollama_load_sec=48.0, ollama_models_after=[MODEL])
    record.update(unloaded_models=[MODEL], db_tickets_before=PLANTED)
    record.update(launch or {})
    record = {key: value for key, value in record.items() if value is not None}
    (run / "launch.json").write_text(json.dumps(record, ensure_ascii=False), "utf-8")

    samples_path = folder / f"{label}.samples.jsonl"
    start = {"kind": "start", "schema": reader.SAMPLES_SCHEMA, "every_sec": 5.0}
    start.update(monotonic=base - 50.0, names=["llama-server"], log="/x/ollama_serve.log")
    lines = [start]
    counters = dict.fromkeys(VM_KEYS, 1000)
    moment = base - 50.0
    last = max(ends, default=base) + 10.0
    while moment <= last:
        now = [p for at, p in changes if at <= moment][-1]
        busy = any(low <= moment <= high for low, high in a_reranks)
        counters["pageins"] += 4000 if busy else 50
        counters["decompressions"] += 2000 if busy else 20
        procs = [{"pid": now, "rss_mib": 3000.0, "mem_mib": 3500.0, "cmprs_mib": 90.0}]
        sample = {"kind": "sample", "utc": "2026-10-28T10:00:00+00:00", "monotonic": moment}
        sample.update(log_bytes=1000, page_size=4096, vm=dict(counters), loadavg=[2.0, 2.0, 2.0])
        sample.update(swap_mib={"total": 4096.0, "used": 2000.0, "free": 2096.0})
        sample.update(procs=procs if now else [], notes=[] if now else [reader.QUIET_NOTES[0]])
        lines.append(sample)
        moment += 5.0
    lines.append({"kind": "stop", "reason": "stop file", "samples": len(lines) - 1})
    text = "".join(json.dumps(row) + "\n" for row in lines)
    samples_path.write_text(text, "utf-8")
    return ["--run", str(samples_path), str(run)]


QS = reader.CASES


def both_runs(
    folder: Path, a: dict[str, float], b: dict[str, float], **more: dict[str, Any]
) -> list[str]:
    """The registered runs, s1-baba BABA and s1-abab ABAB, A's and B's rerank seconds by question;
    more: a plan's extra fields by "<label>:<case_id>"."""
    args: list[str] = []
    for base, label in ((10000.0, "s1-baba"), (20000.0, "s1-abab")):
        plans = []
        for case_id, arm in zip(QS, reader.ARMS[label], strict=True):
            extra = more.get(f"{label}:{case_id}", {})
            plans.append(plan(case_id, arm, (a if arm == "A" else b)[case_id], **extra))
        args += write_run(folder, label, plans, base=base, pid=int(base / 100))
    return args


def read(tmp_path: Path, args: list[str], name: str = "step1.json") -> dict[str, Any]:
    out = tmp_path / name
    assert reader.main([str(out), *args]) == 0
    text = out.read_text("utf-8")
    assert "PLANTED" not in text
    assert b"\r" not in out.read_bytes()
    return json.loads(text)


A_RERANK = dict(zip(QS, (100.0, 90.0, 110.0, 80.0), strict=True))


def test_the_readings_contention_yes_and_net_faster(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    b = dict(zip(QS, (30.0, 35.0, 25.0, 40.0), strict=True))
    args = both_runs(folder, A_RERANK, b)
    record = read(tmp_path, args)
    for run in record["runs"]:
        assert run["gate"]["passed"], run["gate"]
        assert run["drivers_sha256"] == reader.DRIVERS_SHA256
        assert [ask["arm"] for ask in run["asks"]] == list(reader.ARMS[run["label"]])
        assert all(ask["read"] and ask["arm_held"] for ask in run["asks"])
    assert [pair["readable"] for pair in record["pairs"]] == [True] * 4
    contention = record["readings"]["contention"]
    assert contention["answer"] == "yes" and contention["readable_pairs"] == 4
    # 0.3, 0.3889, 0.2273, 0.5: the middle two's mean
    assert contention["median_rerank_ratio"] == pytest.approx((0.3 + 35 / 90) / 2, abs=1e-4)
    net = record["readings"]["net"]
    # B saves A's rerank less its own and pays 50 s of load and 1.45 s more of action
    assert net["answer"] == "faster"
    assert net["median_whole_diff_sec"] == pytest.approx((-70 - 55) / 2 + 51.45, abs=1e-3)
    printed = record["readings"]["printed_deciding_nothing"]
    assert printed["median_first_chunk_diff_sec"] == pytest.approx(50.0)
    faulted = printed["median_rerank_faulted_mib"]
    assert faulted["a"] > 10 * faulted["b"] > 0
    assert printed["median_a_llama_mem_at_rerank_mib"] == 3500.0
    first = record["runs"][0]["asks"][0]
    assert first["windows"]["retrieval"]["with_llama"] == 0
    assert first["pool"]["candidates"] == 30 and first["path"]["kind"] == "hybrid"
    assert reader.main([str(tmp_path / "step1.json"), *args]) == 2  # OUT exists


def test_the_readings_contention_no_and_not_faster(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    b = {case_id: 0.9 * value for case_id, value in A_RERANK.items()}
    readings = read(tmp_path, both_runs(folder, A_RERANK, b))["readings"]
    assert (readings["contention"]["answer"], readings["net"]["answer"]) == ("no", "not faster")
    assert readings["contention"]["median_rerank_ratio"] == pytest.approx(0.9)


def test_the_rules_hold_at_exactly_half_and_not_at_exactly_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    a = dict.fromkeys(QS, 100.0)
    b = dict.fromkeys(QS, 50.0)
    # whole = action + total: A 0.05 + 400.0, B 1.5 + 398.55
    more = {
        f"{label}:{case_id}": {"total": 400.0 if arm == "A" else 398.55}
        for label, arms in reader.ARMS.items()
        for case_id, arm in zip(QS, arms, strict=True)
    }
    readings = read(tmp_path, both_runs(folder, a, b, **more))["readings"]
    assert readings["contention"]["answer"] == "yes"
    assert readings["contention"]["median_rerank_ratio"] == 0.5
    assert readings["net"]["answer"] == "not faster"
    assert readings["net"]["median_whole_diff_sec"] == 0.0


def test_an_arm_that_did_not_hold_or_an_unread_ask_leaves_no_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    q1, q2, q3, q4 = QS
    more = {
        f"s1-baba:{q1}": {"linger": True},  # B: the old llama-server still there
        f"s1-baba:{q3}": {"pool_from": 1},  # B: other candidates
        f"s1-baba:{q2}": {"stream_error": True},  # A: the answer's call failed
        f"s1-abab:{q4}": {"action_error": True},  # B: its action failed
        f"s1-abab:{q2}": {"llama_servers": 1},  # B: its process outlasted the unload
    }
    b = dict(zip(QS, (30.0, 35.0, 25.0, 40.0), strict=True))
    record = read(tmp_path, both_runs(folder, A_RERANK, b, **more))
    why = {pair["case_id"]: pair["why"] for pair in record["pairs"]}
    assert "B: a llama-server inside the retrieval" in why[q1]
    assert "A: no answer call, or a failed one" in why[q2]
    assert "B: a model or a llama-server outlasted the unload" in why[q2]
    assert "not the same candidates" in why[q3]
    assert "B: no arm action of its arm, or a failed one" in why[q4]
    assert all("run s1-baba: its gate failed" in reasons for reasons in why.values())
    assert not any(pair["readable"] for pair in record["pairs"])
    readings = record["readings"]
    assert readings["contention"]["answer"] == readings["net"]["answer"] == reader.NOT_EVIDENCE
    gate = record["runs"][0]["gate"]
    assert not gate["asks"] and gate["b_held"] and not gate["passed"]
    asks = record["runs"][1]["asks"]
    assert asks[3]["arm_action"]["error"] == "RuntimeError"
    assert not record["runs"][1]["gate"]["actions"]


def test_a_restarted_server_in_a_retrieval_breaks_arm_a(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    more = {f"s1-abab:{QS[0]}": {"restart": True}}
    b = dict.fromkeys(QS, 30.0)
    record = read(tmp_path, both_runs(folder, A_RERANK, b, **more))
    pair = next(pair for pair in record["pairs"] if pair["case_id"] == QS[0])
    assert "A: not one and the same llama-server through the retrieval" in pair["why"]
    assert record["readings"]["contention"]["readable_pairs"] == 3
    assert record["readings"]["contention"]["answer"] == "yes"


def test_a_run_whose_gate_failed_gives_no_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    b = dict.fromkeys(QS, 30.0)
    args = both_runs(folder, A_RERANK, b)
    (folder / "live_runner.py").write_bytes(b"# another driver\n")
    record = read(tmp_path, args)
    assert [run["gate"]["drivers"] for run in record["runs"]] == [False, False]
    assert all(pair["why"][0].endswith("its gate failed") for pair in record["pairs"])
    assert record["readings"]["net"]["answer"] == reader.NOT_EVIDENCE


@pytest.mark.parametrize(
    "launch",
    [
        {"status": "failed", "runner_exit": 4},
        {"code_sha": "0" * 40},
        {"arm": "ABAB"},  # not s1-baba's registered arms
        {"label": "s1-r3"},  # no registered run
    ],
)
def test_the_gate_reads_the_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, launch: dict[str, Any]
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    plans = [plan(case_id, arm, 50.0) for case_id, arm in zip(QS, "BABA", strict=True)]
    args = write_run(folder, "s1-baba", plans, base=10000.0, launch=launch)
    gate = read(tmp_path, args)["runs"][0]["gate"]
    assert not gate["launch"] and not gate["passed"]


@pytest.mark.parametrize(
    ("note", "where", "passed"),
    [
        ("top: failed", "gone", True),  # its llama-server went between ps and top
        ("top: failed", "kept", False),
        ("top: no row for pid 100", "kept", True),
        ("log: no size", "gone", False),
    ],
)
def test_the_samples_gate_lets_top_fail_only_where_its_llama_server_went(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, note: str, where: str, passed: bool
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    plans = [plan(case_id, arm, 50.0) for case_id, arm in zip(QS, "BABA", strict=True)]
    args = write_run(folder, "s1-baba", plans, base=10000.0)
    samples = Path(args[1])
    rows = [json.loads(line) for line in samples.read_text("utf-8").splitlines()]
    taken = [row for row in rows if row["kind"] == "sample"]
    for row, after in pairwise(taken):
        pids = [proc["pid"] for proc in row["procs"]]
        later = [proc["pid"] for proc in after["procs"]]
        if pids and later == ([] if where == "gone" else pids):
            row["notes"].append(note)
            break
    else:
        raise AssertionError(f"no sample {where}")
    samples.write_text("".join(json.dumps(row) + "\n" for row in rows), "utf-8")
    run = read(tmp_path, args)["runs"][0]
    assert run["gate"]["samples"] is passed and run["gate"]["passed"] is passed
    assert run["samples"]["loud_notes"] == ({} if passed else {note: 1})


def test_a_question_twice_in_an_arm_is_no_pair_and_a_run_named_twice_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = reader_stand(tmp_path, monkeypatch)
    b = dict.fromkeys(QS, 30.0)
    args = both_runs(folder, A_RERANK, b)
    plans = [plan(case_id, arm, 30.0) for case_id, arm in zip(QS, "BABA", strict=True)]
    args += write_run(folder, "s1-baba-r2", plans, base=30000.0, pid=300)
    record = read(tmp_path, args)
    assert record["runs"][2]["gate"]["passed"]  # a rerun keeps its run's arms
    assert {pair["why"][0] for pair in record["pairs"]} == {
        "1 asks in A and 2 in B, not one each",
        "2 asks in A and 1 in B, not one each",
    }
    assert record["readings"]["contention"]["answer"] == reader.NOT_EVIDENCE
    with pytest.raises(SystemExit):
        reader.main([str(tmp_path / "twice.json"), *args[:3], *args[:3]])


def test_one_question_first_reads_the_first_ask_while_the_run_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first CASE line of run 1: its ask is read and its arm held; the next question's
    spans, its case file not yet written, belong to no ask."""
    folder = reader_stand(tmp_path, monkeypatch)
    plans = [
        plan(QS[0], "B", 30.0),
        plan(QS[1], "A", 90.0, no_case=True, unfinished=True),
    ]
    launch = {"status": "running", "runner_exit": None}
    record = read(tmp_path, write_run(folder, "s1-baba", plans, base=10000.0, launch=launch))
    run = record["runs"][0]
    assert len(run["asks"]) == 1
    ask = run["asks"][0]
    assert (ask["arm"], ask["read"], ask["arm_held"]) == ("B", True, True)
    assert ask["spans"][reader.VECTOR] == 1 and ask["spans"][reader.BUILD] == 1
    assert not run["gate"]["passed"]


def test_the_registered_questions_follow_step_0s_five_in_the_file_order() -> None:
    ids = [json.loads(line)["case_id"] for line in CURATED.read_text("utf-8").splitlines() if line]
    assert tuple(ids[5:9]) == reader.CASES
    assert ids[:5] == [
        "aircargo-probation-data",
        "aircargo-probation-extend",
        "aircargo-probation-dismissal",
        "aircargo-dismissal-check",
        "aircargo-dismissal-lawyer",
    ]
    assert reader.ARMS == {"s1-baba": "BABA", "s1-abab": "ABAB"}
    # each question once in each arm, at the same position
    for position in range(4):
        assert {arms[position] for arms in reader.ARMS.values()} == {"A", "B"}


def test_the_spec_names_the_tools_and_the_readings_as_they_stand() -> None:
    """Registered before the first request: the spec names the SHA-256 of each tool, of each
    original and of this test, and a later change shows here (a marked error fix updates it)."""
    spec = SPEC.read_text("utf-8")
    assert "registered before the first request" in spec
    named = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    assert sorted(named) == [
        "reports/stage1/tools/live_runner.py",
        "reports/stage1/tools/live_supervisor.py",
        "reports/stage2/tools/live_api.py",
        "reports/stage4-step0/tools/step0_sampler.py",
        "reports/stage4-step1/tools/live_runner.py",
        "reports/stage4-step1/tools/live_supervisor.py",
        "reports/stage4-step1/tools/step1_reader.py",
        "tests/test_stage4_step1_tools.py",
    ]
    for path, digest in named.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    for name, digest in reader.DRIVERS_SHA256.items():
        source = LIVE_API if name == "live_api.py" else TOOLS / name
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest, name
    assert hashlib.sha256(SAMPLER.read_bytes()).hexdigest() == reader.SAMPLER_SHA256
    assert (reader.CONTENTION_RATIO, reader.MIN_PAIRS) == (0.5, 3)
    assert reader.SETTINGS == {"retrieval_top_k": 20, "rerank_top_k": 5, "rag_device": "cpu"}
    phrases = (
        "at most 0.5",
        "at least three readable pairs",
        "below zero",
        "BABA",
        "ABAB",
        "1,965/1,320 s",
    )
    for phrase in phrases:
        assert phrase in spec, phrase
