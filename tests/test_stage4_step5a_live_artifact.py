"""Stage 4, item 5a's short live series: the record read again from its committed samples with the
committed reader; its gates, its stand, its environment, its stop and its privacy
(docs/specs/stage4-step5a-live.md, «Records»). The series stopped in its first block: its INT8
run failed step 7's look at the Mac after it again as -r2, so the block's five pairs are unread
and the series is `NOT_EVIDENCE`. Every table row of docs/evidence/stage4-step5a-live-record.md is
built from the record and its samples, and so is every number of its prose that a test below
pins."""

from __future__ import annotations

import bisect
import hashlib
import importlib.util
import json
import re
import shutil
import statistics
import sys
import tempfile
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "stage4-step5a-live" / "tools"
STEP1 = ROOT / "reports" / "stage4-step1" / "tools"
RECORDS = ROOT / "reports" / "stage4-step5a-live" / "81cd2ad"
SPEC = ROOT / "docs" / "specs" / "stage4-step5a-live.md"
CAPSULE = ROOT / "docs" / "evidence" / "stage4-step5a-live-record.md"
INDEX = ROOT / "EVIDENCE_INDEX.md"
V4 = ROOT / "reports" / "answer-prompt-v4" / "4f48fed"
STEP1_ENVIRONMENT = ROOT / "reports" / "stage4-step1" / "4f48fed" / "environment.jsonl"
MANIFEST = ROOT / "reports" / "stage4-step5a" / "onnx" / "manifest.json"
SAMPLER = ROOT / "reports" / "stage4-step0" / "tools" / "step0_sampler.py"
LIVE_API = ROOT / "reports" / "stage2" / "tools" / "live_api.py"
CODE_SHA = "81cd2ade80ea9bc5a4f3ea721a16bd05037136fd"
REGISTERED = "3136fb8"
WORKSPACE = "/Users/julia/RAG_new_chat_81cd2ad"
CORPUS = "/Users/julia/RAG_new_external_s1/aircargo"
# the reranker's snapshot: PyTorch's model and both runtimes' tokenizer
SNAPSHOT = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
# the runs whose first question was read while they went on: the first of each runtime, and the
# rerun of one (the spec's «Running it», step 6), each with its samples at that read
FIRST = {"s5a-torch-1": 94, "s5a-int8-1": 70, "s5a-int8-1-r2": 99}
# a run read again as -r2 in its place, by step 7: its after-runs line held a match; its files
# are committed beside the record, which never reads it
REPLACED = ("s5a-int8-1",)
# the rerun whose after-runs line held a match again: by step 7 its block's five pairs are unread
# and the series below sixteen, `NOT_EVIDENCE`; the series stopped after it, the runs left unable
# to lift it to sixteen
STOPPED = "s5a-int8-1-r2"
# the files as copied from the Mac, by their SHA-256, checked identical there before the copy
FILES = {
    "live5a.json": "aa2a03f0a672685f911a0ca2967206abf460eb89991ed123b5037b74c3ac7ae9",
    "s5a-torch-1.live5a.json": "3d21189fde3e1b81dcfc6be0cffbccae485ac8510d5ab9881a0c03fb7ec636d0",
    "s5a-torch-1.q1.live5a.json": "ce1e75b54f54b048ffc5ec235f08b9fdc8a1fde0eeafb8df37b7252f85503586",
    "s5a-torch-1.samples.jsonl": "3a63923336b79596af884d6f2b21db7f38fd99c5bae47ff83b3f3c57f893ce84",
    "s5a-int8-1.live5a.json": "979c969f34f78912aa373e70909784c05cd5c669da181ea618f19af32837a20f",
    "s5a-int8-1.q1.live5a.json": "224668aa2cf0f224ea2ddbb2b6543e56ae14045044e8bb1b46ab0b7956e1c579",
    "s5a-int8-1.samples.jsonl": "68c1ff7ada0bb9d24270c912b91f2bf5a9af7c352387704d70e0f5b256063ded",
    "s5a-int8-1-r2.live5a.json": "586adbb2b03ee81b980581d7f44db022944956ab4b710e2f33cf95d9034d8088",
    "s5a-int8-1-r2.q1.live5a.json": (
        "ab9f03b25e5d586edeee71802a98148d0ceb8577f7f9dddf520a7e29a33133c1"
    ),
    "s5a-int8-1-r2.samples.jsonl": (
        "d9b47f5a5ddbdf2008dced5ac0ea52ae4ac04948f20c52f8fba1527d294064aa"
    ),
    "environment.jsonl": "5420975ae1f072110db4aeeb733a73ecf202b865591887793d8898bf3def4ce3",
    "hf.txt": "2838d1392924c96cb9a9b5e808244210abbd67930888f9e8a2cda9a32b5bd925",
    "after-runs.txt": "9279f5f77e77ad1952c0176889c51b10872ed61cce6ea54a2db263d585a83596",
}
ALLOWED_NOTE = "ps: no process named llama-server"
# each run's one llama-server; top missed the rerun's row once, as it exited
RUN_PIDS = {"s5a-torch-1": 75715, "s5a-int8-1": 94555, "s5a-int8-1-r2": 1339}
EXIT_NOTE = "top: no row for pid 1339"
GATE = ("launch", "settings", "drivers", "asks", "actions", "samples", "reranker", "llama")
# what the supervisor passes the API beside the run's runtime: step 1's
OVERRIDES = {
    "OLLAMA_REQUEST_TIMEOUT_SEC": "3600",
    "RAG_DEVICE": "cpu",
    "REQUEST_TIMEOUT_SEC": "3600",
    "STREAMING_TIMEOUT_SEC": "3600",
}
# the first question's read, taken while its run went on: the notes of a run not over
RUNNING_NOTES = [
    "samples: no stop line",
    "run: 1 hybrid._vector_search started and never ended",
    "run: 1 hybrid.get_relevant_documents_with_path started and never ended",
]

_HERE = tempfile.TemporaryDirectory(prefix="live5a_reader_")


