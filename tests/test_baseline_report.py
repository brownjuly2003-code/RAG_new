"""The baseline report builder on fixture runs; no model, no network, no real run."""

import gzip
import json
import math
import re
from pathlib import Path
from typing import ClassVar

import pytest

from evaluation.blinded_judge import read_store
from evaluation.blinded_judge_clients import Reply
from evaluation.ragas_eval import context_precision
from evaluation.semantic_ruler import family_clusters
from scripts import baseline_judge as judge_tool
from scripts import baseline_report as report
from scripts import production_baseline as baseline
from scripts import production_parity as parity

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "docs/specs/semantic-precision-metrics.md"
GRADES = {"zebra": 3, "okapi": 2, "gnu": 1}


class TokenJudge:
    """Grades a text by the animal it names, whatever the order of the request."""

    route = "fixture"
    parameters: ClassVar[dict] = {"model": "fixture", "temperature": 0}

    def __init__(self, grades=None, version=None):
        self.grades = GRADES if grades is None else grades
        self.version = version

    def grade(self, prompt):
        blocks = re.split(r"^D\d+$", prompt, flags=re.MULTILINE)[1:]
        grades = [
            {
                "doc": f"D{position}",
                "grade": max((g for token, g in self.grades.items() if token in block), default=0),
            }
            for position, block in enumerate(blocks, 1)
        ]
        return Reply(json.dumps({"grades": grades}), "fixture-reported-model", {"tokens": 1}, 0.5)

    def describe(self):
        return {"cli_version": self.version} if self.version else {}


@pytest.fixture(autouse=True)
def few_resamples(request, monkeypatch):
    """Tests run 300 resamples; the one that asks for `registered_resamples` keeps 10 000."""
    if "registered_resamples" not in request.fixturenames:
        monkeypatch.setattr(report, "RESAMPLES", 300)


@pytest.fixture
def registered_resamples():
    return report.RESAMPLES


def _document(text, source="a.md", addressed=True):
    return {
        "text": text,
        "text_sha256": baseline.text_sha(text),
        "metadata": {"source": source},
        "chunk_address": {
            "source_id": source,
            "source_revision": baseline.text_sha(source),
            "chunker_version": "fixture-chunker",
            "section_path": [f"Section {baseline.text_sha(text)[:8]}"],
        }
        if addressed
        else None,
        "address_reason": None if addressed else "address_unresolved",
    }


def _case(case_id, subset="H", keywords=()):
    return {
        "case_id": case_id,
        "subset": subset,
        "query": f"Which cargo rule covers {case_id}?",
        "expected": {"answer_contains": list(keywords)},
    }


def _row(seeds, sent):
    return {
        "status": "ok",
        "seed_documents": seeds,
        "documents": sent,
        "sent_context_sha256": baseline.text_sha("".join(d["text"] for d in sent)),
    }


EXCLUSION = {"case_id": "h3", "subset": "H", "stage": "grade", "reason": "model failure"}
SEEDS_H1 = [_document("zebra seed one"), _document("plain seed two")]
SENT_H1 = [_document("zebra seed one with its neighbours"), _document("plain seed two widened")]
SEEDS_H2 = [_document("plain lonely seed", "b.md")]
SEEDS_M1 = [_document("zebra multihop seed", "c.md")]


def _pairs():
    return [
        (_case("h1", keywords=["neighbours"]), _row(SEEDS_H1, SENT_H1)),
        (_case("h2"), _row(SEEDS_H2, SEEDS_H2)),
        (_case("h3"), {"status": "excluded", "exclusion": EXCLUSION}),
        (_case("m1", "Hm"), _row(SEEDS_M1, [])),
    ]


