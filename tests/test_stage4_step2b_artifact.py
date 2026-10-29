"""Stage 4's step 2b: the records read again with the committed reader; both phases' gates, the
stand, the inputs, the environment and the privacy
(docs/specs/stage4-step2b-continuation-labels.md, «Records»). Every table row of
docs/evidence/stage4-step2b-record.md is built from the records, and so is every number of its
prose that a test below pins."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from collections.abc import Iterator, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "stage4-step2b" / "tools"
RECORDS = ROOT / "reports" / "stage4-step2b" / "57420db"
SPEC = ROOT / "docs" / "specs" / "stage4-step2b-continuation-labels.md"
CAPSULE = ROOT / "docs" / "evidence" / "stage4-step2b-record.md"
STEP2 = ROOT / "reports" / "stage4-step2" / "57420db"
V4 = ROOT / "reports" / "answer-prompt-v4" / "4f48fed"
# the 80's inputs as committed
INPUTS = {
    "plan": ROOT / "reports" / "handover-signal" / "d260d95" / "plan.json",
    "labels": V4 / "v4-aircargo-judge.cases.jsonl",
}
# the stand and the replay's folders on the Mac, as the spec names them
STAND = "/Users/julia/RAG_new_chat_57420db"
V4_RUNS = "/Users/julia/RAG_new_chat_4f48fed/chatlive/runs"
# the files as copied from the Mac, by their SHA-256, which the Mac's copies matched
FILES = {
    "step2b.json": "54bfb186b908631ecec8646a0bcb0e9270402277ebdbc8328166bff26dac3d1e",
    "step2b.first.json": "c4f9397ddb5d6a8a4b9b8edaeace9b3e42172c92c4388716aeffcfac9625b24f",
    "step2b.bridge.json": "ce723ac82091067df0a8a2bd1f6983f9d3cc28e592776bde94261ee60d224310",
    "environment.jsonl": "47c806d835e14c654a64f2bad146feee105d1c11d28dba6d4305d39b30b321cd",
}
GATES = {
    "bridge": ("environment", "failures", "first", "inputs", "launch", "lines", "segments"),
    "labels": ("classes", "classic", "environment", "failures", "input_files", "inputs"),
}
GATES["bridge"] += ("step2", "tools")
GATES["labels"] += ("launch", "lines", "segments", "tools")


def _load() -> Any:
    spec = importlib.util.spec_from_file_location(
        "step2b_reader_record", TOOLS / "step2b_reader.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["step2b_reader_record"] = module
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


record = _json(RECORDS / "step2b.json")
reads = {
    "step2b.first.json": _json(RECORDS / "step2b.first.json"),
    "step2b.bridge.json": _json(RECORDS / "step2b.bridge.json"),
    "step2b.json": record,
}
environment = _lines(RECORDS / "environment.jsonl")
bridge, labels = record["bridge"], record["labels"]
bridge_pairs, pairs = record["bridge_pairs"], record["pairs"]
got = record["readings"]


def fmt(value: float) -> str:
    return f"{value:.3f}"


def span(values: Sequence[float], show: Any = fmt) -> str:
    return f"{show(min(values))}–{show(max(values))}"


def minutes(phase: dict[str, Any]) -> float:
    launch = phase["launch"]
    return (when(launch["finished"]) - when(launch["started"])).total_seconds() / 60


def hours(value: float) -> str:
    whole = round(value)
    return f"{whole // 60} h {whole % 60} min" if whole >= 60 else f"{whole} min"


def test_the_files_are_the_bytes_copied_from_the_mac() -> None:
    assert sorted(path.name for path in RECORDS.iterdir()) == sorted(FILES)
    for name, digest in FILES.items():
        data = (RECORDS / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), b"\r" in data) == (digest, False), name


def test_the_records_were_read_by_the_reader_and_the_replay_the_spec_lists() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    listed = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.(?:py|txt))` `([0-9a-f]{64})`", spec))
    assert len(listed) == 5
    for path, digest in listed.items():
        assert sha(ROOT / path) == digest, path
    by_name = {Path(path).name: digest for path, digest in listed.items()}
    assert (reader.SCHEMA, reader.CODE_SHA, reader.SPEC) == (
        "stage4-step2b-reader/v1",
        "57420db746e0510465bb5a08b7610e092b32e650",
        SPEC.relative_to(ROOT).as_posix(),
    )
    replay = {name: by_name[name] for name in reader.REPLAY_SHA256}
    assert replay == reader.REPLAY_SHA256
    for name, read in reads.items():
        assert (read["schema"], read["spec"], read["tools_sha256"]) == (
            reader.SCHEMA,
            reader.SPEC,
            {"step2b_reader.py": by_name["step2b_reader.py"]},
        ), name
        for phase in reader.PHASES:
            launch = read[phase]["launch"]
            if launch:
                assert launch["tools_sha256"] == replay, (name, phase)


def test_the_pairs_the_readings_and_the_first_answer_are_read_again_from_the_lines() -> None:
    for name, read in reads.items():
        asks, answers = read["step2"]["asks"], read["inputs"]["answers"]
        by_n = {
            phase: {line["n"]: line for line in read[phase]["lines"]} for phase in reader.PHASES
        }
        passed = {phase: read[phase]["gate"]["passed"] for phase in reader.PHASES}
        again = [
            reader.bridge_pair(ask, by_n["bridge"].get(ask["n"]), passed["bridge"]) for ask in asks
        ]
        assert again == read["bridge_pairs"], name
        those = [
            reader.pair_of(answer, by_n["labels"].get(answer["n"]), passed["labels"])
            for answer in answers
        ]
        assert those == read["pairs"], name
        bridged = reader.bridge_reading(again)
        assert {"bridge": bridged, **reader.readings(those, bridged["answer"])} == read["readings"]
        assert reader.first_answer(read["bridge"]["lines"], asks) == read["first_answer"], name


def test_both_phases_passed_their_gates_and_every_answer_was_read() -> None:
    for phase, points in GATES.items():
        assert record[phase]["gate"] == {**dict.fromkeys(points, True), "passed": True}, phase
        assert record[phase]["notes"] == [] and record[phase]["failures"] == [], phase
        launch = record[phase]["launch"]
        assert (launch["status"], launch["model_errors"]) == ("complete", 0), phase
        assert launch["segments"][-1]["status"] == "complete", phase
        assert len(launch["segments"]) <= reader.MAX_SEGMENTS, phase
    assert [line["n"] for line in bridge["lines"]] == list(range(1, 26))
    assert [line["n"] for line in labels["lines"]] == list(range(1, 81))
    assert (bridge["launch"]["answers"], labels["launch"]["answers"]) == (25, 80)
    for pair in (*bridge_pairs, *pairs):
        assert (pair["readable"], pair["unreadable"]) == (True, []), pair["n"]
    for name in ("inputs", "step2"):
        assert record[name]["notes"] == [], name
    assert record["first_answer"]["stop"] is False and record["first_answer"]["why"] == []


def test_the_first_answer_and_the_bridge_were_read_while_the_replay_went_on() -> None:
    one, two = reads["step2b.first.json"], reads["step2b.bridge.json"]
    # the first answer's read: the bridge's first line, its segment the first, read alone
    assert one["first_answer"] == record["first_answer"]
    assert one["bridge"]["lines"] == bridge["lines"][:1]
    assert one["bridge"]["launch"]["status"] == "first"
    assert one["bridge"]["launch"]["segments"] == bridge["launch"]["segments"][:1]
    assert one["bridge"]["gate"] == {
        **dict.fromkeys(GATES["bridge"], True),
        "environment": False,
        "launch": False,
        "lines": False,
        "segments": False,
        "passed": False,
    }
    # the bridge's read, before the 80: the bridge as the whole record has it, the 80 unread
    for key in ("bridge", "bridge_pairs", "first_answer", "step2", "inputs"):
        assert two[key] == record[key], key
    assert two["readings"]["bridge"] == got["bridge"]
    assert (two["labels"]["launch"], two["labels"]["lines"]) == ({}, [])
    assert two["labels"]["gate"]["passed"] is False
    for read in (one, two):
        assert read["readings"]["signal"]["answer"] == reader.NOT_EVIDENCE
    assert len(one["environment"]) == 1 and two["environment"] == record["environment"][:2]


def test_the_stand_the_settings_and_the_inputs_are_the_specs() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    for phase in reader.PHASES:
        launch = record[phase]["launch"]
        assert (launch["schema"], launch["spec"], launch["phase"]) == (
            reader.REPLAY_SCHEMA,
            reader.SPEC,
            phase,
        )
        assert (launch["code_sha"], launch["key"], launch["model"], launch["model_digest"]) == (
            reader.CODE_SHA,
            reader.KEY,
            reader.MODEL,
            reader.MODEL_DIGEST,
        )
        assert f"`{launch['model_digest'][:12]}…`" in spec
        assert (launch["stream_path"], launch["prompt_id"], launch["instruction_sha256"]) == (
            reader.STREAM_PATH,
            reader.PROMPT_ID,
            reader.INSTRUCTION_SHA256,
        )
        assert (launch["num_ctx"], launch["input_limit"], launch["params"]) == (
            reader.NUM_CTX,
            reader.INPUT_LIMIT,
            reader.PARAMS,
        )
        assert (launch["answer_stop_sec"], launch["reload_every"]) == (
            reader.ANSWER_STOP,
            reader.RELOAD_EVERY,
        )
        for line in record[phase]["lines"]:
            assert (line["phase"], line["stream_path"], line["num_ctx"]) == (
                phase,
                reader.STREAM_PATH,
                reader.NUM_CTX,
            )
    # the bridge: step 2's asks its reader read, from step 2's records as committed
    assert bridge["launch"]["runs"] == f"{STAND}/step2/runs"
    assert bridge["launch"]["planned"] == {"s2-both": 12, "s2-both-r2": 13}
    assert record["step2"]["sha256"] == reader.STEP2_SHA256
    asks = []
    for label, name in reader.STEP2_RECORDS.items():
        assert sha(STEP2 / name) == reader.STEP2_SHA256[label]
        for ask in _json(STEP2 / name)["run"]["asks"]:
            if ask["read"]:
                warm = ask["self_eval"]["continuation"]
                asks.append((label, ask["case_id"], warm["score"], warm["sec"]))
    assert [
        (ask["run"], ask["case_id"], ask["warm"]["score"], ask["warm"]["sec"])
        for ask in record["step2"]["asks"]
    ] == asks
    # the 80: the committed plan and labels, the targets first
    assert labels["launch"]["runs"] == V4_RUNS
    assert labels["launch"]["inputs_sha256"] == reader.INPUTS_SHA256
    assert {name: sha(path) for name, path in INPUTS.items()} == reader.INPUTS_SHA256
    inputs = record["inputs"]
    assert (inputs["targets"], inputs["goods"], inputs["unjudged"]) == (17, 63, 0)
    assert inputs["classic"] == {
        "at_80": reader.CLASSIC,
        "under_100": reader.CLASSIC_UNDER_100,
    }
    classes = [answer["class"] for answer in inputs["answers"]]
    assert classes == ["target"] * 17 + ["good"] * 63
    assert labels["launch"]["planned"] == {"goods": 63, "targets": 17}


def test_the_environment_brackets_each_phase_on_v4s_server() -> None:
    stage = _lines(V4 / "v4-environment.jsonl")[-1]
    assert len(environment) == 3
    for line in environment:
        assert line["ollama"] == stage["ollama"]
        assert line["ollama"]["server_version"] == reader.OLLAMA_VERSION
        assert len(line["ollama"]["servers"]) == 1
        assert line["distributions"] == stage["distributions"]
        assert (line["python"], line["python_version"]) == (
            stage["python"],
            stage["python_version"],
        )
    taken = [when(line["taken"]) for line in environment]
    spans = [
        (when(record[phase]["launch"]["started"]), when(record[phase]["launch"]["finished"]))
        for phase in reader.PHASES
    ]
    assert taken[0] < spans[0][0] < spans[0][1] < taken[1] < spans[1][0] < spans[1][1] < taken[2]
    assert [line["taken"] for line in record["environment"]] == [
        line["taken"] for line in environment
    ]


HEX = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00")
VERSION = re.compile(r"\d+(?:\.\d+)+")
RUN = re.compile(r"s2-both(?:-r2)?|v4-aircargo-b(?:0[1-9]|10)")
CASE_FILE = re.compile(r"\d\d-(aircargo-[a-z0-9-]+)\.json")
PROMPT_FILE = re.compile(r"\d{3}-stream\.txt")
PATH = re.compile(
    r"/Users/julia/(?:RAG_new_chat_57420db/(?:step2b/(?:bridge|labels|step2)|step2/runs"
    r"|reports/handover-signal/d260d95/plan\.json"
    r"|reports/answer-prompt-v4/4f48fed/v4-aircargo-judge\.cases\.jsonl)"
    r"|RAG_new_chat_4f48fed/chatlive/runs|RAG_Support_Assistant/\.venv/bin/python"
    r"|RAG_new_tools_ollama_v0\.33\.2/ollama)"
)
WORDS = {
    # the schemas, the spec's path, the stand's key, model and instruction, the enums
    *(reader.SCHEMA, reader.REPLAY_SCHEMA, reader.SPEC, reader.KEY, reader.MODEL),
    *(reader.PROMPT_ID, reader.STREAM_PATH, reader.NOT_EVIDENCE, "held", "not held"),
    *(*reader.PHASES, *reader.CLASSES, *reader.OUTCOMES, *reader.STATUSES),
    *("llm", "auto", "human", "classic", "stop", "None", "huggingface-hub"),
    *("no difference", "effective more", "effective fewer"),
    # the reader's fixed reasons, of the reads taken while the replay went on
    *("no line", "the bridge's gate did not pass", "the 80's gate did not pass"),
    "bridge: 1 lines for 25 answers",
    "bridge segments: the last segment, and it alone, is not the complete one",
    *(f"{phase} environment: fewer than two environment lines" for phase in reader.PHASES),
    "bridge environment: no environment line after the phase",
    "labels environment: no times to set the lines beside the phase",
    *("labels: no readable launch.json", "labels lines: not readable"),
    *("labels: 0 lines for 80 answers", "labels segments: no segments, or one unreadable"),
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
    cases_file = ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
    ids = {json.loads(line)["case_id"] for line in cases_file.read_text("utf-8").splitlines()}
    for name in FILES:
        text = (RECORDS / name).read_text(encoding="utf-8")
        assert not re.search("[\u0400-\u04ff]", text), name
        parsed = _lines(RECORDS / name) if name.endswith(".jsonl") else [_json(RECORDS / name)]
        for value, key in strings(parsed):
            if key:
                assert len(value) <= 40, (name, value)
                continue
            if (case := CASE_FILE.fullmatch(value)) is not None:
                assert case[1] in ids, (name, value)
                continue
            shapes = (HEX, TIME, VERSION, RUN, PROMPT_FILE, PATH)
            known = value in WORDS or value in ids or any(s.fullmatch(value) for s in shapes)
            assert known, (name, value)


NAMES = {"bridge": "the bridge", "labels": "the 80"}


def bridge_rows() -> list[str]:
    out = []
    for pair in bridge_pairs:
        sec, counters = pair["printed"]["sec"], pair["printed"]["counters"]["cold"]
        score, routes = pair["score"], pair["routes"]
        out.append(
            f"| {pair['n']} | `{pair['run']}` | `{pair['case_id']}` | {fmt(sec['warm'])}"
            f" | {fmt(sec['cold'])} | {score['warm']} / {score['cold']}"
            f" | {routes['warm']} / {routes['cold']}"
            f" | {counters['prompt_tokens']:,} / {fmt(counters['prompt_sec'])} |"
        )
    return out


def segment_rows() -> list[str]:
    out = []
    for phase in reader.PHASES:
        for index, segment in enumerate(record[phase]["launch"]["segments"], start=1):
            unload = segment["final_unload"]
            out.append(
                f"| {NAMES[phase]} | {index} | {when(segment['started']):%H:%M:%S}"
                f"–{when(segment['finished']):%H:%M:%S} | {segment['status']}"
                f" | {segment['from_n']} | {fmt(segment['ollama_load_sec'])}"
                f" | {fmt(unload['unload_sec'])}, {unload['polls']} |"
            )
    return out


def bridge_printed_rows() -> list[str]:
    printed = got["bridge"]["printed_deciding_nothing"]
    diff = printed["cold_minus_warm"]

    def scores(side: str) -> str:
        values = printed[side]["scores"].items()
        return ", ".join(f"{score} × {n}" for score, n in sorted(values, key=lambda x: -int(x[0])))

    def counters(side: str) -> str:
        c = printed[side]["median_counters"]
        return (
            f"{c['prompt_tokens']:,}, {fmt(c['prompt_sec'])}, {c['eval_tokens']},"
            f" {fmt(c['eval_sec'])}"
        )

    return [
        f"| Equal scores, warm and cold | {printed['equal']} of {got['bridge']['readable_pairs']} |",
        "| Routes, warm → cold | "
        + ", ".join(f"{k.replace('->', ' → ')} {n}" for k, n in printed["routes"].items())
        + " |",
        "| Cold minus warm: higher / the same / lower, the median"
        f" | {diff['higher']} / {diff['same']} / {diff['lower']}, {diff['median_diff']} |",
        "| Outcomes, cold | "
        + ", ".join(f"{k} {n}" for k, n in printed["by_outcome"].items())
        + " |",
        "| Answers by run | "
        + ", ".join(f"`{k}` {n}" for k, n in printed["by_run"].items())
        + " |",
        f"| Scores, warm | {scores('warm')} |",
        f"| Scores, cold | {scores('cold')} |",
        "| Seconds, a median, warm / cold"
        f" | {fmt(printed['warm']['median_sec'])} / {fmt(printed['cold']['median_sec'])} |",
        "| Warm counters, medians: prompt tokens, prompt s, generated tokens, generated s"
        f" | {counters('warm')} |",
        "| Cold counters, medians: prompt tokens, prompt s, generated tokens, generated s"
        f" | {counters('cold')} |",
    ]


def file_rows() -> list[str]:
    return [
        f"| `{name}` | {(RECORDS / name).stat().st_size:,} | `{sha(RECORDS / name)}` |"
        for name in FILES
    ]
