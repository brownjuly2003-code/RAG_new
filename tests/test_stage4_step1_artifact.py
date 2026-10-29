"""Stage 4's step 1: the record read again from its committed samples with the committed reader;
its gates, its stand, its environment and its privacy (docs/specs/stage4-step1-rerank-memory.md,
«Records»). Every table row of docs/evidence/stage4-step1-record.md is built from the record and
its samples, and so is every number of its prose that a test below pins."""

from __future__ import annotations

import bisect
import hashlib
import importlib.util
import json
import re
import statistics
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "stage4-step1" / "tools"
RECORDS = ROOT / "reports" / "stage4-step1" / "4f48fed"
SPEC = ROOT / "docs" / "specs" / "stage4-step1-rerank-memory.md"
CAPSULE = ROOT / "docs" / "evidence" / "stage4-step1-record.md"
INDEX = ROOT / "EVIDENCE_INDEX.md"
V4 = ROOT / "reports" / "answer-prompt-v4" / "4f48fed"
SAMPLER = ROOT / "reports" / "stage4-step0" / "tools" / "step0_sampler.py"
LIVE_API = ROOT / "reports" / "stage2" / "tools" / "live_api.py"
CODE_SHA = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
CORPUS = "/Users/julia/RAG_new_external_s1/aircargo"
RUNS = ("s1-baba", "s1-abab")
# the files as copied from the Mac, by their SHA-256, checked identical there before the copy
FILES = {
    "step1.json": "c3b5ad317fcfea93e807a3651011bbceea692514c14424bbb601bf17cf7c762b",
    "s1-baba.step1.json": "f0f214ee3e6902f0a5efcfd7ac2cb70682cf00db604556a525d6bc315771898f",
    "s1-abab.step1.json": "8fa78a96df26e044ada25f3008619dd577dced4d071a3c822c4b199ab3a841b7",
    "s1-baba.q1.step1.json": "e08075e0d09dc97fb4d782ba1a668493c926cd9153be2f59e7451d4f0253dfd0",
    "s1-baba.samples.jsonl": "1271d4358c7ab011efb4106875e838a633d7395a7b0790e36ae62d02b11e82d5",
    "s1-abab.samples.jsonl": "3daca175ed48f8c4becbc937f83b150884ad22e6a20c2e9239b017c19948ec02",
    "environment.jsonl": "75b50d60adcfa20c2045d2035a9df0d72a29e69562afd5ba8454637a9fd24551",
}
# run 1's fourth ask, in A: the one beside the load spike
SPIKE = ("s1-baba", 4)
ALLOWED_NOTE = "ps: no process named llama-server"
GATE = ("launch", "settings", "drivers", "asks", "actions", "samples", "b_held")


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("step1_reader_record", TOOLS / "step1_reader.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["step1_reader_record"] = module
    spec.loader.exec_module(module)
    return module


reader = _load()


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
    _, rows = reader.read_samples(RECORDS / f"{label}.samples.jsonl", notes)
    return reader.Samples(rows, notes)


record = _json(RECORDS / "step1.json")
own = {label: _json(RECORDS / f"{label}.step1.json") for label in RUNS}
q1 = _json(RECORDS / "s1-baba.q1.step1.json")
v4 = _json(V4 / "v4-aircargo.json")["provenance"]
runs = {run["label"]: run for run in record["runs"]}
pairs = {pair["case_id"]: pair for pair in record["pairs"]}
SAMPLES = {label: _samples(label) for label in RUNS}


def signed(value: float, places: int) -> str:
    """A difference with its sign, a minus sign for a minus."""
    return f"{value:+,.{places}f}".replace("-", "\u2212")


def asks(label: str) -> list[dict[str, Any]]:
    return sorted(runs[label]["asks"], key=lambda ask: ask["index"])


def ask_of(side: dict[str, Any]) -> dict[str, Any]:
    """A pair's ask in one arm, by its run and position."""
    return asks(side["run"])[side["index"] - 1]


def started(ask: dict[str, Any]) -> float:
    """The request's start on the monotonic clock: the retrieval's less its offset."""
    return float(ask["windows"]["retrieval"]["from"] - ask["retrieval_offset_sec"])


def call_span(ask: dict[str, Any]) -> tuple[float, float]:
    """The answer call's start and end on the monotonic clock."""
    start = started(ask) + ask["answer_call"]["offset_sec"]
    return start, start + ask["answer_call"]["wall_sec"]


def inside(label: str, low: float, high: float) -> list[dict[str, Any]]:
    """The samples between two moments, as the reader's windows take them."""
    samples = SAMPLES[label]
    lo = bisect.bisect_left(samples.times, low)
    return list(samples.rows[lo : bisect.bisect_right(samples.times, high)])


def loads(label: str, low: float, high: float) -> list[float]:
    """The samples' 1-minute vm.loadavg between two moments."""
    return [row["loadavg"][0] for row in inside(label, low, high)]


def at_rerank(label: str, ask: dict[str, Any]) -> dict[str, Any]:
    """The sample the reader's state at the rerank's start was read from."""
    samples = SAMPLES[label]
    return dict(
        samples.rows[bisect.bisect_right(samples.times, ask["windows"]["rerank"]["from"]) - 1]
    )


def mid(values: list[float]) -> float:
    return round(statistics.median(values), 3)


def leave_one_out() -> list[tuple[str, float, float]]:
    """Each readable pair left out in turn: the two medians of the other three, unrounded."""
    exact = {p["case_id"]: p["exact"] for p in reader.pair_up(record["runs"]) if p["readable"]}
    out = []
    for left in reader.CASES:
        rest = [exact[case] for case in reader.CASES if case != left]
        ratio = statistics.median([got["rerank_ratio"] for got in rest])
        whole = statistics.median([got["whole_diff_sec"] for got in rest])
        out.append((left, ratio, whole))
    return out


def readings_rows() -> list[str]:
    got = record["readings"]
    contention, net = got["contention"], got["net"]
    return [
        f"| Contention: B's rerank seconds over A's, a median at most {reader.CONTENTION_RATIO}"
        f" | **{contention['answer']}** | a median {contention['median_rerank_ratio']} over"
        f" {contention['readable_pairs']} readable pairs | yes, a ratio ≈ 0.3–0.45 |",
        f"| Net: B's whole seconds less A's, a median below zero | **{net['answer']}**"
        f" | a median {signed(net['median_whole_diff_sec'], 3)} s over {net['readable_pairs']}"
        f" readable pairs: within 90 s of zero, the sign alone | faster at step 0's pace,"
        f" a wash at V4's |",
    ]


def ask_rows() -> list[str]:
    return [
        f"| {label} | {ask['index']} | `{ask['case_id']}` | {ask['arm']}"
        f" | {ask['arm_action']['sec']:.3f} | {ask['retrieval_sec']:.1f} | {ask['vector_sec']:.1f}"
        f" | {ask['rerank_sec']:.1f} | {ask['answer_call']['first_chunk_sec']:.1f}"
        f" | {ask['first_token_sec']:.1f} | {ask['whole_sec']:.1f} |"
        for label in RUNS
        for ask in asks(label)
    ]


def pair_rows() -> list[str]:
    out = []
    for case in reader.CASES:
        pair = pairs[case]
        a, b = pair["a"], pair["b"]
        out.append(
            f"| `{case}` | {a['run']}, {a['index']} | {b['run']}, {b['index']}"
            f" | {pair['rerank_ratio']:.4f} | {signed(pair['whole_diff_sec'], 3)} |"
        )
    got = record["readings"]
    out.append(
        f"| **The median, {got['contention']['readable_pairs']} readable pairs** | | |"
        f" **{got['contention']['median_rerank_ratio']:.4f}**"
        f" | **{signed(got['net']['median_whole_diff_sec'], 3)}** |"
    )
    return out


def loo_rows() -> list[str]:
    return [
        f"| `{left}` | {reader.rounded(ratio, 4):.4f}"
        f" | {'yes' if ratio <= reader.CONTENTION_RATIO else 'no'}"
        f" | {signed(reader.rounded(whole, 3), 3)} | {'faster' if whole < 0 else 'not faster'} |"
        for left, ratio, whole in leave_one_out()
    ]


def time_rows() -> list[str]:
    out = []
    for case in reader.CASES:
        got = pairs[case]["printed"]
        chunk = got["first_chunk_sec"]
        out.append(
            f"| `{case}` | {got['retrieval_ratio']:.4f} | {got['vector_ratio']:.4f}"
            f" | {signed(got['retrieval_diff_sec'], 3)} | {signed(got['answer_offset_diff_sec'], 3)}"
            f" | {chunk['a']:.3f} / {chunk['b']:.3f} | {signed(got['first_chunk_diff_sec'], 3)}"
            f" | {signed(got['first_token_diff_sec'], 3)} | {signed(got['total_diff_sec'], 3)} |"
        )
    return out


def memory_rows() -> list[str]:
    out = []
    for case in reader.CASES:
        pair = pairs[case]
        got = pair["printed"]
        a, b = ask_of(pair["a"]), ask_of(pair["b"])
        (proc,) = at_rerank(pair["a"]["run"], a)["procs"]
        fault, rate = got["rerank_faulted_mib"], got["rerank_faulted_mib_per_sec"]
        free = a["at_rerank_start"]["free_mib"], b["at_rerank_start"]["free_mib"]
        swap = got["swap_used_at_rerank_mib"]
        out.append(
            f"| `{case}` | {fault['a']:,.1f} / {fault['b']:,.1f} | {rate['a']:.1f} / {rate['b']:.1f}"
            f" | {free[0]:,.1f} / {free[1]:,.1f} | {swap['a']:,.0f} / {swap['b']:,.0f}"
            f" | {got['a_llama_mem_at_rerank_mib']:,.0f} / {proc['rss_mib']:,.1f}"
            f" / {proc['cmprs_mib']:,.0f} |"
        )
    return out


def median_rows() -> list[str]:
    got = record["readings"]["printed_deciding_nothing"]
    chunk, action = got["median_first_chunk_sec"], got["median_action_sec"]
    fault, rate = got["median_rerank_faulted_mib"], got["median_rerank_faulted_mib_per_sec"]
    return [
        f"| The retrieval, B over A | {got['median_retrieval_ratio']} |",
        f"| The vector search, B over A | {got['median_vector_ratio']} |",
        f"| The retrieval, B − A | {signed(got['median_retrieval_diff_sec'], 3)} s |",
        f"| The answer call's start, B − A | {signed(got['median_answer_offset_diff_sec'], 3)} s |",
        f"| The answer's first chunk, A / B | {chunk['a']} / {chunk['b']} s |",
        f"| The answer's first chunk, B − A | {signed(got['median_first_chunk_diff_sec'], 3)} s |",
        f"| The first token, B − A | {signed(got['median_first_token_diff_sec'], 3)} s |",
        f"| The total, B − A | {signed(got['median_total_diff_sec'], 3)} s |",
        f"| Pages faulted back in the rerank, A / B | {fault['a']:,} / {fault['b']:,} MiB |",
        f"| The same a second, A / B | {rate['a']} / {rate['b']} MiB |",
        f"| A's llama-server footprint at its rerank's start | {got['median_a_llama_mem_at_rerank_mib']:,} MiB |",
        f"| The arm's action, A / B | {action['a']} / {action['b']} s |",
    ]


def load_rows() -> list[str]:
    out = []
    for label in RUNS:
        for ask in asks(label):
            window = ask["windows"]["rerank"]
            rerank = loads(label, window["from"], window["to"])
            call = loads(label, *call_span(ask))
            out.append(
                f"| {label} | {ask['index']} | `{ask['case_id']}` | {ask['arm']}"
                f" | {len(rerank)} | {mid(rerank)} / {max(rerank)}"
                f" | {len(call)} | {mid(call)} / {max(call)} |"
            )
    return out


def pace_rows() -> list[str]:
    stage = {row["case_id"]: row for row in _lines(V4 / "v4-aircargo.cases.jsonl")}
    out = []
    for case in reader.CASES:
        then = stage[case]
        a, b = ask_of(pairs[case]["a"]), ask_of(pairs[case]["b"])
        out.append(
            f"| `{case}` | {then['vector_sec']:.1f} / {then['rerank_sec']:.1f}"
            f" | {a['vector_sec']:.1f} / {a['rerank_sec']:.1f}"
            f" | {b['vector_sec']:.1f} / {b['rerank_sec']:.1f} |"
        )
    return out


def forecast_rows() -> list[str]:
    got = record["readings"]
    contention, net = got["contention"], got["net"]
    printed = got["printed_deciding_nothing"]
    firsts = [(label, asks(label)[0]) for label in RUNS]
    later = [ask["total_sec"] for label in RUNS for ask in asks(label)[1:]]
    spans = [
        (when(runs[label]["samples"]["last_utc"]) - when(runs[label]["samples"]["first_utc"]))
        for label in RUNS
    ]
    before, after = _lines(RECORDS / "environment.jsonl")
    mac = (when(after["taken"]) - when(before["taken"])).total_seconds() / 60
    return [
        f"| Contention **yes**, a median ratio ≈ 0.3–0.45 | **{contention['answer']}**,"
        f" {contention['median_rerank_ratio']}: below the range |",
        f"| Net **faster** at step 0's pace, a wash at V4's | **{net['answer']}**,"
        f" {signed(net['median_whole_diff_sec'], 3)} s: the sign alone |",
        f"| B pays ≈ 48 s of load in its answer | its first chunk less A's, a median"
        f" {signed(printed['median_first_chunk_diff_sec'], 3)} s |",
        f"| B may save as much in its retrieval | its retrieval less A's, a median"
        f" {signed(printed['median_retrieval_diff_sec'], 3)} s |",
        "| A run's first question ≈ 655 s | "
        + " and ".join(f"{ask['total_sec']:.1f} s ({ask['arm']}, {label})" for label, ask in firsts)
        + " |",
        f"| A later question ≈ 440 s | {min(later):.1f}–{max(later):.1f} s,"
        f" a median {statistics.median(later):.1f} s |",
        "| A run ≈ 36 min | the samples span "
        + " and ".join(f"{span.total_seconds() / 60:.1f}" for span in spans)
        + " min |",
        f"| ≈ 1 h 20 min of the Mac | {mac:.0f} min from the environment line before run 1"
        f" to the one after run 2 |",
    ]


def file_rows() -> list[str]:
    return [
        f"| `{name}` | {(RECORDS / name).stat().st_size:,} | `{sha(RECORDS / name)}` |"
        for name in FILES
    ]


def spike_phrases() -> list[str]:
    """Where run 1's load peak falls: after its fourth ask's rerank, inside its answer call; and
    how far the net reading stands from that pair."""
    label, index = SPIKE
    rows = SAMPLES[label].rows
    peak = max(rows, key=lambda row: row["loadavg"][0])
    ask = asks(label)[index - 1]
    window = ask["windows"]["rerank"]
    start, end = call_span(ask)
    rerank = loads(label, window["from"], window["to"])
    after = inside(label, window["to"], end)
    above = next(row for row in after if row["loadavg"][0] > max(rerank))
    case = ask["case_id"]
    exact = {p["case_id"]: p["exact"] for p in reader.pair_up(record["runs"]) if p["readable"]}
    rest = [exact[other]["whole_diff_sec"] for other in reader.CASES if other != case]
    turning = -statistics.median(rest)
    tail = ask["total_sec"] - ask["answer_call"]["offset_sec"]
    bound = exact[case]["whole_diff_sec"] + tail
    return [
        f"Run 1's 1-minute load peaked at {peak['loadavg'][0]} at {peak['utc'][11:]},"
        f" inside its fourth ask's answer call",
        f"Inside that ask's rerank ({len(rerank)} samples) the load had a median of {mid(rerank)}"
        f" and a highest of {max(rerank)}",
        f"the first sample above {max(rerank)} is the first after the rerank, {above['utc'][11:]}"
        f" ({above['loadavg'][0]}), {above['monotonic'] - start:.1f} s into the answer call",
        f"the net median stays below zero while this pair's difference is below"
        f" {signed(turning, 3)} s",
        f"less all {tail:.3f} s of A's ask from its answer call's start, the difference is still"
        f" {signed(bound, 3)} s",
    ]


def computed_phrases() -> list[str]:
    """The prose's numbers the test pins, each built from the record and its samples."""
    reranks = [
        load
        for label in RUNS
        for ask in asks(label)
        for load in loads(label, ask["windows"]["rerank"]["from"], ask["windows"]["rerank"]["to"])
    ]
    apart = [
        abs(started(late) - started(early)) / 60
        for early, late in zip(asks(RUNS[0]), asks(RUNS[1]), strict=True)
    ]
    held = [
        ask["at_rerank_start"]["llama_mem_mib"]
        for label in RUNS
        for ask in asks(label)
        if ask["arm"] == "A"
    ]
    return [
        f"Inside the eight reranks the 1-minute load never passed {max(reranks)}",
        f"A question's two asks were {min(apart):.1f}–{max(apart):.1f} min apart",
        f"llama-server's footprint was {min(held):,.0f}–{max(held):,.0f} MiB",
    ]


def stand_phrases() -> list[str]:
    """The provenance section's numbers the test pins, each built from the record and its
    samples."""
    every = [ask for label in RUNS for ask in asks(label)]
    secs = {arm: [ask["arm_action"]["sec"] for ask in every if ask["arm"] == arm] for arm in "AB"}
    pools = [str(ask_of(pairs[case]["a"])["pool"]["candidates"]) for case in reader.CASES]
    preload = [runs[label]["launch"]["ollama_load_sec"] for label in RUNS]
    noted = [runs[label]["samples"]["sample_notes"][ALLOWED_NOTE] for label in RUNS]
    load = [[row["loadavg"][0] for row in SAMPLES[label].rows] for label in RUNS]
    five = [SAMPLES[label].rows[0]["loadavg"][1] for label in RUNS]
    before, after = _lines(RECORDS / "environment.jsonl")
    mac = (when(after["taken"]) - when(before["taken"])).total_seconds() / 60
    return [
        f"The runs took {mac:.0f} min of the Mac.",
        f"That took {min(secs['A']):.3f}–{max(secs['A']):.3f} s, with no poll.",
        f"That took {min(secs['B']):.3f}–{max(secs['B']):.3f} s, with one poll.",
        f"by the pool's SHA-256: {', '.join(pools[:-1])} and {pools[-1]}.",
        f"The supervisor's preload took {preload[0]} s in run 1 and {preload[1]} s in run 2.",
        f"in {noted[0]} samples of run 1 and {noted[1]}",
        f"a median of {mid(load[0])} in run 1 (up to {max(load[0])}) and {mid(load[1])}",
        f"in run 2 (up to {max(load[1])})",
        f"the 5-minute load was {five[0]} and {five[1]} at the runs' first samples, below the"
        f" idle rule's 2",
    ]


def prose_phrases() -> list[str]:
    """The later sections' ranges the test pins, each built from the record and its samples."""
    label, index = SPIKE
    spike = asks(label)[index - 1]
    a_side = [ask_of(pairs[case]["a"]) for case in reader.CASES]
    b_side = [ask_of(pairs[case]["b"]) for case in reader.CASES]
    others = [
        (run, ask) for run in RUNS for ask in asks(run) if (run, ask["index"]) != (label, index)
    ]
    calls = [mid(loads(run, *call_span(ask))) for run, ask in others]
    chunks = [ask["answer_call"]["first_chunk_sec"] for run, ask in others if ask["arm"] == "A"]
    rows = SAMPLES[label].rows
    moved = [
        (rows[k - 1], rows[k])
        for k in range(1, len(rows))
        if rows[k]["swap_mib"]["total"] != rows[k - 1]["swap_mib"]["total"]
    ]
    (was, now), (_, back) = moved
    free = [[ask["at_rerank_start"]["free_mib"] for ask in side] for side in (a_side, b_side)]
    rss = [
        at_rerank(pairs[case]["a"]["run"], ask)["procs"][0]["rss_mib"]
        for case, ask in zip(reader.CASES, a_side, strict=True)
    ]
    stage = {row["case_id"]: row for row in _lines(V4 / "v4-aircargo.cases.jsonl")}
    then = [stage[case] for case in reader.CASES]
    vector = [ask["vector_sec"] for run in RUNS for ask in asks(run)]
    reranks = [ask["rerank_sec"] for ask in a_side]
    v4_vector = [row["vector_sec"] for row in then]
    v4_rerank = [row["rerank_sec"] for row in then]
    return [
        f"The answer calls ran higher: a median of {min(calls)}–{max(calls)}, but for one ask.",
        f"The swap's total went from {was['swap_mib']['total']:,.0f}"
        f" to {now['swap_mib']['total']:,.0f} MiB at {now['utc'][11:]}",
        f"{now['swap_mib']['used']:,.1f} MiB in use; it went back to"
        f" {back['swap_mib']['total']:,.0f} MiB at {back['utc'][11:]}, after the run's last ask",
        f"That answer's first chunk took {spike['answer_call']['first_chunk_sec']} s, against"
        f" {min(chunks)}–{max(chunks)} s in A's other three asks.",
        f"At A's rerank's start {min(free[0]):,.1f}–{max(free[0]):,.1f} MiB were free,"
        f" at B's {min(free[1]):,.1f}–{max(free[1]):,.1f} MiB.",
        f"and its RSS {min(rss):,.1f}–{max(rss):,.1f} MiB",
        f"{min(vector):.1f}–{max(vector):.1f} s, against V4's"
        f" {min(v4_vector):.1f}–{max(v4_vector):.1f} s for these",
        f"A's reranks took {min(reranks):.1f}–{max(reranks):.1f} s against V4's"
        f" {min(v4_rerank):.1f}–{max(v4_rerank):.1f} s",
    ]


def test_the_files_are_the_bytes_copied_from_the_mac() -> None:
    assert sorted(path.name for path in RECORDS.iterdir()) == sorted(FILES)
    for name, digest in FILES.items():
        data = (RECORDS / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), b"\r" in data) == (digest, False), name