def _write_run(run, pairs, code_sha="c0de"):
    manifest = {"cases": [case for case, _ in pairs], "code_sha": code_sha}
    identity = parity.digest(manifest)
    parity.write_new(run / "manifest.json", manifest)
    parity.write_new(run / "registration.json", {"manifest_sha256": identity})
    collected = [case for case, row in pairs if row["status"] == "ok"]
    parity.save_stage(
        run / "report.json",
        {
            "total_cases": len(pairs),
            "denominator": len(collected),
            "denominators": {
                subset: sum(case["subset"] == subset for case in collected)
                for subset in ("H", "Hm")
            },
            "exclusions": [row["exclusion"] for _, row in pairs if row["status"] != "ok"],
            "timings_ms": {"retrieve": {"n": len(pairs), "p50": 10.0, "p95": 20.0}},
            "timing_scope": "fixture scope",
            "latency_evidence": False,
            "provenance": {
                "code_sha": code_sha,
                "config": {"retrieval_top_k": 20},
                "raw_judge_replies": baseline.T65,
                "peak_host_rss": "N/A: collector only",
            },
        },
        identity,
    )
    for case, row in pairs:
        parity.save_stage(run / "grade" / f"{case['case_id']}.json", row, identity)
    return identity


def _write_families(path, case_documents):
    families = {"a.md": "f1", "b.md": "f1", "c.md": "f2", "d.md": "f3"}
    register = {
        "families": [
            {
                "family_id": family,
                "members": [
                    {"source_id": name} for name, owner in families.items() if owner == family
                ],
            }
            for family in sorted(set(families.values()))
        ],
        "development_used": {
            subset: {"case_documents": documents} for subset, documents in case_documents.items()
        }
        | {"pilot": {"documents": ["d.md"]}},
    }
    path.write_text(json.dumps(register), encoding="utf-8")
    return path


CASE_DOCUMENTS = {
    "H": {"h1": ["a.md"], "h2": ["b.md", "c.md"], "h3": ["d.md"]},
    "Hm": {"m1": ["c.md"]},
}


@pytest.fixture
def evidence(tmp_path):
    def create(pairs=None, *, retest=True, client=None, case_documents=None):
        run, inputs, judges = tmp_path / "run", tmp_path / "evidence", tmp_path / "evidence/judge"
        _write_run(run, _pairs() if pairs is None else pairs)
        report.export(run, inputs)
        judge_tool.write_plan(judges, judge_tool.build_plan(run))
        client = TokenJudge(version="9.9.9 (fixture)") if client is None else client
        judge_tool.judge(judges, "opus", client=client)
        judge_tool.consensus(judges)
        if retest:
            judge_tool.judge(judges, "opus", client=client, retest=True)
            judge_tool.retest(judges, "opus")
        families = _write_families(
            tmp_path / "families.json", CASE_DOCUMENTS if case_documents is None else case_documents
        )
        return run, inputs, judges, families

    return create


def _build(inputs, judges, families, **options):
    return report.build(inputs, judges, families=families, families_sha256=None, **options)


def test_export_keeps_five_seeds_every_sent_text_and_the_collector_files(tmp_path):
    seeds = [_document(f"seed {i}") for i in range(6)]
    sent = [_document("seed 0 widened"), seeds[5]]
    run, out = tmp_path / "run", tmp_path / "evidence"
    identity = _write_run(
        run,
        [
            (_case("h1"), _row(seeds, sent)),
            (_case("h3"), {"status": "excluded", "exclusion": EXCLUSION}),
        ],
    )
    summary = report.export(run, out)
    for source, target in (
        ("manifest.json", "manifest.json"),
        ("registration.json", "registration.json"),
        ("report.json", "collector-report.json"),
    ):
        assert (out / target).read_bytes() == (run / source).read_bytes()
    contexts = json.loads(gzip.decompress((out / "contexts.json.gz").read_bytes()))
    first, second = contexts["cases"]
    assert first["seeds"] == [document["text_sha256"] for document in seeds[:5]]
    assert first["sent"] == [document["text_sha256"] for document in sent]
    assert first["grade_file_sha256"] == parity.file_sha(run / "grade/h1.json")
    assert second == {
        "case_id": "h3",
        "subset": "H",
        "status": "excluded",
        "exclusion": EXCLUSION,
        "grade_file_sha256": parity.file_sha(run / "grade/h3.json"),
    }
    assert set(contexts["texts"]) == {document["text_sha256"] for document in [*seeds, sent[0]]}
    assert contexts["run_sha256"] == identity == summary["run_sha256"]
    assert summary == {
        "run_sha256": identity,
        "cases": 2,
        "collected": 1,
        "texts": 7,
        "contexts_sha256": parity.digest(contexts),
    }
    before = (out / "contexts.json.gz").read_bytes()
    assert report.export(run, out) == summary
    assert (out / "contexts.json.gz").read_bytes() == before


