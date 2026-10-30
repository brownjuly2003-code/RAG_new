"""Stage 4, item 5a's n-gram decoding — the record read again with the committed tool; its
gates, its inputs, its fidelity and its privacy (docs/specs/stage4-step5a-ngram-decoding.md,
«Records»). Every table row of docs/evidence/stage4-step5a-ngram-record.md is built from the
record, and so is every number of its prose that a test below pins."""

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
TOOL = ROOT / "reports" / "stage4-step5a-ngram" / "tools" / "ngram_decode.py"
RECORDS = ROOT / "reports" / "stage4-step5a-ngram" / "5558ca8"
SPEC = ROOT / "docs" / "specs" / "stage4-step5a-ngram-decoding.md"
CAPSULE = ROOT / "docs" / "evidence" / "stage4-step5a-ngram-record.md"
CASES_FILE = ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
CODE_SHA = "5558ca84aa17f46eebe5bb7e03266895db1c2ab3"
# the files as copied from the Mac, by their SHA-256, which the Mac's copies matched
FILES = {
    "record.json": "9d0009afa4d36595c45c129dedde1f92ae9510eec4692878e130c2adaffd6ea8",
    "rows.jsonl": "9edcb7326d0590fb416b1f868e631b0af73e5e1e9118d30981b70259387bb233",
}


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("ngram_decode_record", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["ngram_decode_record"] = module
    spec.loader.exec_module(module)
    return module


ng = _load()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


record = _json(RECORDS / "record.json")
rows = _lines(RECORDS / "rows.jsonl")
readings = record["readings"]
speed = readings["speed"]
readable = [row for row in rows if not row["disturbed"]]
BASE, NGRAM = ng.REPEATS["base"], ng.REPEATS["ngram"]
DIRECT = (*BASE, *NGRAM)


def fmt(value: float) -> str:
    return f"{value:,.3f}".replace("-", "−")


def n(value: int) -> str:
    return f"{value:,}"


def ms_a_token(row: dict[str, Any], arm: tuple[str, ...]) -> float:
    """An arm's mean of milliseconds a written token over its two blocks, the tool's speed's."""
    return statistics.mean(ng.per_token(row["blocks"][block]) for block in arm)


def writing_sec(row: dict[str, Any], arm: tuple[str, ...]) -> float:
    return statistics.mean(row["blocks"][block]["predicted_ms"] for block in arm) / 1000


def saved(row: dict[str, Any]) -> float:
    return writing_sec(row, BASE) - writing_sec(row, NGRAM)


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value)


def span() -> tuple[datetime, datetime]:
    blocks = record["blocks"]
    return utc(blocks["0"]["started_at"]), utc(blocks[str(max(map(int, blocks)))]["ended_at"])


def clean_in(block: str) -> list[dict[str, Any]]:
    return [row for row in rows if not row["blocks"][block]["disturbed"]]


def first_and_third() -> tuple[int, int]:
    """Mine, no rule of the spec: ngram's block 3 against base's block 1, the two blocks nearly
    untouched, on the questions undisturbed in both: (slower in block 3, compared)."""
    both = [row for row in clean_in("1") if not row["blocks"]["3"]["disturbed"]]
    slower = sum(
        1 for row in both if ng.per_token(row["blocks"]["3"]) > ng.per_token(row["blocks"]["1"])
    )
    return slower, len(both)


def draft_floor(row: dict[str, Any]) -> float:
    """Mine: milliseconds a drafted token at least, where ngram wrote the same answer slower —
    its writing's extra seconds over the tokens it drafted, the kept ones' saving not added."""
    (drafted,) = {row["blocks"][block]["draft_n"] for block in NGRAM}
    return -saved(row) * 1000 / drafted


def floored() -> list[dict[str, Any]]:
    """The readable questions with the same answer in all four blocks and two drafts' worth of
    tokens drafted, 96 or more."""
    return [
        row
        for row in readable
        if row["first_difference"] == {} and row["blocks"]["2"]["draft_n"] >= 96
    ]


def test_the_files_are_the_bytes_copied_from_the_mac() -> None:
    assert sorted(path.name for path in RECORDS.iterdir()) == sorted(FILES)
    for name, digest in FILES.items():
        data = (RECORDS / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), b"\r" in data) == (digest, False), name


