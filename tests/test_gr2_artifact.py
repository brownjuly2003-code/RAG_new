"""Reproduce the published GR-2 entity-lane measurement without models.

The Mac run produced the four reranked pools, both `G2` pool metas, both
classification caches with their manifests and the extraction manifest. They
are archived under `evaluation/` as gzip; this test decompresses them into a
temporary directory, checks every digest against the published bytes, rebuilds
the report with the code commit of that run and compares it with the published
JSON. Nothing here loads a model, touches the network or reads the corpus.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.ab_context_precision import build_gr2_report, render_gr2_table
from scripts.ab_remote_contextual import _ENTITY_QUESTION_CLASSES

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports/gr/gr2-entity-graph.json"
CAPSULE = ROOT / "docs/evidence/gr2-entity-graph-lane.md"

#: The commit whose `git archive` produced the Mac run (T-26 orchestrator).
CODE_COMMIT = "9ca86301bd53d327e48aaed811a47c4542b08bd2"

#: archive name -> (SHA-256 of the uncompressed bytes, uncompressed size).
#: These are the bytes the orchestrator copied off `deproject-mac`; the writer
#: never regenerated them, so a mismatch here means the archive changed.
ARCHIVES: dict[str, tuple[str, int]] = {
    "gr2-9ca8630-phase-c-G1-candidates.json.gz": (
        "6848b5f33787ca7a91c3137a5f7da90c0b532093048245d378e296a53482a059",
        8341699,
    ),
    "gr2-9ca8630-phase-c-G2-candidates.json.gz": (
        "aa5bf94c2e12f7de29b20e625cf1a338320b7fc82feeb95072bfb5a68e38a654",
        8893885,
    ),
    "gr2-9ca8630-phase-c-G2-pool-meta.json.gz": (
        "4825057628d00f7fc2926a42c623aaebaef5b783cc94cf6c90c7f0943747b396",
        901,
    ),
    "gr2-9ca8630-phase-c-classifications.jsonl.gz": (
        "c5c79e9343b9b22dabc3b8d13a6565f959831ceaa178c017af1cd48e53cdf861",
        32949,
    ),
    "gr2-9ca8630-phase-c-classifications-manifest.json.gz": (
        "e0429f2b287efa733999e9fa9bea2f2feb91ad4be9cdacc3059ef2e6aae45404",
        531,
    ),
    "gr2-9ca8630-bucket-G1-candidates.json.gz": (
        "17db60197eaa7df9173f1c9377368996cbe1600254670057ef9dc397e3f0762b",
        1472052,
    ),
    "gr2-9ca8630-bucket-G2-candidates.json.gz": (
        "73a11d8fa11bd75b8ef9a3319f0659426cc6f9f1c86c95cb3412c56d3cfbec9d",
        2691344,
    ),
    "gr2-9ca8630-bucket-G2-pool-meta.json.gz": (
        "34bda4324e5ca093793d51da13350fa0a417c09aae704c23813bc95150f72326",
        919,
    ),
    "gr2-9ca8630-bucket-classifications.jsonl.gz": (
        "f5f9121eee391ef8e5cef96603b3f5f8e59e7fcdbdd4b784e3b5408eb0240755",
        6393,
    ),
    "gr2-9ca8630-bucket-classifications-manifest.json.gz": (
        "f4709e7172a4d0afa7388c7707bf50891834e3c7277937257d9b17c9c7b6b816",
        530,
    ),
    "gr2-9ca8630-extraction-manifest.json.gz": (
        "d763683ef4bb88202da3a0293099770c1b3933a4adc3945784866464221ef3fd",
        703,
    ),
}

#: Keys that differ between the producer and a local rebuild: stored input
#: paths, and `provenance.code` whose file digests are hashed from the live
#: working tree rather than from the measurement commit.
_SKIP_KEYS = {"pool_path", "pool_meta_path", "code"}

GR1B_POOL = ROOT / "evaluation/gr1b-4436d61-candidates.json.gz"
PHASE_C_G1_POOL = ROOT / "evaluation/gr2-9ca8630-phase-c-G1-candidates.json.gz"
PHASE_C_G2_POOL = ROOT / "evaluation/gr2-9ca8630-phase-c-G2-candidates.json.gz"


def _unpack(tmp_path: Path) -> dict[str, Path]:
    """Decompress every archive into `tmp_path`, checking its digest."""
    unpacked: dict[str, Path] = {}
    for name, (sha256, size) in ARCHIVES.items():
        raw = gzip.decompress((ROOT / "evaluation" / name).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == sha256, name
        assert len(raw) == size, name
        out = tmp_path / name[: -len(".gz")]
        out.write_bytes(raw)
        unpacked[name] = out
    return unpacked


def _strip_paths(value: Any) -> Any:
    """Drop stored input paths and live code digests before comparing reports."""
    if isinstance(value, dict):
        return {k: _strip_paths(v) for k, v in value.items() if k not in _SKIP_KEYS}
    if isinstance(value, list):
        return [_strip_paths(item) for item in value]
    return value


def _phase_c_lane_rerank_deltas() -> list[float]:
    g1_rows = json.loads(gzip.decompress(PHASE_C_G1_POOL.read_bytes()))
    g2_rows = json.loads(gzip.decompress(PHASE_C_G2_POOL.read_bytes()))
    g1_by_case = {row["case_id"]: row for row in g1_rows}
    deltas = [
        round(row["rerank_s"] - g1_by_case[row["case_id"]]["rerank_s"], 4)
        for row in g2_rows
        if row["routed_question_class"] in _ENTITY_QUESTION_CLASSES
    ]
    return sorted(deltas)


def _rebuild(tmp_path: Path) -> dict[str, Any]:
    unpacked = _unpack(tmp_path)
    return build_gr2_report(
        g1_pool_path=unpacked["gr2-9ca8630-phase-c-G1-candidates.json.gz"],
        g2_pool_path=unpacked["gr2-9ca8630-phase-c-G2-candidates.json.gz"],
        g2_pool_meta_path=unpacked["gr2-9ca8630-phase-c-G2-pool-meta.json.gz"],
        bucket_g1_pool_path=unpacked["gr2-9ca8630-bucket-G1-candidates.json.gz"],
        bucket_g2_pool_path=unpacked["gr2-9ca8630-bucket-G2-candidates.json.gz"],
        bucket_g2_pool_meta_path=unpacked["gr2-9ca8630-bucket-G2-pool-meta.json.gz"],
        code_commit=CODE_COMMIT,
    )


def test_published_gr2_reproduces_from_archived_pools(tmp_path: Path) -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    rebuilt = _rebuild(tmp_path)

    for key in ("schema_version", "kind", "evidence_class"):
        assert rebuilt[key] == report[key], key
    for dataset in ("phase_c", "multi_doc_bucket"):
        assert _strip_paths(rebuilt[dataset]) == _strip_paths(report[dataset]), dataset
        assert _strip_paths(rebuilt["provenance"][dataset]) == _strip_paths(
            report["provenance"][dataset]
        ), dataset
    assert rebuilt["provenance"]["config"] == report["provenance"]["config"]
    assert report["provenance"]["code"]["commit"] == CODE_COMMIT
    assert report["provenance"]["config"]["graph_retrieval_default"] == "unchanged"


def test_published_gr2_pool_digests_match_the_archives() -> None:
    """The report's own pool digests are the archived uncompressed bytes."""
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    expected = {
        ("phase_c", "G1"): "gr2-9ca8630-phase-c-G1-candidates.json.gz",
        ("phase_c", "G2"): "gr2-9ca8630-phase-c-G2-candidates.json.gz",
        ("multi_doc_bucket", "G1"): "gr2-9ca8630-bucket-G1-candidates.json.gz",
        ("multi_doc_bucket", "G2"): "gr2-9ca8630-bucket-G2-candidates.json.gz",
    }
    for (dataset, arm), name in expected.items():
        stored = report["provenance"][dataset][arm]["pool_sha256"]
        assert stored == ARCHIVES[name][0], f"{dataset}/{arm}"
    metas = {
        "phase_c": "gr2-9ca8630-phase-c-G2-pool-meta.json.gz",
        "multi_doc_bucket": "gr2-9ca8630-bucket-G2-pool-meta.json.gz",
    }
    for dataset, name in metas.items():
        meta = report["provenance"][dataset]["G2"]["pool_meta"]
        assert meta["pool_meta_sha256"] == ARCHIVES[name][0], dataset
        # The pools were built against the archived extraction and
        # classification caches; the meta pins both by manifest digest.
        assert (
            meta["entities_manifest_sha256"]
            == ARCHIVES["gr2-9ca8630-extraction-manifest.json.gz"][0]
        )
    assert (
        report["provenance"]["phase_c"]["G2"]["pool_meta"]["classifications_manifest_sha256"]
        == ARCHIVES["gr2-9ca8630-phase-c-classifications-manifest.json.gz"][0]
    )
    assert (
        report["provenance"]["multi_doc_bucket"]["G2"]["pool_meta"][
            "classifications_manifest_sha256"
        ]
        == ARCHIVES["gr2-9ca8630-bucket-classifications-manifest.json.gz"][0]
    )


