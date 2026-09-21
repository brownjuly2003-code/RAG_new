"""Reproduce the published GR-3 graph-lane A/B without models.

The Mac run re-measured the hybrid arm and both graph arms on the two
datasets (`Hm`/`G1m`/`G2m`), ran one generation benchmark over the GR-2
`G2` phase-C contexts and built the report from the archived inputs.  The
pools are archived under `evaluation/` as gzip; this test decompresses the
eleven archives the rebuild needs into a temporary directory, checks every
uncompressed digest and size against the pinned table, rebuilds the report
once per module (the bootstrap draws 10000 resamples) and compares it with
the published JSON as a whole object.  Nothing here loads a model, touches
the network or reads the corpus.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.ab_remote_contextual import _ENTITY_QUESTION_CLASSES
from scripts.gr3_graph_lane_ab import build_gr3_report, render_gr3_table

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports/gr/gr3-graph-lane-ab.json"
CAPSULE = ROOT / "docs/evidence/gr3-graph-lane-ab.md"

#: The commit whose clean clone produced every GR-3 measurement (T-28).
CODE_COMMIT = "32de5324454ffbaa72b2b29bd41e466f0664e32a"
HOST = "deproject-mac, Intel i5-7500, 8 GiB, macOS 13.7.8"

#: The only case the paired generation analysis excludes: its LLM-judge row
#: is invalid in all three runs, leaving 99 valid rows per run and 297/300
#: valid rows overall (not 299/300).
EXCLUDED_CASE = "aircargo-business-trip-foreign-approval"

#: archive name -> (SHA-256 of the uncompressed bytes, uncompressed size).
#: The seven GR-3/H archives were placed by the orchestrator; the four
#: `gr2-9ca8630-*` entries are the published `G1`/`G2` arms the re-runs are
#: compared against, copied from the GR-2 publication.
ARCHIVES: dict[str, tuple[str, int]] = {
    "gr3-32de532-phase-c-Hm-candidates.json.gz": (
        "0e93f6e82edc2830269baa803fab8f677fe3fda0803c5afccdfb5289960c2d55",
        7702433,
    ),
    "gr3-32de532-phase-c-G1m-candidates.json.gz": (
        "cd139b0b113ce642613d955914e34d104a1eb74d258b56f311aae084e80feb7d",
        8350434,
    ),
    "gr3-32de532-phase-c-G2m-candidates.json.gz": (
        "fb7a22613514434042695a531f85dae8b319c150e5c3ef25e50bdbf47745792e",
        8893910,
    ),
    "gr3-32de532-bucket-Hm-candidates.json.gz": (
        "3a3020799e8310fcaf3532783cae9d83f8f03b3b0a741488b425ac7edec0aeee",
        1357434,
    ),
    "gr3-32de532-bucket-G1m-candidates.json.gz": (
        "955c74d810e86282cf88a61c670ee9c241f0434763dad7d8206164e093370c93",
        1473362,
    ),
    "gr3-32de532-bucket-G2m-candidates.json.gz": (
        "df4486ffe45a3244cf1d2254b3859570e8cb046258983326d0b43e05c3ba505d",
        2691353,
    ),
    "c1a-c06bdf5-phase-c-C-candidates.json.gz": (
        "91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10",
        7692098,
    ),
    "gr2-9ca8630-phase-c-G1-candidates.json.gz": (
        "6848b5f33787ca7a91c3137a5f7da90c0b532093048245d378e296a53482a059",
        8341699,
    ),
    "gr2-9ca8630-phase-c-G2-candidates.json.gz": (
        "aa5bf94c2e12f7de29b20e625cf1a338320b7fc82feeb95072bfb5a68e38a654",
        8893885,
    ),
    "gr2-9ca8630-bucket-G1-candidates.json.gz": (
        "17db60197eaa7df9173f1c9377368996cbe1600254670057ef9dc397e3f0762b",
        1472052,
    ),
    "gr2-9ca8630-bucket-G2-candidates.json.gz": (
        "73a11d8fa11bd75b8ef9a3319f0659426cc6f9f1c86c95cb3412c56d3cfbec9d",
        2691344,
    ),
}

#: The raw graph generation report and its `.sha256` sidecar, stored the
#: same way C.1a's raw report is stored.
GRAPH_GENERATION = ROOT / ("evaluation/gr3-g2-qwen25-7b-32de532-phase-c-generator-benchmark.json")
GRAPH_GENERATION_SHA256 = "76308bc8963b15c73ab9d75745f444068b2046a86864f2d786e88ccde2f9ada2"
GRAPH_GENERATION_BYTES = 1000646

#: C.1a's published generation report supplies the hybrid half.
HYBRID_GENERATION = ROOT / ("evaluation/c1a-qwen25-7b-c06bdf5-phase-c-generator-benchmark.json")
HYBRID_GENERATION_SHA256 = "ac8d9cc20a8d414490fd0ada46e35731d7a2891e7169c3ec22ef88a4644db534"

DATASET_SHA256 = "3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720"
OLLAMA_DIGEST = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
NLI_REVISION = "8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c"

#: The bucket cases that fall FULL->PART under both graph arms.
BUCKET_FULL_TO_PART = [
    "aircargo-gr-compare-loss-damage-evidence",
    "aircargo-gr-customs-export-readiness",
    "aircargo-gr-offload-road-handover",
]


@pytest.fixture(scope="module")
def unpacked(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Decompress every archive once, checking digest and size."""
    tmp = tmp_path_factory.mktemp("gr3-artifact")
    unpacked: dict[str, Path] = {}
    for name, (sha256, size) in ARCHIVES.items():
        raw = gzip.decompress((ROOT / "evaluation" / name).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == sha256, name
        assert len(raw) == size, name
        out = tmp / name[: -len(".gz")]
        out.write_bytes(raw)
        unpacked[name] = out
    return unpacked


@pytest.fixture(scope="module")
def published() -> dict[str, Any]:
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rebuilt(unpacked: dict[str, Path]) -> dict[str, Any]:
    """Build once per module; the bootstrap draws 10000 resamples."""
    return build_gr3_report(
        phase_c_h=unpacked["c1a-c06bdf5-phase-c-C-candidates.json.gz"],
        phase_c_hm=unpacked["gr3-32de532-phase-c-Hm-candidates.json.gz"],
        phase_c_g1=unpacked["gr2-9ca8630-phase-c-G1-candidates.json.gz"],
        phase_c_g2=unpacked["gr2-9ca8630-phase-c-G2-candidates.json.gz"],
        phase_c_g1m=unpacked["gr3-32de532-phase-c-G1m-candidates.json.gz"],
        phase_c_g2m=unpacked["gr3-32de532-phase-c-G2m-candidates.json.gz"],
        bucket_hm=unpacked["gr3-32de532-bucket-Hm-candidates.json.gz"],
        bucket_g1=unpacked["gr2-9ca8630-bucket-G1-candidates.json.gz"],
        bucket_g2=unpacked["gr2-9ca8630-bucket-G2-candidates.json.gz"],
        bucket_g1m=unpacked["gr3-32de532-bucket-G1m-candidates.json.gz"],
        bucket_g2m=unpacked["gr3-32de532-bucket-G2m-candidates.json.gz"],
        hybrid_generation=HYBRID_GENERATION,
        graph_generation=GRAPH_GENERATION,
        code_commit=CODE_COMMIT,
        host=HOST,
        evidence_class="measured",
    )


def test_rebuilt_report_equals_the_published_json(
    published: dict[str, Any], rebuilt: dict[str, Any]
) -> None:
    """The whole rebuilt object equals the publication, nothing stripped.

    The report stores digests and repository-relative manifest paths only
    (no absolute paths, no live-code hashes), so no key needs stripping.
    """
    assert rebuilt == published


def test_report_pins_every_input_digest(published: dict[str, Any]) -> None:
    """The report pins every archived pool plus the run's commit and host."""
    pools = {
        "phase_c_h": "c1a-c06bdf5-phase-c-C-candidates.json.gz",
        "phase_c_hm": "gr3-32de532-phase-c-Hm-candidates.json.gz",
        "phase_c_g1": "gr2-9ca8630-phase-c-G1-candidates.json.gz",
        "phase_c_g2": "gr2-9ca8630-phase-c-G2-candidates.json.gz",
        "phase_c_g1m": "gr3-32de532-phase-c-G1m-candidates.json.gz",
        "phase_c_g2m": "gr3-32de532-phase-c-G2m-candidates.json.gz",
        "bucket_hm": "gr3-32de532-bucket-Hm-candidates.json.gz",
        "bucket_g1": "gr2-9ca8630-bucket-G1-candidates.json.gz",
        "bucket_g2": "gr2-9ca8630-bucket-G2-candidates.json.gz",
        "bucket_g1m": "gr3-32de532-bucket-G1m-candidates.json.gz",
        "bucket_g2m": "gr3-32de532-bucket-G2m-candidates.json.gz",
    }
    inputs = published["provenance"]["inputs"]
    for key, name in pools.items():
        assert inputs[key] == ARCHIVES[name][0], key
    assert inputs["graph_generation"] == GRAPH_GENERATION_SHA256
    assert inputs["hybrid_generation"] == HYBRID_GENERATION_SHA256
    assert published["schema_version"] == "gr-graph-lane-ab/v1.0"
    assert published["evidence_class"] == "measured"
    assert published["provenance"]["code_commit"] == CODE_COMMIT
    assert published["provenance"]["host"] == HOST
    assert published["latency"]["host"] == HOST
    assert published["provenance"]["phase_c"]["dataset_sha256"] == DATASET_SHA256
    assert published["provenance"]["config"] == {
        "top_k": 5,
        "context_chars": 6000,
        "bootstrap_resamples": 10000,
        "bootstrap_seed": 20260918,
    }


def test_graph_generation_report_is_the_archived_run(published: dict[str, Any]) -> None:
    """The generation half ran over the published `G2` pool, and is not evidence."""
    raw = GRAPH_GENERATION.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == GRAPH_GENERATION_SHA256
    assert len(raw) == GRAPH_GENERATION_BYTES
    sidecar = GRAPH_GENERATION.with_name(GRAPH_GENERATION.name + ".sha256")
    assert sidecar.read_text(encoding="utf-8").split() == [
        GRAPH_GENERATION_SHA256,
        GRAPH_GENERATION.name,
    ]

    gen = json.loads(raw)
    prov = gen["provenance"]
    assert prov["code_sha"] == CODE_COMMIT
    assert prov["code_tree_clean"] is True
    assert prov["dataset_sha256"] == DATASET_SHA256
    # The generation contexts are the published GR-2 `G2` phase-C pool.
    g2_digest = ARCHIVES["gr2-9ca8630-phase-c-G2-candidates.json.gz"][0]
    assert prov["contexts_sha256"] == g2_digest
    assert published["provenance"]["inputs"]["phase_c_g2"] == g2_digest
    assert prov["ollama_model_digest"] == OLLAMA_DIGEST
    assert prov["config"]["allow_short_contexts"] is True
    assert prov["config"]["runs"] == 3
    assert gen["evidence_class"] == "not_evidence"

    assert gen["evidence_reasons"] == [
        "run 1 failed_cases=1",
        "run 2 failed_cases=1",
        "run 3 failed_cases=1",
    ]
    runs = [run["cases"] for run in gen["runs"]]
    assert len(runs) == 3
    for run_rows in runs:
        assert len(run_rows) == 100
        invalid = [row for row in run_rows if not row["llm_judge_valid"]]
        assert len(invalid) == 1  # 99 valid rows per run
        assert invalid[0]["case_id"] == EXCLUDED_CASE
        assert invalid[0]["generation_valid"] is True
        assert invalid[0]["nli_valid"] is True
        assert "'Score: 1.0'" in invalid[0]["error"]
    rows = [row for run_rows in runs for row in run_rows]
    assert len(rows) == 300
    # 297/300 valid rows overall, not 299/300.
    assert sum(1 for row in rows if row["llm_judge_valid"]) == 297


def test_hybrid_pool_is_the_pool_c1a_generated_from(published: dict[str, Any]) -> None:
    """The `H` arm is the published hybrid pool that C.1a generated from."""
    c1a = json.loads(HYBRID_GENERATION.read_text(encoding="utf-8"))
    h_digest = ARCHIVES["c1a-c06bdf5-phase-c-C-candidates.json.gz"][0]
    assert c1a["provenance"]["contexts_sha256"] == h_digest
    assert published["provenance"]["inputs"]["phase_c_h"] == h_digest


def test_measured_outcome_at_the_report(published: dict[str, Any]) -> None:
    """Verdict, criteria, parity blocks, generation and retrieval numbers."""
    decision = published["decision"]
    assert decision["verdict"] == "NO_SHIP_TO_DEFAULT"
    assert decision["failed_criteria"] == [
        "llm_faithfulness_not_significantly_fallen",
        "nli_faithfulness_not_significantly_fallen",
        "retrieve_p95_within_200ms",
    ]
    criteria = decision["criteria"]
    assert criteria["precision_rose"]["status"] == "pass"
    assert criteria["precision_rose"]["passed"] is True
    assert criteria["full_not_fallen"]["status"] == "pass"
    assert criteria["full_not_fallen"]["g2_full"] == 89
    assert criteria["full_not_fallen"]["h_full"] == 87
    faithfulness = (
        "llm_faithfulness_not_significantly_fallen",
        "nli_faithfulness_not_significantly_fallen",
    )
    for name in faithfulness:
        assert criteria[name]["status"] == "not_evidence", name
        assert criteria[name]["passed"] is False, name
    assert criteria["retrieve_p95_within_200ms"]["status"] == "fail"
    assert criteria["retrieve_p95_within_200ms"]["threshold_ms"] == 200.0
    assert criteria["retrieve_p95_within_200ms"]["delta_ms"] == 8765.2

    # All five parity blocks: every re-run is identical case by case.
    blocks = {
        **{f"phase_c/{key}": block for key, block in published["parity"]["phase_c"].items()},
        **{
            f"multi_doc_bucket/{key}": block
            for key, block in published["parity"]["multi_doc_bucket"].items()
        },
    }
    assert set(blocks) == {
        "phase_c/Hm_vs_H",
        "phase_c/G1m_vs_G1",
        "phase_c/G2m_vs_G2",
        "multi_doc_bucket/G1m_vs_G1",
        "multi_doc_bucket/G2m_vs_G2",
    }
    for name, block in blocks.items():
        assert block["identical"] is True, name
        assert block["only_new"] == [], name
        assert block["only_published"] == [], name
        for diff in block["fields"].values():
            assert diff["count"] == 0, name

    generation = published["generation"]
    assert generation["cases"] == 99
    assert generation["excluded_case_ids"] == [EXCLUDED_CASE]
    assert generation["graph_evidence_class"] == "not_evidence"
    assert generation["graph_evidence_reasons"] == [
        "run 1 failed_cases=1",
        "run 2 failed_cases=1",
        "run 3 failed_cases=1",
    ]
    assert generation["graph_mean_context_count"] == 3.04
    llm = generation["metrics"]["llm_faithfulness"]
    assert llm["hybrid_mean"] == 0.8278
    assert llm["graph_mean"] == 0.8005
    assert llm["mean_difference"] == -0.0273
    assert llm["ci_low"] == -0.0591
    assert llm["ci_high"] == 0.0061
    nli = generation["metrics"]["nli_faithfulness"]
    assert nli["hybrid_mean"] == 0.8909
    assert nli["graph_mean"] == 0.8877
    assert nli["mean_difference"] == -0.0032
    assert nli["ci_low"] == -0.0496
    assert nli["ci_high"] == 0.0429
    paired_latency = generation["metrics"]["latency_ms"]["mean_difference"]
    assert round(paired_latency / 1000.0, 1) == -97.4

    # Phase C, all cases: `G2` stays below the 0.63 precision bar.
    arms = published["phase_c"]["arms"]
    assert arms["H"]["all_cases"]["context_precision"] == 0.5067
    assert arms["H"]["all_cases"]["context_recall"] == 0.905
    assert arms["G1"]["all_cases"]["context_precision"] == 0.5475
    assert arms["G2"]["all_cases"]["context_precision"] == 0.5487
    assert arms["G2"]["all_cases"]["context_precision"] < 0.63
    assert arms["G2"]["all_cases"]["context_recall"] == 0.925
    assert arms["H"]["all_cases"]["FULL"] == 87
    assert arms["G1"]["all_cases"]["FULL"] == 88
    assert arms["G2"]["all_cases"]["FULL"] == 89
    g2_h = next(
        d for d in published["phase_c"]["deltas"]["G2-H"] if d["question_class"] == "all cases"
    )
    assert g2_h["context_precision"] == 0.042
    assert g2_h["context_recall"] == 0.02
    losses = published["phase_c"]["keyword_transitions"]["G2-H"]["loss_case_ids"]
    assert losses["FULL->PART"] == ["aircargo-templates-checklist"]
    assert losses["PART->MISS"] == ["aircargo-customs-special-cargo-manual-check"]

    # Multi-document bucket: recall and FULL fall under both graph arms.
    bucket = published["multi_doc_bucket"]["arms"]
    assert bucket["Hm"]["all_cases"]["context_recall"] == 0.5
    assert bucket["Hm"]["all_cases"]["FULL"] == 4
    for arm in ("G1", "G2"):
        assert bucket[arm]["all_cases"]["context_recall"] == 0.4, arm
        assert bucket[arm]["all_cases"]["FULL"] == 1, arm
    assert bucket["Hm"]["mean_contexts"] == 5.0
    assert bucket["G1"]["mean_contexts"] == 2.9333
    assert bucket["G2"]["mean_contexts"] == 2.9333
    transitions = published["multi_doc_bucket"]["keyword_transitions"]
    for arm in ("G1-Hm", "G2-Hm"):
        assert transitions[arm]["loss_case_ids"]["FULL->PART"] == BUCKET_FULL_TO_PART, arm
    assert transitions["G2-G1"]["loss_case_ids"] == {
        "FULL->MISS": [],
        "FULL->PART": [],
        "PART->MISS": [],
    }
    same = next(
        d
        for d in published["multi_doc_bucket"]["deltas"]["G2-G1"]
        if d["question_class"] == "all cases"
    )
    assert same["context_precision"] == 0.0
    assert same["context_recall"] == 0.0


def test_latency_p95_falls_on_the_case_after_the_lane_cases(
    unpacked: dict[str, Path], published: dict[str, Any]
) -> None:
    """The capsule's latency paragraph, recomputed from the archived rows."""
    g2_rows = json.loads(
        unpacked["gr3-32de532-phase-c-G2m-candidates.json.gz"].read_text(encoding="utf-8")
    )
    hybrid_rows = json.loads(
        unpacked["gr3-32de532-phase-c-Hm-candidates.json.gz"].read_text(encoding="utf-8")
    )

    def total_ms(row: dict[str, Any]) -> float:
        return row["rerank_s"] * 1000.0 + sum(row["timing_ms"].values())

    def prerank_size(row: dict[str, Any]) -> int:
        # Rows carry the prerank pool as a list or as a count.
        pool = row["prerank_cands"]
        return len(pool) if isinstance(pool, list) else int(pool)

    lane_rows = [row for row in g2_rows if row["routed_question_class"] in _ENTITY_QUESTION_CLASSES]
    assert len(lane_rows) == 6
    ranked = sorted(g2_rows, key=total_ms, reverse=True)
    slowest = ranked[:5]
    assert [row["case_id"] for row in slowest] == [
        "aircargo-fuel-supply-evidence",
        "aircargo-cargo-insurance-operational-limits",
        "aircargo-customs-broker-escalation",
        "aircargo-internal-transfer-documents",
        "aircargo-waybill-escalation-events",
    ]
    assert [prerank_size(row) for row in slowest] == [90, 79, 87, 81, 73]
    rerank_seconds = [row["rerank_s"] for row in slowest]
    assert round(min(rerank_seconds), 1) == 92.7
    assert round(max(rerank_seconds), 1) == 134.3

    def p95_nearest_rank(values: list[float]) -> float:
        ordered = sorted(values)
        rank = -(-95 * len(ordered) // 100)  # ceil(0.95 * n), nearest-rank method
        return ordered[rank - 1]

    g2_p95 = p95_nearest_rank([total_ms(row) for row in g2_rows])
    hybrid_p95 = p95_nearest_rank([total_ms(row) for row in hybrid_rows])
    assert round(g2_p95, 6) == 77237.718228
    assert round(hybrid_p95, 6) == 68472.506077
    assert all(row in lane_rows for row in slowest)
    assert ranked[5]["case_id"] == "aircargo-breach-notification-required-fields"
    assert max(prerank_size(row) for row in hybrid_rows) == 40


def test_capsule_renders_the_table_and_provenance_verbatim(published: dict[str, Any]) -> None:
    """The capsule embeds the table, every digest, and the ship blockers."""
    body = CAPSULE.read_text(encoding="utf-8")

    assert render_gr3_table(published) in body

    for name, (digest, _) in ARCHIVES.items():
        assert digest in body, name
    for value in (GRAPH_GENERATION_SHA256, CODE_COMMIT, OLLAMA_DIGEST, NLI_REVISION):
        assert value in body, value
    for input_hash in published["provenance"]["inputs"].values():
        assert input_hash in body, input_hash

    assert "297/300" in body
    for phrase in (
        "NO-SHIP",
        "0 approved",
        "not_evidence",
        "Score: 1.0",
        EXCLUDED_CASE,
        "unchanged",
        HOST,
    ):
        assert phrase in body, phrase
    assert "byte-identical" not in body
    assert "bit-identical" not in body