def test_the_record_was_read_by_the_tool_the_spec_registers() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    listed = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    tool = TOOL.relative_to(ROOT).as_posix()
    assert sorted(listed) == [tool, "tests/test_stage4_step5a_ngram_tools.py"]
    for path, digest in listed.items():
        assert sha(ROOT / path) == digest, path
    assert (record["schema"], record["spec"]) == (ng.SCHEMA, ng.SPEC)
    assert (ng.SCHEMA, ng.SPEC) == ("stage4-step5a-ngram/v1", SPEC.relative_to(ROOT).as_posix())
    # the series ran the registering commit's worktree, and its tool read the record
    assert f"in `{CODE_SHA[:7]}`" in spec
    assert record["measured_at_head"] == CODE_SHA
    assert record["tool_sha256"] == listed[tool]


def test_the_readings_are_read_again_from_the_rows() -> None:
    assert [(row["position"], row["case_id"]) for row in rows] == list(enumerate(ng.CASES, start=1))
    cases = [json.loads(line)["case_id"] for line in CASES_FILE.read_text("utf-8").splitlines()]
    assert cases[: len(ng.CASES)] == list(ng.CASES) and len(ng.CASES) == 13
    for row in rows:
        assert sorted(row["blocks"]) == sorted(DIRECT), row["case_id"]
        assert row["disturbed"] == any(e["disturbed"] for e in row["blocks"].values())
        parted = {
            f"{a}-{b}"
            for a, b in (*ng.REPEATS.values(), *ng.PAIRS)
            if row["blocks"][a]["text_sha256"] != row["blocks"][b]["text_sha256"]
        }
        assert set(row["first_difference"]) == parted, row["case_id"]
    assert ng.speed(rows) == speed
    assert ng.equality(rows) == readings["equality"]
    assert ng.acceptance(rows) == readings["acceptance"]
    assert ng.outcome(readings) == record["outcome"] == ng.NOT_EVIDENCE


def test_every_block_passed_its_gate_at_its_first_attempt() -> None:
    blocks = record["blocks"]
    assert {int(key): block["arm"] for key, block in blocks.items()} == ng.SCHEDULE
    assert record["attempts"] == {str(key): 1 for key in ng.SCHEDULE}
    assert record["rejected"] == []
    assert [blocks[str(key)]["calls"] for key in ng.SCHEDULE] == [4, 14, 14, 14, 14]
    assert all(block["sample_errors"] == 0 for block in blocks.values())
    # the four direct blocks ran one server's settings but speculation's type
    settings = {key: dict(blocks[key]["settings"]) for key in DIRECT}
    types = {key: value.pop("speculative.types") for key, value in settings.items()}
    assert types == {"1": "none", "4": "none", "2": "none,ngram-simple", "3": "none,ngram-simple"}
    assert all(value == settings["1"] for value in settings.values())
    assert (settings["1"]["seed"], settings["1"]["n_predict"]) == (ng.SEED, 1024)
    for row in rows:
        for block, entry in row["blocks"].items():
            where = (row["case_id"], block)
            assert entry["stop_type"] in ng.STOP_TYPES, where
            assert entry["tokens_evaluated"] == entry["cache_n"] + entry["prompt_n"], where
            assert entry["predicted_n"] > 0 and entry["chars"] > 0, where
            if block in BASE:
                assert (entry["draft_n"], entry["draft_n_accepted"]) == (0, 0), where
            else:
                assert entry["draft_n"] > entry["draft_n_accepted"] >= 0, where


