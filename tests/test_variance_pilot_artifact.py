"""Hold the capsule of the variance pilot (plan step 1.3c) to its published files."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import pytest

from scripts import model_requests as requests_tool
from scripts import variance_pilot as pilot

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "reports/variance-pilot/768a195"
BASELINE = ROOT / "reports/baseline/68c5f8d"
CAPSULE = ROOT / "docs/evidence/variance-pilot-gold-metrics.md"
LEDGER = ROOT / "evaluation/dev_ledger.jsonl"
ARMS = ("control", "pool30", "sent3")
METRICS = ("evidence_recall_pool", "all_evidence_coverage", "fact_coverage")
RUNS = {
    "`control`": RUN / "control",
    "`pool30`": RUN / "pool30",
    "`sent3`": RUN / "sent3",
    "baseline of slice 2.5": BASELINE,
}
NIGHT = 8 * 3600


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _section(text: str, title: str) -> str:
    """One second-level section of the capsule, its heading included."""
    start = text.index(f"\n## {title}\n")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def _flat(text: str) -> str:
    return " ".join(text.split())


def _table(text: str, after: str = "") -> list[list[str]]:
    """The body rows of the first table that follows `after`."""
    lines = text[text.index(after) :].splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith("|"))
    rows = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def _close(cell: str, value: float, places: int) -> None:
    """A printed number is the value rounded to its places."""
    printed = float(cell.replace(" ", "").rstrip("%"))
    assert abs(printed - value) <= 0.5 * 10**-places + 1e-9, (cell, value)


def _same(published: Any, rebuilt: Any, where: str) -> None:
    """Equal structures; floats to a relative 1e-9, since another host built the published one."""
    if isinstance(published, dict):
        assert isinstance(rebuilt, dict) and published.keys() == rebuilt.keys(), where
        for key in published:
            _same(published[key], rebuilt[key], f"{where}.{key}")
    elif isinstance(published, list):
        assert isinstance(rebuilt, list) and len(published) == len(rebuilt), where
        for index, (left, right) in enumerate(zip(published, rebuilt, strict=True)):
            _same(left, right, f"{where}[{index}]")
    elif isinstance(published, float) or isinstance(rebuilt, float):
        assert isinstance(published, int | float) and isinstance(rebuilt, int | float), where
        assert math.isclose(published, rebuilt, rel_tol=1e-9, abs_tol=1e-12), where
    else:
        assert published == rebuilt, where


@pytest.fixture(scope="module")
def published() -> dict[str, Any]:
    document: dict[str, Any] = _json(RUN / "measure.json")
    return document


@pytest.fixture(scope="module")
def capsule() -> str:
    return CAPSULE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def addresses() -> dict[str, dict[str, Any]]:
    return {
        arm: {entry["case_id"]: entry for entry in _json(RUN / arm / "addresses.json")["cases"]}
        for arm in ARMS
    }


@pytest.fixture(scope="module")
def requests() -> dict[str, list[dict[str, Any]]]:
    return {
        name: requests_tool.read(folder / "model-requests.json") for name, folder in RUNS.items()
    }


@pytest.fixture(scope="module")
def reports() -> dict[str, dict[str, Any]]:
    return {arm: _json(RUN / arm / "collector-report.json")["result"] for arm in ARMS}


def _sent(addresses: dict[str, dict[str, Any]], arm: str, case: str) -> list[int]:
    """The seeds of the documents an arm sent, in the order it sent them."""
    return [document["chunk_index"] for document in addresses[arm][case]["sent"]]


def _texts(addresses: dict[str, dict[str, Any]], arm: str, case: str) -> list[str]:
    """The sent context as the measure compares it: the digests of its documents."""
    return [document["text_sha256"] for document in addresses[arm][case]["sent"]]


def _on_shared_seeds(
    addresses: dict[str, dict[str, Any]], arm: str, cases: list[str]
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Seeds of both arms whose document only the control sent, and only the arm sent."""
    only_control, only_arm = [], []
    for case in cases:
        shared = set(addresses["control"][case]["ranked"]) & set(addresses[arm][case]["ranked"])
        first = [chunk for chunk in _sent(addresses, "control", case) if chunk in shared]
        second = [chunk for chunk in _sent(addresses, arm, case) if chunk in shared]
        only_control += [(case, chunk) for chunk in first if chunk not in second]
        only_arm += [(case, chunk) for chunk in second if chunk not in first]
    return only_control, only_arm


def _without_code(document: dict[str, Any]) -> dict[str, Any]:
    provenance = {
        key: value for key, value in document["provenance"].items() if key != "measure_code_sha256"
    }
    return {**document, "provenance": provenance}


