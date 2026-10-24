"""reports/answer-prompt-v4/tools: the answers' marks, the judge's bridge and the record of V4
against V3, paired.

docs/specs/answer-prompt-v4.md, «How it is read». Toy runs, plans and records of the stage-2
schemas - ids, classes and counts only - stand in for the private answers and plans and the
committed records.
"""

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import math
import re
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from agent import prompts
from agent.prompts import build_qa_prompt
from llm.providers.base import flatten_messages
from scripts import chat_answer_judge as judge

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports" / "answer-prompt-v4" / "tools"
CODE = "5e308fe48cca0955c3007057a574a425f71e2a6a"
STAND = "1234567890abcdef1234567890abcdef12345678"
STAND_DIR = f"reports/answer-prompt-v4/{STAND[:7]}"
# QA_PROMPT_V3's text at stage 2's stand: git show 5e308fe:agent/prompts.py, "qa".
V3_SHA256 = "1fc83b5543492c5f10b34f02b6bee47fd9474a7529ee9a7f2a22b374cc09f107"
# QA_PROMPT_V4's text as the spec registered it: agent/prompts.py, "qa", at the V4 stand.
V4_SHA256 = "9276aff5a3a44bc9ff1adb7a52b7b11a06e8f4b0f7fe79a5dc6b20262db3a515"
# The judge's route as stage 2's records hold it, the toy's own.
ROUTE = {
    "model": "claude-opus-5-5",
    "effort": "max",
    "tools": "none",
    "session": "safe mode",
    "system_prompt_sha256": "toy",
}
DOCS = [
    {"page_content": "Storage costs ten a day.", "metadata": {"source": "fees.md"}},
    {"page_content": "Claims are filed within 14 days.", "metadata": {"source": "claims.md"}},
]
KEYS = ("aircargo", "wixqa", "conditionalqa")
# When each side's toy answers ran, and when the stand's environment was read around V4's.
LAUNCH = {
    "v3": ("2026-10-21T00:00:00+00:00", "2026-10-21T08:00:00+00:00"),
    "v4": ("2026-10-25T00:00:00+00:00", "2026-10-25T08:00:00+00:00"),
}
TAKEN = ("2026-10-24T23:00:00+00:00", "2026-10-25T09:00:00+00:00")
# Each key's ten questions: V3's class and V4's; None where V4's verdict is missing.
V3_CLASSES = {
    "aircargo": ["good"] * 6 + ["partial_ok", "bad", "good", "bad"],
    "wixqa": ["bad"] * 6 + ["good", "good", "good", "partial_ok"],
    "conditionalqa": "bad bad bad good partial_ok bad good bad bad good".split(),
}
V4_CLASSES = {
    "aircargo": ["good"] * 8 + ["bad", "bad"],
    "wixqa": ["good"] * 3 + ["partial_ok", "bad", "bad", "good", "good", "bad", "partial_ok"],
    "conditionalqa": [*"good good bad good bad partial_ok good".split(), None, "good", "good"],
}
# Stage 2's clusters of the external bases; both hold a cluster 0, and they stay apart.
CLUSTERS = {
    "wixqa": [0, 0, 1, 2, 2, 2, 3, 4, 5, 6],
    "conditionalqa": [0, 0, 1, 1, 2, 3, 4, 5, 6, 7],
}
NOT_ANSWERABLE = {"c8", "c9"}
# (case, side) -> (answers_question, context_has_answer) where it is not the class's own.
VERDICTS = {
    ("w0", "v3"): ("declined", True),
    ("w1", "v3"): ("declined", True),
    ("a7", "v3"): ("full", False),  # V4's context holds what V3's did not
    ("c0", "v3"): ("declined", True),
    ("c0", "v4"): ("declined", False),  # bad to good by a decline: V4's context lost the answer
    ("c7", "v3"): ("declined", True),  # its pair is broken: V4's verdict is missing
    ("c8", "v3"): ("full", False),
    ("c8", "v4"): ("declined", False),
    ("c9", "v3"): ("declined", False),
    ("c9", "v4"): ("declined", False),
}
HUMAN = {
    ("aircargo", "v3"): {"a7"},
    ("wixqa", "v3"): {"w0", "w1", "w4"},
    ("wixqa", "v4"): {"w4", "w8"},
    ("conditionalqa", "v3"): {"c0", "c8"},
    ("conditionalqa", "v4"): {"c4"},
}
# M2 of each question, V3's and V4's: the judge's reference, or right or wrong by a decline.
M2 = {
    "wixqa": (
        "declined declined disagrees partial disagrees agrees agrees agrees agrees partial".split(),
        "agrees agrees agrees partial disagrees agrees agrees agrees disagrees partial".split(),
    ),
    "conditionalqa": (
        "declined disagrees disagrees agrees partial disagrees agrees declined wrong right".split(),
        ["agrees", "agrees", "disagrees", "agrees", "disagrees", "partial", "agrees", None]
        + ["right", "right"],
    ),
}
# (key, side) -> the answers with the placeholder, and those with the referral.
MARKS = {
    ("aircargo", "v3"): (set(), {"a7"}),
    ("wixqa", "v3"): ({"w2", "w3"}, {"w0", "w1", "w2"}),
    ("conditionalqa", "v3"): ({"c5"}, {"c0", "c7"}),
}


@pytest.fixture(scope="module")
def tools() -> Iterator[dict[str, Any]]:
    """The tools, loaded from their files; the sys.path entries they add are taken back."""
    saved = list(sys.path)
    loaded = {}
    for name in ("answer_marks", "bridge_plan", "v4_record"):
        spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
        assert spec and spec.loader
        loaded[name] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded[name])
    yield loaded
    sys.path[:] = saved


@pytest.fixture()
def marks(tools: dict[str, Any]) -> Any:
    return tools["answer_marks"]


@pytest.fixture()
def record(tools: dict[str, Any]) -> Any:
    return tools["v4_record"]


def _prompt(monkeypatch: pytest.MonkeyPatch, template: str, question: str) -> str:
    """The stream prompt of a question over DOCS under an answer template."""
    with monkeypatch.context() as patch:
        patch.setitem(prompts.DEPLOYED_PROMPT_OVERRIDES, "qa", template)
        return flatten_messages([{"role": "user", "content": build_qa_prompt(question, DOCS)}])


