"""The answer prompt V5, the judge's first step: v5_core.py.

docs/specs/answer-prompt-v5.md, «Amendment 1, 2026-10-27: the judge in two steps». The core reads
M1 and the bridges of WixQA and ConditionalQA as v5_record.py reads them, and its step stops only
where no grade of the rest could make the spec's table adopt V5.
"""

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.test_answer_prompt_v5 import ROOT, TOOLS, _edit, _world

DIRECTIONS = ("falls", "rises", "not detected")


@pytest.fixture(scope="module")
def core() -> Iterator[Any]:
    """The tool, loaded from its file; the sys.path entries it adds are taken back."""
    saved = list(sys.path)
    spec = importlib.util.spec_from_file_location("v5_core", TOOLS / "v5_core.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    sys.path[:] = saved


def _rest(stand: Path, folders: dict, keys: tuple[str, ...]) -> list[Path]:
    """The records the core does not read: M2, aircargo's plans and bridge, other bases."""
    v4_dir = folders["v4_dir"]
    paths = [stand / "v5-bridge-aircargo.json", stand / "v5-bridge-aircargo.cases.jsonl"]
    for key in ("wixqa", "conditionalqa", "aircargo"):
        parts = ("m1", "m2") if key not in keys else ("m2",)
        for side, folder in (("v4", v4_dir), ("v5", stand)):
            for part in parts:
                name = f"{side}-{key}-judge" if key == "aircargo" else f"{side}-{key}-judge-{part}"
                paths += [folder / f"{name}.json", folder / f"{name}.cases.jsonl"]
        if key not in keys and key != "aircargo":
            paths += [stand / f"v5-bridge-{key}.json", stand / f"v5-bridge-{key}.cases.jsonl"]
    return sorted(set(paths))


def test_the_core_reads_m1_and_the_bridges_as_the_record_does(core: Any, tmp_path: Path) -> None:
    vr = core.vr
    stand, folders = _world(vr, tmp_path)
    whole = vr.build(stand, **folders)
    for path in _rest(stand, folders, vr.BASES):
        path.unlink()

    got = core.core(stand, **folders)

    assert got["keys"] == ["wixqa", "conditionalqa"] and got["amendment"] == core.AMENDMENT
    assert got["primary"] == whole["primary"] and got["same_context"] == whole["same_context"]
    for key in vr.BASES:
        assert got["corpora"][key] == {
            name: numbers for name, numbers in whole["corpora"][key].items() if name != "m2"
        }
    assert got["environment"] == whole["environment"]
    assert set(got["tools"]) == {*vr.TOOLS, "v5_core.py"}
    assert not any("m2" in name or "aircargo-judge" in name for name in got["inputs"])
    assert "reports/answer-prompt-v5/4f48fed/v5-bridge-conditionalqa.json" in got["inputs"]
    assert set(got["plans"]) == {
        f"{prefix}-{key}{suffix}"
        for key in vr.BASES
        for prefix, suffix in (("v4", "-judge-m1"), ("v5", "-judge-m1"), ("v5-bridge", ""))
    }
    assert got["step"] == {
        "step": "go on",
        "decision": None,
        "v5_replaces_v4": False,
        "reasons": ["fewer bad answers: M2 and aircargo are graded, v5_record.py decides"],
        "harm": [],
        "not_counted": {},
    }

    out = tmp_path / "core.json"
    assert core.main([str(stand), str(out)], **folders) == 0
    assert b"\r" not in out.read_bytes() and json.loads(out.read_text("utf-8")) == got


def test_one_base_judged_waits_and_its_harm_stops(core: Any, tmp_path: Path) -> None:
    vr = core.vr
    stand, folders = _world(vr, tmp_path)
    for path in _rest(stand, folders, ("wixqa",)):
        path.unlink()

    got = core.core(stand, ("wixqa",), **folders)
    assert got["keys"] == ["wixqa"] and got["primary"]["keys"] == ["wixqa"]
    assert (got["step"]["step"], got["step"]["decision"]) == ("wait", None)
    assert got["step"]["reasons"] == ["not judged yet: conditionalqa"]

    # V4 answered all ten well, V5 all ten badly: WixQA's harm stops before ConditionalQA.
    def grade(value: str) -> Any:
        return lambda rows: [{**row, "grade": value} for row in rows]

    _edit(folders["v4_dir"] / "v4-wixqa-judge-m1.cases.jsonl", grade("good"))
    _edit(stand / "v5-bridge-wixqa.cases.jsonl", grade("good"))
    _edit(stand / "v5-wixqa-judge-m1.cases.jsonl", grade("bad"))
    got = core.core(stand, ("wixqa",), **folders)["step"]
    assert (got["step"], got["decision"], got["v5_replaces_v4"]) == ("stop", "not adopted", False)
    assert (
        got["reasons"]
        == got["harm"]
        == [
            "wixqa: the bad share rises",
            "wixqa: the good share falls, the bad share does not",
        ]
    )

    _edit(stand / "v5-bridge-wixqa.json", lambda data: {**data, "status": "NOT_EVIDENCE"})
    got = core.core(stand, ("wixqa",), **folders)["step"]
    assert (got["step"], got["decision"], got["harm"]) == ("stop", "NOT_EVIDENCE", [])
    assert got["reasons"] == ["a plan not counted: v5-bridge-wixqa"]


def test_the_core_refuses_what_the_record_refuses(core: Any, tmp_path: Path) -> None:
    vr = core.vr
    stand, folders = _world(vr, tmp_path)
    plan = stand / "v5-wixqa-judge-m1.json"
    saved = plan.read_bytes()
    _edit(plan, lambda data: {**data, "provenance": {**data["provenance"], "adapter_sha256": "x"}})
    with pytest.raises(SystemExit, match="read by another judge than the registered"):
        core.core(stand, **folders)
    plan.write_bytes(saved)
    _edit(
        stand / "v5-wixqa-judge-m1.cases.jsonl",
        lambda rows: [{**row, "prompt_sha256": "0" * 64} for row in rows],
    )
    with pytest.raises(SystemExit, match="graded other prompts than the replay's"):
        core.core(stand, **folders)
    with pytest.raises(SystemExit, match="--keys names some of wixqa,conditionalqa"):
        core.core(stand, ("aircargo",), **folders)
    with pytest.raises(SystemExit, match="usage"):
        core.main([str(stand), "a", "b"], **folders)


def _numbers(bad: str, good: str, guard: str | None = None) -> dict:
    numbers: dict[str, Any] = {"bad": {"direction": bad}, "good": {"direction": good}}
    if guard is not None:
        numbers["declines_without_answer"] = {"direction": guard}
    return numbers


def _outcomes(vr: Any, primary: dict, corpora: dict, readable: list, not_counted: dict) -> set:
    """The table's outcomes over every grade of the rest: aircargo's and M2's."""
    found = set()
    for bad, good, recall, counted in itertools.product(
        DIRECTIONS, ("falls", "not detected"), (None, *DIRECTIONS), (True, False)
    ):
        rest = dict(not_counted)
        if not counted:
            rest["aircargo"] = ["v5-aircargo-judge"]
        found.add(
            vr.decision(
                primary,
                None if recall is None else {"direction": recall},
                {**corpora, "aircargo": _numbers(bad, good)},
                list(vr.KEYS),
                [*readable, *(["aircargo"] if counted else [])],
                rest,
            )["decision"]
        )
    return found


def test_a_stop_is_where_no_grade_of_the_rest_adopts_v5(core: Any) -> None:
    vr = core.vr
    steps = set()
    for pooled, w_bad, w_good, c_bad, c_good, guard in itertools.product(DIRECTIONS, repeat=6):
        corpora = {
            "wixqa": _numbers(w_bad, w_good),
            "conditionalqa": _numbers(c_bad, c_good, guard),
        }
        primary = {"keys": list(vr.BASES), "direction": pooled}
        for dropped in (None, *vr.BASES):
            readable = [key for key in vr.BASES if key != dropped]
            not_counted = {dropped: [f"v5-bridge-{dropped}"]} if dropped else {}
            got = core.step(primary, corpora, vr.BASES, readable, not_counted)
            outcomes = _outcomes(vr, primary, corpora, readable, not_counted)
            steps.add((got["step"], got["decision"]))
            assert not got["v5_replaces_v4"]
            if got["step"] == "stop":
                assert "adopted" not in outcomes and got["decision"] in outcomes
            else:
                assert got["step"] == "go on" and "adopted" in outcomes
    assert steps == {
        ("stop", "not adopted"),
        ("stop", "NOT_EVIDENCE"),
        ("go on", None),
    }
    # The stops' reasons, in the order of the step.
    falls = {"keys": list(vr.BASES), "direction": "falls"}
    calm = {key: _numbers("not detected", "not detected") for key in vr.BASES}
    assert core.step({**falls, "direction": "rises"}, calm, vr.BASES, list(vr.BASES), {})[
        "reasons"
    ] == ["pooled: the bad share rises"]
    assert core.step({**falls, "direction": "not detected"}, calm, vr.BASES, list(vr.BASES), {})[
        "reasons"
    ] == ["no gain"]
    unread = core.step(falls, calm, vr.BASES, ["wixqa"], {"conditionalqa": ["v4-x", "v5-y"]})
    assert unread["reasons"] == ["a plan not counted: v4-x, v5-y"]


def test_a_stop_on_the_first_base_holds_whatever_the_second_gives(core: Any) -> None:
    vr = core.vr
    for w_bad, w_good, counted in itertools.product(DIRECTIONS, DIRECTIONS, (True, False)):
        first = {"wixqa": _numbers(w_bad, w_good)}
        readable = ["wixqa"] if counted else []
        not_counted = {} if counted else {"wixqa": ["v5-bridge-wixqa"]}
        got = core.step(
            {"keys": ["wixqa"], "direction": w_bad}, first, ("wixqa",), readable, not_counted
        )
        if got["step"] == "wait":
            assert got["reasons"] == ["not judged yet: conditionalqa"]
            continue
        assert got["step"] == "stop"
        for pooled, c_bad, c_good, guard, second in itertools.product(
            DIRECTIONS, DIRECTIONS, DIRECTIONS, DIRECTIONS, (True, False)
        ):
            corpora = {**first, "conditionalqa": _numbers(c_bad, c_good, guard)}
            both = {**not_counted, **({} if second else {"conditionalqa": ["v5-bridge-x"]})}
            outcomes = _outcomes(
                vr,
                {"keys": list(vr.BASES), "direction": pooled},
                corpora,
                [*readable, *(["conditionalqa"] if second else [])],
                both,
            )
            assert "adopted" not in outcomes


def test_the_spec_registers_the_two_steps_and_this_reading(core: Any) -> None:
    spec = (ROOT / "docs/specs/answer-prompt-v5.md").read_text("utf-8")
    assert f"## {core.AMENDMENT}" in spec
    named = dict(
        re.findall(
            r"`((?:reports/answer-prompt-v5/tools/v5_core|tests/test_answer_prompt_v5_core)\.py)`,"
            r" SHA-256 `([0-9a-f]{64})`",
            spec,
        )
    )
    assert sorted(named) == [
        "reports/answer-prompt-v5/tools/v5_core.py",
        "tests/test_answer_prompt_v5_core.py",
    ]
    for path, digest in named.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
