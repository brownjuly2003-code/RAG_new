"""Stage 4, step 4b: num_ctx 3,584 against 4,096, timed — the record read again with the
committed tool; its gates, its stand, its inputs and its privacy
(docs/specs/stage4-step4b-window-timing.md, «Records»). Every table row of
docs/evidence/stage4-step4b-record.md is built from the record, and so is every number of its
prose that a test below pins."""

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
TOOL = ROOT / "reports" / "stage4-step4b" / "tools" / "window_timing.py"
RECORDS = ROOT / "reports" / "stage4-step4b" / "d1ef9e5"
SPEC = ROOT / "docs" / "specs" / "stage4-step4b-window-timing.md"
CAPSULE = ROOT / "docs" / "evidence" / "stage4-step4b-record.md"
CASES_FILE = ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
STEP4_ROWS = ROOT / "reports" / "stage4-step4" / "5e308fe" / "rows.jsonl"
V4_ROWS = ROOT / "reports" / "answer-prompt-v4" / "4f48fed" / "v4-aircargo.cases.jsonl"
CODE_SHA = "d1ef9e5584c37b91c426d41bfbc34a78362ae1be"
# the files as copied from the Mac, by their SHA-256, which the Mac's copies matched
FILES = {
    "record.json": "e56b023aa32928c218b65809a8bd8f393c4b3c1d0e907408605c9a952aeb9937",
    "rows.jsonl": "6eae246cb024446fc22738426640e4930568ca2fb997a753a4e3108a2e702905",
}
PLAN_KEYS = ("block", "position", "case_id", "window", "order")
SIZES = ("documents", "cut", "chars", "est_tokens")


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("window_timing_record", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["window_timing_record"] = module
    spec.loader.exec_module(module)
    return module


wt = _load()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


record = _json(RECORDS / "record.json")
rows = _lines(RECORDS / "rows.jsonl")
pairs = record["pairs"]
readable = [pair for pair in pairs if pair["readable"]]
W, S = wt.TODAY, wt.SMALL


def fmt(value: float) -> str:
    return f"{value:,.3f}"


def n(value: int) -> str:
    return f"{value:,}"


def tok(value: float) -> str:
    """A count, or a median of counts that may fall between two."""
    return n(int(value)) if value == int(value) else f"{value:,.1f}"


def side(pair: dict[str, Any], name: str, show: Any = str) -> str:
    """A pair's value at both windows, 4,096's first."""
    return f"{show(pair[f'w{W}_{name}'])} / {show(pair[f'w{S}_{name}'])}"


def spread(name: str) -> tuple[float, float]:
    values = [pair[name] for pair in readable]
    return min(values), max(values)


def at_window(window: int, name: str) -> list[Any]:
    """A field of the readable pairs' blocks at one window, in the pairs' order."""
    return [
        row[name]
        for pair in readable
        for row in rows
        if (row["position"], row["window"]) == (pair["position"], window)
    ]


def less(name: str) -> list[float]:
    """Each readable pair's 4,096 value less its 3,584 value."""
    return [pair[f"w{W}_{name}"] - pair[f"w{S}_{name}"] for pair in readable]


def first_token_saving() -> list[float]:
    today, small = at_window(W, "first_token_sec"), at_window(S, "first_token_sec")
    return [a - b for a, b in zip(today, small, strict=True)]


def tokens_ratio(pair: dict[str, Any]) -> float:
    """The two prompts' tokens at 3,584 over 4,096's."""

    def both(window: int) -> int:
        return pair[f"w{window}_answer_prompt_tokens"] + pair[f"w{window}_eval_prompt_tokens"]

    return both(S) / both(W)


def sizes() -> tuple[int, int]:
    """/api/ps's size at each window, the same in every block of it."""
    (today,) = {row["ps_size"] for row in rows if row["window"] == W}
    (small,) = {row["ps_size"] for row in rows if row["window"] == S}
    return today, small


def mib(value: float) -> str:
    return f"{value / 2**20:,.1f}"


def test_the_files_are_the_bytes_copied_from_the_mac() -> None:
    assert sorted(path.name for path in RECORDS.iterdir()) == sorted(FILES)
    for name, digest in FILES.items():
        data = (RECORDS / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), b"\r" in data) == (digest, False), name