def test_the_fidelity_holds_on_block_0s_calls() -> None:
    fidelity = readings["fidelity"]
    assert fidelity["reading"] == "holds"
    calls = fidelity["calls"]
    assert [call["case_id"] for call in calls] == ["warm-up", *ng.CASES[: ng.FIDELITY]]
    for call in calls:
        assert call["same_text"] is True, call["case_id"]
        assert call["prompt_tokens"][0] == call["prompt_tokens"][1], call["case_id"]
        assert call["answer_tokens"][0] == call["answer_tokens"][1], call["case_id"]
    # the three questions' Ollama counters, kept in their rows, are block 1's own
    for row, call in zip(rows[: ng.FIDELITY], calls[1:], strict=True):
        zero, one = row["ollama"], row["blocks"]["1"]
        assert zero["text_sha256"] == one["text_sha256"], row["case_id"]
        assert zero["done_reason"] == "stop" and one["stop_type"] == "eos", row["case_id"]
        assert zero["prompt_eval_count"] == one["cache_n"] + one["prompt_n"]
        assert zero["eval_count"] == one["predicted_n"]
        assert call["prompt_tokens"] == [zero["prompt_eval_count"]] * 2
        assert call["answer_tokens"] == [zero["eval_count"]] * 2


def test_the_inputs_are_step_4bs_and_the_runner_ollamas() -> None:
    inputs = record["inputs"]
    assert inputs["step4b_inputs_sha256"] == ng.STEP4B_INPUTS_SHA256
    assert (inputs["model"], inputs["ollama_version"]) == (
        "qwen3:4b-instruct-2507-q4_K_M",
        ng.OLLAMA_VERSION,
    )
    assert ng.OLLAMA_VERSION == "0.33.2" and inputs["digest"].startswith("0edcdef3")
    assert [call["case_id"] for call in inputs["calls"]] == ["warm-up", *ng.CASES]
    options = inputs["options"]
    assert {key: options[key] for key in ng.REQUEST} == ng.REQUEST
    assert (options["num_ctx"], options["seed"], options["temperature"]) == (4096, 1030, 0.2)
    show = inputs["show"]
    assert (show["renderer"], show["parser"]) == (None, None)
    runner = inputs["runner"]
    assert runner["binary"].endswith("/llama-server")
    assert runner["version"].startswith("version: ")
    assert "--spec-type" not in runner["args"]
    assert sorted(runner["env"]) == ["DYLD_LIBRARY_PATH", "LLAMA_MEDIA_MARKER"]
    assert inputs["gguf"]["path"] in runner["args"]


HEX = re.compile(r"[0-9a-f]{64}")


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


def test_the_record_holds_no_question_prompt_or_answer() -> None:
    questions = [json.loads(line)["query"] for line in CASES_FILE.read_text("utf-8").splitlines()]
    for name in FILES:
        text = (RECORDS / name).read_text(encoding="utf-8")
        # the questions, the warm-up and the answers are Russian; nothing Cyrillic is kept
        assert not re.search("[Ѐ-ӿ]", text), name
        assert not [q for q in questions[: len(ng.CASES)] if q in text], name
    # the Mac's paths only where the spec keeps them: the runner and the GGUF
    outside = {**record, "inputs": {**record["inputs"], "runner": None, "gguf": None}}
    assert "/Users/" not in json.dumps(outside)
    # a row holds numbers, the question's id, SHA-256 strings and the stop's type
    for string, key in strings(rows):
        known = key or string in ng.CASES or HEX.fullmatch(string) or string in ng.STOP_TYPES
        assert known or string in ng.DONE_REASONS, string


def test_the_readings_against_the_forecast() -> None:
    assert (speed["questions"], speed["readable"], speed["reading"]) == (13, 7, ng.NOT_EVIDENCE)
    assert ng.MIN_READABLE == 10 and speed["readable"] < ng.MIN_READABLE
    assert (speed["faster"], speed["slower"], speed["p"]) == (1, 6, 0.125)
    assert (speed["ratio_median"], speed["saved_decode_sec_median"]) == (0.751, -3.384)
    assert readings["equality"]["reading"] == "differ"
    assert readings["equality"]["repeat"] == {"base": 13, "ngram": 13}
    assert set(readings["equality"]["pairs"].values()) == {9}
    # the spec's outcome: not faster, or NOT_EVIDENCE with too few readable — the lever closes
    assert record["outcome"] == ng.NOT_EVIDENCE
    # the forecast: faster on 11 or 12 of 13, byte-equal, kept over drafted ≈ 0.2
    assert speed["faster"] < 11
    assert {value["rate"] for value in readings["acceptance"].values()} == {0.2392}
    # mine, no rule of the spec: block 3 against block 1, slower on every question both kept
    assert first_and_third() == (12, 12)
    assert [row["case_id"] for row in floored()] == [
        "aircargo-leave-compensation",
        "aircargo-matliab-disputed",
    ]


