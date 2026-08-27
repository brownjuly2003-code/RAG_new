"""Regression coverage for the second journey-admission provenance repair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.journey_admission import _source_digest, score_default_corpus


def _case_payload(*, journey: str, query: str) -> dict[str, object]:
    return {
        "case_id": f"case-{journey}",
        "query": query,
        "tags": [],
        "label": {
            "journey": journey,
            "expected_terminal": "verified",
            "root_cause": (
                "no_shipment_binding"
                if journey == "shipment_status"
                else "no_contract_for_intent"
            ),
            "binds_shipment": False,
            "confidence": "high",
            "labelled_by": "test-agent",
            "labelled_at": "2026-08-27",
            "batch": 1,
            "approved_by": None,
            "evidence_class": "agent_labelled",
            "note": "",
        },
    }


def test_score_uses_the_digest_verified_corpus_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus = tmp_path / "cases.jsonl"
    manifest = tmp_path / "cases.manifest.json"
    original = (json.dumps(_case_payload(journey="shipment_status", query="shipment status")) + "\n").encode(
        "utf-8"
    )
    replacement = (json.dumps(_case_payload(journey="out_of_scope", query="unrelated")) + "\n").encode(
        "utf-8"
    )
    corpus.write_bytes(original)
    manifest.write_text(
        json.dumps({"dataset_sha256": hashlib.sha256(original).hexdigest()}),
        encoding="utf-8",
    )

    read_bytes = Path.read_bytes
    has_switched = False

    def switching_read_bytes(path: Path) -> bytes:
        nonlocal has_switched
        if path == corpus and not has_switched:
            has_switched = True
            corpus.write_bytes(replacement)
            return original
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", switching_read_bytes)

    report = score_default_corpus(corpus_path=corpus, manifest_path=manifest)

    assert has_switched is True
    assert report.journey_counts["shipment_status"] == 1
    assert report.journey_counts["out_of_scope"] == 0


def test_source_digest_frames_each_file_boundary() -> None:
    first = _source_digest((b"a", b"bc", b"d"))
    second = _source_digest((b"ab", b"c", b"d"))

    assert first != second
