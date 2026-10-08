"""The parts of the external bases: the rules on small bases, and the registration as committed."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from evaluation import external_bases as bases
from evaluation import external_parts as parts
from scripts import external_base

# The parts and selections as registered 2026-10-05: cases and the SHA-256 of their ids.
REGISTERED = {
    ("conditionalqa", "tuning"): (
        882,
        "da05fc233a1af478e9af655b80ac0c90fe085b3398f65cac361f1f6b24f3d971",
    ),
    ("conditionalqa", "locked"): (
        859,
        "6bd328fb9ff4cd3b112588165e803d70a74c6704c2ae7d7631e5479000acf3a7",
    ),
    ("conditionalqa", "reserve"): (
        882,
        "cfda18cec1141a4c07d5bcd94b5f945508674ef36b96788f96876a1401b12060",
    ),
    ("wixqa", "tuning"): (142, "cff20933b0ebc748c6f063ebe8d5f0d7b2cbc36d95b253bb87e725a3a74950b5"),
    ("wixqa", "locked"): (200, "d44d5ac308e318a4a09ec9184ee24b087a72d4893decbc83a5bb873ee8c5f7cd"),
    ("wixqa", "excluded"): (58, "890edf739d9a75d084fb66018869fae27dcd099ce15d9dfccf878e53d09834eb"),
    ("multihoprag", "advisory"): (
        1117,
        "52431d7c3d59fb5344e2af14ae1218f43d9e97a9e8433214917fea665c6648ec",
    ),
}
PILOTS = {
    "conditionalqa": (50, "5c3f5ae6faa9941318ab1e3f487a8284e650bdd7cd93e35afad4b81539dfffd4"),
    "wixqa": (40, "74effed693bafe0e46d50e9a65c22ba9e3f70424b7dd110e48102329f22452f4"),
}


def _cq(number: int, document: str, kind: str = "a", sections: tuple[int, ...] = (1,)) -> dict:
    """A ConditionalQA case: a — primary, n — not answerable, e — no evidence, u — unresolved."""
    groups = [
        {
            "alternatives": [
                {"source_id": document, "start": 0, "end": 1, "section": section, "part": 0}
            ]
        }
        for section in sections
        if kind != "e"
    ]
    return {
        "case_id": f"conditionalqa-train-{number}",
        "base": "conditionalqa",
        "stratum": "not_answerable" if kind == "n" else "answerable",
        "query": f"scenario and question {number}",
        "document": document,
        "gold_sources": [document] if groups else [],
        "evidence_groups": groups,
        "unresolved_evidence": int(kind == "u"),
    }


def _wix(stratum: str, number: int, *articles: str) -> dict:
    return {
        "case_id": f"wixqa-{stratum}-{number:03d}",
        "base": "wixqa",
        "stratum": stratum,
        "query": f"how do I {stratum} {number}",
        "gold_sources": list(articles),
    }


def _hop(number: int, kind: str, *documents: str) -> dict:
    return {
        "case_id": f"multihoprag-{number:04d}",
        "base": "multihoprag",
        "stratum": kind,
        "query": f"which outlet {number}",
        "gold_sources": sorted(documents),
        "evidence_groups": [{"alternatives": [{"source_id": name}]} for name in documents],
        "unresolved_evidence": 0,
    }


CONDITIONALQA = [
    _cq(number, f"page-{number % 7}.md", "n" if number % 5 == 0 else "a", (1, 1 + number % 2))
    for number in range(35)
]
WIXQA = [
    _wix("expertwritten", 0, "a.md"),
    _wix("expertwritten", 1, "b.md", "c.md"),
    _wix("simulated", 0, "c.md"),
    _wix("simulated", 1, "d.md", "a.md"),
    _wix("simulated", 2, "d.md"),
    _wix("simulated", 3, "e.md"),
    _wix("simulated", 4, "f.md", "e.md"),
]
MULTIHOPRAG = [
    _hop(0, "inference_query", "a.md", "b.md"),
    _hop(1, "null_query"),
    _hop(2, "comparison_query", "a.md", "c.md"),
    _hop(3, "temporal_query", "b.md", "c.md"),
    _hop(4, "inference_query", "c.md", "d.md"),
]
CASES = {"conditionalqa": CONDITIONALQA, "wixqa": WIXQA, "multihoprag": MULTIHOPRAG}
# Pages whose question has evidence in one section, in two, in one, in two.
SPREAD = (("six.md", (1,)), ("seven.md", (1, 2)), ("eight.md", (3, 3)), ("nine.md", (2, 4)))
SMALL_PILOT = {
    "conditionalqa": {"part": "tuning", "stratum": "primary", "documents": 2, "per_document": 2},
    "wixqa": {"part": "tuning", "questions": 2},
}


def _file(cases: list[dict]) -> bytes:
    return "".join(json.dumps(case, sort_keys=True) + "\n" for case in cases).encode("utf-8")


def _ids(cases: list[Any]) -> list[str]:
    return [case["case_id"] for case in cases]


@pytest.fixture
def small(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """The registration the rules give for the three small bases, with a pilot of their size."""
    monkeypatch.setattr(parts, "PILOT", SMALL_PILOT)
    return parts.build(CASES, {base: bases.sha256(_file(cases)) for base, cases in CASES.items()})


def test_the_order_is_the_sha256_of_seed_base_kind_and_id() -> None:
    expected = hashlib.sha256(b"20260925:wixqa:question:wixqa-simulated-007").hexdigest()
    assert parts.rank("wixqa", "question", "wixqa-simulated-007") == expected
    ids = [f"q{number}" for number in range(20)]
    by_hand = sorted(
        ids, key=lambda item: hashlib.sha256(f"20260925:wixqa:question:{item}".encode()).hexdigest()
    )
    assert parts.in_order("wixqa", "question", reversed(ids)) == by_hand != ids
    assert parts.in_order("multihoprag", "question", ids) != by_hand
    assert parts.in_order("wixqa", "document", ids) != by_hand
    assert parts.digest(["a", "b"]) == hashlib.sha256(b"a\nb\n").hexdigest()


def test_documents_are_cut_into_three_runs_and_questions_follow_their_document() -> None:
    split = parts.split("conditionalqa", CONDITIONALQA)

    assert list(split) == ["tuning", "locked", "reserve"]
    documents = {
        name: list(dict.fromkeys(case["document"] for case in part)) for name, part in split.items()
    }
    # Seven documents: sizes differ by one at most, an earlier run the larger.
    assert [len(names) for names in documents.values()] == [3, 2, 2]
    order = parts.in_order("conditionalqa", "document", {f"page-{n}.md" for n in range(7)})
    assert documents["tuning"] + documents["locked"] + documents["reserve"] == order
    # Every question stands once, a not-answerable one too, and beside the others of its page.
    assert sorted(_ids([case for part in split.values() for case in part])) == sorted(
        _ids(CONDITIONALQA)
    )
    for part in split.values():
        for document in dict.fromkeys(case["document"] for case in part):
            of_document = [case for case in part if case["document"] == document]
            first = part.index(of_document[0])
            assert part[first : first + len(of_document)] == of_document
            assert _ids(of_document) == parts.in_order(
                "conditionalqa", "question", _ids(of_document)
            )
            assert len(of_document) == 5
    # The cut does not depend on the order the cases came in.
    assert parts.split("conditionalqa", CONDITIONALQA[::-1]) == split
    assert [parts._thirds(count) for count in (6, 7, 8, 495)] == [
        (2, 2, 2),
        (3, 2, 2),
        (3, 3, 2),
        (165, 165, 165),
    ]


def test_a_simulated_question_that_shares_a_gold_article_with_a_locked_one_is_excluded() -> None:
    split = parts.split("wixqa", WIXQA)

    assert {name: set(_ids(part)) for name, part in split.items()} == {
        # 002 shares an article with an excluded question only, and stays.
        "tuning": {"wixqa-simulated-002", "wixqa-simulated-003", "wixqa-simulated-004"},
        "locked": {"wixqa-expertwritten-000", "wixqa-expertwritten-001"},
        "excluded": {"wixqa-simulated-000", "wixqa-simulated-001"},
    }
    for name, part in split.items():
        assert _ids(part) == parts.in_order("wixqa", "question", _ids(part)), name
    with pytest.raises(ValueError, match="unregistered stratum"):
        parts.split("wixqa", [*WIXQA, {**WIXQA[0], "case_id": "other", "stratum": "other"}])
    with pytest.raises(ValueError, match="unregistered base"):
        parts.split("hotpotqa", WIXQA)


def test_multihoprag_has_one_open_part_of_two_question_types(small: dict[str, Any]) -> None:
    block = small["bases"]["multihoprag"]

    assert list(block["parts"]) == ["advisory"] and "multihoprag" not in small["selections"]
    advisory = block["parts"]["advisory"]
    assert set(advisory["case_ids"]) == {"multihoprag-0000", "multihoprag-0001", "multihoprag-0004"}
    assert advisory["access"] == "open" and block["in_no_part"] == 2
    assert advisory["questions_by_type"] == {"inference_query": 2, "null_query": 1}
    # The question without gold joins no cluster; the two others share no document.
    assert advisory["questions_by_gold_documents"] == {"0": 1, "2": 2}
    assert (advisory["clusters"], advisory["cluster_sizes"]) == (2, {"1": 2})
    assert parts.read(small, "multihoprag", part="advisory") == advisory["case_ids"]


def test_a_selection_by_documents_takes_the_first_documents_with_enough_primary_questions() -> None:
    kinds = {"one.md": "aa", "three.md": "a", "five.md": "aeu", "two.md": "ana", "four.md": "aaaa"}
    numbers = iter(range(100))
    part = [_cq(next(numbers), name, kind) for name, row in kinds.items() for kind in row]
    of = {name: [case for case in part if case["document"] == name] for name in kinds}

    def take(documents: int, per_document: int, stratum: str = "primary") -> list[Any]:
        rule = {"part": "tuning", "stratum": stratum, "documents": documents}
        return parts.select("conditionalqa", part, {**rule, "per_document": per_document})

    # three.md and five.md carry one primary question each and are passed over; the
    # not-answerable question of two.md is not taken.
    assert take(2, 2) == [*of["one.md"], of["two.md"][0], of["two.md"][2]]
    assert take(3, 2) == [*take(2, 2), *of["four.md"][:2]]
    with pytest.raises(ValueError, match="fewer such documents"):
        take(4, 2)
    # One question a document: the question without evidence and the one with unresolved
    # evidence of five.md are no more primary than a not-answerable one.
    assert take(5, 1) == [
        of["one.md"][0],
        of["three.md"][0],
        of["five.md"][0],
        of["two.md"][0],
        of["four.md"][0],
    ]
    assert [parts.primary(case) for case in of["five.md"]] == [True, False, False]
    # Another stratum is read the same way: the first documents that carry such questions.
    spread = [_cq(next(numbers), name, "a", sections) for name, sections in SPREAD]
    # eight.md has two pieces of evidence in one section: its question is not such a one.
    assert parts.select(
        "conditionalqa",
        spread,
        {"part": "tuning", "stratum": "several_sections", "documents": 2, "per_document": 1},
    ) == [spread[1], spread[3]]
    assert parts.select(
        "conditionalqa",
        [*part, *spread],
        {"part": "tuning", "stratum": "not_answerable", "questions": 1},
    ) == [of["two.md"][1]]
    for rule in (
        {"part": "tuning", "documents": 1, "per_document": 1},
        {"part": "tuning", "stratum": "primary", "documents": 1, "per_document": 1},
    ):
        with pytest.raises(ValueError, match="needs a stratum of ConditionalQA"):
            parts.select("wixqa" if "stratum" in rule else "conditionalqa", part, rule)
    with pytest.raises(ValueError, match="unregistered stratum of ConditionalQA: easy"):
        parts.select("conditionalqa", part, {"part": "tuning", "stratum": "easy", "questions": 1})


def test_a_selection_by_questions_is_a_prefix_of_its_part() -> None:
    part = parts.split("wixqa", WIXQA)["tuning"]

    two = parts.select("wixqa", part, {"part": "tuning", "questions": 2})
    assert two == part[:2] == parts.select("wixqa", part, {"part": "tuning", "questions": 3})[:2]
    with pytest.raises(ValueError, match="fewer questions"):
        parts.select("wixqa", part, {"part": "tuning", "questions": 4})
    # A stratum narrows the questions the prefix is taken of.
    advisory = parts.split("multihoprag", MULTIHOPRAG)["advisory"]
    rule = {"part": "advisory", "stratum": "inference_query", "questions": 2}
    assert _ids(parts.select("multihoprag", advisory, rule)) == parts.in_order(
        "multihoprag", "question", ["multihoprag-0000", "multihoprag-0004"]
    )
    with pytest.raises(ValueError, match="fewer questions"):
        parts.select("multihoprag", advisory, {**rule, "stratum": "null_query"})


def test_the_registration_carries_counts_digests_and_the_ids_in_order(
    small: dict[str, Any],
) -> None:
    assert small["seed"] == 20260925 and small["rules"] == parts.RULES and small["opened"] == []
    conditionalqa = small["bases"]["conditionalqa"]
    assert conditionalqa["cases"] == 35 and conditionalqa["in_no_part"] == 0
    tuning = conditionalqa["parts"]["tuning"]
    assert tuning["access"] == "open" and tuning["documents"] == 3 and tuning["cases"] == 15
    assert tuning["cases_sha256"] == parts.digest(tuning["case_ids"])
    # Each page holds five questions, one of them not answerable.
    assert (tuning["answerable"], tuning["not_answerable"], tuning["primary"]) == (12, 3, 12)
    assert (tuning["clusters"], tuning["cluster_sizes"]) == (3, {"4": 3})
    by_id = {case["case_id"]: case for case in CONDITIONALQA}
    several = [
        case_id
        for case_id in tuning["case_ids"]
        if parts.primary(by_id[case_id]) and int(case_id.rsplit("-", 1)[1]) % 2
    ]
    assert tuning["primary_with_evidence_in_several_sections"] == len(several) > 0
    # The questions of each stratum by document, the documents in the order of the part.
    pages = list(dict.fromkeys(by_id[case_id]["document"] for case_id in tuning["case_ids"]))
    assert tuning["primary_by_document"] == [4, 4, 4]
    assert tuning["several_sections_by_document"] == [
        sum(by_id[case_id]["document"] == name for case_id in several) for name in pages
    ]
    assert [part["access"] for part in conditionalqa["parts"].values()] == [
        "open",
        "locked",
        "locked",
    ]
    pilot = small["selections"]["conditionalqa"]["pilot"]
    assert pilot["rule"] == SMALL_PILOT["conditionalqa"] and pilot["cases"] == 4
    assert (pilot["documents"], pilot["clusters"], pilot["cluster_sizes"]) == (2, 2, {"2": 2})
    assert set(pilot["case_ids"]) < set(tuning["case_ids"])
    wixqa = small["bases"]["wixqa"]["parts"]
    assert {name: part["access"] for name, part in wixqa.items()} == {
        "tuning": "open",
        "locked": "locked",
        "excluded": "locked",
    }
    # 003 and 004 share e.md and make one cluster; 002 stands alone.
    assert (wixqa["tuning"]["clusters"], wixqa["tuning"]["cluster_sizes"]) == (2, {"1": 1, "2": 1})
    assert wixqa["tuning"]["gold_documents"] == 3 and wixqa["tuning"]["distinct_gold_sets"] == 3
    assert wixqa["tuning"]["questions_by_gold_documents"] == {"1": 2, "2": 1}
    assert small["selections"]["wixqa"]["pilot"]["case_ids"] == wixqa["tuning"]["case_ids"][:2]
    assert json.loads(parts.dump(small)) == small and parts.dump(small).endswith(b"\n")


def test_opening_a_selection_keeps_the_rest_of_its_part_locked(small: dict[str, Any]) -> None:
    locked = small["bases"]["wixqa"]["parts"]["locked"]["case_ids"]

    assert parts.read(small, "wixqa", part="tuning") == parts.in_order(
        "wixqa", "question", ["wixqa-simulated-002", "wixqa-simulated-003", "wixqa-simulated-004"]
    )
    assert len(parts.read(small, "conditionalqa", selection="pilot")) == 4
    for base, part in (
        ("conditionalqa", "locked"),
        ("conditionalqa", "reserve"),
        ("wixqa", "locked"),
        ("wixqa", "excluded"),
    ):
        with pytest.raises(parts.Locked, match="locked until acceptance 4.1"):
            parts.read(small, base, part=part)
    small["selections"]["wixqa"]["acceptance"] = {
        "rule": {"part": "locked", "questions": 1},
        "cases_sha256": parts.digest(locked[:1]),
        "case_ids": locked[:1],
    }
    with pytest.raises(parts.Locked):
        parts.read(small, "wixqa", selection="acceptance")
    small["opened"].append({"base": "wixqa", "part": "locked", "by": "acceptance 4.1"})
    with pytest.raises(parts.Locked):
        parts.read(small, "wixqa", selection="acceptance")
    small["opened"] = [{
        "base": "wixqa", "part": "locked", "selection": "acceptance",
        "cases_sha256": parts.digest(locked[:1]), "by": "acceptance 4.1",
    }]
    assert parts.read(small, "wixqa", selection="acceptance") == locked[:1]
    with pytest.raises(parts.Locked):
        parts.read(small, "wixqa", part="locked")
    # The entry opens the part it names and no other.
    for base, part in (("wixqa", "excluded"), ("conditionalqa", "locked")):
        with pytest.raises(parts.Locked):
            parts.read(small, base, part=part)
    with pytest.raises(ValueError, match="name a part or a selection"):
        parts.read(small, "wixqa")
    with pytest.raises(ValueError, match="name a part or a selection"):
        parts.read(small, "wixqa", part="tuning", selection="pilot")


def test_verify_holds_the_registered_parts_to_the_cases(small: dict[str, Any]) -> None:
    for base, cases in CASES.items():
        report = parts.verify(small, base, cases)
        # The report of the check is counts and digests: it lists no id and holds no question.
        written = json.dumps(report)
        assert "case_ids" not in written and cases[0]["case_id"] not in written
        assert report["cases"] == len(cases) and report["seed"] == 20260925
    assert parts.verify(small, "conditionalqa", CONDITIONALQA)["shared_between_parts"] == {
        "tuning/locked": 0,
        "tuning/reserve": 0,
        "locked/reserve": 0,
    }
    assert parts.verify(small, "wixqa", WIXQA)["shared_between_parts"] == {"tuning/locked": 0}

    moved = copy.deepcopy(small)
    wixqa = moved["bases"]["wixqa"]["parts"]
    wixqa["tuning"]["case_ids"].append(wixqa["excluded"]["case_ids"].pop())
    with pytest.raises(ValueError, match="not those the rules give"):
        parts.verify(moved, "wixqa", WIXQA)
    with pytest.raises(ValueError, match="not those the rules give"):
        parts.verify(small, "wixqa", WIXQA[:-1])


def test_the_checks_of_the_registered_ids_do_not_rest_on_the_builder(
    small: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the rebuilding check out of the way, the ids alone still give a fault away."""
    edited: dict[str, Any] = {}

    def as_registered(
        base: str, cases: Any, cases_sha256: str, *, selection_rules: Any = None
    ) -> tuple[dict, dict]:
        return edited["bases"][base], edited["selections"].get(base, {})

    monkeypatch.setattr(parts, "build_base", as_registered)

    edited = copy.deepcopy(small)
    pages = edited["bases"]["conditionalqa"]["parts"]
    pages["tuning"]["case_ids"].append(pages["locked"]["case_ids"].pop())
    with pytest.raises(ValueError, match="parts share a document: {'tuning/locked': 1"):
        parts.verify(edited, "conditionalqa", CONDITIONALQA)

    edited = copy.deepcopy(small)
    articles = edited["bases"]["wixqa"]["parts"]
    articles["tuning"]["case_ids"].append(articles["excluded"]["case_ids"].pop())
    with pytest.raises(ValueError, match="parts share a document: {'tuning/locked': 1}"):
        parts.verify(edited, "wixqa", WIXQA)

    edited = copy.deepcopy(small)
    pages = edited["bases"]["conditionalqa"]["parts"]
    pages["reserve"]["case_ids"].append(pages["locked"]["case_ids"][0])
    with pytest.raises(ValueError, match="stands in two parts"):
        parts.verify(edited, "conditionalqa", CONDITIONALQA)

    edited = copy.deepcopy(small)
    edited["bases"]["wixqa"]["parts"]["tuning"]["case_ids"].append("wixqa-simulated-999")
    with pytest.raises(ValueError, match="in no case file"):
        parts.verify(edited, "wixqa", WIXQA)

    edited = copy.deepcopy(small)
    edited["selections"]["wixqa"]["pilot"]["case_ids"][0] = "wixqa-expertwritten-000"
    with pytest.raises(ValueError, match="the selection 'pilot' leaves its part"):
        parts.verify(edited, "wixqa", WIXQA)


