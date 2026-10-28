"""Stage 3b: the record of the answer prompt V5 against V4, derived again from the committed
records (docs/specs/answer-prompt-v5.md, «Records»)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from scripts.chat_answer_judge import classify

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports/answer-prompt-v5/tools"
STAND = ROOT / "reports/answer-prompt-v5/4f48fed"
V4 = ROOT / "reports/answer-prompt-v4/4f48fed"
RECORD = STAND / "v5-record.json"
CORE = STAND / "v5-core.json"
CAPSULE = ROOT / "docs/evidence/answer-prompt-v5-record.md"
SPEC = ROOT / "docs/specs/answer-prompt-v5.md"
STAND_SHA = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
KEYS = ("wixqa", "conditionalqa", "aircargo")
BASES = ("wixqa", "conditionalqa")
NAMES = {"aircargo": "aircargo", "wixqa": "WixQA", "conditionalqa": "ConditionalQA"}
CLASSES = ("good", "partial_ok", "bad")
FORMAT = ("other", "copied_context")
# Each V5 plan's SHA-256 as committed before its first grade (e078f95, 2a9cc5c, 6e7c02b),
# each bridge's as the spec registered it; requests and the prompt its answers were written by.
PLANS = {
    "v5-wixqa-judge-m1": (
        "5a5efd44f048e3905015898d82b561a214c0de861708ec0ff7d01ca14f44cd9f",
        115,
        "QA_PROMPT_V5",
    ),
    "v5-wixqa-judge-m2": (
        "3c5150fbeaef370df63d31201dbd2e469ec387f839ffddb1da1150ce010e1adb",
        115,
        "QA_PROMPT_V5",
    ),
    "v5-conditionalqa-judge-m1": (
        "469d7d4699d243e49eb10a6fac72021d1c7b5de5f903e32b8efa937d5abe714b",
        115,
        "QA_PROMPT_V5",
    ),
    "v5-conditionalqa-judge-m2": (
        "c6dc5bab1189178b41bf8fb3390bee2531e67803e47a53730f6f1f2b5cadc394",
        115,
        "QA_PROMPT_V5",
    ),
    "v5-aircargo-judge": (
        "d1dea2828d465996f323edafd1c452d9c1a9aa737479bcc50e143ad67f0b6cc5",
        115,
        "QA_PROMPT_V5",
    ),
    "v5-bridge-wixqa": (
        "db88932ee23275e4194081ec831992f93816074f2c5b2299803e6b26bf4de37a",
        30,
        "QA_PROMPT_V4",
    ),
    "v5-bridge-conditionalqa": (
        "582de3638d6b0e3652e80df9a44741c6d385242cce21c0c03cba56a4bc3da421",
        30,
        "QA_PROMPT_V4",
    ),
    "v5-bridge-aircargo": (
        "f4e646b9904b2c6d419dab423155efa0bea52ae2105c416f9d1054c557e366cf",
        30,
        "QA_PROMPT_V4",
    ),
}
# The plans the stability rule leaves uncounted, by key, in the record's order.
NOT_COUNTED = {
    "wixqa": ["v5-wixqa-judge-m2"],
    "conditionalqa": ["v5-conditionalqa-judge-m1"],
    "aircargo": ["v5-aircargo-judge"],
}


def load(folder, name):
    record = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (folder / f"{name}.cases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return record, rows


def m1_name(side, key):
    return f"{side}-aircargo-judge" if key == "aircargo" else f"{side}-{key}-judge-m1"


def graded(folder, name):
    return {row["case_id"]: row for row in load(folder, name)[1] if row["grade"] is not None}


def tool(name):
    """A registered tool, loaded as a module with sys.path restored after."""
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    before = list(sys.path)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = before
    return module


def format_aside(row):
    """The class a V5 row would get without its format defects: the post-hoc reading."""
    return classify({**row, "defect": "none" if row["defect"] in FORMAT else row["defect"]})


@pytest.fixture(scope="module")
def record():
    return json.loads(RECORD.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def capsule():
    return CAPSULE.read_text(encoding="utf-8")


def pp(value):
    return f"{100 * value:+.1f}"


def moved(entry):
    """A paired yes or no as the capsule prints it: V4 → V5 of n, the difference, the read."""
    table, n = entry["table"], entry["n"]
    low, high = entry["read95"]
    return (
        f"{table['a'] + table['b']} → {table['a'] + table['c']} of {n} "
        f"({pp(entry['difference'])} pp; {pp(low)} to {pp(high)}), {entry['direction']}"
    )


def retest(entry):
    kappa = entry["quadratic_kappa"]
    return (
        f"{entry['agree']}/{entry['pairs']} agree, {entry['two_steps_apart']} two steps apart, "
        f"κ {'—' if kappa is None else f'{kappa:.2f}'}"
    )


def share(part):
    return f"{100 * part['share']:.1f} %"


def aside_counts(key):
    """Each side's M1 classes on the pairs, its format defects set aside: read after the grades."""
    v4, v5 = graded(V4, m1_name("v4", key)), graded(STAND, m1_name("v5", key))
    found = {side: dict.fromkeys(CLASSES, 0) for side in ("v4", "v5")}
    for case in v4.keys() & v5.keys():
        found["v4"][format_aside(v4[case])] += 1
        found["v5"][format_aside(v5[case])] += 1
    return found


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
        ("the same, on the pairs whose context V5 read unchanged", record["same_context"]),
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
        found = corpora[key]["defects"]
        v4, v5 = found["v4"], found["v5"]
        kinds = " | ".join(f"{v4[name]} → {v5[name]}" for name in ("other", "copied_context"))
        rest = sum(v5[name] for name in v5 if name not in (*FORMAT, "none"))
        quoted = corpora[key]["quoted"]
        aside = aside_counts(key)
        classes = [" · ".join(str(aside[side][name]) for name in CLASSES) for side in aside]
        lines.append(
            f"| {NAMES[key]} | {kinds} | {rest} | {quoted['v4']} → {quoted['v5']} "
            f"| {classes[0]} → {classes[1]} |"
        )
    for key in KEYS:
        numbers = corpora[key]
        held = numbers["context_has_answer"]
        claims = numbers["claims_supported"]
        lines.append(
            f"| {NAMES[key]} | {numbers['wrong_declines']['v4']} → "
            f"{numbers['wrong_declines']['v5']} | {held['same']}, {held['lost']}, {held['gained']} "
            f"| {share(claims['v4'])} → {share(claims['v5'])} "
            f"| {numbers['same_context']}/{numbers['answers']} |"
        )
    for key in KEYS:
        numbers = corpora[key]
        table = numbers["transitions"]
        rows = " / ".join(" · ".join(str(table[a][b]) for b in CLASSES) for a in CLASSES)
        sec, chunks = numbers["stream_sec"], numbers["chunks"]
        lines.append(
            f"| {NAMES[key]} | {rows} | {sec['v4']['median']:.1f} → {sec['v5']['median']:.1f} "
            f"| {chunks['v4']['median']:.0f} → {chunks['v5']['median']:.0f} "
            f"| {numbers['at_token_cap']['v5']} |"
        )
    for base in BASES:
        m2 = corpora[base]["m2"]
        held, without = m2["with_reference"], m2["without_reference"]
        right = (
            f"{without['right']['v4']} → {without['right']['v5']} of {without['pairs']}"
            if without["pairs"]
            else "—"
        )
        status = record["plans"][f"v5-{base}-judge-m2"]["status"]
        lines.append(f"| {NAMES[base]} | {status} | {moved(held['agrees'])} | {right} |")
    lines.append(f"| WixQA and ConditionalQA pooled | {moved(record['recall'])} |")
    return lines