def test_the_record_was_read_by_the_tool_the_spec_registers() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    listed = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    tool = TOOL.relative_to(ROOT).as_posix()
    assert sorted(listed) == [tool, "tests/test_stage4_step4b_tools.py"]
    for path, digest in listed.items():
        assert sha(ROOT / path) == digest, path
    assert (record["schema"], record["spec"]) == (wt.SCHEMA, wt.SPEC)
    assert (wt.SCHEMA, wt.SPEC) == ("stage4-step4b/v1", SPEC.relative_to(ROOT).as_posix())
    # the series ran the registering commit's worktree, and its tool read the record
    assert f"in `{CODE_SHA[:7]}`" in spec
    assert record["series"]["code_sha"] == record["inputs"]["code_sha"] == CODE_SHA
    assert record["series"]["tool_sha256"] == record["reader_sha256"] == listed[tool]
    assert record["model"] == {
        "name": "qwen3:4b-instruct-2507-q4_K_M",
        "digest": wt.DIGEST,
        "ollama_version": "0.33.2",
    }
    assert wt.DIGEST.startswith("0edcdef3")
    assert record["windows"] == [4096, 3584] == [W, S]


def test_the_pairs_and_the_readings_are_read_again_from_the_rows() -> None:
    assert [{key: row[key] for key in PLAN_KEYS} for row in rows] == wt.BLOCKS
    assert wt.pair_up(rows) == pairs
    assert wt.readings(pairs) == record["readings"]
    assert [(pair["position"], pair["case_id"]) for pair in pairs] == list(
        enumerate(wt.CASES, start=1)
    )
    # ABBA: each window first in six of the twelve pairs
    firsts = [pair["first"] for pair in pairs[1:]]
    assert (firsts.count(W), firsts.count(S)) == (6, 6)


def test_every_block_passed_its_gate_undisturbed_at_its_window() -> None:
    assert len(rows) == 26
    for row in rows:
        where = (row["block"], row["case_id"], row["window"])
        assert (row["present"], row["gate"], row["disturbed"]) == (True, [], []), where
        assert row["context_length"] == row["window"], where
        assert row["ps_size_vram"] == 0, where
        assert row["route"] in ("auto", "human"), where
        assert row["answer_chars"] > 0 and row["answer_tokens"] > 0, where
        assert row["unload_sec"] is not None and row["first_token_sec"] is not None, where
        for name in ("prompt_sec", "whole_sec", "result_sec", "load_sec", "eval_load_sec"):
            assert isinstance(row[name], float), (where, name)
        # the two prompts' seconds are the two calls' own, summed before rounding
        assert abs(row["prompt_sec"] - row["answer_prompt_sec"] - row["eval_prompt_sec"]) < 0.002
    assert record["attempts"] == {str(block["block"]): 1 for block in wt.BLOCKS}
    assert record["rejected"] == []
    assert [pair["readable"] for pair in pairs] == [False] + [True] * 12
    assert all(pair["why"] == [] for pair in pairs)


def test_one_ollama_and_one_interpreter_ran_the_series() -> None:
    env = record["environment"]
    # the series stopped after block 1 by the spec's stop file and was started again once
    assert (env["lines"], env["tags"]) == (3, ["start", "start", "end"])
    assert env["server_versions"] == ["0.33.2"]
    assert len(env["servers"]) == 1
    assert env["python_versions"] == ["3.11.15"]
    assert len(env["freeze_sha256"]) == 1
    (packages,) = env["packages"]
    assert json.loads(packages)["langchain-ollama"] == "1.1.0"
    assert env["llama_config"] is False


