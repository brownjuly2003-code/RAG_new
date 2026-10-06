"""The sample, the requests and the reference labels of plan slice 2.8.

The pool is rebuilt from the committed phase C artifacts and no model is asked: the labeller of
the stage tests is a stand-in that answers by a rule.
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from evaluation import isolated_request as isolated
from evaluation import nli_validation as nv
from evaluation.blinded_judge_clients import JudgeUnavailable
from scripts import generator_benchmark as benchmark
from scripts import nli_reference as ref

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/specs/semantic-precision-metrics.md"
SESSION = {
    "cli_version": "9.9.9",
    "model": isolated.MODEL,
    "loaded": {kind: [] for kind in isolated.LOADED},
    "builtin": {"plugins": [], "agents": []},
    "turns": 1,
    "context_tokens": 100,
}


@pytest.fixture(scope="module")
def pool() -> list[dict[str, Any]]:
    return nv.build_pool()


@pytest.fixture(scope="module")
def drawn(pool: list[dict[str, Any]]) -> dict[str, Any]:
    return nv.draw(pool)


def reply(label: str, **fields: Any) -> str:
    return json.dumps({"label": label, "flags": [], "passages": [], "reason": "why", **fields})


class Labeller:
    """A stand-in for the model: `rule` gives the reply text of a request text."""

    def __init__(self, rule: Callable[[str], str]) -> None:
        self.rule = rule
        self.seen: list[str] = []

    def grade(self, text: str) -> isolated.IsolatedReply:
        self.seen.append(text)
        return isolated.IsolatedReply(self.rule(text), isolated.MODEL, {}, 0.25, SESSION)


def planned(tmp_path: Path) -> Path:
    ref._write(tmp_path / ref.PLAN, ref.build_plan())
    return tmp_path


def test_the_pool_is_the_one_the_research_counted(pool: list[dict[str, Any]]) -> None:
    assert len(pool) == 656
    assert Counter(unit["source"] for unit in pool) == {"c1a": 516, "c1b": 140}
    assert Counter(unit["stratum"] for unit in pool) == {
        name: row[1] for name, row in nv.STRATA.items()
    }
    for name, _, held in nv.QUOTAS:
        assert sum(unit["flags"][name] for unit in pool) == held
    # The same text of the same question in both sources: 19 pairs, as the research has it.
    assert len(pool) - len({(unit["case_id"], unit["text"]) for unit in pool}) == 19
    assert [unit["claim_id"] for unit in pool] == sorted(unit["claim_id"] for unit in pool)
    for unit in pool:
        start, end = unit["span"]
        assert unit["answer"][start:end] == unit["text"]
        assert unit["claim_id"] == nv.claim_id(unit["source"], unit["case_id"], unit["text"])
        assert len(unit["contexts"]) == len(unit["nli_scores"]) == 5
        assert unit["families"] and max(unit["nli_scores"]) == pytest.approx(unit["nli_best"])


def test_the_units_are_the_lines_of_the_benchmark_splitter() -> None:
    answers = [
        case["answer"]
        for path, _ in nv.REPORTS.values()
        for run in json.loads((ROOT / path).read_text(encoding="utf-8"))["runs"]
        for case in run["cases"]
    ]
    answers += [
        "  1. First point. Second one!\r\n- третий пункт:\n\n   * four?  five\n",
        "Одна строка без точки",
        "",
    ]
    for answer in answers:
        spans = nv.claim_spans(answer)
        assert [text for text, _, _ in spans] == benchmark.split_material_claims(answer)
        assert all(answer[start:end] == text for text, start, end in spans)
    contexts = ["a" * 4000, "", "b" * 4000, "c"]
    for limit in (0, 5, 6000, 8001, 20000):
        assert nv.cut_contexts(contexts, limit) == benchmark._truncate_contexts(contexts, limit)


def test_a_changed_input_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    path, digest = nv.REPORTS["c1b"]
    monkeypatch.setitem(nv.REPORTS, "c1b", (path, digest[::-1]))
    with pytest.raises(ValueError, match="not the registered file"):
        nv.build_pool()


def test_the_sample_holds_the_sizes_the_cap_and_the_quotas(
    pool: list[dict[str, Any]], drawn: dict[str, Any]
) -> None:
    by_id = {unit["claim_id"]: unit for unit in pool}
    for name in ("drawn", "sample"):
        chosen = [by_id[key] for key in drawn[name]]
        assert Counter(unit["stratum"] for unit in chosen) == {
            stratum: row[2] for stratum, row in nv.STRATA.items()
        }
        assert max(Counter(unit["case_id"] for unit in chosen).values()) <= nv.CAP
    sample = [by_id[key] for key in drawn["sample"]]
    for flag, least, _ in nv.QUOTAS:
        assert sum(unit["flags"][flag] for unit in sample) >= least
    # A replacement stays inside its stratum and brings the flag in.
    assert drawn["replacements"]
    for row in drawn["replacements"]:
        out, came = by_id[row["out"]], by_id[row["in"]]
        assert out["stratum"] == came["stratum"] == row["stratum"]
        assert came["flags"][row["quota"]] and not out["flags"][row["quota"]]
        assert row["out"] in drawn["drawn"] and row["in"] not in drawn["drawn"]
    assert set(drawn["sample"]) == (
        set(drawn["drawn"]) - {row["out"] for row in drawn["replacements"]}
    ) | {row["in"] for row in drawn["replacements"]}
    # The order the pool is given in decides nothing.
    shuffled = list(pool)
    random.Random(7).shuffle(shuffled)
    assert nv.draw(shuffled) == drawn
    summary = nv.summary(pool, drawn["sample"])
    assert summary["units"] == 200 and summary["most_units_a_question"] <= nv.CAP
    assert summary["strata"]["a4"]["weight"] == pytest.approx(320 / 35)


def test_the_walk_looks_ahead_because_a_plain_one_ends_a_stratum_short(
    pool: list[dict[str, Any]],
) -> None:
    sizes = {name: row[2] for name, row in nv.STRATA.items()}
    whole = {name for name, row in nv.STRATA.items() if row[1] == row[2]}
    order = sorted(pool, key=lambda unit: nv._hash("nli_sample", unit["claim_id"]))
    cases: Counter[str] = Counter()
    strata: Counter[str] = Counter()
    for unit in sorted(order, key=lambda unit: unit["stratum"] not in whole):
        if strata[unit["stratum"]] < sizes[unit["stratum"]] and cases[unit["case_id"]] < nv.CAP:
            strata[unit["stratum"]] += 1
            cases[unit["case_id"]] += 1
    assert [name for name in sizes if strata[name] < sizes[name]] == ["a1"]
    # Two strata that want the four places of one question cannot both be filled.
    ahead = {("x", "q"): 4, ("y", "q"): 4, ("y", "r"): 1}
    assert nv._completable({"x": 4, "y": 1}, ahead, {})
    assert not nv._completable({"x": 4, "y": 2}, ahead, {})
    assert not nv._completable({"x": 4, "y": 1}, ahead, {"q": 1})
    assert nv._completable({"x": 3, "y": 1}, ahead, {"q": 1})
    assert nv._completable({}, {}, {})


def test_the_top_up_goes_on_in_the_first_order_under_the_cap(
    pool: list[dict[str, Any]], drawn: dict[str, Any]
) -> None:
    by_id = {unit["claim_id"]: unit for unit in pool}
    added = nv.top_up(pool, drawn["sample"])
    assert not set(added) & set(drawn["sample"])
    assert {by_id[key]["stratum"] for key in added} <= set(nv.TOP_UP_STRATA)
    both = Counter(by_id[key]["case_id"] for key in [*drawn["sample"], *added])
    assert max(both.values()) <= nv.CAP
    # The questions of the other units of the top-up strata are full: 24 units, not 50.
    assert len(added) == 24
    left = [
        unit
        for unit in pool
        if unit["stratum"] in nv.TOP_UP_STRATA
        and unit["claim_id"] not in {*drawn["sample"], *added}
    ]
    assert left and all(both[unit["case_id"]] == nv.CAP for unit in left)


def test_a_pair_of_both_sources_is_labelled_once(
    pool: list[dict[str, Any]], drawn: dict[str, Any]
) -> None:
    by_id = {unit["claim_id"]: unit for unit in pool}
    units = nv.labelling_units(pool, drawn["sample"])
    assert sorted(key for unit in units for key in unit["serves"]) == drawn["sample"]
    assert all(unit["new"] and unit["request_id"] == min(unit["serves"]) for unit in units)
    double = [unit for unit in units if len(unit["serves"]) > 1]
    assert len(units) == 198 and len(double) == 2
    for unit in double:
        first, second = (by_id[key] for key in unit["serves"])
        assert (first["case_id"], first["text"]) == (second["case_id"], second["text"])
        assert {first["source"], second["source"]} == {"c1a", "c1b"}
    # A unit of the top-up whose pair stage 1 labelled gets no request of its own.
    added = nv.top_up(pool, drawn["sample"])
    later = nv.labelling_units(pool, added, [unit["request_id"] for unit in units])
    served = [unit for unit in later if not unit["new"]]
    assert len(served) == 1 and served[0]["request_id"] in {unit["request_id"] for unit in units}


def test_the_control_shows_a_unit_beside_the_contexts_of_another_family(
    pool: list[dict[str, Any]], drawn: dict[str, Any]
) -> None:
    by_id = {unit["claim_id"]: unit for unit in pool}
    order = nv.control_order(pool, drawn["sample"])
    units = [by_id[key] for key in order]
    assert len(order) == 92 and {unit["stratum"] for unit in units} == set(nv.CONTROL_STRATA)
    assert order != nv.control_order(pool, drawn["sample"], "nli_control2")
    for index in range(nv.CONTROL_FIRST):
        partner = nv.control_partner(units, index, nv.CONTROL_FIRST)
        assert partner is not None and partner != index and partner < nv.CONTROL_FIRST
        assert units[partner]["case_id"] != units[index]["case_id"]
        assert not set(units[partner]["families"]) & set(units[index]["families"])
    twins = [dict(units[0]), dict(units[0], claim_id="other")]
    assert nv.control_partner(twins, 0, 2) is None
    # Twenty always; then on until ten are supported where they were retrieved.
    assert nv.control_drawn([True] * 92) == 20
    assert nv.control_drawn([True] * 9 + [False] * 11 + [False, True, True]) == 22
    assert nv.control_drawn([False] * 92) == 92
    assert nv.control_drawn([True] * 5) == 5


def test_a_request_holds_the_unit_in_its_answer_and_nothing_of_the_plan(
    pool: list[dict[str, Any]], drawn: dict[str, Any]
) -> None:
    by_id = {unit["claim_id"]: unit for unit in pool}
    instructions = nv.PROMPT_TEMPLATE.split("QUESTION")[0] + "".join(nv.LABEL_DEFINITIONS.values())
    assert not re.search(r"\b(pass|control|score|judge|nli|stratum|c\.1\w?)\b", instructions, re.I)
    for key in drawn["sample"]:
        unit = by_id[key]
        first = nv.request_text(unit, unit["contexts"], nv.request_id(key, 1))
        second = nv.request_text(unit, unit["contexts"], nv.request_id(key, 2))
        assert first.count(f"{nv.MARK_OPEN}{unit['text']}{nv.MARK_CLOSE}") == 1
        assert f"\nUNIT\n{unit['text']}\n" in first and unit["question"].strip() in first
        for text in (first, second):
            assert key not in text and nv.PASS_SUFFIX not in text
            assert all(context.strip() in text for context in unit["contexts"])
            assert all(definition in text for definition in nv.LABEL_DEFINITIONS.values())
        # The second pass is the same material in another order of labels and of contexts.
        assert first != second and sorted(first.split("\n")) == sorted(second.split("\n"))
        shown = nv.presentation(nv.request_id(key, 2), 5)
        assert shown["labels"] != [0, 1, 2, 3] and sorted(shown["labels"]) == [0, 1, 2, 3]
        assert shown["passages"] != [0, 1, 2, 3, 4] and sorted(shown["passages"]) == [0, 1, 2, 3, 4]
        places = [second.index(f"PASSAGE {place + 1}\n") for place in range(5)]
        assert places == sorted(places)
        assert second.index(unit["contexts"][shown["passages"][0]].strip()) > places[0]
    # A control request is a request like any other, with the contexts of its partner.
    unit, other = by_id[drawn["sample"][0]], by_id[drawn["sample"][-1]]
    control = nv.request_text(
        unit, other["contexts"], nv.request_id(unit["claim_id"], 1, control=True)
    )
    assert nv.CONTROL_PREFIX not in control and other["contexts"][0].strip() in control
    assert (
        control.split("PASSAGE 1")[0]
        == nv.request_text(unit, unit["contexts"], unit["claim_id"]).split("PASSAGE 1")[0]
    )


def test_the_prompt_is_registered_in_the_spec() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    assert re.findall(r"Prompt SHA-256 \(rubric nli-reference/v1\): `([0-9a-f]{64})`", spec) == [
        nv.PROMPT_SHA256
    ]
    assert re.findall(
        r"System prompt SHA-256 \(rubric nli-reference/v1\): `([0-9a-f]{64})`", spec
    ) == [nv.SYSTEM_PROMPT_SHA256]
    assert nv.prompt_sha256() == nv.PROMPT_SHA256
    settings = isolated.settings(nv.SYSTEM_PROMPT)
    assert settings["system_prompt_sha256"] == nv.SYSTEM_PROMPT_SHA256
    assert (settings["model"], settings["effort"]) == ("claude-opus-5-5", "max")


def test_a_plan_is_not_made_with_another_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(nv.LABEL_DEFINITIONS, "PARTIAL", "PARTIAL - anything in between.")
    with pytest.raises(ValueError, match="the prompt is not the registered one"):
        ref.build_plan()


def test_a_reply_is_read_in_its_form() -> None:
    read = nv.parse_reply(
        'Here it is:\n{"label": "partial", "flags": ["outside", "MULTI"], "passages": [3, 1],'
        ' "reason": " One item is in no passage. "}'
    )
    assert read == {
        "label": "PARTIAL",
        "flags": ["MULTI", "OUTSIDE"],
        "passages": [1, 3],
        "reason": "One item is in no passage.",
    }
    assert nv.parse_reply('{"label": "NOT_CLAIM", "reason": "An introducing line."}')["flags"] == []
    for bad in (
        "SUPPORTED",
        reply("SUPPORTED") + reply("PARTIAL"),
        reply("MOSTLY"),
        reply(7),
        reply("SUPPORTED", flags="MULTI"),
        reply("SUPPORTED", flags=["AMBIGUOUS"]),
        reply("SUPPORTED", passages=[0]),
        reply("SUPPORTED", passages=[6]),
        reply("SUPPORTED", passages=[2, 2]),
        reply("SUPPORTED", passages=[True]),
        reply("SUPPORTED", reason=" "),
        '{"label": "SUPPORTED", "label": "PARTIAL", "reason": "twice"}',
    ):
        with pytest.raises(nv.ReplyFormatError):
            nv.parse_reply(bad)


def test_the_numbers_of_a_reply_come_back_to_the_stored_contexts() -> None:
    request = nv.request_id("ab" * 32, 2)
    shown = nv.presentation(request, 5)["passages"]
    cited = nv.cited_contexts({"passages": [1, 5]}, request)
    assert cited == sorted([shown[0], shown[4]])
    assert nv.cited_contexts({"passages": [1, 5]}, nv.request_id("ab" * 32, 1)) == [0, 4]
    # An order the hashes leave as it was is turned by one place: the second order differs.
    assert nv.second_order("r", "k", ["only"]) == [0]
    for name in map(str, range(400)):
        order = nv.second_order(name, "label", nv.LABELS)
        assert order != [0, 1, 2, 3] and sorted(order) == [0, 1, 2, 3]


def test_two_passes_make_a_reference_label() -> None:
    assert nv.reference("SUPPORTED", "SUPPORTED") == {"state": "stable", "label": "supported"}
    assert nv.reference("PARTIAL", "UNSUPPORTED") == {"state": "stable", "label": "not_supported"}
    assert nv.reference("NOT_CLAIM", "NOT_CLAIM") == {"state": "stable", "label": "not_claim"}
    assert nv.reference("SUPPORTED", "PARTIAL") == {"state": "unstable", "label": None}
    assert nv.reference(None, "SUPPORTED") == {"state": "invalid", "label": None}


def test_kappa_and_its_interval_by_question() -> None:
    assert nv.cohen_kappa([("a", "a"), ("b", "b")]) == pytest.approx(1.0)
    assert nv.cohen_kappa([("a", "a"), ("a", "b"), ("b", "a"), ("b", "b")]) == pytest.approx(0.0)
    assert nv.cohen_kappa([("a", "a"), ("a", "a")]) is None and nv.cohen_kappa([]) is None
    # 20 + 15 agreed of 50, margins 25/25 and 30/20: kappa = (0.7 - 0.5) / 0.5.
    pairs = [("s", "s")] * 20 + [("s", "n")] * 5 + [("n", "s")] * 10 + [("n", "n")] * 15
    assert nv.cohen_kappa(pairs) == pytest.approx(0.4)
    rows = [(f"q{index // 2}", left, right) for index, (left, right) in enumerate(pairs)]
    interval = nv.kappa_interval(rows)
    assert interval == nv.kappa_interval(rows)
    assert interval["kappa"] == pytest.approx(0.4) and interval["questions"] == 25
    low, high = interval["ci95"]
    assert low < 0.4 < high and interval["undefined_resamples"] == 0
    constant = nv.kappa_interval([("q", "s", "s")] * 3)
    assert constant["ci95"] is None and constant["undefined_resamples"] == nv.RESAMPLES


def units_of(labels: list[tuple[str | None, str | None]]) -> list[dict[str, Any]]:
    return [
        {"case_id": f"q{index}", "serves": 1, "first": first, "second": second}
        for index, (first, second) in enumerate(labels)
    ]


def controls_of(fooled: int, read: int = 10) -> list[dict[str, Any]]:
    return [
        {
            "partner": True,
            "own": {"state": "stable", "label": "supported"},
            "first": "SUPPORTED" if index < fooled else "UNSUPPORTED",
            "second": "SUPPORTED" if index < fooled else "NOT_CLAIM",
        }
        for index in range(read)
    ]


def test_the_stability_bound_names_what_failed() -> None:
    steady = [("SUPPORTED", "SUPPORTED")] * 60 + [("UNSUPPORTED", "PARTIAL")] * 40
    passed = nv.stability(units_of(steady), controls_of(1))
    assert passed["failures"] == [] and not passed["ambiguous"]
    assert (passed["stable"], passed["unstable"], passed["invalid"]) == (100, 0, 0)
    assert passed["control"]["read"] == 10 and passed["control"]["supported_in_both_passes"] == 1
    # More than a tenth of the sample without a stable label: unstable and invalid count alike.
    shaky = steady[:89] + [("SUPPORTED", "PARTIAL")] * 6 + [(None, "SUPPORTED")] * 5
    failed = nv.stability(units_of(shaky), controls_of(0))
    assert "unstable_share" in failed["failures"] and failed["not_stable_share"] == 0.11
    assert (failed["unstable"], failed["invalid"]) == (6, 5)
    # Stable on ninety in a hundred and still a kappa whose lower bound is under the bar.
    skewed = [("SUPPORTED", "SUPPORTED")] * 90 + [("SUPPORTED", "UNSUPPORTED")] * 5
    skewed += [("UNSUPPORTED", "SUPPORTED")] * 5
    assert nv.stability(units_of(skewed), controls_of(0))["failures"] == ["pass_kappa"]
    # More than a tenth of the read control units called supported twice.
    assert nv.stability(units_of(steady), controls_of(2))["failures"] == ["control"]
    # Under ten read units the control bounds nothing; a unit not supported in its own
    # contexts, or without a partner, is not read.
    few = controls_of(9, 9) + [
        {**controls_of(1, 1)[0], "own": {"state": "stable", "label": "not_claim"}},
        {**controls_of(1, 1)[0], "partner": False},
    ]
    unread = nv.stability(units_of(steady), few)
    assert unread["failures"] == [] and unread["control"]["bounds"] is False
    assert unread["control"] | {"drawn": 11, "read": 9, "without_partner": 1} == unread["control"]
    # A pair of both sources counts twice in the share and once in kappa.
    double = units_of(steady)
    double[0]["serves"] = 2
    counted = nv.stability(double, controls_of(0))
    assert counted["sample_units"] == 101 and counted["pass_kappa"]["units"] == 100


def test_the_stages_run_from_the_plan_to_the_labels(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = planned(tmp_path)
    plan = ref.load_plan(out)
    assert len(plan["requests"]) == 2 * 198 + 2 * 20 and plan["top_up_available"] == 24
    assert [request["request_id"] for request in plan["requests"]] == sorted(
        (request["request_id"] for request in plan["requests"]), key=nv.sending_order
    )
    assert Counter((request["kind"], request["pass"]) for request in plan["requests"]) == {
        ("unit", 1): 198,
        ("unit", 2): 198,
        ("control", 1): 20,
        ("control", 2): 20,
    }
    # The plan names units and requests and holds the text of none.
    assert {key for request in plan["requests"] for key in request} == {
        "request_id",
        "kind",
        "pass",
        "stage",
        "shows",
        "contexts_of",
        "serves",
        "request_sha256",
    }
    assert set(plan["sample"][0]) == {"claim_id", "source", "case_id", "stratum"}
    assert plan["route"]["effort"] == "max" and plan["route"]["model"] == isolated.MODEL
    with pytest.raises(ValueError, match="stage 1 is not complete"):
        ref.next_stage(out)
    # Every unit supported: under forty not supported, so the top-up is listed.
    labeller = Labeller(lambda text: reply("SUPPORTED", passages=[2]))
    limited = ref.send(out, client=labeller, limit=5)
    assert (limited["valid"], limited["pending"], limited["sent"]) == (5, 431, 5)
    done = ref.send(out, client=labeller)
    assert (done["valid"], done["pending"], done["sent"]) == (436, 0, 431)
    assert sorted(labeller.seen) == sorted(set(labeller.seen))
    with pytest.raises(ValueError, match="stage 2 is not listed"):
        ref.derive(out)
    listed = ref.next_stage(out)
    assert (
        listed
        == ref.next_stage(out)
        == {
            "top_up_units": 24,
            "top_up_units_labelled_in_stage_1": 1,
            "control_units_added": 0,
            "control_units_without_partner": 0,
            "requests": 46,
        }
    )
    with pytest.raises(ValueError, match="requests wait"):
        ref.derive(out)
    assert ref.send(out, client=labeller)["sent"] == 46
    derived = ref.derive(out)
    assert (
        derived["counts"] | {"sample": 200, "top_up": 24, "labelling_units": 221}
        == (derived["counts"])
    )
    assert derived["counts"]["stable_not_supported"] == 0
    # A labeller that calls everything supported is caught by its control and by nothing else:
    # one label in both passes leaves kappa undefined, and that fails the bound too.
    assert derived["stability"]["failures"] == ["pass_kappa", "control"]
    assert (
        derived["stability"]["control"] | {"read": 20, "supported_in_both_passes": 20}
        == (derived["stability"]["control"])
    )
    labels = json.loads((out / ref.LABELS).read_text(encoding="utf-8"))
    assert len(labels["units"]) == 224 and sum(unit["top_up"] for unit in labels["units"]) == 24
    unit = labels["units"][0]
    assert unit["state"] == "stable" and unit["label"] == "supported"
    assert [entry["label"] for entry in unit["passes"]] == ["SUPPORTED", "SUPPORTED"]
    # Passage 2 of the second pass is another stored context than passage 2 of the first.
    assert unit["passes"][0]["contexts"] == [1]
    assert unit["passes"][1]["contexts"] == [
        nv.presentation(nv.request_id(unit["request_id"], 2), 5)["passages"][1]
    ]
    assert ref.check(out)["labels_derived"] is True
    # Before the labels are derived nothing printed names one.
    printed = capsys.readouterr().out
    assert "attempt 1: valid" in printed
    assert not any(label in printed for label in nv.LABELS)


def test_a_labeller_that_supports_nothing_gets_no_top_up_and_the_whole_control(
    tmp_path: Path,
) -> None:
    out = planned(tmp_path)
    labeller = Labeller(lambda text: reply("UNSUPPORTED", flags=["OUTSIDE"]))
    ref.send(out, client=labeller)
    listed = ref.next_stage(out)
    # No unit is supported where it was retrieved, so the control is drawn to its end.
    assert listed["top_up_units"] == 0 and listed["control_units_added"] == 72
    assert listed["requests"] == 2 * 72 - 2 * listed["control_units_without_partner"]
    ref.send(out, client=labeller)
    derived = ref.derive(out)
    assert derived["counts"]["stable_not_supported"] == 200
    assert (
        derived["stability"]["control"] | {"drawn": 92, "read": 0, "bounds": False}
        == (derived["stability"]["control"])
    )


def test_a_reply_out_of_form_is_asked_again_and_an_outage_is_no_attempt(tmp_path: Path) -> None:
    out = planned(tmp_path)
    plan = ref.load_plan(out)
    first = plan["requests"][0]["request_id"]

    class Outage(Labeller):
        def grade(self, text: str) -> isolated.IsolatedReply:
            if len(self.seen) == 4:
                self.seen.append(text)
                raise JudgeUnavailable("cli_exit", "the model gives no reply")
            return super().grade(text)

    # Three replies out of form close the first request as invalid; the fifth call is an outage.
    answers = iter(["no object", reply("MAYBE"), "{}", reply("PARTIAL")])
    labeller = Outage(lambda text: next(answers))
    stopped = ref.send(out, client=labeller)
    assert stopped | {"valid": 1, "invalid": 1, "sent": 5, "unavailable": "cli_exit"} == stopped
    rows = ref.read_stores(out, plan["requests"], plan)
    assert [row["status"] for row in rows[first]] == ["invalid"] * 3
    second = plan["requests"][1]["request_id"]
    third = plan["requests"][2]["request_id"]
    assert [row["status"] for row in rows[second]] == ["valid"]
    assert [(row["status"], row["attempt"]) for row in rows[third]] == [("unavailable", 1)]
    # The rerun sends the unavailable request again as its first attempt, and no closed one.
    again = Labeller(lambda text: reply("SUPPORTED"))
    ref.send(out, client=again, limit=1)
    rows = ref.read_stores(out, plan["requests"], plan)
    assert [(row["status"], row["attempt"]) for row in rows[third]] == [
        ("unavailable", 1),
        ("valid", 1),
    ]
    assert len(rows[first]) == 3 and ref.state(rows[first]) == "invalid"
    ref.send(out, client=again)
    ref.next_stage(out)
    ref.send(out, client=again)
    labels = ref.build_labels(out)
    served = plan["requests"][0]["serves"] or [plan["requests"][0]["shows"]]
    invalid = [unit for unit in labels["units"] if unit["state"] == "invalid"]
    if plan["requests"][0]["kind"] == "unit":
        assert sorted(unit["claim_id"] for unit in invalid) == sorted(served)
        assert labels["stability"]["invalid"] == len(served)
    else:
        assert invalid == []


def test_a_store_that_send_did_not_write_is_refused(tmp_path: Path) -> None:
    out = planned(tmp_path)
    plan = ref.load_plan(out)
    ref.send(out, client=Labeller(lambda text: reply("SUPPORTED")), limit=3)
    name = ref.STORES[(plan["requests"][0]["kind"], plan["requests"][0]["pass"])]
    path = out / name
    kept = path.read_text(encoding="utf-8")
    row = json.loads(kept.splitlines()[0])
    for change, message in (
        ({"request_sha256": "0" * 64}, "not of this plan"),
        ({"prompt_sha256": "0" * 64}, "not of this plan"),
        ({"request_id": "f" * 64}, "not of this plan"),
        ({"attempt": 2}, "attempts that send does not write"),
        ({"session": {**SESSION, "turns": 2}}, "does not vouch"),
        ({"session": {**SESSION, "loaded": {**SESSION["loaded"], "tools": ["Bash"]}}}, "vouch"),
        ({"model": "claude-sonnet-5-5"}, "another model"),
        ({"raw_reply": "SUPPORTED"}, "not in the form"),
    ):
        path.write_text(json.dumps({**row, **change}) + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            ref.check(out)
    # A second reply after a valid one is not written by send either.
    path.write_text(kept + kept.splitlines()[0] + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="attempts that send does not write"):
        ref.check(out)
    path.write_text(kept, encoding="utf-8")
    assert ref.check(out)["stage_1"]["valid"] == 3
    # A plan the inputs do not rebuild is not read.
    stored = json.loads((out / ref.PLAN).read_text(encoding="utf-8"))
    stored["sample"] = stored["sample"][1:]
    ref._write(out / ref.PLAN, stored)
    with pytest.raises(ValueError, match="no longer rebuild the plan"):
        ref.send(out, client=Labeller(lambda text: reply("SUPPORTED")))


def test_the_committed_plan_is_the_one_the_inputs_rebuild() -> None:
    plan = ref.load_plan(ref.OUT)
    assert plan["version"] == nv.RUBRIC_VERSION and plan["prompt_sha256"] == nv.PROMPT_SHA256
    assert plan["summary"]["units"] == 200
    # Whatever is stored beside it follows the rules of the stages.
    ref.check(ref.OUT)
