"""Stage 4's item 5: the record read again from its committed samples with the committed reader;
its gate, its limit, its stand, its environment and its privacy
(docs/specs/stage4-step5-cache-cap-series.md, «Records»). Every table row of
docs/evidence/stage4-step5-record.md is built from the record, and so is every number of its prose
that comes from the record or 19beeb1's."""

from __future__ import annotations

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
TOOLS = ROOT / "reports" / "stage4-step5" / "tools"
STEP0_TOOLS = ROOT / "reports" / "stage4-step0" / "tools"
RECORDS = ROOT / "reports" / "stage4-step5" / "4f48fed"
SPEC = ROOT / "docs" / "specs" / "stage4-step5-cache-cap-series.md"
STEP0_SPEC = ROOT / "docs" / "specs" / "stage4-step0-diagnostics.md"
CAPSULE = ROOT / "docs" / "evidence" / "stage4-step5-record.md"
V4 = ROOT / "reports" / "answer-prompt-v4" / "4f48fed"
CODE_SHA = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
LABEL = "s5-30"
CONFIG = "/Users/julia/.config/llama.cpp/config.ini"
FILES = ("step5.json", "s5-30.samples.jsonl", "environment.jsonl")
# what step 0's Samples.attach writes into a request's row
WINDOWS = (
    "request_window",
    "first_line_by",
    "release_after",
    "mem_after_state_mib",
    "prompt_window",
    "generation_window",
)
ALLOWED_NOTE = "ps: no process named llama-server"


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