def test_the_record_was_read_by_the_tools_the_spec_lists() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    listed = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    tools = {
        "step1_reader.py": listed["reports/stage4-step1/tools/step1_reader.py"],
        "step0_sampler.py": listed["reports/stage4-step0/tools/step0_sampler.py"],
    }
    assert tools == {
        "step1_reader.py": sha(TOOLS / "step1_reader.py"),
        "step0_sampler.py": sha(SAMPLER),
    }
    assert tools["step0_sampler.py"] == reader.SAMPLER_SHA256
    assert (reader.CODE_SHA, reader.SPEC) == (CODE_SHA, SPEC.relative_to(ROOT).as_posix())
    for read in (record, *own.values(), q1):
        assert (read["schema"], read["spec"], read["tools_sha256"]) == (
            reader.SCHEMA,
            reader.SPEC,
            tools,
        )
    # the drivers the runs ran: V4's live_api.py and this step's copies of its runner and
    # supervisor, each as the spec lists it and as committed
    drivers = {
        "live_api.py": listed["reports/stage2/tools/live_api.py"],
        "live_runner.py": listed["reports/stage4-step1/tools/live_runner.py"],
        "live_supervisor.py": listed["reports/stage4-step1/tools/live_supervisor.py"],
    }
    assert drivers == reader.DRIVERS_SHA256
    assert drivers == {
        "live_api.py": sha(LIVE_API),
        "live_runner.py": sha(TOOLS / "live_runner.py"),
        "live_supervisor.py": sha(TOOLS / "live_supervisor.py"),
    }
    assert drivers["live_api.py"] == v4["tools_sha256"]["live_api.py"]
    for run in (*record["runs"], *q1["runs"]):
        assert run["drivers_sha256"] == drivers


