"""reports/stage4-step5a-live/tools: the supervisor copy's marked lines and runtimes, the reader's
gates, pairs and readings.

docs/specs/stage4-step5a-live.md. Synthetic fixtures only: every number, path and text in them is
made up but the registered constants. The run files are step 1's test's (its write_run: the
shapes V4's drivers and step 0's sampler write), with what this series adds: the reranker's
runtime and file in launch.json and in the API's effective settings, the five the rerank kept in
its end row, the reranker's load at the API's start and its cached return in the warm-up's
build; the stand's corpus files and stand_env.py's lines beside the runs. No network, Ollama,
API, database, model or ONNX file: the copy is imported with its ports, Ollama and the Mac's
files replaced by fakes, the reader's hash of the ONNX file by a stand-in, and the corpus's
registered SHA-256 by the made-up files'.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

from config.settings import Settings
from tests.test_stage4_step1_tools import PLANTED, load, plan, write_run

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "stage4-step5a-live" / "tools"
STEP1 = ROOT / "reports" / "stage4-step1" / "tools"
SAMPLER = ROOT / "reports" / "stage4-step0" / "tools" / "step0_sampler.py"
LIVE_API = ROOT / "reports" / "stage2" / "tools" / "live_api.py"
CURATED = ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
MANIFEST = ROOT / "reports" / "stage4-step5a" / "onnx" / "manifest.json"
SPEC = ROOT / "docs" / "specs" / "stage4-step5a-live.md"
BEGIN, END = "# stage4-step5a-live: begin", "# stage4-step5a-live: end"
MARK = "  # stage4-step5a-live"
# Step 1's lines the copy replaces by marked ones, each once in step 1's copy.
REPLACED = (
    'DEPLOYMENT = {"RAG_DEVICE", "RAG_RETRIEVAL_TOP_K"}  # stage4-step1',
    'TARGET_PATHS = {"CHROMA", "CASES_FILE"}',
)
CODE_SHA = "81cd2ade80ea9bc5a4f3ea721a16bd05037136fd"
ONNX = "/Users/julia/RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx"
CASES = (
    "aircargo-dismissal-lawyer",
    "aircargo-dismissal-order",
    "aircargo-leave-sources",
    "aircargo-leave-compensation",
    "aircargo-leave-risk",
    "aircargo-matliab-check",
)
WARM_UP, PAIRED = CASES[0], CASES[1:]
CAP = "1440/1200"

supervisor = load(TOOLS / "live_supervisor.py", "stage4_step5a_live_supervisor")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- the supervisor copy: marked lines only ---------------------------------------------------


def unmarked(lines: list[str]) -> tuple[list[str], int]:
    """The lines outside this series' marked blocks and without its end-of-line mark; the marked
    count. Step 1's marks stay: their lines are step 1's copy's."""
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


def test_the_copy_is_step_1s_supervisor_but_for_its_marked_lines() -> None:
    data = (TOOLS / "live_supervisor.py").read_bytes()
    assert b"\r" not in data
    copy = data.decode("utf-8").split("\n")
    expected = (STEP1 / "live_supervisor.py").read_bytes().decode("utf-8").split("\n")
    for line in REPLACED:
        assert expected.count(line) == 1, line
        expected.remove(line)
    kept, marked = unmarked(copy)
    assert kept == expected
    assert marked > len(REPLACED)
    header = "\n".join(copy[copy.index(BEGIN) : copy.index(END)])
    assert "docs/specs/stage4-step5a-live.md" in header
    assert f"({sha(STEP1 / 'live_supervisor.py')[:8]}...)" in header


# --- the supervisor copy: RAG_RERANKER_RUNTIME and RAG_RERANKER_ONNX ---------------------------

# The Mac's export as the copy finds it there, whatever this machine holds: its file, its folder,
# and the file again by a path through "..".
FOLDER = ONNX.rsplit("/", 1)[0]
DOTTED = "/Users/julia/RAG_new_ort/../RAG_new_ort/bge-reranker-v2-m3/int8/model.onnx"
ON_THE_MAC = {ONNX: "file", FOLDER: "folder", DOTTED: "file"}


class MacPath(type(Path())):  # type: ignore[misc]
    def exists(self, *args: Any, **kwargs: Any) -> bool:
        return self.as_posix() in ON_THE_MAC or super().exists(*args, **kwargs)

    def is_file(self, *args: Any, **kwargs: Any) -> bool:
        if self.as_posix() in ON_THE_MAC:
            return ON_THE_MAC[self.as_posix()] == "file"
        return super().is_file(*args, **kwargs)