def test_the_measure_is_rebuilt_from_the_files_of_the_repository(published):
    rebuilt = pilot.measure({arm: RUN / arm for arm in ARMS})
    # The digests of the measuring code are those of the commit of the runs; the code has moved
    # since, and the document it builds from the same files has not.
    for document in (published, rebuilt):
        assert sorted(document["provenance"]["measure_code_sha256"]) == sorted(pilot.CODE_FILES)
    _same(_without_code(published), _without_code(rebuilt), "measure")


def test_the_provenance_table_is_the_files(published, capsule):
    section = _section(capsule, "Provenance")
    table = {row[0]: row[1] for row in _table(section)}
    provenance = published["provenance"]
    manifests = {arm: _json(RUN / arm / "manifest.json") for arm in ARMS}
    expected = {
        "Code of the collection and of the measure": provenance["code_sha"],
        "Corpus SHA-256": provenance["corpus_sha256"],
        "Chunk archive, the ingestion snapshot": manifests["control"]["index_receipt"][
            "corpus_sha256"
        ],
        "Index receipt": provenance["index_receipt_sha256"],
        "Questions of the 24 cases": provenance["questions_sha256"],
        "Verified cases with their labels": provenance["verified_cases_sha256"],
        "Family map": provenance["families_sha256"],
        "Registered split": provenance["split_sha256"],
        "`qwen2.5:7b`, digest": provenance["llm"]["digest"],
        "`BAAI/bge-reranker-v2-m3`, revision": provenance["reranker"]["revision"],
        "Requests of the baseline, `reports/baseline/68c5f8d/model-requests.json`": _sha(
            BASELINE / "model-requests.json"
        ),
        "`measure.json`": _sha(RUN / "measure.json"),
    }
    for entry, arm in enumerate(ARMS, start=3):
        config = manifests[arm]["ledger_entry"]["config_sha256"]
        expected[f"Config of `{arm}`, ledger entry {entry}"] = config
        expected[f"Run identity of `{arm}`"] = published["arms"][arm]["run_sha256"]
        for name in ("collector-report.json", "model-requests.json"):
            expected[f"`{arm}/{name}`"] = _sha(RUN / arm / name)
    for what, value in expected.items():
        assert table[what] == f"`{value}`", what
    for what in ("Supervisor state, not committed", "Host samples, not committed"):
        assert re.fullmatch(r"`[0-9a-f]{64}`", table[what]), what
    assert len(table) == len(expected) + 2
    assert provenance["chunker_version"].endswith(expected["Chunk archive, the ingestion snapshot"])
    config = provenance["config"]
    assert (config["retrieval_top_k"], config["rerank_top_k"]) == (20, 5)
    assert (config["parent_expansion_window"], config["parent_expansion_max_chars"]) == (2, 3600)
    assert published["arms"]["pool30"]["moved"] == {"retrieval_top_k": 30}
    assert published["arms"]["sent3"]["moved"] == {"rerank_top_k": 3}
    for rule in (
        provenance["match_rule"],
        provenance["fact_label_rule"],
        provenance["fact_matcher"],
    ):
        assert f"`{rule}`" in section
    for arm in ARMS:
        # A request file names the manifest of its run, and that manifest is the committed one.
        head = _json(RUN / arm / "model-requests.json")
        assert head["run_manifest_sha256"] == _sha(RUN / arm / "manifest.json")
        assert head["models"] == [provenance["llm"]]
    head = _json(BASELINE / "model-requests.json")
    assert head["run_manifest_sha256"] == _sha(BASELINE / "manifest.json")


