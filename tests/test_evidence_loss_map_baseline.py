"""Fixture contracts for the finished-baseline evidence loss map."""

from __future__ import annotations

import gzip
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

from evaluation.devset import RU_TO_EN_RULE
from scripts import evidence_loss_map as loss_map
from scripts import production_baseline as baseline
from scripts import production_parity as parity

MODE = "hybrid; graph off; model routing off; single-turn"
STAGES = ("index", "initial_pool", "caps_dedup", "rerank", "expansion", "packing", "grading")


def document(text: str = "ALPHA", source: str = "a.md") -> dict[str, Any]:
    return {"text": text, "metadata": {"source": source}}


def case_row(
    case_id: str, loss: str = "no_observed_loss", *, subset: str = "H", term: str = "ALPHA"
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    case: dict[str, Any] = {
        "case_id": case_id,
        "subset": subset,
        "query": "Какое правило?",
        "expected": {"answer_contains": [term]},
        "answer_sources": {term: "a.md"},
        "source_documents": ["a.md", "b.md"],
    }
    row: dict[str, Any] = {
        "status": "ok",
        "routing_mode": MODE,
        "query_effective": "Which policy?",
        "query_transform": "rewrite",
        "vector": [0],
        "pool": [0],
        "seed_documents": [document(term)],
        "expanded_documents": [document(term)],
        "documents": [document(term)],
        "model_calls": [],
    }
    if loss in ("index", "index_to_pool_unknown"):
        row["vector"] = []
        row["pool"] = []
    if loss == "caps_dedup":
        row["pool"] = []
    for field, stage in (
        ("seed_documents", "rerank"),
        ("expanded_documents", "expansion"),
        ("documents", "packing"),
    ):
        if loss != "no_observed_loss" and (
            loss == "index_to_pool_unknown" or STAGES.index(loss) <= STAGES.index(stage)
        ):
            row[field] = []
    grade = {**row, "documents": row["documents"] if loss == "no_observed_loss" else []}
    return case, row, grade


@pytest.fixture
def finished_run(tmp_path: Path) -> Any:
    def create(
        pairs: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] | None = None,
    ) -> Path:
        if pairs is None:
            pairs = [case_row("valid")]
        archive = tmp_path / "chunks.json.gz"
        archive.write_bytes(
            gzip.compress(
                json.dumps(
                    {
                        "chunks": [
                            {"page_content": "ALPHA", "metadata": {"source": "a.md"}},
                            {"page_content": "split", "metadata": {"source": "a.md"}},
                            {"page_content": " phrase ALPHA", "metadata": {"source": "b.md"}},
                        ]
                    }
                ).encode(),
                mtime=0,
            )
        )
        sources = tmp_path / "sources"
        sources.mkdir()
        for name, text in (("a.md", "ALPHA split phrase"), ("b.md", "ALPHA")):
            (sources / name).write_text(text, encoding="utf-8")
        manifest = {
            "cases": [case for case, _, _ in pairs],
            "corpus": str(archive),
            "index_receipt": {"corpus_sha256": parity.file_sha(archive)},
            "source_directory": str(sources),
            "source_manifest": {
                "files": [
                    {"name": name, "sha256": parity.file_sha(sources / name)}
                    for name in ("a.md", "b.md")
                ]
            },
        }
        run = tmp_path / "run"
        identity = parity.digest(manifest)
        parity.write_new(run / "manifest.json", manifest)
        parity.write_new(run / "registration.json", {"manifest_sha256": identity})
        parity.save_stage(run / "report.json", {"status": "FINISHED"}, identity)
        for case, retrieve, grade in pairs:
            early = (
                retrieve
                if retrieve["status"] == "excluded"
                else {"status": "ok", "routing_mode": MODE}
            )
            for stage, row in (
                ("prepare", {"status": "ok", "case": case}),
                ("transform", early),
                ("embed", early),
                ("retrieve", retrieve),
                ("grade", grade),
            ):
                parity.save_stage(run / stage / (case["case_id"] + ".json"), row, identity)
        return run

    return create