def test_a_registration_of_other_rules_is_not_read(small: dict[str, Any], tmp_path: Path) -> None:
    path = tmp_path / "parts.json"
    path.write_bytes(parts.dump(small))
    assert parts.registration(path) == small

    for change in (
        lambda value: value.update(seed=1),
        lambda value: value["rules"].update(wixqa="every question is open"),
        lambda value: value["bases"]["wixqa"]["parts"]["locked"].update(access="open"),
        lambda value: value["bases"]["conditionalqa"]["parts"].pop("reserve"),
    ):
        edited = copy.deepcopy(small)
        change(edited)
        path.write_bytes(parts.dump(edited))
        with pytest.raises(ValueError, match="the registration names"):
            parts.registration(path)


@pytest.fixture
def host(small: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """The small bases converted on a host, with the two registrations that describe them."""
    converted = json.loads(bases.REGISTRATION.read_text(encoding="utf-8"))
    for base, cases in CASES.items():
        folder = tmp_path / base
        folder.mkdir()
        (folder / "cases.jsonl").write_bytes(_file(cases))
        converted["bases"][base]["converted"]["cases_sha256"] = bases.sha256(_file(cases))
    (tmp_path / "bases.json").write_text(json.dumps(converted), encoding="utf-8")
    (tmp_path / "parts.json").write_bytes(parts.dump(small))
    monkeypatch.setattr(bases, "REGISTRATION", tmp_path / "bases.json")
    monkeypatch.setattr(parts, "REGISTRATION", tmp_path / "parts.json")
    return SimpleNamespace(root=tmp_path, registered=small)


def test_the_parts_step_writes_a_report_of_counts(host: SimpleNamespace) -> None:
    out = host.root / "wixqa"

    report = external_base.parts_step("wixqa", out)

    assert json.loads((out / "parts-report.json").read_text(encoding="utf-8")) == report
    assert report == parts.verify(host.registered, "wixqa", WIXQA)
    assert report["parts"]["excluded"]["cases"] == 2 and "simulated" not in json.dumps(report)
    (out / "cases.jsonl").write_bytes(_file(WIXQA[:-1]))
    with pytest.raises(ValueError, match="differs from the registered conversion"):
        external_base.parts_step("wixqa", out)
    with pytest.raises(ValueError, match="differs from the registered conversion"):
        parts.main(["--data", str(host.root)])  # the builder reads no other file either
    with pytest.raises(SystemExit, match="unregistered base"):
        external_base.parts_step("hotpotqa", out)


def test_the_builder_rebuilds_the_registration_byte_for_byte(
    host: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    registration = host.root / "parts.json"
    written = registration.read_bytes()

    assert parts.main(["--data", str(host.root)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert sorted(printed) == ["conditionalqa", "multihoprag", "wixqa"]
    assert printed["wixqa"] == parts.verify(host.registered, "wixqa", WIXQA)
    registration.write_bytes(written.replace(b'"opened": []', b'"opened": [ ]'))
    assert parts.main(["--data", str(host.root)]) == 1
    assert "differs" in capsys.readouterr().out
    assert parts.main(["--data", str(host.root), "--write"]) == 0
    assert registration.read_bytes() == written


@pytest.fixture
def extended(host: SimpleNamespace) -> SimpleNamespace:
    for base in CASES:
        if base in SMALL_PILOT:
            baseline = copy.deepcopy(host.registered["selections"][base]["pilot"])
        else:
            baseline = copy.deepcopy(host.registered["bases"][base]["parts"]["advisory"])
            baseline.pop("access")
            baseline = {"rule": {"part": "advisory", "questions": baseline["cases"]}, **baseline}
        host.registered["selections"].setdefault(base, {})["baseline"] = baseline
    (host.root / "parts.json").write_bytes(parts.dump(host.registered))
    return host


@pytest.mark.parametrize("base", CASES)
def test_later_selections_are_verified_and_exported(extended: SimpleNamespace, base: str) -> None:
    expected = extended.registered["selections"][base]["baseline"]

    verified = parts.verify(extended.registered, base, CASES[base])
    assert verified["selections"]["baseline"] == {
        key: value for key, value in expected.items() if key != "case_ids"
    }
    report = external_base.select_step(base, extended.root / base, "baseline")
    written = (extended.root / base / "selections" / "baseline.questions.jsonl").read_bytes()
    rows = [json.loads(line) for line in written.splitlines()]
    by_id = {case["case_id"]: case for case in CASES[base]}
    assert rows == [
        {"case_id": case_id, "query": by_id[case_id]["query"]} for case_id in expected["case_ids"]
    ]
    assert report["cases_sha256"] == expected["cases_sha256"]
    assert report["questions_sha256"] == bases.sha256(written)


def test_the_builder_preserves_later_selections_byte_for_byte(
    extended: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    path = extended.root / "parts.json"
    written = path.read_bytes()

    for flags in ([], ["--write"]):
        assert parts.main(["--data", str(extended.root), *flags]) == 0
        report = json.loads(capsys.readouterr().out)
        assert all("baseline" in report[base]["selections"] for base in CASES)
        assert path.read_bytes() == written


@pytest.mark.parametrize("field", ["order", "rule", "cases", "cases_sha256", "clusters"])
def test_later_selections_must_match_their_rule_and_counts(
    extended: SimpleNamespace, field: str
) -> None:
    baseline = extended.registered["selections"]["wixqa"]["baseline"]
    if field == "order":
        baseline["case_ids"].reverse()
        baseline["cases_sha256"] = parts.digest(baseline["case_ids"])
    elif field == "rule":
        baseline["rule"]["questions"] += 1
    elif field == "cases_sha256":
        baseline[field] = "0" * 64
    else:
        baseline[field] += 1

    with pytest.raises(ValueError, match="not those the rules give"):
        parts.verify(extended.registered, "wixqa", WIXQA)


@pytest.mark.parametrize("change", ["remove", "replace"])
def test_later_selections_do_not_allow_changing_the_registered_pilot(
    extended: SimpleNamespace, change: str
) -> None:
    selections = extended.registered["selections"]["wixqa"]
    if change == "remove":
        selections.pop("pilot")
    else:
        pilot = copy.deepcopy(extended.registered["bases"]["wixqa"]["parts"]["tuning"])
        pilot.pop("access")
        selections["pilot"] = {"rule": {"part": "tuning", "questions": pilot["cases"]}, **pilot}

    with pytest.raises(ValueError, match="not those the rules give"):
        parts.verify(extended.registered, "wixqa", WIXQA)


def test_verifying_a_later_locked_selection_does_not_open_it(host: SimpleNamespace) -> None:
    acceptance = copy.deepcopy(host.registered["bases"]["wixqa"]["parts"]["locked"])
    acceptance.pop("access")
    host.registered["selections"]["wixqa"]["acceptance"] = {
        "rule": {"part": "locked", "questions": acceptance["cases"]}, **acceptance
    }
    (host.root / "parts.json").write_bytes(parts.dump(host.registered))

    report = parts.verify(host.registered, "wixqa", WIXQA)
    assert report["selections"]["acceptance"]["cases"] == 2
    assert host.registered["opened"] == []
    with pytest.raises(parts.Locked):
        external_base.select_step("wixqa", host.root / "wixqa", "acceptance")
    assert not (host.root / "wixqa" / "selections").exists()


@pytest.fixture
def permitted(host: SimpleNamespace) -> SimpleNamespace:
    _, selections = parts.build_base(
        "wixqa", WIXQA, host.registered["bases"]["wixqa"]["cases_sha256"],
        selection_rules={
            "acceptance": {"part": "locked", "questions": 1},
            "larger": {"part": "locked", "questions": 2},
        },
    )
    host.registered["selections"]["wixqa"] = selections
    host.registered["opened"] = [{
        "base": "wixqa", "part": "locked", "selection": "acceptance",
        "cases_sha256": selections["acceptance"]["cases_sha256"], "by": "acceptance 4.1",
    }]
    (host.root / "parts.json").write_bytes(parts.dump(host.registered))
    return host


def test_export_reads_the_permitted_selection_and_refuses_other_selections(
    permitted: SimpleNamespace,
) -> None:
    out = permitted.root / "wixqa"
    chosen = permitted.registered["selections"]["wixqa"]["acceptance"]
    report = external_base.select_step("wixqa", out, "acceptance")
    written = (out / "selections" / "acceptance.questions.jsonl").read_bytes()
    assert [json.loads(line)["case_id"] for line in written.splitlines()] == chosen["case_ids"]
    assert report["cases"] == 1 and report["cases_sha256"] == chosen["cases_sha256"]
    assert not parts.is_open(permitted.registered, "wixqa", "locked")

    permitted.registered["selections"]["wixqa"]["another"] = copy.deepcopy(chosen)
    (permitted.root / "parts.json").write_bytes(parts.dump(permitted.registered))
    for selection in ("larger", "another"):
        with pytest.raises(parts.Locked):
            external_base.select_step("wixqa", out, selection)
        assert not (out / "selections" / f"{selection}.questions.jsonl").exists()


@pytest.mark.parametrize("flags", [[], ["--write"]], ids=["verify", "write"])
def test_the_builder_preserves_selection_permits(
    permitted: SimpleNamespace, flags: list[str],
) -> None:
    path = permitted.root / "parts.json"
    written = path.read_bytes()
    assert parts.main(["--data", str(permitted.root), *flags]) == 0
    assert path.read_bytes() == written
    registered = parts.registration()
    assert parts.read(registered, "wixqa", selection="acceptance") == permitted.registered[
        "selections"
    ]["wixqa"]["acceptance"]["case_ids"]
    with pytest.raises(parts.Locked):
        parts.read(registered, "wixqa", selection="larger")


@pytest.mark.parametrize(
    "change", ["legacy", "selection", "digest", "by", "replacement", "expanded", "reordered"]
)
def test_export_refuses_an_incomplete_or_stale_selection_permit(
    permitted: SimpleNamespace, change: str,
) -> None:
    entry = permitted.registered["opened"][0]
    chosen = permitted.registered["selections"]["wixqa"]["acceptance"]
    locked = permitted.registered["bases"]["wixqa"]["parts"]["locked"]["case_ids"]
    if change == "legacy":
        entry.pop("selection")
        entry.pop("cases_sha256")
    elif change == "selection":
        entry["selection"] = "larger"
    elif change == "digest":
        entry["cases_sha256"] = "0" * 64
    elif change == "by":
        entry["by"] = "development"
    elif change == "replacement":
        chosen["case_ids"] = locked[1:]
    else:
        chosen.update(copy.deepcopy(permitted.registered["selections"]["wixqa"]["larger"]))
        if change == "reordered":
            entry["cases_sha256"] = chosen["cases_sha256"]
            chosen["case_ids"].reverse()
            chosen["cases_sha256"] = parts.digest(chosen["case_ids"])
    (permitted.root / "parts.json").write_bytes(parts.dump(permitted.registered))

    with pytest.raises(parts.Locked):
        parts.read(permitted.registered, "wixqa", selection="acceptance")
    with pytest.raises(parts.Locked):
        external_base.select_step("wixqa", permitted.root / "wixqa", "acceptance")
    assert not (permitted.root / "wixqa" / "selections").exists()


def test_the_select_step_writes_the_questions_of_an_open_selection_only(
    host: SimpleNamespace,
) -> None:
    out = host.root / "conditionalqa"

    report = external_base.select_step("conditionalqa", out, "pilot")

    pilot = host.registered["selections"]["conditionalqa"]["pilot"]
    written = (out / "selections" / "pilot.questions.jsonl").read_bytes()
    rows = [json.loads(line) for line in written.decode("utf-8").splitlines()]
    # The ids in the registered order with their questions, and none of the labels.
    assert [row["case_id"] for row in rows] == pilot["case_ids"]
    assert all(
        row == {"case_id": row["case_id"], "query": f"scenario and question {number}"}
        for row in rows
        for number in [row["case_id"].rsplit("-", 1)[1]]
    )
    assert report == {
        "base": "conditionalqa",
        "selection": "pilot",
        "part": "tuning",
        "cases": 4,
        "cases_sha256": pilot["cases_sha256"],
        "questions_sha256": bases.sha256(written),
    }
    with pytest.raises(SystemExit, match="unregistered selection of conditionalqa: baseline"):
        external_base.select_step("conditionalqa", out, "baseline")

    # A selection of a locked part is registered, and still nothing of it is written.
    registered = copy.deepcopy(host.registered)
    locked = registered["bases"]["wixqa"]["parts"]["locked"]["case_ids"]
    registered["selections"]["wixqa"]["acceptance"] = {
        "rule": {"part": "locked", "questions": 1},
        "cases": 1,
        "cases_sha256": parts.digest(locked[:1]),
        "case_ids": locked[:1],
    }
    (host.root / "parts.json").write_bytes(parts.dump(registered))
    with pytest.raises(parts.Locked):
        external_base.select_step("wixqa", host.root / "wixqa", "acceptance")
    assert not (host.root / "wixqa" / "selections").exists()


def test_the_registration_is_whole_and_no_locked_part_is_opened() -> None:
    """The committed file, without the bases: what its own ids and digests can show."""
    registered = parts.registration()
    converted = bases.registration()["bases"]

    # Acceptance 4.1 alone opens a part, by a commit that changes this line with the file.
    assert registered["opened"] == []
    assert registered["registered"] == "2026-10-05" and registered["schema_version"] == 1
    assert sorted(registered["selections"]) == ["conditionalqa", "wixqa"]
    found = {}
    for base, block in registered["bases"].items():
        assert block["cases"] == converted[base]["converted"]["cases"]
        assert block["cases_sha256"] == converted[base]["converted"]["cases_sha256"]
        listed = [case_id for part in block["parts"].values() for case_id in part["case_ids"]]
        assert len(set(listed)) == len(listed) == block["cases"] - block["in_no_part"]
        for name, part in block["parts"].items():
            assert part["cases"] == len(part["case_ids"])
            assert part["cases_sha256"] == parts.digest(part["case_ids"])
            found[base, name] = (part["cases"], part["cases_sha256"])
    assert found == REGISTERED

    pages = registered["bases"]["conditionalqa"]["parts"]
    assert [part["documents"] for part in pages.values()] == [165, 165, 165]
    assert all(part["clusters"] == 165 for part in pages.values())
    assert {name: part["primary"] for name, part in pages.items()} == {
        "tuning": 844,
        "locked": 823,
        "reserve": 850,
    }
    assert sum(part["not_answerable"] for part in pages.values()) == 105
    for part in pages.values():
        counted, several = part["primary_by_document"], part["several_sections_by_document"]
        assert len(counted) == len(several) == part["documents"]
        assert sum(counted) == part["primary"]
        assert dict(sorted(Counter(str(size) for size in counted if size).items())) == dict(
            sorted(part["cluster_sizes"].items())
        )
        assert sum(several) == part["primary_with_evidence_in_several_sections"]
        assert sum(size > 0 for size in several) == part["clusters_with_a_several_section_question"]
        assert all(some <= every for some, every in zip(several, counted, strict=True))
    assert all(
        re.fullmatch(r"conditionalqa-(train|dev)-\d+", case_id)
        for part in pages.values()
        for case_id in part["case_ids"]
    )

    articles = registered["bases"]["wixqa"]["parts"]
    assert sorted(articles["locked"]["case_ids"]) == [
        f"wixqa-expertwritten-{number:03d}" for number in range(200)
    ]
    assert sorted(articles["tuning"]["case_ids"] + articles["excluded"]["case_ids"]) == [
        f"wixqa-simulated-{number:03d}" for number in range(200)
    ]
    assert (articles["tuning"]["clusters"], articles["locked"]["clusters"]) == (109, 154)
    advisory = registered["bases"]["multihoprag"]["parts"]["advisory"]
    assert advisory["questions_by_type"] == {"inference_query": 816, "null_query": 301}
    # Parts drawn by questions stand in the registered order, which the ids alone give.
    for base, part in (("multihoprag", advisory), *(("wixqa", part) for part in articles.values())):
        assert part["case_ids"] == parts.in_order(base, "question", part["case_ids"])

    for base, (cases, sha256) in PILOTS.items():
        pilot = registered["selections"][base]["pilot"]
        assert pilot["rule"] == parts.PILOT[base] and pilot["rule"]["part"] == "tuning"
        assert (len(pilot["case_ids"]), pilot["cases"], pilot["cases_sha256"]) == (
            cases,
            cases,
            sha256,
        )
        assert pilot["cases_sha256"] == parts.digest(pilot["case_ids"])
        tuning = registered["bases"][base]["parts"]["tuning"]["case_ids"]
        assert [case_id for case_id in tuning if case_id in set(pilot["case_ids"])] == pilot[
            "case_ids"
        ]
        assert parts.read(registered, base, selection="pilot") == pilot["case_ids"]
    assert (
        registered["selections"]["wixqa"]["pilot"]["case_ids"]
        == articles["tuning"]["case_ids"][:40]
    )
    page_pilot = registered["selections"]["conditionalqa"]["pilot"]
    assert (page_pilot["documents"], page_pilot["cluster_sizes"]) == (25, {"2": 25})
    for base, part in (
        ("conditionalqa", "locked"),
        ("conditionalqa", "reserve"),
        ("wixqa", "locked"),
        ("wixqa", "excluded"),
    ):
        with pytest.raises(parts.Locked):
            parts.read(registered, base, part=part)