def test_export_refuses_another_run_in_the_same_directory_and_a_wrong_text_hash(tmp_path):
    out = tmp_path / "evidence"
    _write_run(tmp_path / "one", [(_case("h1"), _row(SEEDS_H1, SENT_H1))])
    _write_run(tmp_path / "two", [(_case("h2"), _row(SEEDS_H2, SEEDS_H2))])
    report.export(tmp_path / "one", out)
    with pytest.raises(FileExistsError, match="manifest.json"):
        report.export(tmp_path / "two", out)
    broken = {**_document("zebra"), "text_sha256": baseline.text_sha("another text")}
    _write_run(tmp_path / "three", [(_case("h1"), _row([broken], []))])
    with pytest.raises(baseline.IntegrityError, match="text hash mismatch"):
        report.export(tmp_path / "three", tmp_path / "elsewhere")


def test_build_gives_the_hand_computed_points_of_every_subset(evidence):
    _, inputs, judges, families = evidence()
    built = _build(inputs, judges, families)
    h, hm = built["subsets"]["H"], built["subsets"]["Hm"]
    assert h["per_case"]["precision_at_5"] == {"h1": 0.2, "h2": 0.0}
    assert h["per_case"]["sent_precision"] == {"h1": 0.5, "h2": 0.0}
    ideal = 3 + 3 / math.log2(3)
    assert h["per_case"]["ndcg_at_5"] == {"h1": pytest.approx(3 / ideal)}
    assert h["zero_idcg"] == ["h2"]
    assert hm["per_case"]["precision_at_5"] == {"m1": 0.2}
    assert hm["per_case"]["sent_precision"] == {"m1": 0.0}
    assert hm["per_case"]["ndcg_at_5"] == {"m1": 1.0}
    assert h["metrics"]["precision_at_5"]["point"] == pytest.approx(0.1)
    assert h["metrics"]["sent_precision"]["point"] == pytest.approx(0.25)
    assert (h["metrics"]["ndcg_at_5"]["n"], h["metrics"]["ndcg_at_5"]["excluded"]) == (1, 1)
    assert (h["case_count"], h["collected"]) == (3, 2)
    assert h["collection_excluded"] == [{"case_id": "h3", "exclusion": EXCLUSION}]
    assert h["judged_excluded"] == [] and hm["judged_excluded"] == []
    assert h["contexts"]["seeds"] == {"n": 2, "min": 1, "mean": 1.5, "max": 2}
    assert hm["contexts"]["empty_sent"] == 1 and hm["contexts"]["sent"]["max"] == 0
    assert built["total_cases"] == 4 and built["denominators"] == {"H": 2, "Hm": 1}
    assert built["exclusions"] == [EXCLUSION]
    assert built["grade_source"] == "single_judge" and built["judge"] == "opus"


