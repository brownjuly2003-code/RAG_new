"""Stage 4's step 0: the record read again from its committed samples with the committed reader;
its gate, its stand, its environment and its privacy (docs/specs/stage4-step0-diagnostics.md,
«Records»). Every table row of docs/evidence/stage4-step0-record.md is built from the record."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "stage4-step0" / "tools"
RECORDS = ROOT / "reports" / "stage4-step0" / "4f48fed"
SPEC = ROOT / "docs" / "specs" / "stage4-step0-diagnostics.md"
CAPSULE = ROOT / "docs" / "evidence" / "stage4-step0-record.md"
V4 = ROOT / "reports" / "answer-prompt-v4" / "4f48fed"
LAUNCH_PY = ROOT / "reports" / "stage1" / "tools" / "launch.py"
CODE_SHA = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
# run 1's own read, the gate's, was made by the reader before the error fix the spec names
READER_BEFORE_FIX = "655d7c22698b0f9e7eb308c5efa4d714ffceec78fd9a32d82d6d6f9d4db8b5ed"
RUNS = {
    "s0-first": ["aircargo-probation-data"],
    "s0-rest": [
        "aircargo-probation-extend",
        "aircargo-probation-dismissal",
        "aircargo-dismissal-check",
        "aircargo-dismissal-lawyer",
    ],
}
FILES = (
    "step0.json",
    "s0-first.step0.json",
    "s0-rest.step0.json",
    "s0-first.samples.jsonl",
    "s0-rest.samples.jsonl",
    "environment.jsonl",
)
# what Samples.attach writes into a request's row
WINDOWS = (
    "request_window",
    "first_line_by",
    "release_after",
    "mem_after_state_mib",
    "prompt_window",
    "generation_window",
)
ALLOWED_NOTE = "ps: no process named llama-server"
READINGS = ("q1_cache_growth", "q2_memory_wait", "q3_prefix_reuse", "repack")


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("step0_reader_record", TOOLS / "step0_reader.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["step0_reader_record"] = module
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


record = _json(RECORDS / "step0.json")
own = {label: _json(RECORDS / f"{label}.step0.json") for label in RUNS}
v4 = _json(V4 / "v4-aircargo.json")["provenance"]


def requests() -> Iterator[tuple[str, dict[str, Any]]]:
    for label, part in zip(RUNS, record["parts"], strict=True):
        for process in part["processes"]:
            for row in process["requests"]:
                yield label, row


def test_the_record_was_read_by_the_committed_tools() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    pattern = r"^- `reports/stage4-step0/tools/(step0_\w+\.py)` `([0-9a-f]{64})`$"
    listed = dict(re.findall(pattern, spec, re.M))
    assert listed == {name: sha(TOOLS / name) for name in reader.TOOLS}
    assert record["tools_sha256"] == own["s0-rest"]["tools_sha256"] == listed
    assert own["s0-first"]["tools_sha256"] == {**listed, "step0_reader.py": READER_BEFORE_FIX}
    assert f"`step0_reader.py` was `{READER_BEFORE_FIX[:8]}…{READER_BEFORE_FIX[-6:]}`" in spec


def test_every_reading_is_a_function_of_the_rows() -> None:
    for read in (record, *own.values()):
        assert reader.readings(read["parts"]) == read["readings"]


def test_the_record_holds_each_runs_own_read() -> None:
    first, rest = record["parts"]
    assert rest == own["s0-rest"]["parts"][0]
    before = own["s0-first"]["parts"][0]

    def aside(part: dict[str, Any]) -> dict[str, Any]:
        return {**part, "processes": [{**p, "load": None} for p in part["processes"]]}

    assert aside(first) == aside(before)
    # the error fix reads the tagged build and system_info lines; nothing else of the load moved
    assert len(first["processes"]) == len(before["processes"]) == 1
    old, new = before["processes"][0]["load"], first["processes"][0]["load"]
    moved = sorted(key for key in new if new[key] != old[key])
    assert moved == ["build", "commit", "lines", "notes", "system_info"]
    assert (old["build"], old["commit"], old["system_info"]) == (None, None, None)
    assert old["notes"] == ["no build line", "no system_info line", "no load_backend line"]
    assert (new["build"], new["commit"], new["lines"] - old["lines"]) == (1, "d222767c7", 2)
    assert new["notes"] == ["no load_backend line"]


def test_the_samples_read_are_the_committed_files() -> None:
    for label, part in zip(RUNS, record["parts"], strict=True):
        notes: list[str] = []
        meta, _ = reader.read_samples(RECORDS / f"{label}.samples.jsonl", notes)
        assert (meta, notes) == (part["samples"], [])
        assert meta["stop_reason"] == "stop file"


def test_every_window_attaches_again_from_the_committed_samples() -> None:
    for label, part in zip(RUNS, record["parts"], strict=True):
        notes: list[str] = []
        _, rows = reader.read_samples(RECORDS / f"{label}.samples.jsonl", notes)
        samples = reader.Samples(rows, notes)
        assert (samples.pid, samples.page_size, notes) == (part["pid"], part["page_size"], [])
        for process in part["processes"]:
            for row in process["requests"]:
                again = {key: value for key, value in row.items() if key not in WINDOWS}
                samples.attach(again)
                assert again == row


def test_both_runs_pass_the_gate_run_one_was_held_to() -> None:
    drivers = {name: v4["tools_sha256"][name] for name in reader.DRIVERS if name != "launch.py"}
    for (label, cases), part in zip(RUNS.items(), record["parts"], strict=True):
        run = part["run"]
        # (i) the stand's code, a complete run, V4's drivers
        launch = run["launch"]
        assert (launch["code_sha"], launch["status"], launch["runner_exit"]) == (
            CODE_SHA,
            "complete",
            0,
        )
        assert {name: run["drivers_sha256"][name] for name in drivers} == drivers
        # (ii) every call of the run took a request of the log, each request a call
        assert run["joined"] == {
            "calls": 3 * len(cases),
            "matched": 3 * len(cases),
            "requests": 3 * len(cases),
        }
        # (iii) each request complete, with a cache state after the first
        rows = [row for process in part["processes"] for row in process["requests"]]
        for k, row in enumerate(rows):
            assert row["complete"], (label, k)
            assert None not in (
                row["cached_tokens"],
                row["prompt_ms"],
                row["eval_ms"],
                row["total_ms"],
            )
            assert k == 0 or row["cache_mib"] is not None
        # (iv) one model process, no sample note but the one before the model loads
        assert part["pid"] is not None and part["notes"] == []
        assert set(part["samples"]["sample_notes"]) == {ALLOWED_NOTE}
        assert [case["case_id"] for case in run["cases"]] == cases
        assert not any(case["client_error"] or case["drain_error"] for case in run["cases"])


def test_the_stand_is_v4s() -> None:
    assert record["corpus"] == {
        "dir": "/Users/julia/RAG_new_external_s1/aircargo",
        "sha256": v4["source_sha256"],
    }
    assert record["log"] == "/Users/julia/gr2_bench/ollama_serve.log"
    drivers = {name: v4["tools_sha256"][name] for name in reader.DRIVERS if name != "launch.py"}
    for (label, cases), part in zip(RUNS.items(), record["parts"], strict=True):
        run, launch = part["run"], part["run"]["launch"]
        assert run["dir"] == f"{v4['code']['workspace']}/chatlive/runs/{label}"
        assert run["drivers_sha256"] == {**drivers, "launch.py": sha(LAUNCH_PY)}
        assert (launch["label"], launch["cases"], launch["mode"]) == (label, cases, "prod")
        assert (launch["tenant"], launch["client_cap_sec"]) == ("aircargo", "1020/1200")
        assert (launch["workspace"], [launch["code_sha"]]) == (
            v4["code"]["workspace"],
            v4["code_sha"],
        )
        assert ([launch["model"]], [launch["model_digest"]]) == (v4["model"], v4["model_digest"])
        assert (launch["cases_file"], launch["overrides"]) == (v4["cases_file"], v4["overrides"])
        assert launch["chroma_dir"] == run["dir"] + ".chroma"
        assert (launch["ollama_models_before"], launch["ollama_models_after"]) == ([], v4["model"])


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
    first, rest = record["parts"]
    assert when(before["taken"]) < when(first["samples"]["first_utc"])
    assert when(rest["samples"]["last_utc"]) < when(after["taken"])


HEX = re.compile(r"[0-9a-f]{7,64}")
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)")
VERSION = re.compile(r"\d+(?:\.\d+)*")
PATH = re.compile(
    r"/Users/julia/(?:RAG_new_chat_4f48fed(?:/[\w.-]+)*|RAG_Support_Assistant/\.venv/bin/python"
    r"|gr2_bench/ollama_serve\.log|RAG_new_external_s1/aircargo"
    r"|RAG_new_tools_ollama_v0\.33\.2/ollama)"
)
WORDS = {
    # the record's enums, schemas and the spec's path
    *("stage4-step0/v1", "stage4-step0-samples/v1", "docs/specs/stage4-step0-diagnostics.md"),
    *("start", "sample", "stop", "stop file", "llama-server", ALLOWED_NOTE),
    *(
        "yes",
        "no",
        "on",
        "NOT_EVIDENCE",
        "complete",
        "prod",
        "aircargo",
        "auto",
        "cpu",
        "1020/1200",
    ),
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
    ids = set(RUNS) | {case for cases in RUNS.values() for case in cases} | set(FILES)
    assert sorted(path.name for path in RECORDS.iterdir()) == sorted(FILES)
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
    got = record["readings"]
    q1, q2, q3, rp = (got[key] for key in READINGS)
    assert (q1["answer"], q1["requests_spanned"], q1["accounts"]) == ("yes", 13, True)
    assert (q1["restored"], q1["removed_entries"], q1["skipped_saves"]) == (0, 0, 0)
    assert (q2["answer"], q2["windows"]) == ("no", 6)
    assert (q3["answer"], q3["lever"], len(q3["answers"]), q3["unreadable_answers"]) == (
        "no",
        "yes",
        3,
        0,
    )
    assert (rp["answer"], rp["model_buffers"], rp["backends"]) == (
        "on",
        ["CPU", "CPU_REPACK"],
        None,
    )
    # run 1 alone, the gate's file: too few requests for Q1, no later answer for Q3
    first = own["s0-first"]["readings"]
    assert (
        first["q1_cache_growth"]["answer"] == first["q3_prefix_reuse"]["answer"] == "NOT_EVIDENCE"
    )


def readings_rows() -> list[str]:
    q1, q2, q3, rp = (record["readings"][key] for key in READINGS)
    return [
        f"| Q1, the cache grows ≈ 300 MiB a request | **{q1['answer']}** |"
        f" {q1['growth_per_request_mib']} MiB a request over {q1['requests_spanned']};"
        f" the footprint {q1['footprint_delta_mib']:,} MiB for the cache's"
        f" {q1['cache_delta_mib']:,} (ratio {q1['ratio']}) | yes |",
        f"| Q2, generation waits on memory | **{q2['answer']}** |"
        f" a median {q2['median_faulted_mib_per_token']} MiB brought back a generated token,"
        f" {q2['windows']} windows | no |",
        f"| Q3, a later answer reuses its instructions | **{q3['answer']}** |"
        f" a median {q3['median_cached_tokens']:.0f} tokens reused, {len(q3['answers'])} answers | no |",
        f"| Q3's lever, the best prefix at hand saves ≥ 4 s | **{q3['lever']}** |"
        f" a median {q3['median_saving_ms'] / 1000:.1f} s an answer | no |",
        f"| Repacking | **{rp['answer']}** | model buffers {' and '.join(rp['model_buffers'])},"
        f" `system_info` REPACK = {rp['system_info_repack']} | on |",
    ]


def request_rows() -> list[str]:
    return [
        f"| {label} | `{row['case_id']}` | {row['role']} | {row['prompt_tokens']:,}"
        f" | {row['cached_tokens']} | {row['prompt_ms'] / 1000:.1f} | {row['eval_tokens']}"
        f" | {row['eval_tps']} | {row['cache_mib']:,.1f} | {row['mem_after_state_mib']:,.0f} |"
        for label, row in requests()
    ]


def window_rows() -> list[str]:
    out = []
    for label, row in requests():
        window = row["generation_window"] or {}
        if window.get("faulted_mib_per_token") is not None:
            out.append(
                f"| {label} | `{row['case_id']}` | {row['role']} | {window['sec']:.0f}"
                f" | {window['faulted_mib']:,.1f} | {window['faulted_mib_per_token']} |"
            )
    return out


def answer_rows() -> list[str]:
    rows = {(row["task"], row["case_id"]): row for _, row in requests()}
    out = []
    for got in record["readings"]["q3_prefix_reuse"]["answers"]:
        per_token = rows[got["task"], got["case_id"]]["prompt_ms_per_token"]
        out.append(
            f"| `{got['case_id']}` | {got['cached_tokens']} | {got['best_prefix']}"
            f" | {per_token} | {got['saving_ms'] / 1000:.1f} |"
        )
    return out


def time_rows() -> list[str]:
    stage = {row["case_id"]: row for row in _lines(V4 / "v4-aircargo.cases.jsonl")}
    out = []
    for part in record["parts"]:
        for case in part["run"]["cases"]:
            then = stage[case["case_id"]]
            out.append(
                f"| `{case['case_id']}` | {then['total_sec']:.1f} | {case['total_sec']:.1f}"
                f" | {then['route']} | {case['route']} |"
            )
    return out


def file_rows() -> list[str]:
    return [
        f"| `{name}` | {(RECORDS / name).stat().st_size:,} | `{sha(RECORDS / name)}` |"
        for name in FILES
    ]


def test_the_capsule_tables_are_the_records() -> None:
    text = CAPSULE.read_text(encoding="utf-8")
    rows = readings_rows() + request_rows() + window_rows() + answer_rows() + time_rows()
    for line in rows + file_rows():
        assert line in text, line
    assert len(request_rows()) == 15 and len(window_rows()) == 6 and len(answer_rows()) == 3
