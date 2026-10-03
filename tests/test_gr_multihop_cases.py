"""GR-0.2: supplemental questions genuinely join multiple corpus documents."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import pytest

from evaluation.aircargo_labels import EvidenceClass, dataset_digest
from evaluation.question_class_labels import load_classified_cases

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION = PROJECT_ROOT / "evaluation"
BASE_DATASET = EVALUATION / "curated_cases_aircargo.jsonl"
DATASET = EVALUATION / "curated_cases_aircargo_gr_multihop.jsonl"
DATASET_MANIFEST = EVALUATION / "curated_cases_aircargo_gr_multihop.manifest.json"
SIDECAR = EVALUATION / "curated_cases_aircargo_gr_multihop_question_class.jsonl"
CLASS_MANIFEST = (
    EVALUATION / "curated_cases_aircargo_gr_multihop_question_class.manifest.json"
)
CORPUS_MANIFEST = EVALUATION / "aircargo_corpus.manifest.json"
PUBLISHED_PHASE_C_DATASET_SHA256 = (
    "3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720"
)


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for raw in path.read_text(encoding="utf-8").splitlines()
        if (line := raw.strip()) and not line.startswith("#")
    ]


def _corpus_dir() -> Path:
    configured = os.environ.get("AIRCARGO_CORPUS_DIR")
    if configured:
        return Path(configured)
    return PROJECT_ROOT / "data" / "uploads" / "aircargo"


def test_phase_c_dataset_remains_byte_identical() -> None:
    assert hashlib.sha256(BASE_DATASET.read_bytes()).hexdigest() == (
        PUBLISHED_PHASE_C_DATASET_SHA256
    )


def test_supplement_has_fifteen_multi_document_questions() -> None:
    """Prove the supplement has fifteen multi-document cases backed by manifest-listed sources."""
    rows = _jsonl(DATASET)
    base_ids = {str(row["case_id"]) for row in _jsonl(BASE_DATASET)}
    corpus_manifest = json.loads(CORPUS_MANIFEST.read_text(encoding="utf-8"))
    corpus_files = {str(row["name"]): row for row in corpus_manifest["files"]}

    assert len(rows) == 15
    assert len({str(row["case_id"]) for row in rows}) == 15
    assert not ({str(row["case_id"]) for row in rows} & base_ids)

    used_sources: set[str] = set()
    for row in rows:
        assert row["tenant_id"] == "aircargo"
        assert row["case_source"] == "agent_authored_over_real_documents"
        assert row["tags"] == ["gr_eval", "aircargo"]
        query = row["query"]
        assert isinstance(query, str) and query.strip() == query and query.endswith("?")

        expected = row["expected"]
        assert isinstance(expected, dict)
        keywords = expected["answer_contains"]
        assert isinstance(keywords, list) and len(keywords) >= 2
        assert len(set(keywords)) == len(keywords)
        assert expected["min_quality"] == 0.5

        source_documents = row["source_documents"]
        answer_sources = row["answer_sources"]
        assert isinstance(source_documents, list) and len(source_documents) >= 2
        assert len(set(source_documents)) == len(source_documents)
        assert isinstance(answer_sources, dict)
        assert set(answer_sources) == set(keywords)
        assert set(answer_sources.values()) == set(source_documents)

        for source in source_documents:
            assert source == Path(source).name
            assert source in corpus_files
            used_sources.add(source)

    manifest = json.loads(DATASET_MANIFEST.read_text(encoding="utf-8"))
    assert manifest == {
        "schema_version": "aircargo-gr-eval-dataset/v1.0",
        "dataset": "evaluation/curated_cases_aircargo_gr_multihop.jsonl",
        "dataset_sha256": dataset_digest(DATASET),
        "case_source": "agent_authored_over_real_documents",
        "case_count": 15,
        "source_document_count": len(used_sources),
        "corpus_manifest": "evaluation/aircargo_corpus.manifest.json",
        "corpus_sha256": corpus_manifest["corpus_sha256"],
        "question_class_sidecar": (
            "evaluation/curated_cases_aircargo_gr_multihop_question_class.jsonl"
        ),
    }


def test_supplement_sources_prove_every_answer_keyword() -> None:
    """Prove corpus source files match the manifest and contain their answer keywords."""
    corpus_dir = _corpus_dir()
    if not corpus_dir.is_dir():
        pytest.skip(f"AirCargo corpus absent at {corpus_dir}; set AIRCARGO_CORPUS_DIR")

    corpus_manifest = json.loads(CORPUS_MANIFEST.read_text(encoding="utf-8"))
    corpus_files = {str(row["name"]): row for row in corpus_manifest["files"]}

    for row in _jsonl(DATASET):
        for source in row["source_documents"]:
            source_path = corpus_dir / source
            raw = source_path.read_bytes()
            assert len(raw) == corpus_files[source]["bytes"]
            assert hashlib.sha256(raw).hexdigest() == corpus_files[source]["sha256"]

        for keyword, source in row["answer_sources"].items():
            source_text = (corpus_dir / source).read_text(encoding="utf-8").casefold()
            assert keyword.casefold() in source_text, (row["case_id"], keyword, source)


def test_supplement_question_classes_are_complete_agent_labels() -> None:
    rows = {str(row["case_id"]): row for row in _jsonl(DATASET)}
    labels = _jsonl(SIDECAR)
    classified = load_classified_cases(DATASET, SIDECAR, CLASS_MANIFEST)
    counts = Counter(case.label.question_class.value for case in classified)

    assert counts == {"multi_hop": 10, "aggregation": 5}
    assert len(classified) == len(labels) == len(rows) == 15
    assert all(case.label.evidence_class is EvidenceClass.AGENT_LABELLED for case in classified)
    assert all(case.label.approved_by is None for case in classified)

    for label in labels:
        assert label["labelled_by"] == "agent:codex"
        assert label["labelled_at"] == "2026-09-11"
        assert label["batch"] == 1
        assert label["evidence_class"] == "agent_labelled"
        reason = str(label["reason"])
        for source in rows[str(label["case_id"])]["source_documents"]:
            assert source in reason

    manifest = json.loads(CLASS_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["dataset"] == "evaluation/curated_cases_aircargo_gr_multihop.jsonl"
    assert manifest["dataset_sha256"] == dataset_digest(DATASET)
    assert manifest["evidence_class"] == "agent_labelled"
    assert manifest["case_count"] == 15
    assert manifest["question_class_counts"] == {
        "aggregation": 5,
        "global": 0,
        "multi_hop": 10,
        "single_hop": 0,
    }
