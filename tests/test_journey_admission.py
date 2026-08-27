"""Published measurement of the shipment-status admission gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.aircargo_labels import Journey
from evaluation.journey_admission import (
    AdmissionDecision,
    CorpusDigestMismatchError,
    admission_confusion_matrix,
    format_report,
    score_default_corpus,
    verify_corpus_digest,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET = PROJECT_ROOT / "evaluation" / "curated_cases_aircargo.jsonl"
MANIFEST = PROJECT_ROOT / "evaluation" / "curated_cases_aircargo.manifest.json"


def test_digest_guard_fails_closed_when_the_corpus_is_tampered(tmp_path: Path) -> None:
    corpus = tmp_path / "cases.jsonl"
    manifest = tmp_path / "cases.manifest.json"
    corpus.write_bytes(DATASET.read_bytes())
    manifest.write_text(MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
    corpus.write_bytes(corpus.read_bytes() + b"\n")

    with pytest.raises(CorpusDigestMismatchError, match="sha256 mismatch"):
        verify_corpus_digest(corpus, manifest)


def test_confusion_matrix_arithmetic_is_right_on_a_small_fixture() -> None:
    matrix = admission_confusion_matrix(
        (
            AdmissionDecision(Journey.SHIPMENT_STATUS, admitted=True),
            AdmissionDecision(Journey.OUT_OF_SCOPE, admitted=True),
            AdmissionDecision(Journey.SHIPMENT_STATUS, admitted=False),
            AdmissionDecision(Journey.CUSTOMS_DOCS, admitted=False),
        )
    )

    assert matrix.true_positive == 1
    assert matrix.false_positive == 1
    assert matrix.false_negative == 1
    assert matrix.true_negative == 1
    assert matrix.total == 4
    assert matrix.precision == pytest.approx(0.5)
    assert matrix.recall == pytest.approx(0.5)


def test_reported_counts_add_up_to_100_on_the_real_corpus() -> None:
    report = score_default_corpus(git_sha="test-sha")

    assert report.case_count == 100
    assert sum(report.journey_counts.values()) == 100
    assert report.confusion_matrix.total == 100
    assert report.as_dict()["corpus_sha256"] == json.loads(
        MANIFEST.read_text(encoding="utf-8")
    )["dataset_sha256"]


def test_report_publishes_decline_and_corpus_reachability_diagnostics() -> None:
    report = score_default_corpus(git_sha="test-sha")

    assert report.decline_reasons == {
        "no_shipment_reference": 99,
        "no_domain_noun": 78,
        "no_status_cue": 94,
        "neither_domain_noun_nor_status_cue": 73,
    }
    assert report.script_composition == {
        "contains_latin": 33,
        "contains_no_latin": 67,
    }
    assert report.vocabulary_reachability == {
        "contains_domain_noun": 22,
        "contains_status_cue": 6,
        "contains_both_domain_noun_and_status_cue": 1,
    }

    payload = report.as_dict()
    assert payload["decline_reasons"] == report.decline_reasons
    assert payload["script_composition"] == report.script_composition
    assert payload["vocabulary_reachability"] == report.vocabulary_reachability

    rendered = format_report(report)
    assert "Decline reasons (declined cases only):" in rendered
    assert "Script composition:" in rendered
    assert "Vocabulary reachability:" in rendered