def test_the_pairs_and_both_readings_are_read_again_from_the_asks() -> None:
    for read in (record, *own.values(), q1):
        again = reader.pair_up(read["runs"])
        assert [{k: v for k, v in pair.items() if k != "exact"} for pair in again] == read["pairs"]
        assert reader.readings(again) == read["readings"]


def test_each_runs_own_read_is_the_records_run() -> None:
    for label, read in own.items():
        assert (read["runs"], read["corpus"]) == ([runs[label]], None)


def test_the_first_questions_read_is_run_ones_first_ask_from_the_start_of_its_samples(
    tmp_path: Path,
) -> None:
    """Taken while run 1 went on: its one ask is the record's, and its samples are the first
    lines of the committed file."""
    (run,) = q1["runs"]
    (ask,) = run["asks"]
    assert ask == asks(RUNS[0])[0]
    assert (ask["arm"], ask["read"], ask["arm_held"]) == ("B", True, True)
    assert run["gate"] == {**{key: key not in ("launch", "asks") for key in GATE}, "passed": False}
    assert (run["launch"]["status"], "runner_exit" in run["launch"]) == ("running", False)
    assert run["notes"] == [
        "samples: no stop line",
        "run: 1 hybrid._vector_search started and never ended",
        "run: 1 hybrid.get_relevant_documents_with_path started and never ended",
    ]
    assert (run["label"], run["dir"], run["llama_pids_seen"]) == (
        RUNS[0],
        runs[RUNS[0]]["dir"],
        2,
    )
    meta = run["samples"]
    lines = (RECORDS / "s1-baba.samples.jsonl").read_bytes().splitlines(keepends=True)
    prefix = tmp_path / "s1-baba.samples.jsonl"
    prefix.write_bytes(b"".join(lines[: meta["samples"] + 1]))
    notes: list[str] = []
    again, rows = reader.read_samples(prefix, notes)
    assert {**again, "loud_notes": reader.loud_notes(rows)} == meta
    assert notes == ["samples: no stop line"]
    assert (meta["samples"], meta["stop_reason"]) == (119, None)
    assert meta["first_utc"] == runs[RUNS[0]]["samples"]["first_utc"]