@pytest.fixture
def stand(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The copy's folder, $S/live5a, in tmp_path; the export where the Mac has it; both ports
    taken and Ollama unreachable, so it writes launch.json, starts nothing and stops."""
    here = tmp_path / "ws" / "live5a"
    here.mkdir(parents=True)
    (here.parent / "CODE_SHA").write_text(CODE_SHA + "\n", "utf-8")
    monkeypatch.setattr(supervisor, "HERE", here)
    monkeypatch.setattr(supervisor, "WS", here.parent)
    monkeypatch.setattr(supervisor, "RUNTIME", tmp_path / "no-runtime")
    monkeypatch.setattr(supervisor, "PY", str(tmp_path / "no-python"))
    monkeypatch.setattr(supervisor, "port_free", lambda port: False)
    monkeypatch.setattr(supervisor, "Path", MacPath)

    def no_ollama(*args: Any, **kwargs: Any) -> Any:
        raise OSError("no Ollama in a test")

    monkeypatch.setattr(supervisor, "ollama", no_ollama)
    return here


def supervise(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["live_supervisor.py", *args])
    return supervisor.main()


def launched(stand: Path, label: str) -> dict[str, Any]:
    return json.loads((stand / "runs" / label / "launch.json").read_text("utf-8"))


def test_the_copy_keeps_the_runtime_and_its_file_as_deployment_settings(
    stand: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cases = ",".join(CASES)
    named = "TENANT=aircargo,ARM=AAAAAA,RAG_RERANKER_RUNTIME="
    extra = f"{named}onnx,RAG_RERANKER_ONNX={ONNX}"
    assert supervise(monkeypatch, "s5a-int8-1", "prod", cases, CAP, extra) == 2
    launch = launched(stand, "s5a-int8-1")
    assert launch["overrides"]["RAG_RERANKER_RUNTIME"] == "onnx"
    assert launch["overrides"]["RAG_RERANKER_ONNX"] == ONNX
    assert (launch["arm"], launch["code_sha"], launch["cases"]) == ("AAAAAA", CODE_SHA, list(CASES))
    assert launch["status"] == "failed"
    assert launch["error"].startswith("RuntimeError: port 8002 is taken")
    assert "LIVE_DONE s5a-int8-1 failed exit 2" in capsys.readouterr().out
    assert supervise(monkeypatch, "s5a-torch-1", "prod", cases, CAP, f"{named}torch") == 2
    overrides = launched(stand, "s5a-torch-1")["overrides"]
    assert overrides["RAG_RERANKER_RUNTIME"] == "torch" and "RAG_RERANKER_ONNX" not in overrides
    # without the two names it writes what step 1's copy writes
    assert supervise(monkeypatch, "s5a-plain", "floor", cases, "100") == 2
    plain = launched(stand, "s5a-plain")["overrides"]
    assert not {"RAG_RERANKER_RUNTIME", "RAG_RERANKER_ONNX"} & set(plain)


@pytest.mark.parametrize(
    "extra",
    [
        "RAG_RERANKER_RUNTIME=int8",  # neither torch nor onnx
        "RAG_RERANKER_RUNTIME=ONNX",
        "RAG_RERANKER_RUNTIME=onnx",  # onnx without its file
        f"RAG_RERANKER_RUNTIME=torch,RAG_RERANKER_ONNX={ONNX}",  # a file with torch
        f"RAG_RERANKER_ONNX={ONNX}",  # a file, the runtime left at its default
        f"RAG_RERANKER_RUNTIME=onnx,RAG_RERANKER_ONNX={FOLDER}/none.onnx",  # no such file
        f"RAG_RERANKER_RUNTIME=onnx,RAG_RERANKER_ONNX={FOLDER}",  # a folder
        f"RAG_RERANKER_RUNTIME=onnx,RAG_RERANKER_ONNX={DOTTED}",  # "..", though it is the file
        "RAG_RERANKER_RUNTIME=onnx,RAG_RERANKER_ONNX=/tmp/model.onnx",  # not under the home
        "RAG_RERANKER_RUNTIME=onnx,RAG_RERANKER_ONNX=int8/model.onnx",  # not absolute
    ],
)
def test_the_copy_refuses_a_runtime_and_a_file_that_do_not_go_together(
    stand: Path, monkeypatch: pytest.MonkeyPatch, extra: str
) -> None:
    # the names the accepted runs give, so the runtime and its file alone are refused
    named = f"TENANT=aircargo,ARM=AAAAAA,{extra}"
    with pytest.raises(AssertionError):
        supervise(monkeypatch, "s5a-bad", "prod", ",".join(CASES), CAP, named)
    assert not (stand / "runs").exists()


# --- the reader: synthetic runs ---------------------------------------------------------------


@pytest.fixture(scope="module")
def reader(tmp_path_factory: pytest.TempPathFactory) -> Any:
    """The reader as it runs on the Mac: step 1's reader beside it, loaded at its import."""
    here = tmp_path_factory.mktemp("tools")
    for path in (TOOLS / "live5a_reader.py", STEP1 / "step1_reader.py"):
        shutil.copyfile(path, here / path.name)
    return load(here / "live5a_reader.py", "stage4_step5a_live5a_reader")


def environment_line(taken: str, **ollama: Any) -> dict[str, Any]:
    """A line as V4's stand_env.py writes it; ollama: its fields laid over one 0.33.2 server's."""
    server = {"pid": 812, "started": "2026-10-30T06:12:09+00:00", "binary": f"/x/{PLANTED}"}
    server["binary_changed"] = "2026-10-20T08:00:00+00:00"
    found = {"server_version": "0.33.2", "servers": [server], **ollama}
    packages = {"count": 212, "freeze_sha256": "ab" * 32, "newest": [[PLANTED, taken]]}
    packages["versions"] = {"onnxruntime": "1.23.2", PLANTED: "1.0"}
    line = {"taken": taken, "python": f"/x/{PLANTED}/python", "python_version": "3.11.9"}
    line.update(ollama=found, distributions=packages, runtime={"note": PLANTED})
    return line


BEFORE, AFTER = "2026-10-30T17:00:05+00:00", "2026-10-30T23:10:41+00:00"


def write_environment(path: Path, *lines: dict[str, Any]) -> None:
    path.write_text("".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines), "utf-8")


