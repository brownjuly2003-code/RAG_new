"""Stage 2's completed retrieval runs, exported without corpus text on 2026-10-21."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean

import pytest

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "reports/stage2/retrieval-20261021"
CODE = "5e308fe48cca0955c3007057a574a425f71e2a6a"
COUNTS = {
    "aircargo": 100,
    "aircargo-gr": 15,
    "conditionalqa": 100,
    "wixqa": 100,
    "multihoprag": 100,
}
POINTS = ("vector", "bm25", "pool", "ranked", "expanded", "sent")


def load(key):
    record = json.loads((RECORD / f"p2-{key}.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (RECORD / f"p2-{key}.cases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return record, rows


def test_export_bytes_are_pinned():
    manifest = json.loads((RECORD / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["code_sha"] == CODE
    assert set(manifest["files"]) == {
        f"{part}{suffix}"
        for part in ("p1-aircargo", *(f"p2-{key}" for key in COUNTS))
        for suffix in (".json", ".cases.jsonl")
    }
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((RECORD / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("key,n", COUNTS.items())
def test_all_registered_questions_complete_on_one_intact_path(key, n):
    record, rows = load(key)
    aggregate, provenance = record["aggregate"], record["provenance"]
    assert len(rows) == len({row["case_id"] for row in rows}) == n
    assert [row["index"] for row in rows] == list(range(1, n + 1))
    assert aggregate["registered"] == aggregate["asked"] == aggregate["measured"] == n
    assert aggregate["in_registered_order"] and not aggregate["missing"]
    assert not aggregate["path_breaks"] and not provenance["path_breaks"]
    assert provenance["status"] == "complete" and provenance["code_sha"] == CODE
    assert provenance["archive_sha256"] == provenance["receipt_corpus_sha256"]
    assert len(provenance["source_sha256"]) >= 3
    assert all(len(value) == 64 for value in provenance["source_sha256"].values())
    assert (
        hashlib.sha256(json.dumps(provenance["settings"], sort_keys=True).encode()).hexdigest()
        == provenance["settings_sha256"]
    )
    for name in ("stage2.sh", "stage2_cases.py", "stage2_common.py", "retrieval_summary.py"):
        assert (
            hashlib.sha256((ROOT / "reports/stage2/tools" / name).read_bytes()).hexdigest()
            == provenance["tools_sha256"][name]
        )
    for row in rows:
        assert not row["path_breaks"] and row["rerank_status"] == "ok"
        assert row["candidates"]["vector"] > 0 and row["candidates"]["bm25"] > 0
        assert row["expanded_documents"] == 5
        assert 0 < row["sent_documents"] <= 5
        assert row["ranked_scores"] == sorted((item[2] for item in row["pool"]), reverse=True)[:5]


@pytest.mark.parametrize(
    "key,n,metric,hits",
    [
        ("conditionalqa", 80, "all_evidence_coverage", 60),
        ("wixqa", 100, "gold_article", 68),
        ("multihoprag", 70, "all_evidence_coverage", 10),
    ],
)
def test_m3_and_k_curve_are_derived_only_from_questions_with_gold(key, n, metric, hits):
    record, rows = load(key)
    gold = [row for row in rows if row["gold"]]
    aggregate = record["aggregate"]["m3"]
    assert len(gold) == aggregate["with_gold"] == n
    assert aggregate["without_gold"] == 100 - n
    assert all(row["gold_in_index"] for row in gold)
    assert sum(row["points"]["sent"][metric] for row in gold) == hits
    for point in POINTS:
        assert aggregate["points"][point]["n"] == n
        for name, value in aggregate["points"][point].items():
            if name != "n":
                assert value == round(mean(row["points"][point][name] for row in gold), 4)
    eligible = [row for row in gold if row["k20_is_ranked"]]
    assert len(eligible) == aggregate["k_curve_questions"] == n
    assert aggregate["k20_not_ranked"] == 0
    assert len(aggregate["k_curve"]) == 20
    for k, values in enumerate(aggregate["k_curve"]):
        for name, value in values.items():
            assert value == round(mean(row["k_curve"][k][name] for row in eligible), 4)
    assert all(row["k_curve"][-1] == row["points"]["ranked"] for row in eligible)


def test_aircargo_retrieval_is_the_context_of_all_100_completed_answers():
    retrieval, rows = load("aircargo")
    answers = [
        json.loads(line)
        for line in (RECORD / "p1-aircargo.cases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    by_id = {row["case_id"]: row for row in answers}
    assert len(by_id) == len(answers) == 100
    assert {row["case_id"] for row in rows} == set(by_id)
    for row in rows:
        assert row["answer_prompt_same"] is True
        assert row["prompt"]["sha256"] == by_id[row["case_id"]]["prompts"][0]["sha256"]
    assert retrieval["aggregate"]["parity"] == {"True": 100}
    record = json.loads((RECORD / "p1-aircargo.json").read_text(encoding="utf-8"))
    assert record["provenance"]["code_sha"] == [CODE]
    assert record["aggregate"]["measured"] == record["aggregate"]["answered"] == 100
    assert record["aggregate"]["missing"] == []
    assert not record["aggregate"]["path_breaks"]
    assert len(record["runs"]) == 10 and all(run["counted"] for run in record["runs"])
    assert (
        Counter(row["route"] for row in answers)
        == record["aggregate"]["routes"]
        == {"auto": 97, "human": 3}
    )