def test_the_samples_read_are_the_committed_files() -> None:
    for label in RUNS:
        notes: list[str] = []
        meta, rows = reader.read_samples(RECORDS / f"{label}.samples.jsonl", notes)
        assert ({**meta, "loud_notes": reader.loud_notes(rows)}, notes) == (
            runs[label]["samples"],
            [],
        )
        assert (meta["sha256"], meta["stop_reason"], meta["every_sec"]) == (
            FILES[f"{label}.samples.jsonl"],
            "stop file",
            5.0,
        )
        assert list(meta["sample_notes"]) == [ALLOWED_NOTE]


def test_every_window_and_state_attaches_again_from_the_samples() -> None:
    for label in RUNS:
        samples = SAMPLES[label]
        assert (samples.ordered, samples.page_size) == (True, 4096)
        for ask in asks(label):
            for name in ("retrieval", "vector", "rerank"):
                window = ask["windows"][name]
                assert samples.window(window["from"], window["to"]) == window, (label, name)
            assert samples.state(ask["windows"]["rerank"]["from"]) == ask["at_rerank_start"]


def test_no_sample_lies_within_a_hundredth_of_a_second_of_an_edge() -> None:
    """The record keeps each window's edges to the millisecond, and an answer call's span is
    summed from rounded seconds: no sample sits close enough to an edge to move across it."""
    for label in RUNS:
        times = SAMPLES[label].times
        for ask in asks(label):
            edges = [*call_span(ask)]
            for name in ("retrieval", "vector", "rerank"):
                edges += [ask["windows"][name]["from"], ask["windows"][name]["to"]]
            for edge in edges:
                k = bisect.bisect_left(times, edge)
                gap = min(abs(times[j] - edge) for j in (k - 1, k) if 0 <= j < len(times))
                assert gap > 0.01, (label, ask["index"], edge)