def test_lexical_ruler_reads_the_asked_question_the_sent_texts_and_the_case_keywords(evidence):
    pairs = _pairs()
    _, inputs, judges, families = evidence(pairs)
    built = _build(inputs, judges, families)
    h, hm = built["subsets"]["H"], built["subsets"]["Hm"]
    question = pairs[0][0]["query"]
    sent = context_precision(question, [d["text"] for d in SENT_H1], ["neighbours"])
    seeds = context_precision(question, [d["text"] for d in SEEDS_H1], ["neighbours"])
    assert sent == pytest.approx(0.2 / 1.5) and seeds == 0.0
    assert context_precision(question, [d["text"] for d in SENT_H1], []) == 0.0
    assert h["per_case"]["context_precision"] == {"h1": sent, "h2": 0.0}
    assert h["per_case"]["context_precision_seeds"] == {"h1": seeds, "h2": 0.0}
    assert h["metrics"]["context_precision"]["point"] == pytest.approx(sent / 2)
    assert (h["metrics"]["context_precision"]["n"], hm["metrics"]["context_precision"]["n"]) == (
        2,
        1,
    )
    assert hm["per_case"]["context_precision"] == {"m1": 0.0}
    assert built["config"]["official_context_precision_gate"] == 0.63
    assert built["config"]["gate_applies_to"].startswith("neither lexical number here")


def test_intervals_follow_the_registered_small_cluster_rule(evidence, registered_resamples):
    assert registered_resamples == 10_000
    _, inputs, judges, families = evidence()
    built = _build(inputs, judges, families)
    h, hm = built["subsets"]["H"], built["subsets"]["Hm"]
    assert h["cluster_unit"]["count"] == 2 and h["cluster_unit"]["sizes"] == [2, 1]
    assert h["cluster_unit"]["components"] == [["h1", "h2"], ["h3"]]
    assert h["cluster_unit"]["mapping"] == {"h1": ["f1"], "h2": ["f1", "f2"], "h3": ["f3"]}
    metric = h["metrics"]["precision_at_5"]
    assert (metric["n"], metric["clusters"], metric["cluster_sizes"]) == (2, 1, [2])
    assert metric["ci95"] == pytest.approx([0.1, 0.1])
    assert metric["t_ci95"] == [0.0, 1.0] and metric["ci95_conservative"] == [0.0, 1.0]
    assert metric["case_bootstrap_ci95"] == pytest.approx([0.0, 0.2])
    assert hm["metrics"]["sent_precision"]["t_ci95"] == [0.0, 1.0]
    assert built["config"]["seed"] == 20261001 and built["config"]["resamples"] == 10_000
    two = {"H": {"h1": ["a.md"], "h2": ["c.md"], "h3": ["d.md"]}, "Hm": {"m1": ["c.md"]}}
    apart = _build(inputs, judges, _write_families(families, two))["subsets"]["H"]
    assert apart["metrics"]["precision_at_5"]["clusters"] == 2
    assert apart["metrics"]["precision_at_5"]["t_ci95"] == [0.0, 1.0]
    assert apart["metrics"]["ndcg_at_5"]["clusters"] == 1


def test_unmeasured_metrics_are_printed_with_their_reason_and_cover_the_deciding_table(evidence):
    _, inputs, judges, families = evidence()
    built = _build(inputs, judges, families)
    measured = {"sent_precision", "precision_at_5", "context_precision", "retrieve_p95"}
    assert set(report.UNMEASURED) | measured == set(baseline.DECIDING_METRICS)
    assert not set(report.UNMEASURED) & measured
    for block in built["subsets"].values():
        for name, reason in report.UNMEASURED.items():
            assert block["metrics"][name] == {"point": "N/A", "reason": reason, "n": 0}
    deciding = built["provenance"]["metrics"]
    assert list(deciding) == list(baseline.DECIDING_METRICS)
    for name in report.UNMEASURED:
        assert set(deciding[name]) == {"n", "clusters", "MDE", "achieved_power"}
        assert all(value.startswith("N/A: ") for value in deciding[name].values())
    for name in ("sent_precision", "precision_at_5", "context_precision"):
        assert deciding[name]["H"]["n"] == 2 and deciding[name]["H"]["clusters"] == 1
        assert deciding[name]["Hm"]["n"] == 1
        for subset in ("H", "Hm"):
            assert deciding[name][subset]["MDE"].startswith("N/A: single arm")
            assert deciding[name][subset]["achieved_power"].startswith("N/A: single arm")
    assert deciding["retrieve_p95"]["n"] == 4
    assert built["timings_ms"] == {"retrieve": {"n": 4, "p50": 10.0, "p95": 20.0}}
    assert built["latency_evidence"] is False and built["timing_scope"] == "fixture scope"