def test_the_inputs_are_step_4s_documents_and_v4s_prompt_at_4096() -> None:
    inputs = record["inputs"]
    assert inputs["step4_rows_sha256"] == sha(STEP4_ROWS)
    step4 = {row["case_id"]: row for row in _lines(STEP4_ROWS) if row["base"] == "aircargo"}
    v4 = {row["case_id"]: row for row in _lines(V4_ROWS)}
    cases = [json.loads(line)["case_id"] for line in CASES_FILE.read_text("utf-8").splitlines()]
    assert cases[: len(wt.CASES)] == list(wt.CASES)
    assert [(case["position"], case["case_id"]) for case in inputs["cases"]] == list(
        enumerate(wt.CASES, start=1)
    )
    for case in inputs["cases"]:
        row = step4[case["case_id"]]
        assert case["index"] == row["index"] and row["v4_prompt_checked"] is True
        for entry in row["windows"]:
            if entry["window"] in wt.WINDOWS:
                got = case["prompts"][str(entry["window"])]
                assert {key: got[key] for key in SIZES} == {key: entry[key] for key in SIZES}
        assert case["prompts"][str(W)]["sha256"] == v4[case["case_id"]]["prompts"][0]["sha256"]
    # each block sent its question's registered prompt at its window
    by_case = {case["case_id"]: case for case in inputs["cases"]}
    for row in rows:
        got = by_case[row["case_id"]]["prompts"][str(row["window"])]
        assert (row["prompt_sha256"], row["documents"], row["prompt_est_tokens"]) == (
            got["sha256"],
            got["documents"],
            got["est_tokens"],
        ), row["block"]