def test_both_runs_pass_their_gates_on_all_seven_points() -> None:
    for label in RUNS:
        run = runs[label]
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
            reader.ARMS[label],
            list(reader.CASES),
        )
        assert run["settings"] == reader.SETTINGS
        assert "".join(ask["arm"] for ask in asks(label)) == reader.ARMS[label]
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
            # the whole is the arm's action plus the question's total
            assert ask["whole_sec"] == reader.rounded(ask["total_sec"] + ask["arm_action"]["sec"])


def test_each_arm_acted_as_registered() -> None:
    model = [reader.MODEL]
    for label in RUNS:
        for ask in asks(label):
            action = ask["arm_action"]
            assert (action["arm"], action["error"]) == (ask["arm"], None)
            got = (action["ps_before"], action["ps_after"], action["polls"])
            if ask["arm"] == "A":
                # the preload sent again: the model resident before and after, no poll
                assert (*got, action["llama_servers"]) == (model, model, 0, None)
            else:
                # unloaded, then polled until neither Ollama nor ps listed it
                assert (*got, action["llama_servers"]) == (model, [], 1, 0)


def test_each_b_answer_loads_a_new_llama_server_and_each_a_ask_runs_beside_the_last() -> None:
    for label in RUNS:
        born: dict[int, float] = {}
        for row in SAMPLES[label].rows:
            for pid in reader.pids_of(row):
                born.setdefault(pid, row["monotonic"])
        # the supervisor's preload, the one llama-server before the run's first question
        (last,) = [pid for pid, at in born.items() if at < started(asks(label)[0])]
        for ask in asks(label):
            if ask["arm"] == "B":
                assert ask["windows"]["retrieval"]["with_llama"] == 0
                assert ask["windows"]["rerank"]["llama_pids"] == []
                start, end = call_span(ask)
                (last,) = [pid for pid, at in born.items() if start <= at <= end]
            else:
                windows = ask["windows"]
                for got in (windows["retrieval"], windows["rerank"], ask["at_rerank_start"]):
                    assert got["llama_pids"] == [last], (label, ask["index"])
        assert len(born) == runs[label]["llama_pids_seen"] == 3


