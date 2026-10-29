"""Stage 4's step 2: the records read again with the committed reader; their gates, their stand,
their questions, their environment and their privacy
(docs/specs/stage4-step2-self-eval-continuation.md, «Records»). Every table row of
docs/evidence/stage4-step2-record.md is built from the records, and so is every number of its
prose that a test below pins."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import statistics
import sys
from collections.abc import Iterator, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "stage4-step2" / "tools"
RECORDS = ROOT / "reports" / "stage4-step2" / "57420db"
SPEC = ROOT / "docs" / "specs" / "stage4-step2-self-eval-continuation.md"
CAPSULE = ROOT / "docs" / "evidence" / "stage4-step2-record.md"
CASES_FILE = ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
V4 = ROOT / "reports" / "answer-prompt-v4" / "4f48fed"
# the drivers each run ran, two levels above it, as committed
DRIVERS = {
    "live_api.py": ROOT / "reports" / "stage2" / "tools" / "live_api.py",
    "live_runner.py": ROOT / "reports" / "stage4-step1" / "tools" / "live_runner.py",
    "live_supervisor.py": TOOLS / "live_supervisor.py",
}
CODE_SHA = "57420db746e0510465bb5a08b7610e092b32e650"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
# the stand and the corpus on the Mac, as the spec names them
STAND = "/Users/julia/RAG_new_chat_57420db"
CORPUS = "/Users/julia/RAG_new_external_s1/aircargo"
# the files as copied from the Mac, by their SHA-256, which the Mac's copies matched
FILES = {
    "step2.json": "e28b0fcbf032f2e745593d07baa01db9536a29f5ed52d961534779e78919e15f",
    "s2-both.q1.step2.json": "78ab61762b164f0c05bc87b5497e987ef03937b06596bb0b23b8c74dae59dbbb",
    "step2.s2-both-r2.json": "2cc0d1dd284d4790bb92122a8c42eec59db108a0a4fadc40abaae6e03b5fa65c",
    "s2-both-r2.q1.step2.json": "a792cdcdb47dbe3f154a8f5d5bef49f37910f718160aab7df509a17560494968",
    "environment.jsonl": "a6033ffe6af8d8033e640210a44b0edcd86cbf1a0890bef7353ed423f1a429b4",
}
# each run's record; the rerun's is the one the readings are taken from
RUNS = {"s2-both": "step2.json", "s2-both-r2": "step2.s2-both-r2.json"}
GATE = ("launch", "settings", "drivers", "asks")
# the reader's reasons for s2-both's thirteenth ask, stopped at its cap
UNREAD = [
    "no delivered answer",
    "no continuation self-evaluation with a score and seconds",
    "no classic self-evaluation with a score and seconds",
]


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("step2_reader_record", TOOLS / "step2_reader.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["step2_reader_record"] = module
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


reads = {label: _json(RECORDS / name) for label, name in RUNS.items()}
q1 = {label: _json(RECORDS / f"{label}.q1.step2.json") for label in RUNS}
first, record = reads["s2-both"], reads["s2-both-r2"]
pairs = record["pairs"]
environment = _lines(RECORDS / "environment.jsonl")
v4 = _json(V4 / "v4-aircargo.json")["provenance"]


def fmt(value: float) -> str:
    return f"{value:.3f}"


def mid(values: list[float]) -> float:
    return round(statistics.median(values), 3)


def thousands(value: int) -> str:
    return f"{value:,}"


def span(values: Sequence[float], show: Any = fmt) -> str:
    return f"{show(min(values))}–{show(max(values))}"


def read_asks(label: str) -> list[dict[str, Any]]:
    return [ask for ask in reads[label]["run"]["asks"] if ask["read"]]


def side(ask: dict[str, Any], name: str, key: str) -> Any:
    return ask["self_eval"][name][key]


def the_wall(label: str) -> tuple[float, float]:
    """A run's minutes: its asks' totals summed, and from its launch to the environment line
    after it."""
    run = reads[label]["run"]
    started = when(run["launch"]["started"])
    after = min(when(line["taken"]) for line in environment if when(line["taken"]) > started)
    return sum(ask["total_sec"] for ask in run["asks"]) / 60, (after - started).total_seconds() / 60


def test_the_files_are_the_bytes_copied_from_the_mac() -> None:
    assert sorted(path.name for path in RECORDS.iterdir()) == sorted(FILES)
    for name, digest in FILES.items():
        data = (RECORDS / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), b"\r" in data) == (digest, False), name


def test_the_records_were_read_by_the_readers_and_the_drivers_the_spec_lists() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    listed = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    assert len(listed) == 6
    for path, digest in listed.items():
        assert sha(ROOT / path) == digest, path
    assert (reader.SCHEMA, reader.CODE_SHA, reader.SPEC) == (
        "stage4-step2/v1",
        CODE_SHA,
        SPEC.relative_to(ROOT).as_posix(),
    )
    # s2-both was read by the reader as registered, the rerun by Amendment 1's, the committed one
    registered = re.search(r"registered as `([0-9a-f]{64})`, which read `s2-both`", spec)
    assert registered
    amended = listed["reports/stage4-step2/tools/step2_reader.py"]
    for label, digest in (("s2-both", registered[1]), ("s2-both-r2", amended)):
        for read in (reads[label], q1[label]):
            assert (read["schema"], read["spec"], read["tools_sha256"]) == (
                reader.SCHEMA,
                reader.SPEC,
                {"step2_reader.py": digest},
            ), label
    drivers = {name: listed[path.relative_to(ROOT).as_posix()] for name, path in DRIVERS.items()}
    assert drivers == reader.DRIVERS_SHA256
    # V4's own live_api.py
    assert drivers["live_api.py"] == v4["tools_sha256"]["live_api.py"]
    for read in (*reads.values(), *q1.values()):
        assert read["run"]["drivers_sha256"] == drivers


def test_the_pairs_the_readings_and_the_first_asks_are_read_again_from_the_asks() -> None:
    for read in (*reads.values(), *q1.values()):
        run = read["run"]
        again = [reader.pair_of(ask, run["gate"]["passed"]) for ask in run["asks"]]
        assert again == read["pairs"]
        assert reader.readings(again) == read["readings"]
        assert reader.first_ask(run["asks"]) == read["first_ask"]


def test_the_rerun_passed_its_gate_on_all_four_points_and_every_ask_was_read() -> None:
    run = record["run"]
    assert run["gate"] == {**dict.fromkeys(GATE, True), "passed": True}
    assert run["notes"] == []
    assert [(ask["index"], ask["case_id"]) for ask in run["asks"]] == list(
        enumerate(reader.CASES, start=1)
    )
    for ask in run["asks"]:
        case = ask["case_id"]
        assert (ask["read"], ask["unread"], ask["continuation_held"]) == (True, [], True), case
        assert (ask["http_status"], ask["answered"], ask["answer_source"]) == (200, True, "stream")
        assert ask["spans"] == {reader.STREAM: 1, reader.GENERATE: 2}, case
        score = side(ask, "continuation", "score")
        assert (ask["quality_score"], ask["quality_source"]) == (score, "llm"), case
        assert ask["route"] == reader.route_of(score), case
        # the classic's call, then one the reader names "other", its span with no output limit
        assert [(call["call"], call["max_tokens"]) for call in ask["after_answer"]] == [
            ("classic", 128),
            ("other", None),
        ], case
        assert ask["suggested"] == 3, case
        # the classic's entry is its score and seconds alone, its counters none
        assert {key: side(ask, "classic", key) for key in reader.COUNTERS} == dict.fromkeys(
            reader.COUNTERS
        )
    for pair in pairs:
        assert (pair["readable"], pair["held"], pair["compared"]) == (True, True, True)


def test_s2_both_stopped_at_its_thirteenth_question_and_failed_its_launch_point_alone() -> None:
    run = first["run"]
    assert run["gate"] == {**dict.fromkeys(GATE, True), "launch": False, "passed": False}
    assert run["notes"] == []
    launch = run["launch"]
    assert (launch["status"], launch["runner_exit"], "arm" in launch) == ("failed", 5, False)
    *twelve, last = run["asks"]
    assert [ask["read"] for ask in twelve] == [True] * 12
    assert all(ask["continuation_held"] for ask in twelve)
    assert (last["case_id"], last["read"], last["answered"]) == (reader.CASES[-1], False, False)
    assert last["unread"] == UNREAD
    # past its cap, 1,365 s, its first token at 1,281 s
    cap = int(launch["client_cap_sec"].split("/")[1])
    assert last["total_sec"] > cap and round(last["first_token_sec"]) == 1281
    for pair in first["pairs"]:
        assert pair["unreadable"][0] == "the run's gate did not pass"
    for key, value in first["readings"].items():
        if key != "printed_deciding_nothing":
            assert value["answer"] == reader.NOT_EVIDENCE, key


def test_the_first_questions_reads_were_taken_while_each_run_went_on() -> None:
    for label, read in q1.items():
        run, full = read["run"], reads[label]["run"]
        (ask,) = run["asks"]
        assert ask == full["asks"][0]
        assert run["gate"] == {
            **dict.fromkeys(GATE, False),
            "settings": True,
            "drivers": True,
            "passed": False,
        }
        assert run["notes"] == []
        assert read["first_ask"] == reads[label]["first_ask"]
        assert read["first_ask"]["stop"] is False
        assert read["first_ask"]["ratio"] < reader.FIRST_RATIO
        # the launch file as the supervisor kept it while the run went on
        moved = {key for key in full["launch"] if run["launch"].get(key) != full["launch"][key]}
        assert moved == {"status", "runner_exit", "ollama_models_after", "unloaded_models"}
        assert run["launch"]["status"] == "running"
        assert run["sha256"]["effective_settings.json"] == full["sha256"]["effective_settings.json"]


def test_the_stand_the_settings_the_corpus_and_the_questions_are_the_specs() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    for label, read in reads.items():
        run, launch = read["run"], read["run"]["launch"]
        assert (run["label"], launch["label"], launch["code_sha"]) == (label, label, CODE_SHA)
        assert (launch["mode"], launch["tenant"], launch["client_cap_sec"]) == (
            "prod",
            "aircargo",
            "2010/1365",
        )
        assert [launch["model"]] == v4["model"] == [MODEL]
        assert [launch["model_digest"]] == v4["model_digest"]
        assert f"(`{launch['model_digest'][:12]}…`)" in spec
        assert launch["cases"] == list(reader.CASES)
        # V4's overrides and the mode
        assert launch["overrides"] == {**v4["overrides"], "STREAMING_SELF_EVAL_MODE": "both"}
        assert launch.get("arm") == (reader.RERUN_ARM if label == "s2-both-r2" else None)
        assert (launch["ollama_models_before"], launch["ollama_models_after"]) == ([], [MODEL])
        assert launch["unloaded_models"] == [MODEL]
        assert (launch["workspace"], run["dir"], launch["chroma_dir"]) == (
            STAND,
            f"{STAND}/step2/runs/{label}",
            f"{STAND}/step2/runs/{label}.chroma",
        )
        assert launch["cases_file"] == f"{STAND}/evaluation/curated_cases_aircargo.jsonl"
        # V4's settings that the reader keeps, the mode and the stand's code
        assert run["settings"] == {
            **{key: v4["settings"][key] for key in reader.SETTINGS},
            "streaming_self_eval_mode": "both",
            "code_sha": CODE_SHA,
        }
        assert run["settings_printed"] == {
            key: v4["settings"][key] for key in reader.CONTEXT_SETTINGS
        }
        # V4's corpus, by its three files
        assert read["corpus"] == {
            "dir": f"{v4['data_root']}/aircargo",
            "sha256": v4["source_sha256"],
        }
        assert read["corpus"]["dir"] == CORPUS
    starts = [when(read["run"]["launch"]["started"]) for read in reads.values()]
    assert starts == sorted(starts)
    # the questions: the committed file's first thirteen, V4's file
    cases = [json.loads(line)["case_id"] for line in CASES_FILE.read_text("utf-8").splitlines()]
    assert cases[: len(reader.CASES)] == list(reader.CASES)
    assert sha(CASES_FILE) == v4["cases_file_sha256"]


def test_the_environment_brackets_each_run_on_v4s_server() -> None:
    stage = _lines(V4 / "v4-environment.jsonl")[-1]
    assert len(environment) == 4
    for line in environment:
        assert line["ollama"] == stage["ollama"]
        assert line["ollama"]["server_version"] == "0.33.2"
        assert len(line["ollama"]["servers"]) == 1
        assert line["distributions"] == stage["distributions"]
        assert (line["python"], line["python_version"]) == (
            stage["python"],
            stage["python_version"],
        )
    taken = [when(line["taken"]) for line in environment]
    one, two = (when(read["run"]["launch"]["started"]) for read in reads.values())
    assert taken[0] < one < taken[1] < taken[2] < two < taken[3]


HEX = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00")
VERSION = re.compile(r"\d+(?:\.\d+)+")
PATH = re.compile(
    r"/Users/julia/(?:RAG_new_chat_57420db(?:/evaluation/curated_cases_aircargo\.jsonl"
    r"|/step2/runs/s2-both(?:-r2)?(?:\.chroma)?)?|RAG_Support_Assistant/\.venv/bin/python"
    r"|RAG_new_external_s1/aircargo|RAG_new_tools_ollama_v0\.33\.2/ollama)"
)
WORDS = {
    # the record's schema and the spec's path, its enums and values
    *("stage4-step2/v1", "docs/specs/stage4-step2-self-eval-continuation.md", "NOT_EVIDENCE"),
    *("faster", "useful", "agree", "held", "continuation", "classic", "auto", "human", "llm"),
    *("prod", "aircargo", "complete", "failed", "running", "cpu", "both", "stream", "other"),
    *("2010/1365", "3600", reader.RERUN_ARM, MODEL, "huggingface-hub"),
    # the reader's fixed reasons
    *UNREAD,
    *("its ask is not read", "the run's gate did not pass", "no continuation score of 1-100"),
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


def test_the_records_hold_numbers_ids_enums_paths_and_hashes_only() -> None:
    ids = set(reader.LABELS) | set(reader.CASES)
    for name in FILES:
        text = (RECORDS / name).read_text(encoding="utf-8")
        assert not re.search("[\u0400-\u04ff]", text), name
        parsed = _lines(RECORDS / name) if name.endswith(".jsonl") else [_json(RECORDS / name)]
        for value, key in strings(parsed):
            if key:
                assert len(value) <= 40, (name, value)
                continue
            shapes = (HEX, TIME, VERSION, PATH)
            known = value in WORDS or value in ids or any(s.fullmatch(value) for s in shapes)
            assert known, (name, value)


def test_the_readings_against_the_forecast() -> None:
    got = record["readings"]
    speed = got["speed"]
    assert (speed["answer"], speed["readable_pairs"], speed["ties"]) == ("faster", 13, 0)
    assert (speed["continuation_faster"], speed["continuation_slower"]) == (13, 0)
    assert (speed["sign_p"], speed["median_ratio"]) == (0.000244, 0.1408)
    assert got["useful"] == {
        "answer": "useful",
        "median_saving_sec": 54.009,
        "least_median_saving_sec": 30.0,
    }
    assert got["routes"] == {
        "answer": "agree",
        "compared_pairs": 13,
        "differ": 1,
        "differing": ["aircargo-probation-extend"],
    }
    assert got["scores"] == {"answer": "held", "readable_pairs": 13, "missed": 0, "misses": []}
    assert got["candidate"] == {"answer": "continuation"}
    # the sign test decides at 11 of 13, the spec's p = 0.0225; 10 of 13 gives 0.092
    assert round(reader.sign_p(11, 2), 4) == 0.0225 and round(reader.sign_p(10, 3), 3) == 0.092
    # the forecast: faster on 13 of 13, useful, held, agreeing; the continuation's prompt read
    # faster than its 10-15 s, the classic faster than step 0's 65-105 s
    prompt = [pair["printed"]["counters"]["continuation"]["prompt_sec"] for pair in pairs]
    classic = [pair["sec"]["classic"] for pair in pairs]
    assert statistics.median(prompt) < 10 and min(classic) < 65
    # the first run's reads pair nothing, nor do the first questions' reads
    for read in (first, *q1.values()):
        assert read["readings"]["candidate"]["answer"] == reader.NOT_EVIDENCE


def readings_rows() -> list[str]:
    got = record["readings"]
    speed, routes = got["speed"], got["routes"]
    savings = [pair["saving_sec"] for pair in pairs]
    return [
        "| Speed: the continuation's cost below the classic's seconds on more questions, the exact"
        f" two-sided sign test's p below 0.05 | **{speed['answer']}** | below on"
        f" {speed['continuation_faster']} of {speed['readable_pairs']} readable questions, above"
        f" on {speed['continuation_slower']}; p {speed['sign_p']:.6f} | faster, on 13 of 13 |",
        "| Use: the median saving, the classic's seconds less the continuation's cost, at least"
        f" 30 s | **{got['useful']['answer']}** | {fmt(got['useful']['median_saving_sec'])} s,"
        f" {span(savings)} s by question; the median ratio {speed['median_ratio']:.4f} | useful |",
        "| Routes: at most one compared question routed otherwise"
        f" | **{routes['answer']}** | {routes['differ']} of {routes['compared_pairs']}:"
        f" `{routes['differing'][0]}` | agree, with the least confidence |",
        "| Scores: the continuation scored 1–100 on all but at most one readable question"
        f" | **{got['scores']['answer']}** | missed on {got['scores']['missed']} of"
        f" {got['scores']['readable_pairs']} | held |",
        "| The candidate: the continuation when faster, useful, agreeing and held"
        f" | **{got['candidate']['answer']}** | all four | the continuation |",
    ]


def pair_rows() -> list[str]:
    out = []
    for pair in pairs:
        counters = pair["printed"]["counters"]["continuation"]
        score, routes = pair["score"], pair["routes"]
        out.append(
            f"| {pair['index']} | `{pair['case_id']}` | {fmt(pair['sec']['classic'])}"
            f" | {fmt(pair['sec']['continuation'])} | {fmt(pair['saving_sec'])}"
            f" | {pair['ratio']:.4f} | {score['classic']} / {score['continuation']}"
            f" | {routes['classic']} / {routes['continuation']}"
            f" | {counters['prompt_tokens']:,} / {fmt(counters['prompt_sec'])} |"
        )
    return out


def run_rows() -> list[str]:
    out = []
    for label, read in reads.items():
        launch, asks = read["run"]["launch"], read_asks(label)
        memories = [ask["memory"] for ask in asks]
        swap = max(value for memory in memories for value in memory["swap_used_mib"])
        rss = max(memory["llama_rss_mib_max"] for memory in memories)
        arm = "`B` before each question" if launch.get("arm") else "none"
        out.append(
            f"| `{label}` | {when(launch['started']):%H:%M:%S} | {arm}"
            f" | {launch['status']}, {launch['runner_exit']}"
            f" | {len(asks)} of {len(read['run']['asks'])} | {fmt(launch['ollama_load_sec'])}"
            f" | {fmt(mid([ask['first_token_sec'] for ask in asks]))}"
            f" | {fmt(mid([ask['total_sec'] for ask in asks]))} | {swap:,.2f} | {rss:,.1f} |"
        )
    return out


def printed_rows() -> list[str]:
    got = record["readings"]["printed_deciding_nothing"]
    counters = got["median_counters"]["continuation"]
    higher = got["continuation_scored"]
    memory = got["memory"]

    def routes(side: str) -> str:
        return ", ".join(f"{route} {n}" for route, n in got[f"{side}_routes"].items())

    return [
        f"| The saving, summed, s | {fmt(got['total_saving_sec'])} |",
        f"| The saving, the least, s | {fmt(got['worst_saving_sec'])} |",
        f"| The continuation's cost, a median, s | {fmt(got['median_cost_sec'])} |",
        f"| The classic's seconds, a median | {fmt(got['median_classic_sec'])} |",
        f"| The classic's call in its span, a median, s | {fmt(got['median_classic_call_wall_sec'])} |",
        "| The continuation's counters, medians: prompt tokens, prompt s, generated tokens,"
        f" generated s | {counters['prompt_tokens']:,}, {fmt(counters['prompt_sec'])},"
        f" {counters['eval_tokens']}, {fmt(counters['eval_sec'])} |",
        "| The scores, a median, the classic / the continuation"
        f" | {got['median_score']['classic']} / {got['median_score']['continuation']} |",
        "| The continuation scored higher / the same / lower"
        f" | {higher['higher']} / {higher['same']} / {higher['lower']} |",
        f"| The classic's routes | {routes('classic')} |",
        f"| The continuation's routes | {routes('continuation')} |",
        f"| The answer's call, a median, s | {fmt(got['median_answer_wall_sec'])} |",
        f"| The first token, a median, s | {fmt(got['median_first_token_sec'])} |",
        f"| The total, a median, s | {fmt(got['median_total_sec'])} |",
        f"| The swap used, at most, MiB | {memory['swap_used_mib_max']:,.2f} |",
        f"| llama-server's resident memory, at most, MiB | {memory['llama_rss_mib_max']:,.1f} |",
        f"| The swap-outs, summed over the asks | {memory['swapouts']:,} |",
    ]


def first_run_rows() -> list[str]:
    out = []
    for ask in read_asks("s2-both"):
        out.append(
            f"| {ask['index']} | `{ask['case_id']}` | {fmt(side(ask, 'classic', 'sec'))}"
            f" | {fmt(side(ask, 'continuation', 'sec'))}"
            f" | {side(ask, 'classic', 'score')} / {side(ask, 'continuation', 'score')}"
            f" | {ask['total_sec']:,.3f} |"
        )
    return out


# the spec's forecasts, in its words
FORECAST = (
    "**faster** on 13 of 13, and **useful**: the continuation's prompt read in ≈ 10–15 s against"
    " the classic's 65–105 s",
    "**scores held**",
    "**routes agree**, with the least confidence of the four",
    "The forecast candidate: the continuation.",
    "≈ 1 h 10 min – 1 h 30 min for the thirteen on an idle Mac",
)


def forecast_rows() -> list[str]:
    got = record["readings"]
    prompt = [pair["printed"]["counters"]["continuation"]["prompt_sec"] for pair in pairs]
    classic = [pair["sec"]["classic"] for pair in pairs]
    asks, wall = the_wall("s2-both-r2")
    measured = (
        f"**{got['speed']['answer']}** on {got['speed']['continuation_faster']} of"
        f" {got['speed']['readable_pairs']}, and **{got['useful']['answer']}**: the"
        f" continuation's prompt read in {span(prompt)} s, the classic took {span(classic)} s",
        f"**{got['scores']['answer']}**: the continuation scored all"
        f" {got['scores']['readable_pairs']}",
        f"**{got['routes']['answer']}**: {got['routes']['differ']} of"
        f" {got['routes']['compared_pairs']} routed otherwise",
        f"The candidate: **{got['candidate']['answer']}**.",
        f"the thirteen asks' totals {asks:.1f} min; {wall:.1f} min from the launch to the"
        " environment line after the run",
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
        readings_rows: 5,
        pair_rows: 13,
        run_rows: 2,
        printed_rows: 16,
        first_run_rows: 12,
        forecast_rows: 5,
        file_rows: 5,
    }
    for build, count in tables.items():
        rows = build()
        assert len(rows) == count, build.__name__
        for row in rows:
            assert row in lines, row


# the capsule's own words for its limits and its reading; each sits on one line of it
PHRASES = (
    "The record holds no question, answer, prompt, source name, log line, command line or process"
    " environment.",
    "in `f532c96` before the first request;",
    "No default changes here.",
    "The default stays `classic` until step 2b reads.",
    "Nothing on the badge's quality here.",
    "(mine, no rule of the spec)",
    "The classic's counters are null in every ask:",
    "The record does not count the tokens kept from the slot.",
    "Step 2 is no slice by the acceptance rule:",
)


def computed_phrases() -> list[str]:
    got = record["readings"]
    printed = got["printed_deciding_nothing"]
    speed = got["speed"]
    counters = printed["median_counters"]["continuation"]
    starts = [when(read["run"]["launch"]["started"]) for read in reads.values()]
    (case,) = got["routes"]["differing"]
    pair = next(pair for pair in pairs if pair["case_id"] == case)
    higher = [
        pair["case_id"]
        for pair in pairs
        if pair["score"]["continuation"] > pair["score"]["classic"]
    ]
    twelve = read_asks("s2-both")
    continuation = [side(ask, "continuation", "sec") for ask in twelve]
    classic = [side(ask, "classic", "sec") for ask in twelve]
    at_least = all(
        side(ask, "continuation", "score") >= side(ask, "classic", "score") for ask in twelve
    )
    # s2-both's twelve routed otherwise on the rerun's question alone
    (moved,) = [
        ask
        for ask in twelve
        if reader.route_of(side(ask, "classic", "score"))
        != reader.route_of(side(ask, "continuation", "score"))
    ]
    assert moved["case_id"] == case
    last = first["run"]["asks"][-1]
    estimates = [
        call["prompt_est_tokens"]
        for ask in record["run"]["asks"]
        for call in ask["after_answer"]
        if call["call"] == "classic"
    ]
    swap = {
        label: max(v for ask in read_asks(label) for v in ask["memory"]["swap_used_mib"])
        for label in reads
    }
    totals = {label: mid([ask["total_sec"] for ask in read_asks(label)]) for label in reads}
    return [
        f"The runs started at {starts[0]:%H:%M} and {starts[1]:%H:%M} UTC on 2026-10-29.",
        f"below the classic on {speed['continuation_faster']} of {speed['readable_pairs']}"
        f" questions, p {speed['sign_p']:.6f}",
        f"The median saving is {fmt(got['useful']['median_saving_sec'])} s, the median ratio"
        f" {speed['median_ratio']:.4f}.",
        f"a median {fmt(printed['median_cost_sec'])} s against the classic's"
        f" {fmt(printed['median_classic_sec'])} s",
        f"a median {counters['prompt_tokens']:,} prompt tokens counted, read in"
        f" {fmt(counters['prompt_sec'])} s",
        f"`{case}`: the classic's {pair['score']['classic']} ({pair['routes']['classic']})"
        f" against the continuation's {pair['score']['continuation']}"
        f" ({pair['routes']['continuation']})",
        f"higher on {len(higher)} of {len(pairs)} questions and lower on none",
        f"{span(continuation)} s against the classic's {span(classic)} s",
        f"the same or higher on {len(twelve)} of {len(twelve)}" if at_least else "<not at least>",
        f"the classic's {side(moved, 'classic', 'score')} against the continuation's"
        f" {side(moved, 'continuation', 'score')}",
        f"its first token at {last['first_token_sec']:,.0f} s and its total at"
        f" {last['total_sec']:,.3f} s",
        f"estimated at {span(estimates, thousands)} tokens in its span",
        f"{swap['s2-both-r2']:,.2f} MiB at most against `s2-both`'s {swap['s2-both']:,.2f}",
        f"a median {fmt(totals['s2-both-r2'])} s an ask against `s2-both`'s"
        f" {fmt(totals['s2-both'])}",
        f"`s2-both`'s thirteen asks' totals summed to {the_wall('s2-both')[0]:.1f} min",
    ]


def test_the_capsule_states_its_limits_and_the_records_numbers_each_on_one_line() -> None:
    text = CAPSULE.read_text(encoding="utf-8")
    assert not re.search("[\u0400-\u04ff]", text)
    lines = text.splitlines()
    built = computed_phrases()
    assert len(built) == 15 and "<not at least>" not in built
    for phrase in (*PHRASES, *built):
        assert any(phrase in line for line in lines), phrase


def test_the_spec_names_this_record_and_its_forecasts_as_the_capsule_quotes_them() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    assert "registered before the first request" in spec
    assert "[the record](../evidence/stage4-step2-record.md)" in spec
    flat = " ".join(spec.split())
    for said in FORECAST:
        assert said in flat, said
    # step 0's classic, as the spec quotes it and the capsule after it
    capsule = " ".join(CAPSULE.read_text(encoding="utf-8").split())
    for said in ("read 2,377–2,690 prompt tokens", "spent 65.0–105.1 s reading them"):
        assert said in flat and said in capsule, said