def test_valid_reference_recovery_is_not_rejected_or_listed_as_loss(finished_run: Any) -> None:
    case, retrieve, grade = case_row("recovered")
    retrieve["seed_documents"] = []
    result = loss_map.build_baseline_map(finished_run([(case, retrieve, grade)]))
    row = result["per_case"][0]
    assert row["first_loss"] == "no_observed_loss"
    assert row["terms"][0]["last_loss"] == "no_observed_loss"
    assert row["terms"][0]["presence"] == {
        "index": True,
        "initial_pool": True,
        "caps_dedup": True,
        "rerank": False,
        "expansion": True,
        "packing": True,
        "grading": True,
    }
    assert result["index_stage_losses"] == []
    assert result["g3"]["H"]["rerank_to_expansion"]["losses"] == []
    assert result["g3"]["H"]["rerank_to_grading"]["losses"] == []
    assert row["query_effective"] == "Which policy?"
    assert row["query_transform"] == "rewrite"


@pytest.mark.parametrize(
    "loss",
    [
        "index",
        "index_to_pool_unknown",
        "caps_dedup",
        "rerank",
        "expansion",
        "packing",
        "grading",
    ],
)
def test_first_loss_at_each_observed_stage(finished_run: Any, loss: str) -> None:
    term = "MISSING" if loss == "index" else "ALPHA"
    result = loss_map.build_baseline_map(finished_run([case_row("lost", loss, term=term)]))
    row = result["per_case"][0]
    assert row["first_loss"] == row["terms"][0]["first_loss"] == loss
    first = "initial_pool" if loss == "index_to_pool_unknown" else loss
    assert row["terms"][0]["presence"] == {
        stage: STAGES.index(stage) < STAGES.index(first) for stage in STAGES
    }
    assert row["terms"][0]["last_loss"] == loss
    assert result["summary"]["all"]["first_loss_cases"][loss] == {"count": 1, "share": 1.0}


def test_unknown_cases_do_not_enter_stage_denominators(finished_run: Any) -> None:
    empty, er, eg = case_row("empty")
    empty["expected"]["answer_contains"] = []
    excluded, xr, xg = case_row("excluded")
    xg.update(
        status="excluded",
        exclusion={
            "stage": "grade",
            "reason": "grader failed",
            "error_type": "ModelFailure",
        },
    )
    result = loss_map.build_baseline_map(
        finished_run(
            [
                (empty, er, eg),
                (excluded, xr, xg),
                case_row("valid"),
            ]
        )
    )
    rows = result["per_case"]
    assert rows[0]["first_loss"] == rows[1]["first_loss"] == "unknown"
    assert rows[0]["reason"] == "no_gold"
    assert rows[1]["reason"] == "excluded"
    assert rows[1]["exclusion"] == xg["exclusion"]
    summary = result["summary"]["H"]
    assert summary["cases"] == {
        "total": 3,
        "counted": 1,
        "unknown_by_reason": {
            "no_gold": 1,
            "excluded": 1,
        },
    }
    for row in summary["stages"].values():
        assert row["case_denominator"] == row["term_denominator"] == 1
        assert row["terms_held"] == row["cases_all_held"] == 1
    assert result["summary"]["Hm"]["case_denominator"] == 0
    assert result["summary"]["Hm"]["first_loss_cases"]["index"]["share"] is None


def test_last_loss_after_recovery_and_case_earliest_term(finished_run: Any) -> None:
    case, retrieve, grade = case_row("repeated", "rerank")
    case["expected"]["answer_contains"] = ["ALPHA", "MISSING"]
    retrieve["expanded_documents"] = [document()]
    result = loss_map.build_baseline_map(finished_run([(case, retrieve, grade)]))
    row = result["per_case"][0]
    assert row["first_loss"] == "index"
    assert row["terms"][0]["first_loss"] == "rerank"
    assert row["terms"][0]["last_loss"] == "packing"
    summary = result["summary"]["all"]
    assert summary["case_denominator"] == 1
    assert summary["term_denominator"] == 2
    assert summary["stages"]["rerank"]["terms_lost"] == 1
    assert summary["stages"]["expansion"]["terms_gained"] == 1
    assert summary["first_loss_terms"]["index"] == {"count": 1, "share": 0.5}
    assert summary["first_loss_terms"]["rerank"] == {"count": 1, "share": 0.5}