def test_the_record_is_the_tools_output_of_the_committed_records(record):
    assert tool("v5_record").build(STAND) == record
    assert record["stand"] == STAND_SHA and record["keys"] == list(KEYS)
    for path, digest in record["inputs"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    pinned = dict(
        re.findall(
            r"^- `reports/answer-prompt-v5/tools/(\S+)` `([0-9a-f]{64})`",
            SPEC.read_text(encoding="utf-8"),
            re.M,
        )
    )
    assert record["tools"] == {name: pinned[name] for name in record["tools"]}


def test_the_cores_step_is_printed_beside_it(record):
    core = json.loads(CORE.read_text(encoding="utf-8"))
    assert tool("v5_core").core(STAND, ("wixqa",)) == core
    assert core["keys"] == ["wixqa"]
    assert core["primary"]["table"] == record["corpora"]["wixqa"]["bad"]["table"]
    step = core["step"]
    assert (step["step"], step["decision"]) == ("stop", "not adopted")
    assert step["harm"] == [
        "wixqa: the bad share rises",
        "wixqa: the good share falls, the bad share does not",
    ]


@pytest.mark.parametrize("name", PLANS)
def test_each_plans_status_is_the_stability_rules(name):
    plan_sha, requests, prompt = PLANS[name]
    plan, rows = load(STAND, name)
    provenance, test = plan["provenance"], plan["retest"]
    assert provenance["plan_sha256"] == plan_sha and provenance["prompt_id"] == prompt
    assert plan["requests_valid"] == requests
    assert plan["replies"]["models"] == {"claude-opus-5-5": requests}
    assert plan["missing"] == [] and all(not row["missing"] for row in rows)
    pairs = test["pairs_list"]
    assert test["pairs"] == len(pairs) == test["planned"] == 15
    agree = sum(first == second for first, second in pairs)
    apart = sum(abs(first - second) == 2 for first, second in pairs)
    assert (test["agree"], test["two_steps_apart"]) == (agree, apart)
    kappa = test["quadratic_kappa"]
    assert test["passed"] is ((kappa is not None and kappa >= 0.6) or (agree >= 13 and apart == 0))
    uncounted = any(name in names for names in NOT_COUNTED.values())
    assert test["passed"] is not uncounted
    assert plan["status"] == ("NOT_EVIDENCE" if uncounted else "counted")
    if "-judge-m" in name:
        assert provenance["references_withheld"] is name.endswith("-m1")


@pytest.mark.parametrize("key", KEYS)
def test_v5_answered_each_key_whole_at_the_stand(key):
    summary, rows = load(STAND, f"v5-{key}")
    assert summary["whole"] is True and summary["answers"] == len(rows) == 100
    assert {launch["code_sha"] for launch in summary["launches"]} == {STAND_SHA}
    assert {launch["status"] for launch in summary["launches"]} == {"complete"}
    assert {launch["prompt_id"] for launch in summary["launches"]} == {"QA_PROMPT_V5"}
    parity = [
        json.loads(line)
        for line in (STAND / f"v5-{key}.check.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(parity) == 100 and all(row["parity"] for row in parity)


@pytest.mark.parametrize("key", KEYS)
def test_the_paired_classes_are_counted_from_the_rows(record, key):
    v4 = graded(V4, m1_name("v4", key))
    v5 = graded(STAND, m1_name("v5", key))
    pairs = sorted(set(v4) & set(v5))
    numbers = record["corpora"][key]
    assert numbers["pairs"] == len(pairs) == 100
    for name in ("bad", "good"):
        table = numbers[name]["table"]
        assert table == {
            "a": sum(v4[c]["grade"] == name and v5[c]["grade"] == name for c in pairs),
            "b": sum(v4[c]["grade"] == name and v5[c]["grade"] != name for c in pairs),
            "c": sum(v4[c]["grade"] != name and v5[c]["grade"] == name for c in pairs),
            "d": sum(v4[c]["grade"] != name and v5[c]["grade"] != name for c in pairs),
        }
        entry = numbers[name]
        assert entry["difference"] == round((table["c"] - table["b"]) / len(pairs), 4)
        low, high = entry["read95"]
        assert low == min(entry["newcombe95"][0], entry["cluster95"][0])
        assert high == max(entry["newcombe95"][1], entry["cluster95"][1])
        assert entry["detected"] is (low > 0 or high < 0)
    assert numbers["transitions"] == {
        a: {b: sum(v4[c]["grade"] == a and v5[c]["grade"] == b for c in pairs) for b in CLASSES}
        for a in CLASSES
    }
    assert numbers["defects"]["v5"] == {
        name: sum(v5[c]["defect"] == name for c in pairs) for name in numbers["defects"]["v5"]
    }
    # Each V5 row's class is chat_answer_judge's; the post-hoc reading changes the defect alone.
    assert all(classify(v5[c]) == v5[c]["grade"] for c in pairs)
    without = [c for c in pairs if v4[c].get("stratum") == "not_answerable"]
    if key == "conditionalqa":
        guard = numbers["declines_without_answer"]["table"]
        assert numbers["declines_without_answer"]["n"] == len(without) == 20
        declined = {
            side: {c for c in without if rows[c]["answers_question"] == "declined"}
            for side, rows in (("v4", v4), ("v5", v5))
        }
        assert guard["a"] + guard["b"] == len(declined["v4"])
        assert guard["a"] + guard["c"] == len(declined["v5"])
    else:
        assert not without and "declines_without_answer" not in numbers


def test_the_pooled_primary_is_the_two_bases_pairs(record):
    primary, corpora = record["primary"], record["corpora"]
    assert primary["keys"] == list(BASES) and primary["indicator"] == "bad"
    for part in ("a", "b", "c", "d"):
        assert primary["table"][part] == sum(corpora[base]["bad"]["table"][part] for base in BASES)
    assert primary["n"] == sum(corpora[base]["pairs"] for base in BASES)


def test_the_decision_reads_the_spec_table_in_order(record):
    corpora, decision, plans = record["corpora"], record["decision"], record["plans"]

    def counted(name):
        return plans[name]["status"] == "counted"

    # A key's harm is read when its bridge and both sides' M1 plans count.
    readable = [
        key
        for key in KEYS
        if counted(f"v5-bridge-{key}") and all(counted(m1_name(side, key)) for side in ("v4", "v5"))
    ]
    harm = []
    for key in readable:
        bad, good = corpora[key]["bad"]["direction"], corpora[key]["good"]["direction"]
        if bad == "rises":
            harm.append(f"{key}: the bad share rises")
        if good == "falls" and bad != "falls":
            harm.append(f"{key}: the good share falls, the bad share does not")
        if (corpora[key].get("declines_without_answer") or {}).get("direction") == "falls":
            harm.append(f"{key}: fewer declines where the gold says not answerable")
    if set(BASES) <= set(readable) and record["primary"]["direction"] == "rises":
        harm.append("pooled: the bad share rises")
    m2 = all(counted(f"{side}-{base}-judge-m2") for side in ("v4", "v5") for base in BASES)
    if m2 and record["recall"]["direction"] == "falls":
        harm.append("pooled: M2's agreement with the reference falls")
    assert decision["harm"] == harm and "wixqa: the bad share rises" in harm
    assert decision["decision"] == "not adopted" and decision["v5_replaces_v4"] is False
    assert decision["reasons"] == harm and decision["not_run"] == []
    assert decision["not_counted"] == NOT_COUNTED


def test_the_environment_brackets_the_answers_on_stage_twos_server(record):
    found = record["environment"]
    assert found["snapshots"] == 4 and found["ollama"] == "0.33.2"
    assert [server["started"] for server in found["servers"]] == ["2026-09-13T16:37:06+00:00"]
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
        "Evidence / Answer / Status",
    ):
        assert phrase in flat