def test_what_was_run_is_the_registered_pilot(published, capsule, reports):
    flat = _flat(_section(capsule, "What was run"))
    verified = pilot.read_lines(pilot.VERIFIED)
    cases = [case for case in verified if case["evidence_spans"]]
    classes = [case["primary_class"] for case in cases]
    assert len(cases) == len(published["cases"]) == 24
    assert [case["case_id"] for case in cases] == list(published["cases"])
    assert len(verified) - len(cases) == 6
    assert "The six refusal or clarification cases of the pilot carry no gold evidence" in flat
    assert (
        f"{classes.count('single-doc')} single-doc, {classes.count('multi-doc')} multi-doc, "
        f"{classes.count('aggregation')} aggregation"
    ) in flat
    spans = sum(len(case["evidence_spans"]) for case in cases)
    groups = sum(len(case["required_evidence_groups"]) for case in cases)
    required = sum(len(case["required_facts"]) for case in cases)
    critical = sum(len(case["critical_facts"]) for case in cases)
    assert all(fact in case["required_facts"] for case in cases for fact in case["critical_facts"])
    assert (
        f"{spans} gold spans in {groups} evidence groups and {required} required facts, "
        f"{critical} of them critical"
    ) in flat
    assert spans == published["index_bound"]["spans"]
    assert {case["label_check"]["status"] for case in cases} == {"single_model_verified"}
    assert {tuple(case["label_check"]["verifiers"]) for case in cases} == {("claude-opus-5-5",)}
    assert "`single_model_verified`" in capsule and "`label-verification/v2`" in capsule
    for arm in ARMS:
        assert reports[arm]["denominators"] == {pilot.SUBSET: 24}
        assert reports[arm]["exclusions"] == [] and published["arms"][arm]["excluded"] == []
        assert reports[arm]["latency_evidence"] is False
    assert "No arm excluded a case: 24 of 24 in each." in flat
    sizes = published["pilot"]["pool30"]["metrics"]["fact_coverage"]["cluster_sizes"]
    assert (len(sizes), sizes.count(4), sizes.count(2), sizes.count(1)) == (15, 2, 3, 10)
    assert "The 24 cases form 15: two of 4, three of 2 and ten of 1." in _flat(capsule)


def test_the_bound_of_the_index_is_the_measure(published, capsule):
    flat = _flat(_section(capsule, "The gold rule and the bound of the index"))
    bound = published["index_bound"]
    assert (bound["spans"], bound["held_whole_by_a_chunk"]) == (38, 37)
    assert bound["held_by_several_chunks"] == {} and bound["held_by_no_chunk"] == ["T64-16-E2"]
    assert "Of the 38 spans, 37 are held whole by exactly one chunk of the index." in flat
    assert "One span, `T64-16-E2`, is held whole by no chunk" in flat
    assert all(published["cases"]["T64-16"][arm]["all_evidence_coverage"] == 0 for arm in ARMS)


@pytest.mark.parametrize("arm", ["pool30", "sent3"])
def test_the_table_of_a_perturbation_is_the_measure(arm, published, capsule):
    section = _section(capsule, "Numbers")
    rows = {row[0]: row[1:] for row in _table(section, f"`{arm}` against `control`:")}
    found = published["pilot"][arm]
    assert found["variance_used"] and found["pairs"] == 24 and found["lost_pairs"] == []
    assert sorted(rows) == sorted(f"`{metric}`" for metric in METRICS)
    for metric in METRICS:
        stats, cells = found["metrics"][metric], rows[f"`{metric}`"]
        _close(cells[0], stats["control_mean"], 4)
        _close(cells[1], stats["arm_mean"], 4)
        _close(cells[2], stats["mean"], 4)
        _close(cells[3], stats["variance"], 4)
        assert int(cells[4]) == stats["differing_pairs"]
        assert cells[5] == f"{stats['gains']} / {stats['losses']}"
        assert int(cells[6]) == stats["nonzero_clusters"]
        raw = stats["intraclass_correlation_unclamped"]
        if raw is None:
            assert cells[7] == "none"
        else:
            _close(cells[7], raw, 4)
        assert stats["variance"] < pilot.REGISTERED_GRID_VARIANCE


def test_the_notes_under_the_tables_are_the_measure(published, capsule):
    flat = _flat(_section(capsule, "Numbers"))
    control = published["pilot"]["pool30"]["metrics"]
    cases = published["cases"]
    assert sum(cases[case]["control"]["all_evidence_coverage"] for case in cases) == 12
    assert (
        f"its pool held {control['evidence_recall_pool']['control_mean']:.4f} of the gold spans "
        "by case mean, its sent context held every required evidence group in 12 of the 24 cases "
        f"({control['all_evidence_coverage']['control_mean']:.4f}) and "
        f"{control['fact_coverage']['control_mean']:.4f} of the required facts"
    ) in flat
    pool30, sent3 = published["pilot"]["pool30"], published["pilot"]["sent3"]
    assert (
        f"`pool30` has another pool in {pool30['cases_with_another_pool']} cases and another sent "
        f"context in {pool30['cases_with_another_context']}. `sent3` has another pool in "
        f"{sent3['cases_with_another_pool']} cases and another sent context in "
        f"{sent3['cases_with_another_context']}."
    ) in flat
    assert sent3["cases_with_another_pool"] == 0
    for found in (pool30, sent3):
        assert (found["critical_facts_lost"], found["cases_with_a_critical_fact_lost"]) == (3, 1)
    for arm in ("pool30", "sent3"):
        lost = [
            case
            for case, by_arm in cases.items()
            if any(
                held and not kept
                for held, kept in zip(
                    by_arm["control"]["critical_facts_in_context"],
                    by_arm[arm]["critical_facts_in_context"],
                    strict=True,
                )
            )
        ]
        assert lost == ["T64-13"]
    assert "all in one case, T64-13" in flat
    estimates = [
        found["metrics"][metric]["intraclass_correlation_unclamped"]
        for found in (pool30, sent3)
        for metric in METRICS
    ]
    assert sum(value is not None and value < 0 for value in estimates) == 3
    assert f"The largest, {max(value for value in estimates if value is not None):.4f}," in flat


