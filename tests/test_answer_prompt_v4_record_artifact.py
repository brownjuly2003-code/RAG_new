"""Stage 2b: the record of the answer prompt V4 against stage 2's V3, derived again from the
committed records (docs/specs/answer-prompt-v4.md, «Records»)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports/answer-prompt-v4/tools"
STAND = ROOT / "reports/answer-prompt-v4/4f48fed"
JUDGE = ROOT / "reports/stage2/5e308fe"
RECORD = STAND / "v4-record.json"
CAPSULE = ROOT / "docs/evidence/answer-prompt-v4-record.md"
SPEC = ROOT / "docs/specs/answer-prompt-v4.md"
STAND_SHA = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
KEYS = ("aircargo", "wixqa", "conditionalqa")
BASES = ("wixqa", "conditionalqa")
NAMES = {"aircargo": "aircargo", "wixqa": "WixQA", "conditionalqa": "ConditionalQA"}
CLASSES = ("good", "partial_ok", "bad")
# Each V4 plan's SHA-256 as committed before its first grade (410a642, d5f6e91), each bridge's
# as the spec registered it (4f48fed); requests and the prompt its answers were written by.
PLANS = {
    "v4-aircargo-judge": (
        "ad67e68c17534b6656d3e75daff292c55c161872406498f874714b2b74b738e1",
        115,
        "QA_PROMPT_V4",
    ),
    "v4-wixqa-judge-m1": (
        "fd090ede6a5f98b61d16fd5502ee2ddff79fd117bc87d729b6dbb8fbdcc1f05d",
        115,
        "QA_PROMPT_V4",
    ),
    "v4-wixqa-judge-m2": (
        "f8e4cc4bb6a9e2afa5347f647c9462ebbee4bfe5506bc0f54376e33141b15696",
        115,
        "QA_PROMPT_V4",
    ),
    "v4-conditionalqa-judge-m1": (
        "4cabf98b9d4e49fa120c7dedad9cc8a8923668c2e1e460bc5e3610d57d74bbe4",
        115,
        "QA_PROMPT_V4",
    ),
    "v4-conditionalqa-judge-m2": (
        "7d8f16399bd41e6e194ad08ca05020b1dc88b48aada8a16f35e3904ea284473e",
        115,
        "QA_PROMPT_V4",
    ),
    "v4-bridge-aircargo": (
        "23e6e13eafd9ebb8aea1562c980bf1309988f9a6d850592cd7801b8f3882d1a3",
        30,
        "QA_PROMPT_V3",
    ),
    "v4-bridge-wixqa": (
        "5697593e39d81ca8cf551b339b1624c0186cca16216ae03c54504fc6e6e107d5",
        30,
        "QA_PROMPT_V3",
    ),
    "v4-bridge-conditionalqa": (
        "ed89a6b6a2b939041e7df23ff8b749d9e4908fc91c89864cb4dc85da9179fc93",
        30,
        "QA_PROMPT_V3",
    ),
}


def load(folder, name):
    record = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (folder / f"{name}.cases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return record, rows


def m1_names(key):
    if key == "aircargo":
        return "p1-aircargo-judge", "v4-aircargo-judge"
    return f"p4-{key}-judge-m1", f"v4-{key}-judge-m1"


@pytest.fixture(scope="module")
def record():
    return json.loads(RECORD.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def capsule():
    return CAPSULE.read_text(encoding="utf-8")


def pp(value):
    return f"{100 * value:+.1f}"


def moved(entry):
    """A paired yes or no as the capsule prints it: V3 → V4 of n, the difference, the read."""
    table, n = entry["table"], entry["n"]
    low, high = entry["read95"]
    return (
        f"{table['a'] + table['b']} → {table['a'] + table['c']} of {n} "
        f"({pp(entry['difference'])} pp; {pp(low)} to {pp(high)}), {entry['direction']}"
    )


def retest(entry):
    return (
        f"{entry['agree']}/{entry['pairs']} agree, {entry['two_steps_apart']} two steps apart, "
        f"κ {entry['quadratic_kappa']:.2f}"
    )


def share(part):
    return f"{100 * part['share']:.1f} %"


def table_lines(record):
    """Every table row of the capsule, built from the record and the plans' records."""
    corpora = record["corpora"]
    lines = []
    for name in PLANS:
        plan = json.loads((STAND / f"{name}.json").read_text(encoding="utf-8"))
        lines.append(
            f"| `{name}` | {plan['requests_valid']} | ${plan['replies']['cost_usd']:.2f} "
            f"| {retest(plan['retest'])} | {plan['status']} |"
        )
    for label, entry in (
        ("WixQA and ConditionalQA pooled", record["primary"]),
        ("the same, on the pairs whose context V4 read unchanged", record["same_context"]),
    ):
        lines.append(f"| {label} | {moved(entry)} |")
    for key in KEYS:
        numbers = corpora[key]
        guard = numbers.get("declines_without_answer")
        lines.append(
            f"| {NAMES[key]} | {numbers['pairs']} | {moved(numbers['bad'])} "
            f"| {moved(numbers['good'])} | {moved(guard) if guard else '—'} |"
        )
    for key in KEYS:
        numbers = corpora[key]
        v3, v4 = numbers["marks"]["v3"], numbers["marks"]["v4"]
        lines.append(
            f"| {NAMES[key]} | {v3['placeholder']} → {v4['placeholder']} "
            f"| {moved(numbers['referral'])} | {v3['referral_routed']} → {v4['referral_routed']} |"
        )
    for key in KEYS:
        numbers = corpora[key]
        held = numbers["context_has_answer"]
        claims = numbers["claims_supported"]
        pairing = numbers["pairing"]
        lines.append(
            f"| {NAMES[key]} | {numbers['wrong_declines']['v3']} → "
            f"{numbers['wrong_declines']['v4']} | {numbers['bad_to_good_declining']} "
            f"| {held['same']}, {held['lost']}, {held['gained']} "
            f"| {share(claims['v3'])} → {share(claims['v4'])} | {moved(numbers['human'])} "
            f"| {pairing['same_context']}/{pairing['questions']} |"
        )
    for key in KEYS:
        table = corpora[key]["transitions"]
        rows = " / ".join(" · ".join(str(table[a][b]) for b in CLASSES) for a in CLASSES)
        times = corpora[key]["times"]
        lines.append(
            f"| {NAMES[key]} | {rows} | {times['v3']['median']:.1f} | {times['v4']['median']:.1f} |"
        )
    for base in BASES:
        m2 = corpora[base]["m2"]
        held, without = m2["with_reference"], m2["without_reference"]
        right = (
            f"{without['right']['v3']} → {without['right']['v4']} of {without['pairs']}"
            if without["pairs"]
            else "—"
        )
        lines.append(f"| {NAMES[base]} | {m2['status']} | {moved(held['agrees'])} | {right} |")
    return lines