def test_a_case_with_an_unjudged_text_leaves_the_judged_metrics_and_stays_lexical(evidence):
    pairs = _pairs()
    lost = _document("zebra text without an address", addressed=False)
    pairs[1] = (_case("h2"), _row(SEEDS_H2, [lost]))
    _, inputs, judges, families = evidence(pairs)
    h = _build(inputs, judges, families)["subsets"]["H"]
    assert h["judged_excluded"] == [
        {
            "case_id": "h2",
            "reason": "unjudged document in deciding population",
            "unjudged": {lost["text_sha256"]: "address_unresolved"},
        }
    ]
    assert set(h["per_case"]["precision_at_5"]) == {"h1"}
    assert set(h["per_case"]["context_precision"]) == {"h1", "h2"}
    assert (h["metrics"]["sent_precision"]["n"], h["metrics"]["sent_precision"]["excluded"]) == (
        1,
        1,
    )
    assert h["metrics"]["context_precision"]["excluded"] == 0


def test_the_ruler_is_provisional_until_the_retest_passes(evidence):
    _, inputs, judges, families = evidence(retest=False)
    before = _build(inputs, judges, families)
    assert before["provisional_ruler"] is True
    assert before["provisional_reason"] == "the stability retest has not been run"
    assert before["retest"] == "N/A: the stability retest has not been run"
    assert before["provenance"]["raw_judge_replies"]["retest_pass"].startswith("N/A: ")
    client = TokenJudge()
    judge_tool.judge(judges, "opus", client=client, retest=True)
    judge_tool.retest(judges, "opus")
    passed = _build(inputs, judges, families)
    assert passed["provisional_ruler"] is False
    assert passed["provisional_reason"] == "the stability retest passed"
    assert passed["retest"]["verdict"] == "single_judge" and passed["retest"]["units"] == 6
    assert passed["retest"]["all"]["quadratic_kappa"] == 1.0
    assert set(passed["retest"]["by_subset"]) == {"H", "Hm"}
    for name in ("precision_at_5", "sent_precision", "ndcg_at_5"):
        assert passed["subsets"]["H"]["per_case"][name] == before["subsets"]["H"]["per_case"][name]


def test_a_judge_that_contradicts_itself_leaves_the_ruler_provisional(evidence):
    _, inputs, judges, families = evidence(retest=False)
    judge_tool.judge(judges, "opus", client=TokenJudge({"plain": 3}), retest=True)
    assert judge_tool.retest(judges, "opus")["verdict"] == "provisional_ruler"
    built = _build(inputs, judges, families)
    assert built["provisional_ruler"] is True
    assert built["provisional_reason"] == "the stability retest gave provisional_ruler"
    assert built["subsets"]["H"]["per_case"]["precision_at_5"] == {"h1": 0.2, "h2": 0.0}