def test_the_registered_table_is_the_measure(published, capsule):
    section = _section(capsule, "The registered MDE")
    flat = _flat(section)
    rows = published["registered_mde"]
    assert len(rows) == 22 and {row["variance_source"] for row in rows} == {"grid"}
    assert {row["variance"] for row in rows} == {pilot.REGISTERED_GRID_VARIANCE}
    assert "all 22 rows of the registered table — 11 deciding metrics in two splits" in flat
    by: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        by.setdefault((row["split"], row["population"]), []).append(row)
    table = _table(section)
    assert sorted((cells[0], cells[1]) for cells in table) == sorted(by) and len(table) == 6
    for cells in table:
        for row in by[(cells[0], cells[1])]:
            assert (int(cells[2]), int(cells[3])) == (row["n"], row["clusters"])
            for cell, key in zip(
                cells[4:],
                (
                    "mde",
                    "power_rule_at_mue",
                    "power_noninferiority_at_zero",
                    "effect_for_noninferiority",
                    "mde_independent_cases",
                    "mde_at_correlation_estimate",
                ),
                strict=True,
            ):
                _close(cell, row[key], 3)
            assert f"MDE at correlation {row['correlation_estimate']:.4f} |" in section
    for metric, population in pilot.DECIDING.items():
        assert {row["population"] for row in rows if row["metric"] == metric} == {population}
    named = flat.split("**Populations.**")[1].split("- **Columns.**")[0].split(";")
    for part, population in zip(named, pilot.POPULATIONS, strict=True):
        assert population in part
        assert set(re.findall(r"`(\w+)`", part)) == {
            metric for metric, where in pilot.DECIDING.items() if where == population
        }
    spans = {
        split: [row["mde"] for row in rows if row["split"] == split]
        for split in ("development", "holdout")
    }
    assert (
        f"{min(spans['development']):.3f} to {max(spans['development']):.3f} in development, "
        f"{min(spans['holdout']):.3f} to {max(spans['holdout']):.3f} in the holdout"
    ) in _flat(capsule)
    times = [row["mde"] / 0.05 for row in rows]
    assert 3 <= min(times) < 3.5 and 6 <= max(times) < 6.5
    assert "The registered MDE is three to six times the minimally useful +0.05." in flat
    powers = [row["power_noninferiority_at_zero"] for row in rows]
    assert max(powers) < 0.8
    assert f"on these rows the power is {min(powers):.2f} to {max(powers):.2f}" in flat
    assert f"only from {published['zero_loss_cases']} cases on" in flat
    moved = [
        found["metrics"][metric]["differing_pairs"]
        for found in published["pilot"].values()
        for metric in METRICS
    ]
    assert sorted(moved) == [0, 1, 2, 2, 2, 2]
    assert "moved 2 of 24 pairs on a metric of the sent context and 1 or 0 on the pool" in flat