def test_multihop_gold_is_bound_to_source_document(finished_run: Any) -> None:
    wrong, retrieve, grade = case_row("wrong", subset="Hm")
    grade["documents"] = [document(source="b.md")]
    result = loss_map.build_baseline_map(
        finished_run(
            [
                (wrong, retrieve, grade),
                case_row("right", subset="Hm"),
            ]
        )
    )
    left, right = result["per_case"]
    assert left["first_loss"] == "grading"
    assert right["first_loss"] == "no_observed_loss"
    assert left["terms"][0]["document"] == "a.md"
    assert left["source_documents_present"] == {
        stage: ["b.md"]
        if stage == "grading"
        else ["a.md", "b.md"]
        if stage == "index"
        else ["a.md"]
        for stage in STAGES
    }
    assert right["source_documents_present"]["grading"] == ["a.md"]


def test_registered_stratum_and_archive_proxy_are_independent(finished_run: Any) -> None:
    inside = case_row("inside", "rerank")
    outside = case_row("outside")
    outside[0]["query"] = "Which rule?"
    disagreement = case_row("disagreement")
    disagreement[0]["query"] = "Какое правило ALPHA?"
    multi = case_row("multi", "packing", subset="Hm")
    result = loss_map.build_baseline_map(finished_run([inside, outside, disagreement, multi]))
    assert [(r["ru_to_en"], r["archive_proxy"]) for r in result["per_case"]] == [
        (True, True),
        (False, False),
        (False, True),
        (True, True),
    ]
    g2 = result["g2"]
    assert g2["registered"]["rule"] == RU_TO_EN_RULE
    registered = g2["registered"]["subsets"]
    proxy = g2["archive_proxy"]["subsets"]
    assert registered["H"]["inside"]["case_denominator"] == 1
    assert registered["H"]["inside"]["first_loss_cases"]["rerank"]["count"] == 1
    assert registered["H"]["outside"]["case_denominator"] == 2
    assert registered["H"]["outside"]["first_loss_cases"]["no_observed_loss"]["count"] == 2
    assert registered["Hm"]["inside"]["case_denominator"] == 1
    assert registered["Hm"]["inside"]["first_loss_cases"]["packing"]["count"] == 1
    assert registered["Hm"]["outside"]["case_denominator"] == 0
    assert registered["all"]["inside"]["case_denominator"] == 2
    assert proxy["H"]["inside"]["case_denominator"] == 2
    assert proxy["H"]["inside"]["first_loss_cases"]["rerank"]["count"] == 1
    assert proxy["H"]["inside"]["first_loss_cases"]["no_observed_loss"]["count"] == 1
    assert proxy["H"]["outside"]["case_denominator"] == 1
    assert proxy["H"]["outside"]["first_loss_cases"]["no_observed_loss"]["count"] == 1
    assert g2["archive_proxy"]["label"] == "archive proxy for preliminary-map comparison"


def test_expansion_reports_losses_sent_losses_and_gains_apart(finished_run: Any) -> None:
    recovery = case_row("gain")
    recovery[1]["seed_documents"] = []
    result = loss_map.build_baseline_map(
        finished_run(
            [
                case_row("expand", "expansion"),
                case_row("pack", "packing"),
                recovery,
            ]
        )
    )
    g3 = result["g3"]["H"]
    assert g3["rerank_to_expansion"]["lost_terms"] == 1
    assert g3["rerank_to_expansion"]["losses"] == [{"case_id": "expand", "terms": ["ALPHA"]}]
    assert g3["rerank_to_grading"]["lost_terms"] == 2
    assert g3["rerank_to_grading"]["losses"] == [
        {"case_id": "expand", "terms": ["ALPHA"]},
        {"case_id": "pack", "terms": ["ALPHA"]},
    ]
    assert g3["expansion_gains"]["gained_terms"] == 1
    assert g3["expansion_gains"]["gains"] == [{"case_id": "gain", "terms": ["ALPHA"]}]
    assert result["g3"]["Hm"]["rerank_to_grading"]["lost_terms"] == 0