HEX = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00")
SERVER = re.compile(r"\d+ \d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00")
PACKAGE = re.compile(r"[a-z0-9_.-]+")
WORDS = {
    # the schema, the spec's path, the model, the versions, the readings' and rows' enums
    *("stage4-step4b/v1", "docs/specs/stage4-step4b-window-timing.md"),
    *("qwen3:4b-instruct-2507-q4_K_M", "0.33.2", "3.11.15", "start", "end"),
    *("faster", "slower", "no detected difference", "NOT_EVIDENCE", "auto", "human", "llm"),
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


def test_the_record_holds_numbers_ids_enums_and_hashes_only() -> None:
    questions = [json.loads(line)["query"] for line in CASES_FILE.read_text("utf-8").splitlines()]
    ids = set(wt.CASES)
    for name in FILES:
        text = (RECORDS / name).read_text(encoding="utf-8")
        assert not re.search("[\u0400-\u04ff]", text), name
        assert "/Users/" not in text, name
        assert not [q for q in questions[: len(wt.CASES)] if q in text], name
    env = dict(record["environment"])
    for packages in env.pop("packages"):
        for package, version in json.loads(packages).items():
            assert PACKAGE.fullmatch(package) and PACKAGE.fullmatch(version), (package, version)
    parsed = {"record.json": {**record, "environment": env}, "rows.jsonl": rows}
    for name, value in parsed.items():
        for string, key in strings(value):
            if key:
                assert len(string) <= 40, (name, string)
                continue
            shapes = (HEX, TIME, SERVER)
            known = string in WORDS or string in ids or any(s.fullmatch(string) for s in shapes)
            assert known, (name, string)


def test_the_readings_against_the_forecast() -> None:
    got = record["readings"]
    assert (got["answer"], got["readable_questions"]) == ("faster", 12)
    assert (got["small_faster"], got["small_slower"], got["sign_p"]) == (12, 0, 0.000488)
    # with twelve readable pairs faster needed ten: the spec's p = 0.039
    assert wt.sign_p(10, 2) < wt.ALPHA <= wt.sign_p(9, 3)
    assert round(wt.sign_p(10, 2), 3) == 0.039
    assert (got["median_prompt_saving_sec"], got["median_prompt_ratio"]) == (24.681, 0.792)
    printed = got["printed_deciding_nothing"]
    assert printed["median_prompt_sec"] == {f"w{W}": 118.708, f"w{S}": 94.192}
    assert printed["median_prompt_token_saving"] == {"answer": 416.5, "eval": 435.5}
    for key in ("whole", "result"):
        assert (printed[key]["small_faster"], printed[key]["small_slower"]) == (12, 0), key
    assert (printed["same_route"], printed["same_answer"]) == (11, 3)
    assert printed["routes"] == {
        f"w{W}": {"auto": 12, "human": 0},
        f"w{S}": {"auto": 11, "human": 1},
    }
    # the forecast: faster on 12 of 12 held, the saving within ≈ 23-30 s, the ratio below
    # ≈ 0.82; the two prompts at 4,096 took less than ≈ 150 s; /api/ps fell by ≈ 72 MiB
    assert 23 <= got["median_prompt_saving_sec"] <= 30 and got["median_prompt_ratio"] < 0.82
    assert printed["median_prompt_sec"][f"w{W}"] < 150
    today, small = sizes()
    assert round((today - small) / 2**20, 1) == 72.5
    # every pair's seconds fell further than its tokens
    assert all(pair["prompt_sec_ratio"] < tokens_ratio(pair) for pair in readable)
    # the answer's first token came earlier at 3,584 in every pair (mine, no rule of the spec)
    assert all(value > 0 for value in first_token_saving())


def fmt_range(values: list[float], unit: str = "") -> str:
    return f"{fmt(min(values))}–{fmt(max(values))}{unit}"


def readings_rows() -> list[str]:
    got = record["readings"]
    return [
        "| The answer: 3,584's prompt seconds below 4,096's on more pairs, the exact two-sided"
        f" sign test's p below 0.05 | **{got['answer']}** | below on {got['small_faster']} of"
        f" {got['readable_questions']} readable pairs, above on {got['small_slower']};"
        f" p {got['sign_p']:.6f} | faster, on 12 of 12 |",
        "| The number: the median saving, 4,096's prompt seconds less 3,584's"
        f" | **{fmt(got['median_prompt_saving_sec'])} s**"
        f" | {fmt_range([p['prompt_sec_saving'] for p in readable], ' s')} by question"
        " | ≈ 23–30 s |",
        "| The number: the median ratio, 3,584's prompt seconds over 4,096's"
        f" | **{fmt(got['median_prompt_ratio'])}**"
        f" | {fmt_range([p['prompt_sec_ratio'] for p in readable])} by question | ≈ 0.82 |",
    ]


def prompt_rows() -> list[str]:
    return [
        f"| {pair['position']} | `{pair['case_id']}` | {n(pair['first'])}"
        f" | {side(pair, 'documents')} | {side(pair, 'answer_prompt_tokens', n)}"
        f" | {side(pair, 'eval_prompt_tokens', n)} | {side(pair, 'prompt_sec', fmt)}"
        f" | {fmt(pair['prompt_sec_saving'])} | {fmt(pair['prompt_sec_ratio'])} |"
        for pair in readable
    ]


def answer_rows() -> list[str]:
    return [
        f"| {pair['position']} | `{pair['case_id']}` | {side(pair, 'answer_tokens', n)}"
        f" | {side(pair, 'whole_sec', fmt)} | {side(pair, 'result_sec', fmt)}"
        f" | {fmt(pair['result_sec_saving'])} | {side(pair, 'score')} | {side(pair, 'route')} |"
        for pair in readable
    ]


def printed_rows() -> list[str]:
    got = record["readings"]["printed_deciding_nothing"]
    count = record["readings"]["readable_questions"]
    warm = got["warm_up"]

    def row(name: str, values: dict[str, Any], show: Any) -> str:
        return f"| {name} | {show(values[f'w{W}'])} | {show(values[f'w{S}'])} |"

    def first(key: str) -> dict[str, Any]:
        return {window: value[key] for window, value in warm.items()}

    return [
        row("The two prompts' seconds, a median", got["median_prompt_sec"], fmt),
        row("The result's seconds, a median", got["median_result_sec"], fmt),
        row("The answer's prompt, tokens, a median", got["median_answer_prompt_tokens"], tok),
        row(
            "The self-evaluation's prompt, tokens, a median", got["median_eval_prompt_tokens"], tok
        ),
        row(
            "The answer's prompt read, tokens a second, a median",
            got["median_answer_prompt_rate"],
            fmt,
        ),
        row("The answer's generated tokens, a median", got["median_answer_tokens"], tok),
        row(
            "The answer's generation, tokens a second, a median",
            got["median_generation_rate"],
            fmt,
        ),
        row("The load, s, a median", got["median_load_sec"], fmt),
        row("`/api/ps`'s size, bytes, a median", got["median_ps_size"], tok),
        row("Routes, auto / human", got["routes"], lambda v: f"{v['auto']} / {v['human']}"),
        row("Scores parsed", got["scores_parsed"], lambda v: f"{v} of {count}"),
        row("The first question's prompt seconds", first("prompt_sec"), fmt),
        row("The first question's result, s", first("result_sec"), fmt),
        row("The first question's load, s", first("load_sec"), fmt),
    ]


def compared_rows() -> list[str]:
    got = record["readings"]["printed_deciding_nothing"]
    count = record["readings"]["readable_questions"]
    return [
        f"| {name} | {got[key]['small_faster']} of {count} | {got[key]['small_slower']}"
        f" | {got[key]['sign_p']:.6f} | {fmt(got[key]['median_saving_sec'])}"
        f" | {fmt(got[key]['median_ratio'])} |"
        for name, key in (("The whole", "whole"), ("The result", "result"))
    ]


# the spec's forecasts, in its words
FORECAST = (
    "**faster**, on 12 of 12",
    "about 430 exact tokens a call: 469 estimated, the estimate about 10% above the exact count",
    "At 4,096 the two prompts take ≈ 150 s together",
    "the saving is ≈ 23–30 s and the ratio ≈ 0.82",
    "The whole and the result fall by about as much, with the answers' spread around it",
    "`/api/ps`'s size falls by about the KV cache of 512 tokens, ≈ 72 MiB at f16 (36 layers, 8 KV"
    " heads of 128)",
    "a block ≈ 200 s at 4,096 — a load ≈ 15 s, the answer's prompt ≈ 70 s, ≈ 190 tokens generated"
    " at ≈ 4 a second, the self-evaluation's prompt ≈ 75 s — and ≈ 180 s at 3,584",
    "≈ 85 min for the 26, ≈ 1.5 h with the unloads and the checks",
)


def forecast_rows() -> list[str]:
    got = record["readings"]
    printed = got["printed_deciding_nothing"]
    saved = printed["median_prompt_token_saving"]
    today, small = sizes()

    def with_load(window: int) -> str:
        return fmt(
            wt.median([p[f"w{window}_result_sec"] + p[f"w{window}_load_sec"] for p in readable])
        )

    measured = (
        f"**{got['answer']}**, on {got['small_faster']} of {got['readable_questions']}",
        f"a median {tok(saved['answer'])} in the answer's prompt and {tok(saved['eval'])} in the"
        f" self-evaluation's, against {tok(wt.median(less('prompt_est_tokens')))} estimated",
        f"a median {fmt(printed['median_prompt_sec'][f'w{W}'])} s; the answer's prompt read at"
        f" {fmt(printed['median_answer_prompt_rate'][f'w{W}'])} tokens a second",
        f"a saving of {fmt(got['median_prompt_saving_sec'])} s and a ratio of"
        f" {fmt(got['median_prompt_ratio'])}",
        f"the whole {fmt(printed['whole']['median_saving_sec'])} s and the result"
        f" {fmt(printed['result']['median_saving_sec'])} s less, a median; the result's saving"
        f" {fmt_range([p['result_sec_saving'] for p in readable], ' s')} by question",
        f"{mib(today - small)} MiB: {n(today)} bytes at 4,096 in every block, {n(small)} at 3,584",
        f"at 4,096 a load of {fmt(printed['median_load_sec'][f'w{W}'])} s, the answer's prompt"
        f" {fmt(wt.median([p[f'w{W}_answer_prompt_sec'] for p in readable]))} s,"
        f" {tok(printed['median_answer_tokens'][f'w{W}'])} tokens generated at"
        f" {fmt(printed['median_generation_rate'][f'w{W}'])} a second, the self-evaluation's"
        f" prompt {fmt(wt.median([p[f'w{W}_eval_prompt_sec'] for p in readable]))} s, each a"
        f" median; the result and the load {with_load(W)} s at 4,096 and {with_load(S)} s at"
        " 3,584",
        "the record keeps no block's start or end",
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
        prompt_rows: 12,
        answer_rows: 12,
        printed_rows: 14,
        compared_rows: 2,
        forecast_rows: 8,
        file_rows: 2,
    }
    for build, count in tables.items():
        built = build()
        assert len(built) == count, build.__name__
        for row in built:
            assert row in lines, row


# step 4's gold for the window, in the spec's words; the capsule quotes it
GOLD = "keep it at «sent» in 134 of 250 questions against 137 at 4,096 (b 3, c 0, p = 0.25)"

# the capsule's own words for its limits and its reading; each sits on one line of it
PHRASES = (
    "The record holds no question, document, source name, answer, prompt or command line.",
    "Seconds of two calls; nothing on quality.",
    "No window is adopted here.",
    "the window in the path is Julia's word",
    "The record does not say why.",
    "(mine, no rule of the spec)",
    "One score of one answer decides nothing on quality.",
    "The series' wall is not in the record.",
    "Item 5 measures memory.",
    GOLD,
)


def computed_phrases() -> list[str]:
    got = record["readings"]
    printed = got["printed_deciding_nothing"]
    count = got["readable_questions"]
    started = datetime.fromisoformat(record["series"]["started"])
    env = record["environment"]
    (server,) = env["servers"]
    (packages,) = env["packages"]
    loads = [row["loadavg_before"][1] for row in rows[:2]]
    saved = printed["median_prompt_token_saving"]
    order = {key: value["median_prompt_saving_sec"] for key, value in printed["by_order"].items()}
    rate = printed["median_answer_prompt_rate"]
    generated = printed["median_answer_tokens"]
    first = first_token_saving()
    (moved,) = [pair for pair in readable if pair[f"w{W}_route"] != pair[f"w{S}_route"]]
    today, small = sizes()
    return [
        f"in `{CODE_SHA[:7]}` before the first request; nothing changed after it.",
        f"The series started at {started:%H:%M} UTC on {started:%Y-%m-%d}.",
        f"code `{record['series']['code_sha']}`",
        f"Python {env['python_versions'][0]} with `langchain-ollama`"
        f" {json.loads(packages)['langchain-ollama']}",
        f"**Ollama:** {env['server_versions'][0]} at the series' start, at its resume and at its end",
        f"One server throughout, up since {server.split()[1][:10]}.",
        f"`{record['model']['name']}`, digest `{record['model']['digest'][:8]}…`",
        f"`evaluation/curated_cases_aircargo.jsonl` (`{sha(CASES_FILE)[:8]}…`)",
        f"`{wt.CASES[0]}` came first",
        f"step 4's committed rows (`{record['inputs']['step4_rows_sha256'][:8]}…`)",
        f"The self-evaluation's load was at most {fmt(max(row['eval_load_sec'] for row in rows))} s",
        f"The 5-minute load was {loads[0]} before block 1 and {loads[1]} before block 2",
        f"faster needed at least 10 of 12 (p = {wt.sign_p(10, 2):.3f})",
        f"a median: {tok(saved['answer'])} in the answer's prompt, {tok(saved['eval'])} in the",
        f"The same route in {printed['same_route']} of {count} pairs; the same answer, by SHA-256,"
        f" in {printed['same_answer']} of {count}.",
        f"4,096 first in {printed['by_order'][f'w{W}_first']['pairs']} pairs, a median saving of"
        f" {fmt(order[f'w{W}_first'])} s;",
        f"3,584 first in {printed['by_order'][f'w{S}_first']['pairs']},"
        f" {fmt(order[f'w{S}_first'])} s.",
        f"a median over the twelve: {fmt(wt.median(at_window(W, 'first_token_sec')))} at 4,096"
        f" against {fmt(wt.median(at_window(S, 'first_token_sec')))} at 3,584.",
        f"It came earlier at 3,584 in {sum(1 for value in first if value > 0)} of {count} pairs, by"
        f" a median {fmt(wt.median(first))} s ({fmt_range(first)}).",
        f"below 4,096 on {got['small_faster']} of {count} pairs, p {got['sign_p']:.6f}",
        f"The median saving is {fmt(got['median_prompt_saving_sec'])} s, the median ratio"
        f" {fmt(got['median_prompt_ratio'])}.",
        f"the answer's prompt a median {fmt(wt.median(less('answer_prompt_sec')))} s and the"
        f" self-evaluation's {fmt(wt.median(less('eval_prompt_sec')))} s.",
        f"its ratio of prompt tokens, a median {fmt(wt.median([tokens_ratio(p) for p in readable]))}.",
        f"The answer's prompt was read at {fmt(rate[f'w{S}'])} tokens a second at 3,584 against"
        f" {fmt(rate[f'w{W}'])} at 4,096.",
        f"answer's prompt was read at a median {fmt(rate[f'w{W}'])} tokens a second at 4,096",
        f"by a median {fmt(wt.median(first))} s (mine, above)",
        f"a median {fmt(printed['whole']['median_saving_sec'])} s and"
        f" {fmt(printed['result']['median_saving_sec'])} s.",
        f"{tok(generated[f'w{S}'])} generated tokens a median against {tok(generated[f'w{W}'])}.",
        f"`/api/ps`'s size was {mib(today - small)} MiB smaller at 3,584",
        f"{fmt(order[f'w{W}_first'])} s with 4,096 first, {fmt(order[f'w{S}_first'])} s with 3,584"
        " first.",
        f"scored `{moved['case_id']}` {moved[f'w{S}_score']} against {moved[f'w{W}_score']} at"
        f" 4,096 and sent it to a person.",
        f"kept their route, and all {sum(printed['scores_parsed'].values())} scores parsed.",
        f"block: {rows[0]['swap_before_mb']:,} MB before the first, {rows[-1]['swap_after_mb']:,} MB"
        " after the last,",
    ]


def test_the_capsule_states_its_limits_and_the_records_numbers_each_on_one_line() -> None:
    text = CAPSULE.read_text(encoding="utf-8")
    assert not re.search("[Ѐ-ӿ]", text)
    lines = text.splitlines()
    built = computed_phrases()
    assert len(built) == 33
    for phrase in (*PHRASES, *built):
        assert any(phrase in line for line in lines), phrase
    # the one route that moved went to a person at 3,584, and it is the moved pair's
    (moved,) = [pair for pair in readable if pair[f"w{W}_route"] != pair[f"w{S}_route"]]
    assert (moved[f"w{W}_route"], moved[f"w{S}_route"]) == ("auto", "human")


def test_the_spec_names_this_record_and_its_forecasts_as_the_capsule_quotes_them() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    assert "registered before the first request" in spec
    assert "[the record](../evidence/stage4-step4b-record.md)" in spec
    flat = " ".join(spec.split())
    for said in (*FORECAST, GOLD):
        assert said in flat, said
