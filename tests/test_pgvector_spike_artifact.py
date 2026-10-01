"""Recompute every published D.1 metric from pinned corpus text and rankings."""
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from scripts.pgvector_spike import score_rows

ROOT = Path(__file__).resolve().parents[1]
# The spike scripts were published with the report in this commit; they did not
# exist at the report's code_base, so their digests are verified here.
REPORT_COMMIT = "06da9c6"


def test_d1_provenance_and_all_repetitions_replay():
    report = json.loads((ROOT / "evaluation/d1-pgvector-prererank.json").read_text(encoding="utf-8"))
    corpus = gzip.decompress((ROOT / "evaluation/gr1b-4436d61-graph-chunks.json.gz").read_bytes())
    assert hashlib.sha256(corpus).hexdigest() == report["input_sha256"]["ab_phase2_G2_graph_chunks.json"]
    texts = [c["page_content"] for c in json.loads(corpus)["chunks"]]
    cases, buckets = [], {}
    for filename in ("curated_cases_aircargo.jsonl", "curated_cases_aircargo_gr_multihop.jsonl"):
        raw = (ROOT / "evaluation" / filename).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == report["input_sha256"][filename]
        start = len(cases)
        cases.extend({"case_id": r["case_id"], "query": r["query"], "kws": r["expected"]["answer_contains"]}
                     for r in map(json.loads, raw.decode().splitlines()))
        buckets[Path(filename).stem] = (start, len(cases))
    # Provenance, not staleness: each recorded source digest is the blob at the
    # commit it describes (product sources at code_base, scripts at REPORT_COMMIT).
    # The live tree moves on (T-59 changed vectordb/_base_manager.py); the
    # published numbers keep their code SHA.
    for filename, expected in report["source_sha256"].items():
        directory = "scripts" if filename.startswith("pgvector_spike") else (
            "evaluation" if filename == "ragas_eval.py" else "vectordb")
        commit = REPORT_COMMIT if directory == "scripts" else report["code_base"]
        blob = subprocess.check_output(["git", "show", f"{commit}:{directory}/{filename}"], cwd=ROOT)
        assert hashlib.sha256(blob).hexdigest() == expected
    assert report["config"]["cases"] == 115
    assert report["config"]["chunks"] == len(texts) == 5589
    assert report["config"]["reranker"] is False
    assert len(report["runs"]) == 3
    for run in report["runs"]:
        assert set(run) == {"postgres", "chroma_bm25"}
        for result in run.values():
            assert len(result["rankings"]) == len(result["latency_ms"]) == 115
            assert all(np.isfinite(t) and t > 0 for t in result["latency_ms"])
            for ranking in result["rankings"]:
                assert len(ranking) == len(set(ranking))
                assert 1 <= len(ranking) <= 40
                assert all(0 <= index < 5589 for index in ranking)
            for bucket, (start, end) in buckets.items():
                replay = score_rows(cases[start:end], result["rankings"][start:end], texts)
                recorded = result["metrics"][bucket]
                assert replay["rows"] == recorded["rows"]
                for metric in ("mean_context_precision", "mean_context_recall"):
                    assert replay[metric] == pytest.approx(recorded[metric], abs=1e-12)
                for percentile in (50, 95):
                    assert recorded[f"latency_p{percentile}_ms"] == pytest.approx(
                        float(np.percentile(result["latency_ms"][start:end], percentile)))
    assert report["rls"] == {
        f"{tenant}:{table}": count
        for tenant, count in (("unset", 0), ("aircargo", 5589), ("zzz_other", 1))
        for table in ("spike_chunks", "kb_graph_nodes")
    }