def test_the_seeds_and_the_sent_documents_are_the_addresses(published, capsule, addresses):
    flat = _flat(_section(capsule, "What moved the sent context"))
    cases = list(addresses["control"])
    control, pool30, sent3 = (addresses[arm] for arm in ARMS)
    assert [len(control[case]["ranked"]) for case in cases] == [5] * 24
    assert all(control[case]["ranked"][:3] == sent3[case]["ranked"] for case in cases)
    assert all(control[case]["pool"] == sent3[case]["pool"] for case in cases)
    assert (
        "Its three seeds are the control's first three in 24 of 24 cases, and its pool is the "
        "control's, in the same order, in 24 of 24."
    ) in flat
    only_control, only_arm = _on_shared_seeds(addresses, "sent3", cases)
    assert only_control == [("T64-02", 1781), ("T64-03", 425), ("T64-13", 5151)]
    assert only_arm == [("T64-06", 454)]
    assert (
        "the control sent 3 that `sent3` did not — on seed 1781 in T64-02, 425 in T64-03 and "
        "5151 in T64-13 — and `sent3` sent 1 that the control did not, on seed 454 in T64-06"
    ) in flat
    assert all(set(control[case]["pool"]) <= set(pool30[case]["pool"]) for case in cases)
    assert "Its pool contains the control's in 24 of 24 cases." in flat
    same = [case for case in cases if control[case]["ranked"] == pool30[case]["ranked"]]
    moved = [
        case
        for case in same
        if _texts(addresses, "control", case) != _texts(addresses, "pool30", case)
    ]
    assert (len(same), moved) == (18, ["T64-01", "T64-02", "T64-13"])
    assert _on_shared_seeds(addresses, "pool30", same) == (
        [("T64-01", 747), ("T64-02", 1781), ("T64-02", 1799), ("T64-13", 5151)],
        [],
    )
    assert (
        "The reranker kept the control's five seeds in 18 cases. In 3 of those 18 the sent "
        "context still differs: the arm did not send 4 documents the control sent, on seed 747 "
        "in T64-01, 1781 and 1799 in T64-02, and 5151 in T64-13."
    ) in flat
    other = [case for case in cases if case not in same]
    shared = {len(set(control[case]["ranked"]) & set(pool30[case]["ranked"])) for case in other}
    changed = [
        case
        for case in other
        if _texts(addresses, "control", case) != _texts(addresses, "pool30", case)
    ]
    assert (len(other), shared, len(changed)) == (6, {3, 4}, 5)
    assert (
        "In the other 6 cases the arms share 3 or 4 seeds of 5, and 5 of them have another context."
    ) in flat
    for arm in ("pool30", "sent3"):
        # The addresses say what the measure counts.
        found = published["pilot"][arm]
        assert found["cases_with_another_context"] == sum(
            _texts(addresses, "control", case) != _texts(addresses, arm, case) for case in cases
        )
        assert found["cases_with_another_pool"] == sum(
            sorted(control[case]["pool"]) != sorted(addresses[arm][case]["pool"]) for case in cases
        )
    # The four pairs of `all_evidence_coverage`, and what each of them rests on.
    pairs = {
        (arm, case): (
            by_arm["control"]["all_evidence_coverage"],
            by_arm[arm]["all_evidence_coverage"],
        )
        for case, by_arm in published["cases"].items()
        for arm in ("pool30", "sent3")
        if by_arm["control"]["all_evidence_coverage"] != by_arm[arm]["all_evidence_coverage"]
    }
    assert pairs == {
        ("pool30", "T64-13"): (1, 0),
        ("pool30", "T64-20"): (0, 1),
        ("sent3", "T64-06"): (0, 1),
        ("sent3", "T64-13"): (1, 0),
    }
    assert set(pairs) == {
        (arm, case)
        for case, by_arm in published["cases"].items()
        for arm in ("pool30", "sent3")
        if by_arm["control"]["fact_coverage"] != by_arm[arm]["fact_coverage"]
    }
    # T64-13: a seed of all three arms, sent by the control alone.
    assert all(5151 in addresses[arm]["T64-13"]["ranked"] for arm in ARMS)
    assert [5151 in _sent(addresses, arm, "T64-13") for arm in ARMS] == [True, False, False]
    # T64-06: a seed of all three arms, sent by `sent3` alone.
    assert all(454 in addresses[arm]["T64-06"]["ranked"] for arm in ARMS)
    assert [454 in _sent(addresses, arm, "T64-06") for arm in ARMS] == [False, False, True]
    # T64-20: a seed the control's pool does not hold.
    assert 2706 not in control["T64-20"]["pool"] and 2706 in pool30["T64-20"]["ranked"]
    assert 2706 in _sent(addresses, "pool30", "T64-20")
    assert "T64-20 rose from 0 to 1, on seed 2706, which only the wider pool gave" in flat
    assert "Three of the four come from a document both arms could send and one did" in flat