reader = _load(TOOLS / "step5_reader.py", "step5_reader_record")
step0 = reader.load_step0(STEP0_TOOLS)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def when(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


record = _json(RECORDS / "step5.json")
part = record["part"]
questions = record["questions"]
v4 = _json(V4 / "v4-aircargo.json")["provenance"]


def samples() -> Any:
    notes: list[str] = []
    rows = step0.read_samples(RECORDS / f"{LABEL}.samples.jsonl", notes)[1]
    return step0.Samples(rows, notes)


def bounds() -> tuple[float, float]:
    """The series' window: the first question's start to the last one's end."""
    return questions[0]["start"], max(row["end"] for row in questions)


def test_the_record_was_read_by_the_committed_tools() -> None:
    pattern = r"^- `reports/stage4-step[05]/tools/(step\d_\w+\.py)` `([0-9a-f]{64})`$"
    listed = dict(re.findall(pattern, SPEC.read_text(encoding="utf-8"), re.M))
    listed |= dict(re.findall(pattern, STEP0_SPEC.read_text(encoding="utf-8"), re.M))
    committed = {
        "step5_reader.py": sha(TOOLS / "step5_reader.py"),
        **{name: sha(STEP0_TOOLS / name) for name in step0.TOOLS},
    }
    assert record["tools_sha256"] == committed == listed
    assert (record["schema"], record["spec"]) == (
        "stage4-step5/v1",
        "docs/specs/stage4-step5-cache-cap-series.md",
    )


def test_the_samples_read_are_the_committed_file() -> None:
    notes: list[str] = []
    meta, _ = step0.read_samples(RECORDS / f"{LABEL}.samples.jsonl", notes)
    assert (meta, notes) == (part["samples"], [])
    assert meta["stop_reason"] == "stop file"
    assert set(meta["sample_notes"]) <= {ALLOWED_NOTE}


def test_every_request_window_attaches_again_from_the_committed_samples() -> None:
    again = samples()
    assert (again.pid, again.page_size) == (part["pid"], part["page_size"])
    for process in part["processes"]:
        for row in process["requests"]:
            copy = {key: value for key, value in row.items() if key not in WINDOWS}
            again.attach(copy)
            assert copy == row


def test_every_question_row_is_read_again_from_the_committed_samples() -> None:
    # the API's RSS comes from the supervisor's resources.jsonl, which stays on the Mac
    low, high = bounds()
    pid, pids = reader.series_pid(samples(), low, high)
    assert (pid, pids) == (record["series_pid"], 1)
    rows = reader.question_rows(part, samples(), [], record["resources"]["api_pid"], pid)
    assert len(rows) == len(questions) == 30
    for got, row in zip(rows, questions, strict=True):
        assert got["api_rss_mib"] is None and row["api_rss_mib"] is not None
        assert {**got, "api_rss_mib": row["api_rss_mib"]} == row


def test_the_cache_the_gate_and_the_reading_follow_from_the_record() -> None:
    cap = reader.cache_states(part)
    assert cap == record["cache"]
    low, high = bounds()
    _, pids = reader.series_pid(samples(), low, high)
    api_pid = record["resources"]["api_pid"]
    assert reader.gate(part, cap, questions, api_pid, pids) == record["gate"]
    assert reader.reading(questions, record["gate"], record["disturbance"]) == record["reading"]
    assert reader.printed(questions, samples(), cap) == record["printed"]


def test_the_gate_passed_the_limit_held_and_nothing_disturbed_the_series() -> None:
    assert record["gate"] == {"passed": True, "reasons": []}
    cache = record["cache"]
    assert cache["limits_mib"] == [1024.0] and cache["in_force"] is True
    assert cache["max_mib"] <= 1024.0 and cache["reduced_to_mib"] == []
    assert cache["requests"] == cache["states"] == 89
    assert part["run"]["joined"] == {"calls": 89, "matched": 89, "requests": 89}
    assert record["config_files"] == [CONFIG]
    assert record["disturbance"] == {
        "llama_server_pids": 1,
        "foreign_python": [],
        "virtual_machines": [],
        "disturbed": False,
        "reasons": [],
    }
    assert part["notes"] == [] or all(note.startswith("resources: ") for note in part["notes"])


def test_the_stand_is_step0s() -> None:
    assert record["corpus"] == {
        "dir": "/Users/julia/RAG_new_external_s1/aircargo",
        "sha256": v4["source_sha256"],
    }
    assert record["log"] == "/Users/julia/gr2_bench/ollama_serve.log"
    run, launch = part["run"], part["run"]["launch"]
    assert run["dir"] == f"{v4['code']['workspace']}/chatlive/runs/{LABEL}"
    assert run["drivers_sha256"] == reader.DRIVERS_SHA256
    assert (launch["label"], launch["cases"], launch["mode"]) == (LABEL, list(reader.CASES), "prod")
    assert (launch["tenant"], launch["client_cap_sec"]) == ("aircargo", "1020/1200")
    assert (launch["workspace"], launch["code_sha"]) == (v4["code"]["workspace"], CODE_SHA)
    assert ([launch["model"]], [launch["model_digest"]]) == (v4["model"], v4["model_digest"])
    assert (launch["cases_file"], launch["overrides"]) == (v4["cases_file"], v4["overrides"])
    assert launch["chroma_dir"] == run["dir"] + ".chroma"
    assert (launch["ollama_models_before"], launch["ollama_models_after"]) == ([], v4["model"])
    assert [row["case_id"] for row in questions] == list(reader.CASES)
    routes = {row["case_id"]: row["route"] for row in questions}
    assert {case for case, route in routes.items() if route != "auto"} == {
        "aircargo-probation-extend"
    }


def test_the_environment_brackets_the_series_on_v4s_server() -> None:
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
    assert when(before["taken"]) < when(part["samples"]["first_utc"])
    assert when(part["samples"]["last_utc"]) < when(after["taken"])


HEX = re.compile(r"[0-9a-f]{7,64}")
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)")
VERSION = re.compile(r"\d+(?:\.\d+)*")
PATH = re.compile(
    r"/Users/julia/(?:RAG_new_chat_4f48fed(?:/[\w.-]+)*|RAG_Support_Assistant/\.venv/bin/python"
    r"|gr2_bench/ollama_serve\.log|RAG_new_external_s1/aircargo"
    r"|RAG_new_tools_ollama_v0\.33\.2/ollama|\.config/llama\.cpp/config\.ini)"
)
NOTE = re.compile(r"resources: \d+ lines unread or with a monitor error")
WORDS = {
    # the record's enums, schemas, file names and the two specs' paths
    *("stage4-step5/v1", "stage4-step0-samples/v1"),
    *("docs/specs/stage4-step5-cache-cap-series.md", "docs/specs/stage4-step0-diagnostics.md"),
    *("start", "sample", "stop", "stop file", "llama-server", ALLOWED_NOTE, "resources.jsonl"),
    *("holds", "grows", "NOT_EVIDENCE", "complete", "prod", "aircargo", "auto", "human", "cpu"),
    *("1020/1200", "yes", "no", "on"),
    *("answer", "self_eval", "suggestions", "ollama.generate_stream", "ollama.generate", "LRU"),
    *("model", "output", "KV", "compute", "CPU", "CPU_REPACK", "load_mode = none"),
    *("load_tensors", "llama_context", "llama_kv_cache", "sched_reserve"),
    *("no build line", "no system_info line", "no load_backend line"),
    *("qwen3:4b-instruct-2507-q4_K_M", "huggingface-hub"),
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
    ids = {LABEL, *reader.CASES, *FILES, *step0.CORPUS_FILES, *reader.DRIVERS_SHA256}
    ids |= {"step5_reader.py", *step0.TOOLS}
    assert sorted(path.name for path in RECORDS.iterdir()) == sorted(FILES)
    for name in FILES:
        text = (RECORDS / name).read_text(encoding="utf-8")
        assert not re.search("[\u0400-\u04ff]", text), name
        parsed = _lines(RECORDS / name) if name.endswith(".jsonl") else _json(RECORDS / name)
        for value, key in strings(parsed):
            if key:
                assert len(value) <= 40, (name, value)
                continue
            shapes = (HEX, TIME, VERSION, PATH, NOTE)
            known = value in WORDS or value in ids or any(s.fullmatch(value) for s in shapes)
            assert known, (name, value)
    # a sample names a process by its pid, never its arguments or environment
    for row in _lines(RECORDS / f"{LABEL}.samples.jsonl"):
        for proc in row.get("procs") or []:
            assert set(proc) <= {"pid", "rss_mib", "mem_mib", "cmprs_mib"}, proc


BASELINE = ROOT / "reports" / "chat-live-4b" / "19beeb1" / "runs.json"
baseline = {
    case["case"]: case
    for run in _json(BASELINE)["runs"]
    if run["label"] == "qwen3-4b-instruct-q30-r2"
    for case in run["cases"]
}


def mid(n: int) -> float:
    """19beeb1's rerun: question n's swap, the midpoint of the lowest and highest it printed."""
    low, high = baseline[questions[n - 1]["case_id"]]["memory"]["swap_used_mb"]
    return float((low + high) / 2)


def windowed(values: list[float], first: int, last: int) -> float:
    return float(statistics.median(values[first - 1 : last]))


def signed(value: float) -> str:
    return f"{value:+,}".replace("-", "−")


def test_the_reading_against_the_forecast() -> None:
    assert record["reading"] == {
        "swap": "holds",
        "why": None,
        "reference_mib": 3437.5,
        "last_mib": 3257.25,
        "growth_mib": -180.25,
    }
    removed = [row["removed_entries"] for row in questions]
    assert removed[0] == 0 and all(removed[1:]) and sum(removed) == 85
    assert max(row["swap_max_mib"] for row in questions[25:]) == 3915.75
    footprints = [row["footprint_mib"] for row in questions]
    assert (min(footprints), max(footprints)) == (3179.0, 4204.0)
    assert record["printed"]["total_sec_sum"] == 10545.79
    # 19beeb1's rerun asked the same thirty in the same order
    assert list(baseline) == [row["case_id"] for row in questions]
    # the same rule on 19beeb1's rerun, the thirty without a limit, reads it as grows
    mids = [mid(n) for n in range(1, 31)]
    assert (windowed(mids, 6, 10), windowed(mids, 26, 30)) == (5691.5, 10143.625)


def reading_rows() -> list[str]:
    got = record["reading"]
    mids = [mid(n) for n in range(1, 31)]
    then, later = windowed(mids, 6, 10), windowed(mids, 26, 30)
    return [
        f"| Questions 6–10 | {got['reference_mib']:,} | {then:,} |",
        f"| Questions 26–30 | {got['last_mib']:,} | {later:,} |",
        f"| Growth | {signed(got['growth_mib'])} | {signed(later - then)} |",
        f"| «Своп не растёт»: growth below 512 MiB | **{got['swap']}** | grows |",
    ]


def question_table() -> list[str]:
    out = []
    for row in questions:
        low, high = baseline[row["case_id"]]["memory"]["swap_used_mb"]
        out.append(
            f"| {row['n']} | `{row['case_id']}` | {row['route']} | {row['total_sec']:.0f}"
            f" | {row['swap_mib']:,.1f} | {row['swap_max_mib']:,.1f} | {low:,.1f}–{high:,.1f}"
            f" | {row['footprint_mib']:,.0f} | {row['api_rss_mib']:,.0f} | {row['load5']:.2f}"
            f" | {row['cache_mib']:,.1f} | {row['removed_entries']} |"
        )
    return out


def printed_rows() -> list[str]:
    got = record["printed"]
    return [
        f"| llama-server's footprint, 26–30 less 6–10 | {signed(got['footprint_change_mib'])} MiB |",
        f"| The API's RSS, 26–30 less 6–10 | {signed(got['api_rss_change_mib'])} MiB |",
        f"| The swap's slope from question 6 | {signed(got['swap_slope_mib_per_question'])} MiB"
        " a question |",
        f"| The swap at the first and the last sample | {got['swap_first_sample_mib']:,} and"
        f" {got['swap_last_sample_mib']:,} MiB |",
        f"| The swap's highest inside the questions | {got['swap_max_in_questions_mib']:,} MiB |",
        f"| The cache's highest | {got['cache_max_mib']:,} MiB |",
        f"| Entries removed, and their size | {got['removed_entries']},"
        f" {got['removed_mib']:,} MiB |",
        f"| Saves skipped | {got['skipped_saves']} |",
        f"| The questions' seconds, median and sum | {got['total_sec_median']:,} and"
        f" {got['total_sec_sum']:,} |",
        f"| The 5-minute load, median | {got['load5_median']} |",
        f"| The config file llama-server named | `{record['config_files'][0]}` |",
    ]


def forecast_rows() -> list[str]:
    got, printed, cache = record["reading"], record["printed"], record["cache"]
    footprints = [row["footprint_mib"] for row in questions]
    first = next(row["n"] for row in questions if row["removed_entries"])
    later = max(row["swap_max_mib"] for row in questions[25:])
    hours = printed["total_sec_sum"] / 3600

    def held(ok: bool) -> str:
        return "yes" if ok else "no"

    calm = record["gate"]["passed"] and not record["disturbance"]["disturbed"]
    return [
        f"| The gate passes, the series is not disturbed | passed, not disturbed | {held(calm)} |",
        f"| The swap holds, its growth within ± 256 MiB | {got['swap']},"
        f" {signed(got['growth_mib'])} MiB | {held(abs(got['growth_mib']) <= 256)} |",
        f"| The cache at most 1,024 MiB from question 2, removing entries from then | at most"
        f" {cache['max_mib']:,} MiB, the first removal in question {first}"
        f" | {held(cache['max_mib'] <= 1024 and first == 2)} |",
        f"| llama-server's footprint within ≈ 3,174–4,198 MiB | the questions' medians"
        f" {min(footprints):,.0f}–{max(footprints):,.0f} MiB"
        f" | {max(footprints) - 4198:.0f} MiB over the ≈ |",
        f"| The swap at questions 26–30 below 5,000 MiB | at most {later:,} MiB"
        f" | {held(later < 5000)} |",
        f"| The thirty in ≈ 2.3–2.7 h | {hours:.2f} h | {held(2.3 <= hours <= 2.7)} |",
    ]


def file_rows() -> list[str]:
    return [
        f"| `{name}` | {(RECORDS / name).stat().st_size:,} | `{sha(RECORDS / name)}` |"
        for name in FILES
    ]


def test_the_capsule_tables_are_the_records() -> None:
    text = CAPSULE.read_text(encoding="utf-8")
    rows = reading_rows() + question_table() + printed_rows() + forecast_rows()
    for line in rows + file_rows():
        assert line in text, line
    assert len(question_table()) == 30


def slowest_five() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(questions, key=lambda row: row["total_sec"])
    return ordered[-5:], ordered[:-5]


def prose_phrases() -> list[str]:
    """The prose's numbers that come from the record or 19beeb1's, as the capsule writes them."""
    printed, cache, launch = record["printed"], record["cache"], part["run"]["launch"]

    def gb(n: int) -> str:
        low, high = baseline[questions[n - 1]["case_id"]]["memory"]["swap_used_mb"]
        return f"{low / 1000:.1f}–{high / 1000:.1f}"

    swaps = [row["swap_mib"] for row in questions]
    footprints = [row["footprint_mib"] for row in questions]
    slow, others = slowest_five()
    five = sorted(row["n"] for row in slow)
    slow_sec = [row["total_sec"] for row in slow]
    mean = statistics.mean(row["total_sec"] for row in others)
    slow_rss = [row["api_rss_mib"] for row in slow]
    other_rss = [row["api_rss_mib"] for row in others]
    totals = [baseline[row["case_id"]]["total_sec"] for row in questions]
    mids = [mid(n) for n in range(1, 31)]
    then, later = windowed(mids, 6, 10), windowed(mids, 26, 30)
    first, last = part["samples"]["first_utc"], part["samples"]["last_utc"]
    return [
        f"rose from {gb(1)} GB of swap at question 1 to {gb(13)} GB at question 13, and was at"
        f" {gb(30)} GB at question 30",
        f"between {first[11:16]} and {last[11:16]} UTC, the sampler's first and last rows",
        f"the model loaded in {launch['ollama_load_sec']} s",
        f"each of the {cache['states']} cache-state lines printed the limit"
        f" {cache['limits_mib'][0]:,.1f} MiB",
        f"stayed within {min(swaps):,.1f}–{max(swaps):,.1f} MiB question by question",
        f"their slope from question 6 is the {signed(printed['swap_slope_mib_per_question'])} MiB",
        f"was {footprints[0]:,.0f} MiB in question 1, then"
        f" {min(footprints[1:]):,.0f}–{max(footprints[1:]):,.0f} MiB",
        f"the thirty took {printed['total_sec_sum'] / 3600:.2f} h",
        f"`19beeb1`'s rerun took {round(sum(totals), 3):,} s, a median"
        f" {round(statistics.median(totals), 3):,} s",
        f"Five questions — {', '.join(map(str, five[:-1]))} and {five[-1]} — took"
        f" {min(slow_sec):.0f}–{max(slow_sec):.0f} s; the other twenty-five took a mean"
        f" {mean:.1f} s",
        f"In those five the API's RSS medians were {min(slow_rss):,.0f}–{max(slow_rss):,.0f} MiB,"
        f" against {min(other_rss):,.0f}–{max(other_rss):,.0f} MiB in the others",
        f"the other twenty-five's mean gives {mean * 30 / 3600:.2f} h for thirty",
        f"{signed(record['reading']['growth_mib'])} MiB from questions 6–10 to 26–30, where the"
        f" same thirty questions without it grew {signed(later - then)} MB",
        f"at or under 1,024 MiB on all {cache['requests']} requests",
        f"llama-server's footprint at {min(footprints[1:]):,.0f}–{max(footprints[1:]):,.0f} MiB"
        " from question 2 on",
        f"The cache removed {cache['removed_entries']} entries, {cache['removed_mib']:,} MiB in all",
        f"{printed['swap_first_sample_mib']:,} MiB at the first sample",
    ]


def test_the_capsule_prose_is_the_records() -> None:
    flat = " ".join(CAPSULE.read_text(encoding="utf-8").split())
    for phrase in prose_phrases():
        assert phrase in flat, phrase
    # what the prose says of those numbers
    slow, others = slowest_five()
    low, high = min(row["swap_mib"] for row in others), max(row["swap_mib"] for row in others)
    assert all(low <= row["swap_mib"] <= high for row in slow)
    mean = statistics.mean(row["total_sec"] for row in others)
    assert 2.3 <= mean * 30 / 3600 <= 2.7
    assert record["cache"]["max_mib"] <= 1024