def test_provenance_names_the_stores_the_judge_and_the_inputs(evidence):
    _, inputs, judges, families = evidence()
    provenance = _build(inputs, judges, families)["provenance"]
    replies = provenance["raw_judge_replies"]
    assert replies["first_pass"]["sha256"] == parity.file_sha(judges / "opus.jsonl")
    assert replies["retest_pass"]["sha256"] == parity.file_sha(judges / "opus-retest.jsonl")
    assert (replies["first_pass"]["attempts"], replies["first_pass"]["valid"]) == (3, 3)
    assert replies["first_pass"]["elapsed_s"] == 1.5
    assert provenance["judge_model"] == ["fixture-reported-model"]
    assert provenance["rubric_version"] == ["p2-0-3-v1"]
    (version,) = provenance["judge_revision"]["judge_version"]
    assert json.loads(version)["judge"] == "opus"
    assert provenance["judge_revision"]["cli_versions"] == ["9.9.9 (fixture)"]
    assert provenance["bootstrap_seed"] == {"metric_intervals": 20261001, "retest_kappa": 20260925}
    assert provenance["fact_matcher_version"].startswith("semantic-ruler/claim-window-v3; not ")
    assert provenance["family_map"]["sha256"] == parity.file_sha(families)
    assert provenance["judge_plan_sha256"] == parity.file_sha(judges / "plan.json")
    assert provenance["ruler_input_sha256"] == parity.file_sha(judges / "ruler-input.json")
    assert provenance["retest_report_sha256"] == parity.file_sha(judges / "opus-retest.json")
    assert provenance["collector_report_sha256"] == parity.file_sha(
        inputs / "collector-report.json"
    )
    assert provenance["code_sha"] == "c0de" and provenance["config"] == {"retrieval_top_k": 20}
    assert set(provenance["report_code"]) == {"commit", "tracked_tree_clean", "blobs"}
    assert set(provenance["report_code"]["blobs"]) == set(report.CODE_FILES)
    assert all((ROOT / name).is_file() for name in report.CODE_FILES)


def test_a_run_log_without_a_cli_version_and_a_missing_run_log_are_told_apart(evidence):
    _, inputs, judges, families = evidence(client=TokenJudge())
    revision = _build(inputs, judges, families)["provenance"]["judge_revision"]
    assert revision["cli_versions"] == "N/A: the run log names no CLI version"
    (judges / judge_tool.RUN_LOG).unlink()
    again = _build(inputs, judges, families)["provenance"]["judge_revision"]
    assert again["cli_versions"] == "N/A: no run log beside the stores"


def test_collection_block_reads_the_supervisor_state(evidence, tmp_path):
    _, inputs, judges, families = evidence()
    assert _build(inputs, judges, families)["collection"] == "N/A: supervisor state not supplied"
    state, samples = tmp_path / "state.json", tmp_path / "samples.jsonl"
    record = {
        "status": "complete",
        "code_sha": "c0de",
        "started": "2026-10-04T10:11:40+00:00",
        "host": {"cores": "4"},
        "stage_seconds": {"grade": 9.5},
        "attempts": {"grade": 2},
        "pauses": [{"stage": "grade", "mode": "boundary"}],
        "monitor_errors": 0,
        "host_peaks": {
            "transform": {
                "collector_plus_ollama_rss_kb": 700,
                "mem_used_mb": 6984,
                "swap_used_mb": 9.5,
            },
            "grade": {"collector_plus_ollama_rss_kb": 900, "mem_used_mb": 5067},
        },
    }
    state.write_text(json.dumps(record), encoding="utf-8")
    samples.write_text("{}\n", encoding="utf-8")
    built = _build(inputs, judges, families, state=state, host_samples=samples)
    collection = built["collection"]
    assert collection["state_sha256"] == parity.file_sha(state)
    assert collection["host_samples_sha256"] == parity.file_sha(samples)
    assert collection["pauses"] == record["pauses"] and collection["attempts"] == {"grade": 2}
    assert collection["peak_host_rss"]["collector_plus_ollama_rss_kb"] == 900
    assert collection["peak_host_rss"]["mem_used_mb"] == 6984
    assert collection["peak_host_rss"]["swap_used_mb"] == 9.5
    assert built["provenance"]["peak_host_rss"] == collection["peak_host_rss"]
    for change in ({"status": "running"}, {"code_sha": "0ther"}):
        state.write_text(json.dumps({**record, **change}), encoding="utf-8")
        with pytest.raises(ValueError, match="not that of this finished collection"):
            _build(inputs, judges, families, state=state)