@pytest.mark.parametrize("missing_sources", [False, True])
def test_index_losses_are_classified_from_checked_sources(
    finished_run: Any,
    tmp_path: Path,
    missing_sources: bool,
) -> None:
    run = finished_run(
        [
            case_row("split", "index", term="split phrase"),
            case_row("absent", "index", term="MISSING"),
            case_row("other-source", "index", subset="Hm", term="phrase"),
        ]
    )
    # "phrase" exists in b.md's chunk, but not in a.md's chunks; its source does hold it.
    result = loss_map.build_baseline_map(
        run,
        sources=tmp_path / "missing" if missing_sources else None,
    )
    losses = result["index_stage_losses"]
    assert [row["kind"] for row in losses] == (
        ["unknown"] * 3
        if missing_sources
        else [
            "split_by_chunking",
            "absent_from_sources",
            "split_by_chunking",
        ]
    )
    assert losses[2]["document"] == "a.md"
    assert "document" not in losses[0]
    if missing_sources:
        assert all("FileNotFoundError" in row["reason"] for row in losses)
    assert "code fix before" in result["index_loss_policy"]


def test_first_loss_distributions_partition_counted_cases_and_terms(finished_run: Any) -> None:
    result = loss_map.build_baseline_map(
        finished_run(
            [
                case_row("lost", "rerank"),
                case_row("valid"),
                case_row("multi", subset="Hm"),
            ]
        )
    )
    for subset, cases in (("H", 2), ("Hm", 1), ("all", 3)):
        summary = result["summary"][subset]
        assert summary["case_denominator"] == summary["term_denominator"] == cases
        for key in ("first_loss_cases", "first_loss_terms"):
            assert sum(r["count"] for r in summary[key].values()) == cases
            assert sum(r["share"] for r in summary[key].values()) == 1.0


@pytest.mark.parametrize(
    "fault,exception,match",
    [
        ("unfinished", FileNotFoundError, "report"),
        ("abort", baseline.IntegrityError, "Open abort at grade"),
        ("tampered", baseline.IntegrityError, "Stage record integrity mismatch"),
        ("chunks", baseline.IntegrityError, "Chunk archive differs"),
        ("mode", baseline.IntegrityError, "routing_mode"),
        ("graph_on", baseline.IntegrityError, "graph off"),
        ("empty", baseline.IntegrityError, "routing_mode"),
        ("missing", FileNotFoundError, "retrieve"),
        ("damaged_transform", baseline.IntegrityError, "Stage record integrity mismatch"),
        ("damaged_embed", baseline.IntegrityError, "Stage record integrity mismatch"),
        ("missing_prepare", FileNotFoundError, "prepare"),
        ("transform_mode", baseline.IntegrityError, "Expected one routing_mode"),
        ("embed_mode", baseline.IntegrityError, "Expected one routing_mode"),
        ("transform_no_mode", baseline.IntegrityError, "Expected one routing_mode"),
        ("embed_no_mode", baseline.IntegrityError, "Expected one routing_mode"),
    ],
)
def test_invalid_run_refuses_without_partial_output(
    finished_run: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
    exception: type[Exception],
    match: str,
) -> None:
    run = finished_run([] if fault == "empty" else None)
    if fault == "unfinished":
        (run / "report.json").unlink()
    elif fault == "abort":
        parity.write_new(run / "grade.abort.json", {"reason": "open stop"})
    elif fault == "tampered":
        path = run / "grade/valid.json"
        payload = parity.read(path)
        payload["result"]["documents"] = []
        path.write_text(json.dumps(payload), encoding="utf-8")
    elif fault == "chunks":
        (tmp_path / "chunks.json.gz").write_bytes(
            gzip.compress(json.dumps({"chunks": []}).encode(), mtime=0)
        )
    elif fault == "mode":
        path = run / "grade/valid.json"
        payload = parity.read(path)["result"]
        payload["routing_mode"] = "different"
        path.unlink()
        parity.save_stage(path, payload, parity.digest(parity.read(run / "manifest.json")))
    elif fault == "graph_on":
        identity = parity.digest(parity.read(run / "manifest.json"))
        for stage in ("transform", "embed", "retrieve", "grade"):
            path = run / stage / "valid.json"
            payload = parity.load_stage(path, identity)
            payload["routing_mode"] = "hybrid; graph on; single-turn"
            path.unlink()
            parity.save_stage(path, payload, identity)
    elif fault == "missing":
        (run / "retrieve/valid.json").unlink()
    elif fault in ("damaged_transform", "damaged_embed"):
        stage = fault.removeprefix("damaged_")
        path = run / stage / "valid.json"
        payload = parity.read(path)
        payload["result"]["status"] = "damaged"
        path.write_text(json.dumps(payload), encoding="utf-8")
    elif fault == "missing_prepare":
        (run / "prepare/valid.json").unlink()
    elif fault in ("transform_mode", "embed_mode", "transform_no_mode", "embed_no_mode"):
        stage = fault.split("_")[0]
        path = run / stage / "valid.json"
        identity = parity.digest(parity.read(run / "manifest.json"))
        payload = parity.load_stage(path, identity)
        if fault.endswith("no_mode"):
            del payload["routing_mode"]
        else:
            payload["routing_mode"] = "hybrid; graph on; single-turn"
        path.unlink()
        parity.save_stage(path, payload, identity)
    out = tmp_path / "out.json"
    monkeypatch.setattr(sys, "argv", ["loss_map", "--baseline-run", str(run), "--out", str(out)])
    with pytest.raises(exception, match=match):
        loss_map.main()
    assert not out.exists()