def _load() -> Any:
    """The reader as it ran on the Mac: step 1's reader beside it, which it loads at its import
    only when it is step 1's by its SHA-256."""
    here = Path(_HERE.name)
    for path in (TOOLS / "live5a_reader.py", STEP1 / "step1_reader.py"):
        shutil.copyfile(path, here / path.name)
    spec = importlib.util.spec_from_file_location("live5a_reader_record", here / "live5a_reader.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["live5a_reader_record"] = module
    spec.loader.exec_module(module)
    return module


reader = _load()
step1 = reader.step1


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def when(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def _samples(label: str) -> Any:
    notes: list[str] = []
    _, rows = step1.read_samples(RECORDS / f"{label}.samples.jsonl", notes)
    return step1.Samples(rows, notes)


record = _json(RECORDS / "live5a.json")
runs = {run["label"]: run for run in record["runs"]}
LABELS = tuple(runs)
own = {label: _json(RECORDS / f"{label}.live5a.json") for label in (*LABELS, *REPLACED)}
# every run that ran, the record's and the replaced, by its own read, in the order it ran
ran = {
    label: read["runs"][0]
    for label, read in sorted(
        own.items(), key=lambda item: item[1]["runs"][0]["samples"]["first_utc"]
    )
}
q1 = {label: _json(RECORDS / f"{label}.q1.live5a.json") for label in FIRST}
pairs = record["pairs"]
readings = record["readings"]
rerank, whole = readings["rerank"], readings["whole"]
printed = readings["printed_deciding_nothing"]
SAMPLES = {label: _samples(label) for label in ran}
AFTER = re.compile(
    r"(?P<label>s5a-(?:torch|int8)-\d(?:-r2)?) (?P<utc>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)"
    r" \{ (?P<load>\d+\.\d+ \d+\.\d+ \d+\.\d+) \} +(?P<matches>\d+)"
    r" (?P<models>\{\"models\":\[\]\}) +(?P<lock>\d+)"
)


def _after() -> dict[str, dict[str, str]]:
    """after-runs.txt, step 7's line for each run: its label, time, loads, matches, models and
    lock, each line whole by the pattern."""
    out = {}
    for line in (RECORDS / "after-runs.txt").read_text(encoding="utf-8").splitlines():
        match = AFTER.fullmatch(line)
        assert match, line
        out[match["label"]] = match.groupdict()
    return out


after = _after()


def fmt(value: float) -> str:
    return f"{value:,.3f}".replace("-", "\u2212")


def base(label: str) -> str:
    return label.removesuffix("-r2")


def runtime_of(label: str) -> str:
    return str(reader.RUNS[base(label)])


def block_of(label: str) -> int:
    """The block a run is one of the two runs of, or a rerun's run is."""
    (block,) = [n for n, labels in enumerate(reader.BLOCKS, start=1) if base(label) in labels]
    return block


def blocks_not_run() -> list[int]:
    """The blocks neither of whose runs ran: the series stopped before them."""
    bases = {base(label) for label in ran}
    return [n for n, labels in enumerate(reader.BLOCKS, start=1) if not set(labels) & bases]


def asks(label: str) -> list[dict[str, Any]]:
    return sorted(ran[label]["asks"], key=lambda ask: ask["index"])


def ask_of(pair: dict[str, Any], side: str) -> dict[str, Any]:
    """A pair's ask on one side, by its run and position."""
    return asks(pair[side]["run"])[pair[side]["index"] - 1]


def started(ask: dict[str, Any]) -> float:
    """The request's start on the monotonic clock: the retrieval's less its offset."""
    return float(ask["windows"]["retrieval"]["from"] - ask["retrieval_offset_sec"])


def call_span(ask: dict[str, Any]) -> tuple[float, float]:
    """The answer call's start and end on the monotonic clock."""
    start = started(ask) + ask["answer_call"]["offset_sec"]
    return start, start + ask["answer_call"]["wall_sec"]


def readable() -> list[dict[str, Any]]:
    """The pairs the reader counts readable; it does not read after-runs.txt."""
    return [pair for pair in pairs if pair["readable"]]


def unread() -> list[dict[str, Any]]:
    """The stopped rerun's block's pairs, which step 7 leaves unread."""
    return [pair for pair in pairs if pair["block"] == block_of(STOPPED)]


def readable_by_the_spec() -> list[dict[str, Any]]:
    return [pair for pair in readable() if pair not in unread()]


def later(label: str, key: str) -> list[float]:
    """A run's paired questions' seconds, its warm-up left out."""
    return [ask[key] for ask in asks(label) if ask["case_id"] != reader.WARM_UP]


def of_runtime(runtime: str) -> list[str]:
    return [label for label in LABELS if runtime_of(label) == runtime]


def minutes(label: str) -> float:
    """A run's length, its samples' first to last."""
    meta = ran[label]["samples"]
    return (when(meta["last_utc"]) - when(meta["first_utc"])).total_seconds() / 60


def leaning(part: dict[str, Any]) -> str:
    """Each block's pairs with INT8 below and above, in block order."""
    return ", ".join(f"{below}–{above}" for below, above in part["blocks_below_above"].values())


def spread(part: dict[str, Any]) -> tuple[list[float], list[float]]:
    """The readable pairs' ratios, PyTorch's seconds over INT8's, and savings, PyTorch's less
    INT8's, as the reader takes them."""
    ratios = [t / o for t, o in part["by_pair"].values() if o]
    savings = [t - o for t, o in part["by_pair"].values()]
    return ratios, savings


# --- the files and the tools -------------------------------------------------------------------


def test_the_files_are_the_bytes_copied_from_the_mac() -> None:
    assert sorted(path.name for path in RECORDS.iterdir()) == sorted(FILES)
    for name, digest in FILES.items():
        data = (RECORDS / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), b"\r" in data) == (digest, False), name


def test_the_record_was_read_by_the_tools_the_spec_lists() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    listed = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    tools = {
        "live5a_reader.py": listed["reports/stage4-step5a-live/tools/live5a_reader.py"],
        "step1_reader.py": listed["reports/stage4-step1/tools/step1_reader.py"],
        "step0_sampler.py": listed["reports/stage4-step0/tools/step0_sampler.py"],
    }
    assert tools == {
        "live5a_reader.py": sha(TOOLS / "live5a_reader.py"),
        "step1_reader.py": sha(STEP1 / "step1_reader.py"),
        "step0_sampler.py": sha(SAMPLER),
    }
    assert (tools["step1_reader.py"], tools["step0_sampler.py"]) == (
        reader.STEP1_SHA256,
        step1.SAMPLER_SHA256,
    )
    assert (reader.CODE_SHA, reader.SPEC) == (CODE_SHA, SPEC.relative_to(ROOT).as_posix())
    assert f"in `{REGISTERED}`" in spec
    for read in (record, *own.values(), *q1.values()):
        assert (read["schema"], read["spec"], read["tools_sha256"]) == (
            reader.SCHEMA,
            reader.SPEC,
            tools,
        )
    # the drivers the runs ran: V4's live_api.py, step 1's runner and this series' supervisor,
    # each as the spec lists it and as committed
    drivers = {
        "live_api.py": listed["reports/stage2/tools/live_api.py"],
        "live_runner.py": listed["reports/stage4-step1/tools/live_runner.py"],
        "live_supervisor.py": listed["reports/stage4-step5a-live/tools/live_supervisor.py"],
    }
    assert drivers == reader.DRIVERS_SHA256
    assert drivers == {
        "live_api.py": sha(LIVE_API),
        "live_runner.py": sha(STEP1 / "live_runner.py"),
        "live_supervisor.py": sha(TOOLS / "live_supervisor.py"),
    }
    for read in (record, *q1.values()):
        for run in read["runs"]:
            assert run["drivers_sha256"] == drivers


# --- read again --------------------------------------------------------------------------------


def test_the_pairs_the_stand_and_the_readings_are_read_again_from_the_runs() -> None:
    assert reader.read_environment(RECORDS / "environment.jsonl") == record["environment"]
    for read in (record, *own.values(), *q1.values()):
        again = reader.pair_up(read["runs"])
        assert again == read["pairs"]
        stand = reader.stand_gate(read["corpus"], read["environment"])
        assert stand == read["stand_gate"]
        assert reader.readings(again, read["runs"], stand) == read["readings"]


def test_each_runs_own_read_is_the_records_run_and_the_replaced_one_stays_out_of_it() -> None:
    assert sorted(own) == sorted([*LABELS, *REPLACED])
    for label, read in own.items():
        assert (len(read["runs"]), read["corpus"], read["environment"]) == (1, None, [])
        assert read["readings"]["rerank"]["answer"] == reader.NOT_EVIDENCE
        assert read["readings"]["printed_deciding_nothing"]["warm_up"] == {
            label: reader.warm_up(ran[label])
        }
        if label in runs:
            assert read["runs"] == [runs[label]]
            assert printed["warm_up"][label] == reader.warm_up(runs[label])
    for label in REPLACED:
        # read again as -r2 in its place, never beside it
        assert label not in runs and f"{label}-r2" in runs
        assert base(f"{label}-r2") == label


def test_the_first_questions_reads_are_their_runs_first_asks_from_the_start_of_their_samples(
    tmp_path: Path,
) -> None:
    """Taken while each went on: each one ask is its run's own read's, and its samples are the
    first lines of the committed file. INT8's file is hashed once its run is over, so its
    `reranker` point waits for the run's own read."""
    for label, size in FIRST.items():
        (run,) = q1[label]["runs"]
        (ask,) = run["asks"]
        assert ask == asks(label)[0]
        assert (ask["case_id"], ask["read"], ask["arm_held"]) == (reader.WARM_UP, True, True)
        assert ask["five"] is not None
        failed = {"launch", "asks"} | ({"reranker"} if runtime_of(label) == "onnx" else set())
        assert run["gate"] == {**{key: key not in failed for key in GATE}, "passed": False}
        assert (run["launch"]["status"], "runner_exit" in run["launch"]) == ("running", False)
        assert run["notes"] == RUNNING_NOTES
        assert (run["label"], run["dir"], run["runtime"]) == (
            label,
            ran[label]["dir"],
            runtime_of(label),
        )
        assert (run["onnx_sha256"], run["llama_pids_seen"]) == (None, 1)
        assert run["reranker_loads"] == ran[label]["reranker_loads"]
        assert run["settings"] == ran[label]["settings"]
        meta = run["samples"]
        lines = (RECORDS / f"{label}.samples.jsonl").read_bytes().splitlines(keepends=True)
        prefix = tmp_path / f"{label}.samples.jsonl"
        prefix.write_bytes(b"".join(lines[: meta["samples"] + 1]))
        notes: list[str] = []
        again, rows = step1.read_samples(prefix, notes)
        assert {**again, "loud_notes": step1.loud_notes(rows)} == meta
        assert notes == ["samples: no stop line"]
        assert (meta["samples"], meta["stop_reason"]) == (size, None)
        assert meta["first_utc"] == ran[label]["samples"]["first_utc"]


def test_the_samples_read_are_the_committed_files() -> None:
    for label in ran:
        notes: list[str] = []
        meta, rows = step1.read_samples(RECORDS / f"{label}.samples.jsonl", notes)
        assert ({**meta, "loud_notes": step1.loud_notes(rows)}, notes) == (
            ran[label]["samples"],
            [],
        )
        assert (meta["sha256"], meta["stop_reason"], meta["every_sec"]) == (
            FILES[f"{label}.samples.jsonl"],
            "stop file",
            5.0,
        )


def test_each_note_is_one_step_1_keeps_quiet_the_top_note_a_servers_exit() -> None:
    """A sample's notes are no `llama-server`, and once, in the rerun's first sample after its last
    question, top's missing row for the run's own `llama-server`, which the next sample no longer
    lists: the server's exit. Step 1's reader keeps both quiet."""
    exits = []
    for label in ran:
        rows = SAMPLES[label].rows
        assert {pid for row in rows for pid in step1.pids_of(row)} == {RUN_PIDS[label]}, label
        last = max(started(ask) + ask["total_sec"] for ask in asks(label))
        for row, after in zip(rows, [*rows[1:], {}], strict=True):
            for note in row.get("notes") or []:
                assert step1.quiet(note), (label, note)
                if note == ALLOWED_NOTE:
                    continue
                exits.append((label, note))
                assert (step1.pids_of(row), step1.pids_of(after)) == ([RUN_PIDS[label]], [])
                assert last < row["monotonic"] < after["monotonic"], label
        assert step1.loud_notes(rows) == {} == ran[label]["samples"]["loud_notes"]
    assert exits == [(STOPPED, EXIT_NOTE)]


def test_every_window_state_and_load_attaches_again_from_the_samples() -> None:
    for label in ran:
        samples = SAMPLES[label]
        assert (samples.ordered, samples.page_size) == (True, 4096)
        for ask in asks(label):
            for name in ("retrieval", "vector", "rerank"):
                window = ask["windows"][name]
                assert samples.window(window["from"], window["to"]) == window, (label, name)
            window = ask["windows"]["rerank"]
            assert samples.state(window["from"]) == ask["at_rerank_start"]
            assert ask["load1_max"] == {
                "rerank": reader.load_max(samples, window["from"], window["to"]),
                "question": reader.load_max(samples, started(ask), started(ask) + ask["total_sec"]),
            }, (label, ask["index"])


def gap(times: list[float], edge: float) -> float:
    """The distance from an edge to the nearest sample."""
    k = bisect.bisect_left(times, edge)
    return min(abs(times[j] - edge) for j in (k - 1, k) if 0 <= j < len(times))


def test_no_sample_near_an_edge_moves_what_attaches_across_it() -> None:
    """The record keeps each window's edges to the millisecond, and a question's and an answer
    call's spans are summed from rounded seconds. No sample lies within a hundredth of a second of
    a window's or an answer call's edge. Two lie that near a question's edge, 1 ms after
    `s5a-torch-1`'s second question starts and 8 ms before `s5a-int8-1`'s sixth ends; a question's
    span feeds only its load and the samples' cover, and moving either edge a hundredth of a second
    either way leaves both as the record holds them."""
    near = []
    for label in ran:
        samples = SAMPLES[label]
        times = samples.times
        for ask in asks(label):
            edges = [*call_span(ask)]
            for name in ("retrieval", "vector", "rerank"):
                edges += [ask["windows"][name]["from"], ask["windows"][name]["to"]]
            for edge in edges:
                assert gap(times, edge) > 0.01, (label, ask["index"], edge)
            start = started(ask)
            end = start + ask["total_sec"]
            near += [(label, ask["index"]) for edge in (start, end) if gap(times, edge) <= 0.01]
            for low, high in (
                (start - 0.01, end),
                (start + 0.01, end),
                (start, end - 0.01),
                (start, end + 0.01),
            ):
                load = reader.load_max(samples, low, high)
                assert load == ask["load1_max"]["question"], (label, ask["index"], low, high)
            assert times[0] < start - 0.01 and end + 0.01 < times[-1], (label, ask["index"])
    assert near == [("s5a-torch-1", 2), ("s5a-int8-1", 6)]


# --- the gates ---------------------------------------------------------------------------------


def test_the_runs_ran_in_the_registered_order_until_the_stop_a_rerun_right_after_its_run() -> None:
    assert tuple(base(label) for label in LABELS) == tuple(reader.RUNS)[: len(LABELS)]
    assert [run["runtime"] for run in record["runs"]] == list(reader.RUNS.values())[: len(LABELS)]
    assert [label for label in ran if label not in REPLACED] == list(LABELS)
    for label in REPLACED:
        order = list(ran)
        assert order[order.index(label) + 1] == f"{label}-r2"
    # nothing ran after the stop
    assert list(ran)[-1] == LABELS[-1] == STOPPED
    spans = [
        (when(ran[label]["samples"]["first_utc"]), when(ran[label]["samples"]["last_utc"]))
        for label in ran
    ]
    assert all(one[1] < two[0] for one, two in zip(spans, spans[1:], strict=False))


def test_every_run_passes_its_gate_on_all_eight_points() -> None:
    for label in ran:
        run, runtime = ran[label], runtime_of(label)
        assert run["gate"] == {**dict.fromkeys(GATE, True), "passed": True}
        assert run["notes"] == []
        launch = run["launch"]
        assert (launch["code_sha"], launch["status"], launch["runner_exit"], launch["mode"]) == (
            CODE_SHA,
            "complete",
            0,
            "prod",
        )
        assert (launch["label"], launch["arm"], launch["cases"]) == (
            label,
            reader.ARMS,
            list(reader.CASES),
        )
        assert (launch["model"], launch["model_digest"]) == (step1.MODEL, reader.MODEL_DIGEST)
        onnx = {"RAG_RERANKER_ONNX": reader.ONNX} if runtime == "onnx" else {}
        assert launch["overrides"] == {**OVERRIDES, "RAG_RERANKER_RUNTIME": runtime, **onnx}
        assert run["settings"] == reader.expected_settings(runtime)
        assert run["onnx_sha256"] == (reader.ONNX_SHA256 if runtime == "onnx" else None)
        first, *rest = run["reranker_loads"]
        assert (first["before_first_case"], first["error"]) == (True, None)
        assert all(load["error"] is None and not load["before_first_case"] for load in rest)
        assert run["llama_pids_seen"] == 1
        assert "".join(ask["arm"] for ask in asks(label)) == reader.ARMS
        for ask in asks(label):
            assert (ask["read"], ask["unread"], ask["arm_held"], ask["arm_not_held"]) == (
                True,
                [],
                True,
                [],
            )
            assert (ask["answered"], ask["route"], ask["http_status"], ask["model_calls"]) == (
                True,
                "auto",
                200,
                3,
            )
            assert ask["answer_call"]["error"] is None and ask["reranker_ok"]
            assert (ask["path"]["kind"], ask["path"]["rerank_status"]) == ("hybrid", "ok")
            assert ask["pool"]["candidates"] == ask["path"]["candidates"]["merged"]
            assert ask["pool"]["rerank_k"] == reader.SETTINGS["rerank_top_k"]
            assert ask["five"] is not None
            # the whole is the arm's action plus the question's total
            assert ask["whole_sec"] == reader.rounded(ask["total_sec"] + ask["arm_action"]["sec"])


def test_each_ask_ran_beside_the_resident_model_as_arm_a_registers() -> None:
    model = [step1.MODEL]
    for label in ran:
        for ask in asks(label):
            action = ask["arm_action"]
            assert (action["arm"], action["error"]) == ("A", None)
            # the preload sent again: the model resident before and after, no poll
            got = (action["ps_before"], action["ps_after"], action["polls"])
            assert (*got, action["llama_servers"]) == (model, model, 0, None)


def test_one_llama_server_runs_each_run_from_before_its_first_question() -> None:
    for label in ran:
        born: dict[int, float] = {}
        for row in SAMPLES[label].rows:
            for pid in step1.pids_of(row):
                born.setdefault(pid, row["monotonic"])
        ((pid, at),) = born.items()
        assert at < started(asks(label)[0])
        for ask in asks(label):
            windows = ask["windows"]
            for got in (windows["retrieval"], windows["rerank"], ask["at_rerank_start"]):
                assert got["llama_pids"] == [pid], (label, ask["index"])


def test_each_pair_is_its_blocks_question_at_one_position_on_the_same_candidates() -> None:
    """The blocks that never ran pair nothing; the block that ran pairs its five, which the
    reader counts readable (step 7, below, leaves them unread)."""
    assert [(pair["block"], pair["case_id"]) for pair in pairs] == [
        (block, case) for block in range(1, len(reader.BLOCKS) + 1) for case in reader.PAIRED
    ]
    for pair in pairs:
        torch, onnx = reader.BLOCKS[pair["block"] - 1]
        if pair["block"] in blocks_not_run():
            assert pair == {
                "block": pair["block"],
                "case_id": pair["case_id"],
                "readable": False,
                "why": [f"{torch}: 0 runs, not one", f"{onnx}: 0 runs, not one"],
            }
            continue
        assert (base(pair["torch"]["run"]), base(pair["onnx"]["run"])) == (torch, onnx)
        t, o = ask_of(pair, "torch"), ask_of(pair, "onnx")
        position = reader.CASES.index(pair["case_id"]) + 1
        assert (t["case_id"], o["case_id"], t["index"], o["index"]) == (
            pair["case_id"],
            pair["case_id"],
            position,
            position,
        )
        assert t["pool"] == o["pool"]
        assert (pair["readable"], pair["why"]) == (True, [])


def test_step_7_leaves_the_stopped_reruns_block_unread_and_the_series_not_evidence() -> None:
    """The rerun's after-runs line held a match again: its block's five are unread, and the
    twenty less them is below sixteen whatever the rest would have read, so the runs left were
    not run. The reader, which does not read the line, pairs the five, and reads `NOT_EVIDENCE`
    on them as fewer than sixteen."""
    assert (base(STOPPED), after[STOPPED]["matches"] != "0") == (REPLACED[0], True)
    assert [pair["case_id"] for pair in unread()] == list(reader.PAIRED)
    assert unread() == readable()
    assert len(pairs) - len(unread()) < reader.MIN_PAIRS
    assert readable_by_the_spec() == []
    assert blocks_not_run() == list(range(block_of(STOPPED) + 1, len(reader.BLOCKS) + 1))
    assert (rerank["answer"], whole["answer"]) == (reader.NOT_EVIDENCE, reader.NOT_EVIDENCE)
    assert (rerank["readable_pairs"], whole["readable_pairs"]) == (len(unread()), len(unread()))
    # the runs not run: no file, no line after them
    left = [label for label in reader.RUNS if label not in {base(name) for name in ran}]
    assert len(left) == len(reader.RUNS) - len(LABELS) == 6
    assert not [name for name in FILES if name.split(".")[0] in left]
    assert not set(after) & set(left)


def test_the_stand_is_v4s_corpus_and_item_5as_export() -> None:
    v4 = _json(V4 / "v4-aircargo.json")["provenance"]
    assert record["corpus"] == {"dir": CORPUS, "sha256": reader.CORPUS_SHA256}
    assert reader.CORPUS_SHA256 == v4["source_sha256"]
    manifest = _json(MANIFEST)
    assert manifest["files"]["int8/model.onnx"]["sha256"] == reader.ONNX_SHA256
    for label in ran:
        run, launch = ran[label], ran[label]["launch"]
        assert run["dir"] == f"{WORKSPACE}/live5a/runs/{label}"
        assert launch["chroma_dir"] == run["dir"] + ".chroma"
        assert (launch["workspace"], launch["cases_file"]) == (
            WORKSPACE,
            f"{WORKSPACE}/evaluation/curated_cases_aircargo.jsonl",
        )
        assert (launch["tenant"], launch["client_cap_sec"]) == ("aircargo", "1440/1200")
        assert (launch["ollama_models_before"], launch["ollama_models_after"]) == (
            [],
            [step1.MODEL],
        )
        assert launch["unloaded_models"] == [step1.MODEL]


def test_the_environment_brackets_the_series_on_step_1s_server_and_distributions() -> None:
    stage = _lines(STEP1_ENVIRONMENT)[-1]
    before, last = _lines(RECORDS / "environment.jsonl")
    for line in (before, last):
        assert line["ollama"] == stage["ollama"]
        assert line["ollama"]["server_version"] == reader.OLLAMA_VERSION
        assert len(line["ollama"]["servers"]) == 1
        assert line["distributions"] == stage["distributions"]
        assert (line["python"], line["python_version"]) == (
            stage["python"],
            stage["python_version"],
        )
    assert record["stand_gate"] == {"corpus": True, "environment": True, "passed": True}
    assert when(before["taken"]) < when(ran[LABELS[0]]["samples"]["first_utc"])
    assert when(ran[LABELS[-1]]["samples"]["last_utc"]) < when(last["taken"])


def test_the_snapshot_was_the_rerankers_alone_before_the_first_run_and_after_the_last() -> None:
    lines = (RECORDS / "hf.txt").read_text(encoding="utf-8").splitlines()
    assert lines == [SNAPSHOT] * 4


def test_after_each_run_no_model_no_lock_and_a_match_after_both_int8_runs_none_of_ours() -> None:
    """A match after the replaced run and after its rerun, none after the PyTorch run; no model
    and no lock after any. The run's own sampler saw no `llama-server` in its last samples, so
    the matches were not the series' model server."""
    assert list(after) == list(ran)
    for label, line in after.items():
        meta = ran[label]["samples"]
        assert (line["models"], line["lock"]) == ('{"models":[]}', "0")
        assert (line["matches"] == "0") == (label not in (*REPLACED, STOPPED)), label
        assert when(meta["last_utc"]) < when(line["utc"])
        rows = SAMPLES[label].rows
        assert rows[-1]["notes"] == [ALLOWED_NOTE] and not step1.pids_of(rows[-1]), label
    order = list(ran)
    for one, two in zip(order, order[1:], strict=False):
        assert when(after[one]["utc"]) < when(ran[two]["samples"]["first_utc"])


# --- privacy -----------------------------------------------------------------------------------

HEX = re.compile(r"[0-9a-f]{7,64}")
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)")
VERSION = re.compile(r"\d+(?:\.\d+)*")
PATH = re.compile(
    r"/Users/julia/(?:RAG_new_chat_81cd2ad(?:/evaluation/curated_cases_aircargo\.jsonl"
    r"|/live5a/runs/s5a-(?:torch|int8)-\d(?:-r2)?(?:\.chroma)?)?"
    r"|RAG_Support_Assistant/\.venv/bin/python|gr2_bench/ollama_serve\.log"
    r"|RAG_new_external_s1/aircargo|RAG_new_tools_ollama_v0\.33\.2/ollama"
    r"|RAG_new_ort/bge-reranker-v2-m3/int8/model\.onnx)"
)
# a pair a run read alone leaves unpaired, and why
WHY = re.compile(r"s5a-(?:torch|int8)-\d(?:-r2)?: 0 (?:runs|asks of the question), not one")
WORDS = {
    # the record's enums, schemas and the specs' paths
    *("stage4-step5a-live/v1", "stage4-step0-samples/v1"),
    *("docs/specs/stage4-step5a-live.md", "docs/specs/stage4-step0-diagnostics.md"),
    *("start", "sample", "stop", "stop file", "llama-server", ALLOWED_NOTE, EXIT_NOTE),
    *("faster", "slower", "no detected difference", reader.NOT_EVIDENCE),
    *("same order", "same set", "other set", "torch", "onnx", ""),
    *("complete", "running", "prod", "aircargo", "1440/1200", "AAAAAA", "A"),
    *("auto", "cpu", "hybrid", "ok", step1.MODEL, reader.RERANKER, "huggingface-hub"),
    *RUNNING_NOTES,
}