def test_each_pair_shares_its_position_and_its_candidates() -> None:
    for position, case in enumerate(reader.CASES, 1):
        pair = pairs[case]
        a, b = ask_of(pair["a"]), ask_of(pair["b"])
        assert {pair["a"]["run"], pair["b"]["run"]} == set(RUNS)
        assert (a["case_id"], b["case_id"], a["index"], b["index"]) == (
            case,
            case,
            position,
            position,
        )
        assert (a["arm"], b["arm"], pair["readable"], pair["why"]) == ("A", "B", True, [])
        assert a["pool"] == b["pool"]


def test_the_stand_is_v4s() -> None:
    assert record["corpus"] == {"dir": CORPUS, "sha256": v4["source_sha256"]}
    for label in RUNS:
        run, launch = runs[label], runs[label]["launch"]
        assert run["dir"] == f"{v4['code']['workspace']}/step1/runs/{label}"
        assert launch["chroma_dir"] == run["dir"] + ".chroma"
        assert (launch["workspace"], [launch["code_sha"]]) == (
            v4["code"]["workspace"],
            v4["code_sha"],
        )
        assert ([launch["model"]], [launch["model_digest"]]) == (v4["model"], v4["model_digest"])
        assert (launch["cases_file"], launch["overrides"]) == (v4["cases_file"], v4["overrides"])
        assert (launch["tenant"], launch["client_cap_sec"]) == ("aircargo", "1965/1320")
        assert (launch["ollama_models_before"], launch["ollama_models_after"]) == ([], v4["model"])
        assert launch["unloaded_models"] == v4["model"]
        assert run["settings"] == {key: v4["settings"][key] for key in reader.SETTINGS}