def test_published_gr2_states_the_measured_outcome() -> None:
    """The numbers the capsule's verdicts rest on, asserted at the report."""
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    phase_c = report["phase_c"]
    bucket = report["multi_doc_bucket"]

    assert phase_c["G1"]["aggregate"]["num_cases"] == 100
    assert bucket["G1"]["aggregate"]["num_cases"] == 15
    for pair in (phase_c, bucket):
        for arm in ("G1", "G2"):
            assert pair[arm]["labels"]["evidence_class"] == "agent_labelled"
            assert pair[arm]["labels"]["approved"] == 0
        assert pair["comparison"]["non_lane_parity"]["divergent_case_ids"] == []
        assert pair["comparison"]["keyword_loss_case_ids"] == []
        assert pair["comparison"]["downgrades"] == []
        assert pair["G2"]["pool_diagnostics"]["entity_candidates_max"] <= 50
        assert pair["G2"]["pool_diagnostics"]["entity_hops_max"] <= 2

    # Gate 1: single-hop precision is not worse than the G1 (= GR-1b) arm.
    assert phase_c["comparison"]["precision_deltas"]["single_hop"] >= 0
    # Gate 4: the 0.63 precision gate is still missed — NO-SHIP.
    assert phase_c["G2"]["aggregate"]["context_precision"] < 0.63
    # The multi-document bucket moved nothing at all, in either direction.
    assert bucket["comparison"]["aggregate"]["context_precision_delta"] == 0.0
    assert bucket["comparison"]["aggregate"]["context_recall_delta"] == 0.0
    assert bucket["G2"]["pool_diagnostics"]["entity_lane_cases"] == 11
    # The category prefilter matched nothing in either arm or dataset.
    for pair in (phase_c, bucket):
        for arm in ("G1", "G2"):
            assert pair[arm]["pool_diagnostics"]["graph_prefiltered_count"] == 0