def test_the_record_is_the_tools_output_of_the_committed_records(record):
    spec = importlib.util.spec_from_file_location("v4_record", TOOLS / "v4_record.py")
    assert spec and spec.loader
    tool = importlib.util.module_from_spec(spec)
    before = list(sys.path)
    try:
        spec.loader.exec_module(tool)
        assert tool.build(STAND) == record
    finally:
        sys.path[:] = before
    assert record["stand"] == STAND_SHA and record["keys"] == list(KEYS)
    for path, digest in record["inputs"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    pinned = dict(
        re.findall(
            r"^- `reports/answer-prompt-v4/tools/(\S+)` `([0-9a-f]{64})`",
            SPEC.read_text(encoding="utf-8"),
            re.M,
        )
    )
    assert record["tools"] == {name: pinned[name] for name in record["tools"]}


@pytest.mark.parametrize("name", PLANS)
def test_each_plan_counts_by_the_stability_rule(name):
    plan_sha, requests, prompt = PLANS[name]
    plan, rows = load(STAND, name)
    provenance, test = plan["provenance"], plan["retest"]
    assert provenance["plan_sha256"] == plan_sha and provenance["prompt_id"] == prompt
    assert plan["status"] == "counted" and plan["requests_valid"] == requests
    assert plan["replies"]["models"] == {"claude-opus-5-5": requests}
    assert plan["missing"] == [] and all(not row["missing"] for row in rows)
    pairs = test["pairs_list"]
    assert test["pairs"] == len(pairs) == test["planned"] == 15
    agree = sum(first == second for first, second in pairs)
    apart = sum(abs(first - second) == 2 for first, second in pairs)
    assert (test["agree"], test["two_steps_apart"]) == (agree, apart)
    kappa = test["quadratic_kappa"]
    assert test["passed"] is ((kappa is not None and kappa >= 0.6) or (agree >= 13 and apart == 0))
    assert test["passed"]
    if "-judge-m" in name:
        assert provenance["references_withheld"] is name.endswith("-m1")


@pytest.mark.parametrize("key", KEYS)
def test_no_v4_answer_has_a_path_break(key):
    summary, rows = load(STAND, f"v4-{key}")
    aggregate = summary["aggregate"]
    assert aggregate["registered"] == aggregate["measured"] == len(rows) == 100
    assert aggregate["path_breaks"] == {} and aggregate["missing"] == []
    assert all(not row.get("path_breaks") for row in rows)
    assert summary["provenance"]["code_sha"] == [STAND_SHA]


@pytest.mark.parametrize("key", KEYS)
def test_the_paired_classes_are_counted_from_the_rows(record, key):
    first, second = m1_names(key)
    v3 = {row["case_id"]: row for row in load(JUDGE, first)[1] if row["grade"] is not None}
    v4 = {row["case_id"]: row for row in load(STAND, second)[1] if row["grade"] is not None}
    pairs = sorted(set(v3) & set(v4))
    numbers = record["corpora"][key]
    assert numbers["pairs"] == len(pairs) == 100
    for name in ("bad", "good"):
        table = numbers[name]["table"]
        assert table == {
            "a": sum(v3[c]["grade"] == name and v4[c]["grade"] == name for c in pairs),
            "b": sum(v3[c]["grade"] == name and v4[c]["grade"] != name for c in pairs),
            "c": sum(v3[c]["grade"] != name and v4[c]["grade"] == name for c in pairs),
            "d": sum(v3[c]["grade"] != name and v4[c]["grade"] != name for c in pairs),
        }
        entry = numbers[name]
        assert entry["difference"] == round((table["c"] - table["b"]) / len(pairs), 4)
        low, high = entry["read95"]
        assert low == min(entry["newcombe95"][0], entry["cluster95"][0])
        assert high == max(entry["newcombe95"][1], entry["cluster95"][1])
        assert entry["detected"] is (low > 0 or high < 0)
    assert numbers["transitions"] == {
        a: {b: sum(v3[c]["grade"] == a and v4[c]["grade"] == b for c in pairs) for b in CLASSES}
        for a in CLASSES
    }
    without = [c for c in pairs if v3[c].get("stratum") == "not_answerable"]
    if key == "conditionalqa":
        guard = numbers["declines_without_answer"]["table"]
        assert numbers["declines_without_answer"]["n"] == len(without) == 20
        declined = {
            side: {c for c in without if rows[c]["answers_question"] == "declined"}
            for side, rows in (("v3", v3), ("v4", v4))
        }
        assert guard["a"] + guard["b"] == len(declined["v3"])
        assert guard["a"] + guard["c"] == len(declined["v4"])
    else:
        assert not without and "declines_without_answer" not in numbers


@pytest.mark.parametrize("key", KEYS)
def test_the_two_defects_are_counted_from_the_marks(record, key):
    marks = record["corpora"][key]["marks"]
    for side in ("v3", "v4"):
        rows = [
            json.loads(line)
            for line in (STAND / f"{side}-{key}.marks.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        assert len(rows) == marks[side]["answers"] == 100
        assert marks[side]["placeholder"] == sum(row["placeholder"] for row in rows)
        assert marks[side]["referral"] == sum(row["referral"] for row in rows)
        assert {row["prompt_id"] for row in rows} == {f"QA_PROMPT_{side.upper()}"}
    assert marks["v4"]["placeholder"] == 0
    # aircargo's two are answers whose documents name a specialist; no external base keeps one.
    assert marks["v4"]["referral"] == (2 if key == "aircargo" else 0)


def test_the_pooled_primary_is_the_two_bases_pairs(record):
    primary, corpora = record["primary"], record["corpora"]
    assert primary["keys"] == list(BASES) and primary["indicator"] == "bad"
    for part in ("a", "b", "c", "d"):
        assert primary["table"][part] == sum(corpora[base]["bad"]["table"][part] for base in BASES)
    assert primary["n"] == sum(corpora[base]["pairs"] for base in BASES)


def test_the_decision_reads_the_spec_table_in_order(record):
    corpora, decision = record["corpora"], record["decision"]
    harm = [
        key
        for key in KEYS
        if corpora[key]["bad"]["direction"] == "rises"
        or (
            corpora[key]["good"]["direction"] == "falls"
            and corpora[key]["bad"]["direction"] != "falls"
        )
        or (corpora[key].get("declines_without_answer") or {}).get("direction") == "falls"
    ]
    assert harm == [] and decision["harm"] == [] and record["primary"]["direction"] != "rises"
    statuses = {
        name: summary["status"]
        for side in record["plans"].values()
        for name, summary in side.items()
    }
    assert set(statuses.values()) == {"counted"} and decision["not_run"] == []
    assert record["primary"]["direction"] == "falls"
    assert decision["decision"] == "adopted" and decision["v4_stays"] is True
    assert decision["reasons"] == ["fewer bad answers"] and decision["defects_left"] == []


def test_the_environment_brackets_the_answers_on_stage_twos_server(record):
    found = record["environment"]
    assert found["snapshots"] == 4 and found["ollama"] == "0.33.2"
    assert [server["pid"] for server in found["servers"]] == [12377]
    assert found["freeze_sha256"] == (
        "ed8fe1c2142b1a9ff7f1c80db891a0887860ba939131bf5cd3cbde324b161ada"
    )


def test_the_capsule_prints_the_record(record, capsule):
    lines = set(capsule.splitlines())
    missing = [line for line in table_lines(record) if line not in lines]
    assert not missing, missing
    flat = " ".join(capsule.split())
    for phrase in (
        "No person graded an answer",
        "in sample",
        f"**The decision is {record['decision']['decision']}**",
        "ConditionalQA's declines among its 20 not answerable questions are not detected falling",
    ):
        assert phrase in flat