def test_the_environment_brackets_both_runs_on_v4s_server() -> None:
    stage = _lines(V4 / "v4-environment.jsonl")[-1]
    before, after = _lines(RECORDS / "environment.jsonl")
    for line in (before, after):
        assert line["ollama"] == stage["ollama"]
        assert line["ollama"]["server_version"] == "0.33.2"
        assert len(line["ollama"]["servers"]) == 1
        assert line["distributions"] == stage["distributions"]
        assert (line["python"], line["python_version"]) == (
            stage["python"],
            stage["python_version"],
        )
    one, two = (runs[label]["samples"] for label in RUNS)
    assert when(before["taken"]) < when(one["first_utc"])
    assert when(one["last_utc"]) < when(two["first_utc"])
    assert when(two["last_utc"]) < when(after["taken"])


HEX = re.compile(r"[0-9a-f]{7,64}")
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)")
VERSION = re.compile(r"\d+(?:\.\d+)*")
PATH = re.compile(
    r"/Users/julia/(?:RAG_new_chat_4f48fed(?:/[\w.-]+)*|RAG_Support_Assistant/\.venv/bin/python"
    r"|gr2_bench/ollama_serve\.log|RAG_new_external_s1/aircargo"
    r"|RAG_new_tools_ollama_v0\.33\.2/ollama)"
)
WORDS = {
    # the record's enums, schemas and the specs' paths
    *("stage4-step1/v1", "stage4-step0-samples/v1"),
    *("docs/specs/stage4-step1-rerank-memory.md", "docs/specs/stage4-step0-diagnostics.md"),
    *("start", "sample", "stop", "stop file", "llama-server", ALLOWED_NOTE),
    *("yes", "faster", "NOT_EVIDENCE", "complete", "running", "prod", "aircargo", "1965/1320"),
    *("A", "B", "BABA", "ABAB", "auto", "cpu", "hybrid", "ok"),
    *("qwen3:4b-instruct-2507-q4_K_M", "huggingface-hub"),
    # the first question's read, taken while run 1 went on, and the pairs of a run read alone
    "samples: no stop line",
    "run: 1 hybrid._vector_search started and never ended",
    "run: 1 hybrid.get_relevant_documents_with_path started and never ended",
    "0 asks in A and 1 in B, not one each",
    "1 asks in A and 0 in B, not one each",
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
    ids = set(RUNS) | set(reader.CASES) | set(FILES)
    for name in FILES:
        text = (RECORDS / name).read_text(encoding="utf-8")
        assert not re.search("[\u0400-\u04ff]", text), name
        parsed = _lines(RECORDS / name) if name.endswith(".jsonl") else _json(RECORDS / name)
        for value, key in strings(parsed):
            if key:
                assert len(value) <= 40, (name, value)
                continue
            shapes = (HEX, TIME, VERSION, PATH)
            known = value in WORDS or value in ids or any(s.fullmatch(value) for s in shapes)
            assert known, (name, value)
    # a sample names a process by its executable, never its arguments or environment
    for label in RUNS:
        for row in _lines(RECORDS / f"{label}.samples.jsonl"):
            for proc in row.get("procs") or []:
                assert set(proc) <= {"pid", "rss_mib", "mem_mib", "cmprs_mib"}, proc


def test_the_readings_against_the_forecast() -> None:
    contention, net = record["readings"]["contention"], record["readings"]["net"]
    # contention yes, below the forecast's ratio of 0.3-0.45
    assert (contention["answer"], contention["readable_pairs"]) == ("yes", 4)
    assert contention["median_rerank_ratio"] == 0.2594
    assert contention["median_rerank_ratio"] < 0.3
    # net faster, within the spec's 90 s of zero: by its sign alone
    assert (net["answer"], net["readable_pairs"]) == ("faster", 4)
    assert net["median_whole_diff_sec"] == -47.009
    assert abs(net["median_whole_diff_sec"]) < 90
    # a run read alone pairs nothing, nor does the first question's read
    for read in (*own.values(), q1):
        got = read["readings"]
        assert got["contention"]["answer"] == got["net"]["answer"] == reader.NOT_EVIDENCE


def test_one_pair_left_out() -> None:
    """Each leaves three readable pairs, the rules' minimum: contention stays yes; net turns to
    not faster without either faster pair."""
    assert len(reader.CASES) - 1 == reader.MIN_PAIRS
    got = [
        (left, reader.rounded(ratio, 4), reader.rounded(whole, 3))
        for left, ratio, whole in leave_one_out()
    ]
    assert got == [
        ("aircargo-dismissal-order", 0.2151, -141.81),
        ("aircargo-leave-sources", 0.2151, -141.81),
        ("aircargo-leave-compensation", 0.3037, 47.792),
        ("aircargo-leave-risk", 0.3037, 47.792),
    ]


def test_run_ones_load_spike_falls_after_its_fourth_asks_rerank_and_cannot_turn_net() -> None:
    label, index = SPIKE
    samples = SAMPLES[label]
    ask = asks(label)[index - 1]
    assert (ask["arm"], ask["case_id"], index) == ("A", "aircargo-leave-risk", len(asks(label)))
    window = ask["windows"]["rerank"]
    start, end = call_span(ask)
    # the run's highest 1-minute load: inside the answer call, after the rerank
    peak = max(samples.rows, key=lambda row: row["loadavg"][0])
    assert (peak["loadavg"][0], peak["utc"]) == (30.5, "2026-10-28T19:58:29.846Z")
    assert window["to"] < start <= peak["monotonic"] <= end
    rerank = loads(label, window["from"], window["to"])
    assert (len(rerank), mid(rerank), max(rerank)) == (76, 2.425, 4.37)
    following = samples.rows[bisect.bisect_right(samples.times, window["to"])]
    assert start <= following["monotonic"] <= end
    assert following["loadavg"][0] > max(rerank)
    # the swap grew inside the call and shrank after the run's last ask
    rows = samples.rows
    moved = [
        k
        for k in range(1, len(rows))
        if rows[k]["swap_mib"]["total"] != rows[k - 1]["swap_mib"]["total"]
    ]
    grew, shrank = (rows[k] for k in moved)
    assert start <= grew["monotonic"] <= end
    assert started(ask) + ask["total_sec"] < shrank["monotonic"]
    # how far net stands from this pair: it turns at the median of the other three, and the
    # pair's difference with all of A's ask from its answer call's start taken off stays below
    exact = {p["case_id"]: p["exact"] for p in reader.pair_up(record["runs"]) if p["readable"]}
    rest = [exact[case]["whole_diff_sec"] for case in reader.CASES if case != ask["case_id"]]
    tail = ask["total_sec"] - ask["answer_call"]["offset_sec"]
    assert statistics.median([*rest, -statistics.median(rest)]) == 0
    assert exact[ask["case_id"]]["whole_diff_sec"] + tail < -statistics.median(rest)
    assert statistics.median([*rest, exact[ask["case_id"]]["whole_diff_sec"] + tail]) < 0


def test_the_capsule_tables_are_the_records() -> None:
    lines = CAPSULE.read_text(encoding="utf-8").splitlines()
    tables = {
        readings_rows: 2,
        ask_rows: 8,
        pair_rows: 5,
        loo_rows: 4,
        time_rows: 4,
        memory_rows: 4,
        median_rows: 12,
        load_rows: 8,
        pace_rows: 4,
        forecast_rows: 8,
        file_rows: 7,
    }
    for build, count in tables.items():
        rows = build()
        assert len(rows) == count, build.__name__
        for row in rows:
            assert row in lines, row


# the capsule's own words for its limits and its reading; each sits on one line of it
PHRASES = (
    "The record holds no question, answer, prompt, source name, log line, command line or environment.",
    "both runs' gates passed on all seven points",
    "in `44fd650` before the first request",
    "No lever is adopted on four pairs",
    "The reading holds at A's young footprint, not for V4's long series",
    "The mechanism stays open",
    "Within 90 s of zero the spec reads its sign alone.",
    "Run 1's load spike falls after its fourth ask's rerank, not inside it.",
    "No share of the spike inside A's answer can turn the reading.",
    "The record keeps llama-server's footprint (top's MEM), not its RSS",
)


def test_the_capsule_states_its_limits_and_the_records_numbers_each_on_one_line() -> None:
    text = CAPSULE.read_text(encoding="utf-8")
    assert not re.search("[\u0400-\u04ff]", text)
    lines = text.splitlines()
    built = spike_phrases() + computed_phrases() + stand_phrases() + prose_phrases()
    assert len(built) == 25
    for phrase in (*PHRASES, *built):
        assert any(phrase in line for line in lines), phrase


def test_the_index_row_names_this_capsule_its_record_its_test_and_its_spec() -> None:
    (row,) = [
        line
        for line in INDEX.read_text(encoding="utf-8").splitlines()
        if "reports/stage4-step1/4f48fed" in line
    ]
    for link in (
        "[Capsule](docs/evidence/stage4-step1-record.md)",
        "[record](reports/stage4-step1/4f48fed/step1.json)",
        "[read-again and provenance test](tests/test_stage4_step1_artifact.py)",
        "([spec](docs/specs/stage4-step1-rerank-memory.md))",
    ):
        assert link in row, link
    assert set(re.findall(r"reports/[\w./-]+", row)) == {"reports/stage4-step1/4f48fed/step1.json"}
    got = record["readings"]
    assert "| measured |" in row
    assert f"a median {got['contention']['median_rerank_ratio']} of A's" in row
    assert f"a median {signed(got['net']['median_whole_diff_sec'], 3)} s" in row


def test_the_spec_names_this_record() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    assert "registered before the first request" in spec
    assert "[the record](../evidence/stage4-step1-record.md)" in spec
