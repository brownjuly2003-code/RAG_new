"""Hold the capsule of the production baseline (plan slice 2.5) to its published files."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from scripts import baseline_judge as judge_tool
from scripts import baseline_report as report_tool
from scripts import production_parity as parity

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "reports/baseline/68c5f8d"
JUDGE = RUN / "judge"
CAPSULE = ROOT / "docs/evidence/production-baseline-h-hm.md"
ARCHIVE = ROOT / "evaluation/gr1b-4436d61-graph-chunks.json.gz"
FAMILIES = ROOT / "evaluation/document_families.json"
LEDGER = ROOT / "evaluation/dev_ledger.jsonl"
SUBSETS = ("H", "Hm")
MEASURED = (
    "precision_at_5",
    "sent_precision",
    "ndcg_at_5",
    "context_precision",
    "context_precision_seeds",
)
STAGES = ("index", "initial_pool", "caps_dedup", "rerank", "expansion", "packing", "grading")
LOSSES = (
    "index",
    "index_to_pool_unknown",
    "caps_dedup",
    "rerank",
    "expansion",
    "packing",
    "grading",
    "no_observed_loss",
)
PAIR_ROWS = {
    ("first lost before the pool", "among the seeds, through another chunk"): (
        "index_to_pool_unknown",
        True,
        True,
    ),
    ("first lost before the pool", "in the pool, not among the seeds"): (
        "index_to_pool_unknown",
        True,
        False,
    ),
    ("first lost before the pool", "not in the pool"): ("index_to_pool_unknown", False, False),
    ("first lost at the rerank cut", "in the pool, not among the seeds"): ("rerank", True, False),
}
FOUR_DECIMALS = 0.00005000001
ONE_DECIMAL = 0.05000001
INTERVAL = r"(\[[^\]|]+\])"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _unpacked(path: Path) -> Any:
    return json.loads(gzip.decompress(path.read_bytes()))


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _section(text: str, title: str) -> str:
    """One second-level section of the capsule, its heading included."""
    start = text.index(f"\n## {title}\n")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def _flat(text: str) -> str:
    return " ".join(text.split())


def _n(value: float) -> str:
    """An integer as the capsule prints it: groups of three digits, a space between."""
    return f"{round(value):,}".replace(",", " ")


def _pair(cell: str) -> list[float]:
    return [float(value) for value in cell.strip("[]").split(",")]


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


def _mean(values: Any) -> float:
    listed = list(values)
    return math.fsum(listed) / len(listed)


def _width(interval: list[float]) -> float:
    return interval[1] - interval[0]


def _dcg(grades: list[int]) -> float:
    return math.fsum(grade / math.log2(rank + 2) for rank, grade in enumerate(grades))


def _latin(term: str) -> bool:
    """Written in Latin letters alone."""
    return bool(re.search(r"[A-Za-z]", term)) and not re.search(r"[А-Яа-яЁё]", term)


def _lost(items: list[dict[str, Any]], stage: str | None = None) -> int:
    """How many terms or cases have a first loss, or have it at one stage."""
    if stage is None:
        return sum(item["first_loss"] != "no_observed_loss" for item in items)
    return sum(item["first_loss"] == stage for item in items)


def _term_loss(presence: dict[str, bool]) -> str:
    """The first loss of a term: none when the sent context holds it, whatever came before."""
    if presence["grading"]:
        return "no_observed_loss"
    stage = next(name for name in STAGES if not presence[name])
    return "index_to_pool_unknown" if stage == "initial_pool" else stage


def _git(*arguments: str) -> subprocess.CompletedProcess[bytes] | None:
    try:
        return subprocess.run(
            ["git", *arguments], cwd=ROOT, capture_output=True, timeout=60, check=False
        )
    except OSError:
        return None


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    return _json(RUN / "report.json")


@pytest.fixture(scope="module")
def loss() -> dict[str, Any]:
    return _json(RUN / "loss-map.json")


@pytest.fixture(scope="module")
def capsule() -> str:
    return CAPSULE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def reading(loss: dict[str, Any]) -> dict[str, Counter]:
    """Where every lost Hm pair is, read from tracked files alone."""
    source_of = {
        hashlib.sha256(chunk["page_content"].encode("utf-8")).hexdigest(): chunk["metadata"][
            "source"
        ]
        for chunk in _unpacked(ARCHIVE)["chunks"]
    }
    seeds_of = {
        case["case_id"]: {source_of[key] for key in case["seeds"]}
        for case in _unpacked(RUN / "contexts.json.gz")["cases"]
        if case["subset"] == "Hm"
    }
    linked: dict[str, set[str]] = {}
    for link in _json(FAMILIES)["cross_ref_links"]:
        linked.setdefault(link["source_id"], set()).add(link["target_source_id"])
    found: dict[str, Counter] = {
        "pairs": Counter(),
        "links": Counter(),
        "documents": Counter(),
        "seed_documents": Counter(),
    }
    for row in loss["per_case"]:
        if row["subset"] != "Hm":
            continue
        seeds = seeds_of[row["case_id"]]
        gold = {term["document"] for term in row["terms"]}
        held = {stage: gold & set(row["source_documents_present"][stage]) for stage in STAGES}
        assert held["rerank"] == gold & seeds, row["case_id"]
        found["documents"][
            (len(gold), len(held["initial_pool"]), len(held["rerank"]), len(held["grading"]))
        ] += 1
        found["seed_documents"][len(seeds)] += 1
        for term in row["terms"]:
            if term["first_loss"] == "no_observed_loss":
                continue
            document = term["document"]
            key = (term["first_loss"], document in held["initial_pool"], document in seeds)
            found["pairs"][key] += 1
            found["links"][key] += any(document in linked.get(seed, ()) for seed in seeds)
    return found


def test_the_report_is_rebuilt_from_the_files_of_the_repository(report):
    rebuilt = json.loads(json.dumps(report_tool.build(RUN, JUDGE)))
    # The supervisor's state and the host samples are not committed (capsule, last section but one).
    absent = "N/A: supervisor state not supplied"
    assert rebuilt["collection"] == rebuilt["provenance"]["peak_host_rss"] == absent
    assert rebuilt.keys() == report.keys()
    assert rebuilt["provenance"].keys() == report["provenance"].keys()
    for key in report:
        if key == "collection":
            continue
        if key != "provenance":
            _same(report[key], rebuilt[key], key)
            continue
        for name in report[key]:
            if name not in ("peak_host_rss", "report_code"):
                _same(report[key][name], rebuilt[key][name], f"provenance.{name}")


def test_the_judge_summaries_are_rebuilt_from_the_stores(tmp_path):
    for name in ("opus.jsonl", "opus-retest.jsonl"):
        shutil.copyfile(JUDGE / name, tmp_path / name)
    (tmp_path / "plan.json").write_bytes(gzip.decompress((JUDGE / "plan.json.gz").read_bytes()))
    judge_tool.consensus(tmp_path)
    judge_tool.retest(tmp_path, "opus")
    for name in ("ruler-input.json", "opus-retest.json"):
        _same(_json(JUDGE / name), _json(tmp_path / name), name)


def test_the_digests_of_the_report_are_those_of_the_tracked_files(report):
    provenance = report["provenance"]
    replies = provenance["raw_judge_replies"]
    named = {
        JUDGE / "opus.jsonl": replies["first_pass"]["sha256"],
        JUDGE / "opus-retest.jsonl": replies["retest_pass"]["sha256"],
        JUDGE / "ruler-input.json": provenance["ruler_input_sha256"],
        JUDGE / "opus-retest.json": provenance["retest_report_sha256"],
        RUN / "collector-report.json": provenance["collector_report_sha256"],
        ARCHIVE: provenance["archive_sha256"],
        FAMILIES: provenance["family_map"]["sha256"],
        ROOT / "evaluation/curated_cases_aircargo.jsonl": provenance["datasets"]["H"]["sha256"],
        ROOT / "evaluation/curated_cases_aircargo_gr_multihop.jsonl": provenance["datasets"]["Hm"][
            "sha256"
        ],
    }
    for path, digest in named.items():
        assert _sha(path) == digest, path.name
    assert parity.digest(_json(RUN / "manifest.json")) == report["manifest_sha256"]
    assert _json(RUN / "registration.json") == {"manifest_sha256": report["manifest_sha256"]}
    assert parity.digest(_unpacked(RUN / "contexts.json.gz")) == provenance["contexts_sha256"]
    plan = gzip.decompress((JUDGE / "plan.json.gz").read_bytes())
    assert hashlib.sha256(plan).hexdigest() == provenance["judge_plan_sha256"]
    assert provenance["ingestion_snapshot_id"] == provenance["archive_sha256"]


def test_the_provenance_table_is_the_report(report, capsule):
    provenance = report["provenance"]
    replies = provenance["raw_judge_replies"]
    judge_version = json.loads(provenance["judge_revision"]["judge_version"][0])
    expected = {
        "Run identity: SHA-256 of the canonical JSON of `manifest.json`": report["manifest_sha256"],
        "Code of the collection": provenance["code_sha"],
        "Corpus SHA-256": provenance["corpus_sha256"],
        "Chunk archive, the ingestion snapshot": provenance["archive_sha256"],
        "H dataset, 100 cases": provenance["datasets"]["H"]["sha256"],
        "Hm dataset, 15 cases": provenance["datasets"]["Hm"]["sha256"],
        "Config of the run, registered as its entry `T-68/2.5a`": provenance["ledger_entry"][
            "config_sha256"
        ],
        "`qwen2.5:7b`, digest": provenance["model"]["digest"],
        "`BAAI/bge-m3`, revision": provenance["embedder_manifest"]["revision"],
        "`BAAI/bge-reranker-v2-m3`, revision": provenance["reranker"]["revision"],
        "Judge system prompt": judge_version["parameters"]["system_prompt_sha256"],
        "Judge plan, unpacked": provenance["judge_plan_sha256"],
        "Store of the first pass, `judge/opus.jsonl`": replies["first_pass"]["sha256"],
        "Store of the retest, `judge/opus-retest.jsonl`": replies["retest_pass"]["sha256"],
        "`judge/ruler-input.json`": provenance["ruler_input_sha256"],
        "`judge/opus-retest.json`": provenance["retest_report_sha256"],
        "Content of `contexts.json.gz`: SHA-256 of its canonical JSON": provenance[
            "contexts_sha256"
        ],
        "`collector-report.json`": provenance["collector_report_sha256"],
        "Family map, `evaluation/document_families.json`": provenance["family_map"]["sha256"],
        "Supervisor state, not committed": report["collection"]["state_sha256"],
        "Host samples, not committed": report["collection"]["host_samples_sha256"],
        "`report.json`": _sha(RUN / "report.json"),
        "`loss-map.json`": _sha(RUN / "loss-map.json"),
        "Code of the report, tracked tree clean": provenance["report_code"]["commit"],
    }
    rows = re.findall(
        r"^\| ([^|]+) \| `([0-9a-f]{40}|[0-9a-f]{64})` \|$", _section(capsule, "Provenance"), re.M
    )
    assert dict(rows) == expected
    assert len(rows) == len(expected)
    assert provenance["ledger_entry"]["task"] == "T-68/2.5a"
    assert provenance["report_code"]["tracked_tree_clean"] is True
    seeds = provenance["bootstrap_seed"]
    assert (
        f"{seeds['metric_intervals']} for the metric intervals, "
        f"{seeds['retest_kappa']} for the retest κ" in _flat(capsule)
    )


def test_the_metric_table_is_the_report(report, capsule):
    section = _section(capsule, "Numbers")
    rows = re.findall(
        rf"^\| (H|Hm) \| `(\w+)` \| ([\d.]+) \| {INTERVAL} \| {INTERVAL} \| {INTERVAL}"
        rf" \| {INTERVAL} \| (\d+) \| (\d+) \| (\d+) \|$",
        section,
        re.M,
    )
    assert [row[:2] for row in rows] == [(subset, name) for subset in SUBSETS for name in MEASURED]
    for subset, name, point, cluster, student, wider, case, n, clusters, excluded in rows:
        entry = report["subsets"][subset]["metrics"][name]
        assert float(point) == pytest.approx(entry["point"], abs=FOUR_DECIMALS)
        for cell, field in (
            (cluster, "ci95"),
            (student, "t_ci95"),
            (wider, "ci95_conservative"),
            (case, "case_bootstrap_ci95"),
        ):
            assert _pair(cell) == pytest.approx(entry[field], abs=FOUR_DECIMALS), (name, field)
        assert [int(n), int(clusters), int(excluded)] == [
            entry["n"],
            entry["clusters"],
            entry["excluded"],
        ]
        assert entry["ci95_conservative"] == [
            min(entry["ci95"][0], entry["t_ci95"][0]),
            max(entry["ci95"][1], entry["t_ci95"][1]),
        ]
    flat = _flat(capsule)
    for subset in SUBSETS:
        for name, entry in report["subsets"][subset]["metrics"].items():
            if name not in MEASURED:
                assert entry["point"] == "N/A" and entry["n"] == 0 and entry["reason"], name
                assert f"`{name}`" in section or entry["reason"] == report_tool.NO_ANSWER, name
    assert report_tool.NO_GOLD in flat
    assert [report["subsets"][subset]["cluster_unit"]["sizes"] for subset in SUBSETS] == [
        [94, 2, 2, 2],
        [15],
    ]
    assert "4 clusters — of 94, 2, 2 and 2 cases — and Hm into 1, of all 15" in flat
    h, hm = (report["subsets"][subset] for subset in SUBSETS)
    assert [entry["case_id"] for entry in h["judged_excluded"]] == [
        "aircargo-harassment-investigation-timeline"
    ]
    assert h["zero_idcg"] == ["aircargo-cargo-loss-required-fields"]
    assert hm["judged_excluded"] == hm["zero_idcg"] == []
    for case_id in ("aircargo-harassment-investigation-timeline", *h["zero_idcg"]):
        assert f"`{case_id}`" in section
    assert report["exclusions"] == [] and report["denominators"] == {"H": 100, "Hm": 15}
    sent = [block["contexts"]["sent"] for block in (h, hm)]
    size = [block["contexts"]["sent_characters"]["mean"] for block in (h, hm)]
    assert (
        f"{sent[0]['mean']} documents on H (at least {sent[0]['min']}) and {sent[1]['mean']} on Hm"
        f" (at least {sent[1]['min']}) — {_n(size[0])} and {_n(size[1])} characters" in flat
    )
    config = report["config"]
    assert f"{_n(config['resamples'])} resamples, seed {config['seed']}, percentile CI95" in flat
    assert config["official_context_precision_gate"] == 0.63 and "**The 0.63 gate.**" in section
    assert report["subsets"]["H"]["collection_excluded"] == hm["collection_excluded"] == []
    assert "All 115 cases were collected: the collection excluded none" in flat
    assert f"The {_n(len(_unpacked(ARCHIVE)['chunks']))} chunks of the tracked archive" in flat
    assert report["provenance"]["host"] == ["iMac-Julia.local"]
    assert "the host the report calls `iMac-Julia.local`" in flat
    collected = report["config"]["collection"]
    assert [collected["retrieval_top_k"], collected["rerank_top_k"], collected["rrf_k"]] == [
        20,
        5,
        60,
    ]
    assert collected["rerank_batch"] == 8 and "in batches of 8" in flat


def test_the_notes_on_intervals_and_ndcg_are_recounted(report, capsule):
    flat = _flat(_section(capsule, "Numbers"))
    h = report["subsets"]["H"]["metrics"]
    student = [_width(h[name]["t_ci95"]) for name in MEASURED]
    case = [_width(h[name]["case_bootstrap_ci95"]) for name in MEASURED]
    assert (
        f"the t-interval comes out {min(student):.3f} to {max(student):.3f} wide where the case"
        f" bootstrap is {min(case):.3f} to {max(case):.3f} wide" in flat
    )
    assert all(wide > narrow for wide, narrow in zip(case, student, strict=True))
    wider = [
        name
        for name in MEASURED
        if _width(h[name]["case_bootstrap_ci95"]) > _width(h[name]["ci95_conservative"])
    ]
    assert wider == ["sent_precision"]
    assert "for `sent_precision` wider than the bound read" in flat
    largest = [h[name]["cluster_sizes"][0] for name in MEASURED]
    assert largest == [93, 93, 92, 94, 94]
    assert "One cluster holds 94 of the 100 cases (93 and 92 for the judged metrics)" in flat

    ruler = _json(JUDGE / "ruler-input.json")["ruler"]
    above: dict[str, int] = {}
    alone: dict[str, float] = {}
    counted: dict[str, int] = {}
    whole = below = 0
    for subset in SUBSETS:
        published = report["subsets"][subset]["per_case"]
        values = []
        above[subset] = 0
        for entry in ruler["cases"]:
            case_id = entry["case_id"]
            if entry["subset"] != subset or case_id not in published["ndcg_at_5"]:
                continue
            grades, seeds = entry["grades"], entry["seeds"][:5]
            own = [0 if key in seeds[:rank] else grades[key] for rank, key in enumerate(seeds)]
            ideal = _dcg(sorted(grades.values(), reverse=True)[:5])
            best = _dcg(sorted(own, reverse=True))
            assert best > 0, case_id
            assert _dcg(own) / ideal == pytest.approx(published["ndcg_at_5"][case_id], rel=1e-9)
            values.append(_dcg(own) / best)
            above[subset] += ideal > best + 1e-12
        alone[subset] = _mean(values)
        counted[subset] = len(values)
        full = [name for name, value in published["precision_at_5"].items() if value == 1.0]
        whole += len(full)
        below += sum(published["ndcg_at_5"][name] < 1 - 1e-12 for name in full)
    assert f"in {above['H']} of the {counted['H']} H cases and in all {counted['Hm']} of Hm" in flat
    assert above["Hm"] == counted["Hm"]
    assert f"{below} of the {whole} cases with `precision_at_5` 1.0 have an nDCG below 1" in flat
    assert f"give {alone['H']:.4f} on H and {alone['Hm']:.4f} on Hm" in flat
    assert "a sensitivity figure, not a registered metric" in flat


def test_the_judge_section_is_the_stores_and_the_retest(report, capsule):
    section = _section(capsule, "The judge and its stability")
    flat = _flat(section)
    plan = _unpacked(JUDGE / "plan.json.gz")
    case_of = {request["case_id"]: request["baseline_case_id"] for request in plan["requests"]}
    store = _rows(JUDGE / "opus.jsonl")
    valid = [row for row in store if row["status"] == "valid"]
    absent = [row for row in store if row["status"] == "absent"]
    assert len(valid) + len(absent) == len(store)
    assert len(valid) == len(plan["requests"]) == len({row["case_id"] for row in valid})
    assert f"{len(store)} attempts, {len(valid)} valid" in flat
    assert {row["reason"] for row in absent} == {"judge_unavailable"}
    for row in absent:
        assert f"`{case_of[row['case_id']]}`" in section
        assert row["case_id"] in {reply["case_id"] for reply in valid}
    sizes = [len(request["documents"]) for request in plan["requests"]]
    assert f"the {min(sizes)} to {max(sizes)} texts of one case" in flat
    ruler = _json(JUDGE / "ruler-input.json")
    unsent = sum(ruler["unjudged_units"].values())
    assert ruler["units"] == sum(sizes) and ruler["missing"] == {"opus": 0}
    assert f"{_n(ruler['units'])} texts were graded and {unsent} were not sent" in flat
    out = ruler["outbound"]["opus"]
    assert (
        f"{out['calls']} calls, {_n(out['texts'])} texts and {_n(out['characters'])} characters"
        in flat
    )
    summary = _json(JUDGE / "opus-retest.json")
    out = summary["outbound"]
    assert (
        f"{out['calls']} calls, {out['texts']} texts and {_n(out['characters'])} characters" in flat
    )

    runs = _rows(JUDGE / "runs.jsonl")
    for row in runs:
        assert f"{row['started'][11:16]}–{row['finished'][11:16]}" in section
    passes = [row for row in runs if row["store"] == "opus.jsonl"]
    assert [row.get("unavailable") for row in passes] == [None, "cli_timeout", "cli_exit", None]
    # A pass stopped from outside writes no row: its replies are the valid ones no row counts.
    unlogged = len(valid) - sum(row["valid"] for row in passes)
    assert f"{passes[1]['valid']} replies, ended by the timeout" in flat
    assert f"{unlogged} replies, stopped by the working session" in flat
    assert f"ran past the {_n(judge_tool.CLI_TIMEOUT_S)} s limit in the second pass" in flat
    assert "ended with the CLI's exit in the fourth" in flat
    assert f"{passes[2]['valid']} replies, ended by the CLI's exit" in flat
    assert f"the last {passes[3]['valid']}." in flat
    again = [row for row in runs if row["store"] == "opus-retest.jsonl"]
    assert sum(row["valid"] for row in again) == len(_rows(JUDGE / "opus-retest.jsonl"))

    retest = report["retest"]
    blocks = {"H and Hm": retest["all"], **retest["by_subset"]}
    rows = re.findall(
        rf"^\| (H and Hm|H|Hm) \| (\d+) \| (\d+) \| ([\d.]+) \| {INTERVAL} \| (\d+) \| (\d+) \|$",
        section,
        re.M,
    )
    assert [row[0] for row in rows] == ["H and Hm", "H", "Hm"]
    for label, cases, units, kappa, interval, exact, flips in rows:
        block = blocks[label]
        assert [int(cases), int(units), int(exact), int(flips)] == [
            block["cases"],
            block["units"],
            block["exact_agreement"],
            block["relevance_flips"],
        ]
        assert float(kappa) == pytest.approx(block["quadratic_kappa"], abs=FOUR_DECIMALS)
        assert _pair(interval) == pytest.approx(block["ci95"], abs=FOUR_DECIMALS)
    table = retest["all"]["cross_table"]
    cells = re.findall(r"^\| ([0-3]) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$", section, re.M)
    assert [row[0] for row in cells] == ["0", "1", "2", "3"]
    for first, *counts in cells:
        assert [int(count) for count in counts] == [table[first][second] for second in "0123"]
    total = sum(count for row in table.values() for count in row.values())
    assert total == retest["all"]["units"] == retest["units"]
    assert sum(table[grade][grade] for grade in "0123") == retest["all"]["exact_agreement"]
    assert retest["all"]["relevance_flips"] == sum(
        table[first][second]
        for first in "0123"
        for second in "0123"
        if (first in "23") != (second in "23")
    )
    assert retest["missing"] == {"first": 0, "second": 0}
    assert summary["bootstrap"] == {"seed": 20260925, "resamples": 10000, "cluster": "case"}


def test_the_capsule_claims_what_a_single_judge_may(report, capsule):
    flat = _flat(capsule)
    retest = report["retest"]
    assert report["grade_source"] == "single_judge" and report["judge"] == "opus"
    assert report["provisional_ruler"] is False
    assert retest["status"] == "ok" and retest["verdict"] == "single_judge"
    assert retest["all"]["ci95"][0] >= retest["threshold"] == judge_tool.RETEST_THRESHOLD
    for sentence in (
        "Neither a model of another vendor nor a person checked a grade of this run",
        "The points are read as points, and no decision rests on an interval of this run",
        "It is not a second voice",
        "for one grader with itself it is a low bar",
        "It is a prior for the registered route, not a measurement of it",
        "No contamination control",
        "No difference between the two is a result",
        "nothing here is speed evidence",
    ):
        assert sentence in flat, sentence
    for claim in ("model-cross-checked", "human-validated"):
        assert claim not in capsule
    assert report["latency_evidence"] is False


def test_the_timing_section_is_the_report(report, capsule):
    section = _section(capsule, "Timings and the host")
    flat = _flat(section)
    rows = re.findall(r"^\| `(\w+)` \| (\d+) \| ([\d.]+) \| ([\d.]+) \|$", section, re.M)
    assert [row[0] for row in rows] == list(report["timings_ms"])
    for stage, n, p50, p95 in rows:
        block = report["timings_ms"][stage]
        assert int(n) == block["n"] == report["total_cases"]
        assert float(p50) == pytest.approx(block["p50"], abs=ONE_DECIMAL)
        assert float(p95) == pytest.approx(block["p95"], abs=ONE_DECIMAL)
    collection = report["collection"]
    assert len(collection["pauses"]) == 2 and "**Pauses.** Two, both at a case boundary" in flat
    for pause in collection["pauses"]:
        assert pause["mode"] == "boundary"
        assert (
            f"in `{pause['stage']}` after {pause['case_lines']} cases, asked for at"
            f" {pause['requested'][11:19]} and in effect from {pause['effective'][11:19]} to"
            f" {pause['ended'][11:19]} UTC" in flat
        )
    attempts = collection["attempts"]
    assert {stage for stage, count in attempts.items() if count != 1} == {"retrieve", "grade"}
    assert attempts["retrieve"] == attempts["grade"] == 2
    assert "`retrieve` and `grade` each took two attempts" in flat
    peaks = collection["host_peaks"]
    assert (
        ", ".join(
            f"{block['foreign_cpu_samples']} of {_n(block['samples'])} in `{stage}`"
            for stage, block in peaks.items()
        )
        in flat
    )
    top = collection["peak_host_rss"]
    for field in ("mem_used_mb", "swap_used_mb", "load1", "collector_plus_ollama_rss_kb"):
        assert max(peaks, key=lambda stage: peaks[stage][field]) == "grade", field
        assert top.get(field, peaks["grade"][field]) == peaks["grade"][field], field
    assert (
        f"{_n(top['mem_used_mb'])} MB of memory used, {_n(top['swap_used_mb'])} MB of swap, a"
        f" one-minute load of {peaks['grade']['load1']}, and"
        f" {_n(top['collector_plus_ollama_rss_kb'])} kB of resident memory" in flat
    )
    seconds, started = collection["stage_seconds"], collection["started"]
    assert (
        f"started {started[:10]} {started[11:16]} UTC; {_n(sum(seconds.values()))} s of stage"
        f" time, {_n(seconds['grade'])} s of it grading" in _flat(capsule)
    )
    assert f"{_n(report['provenance']['peak_rss_bytes'])} bytes" in _flat(capsule)


def test_the_summaries_of_the_loss_map_follow_from_its_cases(loss, report):
    assert loss["manifest_sha256"] == report["manifest_sha256"]
    assert loss["chunk_archive"]["sha256"] == _sha(ARCHIVE)
    assert loss["index_stage_losses"] == []
    assert loss["routing_mode"] == "hybrid; graph off; model routing off; single-turn"
    for subset in SUBSETS:
        rows = [row for row in loss["per_case"] if row["subset"] == subset]
        block = loss["summary"][subset]
        assert len(rows) == block["case_denominator"] == report["denominators"][subset]
        cases: Counter = Counter()
        terms: Counter = Counter()
        for row in rows:
            for term in row["terms"]:
                assert _term_loss(term["presence"]) == term["first_loss"], row["case_id"]
                terms[term["first_loss"]] += 1
            first = min((term["first_loss"] for term in row["terms"]), key=LOSSES.index)
            assert row["first_loss"] == first, row["case_id"]
            cases[first] += 1
        assert sum(terms.values()) == block["term_denominator"]
        for name in LOSSES:
            assert block["first_loss_cases"][name]["count"] == cases[name], (subset, name)
            assert block["first_loss_terms"][name]["count"] == terms[name], (subset, name)
        for previous, stage in zip((None, *STAGES), STAGES, strict=False):
            held = [[term["presence"][stage] for term in row["terms"]] for row in rows]
            counted: dict[str, int | None] = {
                "terms_held": sum(map(sum, held)),
                "cases_all_held": sum(all(flags) for flags in held),
                "terms_lost": None,
                "terms_gained": None,
                "cases_with_lost_term": None,
            }
            if previous is not None:
                before = [[term["presence"][previous] for term in row["terms"]] for row in rows]
                moves = [
                    list(zip(was, now, strict=True)) for was, now in zip(before, held, strict=True)
                ]
                counted["terms_lost"] = sum(was and not now for case in moves for was, now in case)
                counted["terms_gained"] = sum(
                    now and not was for case in moves for was, now in case
                )
                counted["cases_with_lost_term"] = sum(
                    any(was and not now for was, now in case) for case in moves
                )
            assert {key: block["stages"][stage][key] for key in counted} == counted, (subset, stage)
        for rule, flag in (("registered", "ru_to_en"), ("archive_proxy", "archive_proxy")):
            for side, wanted in (("inside", True), ("outside", False)):
                picked = Counter(row["first_loss"] for row in rows if row[flag] is wanted)
                stratum = loss["g2"][rule]["subsets"][subset][side]
                assert stratum["case_denominator"] == sum(picked.values()), (subset, rule, side)
                for name in LOSSES:
                    assert stratum["first_loss_cases"][name]["count"] == picked[name], (rule, name)
        gains = [
            row["case_id"]
            for row in rows
            for term in row["terms"]
            if term["presence"]["expansion"] and not term["presence"]["rerank"]
        ]
        gained = loss["g3"][subset]["rerank_to_expansion"]
        assert [gained["gained_terms"], gained["gained_cases"]] == [len(gains), len(set(gains))]
        assert gained["lost_terms"] == loss["g3"][subset]["rerank_to_grading"]["lost_terms"] == 0


def test_the_loss_map_tables_are_the_loss_map(loss, capsule):
    section = _section(capsule, "The evidence-loss map")
    flat = _flat(section)
    first = re.findall(
        r"^\| (H|Hm) \| `(\w+)` \| (\d+) of (\d+) \| (\d+) of (\d+) \|$", section, re.M
    )
    assert [row[:2] for row in first] == [(subset, name) for subset in SUBSETS for name in LOSSES]
    for subset, name, cases, case_total, terms, term_total in first:
        block = loss["summary"][subset]
        assert [int(cases), int(case_total)] == [
            block["first_loss_cases"][name]["count"],
            block["case_denominator"],
        ]
        assert [int(terms), int(term_total)] == [
            block["first_loss_terms"][name]["count"],
            block["term_denominator"],
        ]
    stages = re.findall(
        r"^\| (H|Hm) \| `(\w+)` \| (\d+) of (\d+) \| (—|\d+) \| (—|\d+) \| (\d+) of (\d+)"
        r" \| (—|\d+) \|$",
        section,
        re.M,
    )
    assert [row[:2] for row in stages] == [(subset, name) for subset in SUBSETS for name in STAGES]
    for subset, name, held, terms, lost, gained, whole, cases, losing in stages:
        block = loss["summary"][subset]["stages"][name]
        assert [None if cell == "—" else int(cell) for cell in (lost, gained, losing)] == [
            block["terms_lost"],
            block["terms_gained"],
            block["cases_with_lost_term"],
        ]
        assert [int(held), int(terms)] == [block["terms_held"], block["term_denominator"]]
        assert [int(whole), int(cases)] == [block["cases_all_held"], block["case_denominator"]]
    strata = re.findall(
        r"^\| (H|Hm) \| (inside|outside) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$", section, re.M
    )
    assert [row[:2] for row in strata] == [
        (subset, side) for subset in SUBSETS for side in ("inside", "outside")
    ]
    registered = loss["g2"]["registered"]
    for subset, side, cases, pool, rerank, none in strata:
        block = registered["subsets"][subset][side]
        counts = {name: entry["count"] for name, entry in block["first_loss_cases"].items()}
        assert int(cases) == block["case_denominator"] == int(pool) + int(rerank) + int(none)
        assert [int(pool), int(rerank), int(none)] == [
            counts["index_to_pool_unknown"],
            counts["rerank"],
            counts["no_observed_loss"],
        ]
    assert f"`{registered['rule']['version']}`" in section

    def lossy(block: dict[str, Any]) -> int:
        return block["case_denominator"] - block["first_loss_cases"]["no_observed_loss"]["count"]

    inside = registered["subsets"]["H"]["inside"]
    proxy = loss["g2"]["archive_proxy"]["subsets"]["H"]["inside"]
    assert (
        f"On H {lossy(inside)} of the {lossy(loss['summary']['H'])} cases with a loss are inside"
        in flat
    )
    assert (
        f"the H stratum is {proxy['case_denominator']} cases with the same {lossy(proxy)} losses"
        in flat
    )
    assert lossy(proxy) == lossy(inside)
    h, hm = (loss["g3"][subset]["rerank_to_expansion"] for subset in SUBSETS)
    assert (
        f"{h['gained_terms']} terms in {h['gained_cases']} cases of H, {hm['gained_terms']} pairs"
        f" in {hm['gained_cases']} cases of Hm" in flat
    )
    watched = loss["observability"]
    assert [watched[name]["status"] for name in ("bm25_candidates", "coherence", "graph_caps")] == [
        "not_observable"
    ] * 3
    assert watched["answer"]["status"] == "unknown"
    assert f"{_n(len(loss['files']))} files" in _flat(capsule)
    roots = Counter(entry["root"] for entry in loss["files"])
    assert roots == {"run": len(loss["files"]) - 1, "chunk_archive": 1}
    assert f"the {_n(roots['run'])} files of the run directory" in _flat(capsule)

    # What the two gold rules are made of, and the RU→EN rows by terms.
    rows = {name: [row for row in loss["per_case"] if row["subset"] == name] for name in SUBSETS}
    terms = {name: [term for row in rows[name] for term in row["terms"]] for name in SUBSETS}
    single = sum(len(term["term"].split()) == 1 for term in terms["H"])
    assert f"the {len(terms['H'])} keyword terms" in flat
    assert f"{single} of them are a single word" in flat
    latin_hm = [term for term in terms["Hm"] if _latin(term["term"])]
    phrases = sum(len(term["term"].split()) in (2, 3) for term in latin_hm)
    assert (
        f"{len(latin_hm)} of the {len(terms['Hm'])} terms are written in Latin letters alone,"
        f" {phrases} of them phrases of two or three words" in flat
    )
    assert f"all {_n(len(_unpacked(ARCHIVE)['chunks']))} chunks" in flat
    assert watched["query_transform"]["status"] == "reference_only"
    assert {row["query_transform"] for row in loss["per_case"]} == {"rewrite"}
    assert f"the rewritten query in all {len(loss['per_case'])} cases" in flat
    sides = {
        side: [row for row in rows["H"] if row["ru_to_en"] is wanted]
        for side, wanted in (("inside", True), ("outside", False))
    }
    by_side = {
        side: [term for row in part for term in row["terms"]] for side, part in sides.items()
    }
    assert (
        f"{_lost(sides['inside'])} of its {len(sides['inside'])} cases against"
        f" {_lost(sides['outside'])} of the {len(sides['outside'])} outside, and by terms"
        f" {_lost(by_side['inside'])} of {len(by_side['inside'])} lost inside against"
        f" {_lost(by_side['outside'])} of {len(by_side['outside'])} outside" in flat
    )
    latin = [term for term in terms["H"] if _latin(term["term"])]
    other = [term for term in terms["H"] if not _latin(term["term"])]
    assert (
        f"Of the {_lost(terms['H'])} lost H terms {_lost(latin)} are written in Latin letters"
        f" alone — {_lost(latin)} of the {len(latin)} such terms against {_lost(other)} of the"
        f" {len(other)} others" in flat
    )
    inside_hm = sum(row["ru_to_en"] for row in rows["Hm"])
    assert (
        f"On Hm the stratum is {inside_hm} of the {len(rows['Hm'])} cases and shows nothing"
        f" apart; with {len(latin_hm)} of the {len(terms['Hm'])} terms in Latin letters" in flat
    )
    assert (
        f"counts over {_lost(rows['H'])} and {_lost(rows['Hm'])} cases with a loss, and no"
        " interval stands behind them" in flat
    )


def test_the_reading_of_the_lost_hm_pairs_is_recounted(reading, loss, capsule):
    section = _section(capsule, "Where the lost Hm pairs are")
    pairs, links, documents = reading["pairs"], reading["links"], reading["documents"]
    assert set(pairs) == set(PAIR_ROWS.values())
    rows = re.findall(r"^\| (first lost [^|]+) \| ([^|]+) \| (\d+) \| (\d+) \|$", section, re.M)
    assert {
        (where, document): (int(count), int(link)) for where, document, count, link in rows
    } == {label: (pairs[key], links[key]) for label, key in PAIR_ROWS.items()}
    table = re.findall(r"^\| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$", section, re.M)
    assert {tuple(int(cell) for cell in row[:4]): int(row[4]) for row in table} == dict(documents)
    assert len(table) == len(documents)

    flat = _flat(section)
    cases = sum(documents.values())
    gold, pool, seeds, sent = (
        sum(key[index] * count for key, count in documents.items()) for index in range(4)
    )
    summary = loss["summary"]["Hm"]
    assert cases == summary["case_denominator"]
    assert sent == seeds
    assert (
        f"the {cases} cases name {gold} gold documents: the pool holds {pool} of them, the five"
        f" seeds {seeds}, and the sent context the same {sent}" in flat
    )
    lacking = sum(count for key, count in documents.items() if key[1] < key[0])
    kept = sum(count for key, count in documents.items() if key[2] == key[0])
    empty = sum(count for key, count in documents.items() if key[3] == 0)
    assert (
        f"The pool lacks a gold document in {lacking} of the {cases} cases; in the other"
        f" {cases - lacking} it has them all, and the five seeds keep them all in {kept}. In"
        f" {empty} cases no gold document reaches the sent context." in flat
    )
    lost = sum(pairs.values())
    in_pool = sum(count for key, count in pairs.items() if key[1])
    assert lost == summary["term_denominator"] - summary["stages"]["grading"]["terms_held"]
    assert f"{in_pool} of the {lost} lost pairs lie in a document the pool already holds" in flat
    spread = reading["seed_documents"]
    assert (
        f"from one document in {spread[1]} cases, two in {spread[2]}, three in {spread[3]}, four"
        f" in {spread[4]} and five in {spread[5]}" in flat
    )

    choice = _flat(_section(capsule, "Mechanisms for the first campaign"))
    h = loss["summary"]["H"]
    whole = "no_observed_loss"
    assert (
        f"On H {h['first_loss_cases'][whole]['count']} of {h['case_denominator']} cases reach the"
        f" sent context with every term; on Hm {summary['first_loss_cases'][whole]['count']} of"
        f" {cases} do, and {lost} of {summary['term_denominator']} pairs are lost" in choice
    )
    assert f"documents the pool already holds ({in_pool} of {lost})" in choice
    outside = ("index_to_pool_unknown", False, False)
    assert (
        f"reaches the document of {sum(links.values())} of the {lost} lost pairs —"
        f" {links[outside]} of the {pairs[outside]} whose document the pool lacks" in choice
    )
    cut = "rerank"
    assert (
        f"{h['first_loss_cases'][cut]['count']} of the"
        f" {h['case_denominator'] - h['first_loss_cases'][whole]['count']} cases with a loss,"
        f" {h['first_loss_terms'][cut]['count']} of the"
        f" {h['term_denominator'] - h['first_loss_terms'][whole]['count']} lost terms" in choice
    )
    assert (
        f"{pool - seeds} of the {pool} gold documents the Hm pool holds are not among the seeds"
        in choice
    )
    assert "**Second slot: not taken.**" in choice
    assert "the freeze stands" in choice

    hm_rows = [row for row in loss["per_case"] if row["subset"] == "Hm"]
    named = Counter(term["document"] for row in hm_rows for term in row["terms"])
    by_file = Counter(
        term["document"]
        for row in hm_rows
        for term in row["terms"]
        if term["first_loss"] != "no_observed_loss"
    )
    most = by_file.most_common()
    assert sum(named.values()) == gold and sum(by_file.values()) == lost
    assert most[2][1] > most[3][1], "the three files with most lost pairs are not a tie"
    assert f"over {len(named)} files" in flat
    for name, _ in most[:3]:
        assert f"`{name}`" in section
    assert f"carry {sum(count for _, count in most[:3])} of the {lost} lost pairs" in flat
    arrived = sum(
        not term["presence"]["grading"]
        and term["document"] in row["source_documents_present"]["grading"]
        for row in hm_rows
        for term in row["terms"]
    )
    assert arrived == pairs[("index_to_pool_unknown", True, True)]
    assert f"For {arrived} of them the document reached the sent context" in flat


def test_the_two_rulers_are_set_side_by_side(report, loss, capsule):
    section = _section(capsule, "The two rulers side by side")
    flat = _flat(section)
    per = {subset: report["subsets"][subset]["per_case"] for subset in SUBSETS}
    groups: dict[tuple[str, str], list[str]] = {}
    for row in loss["per_case"]:
        if row["subset"] == "H":
            whole = row["first_loss"] == "no_observed_loss"
            label = "no observed loss" if whole else "the map shows a loss"
        else:
            gold = {term["document"] for term in row["terms"]}
            sent = gold & set(row["source_documents_present"]["grading"])
            label = f"{'a' if sent else 'no'} gold document in the sent context"
        groups.setdefault((row["subset"], label), []).append(row["case_id"])
    table = {
        (subset, label): (int(cases), float(precision), float(sent))
        for subset, label, cases, precision, sent in re.findall(
            r"^\| (H|Hm) \| ([^|]+) \| (\d+) \| ([\d.]+) \| ([\d.]+) \|$", section, re.M
        )
    }
    assert table.keys() == groups.keys() and len(table) == 4
    for (subset, label), cases in groups.items():
        judged = [case for case in cases if case in per[subset]["precision_at_5"]]
        count, precision, sent = table[(subset, label)]
        assert count == len(judged), label
        for cell, metric in ((precision, "precision_at_5"), (sent, "sent_precision")):
            mean = _mean(per[subset][metric][case] for case in judged)
            assert cell == pytest.approx(mean, abs=FOUR_DECIMALS), (label, metric)
    # One H case without a loss is the one the judge did not grade.
    assert len(groups[("H", "no observed loss")]) == table[("H", "no observed loss")][0] + 1

    h, hm = (report["subsets"][subset]["metrics"] for subset in SUBSETS)
    assert all(hm[name]["point"] > h[name]["point"] for name in report_tool.JUDGED)
    assert "By the judge Hm stands above H on all three judged metrics" in flat
    empty, held = (
        table[("Hm", f"{word} gold document in the sent context")] for word in ("no", "a")
    )
    assert empty[1] > held[1] and empty[2] > held[2]
    lossy, clean = table[("H", "the map shows a loss")], table[("H", "no observed loss")]
    assert lossy[2] > clean[2]
    assert f"The groups are {lossy[0]} and {empty[0]} cases" in flat
    name = "aircargo-gr-road-air-handover"
    row = next(row for row in loss["per_case"] if row["case_id"] == name)
    kept = sum(term["presence"]["grading"] for term in row["terms"])
    assert f"`{name}` keeps {kept} of its {len(row['terms'])} pairs" in flat
    assert kept == 0
    assert per["Hm"]["precision_at_5"][name] == per["Hm"]["sent_precision"][name] == 1.0
    assert "precision is no measure of completeness" in flat
    assert "rests on the map alone" in flat


def test_the_counts_behind_the_outcome_are_recounted(report, loss, reading, capsule):
    choice = _flat(_section(capsule, "Mechanisms for the first campaign"))
    assert "**Outcome: the plan's default stands" in choice
    assert "The map did not choose it; it gives no ground to replace it." in choice
    assert "H1 is the plan's default left standing, not a measured gain" in choice
    rows = {name: [row for row in loss["per_case"] if row["subset"] == name] for name in SUBSETS}
    terms = {name: [term for row in rows[name] for term in row["terms"]] for name in SUBSETS}
    cases, every = rows["H"] + rows["Hm"], terms["H"] + terms["Hm"]
    before, cut = "index_to_pool_unknown", "rerank"
    assert _lost(every) == _lost(every, before) + _lost(every, cut)
    assert (
        f"before the pool for {_lost(every, before)} of the {_lost(every)} lost terms"
        f" ({_lost(cases, before)} of the {_lost(cases)} cases with a loss) and at the rerank cut"
        f" for {_lost(every, cut)} ({_lost(cases, cut)} cases)" in choice
    )
    assert (
        f"on Hm {_lost(terms['Hm'], before)} of the {_lost(terms['Hm'])} lost pairs go before the"
        f" pool, on H {_lost(terms['H'], cut)} of the {_lost(terms['H'])} lost terms at the cut"
        in choice
    )
    inside_hm = sum(row["ru_to_en"] for row in rows["Hm"])
    assert f"Hm is a single cluster of {len(rows['Hm'])} cases, {inside_hm} of them RU→EN" in choice
    assert report["subsets"]["Hm"]["cluster_unit"]["count"] == 1
    assert (
        f"the first loss of {_lost(terms['Hm'], cut)} of the {_lost(terms['Hm'])} lost Hm pairs"
        in choice
    )
    pairs = reading["pairs"]
    assert (
        f"for {pairs[(cut, True, False)]} the passage with the term was in the pool and was cut,"
        f" for the other {pairs[(before, True, False)]} the pool held only other passages" in choice
    )
    per = report["subsets"]["H"]["per_case"]["sent_precision"]
    at_cut = [row["case_id"] for row in rows["H"] if row["first_loss"] == cut]
    full = sum(per[case] == 1.0 for case in at_cut)
    assert (
        f"in {full} of the {len(at_cut)} H cases the judge finds every sent document relevant"
        in choice
    )
    sides = {
        wanted: [row for row in rows["H"] if row["ru_to_en"] is wanted] for wanted in (True, False)
    }
    latin = [term for term in terms["H"] if _latin(term["term"])]
    assert (
        f"a loss in {_lost(sides[True])} of the {len(sides[True])} cases inside the RU→EN stratum"
        f" against {_lost(sides[False])} of the {len(sides[False])} outside, and {_lost(latin)}"
        f" of the {_lost(terms['H'])} lost terms in Latin letters" in choice
    )
    assert f"Over {_lost(rows['H'])} cases with a loss" in choice
    for claim in ("measured reason the plan asks for", "The map does not point elsewhere"):
        assert claim not in choice


def test_the_report_names_the_code_that_built_it(report, capsule):
    code = report["provenance"]["report_code"]
    assert code["tracked_tree_clean"] is True
    assert sorted(code["blobs"]) == sorted(report_tool.CODE_FILES)
    assert f"`{code['commit']}`" in capsule
    found = _git("cat-file", "-e", f"{code['commit']}^{{commit}}")
    if found is None or found.returncode != 0:
        pytest.skip("the commit that built the report is not in this copy")
    for name, blob in code["blobs"].items():
        shown = _git("rev-parse", f"{code['commit']}:{name}")
        assert shown is not None and shown.stdout.decode().strip() == blob, name


def test_the_ledger_records_the_baseline(report):
    rows = _rows(LEDGER)
    assert [row["entry"] for row in rows] == list(range(1, len(rows) + 1))
    entry = rows[1]
    assert entry["artifact"] == "reports/baseline/68c5f8d/report.json"
    assert entry["artifact_sha256"] == _sha(RUN / "report.json")
    assert entry["config_sha256"] == report["provenance"]["ledger_entry"]["config_sha256"]
    assert entry["families_touched"] == list(SUBSETS)
    assert entry["verdict"] == "development_baseline_single_judge"
    assert sorted(entry) == sorted(rows[0])
