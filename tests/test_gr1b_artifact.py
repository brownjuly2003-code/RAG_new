"""Reproduce the published structural retrieval measurement without models."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from scripts.ab_context_precision import build_bucket_report, render_bucket_table

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports/gr/gr1b-structure-graph.json"
POOL = ROOT / "evaluation/gr1b-4436d61-candidates.json.gz"
CAPSULE = ROOT / "docs/evidence/gr1b-structure-graph.md"


def test_published_gr1b_reproduces_from_archived_pool(tmp_path: Path) -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    provenance = report["provenance"]
    raw = gzip.decompress(POOL.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == provenance["pool_sha256"]
    assert len(raw) == provenance["pool_bytes"]
    pool = tmp_path / "pool.json"
    pool.write_bytes(raw)
    rebuilt = build_bucket_report(
        pool_path=pool,
        dataset_path=ROOT / provenance["dataset"],
        sidecar_path=ROOT / provenance["label_sidecar"],
        label_manifest_path=ROOT / provenance["label_manifest"],
        corpus_manifest_path=ROOT / provenance["corpus"]["manifest"],
        pool_arm="G1",
    )
    for key in ("schema_version", "kind", "labels", "buckets", "aggregate",
                "per_case", "pool_diagnostics"):
        assert rebuilt[key] == report[key], key
    for key in ("dataset_sha256", "label_sidecar_sha256", "label_manifest_sha256",
                "corpus", "config"):
        assert rebuilt["provenance"][key] == provenance[key], key
    assert report["aggregate"]["num_cases"] == 100
    assert report["aggregate"]["context_precision"] < 0.63
    assert report["pool_diagnostics"]["graph_prefiltered_count"] == 0


def test_gr1b_capsule_quotes_report_table_and_provenance() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    capsule = CAPSULE.read_text(encoding="utf-8")
    table = render_bucket_table(report).split("| question class", 1)[1].rstrip()
    assert "| question class" + table in capsule
    for digest in (report["provenance"]["pool_sha256"],
                   report["provenance"]["dataset_sha256"],
                   report["provenance"]["corpus"]["corpus_sha256"],
                   report["provenance"]["code"]["commit"]):
        assert digest in capsule
    assert "NO-SHIP" in capsule
    assert "0 approved" in capsule