def _run(
    monkeypatch: pytest.MonkeyPatch, template: str, folder: Path, cases: list[tuple[str, str, str]]
) -> Path:
    """A stand's answers run under an answer template: one stream prompt per case, saved as
    live_api.py saves it."""
    (folder / "prompts").mkdir(parents=True)
    (folder / "cases").mkdir()
    for index, (case_id, question, answer) in enumerate(cases, start=1):
        (folder / "prompts" / f"{2 * index - 1:03d}-stream.txt").write_text(
            _prompt(monkeypatch, template, question), "utf-8"
        )
        (folder / "prompts" / f"{2 * index:03d}-generate.txt").write_text("self-eval", "utf-8")
        row = {
            "case_id": case_id,
            "question": question,
            "answer": answer,
            "events": [{"type": "result", "answer": answer, "route": "auto"}],
        }
        (folder / "cases" / f"{index:02d}-{case_id}.json").write_text(json.dumps(row), "utf-8")
    return folder


def test_the_templates_are_the_stands_and_v4_adds_its_difference(
    record: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert hashlib.sha256(record.V3_TEMPLATE.encode("utf-8")).hexdigest() == V3_SHA256
    assert hashlib.sha256(record.V4_TEMPLATE.encode("utf-8")).hexdigest() == V4_SHA256
    # The spec's numbers: the template grows by 249 characters, 891 to 1,140.
    sizes = (len(record.V3_TEMPLATE), len(record.V4_TEMPLATE), record.TEMPLATE_DELTA)
    assert sizes == (891, 1140, 249)
    v3 = _prompt(monkeypatch, record.V3_TEMPLATE, "Fee?")
    v4 = _prompt(monkeypatch, record.V4_TEMPLATE, "Fee?")

    assert (judge.prompt_id(v3), judge.prompt_id(v4)) == ("QA_PROMPT_V3", "QA_PROMPT_V4")
    assert judge.read_prompt(v3) == judge.read_prompt(v4)
    assert len(v4) - len(v3) == record.TEMPLATE_DELTA  # the same context, the template apart
    # While agent/prompts.py holds V4, it holds this text; a later prompt leaves the record alone.
    if prompts.PROMPT_REGISTRY["qa"]["prompt_id"] == "QA_PROMPT_V4":
        assert prompts.PROMPT_REGISTRY["qa"]["text"] == record.V4_TEMPLATE


def test_the_marks_are_ids_and_booleans_of_one_prompts_answers(
    marks: Any, record: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    first = _run(
        monkeypatch,
        record.V3_TEMPLATE,
        tmp_path / "b01",
        [
            ("q1", "How much is storage?", "Ten a day [N]. Ask a support specialist for more."),
            ("q2", "How do I file a claim?", "Within 14 days [1]."),
            ("warmup-1", "Hello?", "Hi [N], a specialist will help."),
        ],
    )
    second = _run(
        monkeypatch,
        record.V3_TEMPLATE,
        tmp_path / "b02",
        [
            ("q3", "Сколько стоит хранение?", "Обратитесь к Специалисту поддержки."),
            ("q4", "Can I pay later?", ""),
        ],
    )
    out = tmp_path / "v3-toy.marks.jsonl"

    assert marks.main([str(out), "--run", f"b02={second}", "--run", f"b01={first}"]) == 0

    def row(run: str, case_id: str, placeholder: bool, referral: bool) -> dict:
        return {
            "run": run,
            "case_id": case_id,
            "prompt_id": "QA_PROMPT_V3",
            "placeholder": placeholder,
            "referral": referral,
        }

    assert [json.loads(line) for line in out.read_text("utf-8").splitlines()] == [
        row("b01", "q1", True, True),
        row("b01", "q2", False, False),  # [1] is a citation, not the placeholder
        row("b02", "q3", False, True),  # V3's noun in the question's language
        row("b02", "q4", False, False),  # an empty answer holds neither
    ]
    assert b"\r" not in out.read_bytes()


def test_the_marks_refuse_two_prompts_and_text_of_a_base(
    marks: Any, record: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    answered = [("q1", "How much is storage?", "Ten a day [1].")]
    v3 = _run(monkeypatch, record.V3_TEMPLATE, tmp_path / "v3", answered)
    v4 = _run(monkeypatch, record.V4_TEMPLATE, tmp_path / "v4", answered)
    leak = _run(
        monkeypatch,
        record.V4_TEMPLATE,
        tmp_path / "leak",
        [("storage-fee", "storage-fee", "Ten a day [1].")],
    )
    out = tmp_path / "marks.jsonl"

    with pytest.raises(SystemExit, match="a plan reads one prompt"):
        marks.main([str(out), "--run", f"v3={v3}", "--run", f"v4={v4}"])
    # A label naming a document, a case id holding its question: text of the base would leave.
    with pytest.raises(SystemExit, match="text of the base"):
        marks.main([str(out), "--run", f"fees.md={v4}"])
    with pytest.raises(SystemExit, match="text of the base"):
        marks.main([str(out), "--run", f"leak={leak}"])
    with pytest.raises(SystemExit, match="give each run once"):
        marks.main([str(out), "--run", f"v4={v4}", "--run", f"v4={v4}"])
    assert not out.exists()


def _sides(a: int, b: int, c: int, d: int) -> tuple[dict, dict, dict]:
    """A paired table as the two sides' yes or no, each pair its own cluster."""
    pairs = [(1, 1)] * a + [(1, 0)] * b + [(0, 1)] * c + [(0, 0)] * d
    tags = [f"toy:{index}" for index in range(len(pairs))]
    return (
        {tag: first for tag, (first, _) in zip(tags, pairs, strict=True)},
        {tag: second for tag, (_, second) in zip(tags, pairs, strict=True)},
        {tag: [f"toy:answer:{tag}"] for tag in tags},
    )


def _spans_both(read: dict) -> bool:
    newcombe, cluster = read["newcombe95"], read["cluster95"]
    return read["read95"] == [min(newcombe[0], cluster[0]), max(newcombe[1], cluster[1])]


def test_a_paired_difference_reads_newcombes_and_the_cluster_interval(record: Any) -> None:
    falls = record.paired(*_sides(0, 20, 0, 20))
    assert falls["table"] == {"a": 0, "b": 20, "c": 0, "d": 20}
    assert (falls["v3"], falls["v4"], falls["difference"]) == (0.5, 0.0, -0.5)
    assert falls["detected"] and falls["direction"] == "falls" and _spans_both(falls)
    assert record.paired(*_sides(0, 0, 20, 20))["direction"] == "rises"

    # Every pair concordant: no difference; the bootstrap has no width, Newcombe's has.
    same = record.paired(*_sides(3, 0, 0, 7))
    assert same["difference"] == 0.0 and same["cluster95"] == [0.0, 0.0]
    assert same["newcombe95"] == [-0.2002, 0.2002] and same["read95"] == same["newcombe95"]
    assert not same["detected"] and same["direction"] == "not detected"
    # Three falls in ten: the read spans both intervals, and Newcombe's upper limit holds zero.
    three = record.paired(*_sides(0, 3, 0, 7))
    assert three["newcombe95"] == [-0.6032, 0.0376] and _spans_both(three)
    assert three["read95"][1] == 0.0376 and three["direction"] == "not detected"
    # No yes on either side: a zero margin, phi 0, Wilson's upper limit of 0 in 10 each way.
    assert record.paired(*_sides(0, 0, 0, 10))["newcombe95"] == [-0.2775, 0.2775]
    # No pair: nothing is read; pairs that do not match are refused.
    empty = record.paired({}, {}, {})
    assert (empty["n"], empty["difference"], empty["read95"]) == (0, None, None)
    assert empty["direction"] == "not detected"
    with pytest.raises(SystemExit, match="a yes or no on both sides of each pair"):
        record.paired({"toy:0": 1}, {"toy:1": 1}, {})
    with pytest.raises(SystemExit, match="a yes or no on both sides of each pair"):
        record.paired({"toy:0": 1}, {"toy:0": 2}, {"toy:0": ["toy:answer:0"]})

    for a, b, c, d in itertools.product(range(4), repeat=4):
        if a + b + c + d:
            low, high = (round(value, 4) for value in record.newcombe(a, b, c, d))
            difference = round((c - b) / (a + b + c + d), 4)
            assert -1 <= low <= difference <= high <= 1, (a, b, c, d)


def test_phi_is_zero_on_a_zero_margin_and_reduced_by_half_n(record: Any) -> None:
    assert record.phi(0, 0, 0, 10) == 0.0
    assert record.phi(0, 5, 0, 5) == 0.0
    assert record.phi(2, 4, 1, 3) == 0.0  # a·d - b·c = 2, under n/2 = 5
    assert record.phi(3, 0, 0, 7) == pytest.approx(16 / 21)  # (21 - 5) / √(3·7·3·7)
    assert record.phi(0, 3, 2, 5) == pytest.approx(-6 / math.sqrt(3 * 7 * 2 * 8))


def test_the_decision_is_read_in_the_specs_table_in_its_order(record: Any) -> None:
    def read(
        pooled: str = "not detected",
        bad: dict[str, str] | None = None,
        good: dict[str, str] | None = None,
        guard: str = "not detected",
        placeholder: dict[str, int] | None = None,
        referral: str = "falls",
        keys: tuple[str, ...] = KEYS,
        not_counted: dict[str, list[str]] | None = None,
    ) -> dict:
        corpora: dict[str, dict] = {
            key: {
                "bad": {"direction": (bad or {}).get(key, "not detected")},
                "good": {"direction": (good or {}).get(key, "not detected")},
                "marks": {"v4": {"placeholder": (placeholder or {}).get(key, 0)}},
                "referral": {"direction": "not detected" if key == "aircargo" else referral},
            }
            for key in keys
        }
        if "conditionalqa" in keys:
            corpora["conditionalqa"]["declines_without_answer"] = {"direction": guard}
        primary = {"keys": [key for key in ("wixqa", "conditionalqa") if key in keys]}
        primary["direction"] = pooled
        return record.decision(primary, corpora, list(keys), not_counted or {})

    unfallen = [
        "wixqa: the referral's share does not fall",
        "conditionalqa: the referral's share does not fall",
    ]
    # 3: fewer bad answers, pooled, keep V4 whatever is left of the defects.
    assert read("falls", referral="not detected") == {
        "decision": "adopted",
        "v4_stays": True,
        "reasons": ["fewer bad answers"],
        "harm": [],
        "defects_left": unfallen,
        "not_counted": {},
        "not_run": [],
    }
    # 4 and 5: no gain - V4 stays only with both defects gone; one placeholder a key is let pass.
    kept = read(placeholder={"aircargo": 1, "wixqa": 1})
    assert (kept["decision"], kept["v4_stays"], kept["reasons"]) == (
        "kept",
        True,
        ["the two defects gone"],
    )
    left = read(placeholder={"wixqa": 2}, referral="not detected")
    assert (left["decision"], left["v4_stays"]) == ("not adopted", False)
    assert left["reasons"] == ["no gain", "wixqa: the placeholder in 2 answers", *unfallen]
    assert read(bad={"wixqa": "falls"})["decision"] == "kept"  # a base's own fall is no gain
    # 1: harm decides before all else, each of its four kinds; a good share falling with the
    # bad share is no harm.
    harmed = read(
        "rises",
        bad={"aircargo": "rises", "conditionalqa": "falls"},
        good={"wixqa": "falls", "conditionalqa": "falls"},
        guard="falls",
    )
    assert (harmed["decision"], harmed["v4_stays"]) == ("not adopted", False)
    assert (
        harmed["reasons"]
        == harmed["harm"]
        == [
            "aircargo: the bad share rises",
            "wixqa: the good share falls, the bad share does not",
            "conditionalqa: fewer declines where the gold says not answerable",
            "pooled: the bad share rises",
        ]
    )
    assert read("falls", bad={"wixqa": "rises"})["decision"] == "not adopted"
    # 2: a plan not counted takes its key's harm, and the pooled one's, with it.
    unstable = read("rises", bad={"wixqa": "rises"}, not_counted={"wixqa": ["v4-bridge-wixqa"]})
    assert (unstable["decision"], unstable["harm"]) == ("NOT_EVIDENCE", [])
    assert unstable["reasons"] == ["a plan not counted: v4-bridge-wixqa"]
    assert unstable["not_counted"] == {"wixqa": ["v4-bridge-wixqa"]}
    other = read(bad={"wixqa": "rises"}, not_counted={"aircargo": ["v4-aircargo-judge"]})
    assert other["decision"] == "not adopted"
    # Harm on the first base stops the others; without harm, a base not run leaves no decision.
    early = read("rises", bad={"wixqa": "rises"}, keys=("wixqa",))
    assert (early["decision"], early["harm"]) == ("not adopted", ["wixqa: the bad share rises"])
    assert early["not_run"] == ["aircargo", "conditionalqa"]
    stopped = read("falls", keys=("wixqa", "conditionalqa"))
    assert (stopped["decision"], stopped["reasons"]) == (
        "NOT_EVIDENCE",
        ["not run whole, no harm read: aircargo"],
    )


def _write(folder: Path, name: str, data: dict, rows: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps(data), "utf-8")
    (folder / f"{name}.cases.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), "utf-8"
    )


def _judge_rows(key: str, side: str, part: str) -> list[dict]:
    """A plan's rows as judge_export.py writes them: ids, classes and the verdict's values."""
    rows = []
    for index, grade in enumerate((V3_CLASSES if side == "v3" else V4_CLASSES)[key]):
        case = f"{key[0]}{index}"
        reference = part == "m2" and case not in NOT_ANSWERABLE
        row: dict[str, Any] = {
            "run": f"{side}-{key}-b01",
            "case_id": case,
            "item_id": f"{side}-{part}-{case}",
            "route": "human" if case in HUMAN.get((key, side), ()) else "auto",
            "has_reference": reference,
            "grade": grade,
            "missing": grade is None,
        }
        if grade is not None:
            own = ("partial" if grade == "partial_ok" else "full", True)
            answers, held = VERDICTS.get((case, side), own)
            total = 0 if answers == "declined" else 2 if held else 1
            row.update(
                claims_total=total,
                claims_supported=total - (grade == "bad" and total == 2),
                context_has_answer=held,
                answers_question=answers,
                citations_supported=0,
                reference=M2[key][side == "v4"][index] if reference else "none",
                defect="none",
            )
        if key in CLUSTERS:  # aircargo's rows have neither
            stratum = "not_answerable" if case in NOT_ANSWERABLE else "answerable"
            row.update(stratum="simulated" if key == "wixqa" else stratum)
            row.update(cluster=CLUSTERS[key][index])
        if part == "m2":
            row["m2"] = M2[key][side == "v4"][index]
        rows.append(row)
    return rows


def _judge_record(key: str, side: str, part: str, name: str, rows: list[dict]) -> dict:
    provenance: dict[str, Any] = {
        "references_sha256": None if key == "aircargo" else f"{key}-references",
        "salt": judge.SALT,
        "prompt_id": "QA_PROMPT_V3" if side == "v3" else "QA_PROMPT_V4",
        "instructions_sha256": hashlib.sha256(judge.INSTRUCTIONS.encode()).hexdigest(),
        "route": dict(ROUTE),
        "runs": {
            f"{side}-{key}-b01": {
                "code_sha": CODE if side == "v3" else STAND,
                "model": "qwen3:4b-instruct-2507-q4_K_M",
                "model_digest": "0edcdef34593",
                "tenant": key if key == "aircargo" else f"ext_{key}",
            }
        },
    }
    if (key, side) != ("aircargo", "v3"):  # p1-aircargo-judge.json predates the field
        provenance["references_withheld"] = part == "m1" and key != "aircargo"
    data: dict[str, Any] = {
        "plan": name,
        "status": "counted",
        "judge": "answers",
        "base": key,
        "provenance": provenance,
        "replies": {"admitted_cli": {"2.1.309": len(rows)}},
        "questions": len(rows),
        "missing": sorted(row["case_id"] for row in rows if row["missing"]),
        "retest": {"passed": True},
    }
    if part == "m2":
        data["m2"] = {"with_reference": {}, "without_reference": {}}
    return data


def _answer_rows(key: str, side: str, delta: int) -> list[dict]:
    """answers_summary.py's rows: the route, the time, the retrieval, the prompt's size."""
    rows = []
    for index in range(10):
        case = f"{key[0]}{index}"
        scores, chars = [0.9, round(0.8 - index / 100, 4)], 6000 + index
        if side == "v4":
            chars += delta
            if case == "a8":
                scores = [0.7, 0.6]  # another retrieval
            if case in ("a9", "w9"):
                chars -= 120  # the same retrieval, a shorter fitted tail
        rows.append(
            {
                "case_id": case,
                "batch": 1,
                "run": f"{side}-{key}-b01",
                "index": index + 1,
                "route": "human" if case in HUMAN.get((key, side), ()) else "auto",
                "total_sec": (100 if side == "v3" else 200) + index,
                "ranked_scores": scores,
                "expanded_docs": 5,
                "expanded_chars": 5000 + index,
                "prompts": [{"file": f"{2 * index + 1:03d}-stream.txt", "chars": chars}],
                "path_breaks": [],
            }
        )
    return rows


def _answers_record(record: Any, key: str, side: str) -> dict:
    """answers_summary.py's record: the stand, the path both sides share, the runs."""
    return {
        "key": key,
        "base": key,
        "provenance": {
            "code_sha": [CODE if side == "v3" else STAND],
            **{field: f"{key}-{field}" for field in record.SAME_PATH},
        },
        "runs": [
            {
                "label": f"{side}-{key}-b01",
                # A run's own paths differ by side; the rest of the settings does not.
                "settings": {
                    "rerank_top_k": 5,
                    **{name: f"/{side}/{key}/{name}" for name in record.PER_RUN},
                },
                "launch": dict(zip(("started", "finished"), LAUNCH[side], strict=True)),
            }
        ],
        "aggregate": {"path_breaks": {}},
    }


def _snapshot(record: Any, taken: str) -> dict:
    """stand_env.py's line: stage 2's Ollama server and interpreter."""
    return {
        "taken": taken,
        "ollama": {
            "server_version": record.OLLAMA,
            "servers": [
                {"pid": 7, "started": "2026-09-13T16:37:06+00:00", "binary": "/toy/ollama"}
            ],
        },
        "distributions": {
            "freeze_sha256": record.FREEZE,
            "newest": {"name": "toy", "changed": "2026-05-30T14:51:39+00:00"},
            "versions": {"langchain": "1.3.2"},
        },
    }


def _world(record: Any, root: Path) -> tuple[Path, dict]:
    """Stage 2's V3 records and a V4 stand's records under root, as the tools write them."""
    folders = {
        "judge": root / "reports/stage2/5e308fe",
        "retrieval": root / "reports/stage2/retrieval-20261021",
        "external": root / "reports/stage2/external-answers-20261023",
        "root": root,
    }
    stand = root / STAND_DIR
    stand.mkdir(parents=True)
    for key in KEYS:
        for side in ("v3", "v4"):
            for part in ("m1",) if key == "aircargo" else ("m1", "m2"):
                if side == "v4":
                    folder, name = (
                        stand,
                        f"v4-{key}-judge" + (f"-{part}" if key != "aircargo" else ""),
                    )
                elif key == "aircargo":
                    folder, name = folders["judge"], "p1-aircargo-judge"
                else:
                    folder, name = folders["judge"], f"p4-{key}-judge-{part}"
                rows = _judge_rows(key, side, part)
                _write(folder, name, _judge_record(key, side, part, name, rows), rows)
            if side == "v4":
                folder, name = stand, f"v4-{key}"
            elif key == "aircargo":
                folder, name = folders["retrieval"], "p1-aircargo"
            else:
                folder, name = folders["external"], f"p4-{key}"
            answers = _answers_record(record, key, side)
            _write(folder, name, answers, _answer_rows(key, side, record.TEMPLATE_DELTA))
            placeholder, referral = MARKS.get((key, side), (set(), set()))
            prompt = "QA_PROMPT_V3" if side == "v3" else "QA_PROMPT_V4"
            lines = [
                {
                    "run": f"{side}-{key}-b01",
                    "case_id": f"{key[0]}{index}",
                    "prompt_id": prompt,
                    "placeholder": f"{key[0]}{index}" in placeholder,
                    "referral": f"{key[0]}{index}" in referral,
                }
                for index in range(10)
            ]
            (stand / f"{side}-{key}.marks.jsonl").write_text(
                "".join(json.dumps(line) + "\n" for line in lines), "utf-8"
            )
        # The bridge: stage 2's M1 plan cut to three requests, their first verdicts its own.
        rows = _judge_rows(key, "v3", "m1")[:3]
        bridge = _judge_record(key, "v3", "m1", f"v4-bridge-{key}", rows)
        bridge["provenance"]["plan_sha256"] = record.BRIDGES[key]
        _write(stand, f"v4-bridge-{key}", bridge, rows)
    (stand / "v4-environment.jsonl").write_text(
        "".join(json.dumps(_snapshot(record, taken)) + "\n" for taken in TAKEN), "utf-8"
    )
    return stand, folders


def test_the_record_pairs_v4_with_v3_question_by_question(record: Any, tmp_path: Path) -> None:
    stand, folders = _world(record, tmp_path)

    built = record.build(stand, **folders)

    corpora = built["corpora"]
    wixqa, cqa, air = corpora["wixqa"], corpora["conditionalqa"], corpora["aircargo"]
    assert (wixqa["pairs"], wixqa["unpaired"]) == (10, {"count": 0, "case_ids": []})
    assert (cqa["pairs"], cqa["unpaired"]) == (9, {"count": 1, "case_ids": ["c7"]})
    bad = wixqa["bad"]
    assert bad["table"] == {"a": 2, "b": 4, "c": 1, "d": 3}
    assert (bad["n"], bad["v3"], bad["v4"], bad["difference"]) == (10, 0.6, 0.3, -0.3)
    # By hand: Wilson 3/10 [0.1078, 0.6032], 6/10 [0.3127, 0.8318]; phi 0 (2 - 5 < 0).
    assert bad["newcombe95"] == [-0.6011, 0.1177]
    # w0 and w1 fall together, one cluster; the read spans both intervals.
    assert bad["clusters"] == 7 and _spans_both(bad)
    assert [corpora[key]["bad"]["direction"] for key in KEYS] == ["not detected"] * 3
    assert wixqa["good"]["table"] == {"a": 2, "b": 1, "c": 3, "d": 4}
    assert wixqa["transitions"] == {
        "good": {"good": 2, "partial_ok": 0, "bad": 1},
        "partial_ok": {"good": 0, "partial_ok": 1, "bad": 0},
        "bad": {"good": 3, "partial_ok": 1, "bad": 2},
    }
    assert cqa["bad"]["table"] == {"a": 1, "b": 4, "c": 1, "d": 3}
    assert (air["bad"]["table"], air["bad"]["clusters"]) == ({"a": 1, "b": 1, "c": 1, "d": 7}, 10)
    # The primary pools both bases' pairs; their clusters 0 are two clusters.
    primary = built["primary"]
    assert primary["indicator"] == "bad" and primary["keys"] == ["wixqa", "conditionalqa"]
    assert primary["table"] == {"a": 3, "b": 8, "c": 2, "d": 6}
    assert (primary["n"], primary["clusters"]) == (19, 14)
    assert primary["difference"] == round(-6 / 19, 4)
    # Newcombe's interval alone would read a fall; the cluster interval holds zero, and the
    # read spans both: no gain.
    assert primary["newcombe95"] == [-0.5546, -0.0039]
    assert primary["cluster95"][1] > 0 and _spans_both(primary)
    assert not primary["detected"] and primary["direction"] == "not detected"
    # The same on the pairs whose context V4 read unchanged: w9's tail is shorter.
    same = built["same_context"]
    assert (same["keys"], same["n"]) == (["wixqa", "conditionalqa"], 18)
    assert same["table"] == {"a": 3, "b": 8, "c": 2, "d": 5}

    # Read by the decision: the defects, and the declines where the gold says not answerable.
    assert wixqa["marks"] == {
        "v3": {"answers": 10, "placeholder": 2, "referral": 3, "referral_routed": 2},
        "v4": {"answers": 10, "placeholder": 0, "referral": 0, "referral_routed": 0},
    }
    assert wixqa["referral"]["table"] == {"a": 0, "b": 3, "c": 0, "d": 7}
    assert cqa["referral"]["table"] == {"a": 0, "b": 2, "c": 0, "d": 8}  # c7 has its answers
    assert cqa["marks"]["v3"]["referral_routed"] == 1
    assert cqa["declines_without_answer"]["table"] == {"a": 1, "b": 0, "c": 1, "d": 0}
    assert "declines_without_answer" not in wixqa  # its questions are simulated, not stratified

    # Printed, deciding nothing.
    assert wixqa["wrong_declines"] == {"v3": 2, "v4": 0}
    assert cqa["wrong_declines"] == {"v3": 1, "v4": 0}  # c7's decline has no pair
    assert cqa["context_has_answer"] == {"same": 8, "lost": 1, "gained": 0}
    # c0, and c8: V3 answered where the gold says not answerable, V4 declined.
    assert (cqa["bad_to_good_declining"], air["bad_to_good_declining"]) == (2, 0)
    assert air["context_has_answer"] == {"same": 9, "lost": 0, "gained": 1}
    assert wixqa["claims_supported"] == {
        "v3": {"supported": 12, "total": 16, "share": 0.75},
        "v4": {"supported": 17, "total": 20, "share": 0.85},
    }
    assert wixqa["human"]["table"] == {"a": 1, "b": 2, "c": 1, "d": 6}
    assert cqa["human"]["table"] == {"a": 0, "b": 2, "c": 1, "d": 6}
    assert (wixqa["times"]["v3"]["median"], wixqa["times"]["v4"]["median"]) == (104.5, 204.5)
    assert air["pairing"] == {
        "questions": 10,
        "same_retrieval": 9,
        "same_context": 8,
        "shorter_tail": 1,
        "longer": 0,
    }
    assert wixqa["pairing"]["same_context"] == 9
    assert "m2" not in air
    agrees = wixqa["m2"]["with_reference"]["agrees"]
    assert (agrees["table"], agrees["difference"]) == ({"a": 3, "b": 1, "c": 3, "d": 3}, 0.2)
    held = cqa["m2"]["with_reference"]
    assert (held["questions"], held["pairs"], held["unpaired"]["case_ids"]) == (8, 7, ["c7"])
    assert held["agrees"]["table"] == {"a": 2, "b": 0, "c": 2, "d": 3}
    assert cqa["m2"]["without_reference"]["right"] == {"v3": 1, "v4": 2}
    assert cqa["m2"]["status"] == "counted"

    counted = {"status": "counted", "retest_passed": True}
    assert built["plans"]["v4"]["v4-wixqa-judge-m1"] == {
        **counted,
        "admitted_cli": {"2.1.309": 10},
    }
    assert sorted(built["plans"]["v3"]) == [
        "p1-aircargo-judge",
        "p4-conditionalqa-judge-m1",
        "p4-conditionalqa-judge-m2",
        "p4-wixqa-judge-m1",
        "p4-wixqa-judge-m2",
    ]
    assert built["plans"]["bridge"] == {
        f"v4-bridge-{key}": {**counted, "admitted_cli": {"2.1.309": 3}} for key in KEYS
    }
    # No harm and no gain, and the referral's fall in ten answers is not detected: V3 is back.
    assert built["decision"] == {
        "decision": "not adopted",
        "v4_stays": False,
        "reasons": [
            "no gain",
            "wixqa: the referral's share does not fall",
            "conditionalqa: the referral's share does not fall",
        ],
        "harm": [],
        "defects_left": [
            "wixqa: the referral's share does not fall",
            "conditionalqa: the referral's share does not fall",
        ],
        "not_counted": {},
        "not_run": [],
    }
    assert (built["stand"], built["stage2"], built["keys"]) == (STAND, CODE, list(KEYS))
    assert built["prompts"] == {
        "v3": "QA_PROMPT_V3",
        "v4": "QA_PROMPT_V4",
        "v3_sha256": V3_SHA256,
        "v4_sha256": V4_SHA256,
        "template_delta": 249,
    }
    assert built["tools"] == {
        name: hashlib.sha256((TOOLS / name).read_bytes()).hexdigest()
        for name in (
            "answer_marks.py",
            "bridge_plan.py",
            "raise_stand.sh",
            "stand_env.py",
            "v4_record.py",
        )
    }
    assert built["environment"] == {
        "snapshots": 2,
        "taken": list(TAKEN),
        "ollama": "0.33.2",
        "servers": [{"pid": 7, "started": "2026-09-13T16:37:06+00:00", "binary": "/toy/ollama"}],
        "freeze_sha256": record.FREEZE,
        "newest": {"name": "toy", "changed": "2026-05-30T14:51:39+00:00"},
        "versions": {"langchain": "1.3.2"},
    }
    assert any("in-sample" in line for line in built["disclosure"])
    assert any("/api/ask" in line for line in built["disclosure"])
    # 8 records a side and 3 bridges, .json and .cases.jsonl; 6 marks files; the environment.
    assert len(built["inputs"]) == 45
    for path in (
        "reports/stage2/5e308fe/p4-wixqa-judge-m1.json",
        "reports/stage2/retrieval-20261021/p1-aircargo.cases.jsonl",
        "reports/stage2/external-answers-20261023/p4-conditionalqa.json",
        f"{STAND_DIR}/v4-conditionalqa-judge-m2.cases.jsonl",
        f"{STAND_DIR}/v3-aircargo.marks.jsonl",
        f"{STAND_DIR}/v4-bridge-wixqa.cases.jsonl",
        f"{STAND_DIR}/v4-environment.jsonl",
    ):
        assert built["inputs"][path] == hashlib.sha256((tmp_path / path).read_bytes()).hexdigest()


def test_the_registered_constants_are_the_specs(record: Any) -> None:
    """The bridges bridge_plan.py froze and stage 2's environment, as the spec names them."""
    spec = (ROOT / "docs/specs/answer-prompt-v4.md").read_text("utf-8")
    for digest in (*record.BRIDGES.values(), record.FREEZE):
        assert digest in spec
    assert record.STAGE2_FIRST == "2026-10-19T19:07:50+00:00"
    assert f"Ollama {record.OLLAMA}" in spec


def test_the_record_is_written_once_with_lf(record: Any, tmp_path: Path) -> None:
    stand, folders = _world(record, tmp_path)

    assert record.main([str(stand)], **folders) == 0
    assert record.main([str(stand), str(tmp_path / "other.json")], **folders) == 0

    written = (stand / "v4-record.json").read_bytes()
    built = record.build(stand, **folders)
    assert written == (json.dumps(built, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    assert (tmp_path / "other.json").read_bytes() == written  # the bootstrap's seed is fixed
    assert b"\r" not in written
    with pytest.raises(SystemExit, match="usage"):
        record.main([], **folders)


def test_a_plan_not_counted_makes_the_decision_not_evidence(record: Any, tmp_path: Path) -> None:
    stand, folders = _world(record, tmp_path)
    _edit(stand / "v4-conditionalqa-judge-m2.json", lambda data: {**data, "status": "NOT_EVIDENCE"})

    m2_only = record.build(stand, **folders)
    assert m2_only["decision"]["decision"] == "not adopted"  # M2 decides nothing
    assert m2_only["corpora"]["conditionalqa"]["m2"]["status"] == "NOT_EVIDENCE"

    # An M1 plan, and a bridge: the judge moved since stage 2.
    _edit(stand / "v4-aircargo-judge.json", lambda data: {**data, "status": "NOT_EVIDENCE"})
    _edit(stand / "v4-bridge-wixqa.json", lambda data: {**data, "status": "NOT_EVIDENCE"})
    built = record.build(stand, **folders)
    assert built["decision"]["decision"] == "NOT_EVIDENCE"
    assert built["decision"]["reasons"] == [
        "a plan not counted: v4-aircargo-judge, v4-bridge-wixqa"
    ]
    assert built["decision"]["not_counted"] == {
        "aircargo": ["v4-aircargo-judge"],
        "wixqa": ["v4-bridge-wixqa"],
    }
    assert built["plans"]["v4"]["v4-aircargo-judge"]["status"] == "NOT_EVIDENCE"
    assert built["plans"]["bridge"]["v4-bridge-wixqa"]["status"] == "NOT_EVIDENCE"


def test_harm_on_the_first_base_decides_with_the_others_stopped(
    record: Any, tmp_path: Path
) -> None:
    stand, folders = _world(record, tmp_path)
    # V3 graded every WixQA answer good, V4 every one bad: the bad share rises, detected.
    for path in (
        tmp_path / "reports/stage2/5e308fe/p4-wixqa-judge-m1.cases.jsonl",
        stand / "v4-bridge-wixqa.cases.jsonl",
    ):
        _edit(path, lambda rows: [{**row, "grade": "good"} for row in rows])
    _edit(
        stand / "v4-wixqa-judge-m1.cases.jsonl",
        lambda rows: [{**row, "grade": "bad"} for row in rows],
    )
    for path in [*stand.glob("v4-*conditionalqa*"), *stand.glob("v4-*aircargo*")]:
        path.unlink()  # the bases after it were stopped: no record of theirs

    built = record.build(stand, ("wixqa",), **folders)

    assert built["keys"] == ["wixqa"] and list(built["corpora"]) == ["wixqa"]
    assert (built["primary"]["keys"], built["primary"]["direction"]) == (["wixqa"], "rises")
    harm = ["wixqa: the bad share rises", "wixqa: the good share falls, the bad share does not"]
    assert built["decision"] == {
        "decision": "not adopted",
        "v4_stays": False,
        "reasons": harm,
        "harm": harm,
        "defects_left": ["wixqa: the referral's share does not fall"],
        "not_counted": {},
        "not_run": ["aircargo", "conditionalqa"],
    }
    # 3 records a side and the bridge, .json and .cases.jsonl; 2 marks files; the environment.
    assert len(built["inputs"]) == 17


def test_a_base_not_run_without_harm_leaves_no_decision(record: Any, tmp_path: Path) -> None:
    stand, folders = _world(record, tmp_path)
    out = tmp_path / "two.json"

    built = record.build(stand, ("conditionalqa", "wixqa"), **folders)
    assert record.main([str(stand), str(out), "--keys", "wixqa,conditionalqa"], **folders) == 0

    assert built["keys"] == ["wixqa", "conditionalqa"]
    assert built["decision"]["decision"] == "NOT_EVIDENCE"
    assert built["decision"]["reasons"] == ["not run whole, no harm read: aircargo"]
    assert json.loads(out.read_text("utf-8")) == built
    for keys in ((), ("wixqa", "wixqa"), ("multihoprag",)):
        with pytest.raises(SystemExit, match="--keys names some of"):
            record.build(stand, keys, **folders)
    with pytest.raises(SystemExit, match="usage"):
        record.main([str(stand), "--keys"], **folders)


def _edit(path: Path, change: Callable[[Any], Any]) -> None:
    """Rewrite a record (.json) or the rows of a .jsonl file through change."""
    if path.suffix == ".json":
        path.write_text(json.dumps(change(json.loads(path.read_text("utf-8")))), "utf-8")
        return
    rows = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
    path.write_text("".join(json.dumps(row) + "\n" for row in change(rows)), "utf-8")


def _provenance(**changes: Any) -> Callable[[dict], dict]:
    return lambda data: {**data, "provenance": {**data["provenance"], **changes}}


def _runs(**changes: Any) -> Callable[[dict], dict]:
    """Each run of a judge record's provenance, changed."""

    def change(data: dict) -> dict:
        runs = {name: {**run, **changes} for name, run in data["provenance"]["runs"].items()}
        return _provenance(runs=runs)(data)

    return change


def _settings(**changes: Any) -> Callable[[dict], dict]:
    """Each run's settings of an answers record, changed."""
    return lambda data: {
        **data,
        "runs": [{**run, "settings": {**run["settings"], **changes}} for run in data["runs"]],
    }


def _snapshots(change: Callable[[dict], dict], *, last: bool = False) -> Callable[[list], list]:
    """The environment's first line, or its last, changed."""
    if last:
        return lambda rows: [*rows[:-1], change(rows[-1])]
    return lambda rows: [change(rows[0]), *rows[1:]]


@pytest.mark.parametrize(
    ("path", "change", "match"),
    [
        (
            "reports/stage2/5e308fe/p4-wixqa-judge-m1.json",
            _provenance(prompt_id="QA_PROMPT_V4"),
            "its plan reads QA_PROMPT_V4",
        ),
        (
            f"{STAND_DIR}/v4-aircargo-judge.json",
            _provenance(prompt_id="QA_PROMPT_V3"),
            "its plan reads QA_PROMPT_V3",
        ),
        (
            f"{STAND_DIR}/v4-wixqa-judge-m1.json",
            _provenance(references_withheld=False),
            "the m1 plan withholds the references",
        ),
        (f"{STAND_DIR}/v4-conditionalqa-judge-m2.json", _provenance(salt="x"), "its salt differs"),
        (
            f"{STAND_DIR}/v4-aircargo-judge.json",
            _provenance(route={**ROUTE, "effort": "high"}),
            "its route differs",
        ),
        (
            f"{STAND_DIR}/v4-wixqa-judge-m1.json",
            _runs(model_digest="another"),
            "answers of another model or tenant",
        ),
        (
            f"{STAND_DIR}/v4-wixqa-judge-m2.json",
            _provenance(references_sha256="other"),
            "its references_sha256 differs",
        ),
        (
            "reports/stage2/external-answers-20261023/p4-wixqa.json",
            _provenance(code_sha=[STAND]),
            "not the stand 5e308fe",
        ),
        (f"{STAND_DIR}/v4-wixqa.json", _provenance(code_sha=[CODE]), "one stand, not stage 2's"),
        (f"{STAND_DIR}/v4-aircargo.json", _provenance(code_sha=["f" * 40]), "one stand"),
        (
            f"{STAND_DIR}/v4-conditionalqa.cases.jsonl",
            lambda rows: [{**rows[0], "path_breaks": ["rerank error"]}, *rows[1:]],
            "a counted answer has a path break",
        ),
        (
            f"{STAND_DIR}/v4-wixqa.json",
            _provenance(source_sha256={"corpus.manifest.json": "other"}),
            "not stage 2's path, its source_sha256 differs",
        ),
        (
            f"{STAND_DIR}/v4-conditionalqa.json",
            _provenance(overrides={}),
            "its overrides differ",
        ),
        (f"{STAND_DIR}/v4-aircargo.json", _settings(rerank_top_k=4), "its settings differ"),
        (
            f"{STAND_DIR}/v4-bridge-wixqa.json",
            _provenance(plan_sha256="other"),
            "not the bridge the spec registered",
        ),
        (
            f"{STAND_DIR}/v4-bridge-aircargo.json",
            _provenance(prompt_id="QA_PROMPT_V4"),
            "its plan reads QA_PROMPT_V4",
        ),
        (
            f"{STAND_DIR}/v4-bridge-conditionalqa.json",
            _runs(chroma_dir="/other"),
            "not stage 2's plan, its runs differ",
        ),
        (
            f"{STAND_DIR}/v4-bridge-wixqa.cases.jsonl",
            lambda rows: [{**rows[0], "grade": "partial_ok"}, *rows[1:]],
            "its first verdicts are not stage 2's",
        ),
        (f"{STAND_DIR}/v4-aircargo.cases.jsonl", lambda rows: rows[:-1], "other questions"),
        (f"{STAND_DIR}/v4-wixqa-judge-m1.cases.jsonl", lambda rows: [*rows, rows[0]], "twice"),
        (
            f"{STAND_DIR}/v3-wixqa.marks.jsonl",
            lambda rows: [{**row, "prompt_id": "QA_PROMPT_V4"} for row in rows],
            "marks of another prompt than QA_PROMPT_V3",
        ),
        (
            f"{STAND_DIR}/v4-environment.jsonl",
            _snapshots(lambda row: {**row, "ollama": {**row["ollama"], "server_version": "0.34"}}),
            "not one Ollama server of stage 2's 0.33.2",
        ),
        (
            f"{STAND_DIR}/v4-environment.jsonl",
            _snapshots(
                lambda row: {
                    **row,
                    "distributions": {**row["distributions"], "freeze_sha256": "x"},
                },
                last=True,
            ),
            "the interpreter's distributions are not stage 2's",
        ),
        (
            f"{STAND_DIR}/v4-environment.jsonl",
            _snapshots(
                lambda row: {
                    **row,
                    "distributions": {
                        **row["distributions"],
                        "newest": {"name": "toy", "changed": "2026-10-20T00:00:00+00:00"},
                    },
                }
            ),
            "the interpreter's distributions are not stage 2's",
        ),
        (
            f"{STAND_DIR}/v4-environment.jsonl",
            lambda rows: rows[:1],
            "not read before V4's first answer and after its last",
        ),
        (
            f"{STAND_DIR}/v4-conditionalqa-judge-m2.cases.jsonl",
            lambda rows: [{**row, "has_reference": True} for row in rows],
            "give other questions a reference",
        ),
    ],
)
def test_the_record_refuses_inputs_it_cannot_pair(
    record: Any, tmp_path: Path, path: str, change: Callable[[Any], Any], match: str
) -> None:
    stand, folders = _world(record, tmp_path)
    _edit(tmp_path / path, change)

    with pytest.raises(SystemExit, match=match):
        record.build(stand, **folders)


def test_the_record_reads_the_repositorys_records_in_the_stands_folder(
    record: Any, tmp_path: Path
) -> None:
    stand, folders = _world(record, tmp_path)

    with pytest.raises(SystemExit, match="not a record of the repository"):
        record.build(stand, **{**folders, "root": tmp_path / "reports" / "stage2"})
    other = stand.rename(stand.parent / "abcdef0")
    with pytest.raises(SystemExit, match=f"abcdef0: the folder of the stand {STAND} is 1234567"):
        record.build(other, **folders)
    other.rename(stand)
    for name in ("v4-environment.jsonl", "v4-bridge-aircargo.json", "v4-wixqa.marks.jsonl"):
        (stand / name).unlink()
        with pytest.raises(SystemExit, match=f"{re.escape(name)}: no such record"):
            record.build(stand, **folders)


def _stage2_plan(retests: int = 2) -> dict:
    """A plan of the judge's own, as stage 2 froze one: three requests, the first ones retested."""
    items = []
    for index in range(3):
        message = f"request {index}"
        items.append(
            {
                "item_id": f"i{index}",
                "run": "b01",
                "case_id": f"q{index}",
                "message": message,
                "message_sha256": hashlib.sha256(message.encode("utf-8")).hexdigest(),
            }
        )
    items += [
        {**item, "item_id": f"{item['item_id']}-retest", "retest_of": item["item_id"]}
        for item in items[:retests]
    ]
    return {
        "salt": judge.SALT,
        "prompt_id": "QA_PROMPT_V3",
        "runs": {"b01": {"code_sha": CODE}},
        "route": judge.isolated.settings(judge.SYSTEM_PROMPT),
        "instructions_sha256": hashlib.sha256(judge.INSTRUCTIONS.encode("utf-8")).hexdigest(),
        "references_sha256": None,
        "references_withheld": False,
        "items": items,
    }


def test_a_bridge_keeps_the_retested_requests_and_their_first_replies(
    tools: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bridge = tools["bridge_plan"]
    source = tmp_path / "stage2"
    source.mkdir()
    plan = _stage2_plan()
    (source / "plan.json").write_text(json.dumps(plan), "utf-8")
    # Stage 2's journal as the laptop wrote it, CRLF: a retried request, and a retest's reply.
    lines = [
        json.dumps({"item_id": item_id, "status": status}) + "\r\n"
        for item_id, status in (
            ("i0", "invalid"),
            ("i0", "valid"),
            ("i1", "valid"),
            ("i2", "valid"),
            ("i0-retest", "valid"),
        )
    ]
    (source / "verdicts.jsonl").write_bytes("".join(lines).encode("utf-8"))
    out = tmp_path / "bridge"

    assert bridge.main([str(source), str(out)]) == 0

    frozen = json.loads((out / "plan.json").read_text("utf-8"))
    assert [item["item_id"] for item in frozen["items"]] == ["i0", "i1", "i0-retest", "i1-retest"]
    assert {**frozen, "items": None} == {**plan, "items": None}
    judge.check_plan(frozen)
    # The first requests' replies, as they stand; the retests are left to grade.
    assert (out / "verdicts.jsonl").read_bytes() == "".join(lines[:3]).encode("utf-8")
    data = (out / "plan.json").read_bytes()
    assert b"\r" not in data
    assert f"PLAN_SHA256 {hashlib.sha256(data).hexdigest()}" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="a bridge is frozen once"):
        bridge.main([str(source), str(out)])

    (source / "plan.json").write_text(json.dumps(_stage2_plan(retests=0)), "utf-8")
    with pytest.raises(SystemExit, match="the plan holds no retest"):
        bridge.main([str(source), str(tmp_path / "none")])
    (source / "plan.json").write_text(json.dumps(plan), "utf-8")
    (source / "verdicts.jsonl").write_bytes("".join(lines[:2]).encode("utf-8"))
    with pytest.raises(SystemExit, match="lacks a reply to a request the bridge repeats"):
        bridge.main([str(source), str(tmp_path / "unanswered")])
    (source / "plan.json").write_text(json.dumps({**plan, "salt": "other"}), "utf-8")
    with pytest.raises(SystemExit, match="not frozen by this judge"):
        bridge.main([str(source), str(tmp_path / "foreign")])
    with pytest.raises(SystemExit, match="usage"):
        bridge.main([str(source)])


def test_the_spec_names_the_reading_as_it_stands() -> None:
    """The reading is frozen at registration: the spec names the SHA-256 of each tool and of
    this test, and a later change of one shows here (a marked error fix updates the spec)."""
    spec = (ROOT / "docs/specs/answer-prompt-v4.md").read_text("utf-8")
    named = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.(?:py|sh))` `([0-9a-f]{64})`", spec))
    assert sorted(named) == [
        "reports/answer-prompt-v4/tools/answer_marks.py",
        "reports/answer-prompt-v4/tools/bridge_plan.py",
        "reports/answer-prompt-v4/tools/raise_stand.sh",
        "reports/answer-prompt-v4/tools/stand_env.py",
        "reports/answer-prompt-v4/tools/v4_record.py",
        "tests/test_answer_prompt_v4_record.py",
    ]
    for path, digest in named.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