def readings_rows() -> list[str]:
    equality = readings["equality"]
    calls = readings["fidelity"]["calls"]
    held = sum(
        1
        for c in calls
        if c["same_text"] and len(set(c["prompt_tokens"])) == len(set(c["answer_tokens"])) == 1
    )
    ratios = [ms_a_token(row, BASE) / ms_a_token(row, NGRAM) for row in readable]
    savings = [saved(row) for row in readable]
    (pairs,) = set(equality["pairs"].values())
    return [
        "| The fidelity: block 0's calls through Ollama against block 1's first four — the same"
        " text, prompt tokens and answer tokens"
        f" | **{readings['fidelity']['reading']}** | {held} of {len(calls)} calls | holds |",
        "| The speed: ngram's milliseconds a written token below base's on more readable"
        " questions, the exact two-sided sign test's p below 0.05, at least 10 readable"
        f" | **`{speed['reading']}`** | {speed['readable']} readable of {speed['questions']};"
        f" ngram below on {speed['faster']}, above on {speed['slower']}; p {speed['p']}"
        " | faster, on 11 or 12 of the thirteen |",
        "| The number: the median ratio, base's milliseconds a token over ngram's"
        f" | **{fmt(speed['ratio_median'])}** | from {fmt(min(ratios))} to {fmt(max(ratios))}"
        " by readable question | ≈ 1.1 |",
        "| The number: the median writing saved, base's seconds less ngram's"
        f" | **{fmt(speed['saved_decode_sec_median'])} s** | from {fmt(min(savings))} to"
        f" {fmt(max(savings))} s by readable question | ≈ 2.2 s a question |",
        "| The answers' bytes: base repeats itself on all thirteen, then each base–ngram pair of"
        f" blocks gives the same text on all thirteen | **{equality['reading']}**"
        f" | base {equality['repeat']['base']} of {equality['questions']}, ngram"
        f" {equality['repeat']['ngram']} of {equality['questions']}; each pair {pairs} of"
        f" {equality['questions']} | byte-equal |",
        f"| The outcome | **`{record['outcome']}`**: the lever closes | too few readable"
        " | faster and byte-equal |",
    ]


def question_rows() -> list[str]:
    built = []
    for row in rows:
        blocks = row["blocks"]
        disturbed = ", ".join(b for b in sorted(blocks) if blocks[b]["disturbed"]) or "none"
        (written_b,) = {blocks[b]["predicted_n"] for b in BASE}
        (written_g,) = {blocks[b]["predicted_n"] for b in NGRAM}
        (drafts,) = {(blocks[b]["draft_n"], blocks[b]["draft_n_accepted"]) for b in NGRAM}
        parted = row["first_difference"].get("1-2")
        same = "yes" if parted is None else f"no, from character {n(parted)}"
        built.append(
            f"| {row['position']} | `{row['case_id']}` | {disturbed}"
            f" | {fmt(ms_a_token(row, BASE))} / {fmt(ms_a_token(row, NGRAM))}"
            f" | {fmt(ms_a_token(row, BASE) / ms_a_token(row, NGRAM))} | {fmt(saved(row))}"
            f" | {n(written_b)} / {n(written_g)} | {n(drafts[0])} / {n(drafts[1])} | {same} |"
        )
    return built


def got(block: dict[str, Any], name: str, show: Any = fmt) -> str:
    """A block's value, or a dash where its arm has none: block 0 loads no server of its own."""
    return show(block[name]) if name in block else "—"


def mib(value: float) -> str:
    return f"{value:,.1f}"


def block_rows() -> list[str]:
    return [
        f"| {key} | {block['arm']}"
        f" | {utc(block['started_at']):%H:%M:%S}–{utc(block['ended_at']):%H:%M:%S}"
        f" | {block['calls']} | {fmt(block['warm_up_sec'])} | {got(block, 'load_sec')}"
        f" | {got(block, 'rss_after_load_mib', mib)}"
        f" | {got(block, 'rss_max_after_calls_mib', mib)}"
        f" | {' / '.join(f'{value:,}' for value in block['swap_mb'])}"
        f" | {block['others_cpu_max']} | {block['disturbed']} |"
        for key, block in record["blocks"].items()
    ]