def test_gr2_capsule_quotes_the_table_and_every_digest(tmp_path: Path) -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    capsule = CAPSULE.read_text(encoding="utf-8")

    assert render_gr2_table(report).rstrip("\n") in capsule

    digests = {sha256 for sha256, _ in ARCHIVES.values()}
    digests.add(report["provenance"]["code"]["commit"])
    for dataset in ("phase_c", "multi_doc_bucket"):
        provenance = report["provenance"][dataset]
        digests.add(provenance["dataset_sha256"])
        digests.add(provenance["label_sidecar_sha256"])
        digests.add(provenance["label_manifest_sha256"])
        digests.add(provenance["corpus"]["corpus_sha256"])
        meta = provenance["G2"]["pool_meta"]
        digests.add(meta["graph_chunks_sha256"])
        digests.add(meta["structure_graph_digest"])
    for digest in sorted(digests):
        assert digest in capsule, digest

    assert "NO-SHIP" in capsule
    assert "0 approved" in capsule
    assert "qwen2.5:7b" in capsule
    assert "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e" in capsule
    assert "unchanged" in capsule

    assert "byte-identical" not in capsule
    assert "bit-identical" not in capsule
    assert "identical case by case" in capsule
    assert "rerank_s" in capsule
    assert "identical in candidates and contexts" in capsule

    assert "aircargo-waybill-escalation-events" in capsule
    assert "aircargo-customs-broker-escalation" in capsule
    assert "0.3000" in capsule
    assert "0.3545" in capsule
    assert "0.2364" in capsule
    assert "still MISS" in capsule
    assert "+0.0012" in capsule

    assert "whole-dataset" in capsule
    for delta in _phase_c_lane_rerank_deltas():
        assert str(delta) in capsule, delta