def test_cli_deterministic_bytes_overrides_and_file_digests(
    finished_run: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run = finished_run([case_row("lost", "index", term="MISSING")])
    out = tmp_path / "out.json"
    argv = [
        "loss_map",
        "--baseline-run",
        str(run),
        "--out",
        str(out),
        "--chunks",
        str(tmp_path / "chunks.json.gz"),
        "--sources",
        str(tmp_path / "sources"),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    assert loss_map.main() == 0
    first = out.read_bytes()
    assert loss_map.main() == 0
    assert out.read_bytes() == first
    assert b"\r" not in first and first.endswith(b"\n")
    assert "Index losses: 1" in capsys.readouterr().out.splitlines()
    result = json.loads(first)
    assert result["manifest_sha256"] == parity.digest(parity.read(run / "manifest.json"))
    expected = {
        "manifest.json",
        "registration.json",
        "report.json",
        "prepare/lost.json",
        "transform/lost.json",
        "embed/lost.json",
        "retrieve/lost.json",
        "grade/lost.json",
        "chunks.json.gz",
        "a.md",
        "b.md",
    }
    assert {entry["path"] for entry in result["files"]} == expected
    for entry in result["files"]:
        root = {
            "run": run,
            "chunk_archive": tmp_path,
            "sources": tmp_path / "sources",
        }[entry["root"]]
        assert entry["sha256"] == parity.file_sha(root / entry["path"])
    assert tmp_path.name not in first.decode("utf-8")
    assert result["observability"]["answer"]["status"] == "unknown"
    assert result["observability"]["graph_caps"]["status"] == "not_observable"
    assert result["observability"]["coherence"]["status"] == "not_observable"


@pytest.mark.parametrize("options", [[], ["--capsule", "x"], ["--ledger", "x"]])
def test_cli_baseline_usage_errors_before_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    options: list[str],
) -> None:
    argv = ["loss_map", "--baseline-run", str(tmp_path / "missing")]
    if options:
        argv += ["--out", str(tmp_path / "out.json"), *options]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        loss_map.main()
    assert exc.value.code == 2


def test_sources_are_not_read_without_index_losses(
    finished_run: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_read(*args: Any) -> dict[str, str]:
        raise AssertionError("sources must not be read without index losses")

    monkeypatch.setattr(loss_map, "read_sources", unexpected_read)
    result = loss_map.build_baseline_map(finished_run(), sources=tmp_path / "missing")
    assert result["per_case"][0]["first_loss"] == "no_observed_loss"
    assert result["index_stage_losses"] == []
    assert {entry["path"] for entry in result["files"]} == {
        "manifest.json",
        "registration.json",
        "report.json",
        "prepare/valid.json",
        "transform/valid.json",
        "embed/valid.json",
        "retrieve/valid.json",
        "grade/valid.json",
        "chunks.json.gz",
    }


@pytest.mark.parametrize("stage", ["transform", "embed", "retrieve", "grade"])
def test_valid_referenced_cache_is_accepted_and_pinned(finished_run: Any, stage: str) -> None:
    run = finished_run()
    identity = parity.digest(parity.read(run / "manifest.json"))
    request = {"query": "Which policy?"}
    value = [0.5]
    key = parity.digest({"run": identity, "request": request})
    cache_file = f"cache/embedding-{key}.json"
    parity.write_new(
        run / cache_file,
        {
            "key": key,
            "request": request,
            "value": value,
            "value_sha256": parity.digest(value),
        },
    )
    path = run / stage / "valid.json"
    row = parity.load_stage(path, identity)
    row["model_calls"] = [
        {
            "cache_file": cache_file,
            "kind": "embedding",
            "request_sha256": parity.digest(request),
        }
    ]
    path.unlink()
    parity.save_stage(path, row, identity)
    result = loss_map.build_baseline_map(run)
    assert result["per_case"][0]["first_loss"] == "no_observed_loss"
    assert {entry["path"] for entry in result["files"]} == {
        "manifest.json",
        "registration.json",
        "report.json",
        "prepare/valid.json",
        "transform/valid.json",
        "embed/valid.json",
        "retrieve/valid.json",
        "grade/valid.json",
        "chunks.json.gz",
        cache_file,
    }
    entry = next(entry for entry in result["files"] if entry["path"] == cache_file)
    assert entry["sha256"] == parity.file_sha(run / cache_file)


def test_exclusion_forwarded_before_retrieval_is_unknown(finished_run: Any) -> None:
    case, _, _ = case_row("early", subset="Hm")
    excluded = {
        "status": "excluded",
        "routing_mode": MODE,
        "query_effective": "N/A: transform failed",
        "query_transform": None,
        "exclusion": {"stage": "transform", "reason": "rewrite failed", "error_type": "Error"},
    }
    result = loss_map.build_baseline_map(finished_run([(case, excluded, excluded)]))
    assert result["per_case"][0]["first_loss"] == "unknown"
    assert result["per_case"][0]["exclusion"] == {
        "stage": "transform",
        "reason": "rewrite failed",
        "error_type": "Error",
    }
    assert result["summary"]["all"]["case_denominator"] == 0
    assert result["summary"]["all"]["term_denominator"] == 0


def test_h_gold_list_keeps_term_occurrences(finished_run: Any) -> None:
    case, retrieve, grade = case_row("occurrences")
    case["expected"]["answer_contains"] = ["ALPHA", "ALPHA"]
    retrieve["seed_documents"] = []
    result = loss_map.build_baseline_map(finished_run([(case, retrieve, grade)]))
    assert [term["term"] for term in result["per_case"][0]["terms"]] == ["ALPHA", "ALPHA"]
    assert result["summary"]["H"]["term_denominator"] == 2
    assert result["summary"]["H"]["first_loss_terms"]["no_observed_loss"] == {
        "count": 2,
        "share": 1.0,
    }
    assert result["g3"]["H"]["expansion_gains"]["gained_terms"] == 2
    assert result["g3"]["H"]["expansion_gains"]["gains"] == [
        {"case_id": "occurrences", "terms": ["ALPHA", "ALPHA"]},
    ]


def test_index_loss_does_not_join_separate_source_files(finished_run: Any) -> None:
    result = loss_map.build_baseline_map(
        finished_run(
            [
                case_row("boundary", "index", term="phrase \n ALPHA"),
            ]
        )
    )
    assert result["index_stage_losses"][0]["kind"] == "absent_from_sources"


@pytest.mark.parametrize("option", ["--chunks", "--sources"])
def test_cli_overrides_require_baseline_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, option: str
) -> None:
    out = tmp_path / "out.json"
    monkeypatch.setattr(sys, "argv", ["loss_map", option, "missing", "--out", str(out)])
    with pytest.raises(SystemExit) as exc:
        loss_map.main()
    assert exc.value.code == 2
    assert not out.exists()


def test_file_references_are_location_independent(finished_run: Any, tmp_path: Path) -> None:
    run = finished_run([case_row("split", "index", term="split phrase")])
    copy = tmp_path / "elsewhere"
    copy.mkdir()
    shutil.copyfile(tmp_path / "chunks.json.gz", copy / "chunks.json.gz")
    shutil.copytree(tmp_path / "sources", copy / "sources")
    original = loss_map.build_baseline_map(run)
    relocated = loss_map.build_baseline_map(
        run, chunks=copy / "chunks.json.gz", sources=copy / "sources"
    )
    first = json.dumps(original, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    second = json.dumps(relocated, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    assert first.encode("utf-8") == second.encode("utf-8")
    assert tmp_path.name not in first
    assert "\r" not in first
    assert original["chunk_archive"] == {
        "name": "chunks.json.gz",
        "sha256": parity.file_sha(copy / "chunks.json.gz"),
    }
    files = original["files"]
    assert [(entry["root"], entry["path"]) for entry in files] == [
        ("chunk_archive", "chunks.json.gz"),
        ("run", "embed/split.json"),
        ("run", "grade/split.json"),
        ("run", "manifest.json"),
        ("run", "prepare/split.json"),
        ("run", "registration.json"),
        ("run", "report.json"),
        ("run", "retrieve/split.json"),
        ("run", "transform/split.json"),
        ("sources", "a.md"),
        ("sources", "b.md"),
    ]
    for entry in files:
        assert ".." not in Path(entry["path"]).parts
        assert not Path(entry["path"]).is_absolute()
    assert original["index_stage_losses"][0]["kind"] == "split_by_chunking"


def test_initial_pool_includes_pool_without_vector_candidates(finished_run: Any) -> None:
    case, retrieve, grade = case_row("pool-only", "rerank")
    retrieve["vector"] = []
    result = loss_map.build_baseline_map(finished_run([(case, retrieve, grade)]))
    term = result["per_case"][0]["terms"][0]
    assert term["presence"]["initial_pool"] is True
    assert term["presence"]["caps_dedup"] is True
    assert term["first_loss"] == term["last_loss"] == "rerank"


def test_candidate_positions_and_multihop_gold_contract(finished_run: Any) -> None:
    single = case_row("single", "rerank")
    multi = case_row("multi", "rerank", subset="Hm")
    multi[0]["expected"]["answer_contains"] = ["ALPHA", "EXTRA"]
    for _, retrieve, _ in (single, multi):
        retrieve["vector"] = []
        retrieve["pool"] = [2]
    result = loss_map.build_baseline_map(finished_run([single, multi]))
    h, hm = result["per_case"]
    assert h["terms"][0]["presence"]["caps_dedup"] is True
    assert h["first_loss"] == "rerank"
    assert hm["terms"][0]["presence"]["caps_dedup"] is False
    assert hm["first_loss"] == "index_to_pool_unknown"
    assert hm["terms"][0]["last_loss"] == "index_to_pool_unknown"
    assert [(term["term"], term["document"]) for term in hm["terms"]] == [("ALPHA", "a.md")]
    assert hm["source_documents_present"] == {
        "index": ["a.md", "b.md"],
        "initial_pool": ["b.md"],
        "caps_dedup": ["b.md"],
        "rerank": [],
        "expansion": [],
        "packing": [],
        "grading": [],
    }


def test_last_loss_follows_the_last_holding_stage_when_the_index_lacks_the_term(
    finished_run: Any,
) -> None:
    # No chunk holds "split phrase"; the expanded parent text does, the packed context does not.
    case, retrieve, grade = case_row("parent", "index", term="split phrase")
    retrieve["expanded_documents"] = [document("ALPHA split phrase")]
    result = loss_map.build_baseline_map(finished_run([(case, retrieve, grade)]))
    term = result["per_case"][0]["terms"][0]
    assert term["presence"] == {
        "index": False,
        "initial_pool": False,
        "caps_dedup": False,
        "rerank": False,
        "expansion": True,
        "packing": False,
        "grading": False,
    }
    assert term["first_loss"] == "index"
    assert term["last_loss"] == "packing"