def acceptance_rows() -> list[str]:
    return [
        f"| {key} | {n(value['draft_n'])} | {n(value['draft_n_accepted'])}"
        f" | {n(value['draft_n'] - value['draft_n_accepted'])} | {value['rate']} |"
        for key, value in readings["acceptance"].items()
    ]


def printed_rows() -> list[str]:
    def row(name: str, base: float, ngram: float) -> str:
        return f"| {name} | {fmt(base)} | {fmt(ngram)} |"

    def median(values: list[float]) -> float:
        return float(statistics.median(values))

    return [
        row(
            "Milliseconds a written token, a median",
            speed["base_ms_per_token_median"],
            speed["ngram_ms_per_token_median"],
        ),
        row(
            "The call's wall seconds, a median",
            speed["base_wall_sec_median"],
            speed["ngram_wall_sec_median"],
        ),
        row(
            "The prompt's seconds, a median",
            median([statistics.mean(r["blocks"][b]["prompt_ms"] for b in BASE) for r in readable])
            / 1000,
            median([statistics.mean(r["blocks"][b]["prompt_ms"] for b in NGRAM) for r in readable])
            / 1000,
        ),
        row(
            "The first chunk's seconds, a median",
            median([statistics.mean(r["blocks"][b]["first_sec"] for b in BASE) for r in readable]),
            median([statistics.mean(r["blocks"][b]["first_sec"] for b in NGRAM) for r in readable]),
        ),
    ]


# the spec's forecasts, in its words
FORECAST = (
    "the five blocks pass their gates and the fidelity holds",
    "Base repeats itself on all thirteen",
    "`ngram` keeps base's text on all thirteen — **byte-equal**",
    "`ngram` reads **faster**, on 11 or 12 of the thirteen (p 0.022 or 0.003)",
    "kept over drafted ≈ 0.2, so ≈ 1,325 tokens drafted and ≈ 1,060 thrown away",
    "the net: ≈ 26 s, ≈ 2.2 s a question — ≈ 9 % of the 281 s of writing, a ratio ≈ 1.1",
    "≈ 1.5 h of the Mac once it is idle",
)


def forecast_rows() -> list[str]:
    equality = readings["equality"]
    (pairs,) = set(equality["pairs"].values())
    (kept,) = {
        (v["draft_n"], v["draft_n_accepted"], v["rate"]) for v in readings["acceptance"].values()
    }
    start, end = span()
    minutes = round((end - start).total_seconds() / 60)
    measured = (
        "all five passed at their first attempt, no file rejected; the fidelity holds on all"
        f" {len(readings['fidelity']['calls'])} calls",
        f"{equality['repeat']['base']} of {equality['questions']}",
        f"**{equality['reading']}**: each base–ngram pair of blocks the same on {pairs} of"
        f" {equality['questions']}; ngram repeats itself on {equality['repeat']['ngram']} of"
        f" {equality['questions']}",
        f"**`{speed['reading']}`**: {speed['readable']} readable, fewer than {ng.MIN_READABLE};"
        f" on them ngram below on {speed['faster']}, above on {speed['slower']}, p {speed['p']}",
        f"{kept[2]} in each ngram block: {n(kept[0])} drafted, {n(kept[1])} kept,"
        f" {n(kept[0] - kept[1])} thrown away",
        f"a median {fmt(speed['saved_decode_sec_median'])} s and a ratio"
        f" {fmt(speed['ratio_median'])} over the {speed['readable']} readable",
        f"{start:%H:%M:%S}–{end:%H:%M:%S} UTC, {minutes // 60} h {minutes % 60} min, with the"
        " stop after block 1 the spec makes",
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
        readings_rows: 6,
        question_rows: 13,
        block_rows: 5,
        acceptance_rows: 2,
        printed_rows: 4,
        forecast_rows: 7,
        file_rows: 2,
    }
    for build, count in tables.items():
        built = build()
        assert len(built) == count, build.__name__
        for row in built:
            assert row in lines, row