def _code_blocks(report: dict[str, Any]) -> list[dict[str, Any]]:
    """The top-level and the four per-arm `provenance.code` blocks of the report."""
    blocks = [report["provenance"]["code"]]
    for dataset in ("phase_c", "multi_doc_bucket"):
        for arm in ("G1", "G2"):
            blocks.append(report[dataset][arm]["provenance"]["code"])
    return blocks


def test_published_gr2_code_digests_match_the_measurement_commit() -> None:
    """Every file digest in the report is the LF blob at `code_commit`, never the live tree."""
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    checked = 0
    for code in _code_blocks(report):
        assert code["commit"] == CODE_COMMIT
        for rel, digest in code["files"].items():
            blob = subprocess.check_output(["git", "show", f"{CODE_COMMIT}:{rel}"], cwd=ROOT)
            assert b"\r\n" not in blob, rel
            assert hashlib.sha256(blob).hexdigest() == digest, rel
            checked += 1
    assert checked == 14 + 8 + 14 + 8 + 14


def test_published_gr2_rebuild_skips_live_code_digests(tmp_path: Path, monkeypatch: Any) -> None:
    """A later edit of a source file must not fail the archive-rebuild gate."""
    from scripts import ab_context_precision as mod

    def fake_code_digests(paths: Any = ()) -> dict[str, str]:
        return {rel: "0" * 64 for rel in paths}

    monkeypatch.setattr(mod, "_code_digests", fake_code_digests)
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    rebuilt = _rebuild(tmp_path)
    assert (
        rebuilt["phase_c"]["G1"]["provenance"]["code"]["files"]
        != report["phase_c"]["G1"]["provenance"]["code"]["files"]
    )
    assert _strip_paths(rebuilt["phase_c"]) == _strip_paths(report["phase_c"])
    assert _strip_paths(rebuilt["multi_doc_bucket"]) == _strip_paths(report["multi_doc_bucket"])
    assert report["provenance"]["code"]["commit"] == CODE_COMMIT


def test_phase_c_g1_matches_published_gr1b_pool_case_by_case() -> None:
    """G2 − G1 is the entity lane: phase-C G1 equals the published GR-1b pool."""
    gr1b = json.loads(gzip.decompress(GR1B_POOL.read_bytes()))
    phase_c_g1 = json.loads(gzip.decompress(PHASE_C_G1_POOL.read_bytes()))
    assert [row["case_id"] for row in gr1b] == [row["case_id"] for row in phase_c_g1]
    shared = (
        "cands",
        "prerank_cands",
        "reranked_cands",
        "cand_sources",
        "prerank_sources",
        "reranked_sources",
    )
    for archived, reproduced in zip(gr1b, phase_c_g1, strict=True):
        for key in shared:
            assert archived.get(key) == reproduced.get(key), (
                archived["case_id"],
                key,
            )


def test_agent_state_records_finished_gr2_measurement() -> None:
    """AGENT_STATE.md never reports GR-2 extraction as still running.

    Until 2026-10-17 the digest itself carried the finished state; since the tidy-up of that
    day it holds working conventions only, the measurement is a row of EVIDENCE_INDEX.md, and
    the digest as it stood is archived with the finished state in it.
    """
    text = (ROOT / "AGENT_STATE.md").read_text(encoding="utf-8")
    assert "1159/5589" not in text
    assert "about 22 h left" not in text
    assert "once extraction is done" not in text
    index = (ROOT / "EVIDENCE_INDEX.md").read_text(encoding="utf-8")
    assert "docs/evidence/gr2-entity-graph-lane.md" in index
    archived = (ROOT / "archive/docs/state/agent-state-through-2026-10-17.md").read_text(
        encoding="utf-8"
    )
    assert "5589/5589" in archived
    assert "0 rejected" in archived