def test_build_refuses_contexts_of_another_run(evidence):
    _, inputs, judges, families = evidence()
    path = inputs / "contexts.json.gz"
    contexts = json.loads(gzip.decompress(path.read_bytes()))
    for change, reason in (
        ({"run_sha256": "0" * 64}, "belongs to another run"),
        ({"contexts_version": 2}, "contexts_version"),
        ({"cases": contexts["cases"][:-1]}, "does not list the cases"),
        ({"texts": {**contexts["texts"], baseline.text_sha("x"): "y"}}, "does not match its hash"),
        ({"texts": {}}, "misses a text"),
    ):
        path.write_bytes(gzip.compress(json.dumps({**contexts, **change}).encode("utf-8")))
        with pytest.raises(ValueError, match=reason):
            _build(inputs, judges, families)


def test_build_refuses_a_plan_of_another_run_and_stale_judge_files(evidence, tmp_path):
    _, inputs, judges, families = evidence()
    other, foreign = tmp_path / "other", tmp_path / "foreign"
    _write_run(other, _pairs(), code_sha="0ther")
    judge_tool.write_plan(foreign, judge_tool.build_plan(other))
    judge_tool.judge(foreign, "opus", client=TokenJudge())
    judge_tool.consensus(foreign)
    with pytest.raises(ValueError, match="the judge plan belongs to another run"):
        _build(inputs, foreign, families)
    with pytest.raises(ValueError, match="unknown judge"):
        report.build(inputs, judges, judge="glm", families=families, families_sha256=None)
    retest_store = judges / "opus-retest.jsonl"
    kept = retest_store.read_bytes()
    retest_store.write_bytes(kept + kept.splitlines(keepends=True)[0])
    with pytest.raises(ValueError, match="retest report is not computed"):
        _build(inputs, judges, families)
    retest_store.write_bytes(kept)
    _build(inputs, judges, families)
    store = judges / "opus.jsonl"
    store.write_bytes(store.read_bytes() + store.read_bytes().splitlines(keepends=True)[0])
    with pytest.raises(ValueError, match="ruler-input.json is not computed"):
        _build(inputs, judges, families)


def test_build_refuses_a_ruler_input_that_is_not_the_one_judge(evidence):
    _, inputs, judges, families = evidence(retest=False)
    path = judges / "ruler-input.json"
    ruler_input = json.loads(path.read_text(encoding="utf-8"))
    for change in (
        {"grade_source": "consensus"},
        {"included_judges": []},
        {"status": "NOT_EVIDENCE"},
    ):
        path.write_text(json.dumps({**ruler_input, **change}), encoding="utf-8")
        with pytest.raises(ValueError, match="grades of the one registered judge"):
            _build(inputs, judges, families)


def test_family_map_must_be_the_registered_one_and_cover_every_case(evidence, tmp_path):
    _, inputs, judges, families = evidence()
    with pytest.raises(ValueError, match="not the registered one"):
        report.build(inputs, judges, families=families)
    missing = {"H": {"h1": ["a.md"], "h2": ["b.md"]}, "Hm": {"m1": ["c.md"]}}
    with pytest.raises(ValueError, match="lists no documents for h3"):
        _build(inputs, judges, _write_families(tmp_path / "missing.json", missing))
    unknown = {**CASE_DOCUMENTS, "Hm": {"m1": ["zz.md"]}}
    with pytest.raises(ValueError, match="outside the family map"):
        _build(inputs, judges, _write_families(tmp_path / "unknown.json", unknown))
    register = json.loads(families.read_text(encoding="utf-8"))
    register["families"][0]["members"].append({"source_id": "c.md"})
    families.write_text(json.dumps(register), encoding="utf-8")
    with pytest.raises(ValueError, match="document in two families"):
        _build(inputs, judges, families)


