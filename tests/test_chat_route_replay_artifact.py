"""Check the published replay of the web chat's routing rule on Julia's production model.

The web chat routes an answer ``auto`` when the generator's own score of it is at least
``QUALITY_THRESHOLD`` (80) and ``human`` below it. On 2026-10-16 (19:12-20:12 UTC) the stand
`/Users/julia/RAG_new_chat_7a99c45` - `git archive 7a99c45`, where Qwen3-4B-Instruct-2507 is the
code default - sent that self-evaluation, through the repository's own code and the provider
runtime built from a clean ``Settings()``, for the 100 answers the 4B wrote in the generator
screening, which the judge graded (``reports/generator-screen/86df582``). ``tools/plan.json``
named the inputs, the forecast, the stop rule and the reading before the first request
(``da134d4``). Nothing here needs a model, the network or the Mac: the test pins the bytes,
then derives every published number from the record and the judge's verdicts and finds it in
the evidence row.
"""

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from scripts.generator_answer_judge import classify

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "reports/chat-route-replay/7a99c45"
JUDGE = ROOT / "reports/generator-screen/86df582/judge-100"
# sha256, size and path of every published file, LF line endings (.gitattributes).
PINS = """
672c8c89a6efa24a813a189b2ad7f342d91a15fee474fb2f2d626d537a3a4a83 35842 replay.jsonl
c6e3c96244c754f8a2fd82cb3ded42660cb2fef3edce6c4699545e7d0b8a780e 630 summary.json
be201f7c133d16728b8c43778c3e75fd2a9aa10b1e2ad4cd486057a727d64495 3807 tools/make_replay_plan.py
147d03d69e4e0347adab08fa092bc503a212d41a2c4358a47acbf6c213633c7f 6917 tools/plan.json
a9631ae9a10d96a0dde609b5b63c2b42fa1c9b4d0e63a6f967a7a0c7d0e71e6e 2756 tools/replay_summary.py
8be87dc30a12e714e4a5090743bcc5a69553b7e3214a9302e8f927d6615b6421 7394 tools/route_replay.py
"""
FILES = {
    name: (sha256, int(size)) for sha256, size, name in map(str.split, PINS.strip().splitlines())
}
CODE_SHA = "7a99c452491c141a6a0cab13303bcdf4d4055b41"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
GENERATOR = "qwen3-4b-instruct"


def _rows() -> list[dict]:
    text = (RECORD / "replay.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


def _judge_classes() -> dict[str, str]:
    plan = json.loads((JUDGE / "plan.json").read_text(encoding="utf-8"))
    items = {item["item_id"]: item for item in plan["items"]}
    classes = {}
    for line in (JUDGE / "verdicts.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        item = items.get(row["item_id"])
        if item is None or "retest_of" in item or item["generator"] != GENERATOR:
            continue
        if row.get("status") == "valid":
            classes[item["case_id"]] = classify(row["verdict"])
    return classes


def _wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def test_published_files_are_pinned():
    found = {
        path.relative_to(RECORD).as_posix(): path
        for path in RECORD.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    assert set(found) == set(FILES)
    for name, (sha256, size) in FILES.items():
        data = found[name].read_bytes()
        assert (hashlib.sha256(data).hexdigest(), len(data)) == (sha256, size), name


def test_the_plan_was_named_before_the_first_request_and_the_default_was_served():
    plan = json.loads((RECORD / "tools/plan.json").read_text(encoding="utf-8"))
    rows = _rows()
    start, end = rows[0], rows[-1]
    assert (plan["code_sha"], plan["model"]) == (CODE_SHA, MODEL)
    assert start["kind"] == "start" and end["kind"] == "end"
    assert plan["named"] < start["at"]
    assert start["served"] == {
        "ollama_model_name": MODEL,
        "runtime_profile": "local-first",
        "eval_model": MODEL,
        "eval_provider": "ollama",
        "quality_threshold": 80,
        "ollama_context_window": 4096,
        "provider_registry_path": "/Users/julia/RAG_new_chat_7a99c45/config/providers.yml",
    }
    cases = [row for row in rows if row["kind"] == "case"]
    assert [row["case_id"] for row in cases] == plan["case_order"]
    assert not [row for row in rows if row["kind"] == "stop"]
    # Julia's stop rule: no case ran past 3x its forecast.
    for position, row in enumerate(cases):
        forecast = plan["forecast_first_sec"] if position == 0 else plan["forecast_sec"]
        assert row["forecast_sec"] == forecast
        assert row["elapsed_sec"] < 3 * forecast, row["case_id"]


def test_every_route_follows_the_chats_rule():
    for row in _rows():
        if row["kind"] != "case":
            continue
        assert row["error"] is None and row["quality_source"] == "llm", row["case_id"]
        assert row["quality"] == int(row["raw"].strip()), row["case_id"]
        assert row["route"] == ("auto" if row["quality"] >= 80 else "human"), row["case_id"]
        assert row["docs_sent"] == 5


def test_published_numbers_derive_from_the_record_and_the_judge():
    classes = _judge_classes()
    assert Counter(classes.values()) == {"good": 67, "partial_ok": 21, "bad": 12}
    cases = {row["case_id"]: row for row in _rows() if row["kind"] == "case"}
    assert set(cases) == set(classes)
    routes = Counter(row["route"] for row in cases.values())
    cross = Counter((classes[case_id], row["route"]) for case_id, row in cases.items())
    scores = Counter(row["quality"] for row in cases.values())
    assert routes == {"auto": 98, "human": 2}
    assert _wilson(2, 100) == [0.0055, 0.07]
    assert cross == {
        ("good", "auto"): 67,
        ("partial_ok", "auto"): 21,
        ("bad", "auto"): 10,
        ("bad", "human"): 2,
    }
    assert scores == {100: 89, 95: 7, 90: 2, 60: 1, 20: 1}
    summary = json.loads((RECORD / "summary.json").read_text(encoding="utf-8"))
    assert summary["routes"] == dict(routes)
    assert summary["human_wilson95"] == _wilson(2, 100)
    assert (summary["bad_caught"], summary["bad_passed_auto"], summary["good_sent_human"]) == (
        2,
        10,
        0,
    )
    # Both answers sent to a person are declines where the context held the answer.
    verdicts = {}
    plan = json.loads((JUDGE / "plan.json").read_text(encoding="utf-8"))
    items = {item["item_id"]: item for item in plan["items"]}
    for line in (JUDGE / "verdicts.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        item = items.get(row["item_id"])
        if item and "retest_of" not in item and item["generator"] == GENERATOR:
            if row.get("status") == "valid":
                verdicts[item["case_id"]] = row["verdict"]
    human = [case_id for case_id, row in cases.items() if row["route"] == "human"]
    assert [
        (verdicts[c]["answers_question"], verdicts[c]["context_has_answer"]) for c in human
    ] == [("declined", True), ("declined", True)]

    row = next(
        line
        for line in (ROOT / "EVIDENCE_INDEX.md").read_text(encoding="utf-8").splitlines()
        if "reports/chat-route-replay/7a99c45" in line
    )
    for phrase in (
        "`human` 2 of 100",
        "0.6–7.0 %",
        "10 of the judge's 12 bad answers",
        "no good answer",
        "100 in 89",
        "`7a99c45`",
        "`da134d4`",
    ):
        assert phrase in row, phrase