def test_the_request_table_is_the_request_files(capsule, requests, addresses):
    section = _section(capsule, "What moved the sent context")
    flat = _flat(section)
    table = {row[0]: row[1:] for row in _table(section, "| Run | Cases | Batch requests")}
    assert list(table) == list(RUNS)
    totals = {"batches": 0, "one_schema": 0, "one_text": 0, "none": 0, "documents": 0, "again": 0}
    bare = 0
    for name, rows in requests.items():
        found = requests_tool.summary(rows)
        cells = [int(cell) for cell in table[name]]
        assert cells == [
            found["requests"]["other/text"],
            found["batches"],
            found["batches_with_a_grade_a_document"],
            found["batch_documents"],
            found["documents_asked_one_by_one"],
            found["documents_with_a_structured_verdict"],
            found["documents_asked_again_as_text"],
            found["documents_kept"],
            found["documents_dropped"],
        ]
        assert found["batches_with_a_grade_a_document"] == 0
        assert found["batches_asked_again_as_text"] == found["batches"]
        assert found["batch_documents"] == found["documents_asked_one_by_one"]
        assert (
            found["documents_with_a_structured_verdict"] + found["documents_asked_again_as_text"]
            == found["documents_asked_one_by_one"]
        )
        replies = found["batch_replies_by_grades"]
        assert set(replies["schema"]) | set(replies["text"]) <= {"1", "none"}
        totals["batches"] += found["batches"]
        totals["one_schema"] += replies["schema"].get("1", 0)
        totals["one_text"] += replies["text"].get("1", 0)
        totals["none"] += replies["schema"].get("none", 0) + replies["text"].get("none", 0)
        totals["documents"] += found["documents_asked_one_by_one"]
        totals["again"] += found["documents_asked_again_as_text"]
        bare += sum(
            row["reply_sha256"] in {requests_tool.digest("YES"), requests_tool.digest("NO")}
            for row in rows
            if (row["asks"], row["route"]) == ("document", "schema") and row["relevant"] is None
        )
        # Options: the role's on every request as text, none on a request with a schema.
        assert found["options"]["schema"] == ["{}"]
        assert found["options"]["text"] == [
            '{"max_tokens": 256, "temperature": 0.0, "tools": null}'
        ]
    assert (
        f"In {totals['batches']} of {totals['batches']} contexts the first batch request and its "
        "repeat as text were both made"
    ) in flat
    assert (
        f"{totals['one_schema']} of the {totals['batches']} replies with a schema and "
        f"{totals['one_text']} of the {totals['batches']} as text held one grade, the other "
        f"{totals['none']} held no list"
    ) in flat
    assert (
        f"In {totals['again']} of the {totals['documents']} document requests the reply with a "
        f"schema was not JSON — the bare word in {bare} of them"
    ) in flat
    assert "in all 115 cases of the baseline of slice 2.5" in _flat(capsule)
    for arm in ARMS:
        # The documents the filter kept are the documents the run sent.
        sent = sum(len(entry["sent"]) for entry in addresses[arm].values())
        assert requests_tool.summary(requests[f"`{arm}`"])["documents_kept"] == sent
    prompt = (ROOT / "agent/prompts.py").read_text(encoding="utf-8")
    assert '{{"grades":[{{"index":1,"relevant":true,"reason":"коротко"}}]}}' in prompt
    assert "Ответь ОДНИМ словом: YES или NO." in prompt


def test_the_replies_that_repeat_are_the_request_files(capsule, requests, addresses):
    flat = _flat(_section(capsule, "What moved the sent context"))
    control = requests["`control`"]
    found = {
        arm: requests_tool.compare(control, requests[f"`{arm}`"]) for arm in ("pool30", "sent3")
    }

    def shared(arm: str, asks: str, route: str) -> tuple[int, int]:
        row = next(
            row for row in found[arm]["requests"] if (row["asks"], row["route"]) == (asks, route)
        )
        return row["shared"], row["same_reply"]

    same_seeds = sum(
        addresses["control"][case]["ranked"] == addresses["pool30"][case]["ranked"]
        for case in addresses["control"]
    )
    assert shared("pool30", "batch", "schema") == (same_seeds, 7)
    assert shared("sent3", "batch", "schema") == (0, 0)
    text = {
        arm: [shared(arm, asks, "text") for asks in ("batch", "document", "other")] for arm in found
    }
    assert text == {"pool30": [(18, 18), (10, 10), (24, 24)], "sent3": [(0, 0), (4, 4), (24, 24)]}
    assert (
        "52 of 52 between `control` and `pool30` (18 batch, 10 document, 24 rewrites), 28 of 28 "
        "between `control` and `sent3`"
    ) in flat
    assert shared("pool30", "document", "schema") == (109, 10)
    assert shared("sent3", "document", "schema") == (59, 5)
    assert (
        "With a schema, 7 of 18 batch prompts and 10 of 109 document prompts got the same reply "
        "in `pool30`, and 5 of 59 document prompts in `sent3`."
    ) in flat
    one, two = found["pool30"]["documents"], found["sent3"]["documents"]
    assert (
        one["shared"],
        one["same_verdict"],
        one["kept_by_the_first_only"],
        one["kept_by_the_second_only"],
    ) == (109, 104, 5, 0)
    assert (
        two["shared"],
        two["same_verdict"],
        two["kept_by_the_first_only"],
        two["kept_by_the_second_only"],
    ) == (59, 55, 3, 1)
    assert (
        "Of the 109 documents both `control` and `pool30` asked about, 104 got the same verdict "
        "and 5 were kept by the control only. Of the 59 that `control` and `sent3` share, 55 got "
        "the same verdict, 3 were kept by the control only and 1 by `sent3` only."
    ) in flat
    as_text = sum(
        row["documents"]
        for documents in (one, two)
        for row in documents["by_route"]
        if row["verdict"] != "same" and "text" in (row["first_route"], row["second_route"])
    )
    assert as_text == 5 and "In 5 of these 9 changes" in flat
    assert (
        "in 5 of 109 documents between `control` and `pool30`, and in 4 of 59 between `control` "
        "and `sent3`"
    ) in _flat(capsule)
    changed = one["shared"] - one["same_verdict"] + two["shared"] - two["same_verdict"]
    assert 18 <= (one["shared"] + two["shared"]) / changed <= 20
    assert "it differs in about one document of twenty" in flat
    # By seeds and by requests the same number of documents changed between `control` and `sent3`.
    only_control, only_arm = _on_shared_seeds(addresses, "sent3", list(addresses["control"]))
    assert (len(only_control), len(only_arm)) == (
        two["kept_by_the_first_only"],
        two["kept_by_the_second_only"],
    )
    assert "4 changed documents between `control` and `sent3` in both" in _flat(capsule)