def strings(value: Any) -> Iterator[tuple[str, bool]]:
    """Every string of a parsed file, keys too, each with whether it is a key."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, True
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value, False


def test_the_record_holds_numbers_ids_paths_and_hashes_only() -> None:
    ids = set(ran) | set(reader.CASES) | set(FILES)
    for name in FILES:
        text = (RECORDS / name).read_text(encoding="utf-8")
        assert not re.search("[\u0400-\u04ff]", text), name
        if name.endswith(".txt"):
            continue  # after-runs.txt and hf.txt are read whole by their patterns above
        parsed = _lines(RECORDS / name) if name.endswith(".jsonl") else _json(RECORDS / name)
        for value, key in strings(parsed):
            if key:
                assert len(value) <= 40, (name, value)
                continue
            shapes = (HEX, TIME, VERSION, PATH, WHY)
            known = value in WORDS or value in ids or any(s.fullmatch(value) for s in shapes)
            assert known, (name, value)
    # a sample names a process by its executable, never its arguments or environment
    for label in ran:
        for row in _lines(RECORDS / f"{label}.samples.jsonl"):
            for proc in row.get("procs") or []:
                assert set(proc) <= {"pid", "rss_mib", "mem_mib", "cmprs_mib"}, proc


# --- the capsule -------------------------------------------------------------------------------


def show(answer: str) -> str:
    return f"`{answer}`" if answer == reader.NOT_EVIDENCE else answer


def not_run() -> list[str]:
    """The registered runs that never ran: the series stopped before them."""
    bases = {base(label) for label in ran}
    return [label for label in reader.RUNS if label not in bases]


def blocks(numbers: list[int]) -> str:
    """A run of block numbers, as the capsule names it."""
    return f"{numbers[0]}–{numbers[-1]}" if len(numbers) > 1 else str(numbers[0])


def reading_row(name: str, part: dict[str, Any], forecast: str) -> str:
    """A reading by the spec's rules: step 7 leaves the stopped rerun's block unread."""
    return (
        f"| {name} | **{show(part['answer'])}** | {len(readable_by_the_spec())} readable of"
        f" {len(pairs)}: block {block_of(STOPPED)}'s {len(unread())} unread by step 7, blocks"
        f" {blocks(blocks_not_run())} not run | {forecast} |"
    )


# the spec's outcome for each reading of the rerank, in its words
OUTCOME = {
    "faster": "INT8's idle gain reaches the chat, with its ratio and saving: the number the"
    " package question takes",
    "no detected difference": "the gain is not shown in the chat at twenty pairs: the package"
    " question names INT8 with its idle numbers and this series' medians as not shown",
    "slower": "INT8 costs the chat time, and the package goes without it",
    reader.NOT_EVIDENCE: "nothing is read",
}


def readings_rows() -> list[str]:
    return [
        reading_row(
            "The rerank: INT8's seconds below PyTorch's on more readable pairs, the exact"
            " two-sided sign test's p below 0.05, every block below on more of its pairs than"
            " above, at least sixteen readable",
            rerank,
            "faster, INT8 below on ≈ 16–19 of the 20, every block leaning INT8",
        ),
        reading_row(
            "The whole question: the same rule on the whole seconds",
            whole,
            "no detected difference more likely than faster; INT8 below on ≈ 12–15 of the 20",
        ),
        f"| The outcome, by the rerank's reading | **{show(rerank['answer'])}**:"
        f" {OUTCOME[rerank['answer']]} | the stand's gate"
        f" {'passed' if record['stand_gate']['passed'] else 'failed'} | faster |",
    ]


def reader_rows() -> list[str]:
    """The reader's reading of the five step 7 leaves unread, which it pairs: printed, deciding
    nothing."""

    def row(name: str, *cells: str) -> str:
        return f"| {name} | {' | '.join(cells)} |"

    (rerank_ratios, rerank_savings), (whole_ratios, whole_savings) = spread(rerank), spread(whole)
    return [
        row(
            "INT8 below / above / ties",
            *(f"{p['onnx_below']} / {p['onnx_above']} / {p['ties']}" for p in (rerank, whole)),
        ),
        row("By block", leaning(rerank), leaning(whole)),
        row("The exact two-sided sign test's p", str(rerank["p"]), str(whole["p"])),
        row(
            "The median ratio, PyTorch's seconds over INT8's",
            *(f"**{p['median_ratio']}**" for p in (rerank, whole)),
        ),
        row(
            "The ratio's range by pair",
            *(f"{fmt(min(r))} to {fmt(max(r))}" for r in (rerank_ratios, whole_ratios)),
        ),
        row(
            "The median saving, PyTorch's seconds less INT8's",
            *(f"**{fmt(p['median_saving_sec'])} s**" for p in (rerank, whole)),
        ),
        row(
            "The saving's range by pair",
            *(f"{fmt(min(s))} to {fmt(max(s))} s" for s in (rerank_savings, whole_savings)),
        ),
        row("The reader's answer", *(f"`{p['answer']}`" for p in (rerank, whole))),
    ]


def pair_rows() -> list[str]:
    built = []
    for pair in readable():
        t, o = pair["rerank_sec"]["torch"], pair["rerank_sec"]["onnx"]
        wt, wo = pair["whole_sec"]["torch"], pair["whole_sec"]["onnx"]
        built.append(
            f"| {pair['block']} | `{pair['case_id']}` | {fmt(t)} / {fmt(o)} | {fmt(t / o)}"
            f" | {fmt(wt)} / {fmt(wo)} | {fmt(wt - wo)} | {pair['printed']['five']} |"
        )
    return built


def run_rows() -> list[str]:
    """Every run that ran, the replaced one too: its own read's numbers, which the record never
    reads for that one."""
    built = []
    for label in ran:
        run, meta = ran[label], ran[label]["samples"]
        warm = reader.warm_up(run)
        name = f"`{label}`" + (
            ", replaced" if label in REPLACED else ", the stop" if label == STOPPED else ""
        )
        built.append(
            f"| {name} | {run['runtime']}"
            f" | {when(meta['first_utc']):%H:%M:%S}–{when(meta['last_utc']):%H:%M:%S}"
            f" | {minutes(label):.1f} | {fmt(run['reranker_loads'][0]['sec'])}"
            f" | {fmt(warm['rerank_sec'])} / {fmt(warm['build_sec'])} / {fmt(warm['whole_sec'])}"
            f" | {fmt(statistics.median(later(label, 'rerank_sec')))}"
            f" | {fmt(statistics.median(later(label, 'whole_sec')))}"
            f" | {after[label]['load'].replace(' ', ' / ')} | {after[label]['matches']} |"
        )
    return built


PRINTED = (
    ("The rerank, s", "median_rerank_sec"),
    ("The whole question, s", "median_whole_sec"),
    ("The vector search, s", "median_vector_sec"),
    ("The retrieval, s", "median_retrieval_sec"),
    ("The first token, s", "median_first_token_sec"),
    ("The question's total, s", "median_total_sec"),
    ("The answer call's first chunk, s", "median_answer_first_chunk_sec"),
    ("Pages faulted back inside the rerank, MiB", "median_rerank_faulted_mib"),
    ("llama-server's footprint at the rerank's start, MiB", "median_llama_mem_at_rerank_mib"),
    ("The swap used at the rerank's start, MiB", "median_swap_used_at_rerank_mib"),
    ("The highest 1-minute load inside the rerank", "median_load1_max_rerank"),
    ("The highest 1-minute load inside the question", "median_load1_max_question"),
)


def printed_rows() -> list[str]:
    return [
        f"| {name} | {fmt(printed[key]['torch'])} | {fmt(printed[key]['onnx'])} |"
        for name, key in PRINTED
    ]


# the spec's forecasts, in its words; " … " leaves out the spec's words between two pieces
FORECAST = (
    "the eight run gates pass, and the stand's",
    "The rerank reads **faster**: INT8 below on ≈ 16–19 of the 20 pairs, every block leaning INT8",
    "a ratio ≈ 1.5–2 and a saving ≈ 35–65 s of PyTorch's ≈ 100–135 s",
    "The whole question: INT8 below on ≈ 12–15 of the 20, the median saving about the rerank's;"
    " **no detected difference** is more likely than **faster**",
    "the same order on 16 pairs and the same set on `aircargo-matliab-check`'s four",
    "the warm-up's rerank ≈ 90–180 s for PyTorch … and ≈ 35–70 s for INT8, below its later"
    " reranks' ≈ 50–90 s",
    "A run's first question ≈ 480 s with PyTorch … and ≈ 350 s with INT8, no more than its later"
    " ones; a later one ≈ 400 s with PyTorch … and ≈ 350 s with INT8",
    "≈ 5 h 30 min of runs once the Mac is idle … A run ≈ 44 min with PyTorch and ≈ 38 min with"
    " INT8",
)


def warm(runtime: str, key: str) -> list[float]:
    return [printed["warm_up"][label][key] for label in of_runtime(runtime)]


def later_all(runtime: str, key: str) -> list[float]:
    return [value for label in of_runtime(runtime) for value in later(label, key)]


def span_minutes() -> int:
    first = runs[LABELS[0]]["samples"]["first_utc"]
    last = runs[LABELS[-1]]["samples"]["last_utc"]
    return round((when(last) - when(first)).total_seconds() / 60)


def forecast_rows() -> list[str]:
    fives = printed["fives"]
    matliab = [
        pair["printed"]["five"]
        for pair in readable()
        if pair["case_id"] == "aircargo-matliab-check"
    ]
    (replaced,) = REPLACED
    stand = "passed" if record["stand_gate"]["passed"] else "failed"
    total = span_minutes()
    five = len(unread())

    def median(values: list[float]) -> str:
        return fmt(statistics.median(values))

    def run_minutes(runtime: str) -> str:
        return " and ".join(
            f"{minutes(label):.1f}" for label in ran if runtime_of(label) == runtime
        )

    measured = (
        f"{sum(run['gate']['passed'] for run in ran.values())} of the {len(ran)} runs that ran"
        f" passed; `{replaced}` ran again as `{STOPPED}`, {after[replaced]['matches']} matches"
        f" after it and {after[STOPPED]['matches']} after the rerun, so the series stopped,"
        f" {len(not_run())} runs not run; the stand's {stand}",
        f"**{show(rerank['answer'])}**: {len(readable_by_the_spec())} readable of {len(pairs)};"
        f" on block {block_of(STOPPED)}'s {five} the reader pairs, INT8 below on"
        f" {rerank['onnx_below']}, above on {rerank['onnx_above']}",
        f"on those {five}: a ratio {rerank['median_ratio']} and a saving"
        f" {fmt(rerank['median_saving_sec'])} s of PyTorch's median"
        f" {fmt(printed['median_rerank_sec']['torch'])} s",
        f"**{show(whole['answer'])}**; on those {five}: INT8 below on {whole['onnx_below']},"
        f" above on {whole['onnx_above']}, p {whole['p']}; a median saving"
        f" {fmt(whole['median_saving_sec'])} s",
        f"on those {five}: the same order on {fives['same order']}, the same set on"
        f" {fives['same set']}, another set on {fives['other set']};"
        f" `aircargo-matliab-check`'s: {', '.join(matliab)}",
        f"PyTorch's {', '.join(fmt(v) for v in warm('torch', 'rerank_sec'))} s; INT8's"
        f" {', '.join(fmt(v) for v in warm('onnx', 'rerank_sec'))} s, its later reranks a median"
        f" {median(later_all('onnx', 'rerank_sec'))} s",
        f"a first question {median(warm('torch', 'whole_sec'))} s with PyTorch and"
        f" {median(warm('onnx', 'whole_sec'))} s with INT8; a later one a median"
        f" {median(later_all('torch', 'whole_sec'))} s and"
        f" {median(later_all('onnx', 'whole_sec'))} s",
        f"{total // 60} h {total % 60} min from the first run's first sample to the rerun's"
        f" last, where the series stopped; a run {run_minutes('torch')} min with PyTorch,"
        f" {run_minutes('onnx')} min with INT8, the replaced run and its rerun",
    )
    return [f"| {said} | {seen} |" for said, seen in zip(FORECAST, measured, strict=True)]


def file_rows() -> list[str]:
    return [
        f"| `{name}` | {(RECORDS / name).stat().st_size:,} | `{sha(RECORDS / name)}` |"
        for name in FILES
    ]


def test_the_capsule_tables_are_the_records() -> None:
    lines = CAPSULE.read_text(encoding="utf-8").splitlines()
    tables = {
        readings_rows: 3,
        reader_rows: 8,
        pair_rows: len(unread()),
        run_rows: len(ran),
        printed_rows: 12,
        forecast_rows: 8,
        file_rows: len(FILES),
    }
    for build, count in tables.items():
        built = build()
        assert len(built) == count, build.__name__
        for row in built:
            assert row in lines, row


def prose_phrases() -> list[str]:
    """The capsule prose's numbers, each in the words around it."""
    first, stop = ran[LABELS[0]]["samples"]["first_utc"], after[STOPPED]["utc"]
    (replaced,) = REPLACED
    by_hand = _lines(RECORDS / "environment.jsonl")[-1]["taken"]
    torch = [t for t, _ in rerank["by_pair"].values()]
    onnx = [o for _, o in rerank["by_pair"].values()]
    faulted = printed["median_rerank_faulted_mib"]
    differ = sum(pair["printed"]["five"] != "same order" for pair in readable())
    return [
        f"The series started at {when(first):%H:%M} UTC on 2026-10-30 and stopped at"
        f" {when(stop):%H:%M} UTC, in its first block.",
        f"`{replaced}` with {after[replaced]['matches']} matches of step 3's pattern, and its"
        f" rerun `{STOPPED}` with {after[STOPPED]['matches']}",
        f"the {len(not_run())} runs left could give {len(pairs) - len(unread())} pairs at most",
        f"were then run by hand at {when(by_hand):%H:%M} UTC",
        f"with all {len(unread())} one way the sign test's p is"
        f" {reader.sign_test(len(unread()), 0)}, above 0.05",
        f"INT8's rerank took {fmt(min(onnx))} to {fmt(max(onnx))} s on the block's five against"
        f" PyTorch's {fmt(min(torch))} to {fmt(max(torch))} s, a median ratio"
        f" {rerank['median_ratio']} against the forecast's ≈ 1.5–2",
        f"PyTorch faulted back a median {fmt(faulted['torch'])} MiB inside the rerank, INT8"
        f" {fmt(faulted['onnx'])}",
        f"The whole question a median {fmt(printed['median_whole_sec']['onnx'])} s against"
        f" {fmt(printed['median_whole_sec']['torch'])} s",
        f"INT8's five differs from PyTorch's on {differ} of the block's five here",
    ]