# the capsule's own words for its limits and its reading; each sits on one line of it
PHRASES = (
    "The record holds no question, prompt, answer or document.",
    "the lever closes",
    "(mine, no rule of the spec)",
    "No job of ours ran on the Mac during the series.",
    "Seconds of one call; nothing on quality.",
    "Whether n-gram enters the product was her word; the lever closes before it.",
)


def computed_phrases() -> list[str]:
    start, _ = span()
    inputs = record["inputs"]
    runner, gguf = inputs["runner"], inputs["gguf"]
    blocks = record["blocks"]
    slower, compared = first_and_third()
    order = next(row for row in readable if ms_a_token(row, NGRAM) < ms_a_token(row, BASE))
    late = order["blocks"]["4"]
    early = order["blocks"]["1"]
    floors = [draft_floor(row) for row in floored()]
    disturbed = {key: blocks[key]["disturbed"] for key in ("2", "3", "4")}
    parted = sorted(
        (row["position"], row["first_difference"]["1-2"])
        for row in rows
        if "1-2" in row["first_difference"]
    )
    return [
        f"in `{CODE_SHA[:7]}` before the first request; nothing changed after it.",
        f"The series started at {start:%H:%M} UTC on {start:%Y-%m-%d}.",
        f"code `{record['measured_at_head']}`",
        f"`{runner['binary_sha256'][:8]}…`, `{runner['version'].splitlines()[0]}`",
        f"`{gguf['sha256'][:8]}…`, {n(gguf['bytes'])} bytes",
        f"`{inputs['model']}`, digest `{inputs['digest'][:8]}…`",
        f"step 4b's inputs (`{inputs['step4b_inputs_sha256'][:8]}…`)",
        f"num_predict {n(inputs['options']['num_predict'])}, temperature"
        f" {inputs['options']['temperature']}, top_k {inputs['options']['top_k']}, top_p"
        f" {inputs['options']['top_p']}, seed {inputs['options']['seed']}",
        f"the other {len(blocks['1']['settings']) - 1} settings",
        f"{disturbed['2']} questions in block 2, {disturbed['3']} in block 3 and"
        f" {disturbed['4']} in block 4",
        f"others' CPU at most {blocks['2']['others_cpu_max']} % in block 2 and"
        f" {blocks['4']['others_cpu_max']} % in block 4",
        f"ngram below base on {speed['faster']} of the {speed['readable']} readable questions,"
        f" above on {speed['slower']}",
        f"the median ratio {fmt(speed['ratio_median'])}, a median {fmt(speed['saved_decode_sec_median'])} s",
        f"{fmt(speed['base_ms_per_token_median'])} ms a written token against"
        f" {fmt(speed['ngram_ms_per_token_median'])}",
        f"slower in block 3 than in block 1 on {slower} of the {compared} questions",
        f"`{order['case_id']}`",
        f"{fmt(ng.per_token(late))} ms a token and a prompt of {fmt(late['prompt_ms'] / 1000)} s in"
        f" block 4 against {fmt(ng.per_token(early))} and {fmt(early['prompt_ms'] / 1000)} s in"
        " block 1",
        f"{fmt(-saved(floored()[0]))} and {fmt(-saved(floored()[1]))} s slower",
        f"at least {min(floors):.0f}–{max(floors):.0f} ms a drafted token",
        "the answers part at characters "
        + ", ".join(f"{n(at)} (position {position})" for position, at in parted),
    ]


def test_the_capsule_states_its_limits_and_the_records_numbers_each_on_one_line() -> None:
    text = CAPSULE.read_text(encoding="utf-8")
    assert not re.search("[Ѐ-ӿ]", text)
    lines = text.splitlines()
    built = computed_phrases()
    assert len(built) == 20
    for phrase in (*PHRASES, *built):
        assert any(phrase in line for line in lines), phrase


def test_the_spec_names_this_record_and_its_forecasts_as_the_capsule_quotes_them() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    assert "registered before the first request" in spec
    assert "[the record](../evidence/stage4-step5a-ngram-record.md)" in spec
    flat = " ".join(spec.split())
    for said in FORECAST:
        assert said in flat, said
    assert (
        "not faster: `not faster`, or `NOT_EVIDENCE` with too few readable — the lever closes"
        in flat
    )