def test_the_rewrites_are_the_same_in_the_three_arms(capsule, reports):
    queries = {
        arm: [
            (entry["case_id"], entry["query_transform"], entry["query_effective"])
            for entry in reports[arm]["provenance"]["effective_queries"]
        ]
        for arm in ARMS
    }
    assert queries["control"] == queries["pool30"] == queries["sent3"]
    assert {entry[1] for entry in queries["control"]} == {"rewrite"}
    assert len(queries["control"]) == 24
    assert "The 24 rewritten questions are the same in the three arms" in _flat(capsule)


def test_the_timing_tables_are_the_reports_and_the_requests(capsule, reports, requests):
    section = _section(capsule, "Timings and the host")
    flat = _flat(section)
    table = {row[0]: row[1:] for row in _table(section, "| Stage | `control` p50")}
    assert list(table) == ["`transform`", "`embed`", "`rerank`", "`retrieve`", "`grade`"]
    for stage, cells in table.items():
        for index, arm in enumerate(ARMS):
            timing = reports[arm]["timings_ms"][stage.strip("`")]
            assert timing["n"] == 24
            _close(cells[2 * index], timing["p50"] / 1000, 1)
            _close(cells[2 * index + 1], timing["p95"] / 1000, 1)
    for arm in ARMS:
        assert reports[arm]["timing_scope"].startswith("one run on one host, not speed evidence")
    stages = {row[0]: [float(cell) for cell in row[2:]] for row in _table(section, "| Arm | Start")}
    assert list(stages) == [f"`{arm}`" for arm in ARMS]
    for cells in stages.values():
        assert abs(math.fsum(cells[:5]) - cells[5]) < 0.3
    whole = math.fsum(cells[5] for cells in stages.values())
    assert f"The three arms took {round(whole):,} s".replace(",", " ") in flat
    assert f"{whole / 3600:.1f} hours" in flat
    asked = {row[0]: row[1:] for row in _table(section, "| Run | Cases | Both batch requests")}
    assert list(asked) == list(RUNS)
    for name, rows in requests.items():
        seconds = requests_tool.summary(rows)["seconds"]
        batch = seconds["batch/schema"] + seconds["batch/text"]
        documents = seconds["document/schema"] + seconds["document/text"]
        cells = asked[name]
        assert int(cells[0]) == sum(row["asks"] == "other" for row in rows)
        _close(cells[1], batch, 1)
        _close(cells[2], documents, 1)
        _close(cells[3], seconds["other/text"], 1)
        _close(cells[4], 100 * batch / (batch + documents), 1)
        if name in stages:
            # The model's seconds are inside the seconds of the stages the state gives.
            grade, transform = stages[name][4], stages[name][1]
            assert 0.99 * grade <= batch + documents <= grade
            assert 0.95 * transform <= seconds["other/text"] <= transform
    seconds = requests_tool.summary(requests["`control`"])["seconds"]
    batch = seconds["batch/schema"] + seconds["batch/text"]
    assert (
        f"In the control they took {round(batch / 24)} s of a case's "
        f"{round(stages['`control`'][4] / 24)} s of grading."
    ) in flat
    share = 100 * batch / (batch + seconds["document/schema"] + seconds["document/text"])
    assert f"took {share:.1f} % of the grading seconds of the control" in _flat(capsule)