def test_the_capsules_prose_numbers_are_the_records() -> None:
    flat = " ".join(CAPSULE.read_text(encoding="utf-8").split())
    for phrase in prose_phrases():
        assert phrase in flat, phrase


def test_the_index_row_names_this_capsule_its_record_its_test_and_its_spec() -> None:
    (row,) = [
        line
        for line in INDEX.read_text(encoding="utf-8").splitlines()
        if "reports/stage4-step5a-live/81cd2ad" in line
    ]
    for link in (
        "[Capsule](docs/evidence/stage4-step5a-live-record.md)",
        "[record](reports/stage4-step5a-live/81cd2ad/live5a.json)",
        "[read-again and provenance test](tests/test_stage4_step5a_live_artifact.py)",
        "([spec](docs/specs/stage4-step5a-live.md))",
    ):
        assert link in row, link
    assert set(re.findall(r"reports/[\w./-]+", row)) == {
        "reports/stage4-step5a-live/81cd2ad/live5a.json"
    }
    assert "| measured |" in row
    assert f"**`{rerank['answer']}`, nothing is read**" in row
    torch = [t for t, _ in rerank["by_pair"].values()]
    onnx = [o for _, o in rerank["by_pair"].values()]
    assert (
        f"INT8's rerank {fmt(min(onnx))} to {fmt(max(onnx))} s against PyTorch's"
        f" {fmt(min(torch))} to {fmt(max(torch))} s, a median ratio {rerank['median_ratio']}"
    ) in row


def test_the_spec_names_this_record_and_its_forecasts_as_the_capsule_quotes_them() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    flat = " ".join(spec.split())
    assert "registered before the first request" in spec
    assert "[the record](../evidence/stage4-step5a-live-record.md)" in spec
    for said in FORECAST:
        for piece in said.split(" … "):
            assert piece in flat, piece
    for said in OUTCOME.values():
        assert said in flat, said
