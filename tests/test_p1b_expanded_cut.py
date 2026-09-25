"""Synthetic contract tests for the preregistered P1b expanded cut."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path

import pytest

from scripts import p1_adaptive_k as p1
from scripts import p1b_expanded_cut as p1b
from scripts import rerank_score_capture
from scripts.corpus_manifest import build_manifest, write_manifest
from tests.test_gr_bucket_baseline import _write_fixture


def _fixture(tmp_path: Path) -> dict:
    paths = _write_fixture(tmp_path / "source")
    rows = json.loads(paths["pool"].read_text(encoding="utf-8"))
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for row in rows:
        case_id = row["case_id"]
        source = f"{case_id}.md"
        (corpus / source).write_text(f"synthetic {case_id}\n", encoding="utf-8")
        row["prerank_cands"] = row["cands"] + [f"unique filler {case_id} {i}" for i in range(4)]
        row["prerank_sources"] = [source] * 6
        row["cands"] = list(row["prerank_cands"])
        row["rerank_k"] = 5
    write_manifest(paths["corpus_manifest"], build_manifest(corpus, name="synthetic"))
    raw = json.dumps(rows, ensure_ascii=False).encode("utf-8")
    archive = tmp_path / "archive.json.gz"
    archive.write_bytes(gzip.compress(raw, mtime=0))
    digest = hashlib.sha256(raw).hexdigest()
    probabilities = [0.9, 0.8, 0.3, 0.2, 0.1, 0.05]
    scores = {
        "schema_version": rerank_score_capture.SCHEMA_VERSION,
        "complete": True,
        "parity": {
            "order_matches": len(rows),
            "top_k_matches": len(rows),
            "mismatched_case_ids": [],
        },
        "provenance": {
            "pool_sha256": digest,
            "code": {"commit": "f" * 40},
            "reranker": {"model": p1.RERANKER_MODEL},
            "config": {"batch_size": 8},
        },
        "per_case": [
            {
                "case_id": row["case_id"],
                "n_candidates": 6,
                "probabilities": probabilities,
                "logits": [math.log(p / (1 - p)) for p in probabilities],
                "fresh_order": list(range(6)),
            }
            for row in rows
        ],
    }
    scores_path = tmp_path / "scores.json"
    scores_path.write_text(json.dumps(scores), encoding="utf-8")
    rankings = p1.fresh_rankings(rows, scores["per_case"])
    score_kwargs = {
        "dataset_path": paths["dataset"],
        "sidecar_path": paths["sidecar"],
        "label_manifest_path": paths["label_manifest"],
    }

    def aggregate(kept: list[int]) -> dict:
        scored, _ = p1.score_selection(rows, rankings, kept, **score_kwargs)
        return p1.aggregate(scored)

    top = aggregate([5] * len(rows))
    rel_counts = p1.rule_counts(rankings, "rel", 0.2)
    rel = aggregate(rel_counts)
    per_case = [
        {
            "case_id": row["case_id"],
            "cell": "rel_0.7" if i == 0 else "rel_0.2",
            "kept": 2 if i == 0 else rel_counts[i],
        }
        for i, row in enumerate(rows)
    ]
    p1_report = {
        "labels": {"H": {"source": "synthetic"}, "Hm": {"source": "synthetic"}},
        "h": {
            "in_sample_best": {"cell": "rel_0.2"},
            "cells": [
                {"name": "top_k_5", "aggregate": top},
                {"name": "rel_0.2", "aggregate": rel},
            ],
            "cross_validation": {
                "per_case": per_case,
                "aggregate": aggregate([entry["kept"] for entry in per_case]),
            },
        },
        "hm": {
            "cells": [
                {"name": "top_k_5", "aggregate": top},
                {"name": "rel_0.2", "aggregate": rel},
            ]
        },
    }
    p1_path = tmp_path / "p1.json"
    p1_path.write_text(json.dumps(p1_report), encoding="utf-8")
    kwargs = {
        "corpus_dir": corpus,
        "corpus_manifest_path": paths["corpus_manifest"],
        "p1_report_path": p1_path,
        "h_archive": archive,
        "hm_archive": archive,
        "h_pool_sha256": digest,
        "hm_pool_sha256": digest,
        "h_scores": scores_path,
        "hm_scores": scores_path,
        "dataset_path": paths["dataset"],
        "hm_dataset_path": paths["dataset"],
        "sidecar_path": paths["sidecar"],
        "hm_sidecar_path": paths["sidecar"],
        "label_manifest_path": paths["label_manifest"],
        "hm_label_manifest_path": paths["label_manifest"],
        "grid_bootstrap_samples": 20,
        "headline_bootstrap_samples": 30,
        "code_commit": "0" * 40,
    }
    return {
        "kwargs": kwargs,
        "rows": rows,
        "scores": scores,
        "rankings": rankings,
        "p1_report": p1_report,
        "p1_path": p1_path,
        "paths": paths,
    }


def _chunks(fixture: dict) -> list:
    from vectordb._base_manager import Document

    corpus = fixture["kwargs"]["corpus_dir"]
    return [
        Document(
            page_content=text,
            metadata={"source": str(corpus / row["prerank_sources"][i])},
        )
        for row in fixture["rows"]
        for i, text in enumerate(row["prerank_cands"])
    ]


def _build(fixture: dict, *, chunks: list | None = None) -> dict:
    if chunks is None:
        chunks = _chunks(fixture)
    return p1b.build_report(**fixture["kwargs"], chunks=chunks)


def test_matching_synthetic_corpus_is_admitted(tmp_path):
    fixture = _fixture(tmp_path)
    result = p1b.check_corpus(
        fixture["kwargs"]["corpus_dir"], fixture["kwargs"]["corpus_manifest_path"]
    )
    assert result["name"] == "synthetic"
    assert result["file_count"] == len(fixture["rows"])


def test_changed_corpus_file_is_named_by_build_report(tmp_path):
    fixture = _fixture(tmp_path)
    (fixture["kwargs"]["corpus_dir"] / "syn-one.md").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="syn-one.md"):
        _build(fixture, chunks=[])


def test_extra_corpus_file_is_named_by_build_report(tmp_path):
    fixture = _fixture(tmp_path)
    (fixture["kwargs"]["corpus_dir"] / "extra.md").write_text("extra", encoding="utf-8")
    with pytest.raises(ValueError, match="extra.md"):
        _build(fixture, chunks=[])


def test_corpus_error_names_every_changed_missing_and_extra_file(tmp_path):
    fixture = _fixture(tmp_path)
    corpus = fixture["kwargs"]["corpus_dir"]
    (corpus / "syn-one.md").write_text("changed", encoding="utf-8")
    (corpus / "syn-two.md").unlink()
    (corpus / "extra.md").write_text("extra", encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        p1b.check_corpus(corpus, fixture["kwargs"]["corpus_manifest_path"])
    assert all(name in str(exc.value) for name in ("syn-one.md", "syn-two.md", "extra.md"))


def test_missing_rank_two_chunk_fails_closed(tmp_path):
    pytest.importorskip("langchain_core")
    fixture = _fixture(tmp_path)
    chunks = _chunks(fixture)
    chunks.pop(1)
    with pytest.raises(ValueError, match="syn-one.*rank 2"):
        _build(fixture, chunks=chunks)


def test_duplicate_rank_one_chunk_fails_closed(tmp_path):
    pytest.importorskip("langchain_core")
    from vectordb._base_manager import Document

    fixture = _fixture(tmp_path)
    chunks = _chunks(fixture)
    chunks.append(Document(page_content=chunks[0].page_content, metadata=dict(chunks[0].metadata)))
    with pytest.raises(ValueError, match="syn-one.*rank 1"):
        _build(fixture, chunks=chunks)


def test_wrong_source_chunk_fails_closed(tmp_path):
    pytest.importorskip("langchain_core")
    fixture = _fixture(tmp_path)
    chunks = _chunks(fixture)
    chunks[0].metadata["source"] = str(fixture["kwargs"]["corpus_dir"] / "other.md")
    with pytest.raises(ValueError, match="syn-one.*rank 1"):
        _build(fixture, chunks=chunks)


def _document_chunks(texts: list[str]) -> list:
    from vectordb._base_manager import Document

    return [Document(page_content=text, metadata={"source": "a.md"}) for text in texts]


def test_neighbour_between_kept_chunks_occurs_once():
    pytest.importorskip("langchain_core")
    chunks = _document_chunks([f"text-{i}" for i in range(5)])
    p1b.stamp_chunk_index(chunks)
    retriever = p1b.make_retriever(chunks)
    texts, expanded_count = p1b.expand_kept(retriever, chunks, [1, 3], 2)
    assert sum(text.count("text-2") for text in texts) == 1
    assert expanded_count == 2


def test_cut_frees_a_neighbour_for_expansion():
    pytest.importorskip("langchain_core")
    chunks = _document_chunks([f"text-{i}" for i in range(5)])
    p1b.stamp_chunk_index(chunks)
    retriever = p1b.make_retriever(chunks)
    control, _ = p1b.expand_kept(retriever, chunks, [1, 3], 2)
    cut, _ = p1b.expand_kept(retriever, chunks, [1, 3], 1)
    assert "text-3" not in control[0]
    assert "text-3" in cut[0]


def test_repeated_neighbour_text_uses_index_key():
    pytest.importorskip("langchain_core")
    chunks = _document_chunks(["zero", "repeat", "repeat", "three", "four"])
    p1b.stamp_chunk_index(chunks)
    retriever = p1b.make_retriever(chunks)
    texts, _ = p1b.expand_kept(retriever, chunks, [1], 1)
    assert texts[0].count("repeat") == 2


def test_duplicate_retriever_key_is_rejected_before_scoring(tmp_path):
    pytest.importorskip("langchain_core")
    fixture = _fixture(tmp_path)
    chunks = _chunks(fixture)
    chunks[0].metadata["chunk_id"] = "same"
    chunks[1].metadata["chunk_id"] = "same"
    with pytest.raises(ValueError, match="position 1.*position 0.*syn-one.md"):
        _build(fixture, chunks=chunks)


def test_expansion_constants_equal_fresh_settings_defaults(monkeypatch):
    monkeypatch.delenv("RAG_PARENT_EXPANSION_WINDOW", raising=False)
    monkeypatch.delenv("RAG_PARENT_EXPANSION_MAX_CHARS", raising=False)
    from config.settings import Settings

    settings = Settings()
    assert (p1b.EXPANSION_WINDOW, p1b.EXPANSION_MAX_CHARS) == (2, 3600)
    assert settings.parent_expansion_window == p1b.EXPANSION_WINDOW
    assert settings.parent_expansion_max_chars == p1b.EXPANSION_MAX_CHARS


def test_rebuild_chunks_on_a_tiny_corpus(tmp_path, monkeypatch):
    pytest.importorskip("langchain_core")
    import config.settings as settings_module

    documents = {
        "alpha.md": (
            "# Alpha\n\n## Intake\nThe parcel arrives. Staff record its weight.\n\n"
            "## Dispatch\nThe parcel is sealed. The courier collects it.\n"
        ),
        "beta.md": (
            "# Beta\n\n## Review\nThe manifest is checked. Staff confirm the route.\n\n"
            "## Delivery\nThe courier reaches the depot. The parcel is logged.\n"
        ),
    }
    for name, content in documents.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    monkeypatch.setenv("RAG_SEMANTIC_CHUNKING", "true")
    monkeypatch.setenv("RAG_STRUCTURAL_CHUNKING", "false")
    monkeypatch.setattr(settings_module, "_settings", None)

    chunks, record = p1b.rebuild_chunks(tmp_path)

    sources = [Path(chunk.metadata["source"]).name for chunk in chunks]
    assert chunks
    assert all(source in documents for source in sources)
    assert set(sources) == set(documents)
    assert record["semantic_chunking"] is False
    assert record["structural_chunking"] is True
    assert record["contextual_headers"] == settings_module.get_settings().contextual_headers
    assert record["chunk_count"] == len(chunks)


def test_rebuild_chunks_refuses_settings_that_ignore_the_flags(tmp_path, monkeypatch):
    pytest.importorskip("langchain_core")
    monkeypatch.setenv("RAG_SEMANTIC_CHUNKING", "true")
    monkeypatch.setenv("RAG_STRUCTURAL_CHUNKING", "false")
    from types import SimpleNamespace

    import config.settings as settings_module
    import ingestion.loader as loader_module

    monkeypatch.setattr(
        settings_module,
        "get_settings",
        lambda: SimpleNamespace(semantic_chunking=True, structural_chunking=True),
    )

    def unexpected_loader(*args, **kwargs):
        pytest.fail("DocumentLoader was constructed before the settings check")

    monkeypatch.setattr(loader_module, "DocumentLoader", unexpected_loader)
    with pytest.raises(ValueError, match="semantic_chunking"):
        p1b.rebuild_chunks(tmp_path)


def test_cross_validation_uses_each_recorded_cell(tmp_path):
    fixture = _fixture(tmp_path)
    entries = fixture["p1_report"]["h"]["cross_validation"]["per_case"]
    counts = p1b.cv_counts(fixture["rankings"], entries)
    assert counts == [2, 4, 4, 4]
    assert counts[0] == p1.kept_count(
        "rel",
        0.7,
        fixture["rankings"][0]["probabilities"][:5],
        fixture["rankings"][0]["logits"][:5],
    )


def test_missing_cross_validation_case_names_case(tmp_path):
    pytest.importorskip("langchain_core")
    fixture = _fixture(tmp_path)
    fixture["p1_report"]["h"]["cross_validation"]["per_case"].pop()
    fixture["p1_path"].write_text(json.dumps(fixture["p1_report"]), encoding="utf-8")
    with pytest.raises(ValueError, match="syn-four"):
        _build(fixture)


def test_foreign_cross_validation_case_names_case(tmp_path):
    fixture = _fixture(tmp_path)
    entries = fixture["p1_report"]["h"]["cross_validation"]["per_case"]
    entries.append({"case_id": "foreign", "cell": "rel_0.2", "kept": 4})
    with pytest.raises(ValueError, match="foreign"):
        p1b.cv_counts(fixture["rankings"], entries)


def test_cross_validation_recorded_kept_must_match(tmp_path):
    fixture = _fixture(tmp_path)
    entries = fixture["p1_report"]["h"]["cross_validation"]["per_case"]
    entries[0]["kept"] = 3
    with pytest.raises(ValueError, match="syn-one"):
        p1b.cv_counts(fixture["rankings"], entries)


def test_primary_cell_must_match_p1_report(tmp_path):
    fixture = _fixture(tmp_path)
    fixture["p1_report"]["h"]["in_sample_best"]["cell"] = "rel_0.7"
    fixture["p1_path"].write_text(json.dumps(fixture["p1_report"]), encoding="utf-8")
    with pytest.raises(ValueError, match="rel_0.7"):
        _build(fixture, chunks=[])


def test_primary_ruler_sees_keyword_past_diagnostic_cap(tmp_path):
    fixture = _fixture(tmp_path)
    rows = fixture["rows"]
    target = next(i for i, row in enumerate(rows) if row["case_id"] == "syn-four")
    texts = [[row["cands"][0]] for row in rows]
    texts[target] = ["x" * 6100 + "хранени"]
    primary, diagnostic = p1b.score_rulers(
        rows,
        texts,
        [1] * len(rows),
        dataset_path=fixture["paths"]["dataset"],
        sidecar_path=fixture["paths"]["sidecar"],
        label_manifest_path=fixture["paths"]["label_manifest"],
    )
    assert primary[target]["context_recall"] == 1.0
    assert primary[target]["kw_status"] == "FULL"
    assert diagnostic[target]["context_recall"] == 0.0
    assert diagnostic[target]["kw_status"] == "MISS"


def test_score_rulers_records_grown_documents_per_case(tmp_path):
    fixture = _fixture(tmp_path)
    rows = fixture["rows"]
    texts = [[row["cands"][0]] for row in rows]
    primary, diagnostic = p1b.score_rulers(
        rows,
        texts,
        [1] * len(rows),
        expanded_documents=[1, 0, 1, 0],
        dataset_path=fixture["paths"]["dataset"],
        sidecar_path=fixture["paths"]["sidecar"],
        label_manifest_path=fixture["paths"]["label_manifest"],
    )
    assert [row["expanded_documents"] for row in primary] == [1, 0, 1, 0]
    assert [row["expanded_documents"] for row in diagnostic] == [1, 0, 1, 0]


def _case(
    case_id: str,
    precision: float,
    recall: float = 1.0,
    status: str = "FULL",
    matched: tuple[str, ...] = ("a", "b"),
) -> dict:
    return {
        "case_id": case_id,
        "context_precision": precision,
        "context_recall": recall,
        "kw_status": status,
        "matched_keywords": list(matched),
        "kept": 5,
        "n_docs": 5,
    }


def _decision_rows() -> dict:
    h_control = [_case(f"h-{i}", 0.6) for i in range(100)]
    h_primary = [_case(f"h-{i}", 0.7) for i in range(100)]
    h_cv = [_case(f"h-{i}", 0.7) for i in range(100)]
    hm_control = [_case("hm-0", 0.6)]
    hm_primary = [_case("hm-0", 0.7)]
    return {
        "H": {
            p1b.CONTROL_ARM: h_control,
            p1b.PRIMARY_ARM: h_primary,
            p1b.CV_ARM: h_cv,
        },
        "Hm": {p1b.CONTROL_ARM: hm_control, p1b.PRIMARY_ARM: hm_primary},
    }


def test_invalid_reproduction_invalidates_verdict():
    verdict = p1b.decide(_decision_rows(), reproduces_p1=False)
    assert verdict["decision"] == "INVALID_CONTROL"


def test_equal_aggregate_recall_with_one_fact_loss_is_no_ship():
    rows = _decision_rows()
    rows["H"][p1b.CONTROL_ARM][0] = _case("h-0", 0.6)
    rows["H"][p1b.PRIMARY_ARM][0] = _case("h-0", 0.7, 0.5, "PART", ("a",))
    rows["H"][p1b.CONTROL_ARM][1] = _case("h-1", 0.6, 0.5, "PART", ("a",))
    rows["H"][p1b.PRIMARY_ARM][1] = _case("h-1", 0.7)
    assert (
        p1.aggregate(rows["H"][p1b.PRIMARY_ARM])["context_recall"]
        == p1.aggregate(rows["H"][p1b.CONTROL_ARM])["context_recall"]
    )
    verdict = p1b.decide(rows, reproduces_p1=True)
    assert verdict["decision"] == "NO_SHIP"
    assert not verdict["coverage_and_facts_met"]
    assert verdict["fact_loss_cases"]["H"][p1b.PRIMARY_ARM] == ["h-0"]


def test_decision_names_fact_losses_for_cv_and_hm():
    rows = _decision_rows()
    rows["H"][p1b.CV_ARM][2]["matched_keywords"] = ["a"]
    rows["Hm"][p1b.PRIMARY_ARM][0]["matched_keywords"] = ["a"]
    verdict = p1b.decide(rows, reproduces_p1=True)
    assert verdict["fact_loss_cases"] == {
        "H": {p1b.PRIMARY_ARM: [], p1b.CV_ARM: ["h-2"]},
        "Hm": {p1b.PRIMARY_ARM: ["hm-0"]},
    }


def test_held_out_precision_gate_is_required():
    rows = _decision_rows()
    for row in rows["H"][p1b.CV_ARM]:
        row["context_precision"] = 0.62
    verdict = p1b.decide(rows, reproduces_p1=True)
    assert all(
        verdict[name]
        for name in (
            "precision_gate_met",
            "review_floor_met",
            "coverage_and_facts_met",
            "hm_check_met",
        )
    )
    assert not verdict["held_out_check_met"]
    assert verdict["decision"] == "NO_SHIP"


def test_all_five_conditions_make_ship_candidate():
    verdict = p1b.decide(_decision_rows(), reproduces_p1=True)
    assert verdict["decision"] == "SHIP_CANDIDATE"
    assert all(
        verdict[name]
        for name in (
            "precision_gate_met",
            "review_floor_met",
            "coverage_and_facts_met",
            "held_out_check_met",
            "hm_check_met",
        )
    )
    assert "no default" in verdict["scope"]


def test_q1_comparison_accepts_tolerance_boundary_only():
    prod = {
        "context_precision": 0.5769,
        "context_recall": 0.981,
        "FULL": 97,
        "PART": 2,
        "MISS": 1,
    }
    k3 = dict(p1b.Q1_ROWS["k3"])
    arms = {
        p1b.CONTROL_ARM: {"aggregate": prod},
        p1b.DIAGNOSTIC_ARM: {"aggregate": k3},
    }
    assert p1b.compare_q1(arms)["checks"]["prod"]["equal"]
    prod["context_precision"] = 0.577
    assert not p1b.compare_q1(arms)["checks"]["prod"]["equal"]


def test_stamp_overwrites_old_indices_and_uses_production_keys():
    pytest.importorskip("langchain_core")
    from vectordb._base_manager import _rrf_document_key

    chunks = _document_chunks(["zero", "one", "two"])
    chunks[1].metadata["chunk_index"] = 99
    p1b.stamp_chunk_index(chunks)
    assert [chunk.metadata["chunk_index"] for chunk in chunks] == [0, 1, 2]
    assert _rrf_document_key(chunks[1]) == "metadata:a.md:1"
    assert _rrf_document_key(chunks[2]) == "metadata:a.md:2"
    assert _rrf_document_key(chunks[0]) == "metadata:a.md:0"


def test_changed_p1_aggregate_yields_invalid_control(tmp_path):
    pytest.importorskip("langchain_core")
    fixture = _fixture(tmp_path)
    fixture["p1_report"]["h"]["cells"][1]["aggregate"]["context_recall"] = 0.1234
    fixture["p1_path"].write_text(json.dumps(fixture["p1_report"]), encoding="utf-8")
    report = _build(fixture)
    assert report["verdict"]["decision"] == "INVALID_CONTROL"
    assert not report["reproduction"]["reproduces_p1"]
    assert not report["reproduction"]["checks"]["H"]["rel_0.2"]["equal"]


def test_synthetic_end_to_end_is_deterministic_and_finite(tmp_path, monkeypatch):
    pytest.importorskip("langchain_core")
    fixture = _fixture(tmp_path)
    chunks = _chunks(fixture)
    observed_samples = []
    original_comparison = p1b.paired_comparison

    def record_samples(arm, control, *, samples, seed):
        observed_samples.append(samples)
        return original_comparison(arm, control, samples=samples, seed=seed)

    monkeypatch.setattr(p1b, "paired_comparison", record_samples)
    report = _build(fixture, chunks=chunks)
    assert observed_samples == [30, 20, 20, 20, 20]
    assert list(report) == [
        "schema_version",
        "evidence_class",
        "labels",
        "provenance",
        "config",
        "reproduction",
        "h",
        "hm",
        "q1_comparison",
        "verdict",
    ]
    assert list(report["h"]["arms"]) == [
        p1b.CONTROL_ARM,
        p1b.PRIMARY_ARM,
        p1b.CV_ARM,
        p1b.DIAGNOSTIC_ARM,
    ]
    assert list(report["hm"]["arms"]) == [p1b.CONTROL_ARM, p1b.PRIMARY_ARM, p1b.DIAGNOSTIC_ARM]
    cv_arm = report["h"]["arms"][p1b.CV_ARM]
    assert cv_arm["kept_counts"] == [2, 4, 4, 4]
    assert [row["kept"] for row in cv_arm["per_case"]] == [2, 4, 4, 4]
    assert report["reproduction"]["reproduces_p1"]
    assert report["config"]["chunking"]["chunks"] == "injected"
    for pool in ("h", "hm"):
        for name, arm in report[pool]["arms"].items():
            if name == p1b.CONTROL_ARM:
                assert "comparison" not in arm and "fact_losses" not in arm
            else:
                assert "comparison" in arm and "fact_losses" in arm
            assert (
                sum(row["expanded_documents"] for row in arm["per_case"])
                == arm["expanded_document_total"]
            )
    assert report == _build(fixture, chunks=_chunks(fixture))
    json.dumps(report, allow_nan=False)


def test_render_table_marks_uncompared_controls():
    aggregate = {
        "context_precision": 0.6,
        "context_recall": 1.0,
        "FULL": 1,
        "PART": 0,
        "MISS": 0,
        "mean_kept": 5.0,
    }
    control = {"aggregate": aggregate, "mean_context_chars": 100.0}
    primary = {
        **control,
        "comparison": {"precision_delta": 0.1, "precision_delta_ci95": [0.05, 0.15]},
    }
    report = {
        "h": {"arms": {p1b.CONTROL_ARM: control, p1b.PRIMARY_ARM: primary}},
        "hm": {"arms": {p1b.CONTROL_ARM: control}},
        "reproduction": {"reproduces_p1": True},
        "verdict": {
            "precision_gate_met": True,
            "review_floor_met": True,
            "coverage_and_facts_met": True,
            "held_out_check_met": True,
            "hm_check_met": True,
            "decision": "SHIP_CANDIDATE",
        },
    }
    lines = p1b.render_table(report).splitlines()

    def columns(pool, arm):
        line = next(line for line in lines if line.startswith(f"| {pool} | {arm} |"))
        return [part.strip() for part in line.strip("|").split("|")]

    assert columns("H", p1b.CONTROL_ARM)[-2:] == ["—", "—"]
    assert columns("Hm", p1b.CONTROL_ARM)[-2:] == ["—", "—"]
    assert columns("H", p1b.PRIMARY_ARM)[-2:] == ["+0.1000", "[0.0500, 0.1500]"]


def test_render_write_and_cli_contract(tmp_path, monkeypatch, capsys):
    pytest.importorskip("langchain_core")
    fixture = _fixture(tmp_path)
    report = _build(fixture)
    table = p1b.render_table(report)
    lines = table.splitlines()
    assert any(line.startswith("| pool | arm | precision | recall |") for line in lines)
    assert sum(line.startswith("| H |") for line in lines) == 4
    assert sum(line.startswith("| Hm |") for line in lines) == 3
    assert sum(line.startswith("**Decision: ") for line in lines) == 1
    path = tmp_path / "report.json"
    assert p1b.write_report(path, report) == path
    assert json.loads(path.read_text(encoding="utf-8")) == report
    assert path.read_bytes().endswith(b"\n") and not path.read_bytes().endswith(b"\n\n")
    monkeypatch.setattr(p1b, "build_report", lambda **kwargs: report)
    cli_path = tmp_path / "cli" / "report.json"
    assert (
        p1b.main(["--corpus", str(fixture["kwargs"]["corpus_dir"]), "--report", str(cli_path)]) == 0
    )
    assert json.loads(cli_path.read_text(encoding="utf-8")) == report
    assert capsys.readouterr().out == table
    with pytest.raises(SystemExit) as exc:
        p1b.main([])
    assert exc.value.code == 2