def test_the_budget_is_arithmetic_on_the_control(capsule, requests):
    section = _section(capsule, "The budget of the campaign at the registered sizes")
    flat = _flat(section)
    timings = _section(capsule, "Timings and the host")
    control = next(
        [float(cell) for cell in row[2:]]
        for row in _table(timings, "| Arm | Start")
        if row[0] == "`control`"
    )
    reranked, through = math.fsum(control[:4]) / 24, control[5] / 24
    seconds = requests_tool.summary(requests["`control`"])["seconds"]
    without = through - (seconds["batch/schema"] + seconds["batch/text"]) / 24
    units = [[float(cell) for cell in row[1:]] for row in _table(section, "| Unit |")]
    for cells, value in zip(units, (reranked, through, without), strict=True):
        assert cells == [round(value), round(NIGHT / value)]
    work = {row[0]: row[2] for row in _table(section, "| Work |")}
    generator = through + 176

    def nights(cases: float, seconds_a_case: float) -> float:
        return cases * seconds_a_case / NIGHT

    assert work[next(key for key in work if key.startswith("One arm through grading"))] == (
        f"{nights(60, through):.1f} and {nights(64, through):.1f} nights"
    )
    assert work[next(key for key in work if key.startswith("Screening"))] == (
        f"{nights(900, reranked):.1f}–{nights(1500, reranked):.1f}"
    )
    assert work[next(key for key in work if key.startswith("Paired comparison"))] == (
        f"{nights(120, generator):.1f}"
    )
    acceptance = nights(128, generator)
    assert work[next(key for key in work if key.startswith("Acceptance 4.1"))] == (
        f"{acceptance:.1f}; {acceptance + 0.7:.1f}"
    )
    assert f"takes {nights(120, through):.1f} nights before a word is generated" in flat
    assert f"to the {round(through)} s measured through grading" in flat
    assert "a night is 8 hours, 28 800 s" in flat
    sizes = {(row["split"], row["n"]) for row in _json(RUN / "measure.json")["registered_mde"]}
    assert {("development", 60), ("holdout", 64)} <= sizes


def test_the_capsule_claims_what_the_pilot_may(published, capsule):
    flat = _flat(capsule)
    for sentence in (
        "`pool30` and `sent3` are not mechanism candidates",
        "no level of a metric in an arm is a result",
        "they are not a baseline of the campaign",
        "A mean difference above is not a gain or a loss of anything",
        "They size a budget; they are not evidence of speed",
        "No model of another vendor and no person checked them",
        "that this is the cause was not tested",
        "is a decision of the plan and is not taken here",
        "The pilot cannot say how much of a variance above is the draw",
    ):
        assert sentence in flat, sentence
    for claim in ("model-cross-checked", "human-validated", "human-verified"):
        assert claim not in capsule
    assert all(found["variance_used"] for found in published["pilot"].values())
    assert flat.count("Seven things to know before any number is read") == 1
    assert capsule.split("Words used below:")[0].count("\n- **") == 7


def test_the_ledger_records_the_three_runs(published):
    rows = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines() if line]
    assert [row["entry"] for row in rows] == list(range(1, len(rows) + 1))
    for entry, arm in enumerate(ARMS, start=3):
        row = rows[entry - 1]
        report = RUN / arm / "collector-report.json"
        assert sorted(row) == sorted(rows[0])
        assert row["artifact"] == report.relative_to(ROOT).as_posix()
        assert row["artifact_sha256"] == _sha(report)
        manifest = _json(RUN / arm / "manifest.json")
        assert row["config_sha256"] == manifest["ledger_entry"]["config_sha256"]
        assert manifest["ledger_entry"]["task"] == pilot.TASK == published["task"]
        assert row["families_touched"] == [pilot.SUBSET]
        assert row["slice"] == f"1.3c variance pilot / {arm}"
        assert row["verdict"] == (
            "variance_pilot_control_no_verdict"
            if arm == pilot.CONTROL
            else "variance_pilot_perturbation_no_verdict"
        )
    assert len({rows[entry - 1]["config_sha256"] for entry in (3, 4, 5)}) == 3
    # The control of the pilot is the configuration of the baseline of slice 2.5.
    assert rows[2]["config_sha256"] == rows[1]["config_sha256"]