def test_build_refuses_a_subset_outside_the_registered_population(evidence):
    pairs = [*_pairs(), (_case("x1", "G1"), _row(SEEDS_H2, SEEDS_H2))]
    documents = {**CASE_DOCUMENTS, "G1": {"x1": ["a.md"]}}
    _, inputs, judges, families = evidence(pairs, case_documents=documents)
    with pytest.raises(ValueError, match="outside the registered population"):
        _build(inputs, judges, families)


def test_cli_exports_and_builds(evidence, tmp_path, monkeypatch, capsys):
    run, inputs, judges, families = evidence()
    assert report.main(["export", "--run", str(run), "--out", str(inputs)]) == 0
    assert json.loads(capsys.readouterr().out)["collected"] == 3
    fixture_map = report.load_family_map(families, None)
    monkeypatch.setattr(report, "load_family_map", lambda path, expected: fixture_map)
    out = tmp_path / "report.json"
    arguments = ["build", "--inputs", str(inputs), "--judge-dir", str(judges), "--out", str(out)]
    assert report.main(arguments) == 0
    printed = json.loads(capsys.readouterr().out)
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["schema_version"] == "production-baseline-report/v1"
    assert printed["provisional_ruler"] is False
    assert (
        printed["H"]["precision_at_5"]
        == written["subsets"]["H"]["metrics"]["precision_at_5"]["point"]
    )
    assert (
        printed["Hm"]["context_precision"]
        == written["subsets"]["Hm"]["metrics"]["context_precision"]["point"]
    )
    assert read_store(judges / judge_tool.RUN_LOG)


def test_a_packed_plan_gives_the_same_report_and_another_packed_plan_is_refused(evidence, capsys):
    _, inputs, judges, families = evidence()
    plain = _build(inputs, judges, families)
    plan = judges / "plan.json"
    assert report.main(["pack", "--judge-dir", str(judges)]) == 0
    printed = json.loads(capsys.readouterr().out)
    kept = (judges / "plan.json.gz").read_bytes()
    assert gzip.decompress(kept) == plan.read_bytes()
    assert printed == {
        "plan_sha256": parity.file_sha(plan),
        "plan_bytes": plan.stat().st_size,
        "packed_bytes": len(kept),
    }
    assert report.pack(judges) == printed and (judges / "plan.json.gz").read_bytes() == kept
    plan.rename(judges / "plan.moved")
    assert _build(inputs, judges, families) == plain
    (judges / "plan.moved").rename(plan)
    (judges / "plan.json.gz").write_bytes(gzip.compress(b"{}"))
    with pytest.raises(FileExistsError, match="plan.json.gz"):
        report.pack(judges)


def test_registered_family_map_leaves_four_clusters_in_h_and_one_in_hm():
    family_map = report.load_family_map(ROOT / report.FAMILY_MAP)
    counts = {}
    for subset, dataset in (
        ("H", "evaluation/curated_cases_aircargo.jsonl"),
        ("Hm", "evaluation/curated_cases_aircargo_gr_multihop.jsonl"),
    ):
        cases = [
            {**json.loads(line), "subset": subset}
            for line in (ROOT / dataset).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        components = family_clusters(report.case_families(cases, family_map))
        counts[subset] = sorted((len(component) for component in components), reverse=True)
    assert counts == {"H": [94, 2, 2, 2], "Hm": [15]}


def test_spec_registers_what_the_builder_applies():
    spec = " ".join(SPEC.read_text(encoding="utf-8").split())
    assert "## Baseline of plan slice 2.5" in SPEC.read_text(encoding="utf-8")
    assert report.FAMILY_MAP_SHA256 in spec
    assert "H has **4 clusters — of 94, 2, 2 and 2 cases — and Hm has 1**" in spec
    assert "`scripts/baseline_report.py`" in spec
    assert "`context_precision_seeds`" in spec
    assert "seed 20261001" in spec and "[0, 1]" in spec
    assert "`development_used.<subset>.case_documents`" in spec