@pytest.fixture
def folder(reader: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """$S/live5a on the Mac: V4's live_api.py, step 1's runner, the copy, step 0's sampler and
    the two readers; the runs below it. Beside it the stand: V4's corpus files, made up and
    registered by their own SHA-256 here, and stand_env.py's lines before run 1 and after the
    last."""
    here = tmp_path / "live5a"
    (here / "runs").mkdir(parents=True)
    for path in (
        LIVE_API,
        STEP1 / "live_runner.py",
        TOOLS / "live_supervisor.py",
        SAMPLER,
        TOOLS / "live5a_reader.py",
        STEP1 / "step1_reader.py",
    ):
        shutil.copyfile(path, here / path.name)
    monkeypatch.setattr(reader, "HERE", here)
    corpus = tmp_path / "corpus"
    (corpus / "index").mkdir(parents=True)
    for name in reader.step1.CORPUS_FILES:
        (corpus / name).write_text(f"{name}: {PLANTED}", "utf-8")
    registered = {name: sha(corpus / name) for name in reader.step1.CORPUS_FILES}
    monkeypatch.setattr(reader, "CORPUS_SHA256", registered)
    write_environment(
        tmp_path / "environment.jsonl", environment_line(BEFORE), environment_line(AFTER)
    )
    return here


@pytest.fixture
def asked(reader: Any, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The reader's hash of the ONNX file, a stand-in that gives the export's SHA-256: the paths
    it was asked for, in order."""
    paths: list[str] = []

    def file_sha256(path: Path) -> str:
        paths.append(path.as_posix())
        return reader.ONNX_SHA256

    monkeypatch.setattr(reader, "file_sha256", file_sha256)
    return paths


FIVE = (3, 1, 4, 0, 2)  # the chunks a rerank kept, of the pool's 0 to 29, in its order


def write_series_run(
    reader: Any,
    folder: Path,
    label: str,
    rerank: dict[str, float],
    *,
    base: float,
    runtime: str | None = None,
    cases: tuple[str, ...] = CASES,
    more: dict[str, dict[str, Any]] | None = None,
    launch: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    every: dict[str, Any] | None = None,
    fives: dict[str, tuple[int, ...]] | None = None,
    loads: list[dict[str, Any]] | None = None,
    load1: dict[str, float] | None = None,
    beside: tuple[float, float] | None = None,
) -> list[str]:
    """A run of the series as its drivers write it, the reader's --run pair: step 1's write_run
    with arm A on every question and the rerank's seconds by question; then the runtime (its
    label's unless given) and its file in launch.json and the effective settings, each rerank's
    five in its end row, and the get_reranker calls: by default the load at the API's start,
    12.5 s before the first question, and the cached model's return, 0.001 s, in the warm-up's
    retriever build (a call marked "build" goes there, any other to the API's start). load1:
    the samples' 1-minute load inside a question's rerank, by question; beside: from when to
    when after base the samples list a second llama-server beside the resident one."""
    runtime = runtime or reader.RUNS[label.removesuffix("-r2")]
    plans = [
        plan(case_id, "A", rerank[case_id], **(more or {}).get(case_id, {})) for case_id in cases
    ]
    named = {"RAG_DEVICE": "cpu", "REQUEST_TIMEOUT_SEC": "3600", "RAG_RERANKER_RUNTIME": runtime}
    if runtime == "onnx":
        named["RAG_RERANKER_ONNX"] = ONNX
    args = write_run(
        folder,
        label,
        plans,
        base=base,
        launch={"code_sha": CODE_SHA, "overrides": named, **(launch or {})},
    )
    run = folder / "runs" / label
    every = {
        "note": PLANTED,
        "reranker_runtime": runtime,
        "reranker_onnx_path": ONNX if runtime == "onnx" else "",
        **(every or {}),
    }
    effective = {"settings": {**reader.SETTINGS, **(settings or {})}, "code": {}, "all": every}
    (run / "effective_settings.json").write_text(json.dumps(effective, ensure_ascii=False), "utf-8")
    if loads is None:
        loads = [{"wall_sec": 12.5}, {"wall_sec": 0.001, "build": True}]
    rows = [json.loads(line) for line in (run / "stages.jsonl").read_text("utf-8").splitlines()]
    out: list[dict[str, Any]] = []

    def call(start: float, given: dict[str, Any]) -> None:
        fields = {key: value for key, value in given.items() if key != "build"}
        out.append({"stage": reader.LOAD, "event": "start", "monotonic": start, "thread": 7})
        end = {"stage": reader.LOAD, "event": "end", "thread": 7}
        end.update(monotonic=start + fields["wall_sec"], **fields)
        out.append(end)

    at = base - 40.0  # the API's start: after the sampler's first sample, before any question
    for call_row in loads:
        if not call_row.get("build"):
            call(at, call_row)
            at += call_row["wall_sec"] + 0.5
    case_id = cases[0]
    builds = 0
    started = 0.0
    windows: dict[str, tuple[float, float]] = {}
    for row in rows:
        out.append(row)
        if row["stage"] == reader.step1.BUILD and row["event"] == "start":
            case_id = cases[builds]
            if builds == 0:
                for call_row in loads:
                    if call_row.get("build"):
                        call(row["monotonic"] + 0.01, call_row)
            builds += 1
        elif row["stage"] == reader.step1.RERANK and row["event"] == "start":
            started = row["monotonic"]
        elif row["stage"] == reader.step1.RERANK and row["event"] == "end":
            chunks = (fives or {}).get(case_id, FIVE)
            row.update(sources=[f"{PLANTED}-{n}.md" for n in chunks], chunk_index=list(chunks))
            windows[case_id] = (started, row["monotonic"])
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in out)
    (run / "stages.jsonl").write_text(text, "utf-8")
    if load1 or beside:
        path = folder / f"{label}.samples.jsonl"
        lines = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
        for line in lines:
            if line["kind"] != "sample":
                continue
            for name, value in (load1 or {}).items():
                if windows[name][0] <= line["monotonic"] <= windows[name][1]:
                    line["loadavg"] = [value, 2.0, 2.0]
            if beside and base + beside[0] <= line["monotonic"] <= base + beside[1]:
                foreign = {"pid": 999, "rss_mib": 900.0, "mem_mib": 1000.0, "cmprs_mib": 0.0}
                line["procs"].append(foreign)
        path.write_text("".join(json.dumps(line) + "\n" for line in lines), "utf-8")
    return args


# PyTorch's rerank seconds and INT8's, by question: INT8 at half, and at 0.4 and 0.25 on two.
TORCH = {WARM_UP: 130.0, **dict.fromkeys(PAIRED, 100.0)}
INT8 = {WARM_UP: 20.0, **dict(zip(PAIRED, (50.0, 50.0, 40.0, 25.0, 50.0), strict=True))}


def eight_runs(
    reader: Any,
    folder: Path,
    torch: dict[str, float] = TORCH,
    onnx: dict[str, float] = INT8,
    extra: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """The registered runs in their order, ABBA twice, at each runtime's rerank seconds; extra:
    write_series_run's keywords by label, its "rerank" laid over its runtime's seconds."""
    args: list[str] = []
    for n, (label, runtime) in enumerate(reader.RUNS.items(), start=1):
        given = dict((extra or {}).get(label, {}))
        seconds = {**(torch if runtime == "torch" else onnx), **given.pop("rerank", {})}
        args += write_series_run(reader, folder, label, seconds, base=10000.0 * n, **given)
    return args


def slower(counts: dict[str, int]) -> dict[str, dict[str, Any]]:
    """INT8 above PyTorch's 100 s on a run's first n paired questions, n by INT8 run."""
    return {label: {"rerank": dict.fromkeys(PAIRED[:n], 150.0)} for label, n in counts.items()}


def read(
    reader: Any, tmp_path: Path, args: list[str], name: str = "live5a.json", stand: bool = True
) -> dict[str, Any]:
    """The reader's record of the runs; with the stand's corpus and environment unless not."""
    out = tmp_path / name
    if stand:
        args = [*args, "--corpus", str(tmp_path / "corpus")]
        args += ["--environment", str(tmp_path / "environment.jsonl")]
    assert reader.main([str(out), *args]) == 0
    text = out.read_text("utf-8")
    assert "PLANTED" not in text
    assert b"\r" not in out.read_bytes()
    return json.loads(text)


def failed(run: dict[str, Any]) -> set[str]:
    return {key for key, value in run["gate"].items() if not value}


def test_int8_faster_on_every_pair(
    reader: Any,
    folder: Path,
    asked: list[str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = eight_runs(reader, folder)
    record = read(reader, tmp_path, args)
    assert asked == [ONNX] * 4  # each INT8 run's file, once; never a PyTorch run's
    for run in record["runs"]:
        assert run["gate"]["passed"], run["gate"]
        assert run["runtime"] == reader.RUNS[run["label"]]
        assert run["onnx_sha256"] == (reader.ONNX_SHA256 if run["runtime"] == "onnx" else None)
        assert run["settings"]["reranker_runtime"] == run["runtime"]
        assert [ask["case_id"] for ask in run["asks"]] == list(CASES)
        assert all(ask["read"] and ask["arm_held"] and ask["five"] for ask in run["asks"])
        # the load at the API's start, then the cached model's return in the warm-up's build
        assert run["reranker_loads"] == [
            {"sec": 12.5, "error": None, "before_first_case": True},
            {"sec": 0.001, "error": None, "before_first_case": False},
        ]
        assert run["llama_pids_seen"] == 1
        assert all(ask["load1_max"] == {"rerank": 2.0, "question": 2.0} for ask in run["asks"])
    assert record["stand_gate"] == {"corpus": True, "environment": True, "passed": True}
    assert record["environment"] == [
        {
            "taken": taken,
            "server_version": "0.33.2",
            "servers": [[812, "2026-10-30T06:12:09+00:00"]],
            "freeze_sha256": "ab" * 32,
        }
        for taken in (BEFORE, AFTER)
    ]
    assert [(pair["block"], pair["case_id"]) for pair in record["pairs"]] == [
        (block, case_id) for block in (1, 2, 3, 4) for case_id in PAIRED
    ]
    assert all(pair["readable"] and pair["why"] == [] for pair in record["pairs"])
    assert record["pairs"][0]["torch"] == {"run": "s5a-torch-1", "index": 2}
    assert record["pairs"][-1]["onnx"] == {"run": "s5a-int8-4", "index": 6}
    rerank = record["readings"]["rerank"]
    assert rerank["answer"] == "faster"
    assert (rerank["readable_pairs"], rerank["onnx_below"], rerank["onnx_above"]) == (20, 20, 0)
    assert (rerank["ties"], rerank["p"]) == (0, 0.000002)  # 2 / 2**20
    assert rerank["blocks_below_above"] == dict.fromkeys("1234", [5, 0])
    # PyTorch's 100 s over INT8's 50, 50, 40, 25 and 50 s, in each block
    assert (rerank["median_ratio"], rerank["median_saving_sec"]) == (2.0, 50.0)
    assert rerank["by_pair"][f"1:{PAIRED[3]}"] == [100.0, 25.0]
    # a question's whole seconds: its rerank's and 128.25 s more, in either runtime
    whole = record["readings"]["whole"]
    assert (whole["answer"], whole["onnx_below"], whole["median_saving_sec"]) == (
        "faster",
        20,
        50.0,
    )
    printed = record["readings"]["printed_deciding_nothing"]
    assert printed["median_rerank_sec"] == {"torch": 100.0, "onnx": 50.0}
    assert printed["median_load1_max_rerank"] == {"torch": 2.0, "onnx": 2.0}
    assert printed["fives"] == {"same order": 20, "same set": 0, "other set": 0}
    assert printed["reranker_load_sec"] == dict.fromkeys(reader.RUNS, 12.5)
    warm_up = printed["warm_up"]
    assert warm_up["s5a-torch-1"] == {
        "index": 1,
        "rerank_sec": 130.0,
        "build_sec": 0.08,
        "whole_sec": 258.25,
    }
    assert warm_up["s5a-int8-2"]["rerank_sec"] == 20.0
    assert '"answer": "faster"' in capsys.readouterr().out
    assert reader.main([str(tmp_path / "live5a.json"), *args]) == 2  # OUT exists


@pytest.mark.parametrize(
    ("counts", "answer", "p"),
    [
        ({"s5a-int8-1": 1, "s5a-int8-2": 2, "s5a-int8-3": 1, "s5a-int8-4": 1}, "faster", 0.041389),
        (
            {"s5a-int8-1": 2, "s5a-int8-2": 2, "s5a-int8-3": 1, "s5a-int8-4": 1},
            "no detected difference",
            0.115318,
        ),
    ],
)
def test_fifteen_pairs_of_twenty_read_faster_and_fourteen_do_not(
    reader: Any,
    folder: Path,
    asked: list[str],
    tmp_path: Path,
    counts: dict[str, int],
    answer: str,
    p: float,
) -> None:
    """INT8 above PyTorch on five or six pairs, every block still leaning INT8: p decides."""
    readings = read(reader, tmp_path, eight_runs(reader, folder, extra=slower(counts)))["readings"]
    late = sum(counts.values())
    for key in ("rerank", "whole"):
        reading = readings[key]
        assert (reading["onnx_below"], reading["onnx_above"]) == (20 - late, late)
        assert all(below > above for below, above in reading["blocks_below_above"].values())
        assert (reading["answer"], reading["p"]) == (answer, p)


@pytest.mark.parametrize(
    ("onnx", "extra", "blocks"),
    [
        # INT8 below on 16 of 20, but on one of block 3's five
        (INT8, slower({"s5a-int8-3": 4}), {"1": [5, 0], "2": [5, 0], "3": [1, 4], "4": [5, 0]}),
        # INT8 above on 16 of 20, but below on four of block 1's five
        (
            {WARM_UP: 20.0, **dict.fromkeys(PAIRED, 150.0)},
            {"s5a-int8-1": {"rerank": dict.fromkeys(PAIRED[:4], 50.0)}},
            {"1": [4, 1], "2": [0, 5], "3": [0, 5], "4": [0, 5]},
        ),
    ],
)
def test_a_reading_holds_only_when_every_block_leans_its_way(
    reader: Any,
    folder: Path,
    asked: list[str],
    tmp_path: Path,
    onnx: dict[str, float],
    extra: dict[str, dict[str, Any]],
    blocks: dict[str, list[int]],
) -> None:
    """p below 0.05 one way and a block leaning the other: one run's state cannot carry it."""
    rerank = read(reader, tmp_path, eight_runs(reader, folder, onnx=onnx, extra=extra))["readings"][
        "rerank"
    ]
    assert (rerank["p"], rerank["blocks_below_above"]) == (0.011818, blocks)  # 16 of 20
    assert rerank["answer"] == "no detected difference"


def test_a_tie_counts_on_neither_side(
    reader: Any, folder: Path, asked: list[str], tmp_path: Path
) -> None:
    extra = {"s5a-int8-1": {"rerank": {PAIRED[0]: 100.0}}}
    rerank = read(reader, tmp_path, eight_runs(reader, folder, extra=extra))["readings"]["rerank"]
    assert (rerank["onnx_below"], rerank["onnx_above"], rerank["ties"]) == (19, 0, 1)
    assert rerank["blocks_below_above"]["1"] == [4, 0]
    assert (rerank["answer"], rerank["p"]) == ("faster", 0.000004)  # 2 / 2**19


def test_int8_slower_on_every_pair_reads_slower(
    reader: Any, folder: Path, asked: list[str], tmp_path: Path
) -> None:
    late = {WARM_UP: 130.0, **dict.fromkeys(PAIRED, 125.0)}
    rerank = read(reader, tmp_path, eight_runs(reader, folder, onnx=late))["readings"]["rerank"]
    assert (rerank["answer"], rerank["onnx_above"], rerank["median_ratio"]) == ("slower", 20, 0.8)
    assert rerank["median_saving_sec"] == -25.0


def test_the_whole_question_is_read_apart_from_the_rerank(
    reader: Any, folder: Path, asked: list[str], tmp_path: Path
) -> None:
    """INT8 reranks faster on every pair, and its first three questions' answers take 80 s
    longer: the whole question is slower on twelve pairs and faster on eight."""
    longer = {case_id: {"total": INT8[case_id] + 128.2 + 80.0} for case_id in PAIRED[:3]}
    extra = {label: {"more": longer} for label in reader.RUNS if "int8" in label}
    readings = read(reader, tmp_path, eight_runs(reader, folder, extra=extra))["readings"]
    assert readings["rerank"]["answer"] == "faster"
    whole = readings["whole"]
    assert (whole["answer"], whole["onnx_below"], whole["onnx_above"], whole["p"]) == (
        "no detected difference",
        8,
        12,
        0.503445,
    )


@pytest.mark.parametrize("case_id", [WARM_UP, PAIRED[2]])
def test_an_unread_ask_fails_its_run_and_leaves_its_block_unread(
    reader: Any, folder: Path, asked: list[str], tmp_path: Path, case_id: str
) -> None:
    """A block's five pairs lost leave fifteen readable of the twenty: below sixteen."""
    extra = {"s5a-int8-1": {"more": {case_id: {"stream_error": True}}}}
    record = read(reader, tmp_path, eight_runs(reader, folder, extra=extra))
    assert [run["gate"]["passed"] for run in record["runs"]] == [True, False] + [True] * 6
    assert failed(record["runs"][1]) == {"asks", "passed"}
    first, rest = record["pairs"][:5], record["pairs"][5:]
    assert all("run s5a-int8-1: its gate failed" in pair["why"] for pair in first)
    assert all(pair["readable"] for pair in rest)
    whys = [why for pair in first for why in pair["why"]]
    assert whys.count("onnx: no answer call, or a failed one") == int(case_id in PAIRED)
    for key in ("rerank", "whole"):
        reading = record["readings"][key]
        assert (reading["answer"], reading["readable_pairs"]) == (reader.NOT_EVIDENCE, 15)
        assert reading["blocks_below_above"]["1"] == [0, 0]


def test_other_candidates_leave_their_pair_out(
    reader: Any, folder: Path, asked: list[str], tmp_path: Path
) -> None:
    extra = {"s5a-torch-2": {"more": {PAIRED[3]: {"pool_from": 1}}}}
    record = read(reader, tmp_path, eight_runs(reader, folder, extra=extra))
    assert all(run["gate"]["passed"] for run in record["runs"])
    pair = next(
        pair for pair in record["pairs"] if (pair["block"], pair["case_id"]) == (2, PAIRED[3])
    )
    assert pair["why"] == ["not the same candidates"] and not pair["readable"]
    rerank = record["readings"]["rerank"]
    assert (rerank["readable_pairs"], rerank["answer"], rerank["p"]) == (19, "faster", 0.000004)


def test_the_fives_are_printed_by_order_and_set_and_decide_nothing(
    reader: Any, folder: Path, asked: list[str], tmp_path: Path
) -> None:
    fives = {PAIRED[0]: (1, 3, 4, 0, 2), PAIRED[1]: (3, 1, 4, 0, 5)}  # reordered; one chunk other
    record = read(
        reader, tmp_path, eight_runs(reader, folder, extra={"s5a-int8-1": {"fives": fives}})
    )
    assert all(pair["readable"] for pair in record["pairs"])
    by_case = {pair["case_id"]: pair["printed"]["five"] for pair in record["pairs"][:5]}
    assert [by_case[case_id] for case_id in PAIRED[:3]] == ["same set", "other set", "same order"]
    printed = record["readings"]["printed_deciding_nothing"]
    assert printed["fives"] == {"same order": 18, "same set": 1, "other set": 1}


def test_the_load_inside_a_rerank_is_printed_and_decides_nothing(
    reader: Any, folder: Path, asked: list[str], tmp_path: Path
) -> None:
    """A foreign job's load inside one INT8 rerank: printed for its pair, both spans; the
    readings stand."""
    extra = {"s5a-int8-3": {"load1": {PAIRED[1]: 6.5}}}
    record = read(reader, tmp_path, eight_runs(reader, folder, extra=extra))
    pair = next(
        pair for pair in record["pairs"] if (pair["block"], pair["case_id"]) == (3, PAIRED[1])
    )
    assert pair["readable"]
    assert pair["printed"]["load1_max_rerank"] == {"torch": 2.0, "onnx": 6.5}
    assert pair["printed"]["load1_max_question"] == {"torch": 2.0, "onnx": 6.5}
    others = [other for other in record["pairs"] if other is not pair]
    assert all(other["printed"]["load1_max_rerank"]["onnx"] == 2.0 for other in others)
    rerank = record["readings"]["rerank"]
    assert (rerank["answer"], rerank["onnx_below"]) == ("faster", 20)


@pytest.mark.parametrize(
    ("label", "given", "fails"),
    [
        ("s5a-int8-1", {"launch": {"code_sha": "0" * 40}}, {"launch"}),
        ("s5a-int8-1", {"launch": {"status": "failed", "runner_exit": 4}}, {"launch"}),
        # while it runs, its ONNX file is not read
        (
            "s5a-int8-1",
            {"launch": {"status": "running", "runner_exit": None}},
            {"launch", "reranker"},
        ),
        ("s5a-int8-1", {"launch": {"mode": "floor"}}, {"launch"}),
        ("s5a-int8-1", {"launch": {"model": "qwen3:1.7b"}}, {"launch"}),
        ("s5a-int8-1", {"launch": {"model_digest": "0" * 64}}, {"launch"}),  # the name, re-pulled
        ("s5a-int8-1", {"launch": {"arm": "AAAAA"}}, {"launch"}),
        ("s5a-int8-1", {"launch": {"cases": list(PAIRED)}}, {"launch"}),
        # PyTorch by the code's default, not named
        ("s5a-torch-1", {"launch": {"overrides": {"RAG_DEVICE": "cpu"}}}, {"launch"}),
        (
            "s5a-torch-1",
            {"launch": {"overrides": {"RAG_RERANKER_RUNTIME": "torch", "RAG_RERANKER_ONNX": ONNX}}},
            {"launch"},
        ),
        ("s5a-int8-1", {"settings": {"retrieval_top_k": 14}}, {"settings"}),
        ("s5a-int8-1", {"settings": {"reranker_model": "BAAI/bge-reranker-base"}}, {"settings"}),
        ("s5a-int8-1", {"every": {"reranker_runtime": "torch"}}, {"settings"}),  # the API's own
        ("s5a-int8-1", {"every": {"reranker_onnx_path": ""}}, {"settings"}),
        ("s5a-torch-1", {"every": {"reranker_runtime": "onnx"}}, {"settings"}),
        ("s5a-int8-1", {"loads": []}, {"reranker"}),  # no get_reranker call seen
        (
            "s5a-int8-1",
            {"loads": [{"wall_sec": 2.0, "error": f"OSError: {PLANTED}"}]},
            {"reranker"},
        ),
        # the first call inside a question, not at the API's start
        ("s5a-int8-1", {"loads": [{"wall_sec": 12.5, "build": True}]}, {"reranker"}),
        ("s5a-int8-1", {"digest": "0" * 64}, {"reranker"}),  # another file at the path
        ("s5a-int8-5", {"runtime": "onnx"}, {"launch", "settings", "reranker"}),  # no such run
        # a second llama-server in the samples, in the third question's answer
        ("s5a-torch-2", {"beside": (2150.0, 2160.0)}, {"llama"}),
    ],
)
def test_the_run_gate(
    reader: Any,
    folder: Path,
    asked: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    label: str,
    given: dict[str, Any],
    fails: set[str],
) -> None:
    given = dict(given)
    if "digest" in given:
        digest = given.pop("digest")
        monkeypatch.setattr(reader, "file_sha256", lambda path: digest)
    seconds = INT8 if "int8" in label else TORCH
    run = read(
        reader, tmp_path, write_series_run(reader, folder, label, seconds, base=1e4, **given)
    )["runs"][0]
    assert failed(run) == fails | {"passed"}


@pytest.mark.parametrize(
    ("change", "fails"),
    [
        ("no stand", {"corpus", "environment"}),
        ("corpus", {"corpus"}),
        ("one line", {"environment"}),
        ("another start", {"environment"}),
        ("another version", {"environment"}),
        ("two servers", {"environment"}),
        ("another freeze", {"environment"}),
        ("not a line", {"environment"}),
    ],
)
def test_a_stand_that_fails_its_gate_makes_every_reading_not_evidence(
    reader: Any,
    folder: Path,
    asked: list[str],
    tmp_path: Path,
    change: str,
    fails: set[str],
) -> None:
    """V4's corpus files by their registered SHA-256, and stand_env.py's lines before run 1 and
    after the last: Ollama 0.33.2, one server, the same pid and start and the same installed
    distributions in each. The runs pass their gates; the readings are NOT_EVIDENCE."""
    later = environment_line(AFTER)
    if change == "corpus":
        (tmp_path / "corpus" / "chunks-report.json").write_text("changed", "utf-8")
    elif change == "another start":  # Ollama restarted between the two lines
        later["ollama"]["servers"][0]["started"] = "2026-10-30T19:40:00+00:00"
    elif change == "another version":
        later["ollama"]["server_version"] = "0.33.3"
    elif change == "two servers":
        later["ollama"]["servers"].append({**later["ollama"]["servers"][0], "pid": 813})
    elif change == "another freeze":
        later["distributions"]["freeze_sha256"] = "cd" * 32
    lines = [environment_line(BEFORE)] + ([] if change == "one line" else [later])
    write_environment(tmp_path / "environment.jsonl", *lines)
    if change == "not a line":
        with (tmp_path / "environment.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(f"{PLANTED}\n")
    record = read(reader, tmp_path, eight_runs(reader, folder), stand=change != "no stand")
    assert {key for key, value in record["stand_gate"].items() if not value} == fails | {"passed"}
    assert all(run["gate"]["passed"] for run in record["runs"])
    for key in ("rerank", "whole"):
        reading = record["readings"][key]
        assert (reading["answer"], reading["onnx_below"]) == (reader.NOT_EVIDENCE, 20)


@pytest.mark.parametrize(
    ("name", "source"),
    [("live_supervisor.py", STEP1 / "live_supervisor.py"), ("step0_sampler.py", None)],
)
def test_step_1s_supervisor_or_another_sampler_fails_the_drivers_gate(
    reader: Any,
    folder: Path,
    asked: list[str],
    tmp_path: Path,
    name: str,
    source: Path | None,
) -> None:
    data = source.read_bytes() if source else (folder / name).read_bytes() + b"\n"
    (folder / name).write_bytes(data)
    run = read(reader, tmp_path, write_series_run(reader, folder, "s5a-torch-1", TORCH, base=1e4))[
        "runs"
    ][0]
    assert failed(run) == {"drivers", "passed"}


@pytest.mark.parametrize("beside", ["none", "changed"])
def test_the_reader_will_not_load_without_step_1s_reader_beside_it(
    tmp_path: Path, beside: str
) -> None:
    here = tmp_path / "tools"
    here.mkdir()
    shutil.copyfile(TOOLS / "live5a_reader.py", here / "live5a_reader.py")
    if beside == "changed":
        (here / "step1_reader.py").write_bytes((STEP1 / "step1_reader.py").read_bytes() + b"\n")
    name = f"stage4_step5a_refused_{beside}"
    try:
        with pytest.raises(SystemExit, match="refused: step1_reader.py beside this reader"):
            load(here / "live5a_reader.py", name)
    finally:
        sys.modules.pop(name, None)


def test_file_sha256_reads_a_large_file_a_block_at_a_time(reader: Any, tmp_path: Path) -> None:
    path = tmp_path / "model.onnx"
    data = bytes(range(256)) * 12289  # 3 MiB and 256 bytes
    path.write_bytes(data)
    assert reader.file_sha256(path) == hashlib.sha256(data).hexdigest()
    assert reader.file_sha256(tmp_path / "none.onnx") is None


def test_a_rerun_is_read_in_its_runs_place_never_beside_it(
    reader: Any, folder: Path, asked: list[str], tmp_path: Path
) -> None:
    args = eight_runs(reader, folder)
    rerun = write_series_run(reader, folder, "s5a-int8-1-r2", INT8, base=90000.0)
    beside = read(reader, tmp_path, args + rerun, "beside.json")
    assert beside["runs"][8]["gate"]["passed"]  # a rerun keeps its run's runtime
    assert [pair["why"] for pair in beside["pairs"][:5]] == [["s5a-int8-1: 2 runs, not one"]] * 5
    assert beside["readings"]["rerank"]["answer"] == reader.NOT_EVIDENCE
    placed = read(reader, tmp_path, args[:3] + rerun + args[6:], "placed.json")
    assert all(pair["readable"] for pair in placed["pairs"])
    assert placed["pairs"][0]["onnx"]["run"] == "s5a-int8-1-r2"
    assert placed["readings"]["rerank"]["answer"] == "faster"
    with pytest.raises(SystemExit):
        reader.main([str(tmp_path / "twice.json"), *args[:3], *args[:3]])


@pytest.mark.parametrize("label", ["s5a-torch-1", "s5a-int8-1"])
def test_the_warm_up_is_read_while_its_run_goes_on(
    reader: Any, folder: Path, asked: list[str], tmp_path: Path, label: str
) -> None:
    """The first CASE line of each runtime's first run: the warm-up's ask is read, its arm held,
    its five read, the reranker's load read at the API's start, one llama-server seen; the next
    question's spans, its case file not yet written, belong to no ask; the ONNX file is not read
    while the run goes on."""
    seconds = INT8 if "int8" in label else TORCH
    more = {PAIRED[0]: {"no_case": True, "unfinished": True}}
    launch = {"status": "running", "runner_exit": None}
    args = write_series_run(
        reader, folder, label, seconds, base=1e4, cases=CASES[:2], more=more, launch=launch
    )
    run = read(reader, tmp_path, args)["runs"][0]
    (ask,) = run["asks"]
    assert (ask["case_id"], ask["arm"], ask["read"], ask["arm_held"]) == (WARM_UP, "A", True, True)
    assert ask["five"] is not None and ask["rerank_sec"] == seconds[WARM_UP]
    assert run["reranker_loads"][0] == {"sec": 12.5, "error": None, "before_first_case": True}
    assert run["llama_pids_seen"] == 1
    assert asked == [] and run["onnx_sha256"] is None
    assert not run["gate"]["passed"]


def test_the_registered_questions_runs_and_blocks(reader: Any) -> None:
    ids = [json.loads(line)["case_id"] for line in CURATED.read_text("utf-8").splitlines() if line]
    assert reader.CASES == CASES == tuple(ids[4:10])
    assert (reader.WARM_UP, reader.PAIRED) == (WARM_UP, PAIRED)
    assert PAIRED[:4] == reader.step1.CASES  # step 1's four, in its order
    assert reader.ARMS == "A" * len(CASES)
    assert reader.RUNS == {
        "s5a-torch-1": "torch",
        "s5a-int8-1": "onnx",
        "s5a-int8-2": "onnx",
        "s5a-torch-2": "torch",
        "s5a-torch-3": "torch",
        "s5a-int8-3": "onnx",
        "s5a-int8-4": "onnx",
        "s5a-torch-4": "torch",
    }
    # ABBA twice: a block is a PyTorch run and an INT8 one, each run in one block
    assert [[reader.RUNS[label] for label in block] for block in reader.BLOCKS] == [
        ["torch", "onnx"]
    ] * 4
    assert sorted(label for block in reader.BLOCKS for label in block) == sorted(reader.RUNS)
    assert (reader.CODE_SHA, reader.ONNX, reader.MIN_PAIRS, reader.ALPHA) == (
        CODE_SHA,
        ONNX,
        16,
        0.05,
    )
    # the stand step 1 ran: V4's corpus files, the model by its digest, Ollama 0.33.2
    step1 = json.loads((ROOT / "reports/stage4-step1/4f48fed/step1.json").read_text("utf-8"))
    assert reader.CORPUS_SHA256 == step1["corpus"]["sha256"]
    assert {run["launch"]["model_digest"] for run in step1["runs"]} == {reader.MODEL_DIGEST}
    assert reader.OLLAMA_VERSION == "0.33.2"
    assert reader.SETTINGS == {
        "retrieval_top_k": 20,
        "rerank_top_k": 5,
        "rag_device": "cpu",
        "reranker_model": "BAAI/bge-reranker-v2-m3",
    }
    # the names the reader reads are the product's settings
    names = {field.name for field in dataclasses.fields(Settings)}
    assert {*reader.SETTINGS, "reranker_runtime", "reranker_onnx_path"} <= names


def test_the_spec_names_the_tools_and_the_readings_as_they_stand(reader: Any) -> None:
    """Registered before the first request: the spec names the SHA-256 of each tool, of each
    driver and of this test, and a later change shows here (a marked error fix updates it)."""
    spec = SPEC.read_text("utf-8")
    assert "registered before the first request" in spec
    named = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.(?:py|sh))` `([0-9a-f]{64})`", spec))
    assert sorted(named) == [
        "reports/stage2/tools/live_api.py",
        "reports/stage4-step0/tools/step0_sampler.py",
        "reports/stage4-step1/tools/live_runner.py",
        "reports/stage4-step1/tools/live_supervisor.py",
        "reports/stage4-step1/tools/step1_reader.py",
        "reports/stage4-step5a-live/tools/live5a_reader.py",
        "reports/stage4-step5a-live/tools/live_supervisor.py",
        "reports/stage4-step5a-live/tools/raise_stand.sh",
        "tests/test_stage4_step5a_live_tools.py",
    ]
    for path, digest in named.items():
        assert sha(ROOT / path) == digest, path
    drivers = {
        "live_api.py": LIVE_API,
        "live_runner.py": STEP1 / "live_runner.py",
        "live_supervisor.py": TOOLS / "live_supervisor.py",
    }
    assert {name: sha(path) for name, path in drivers.items()} == reader.DRIVERS_SHA256
    assert sha(STEP1 / "step1_reader.py") == reader.STEP1_SHA256
    assert sha(SAMPLER) == reader.step1.SAMPLER_SHA256
    manifest = json.loads(MANIFEST.read_text("utf-8"))
    assert manifest["files"]["int8/model.onnx"]["sha256"] == reader.ONNX_SHA256
    phrases = (
        "ABBA twice",
        "warm-up",
        "p below 0.05",
        "every block leans its way",
        "at least sixteen readable pairs",
        "1,440/1,200 s",
        "after-runs.txt",
        "--environment $T/environment.jsonl",
        f"`{ONNX}`",
    )
    for phrase in phrases:
        assert phrase in spec, phrase
