"""Offline replay of the committed P1b expanded-cut report.

The pins run anywhere. Live-code file digests are pinned separately against the git
blobs at CODE_COMMIT. The whole-report rebuild ran against the live code until stage 1
changed the chunk header (docs/specs/stage1-fixes.md row 5): the live chunker no longer
writes the texts the record's pool holds, so the rebuild is a check of the record at its
own commit, ``REPLAY_AT_COMMIT`` below, and the live replay skips with that reason.
"""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts import p1_adaptive_k as p1
from scripts import p1b_expanded_cut as p1b
from tests import test_p1_adaptive_k_artifact as p1_artifact
from tests.capsule_prose import capsule_defects, numeric_claims, prose_lines

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports/p1b/p1b-expanded-cut.json"
CAPSULE = ROOT / "docs/evidence/p1b-expanded-cut.md"
INDEX = ROOT / "EVIDENCE_INDEX.md"
CORPUS_ENV = "P1B_CORPUS_DIR"
DEFAULT_CORPUS = ROOT.parent / "RAG_Support_Assistant" / "data" / "uploads" / "aircargo"
REPORT_SHA256 = "6f48bb1957f67235792edb926cf44c4894b56439c9fd423feb6529a7a791bc8b"
CODE_COMMIT = "d1adbbb727d788ce14b4c4dc8676a0bd20b36f86"
CORPUS_SHA256 = "c8562a64f88f72172f29e30865091be79f08d00ce65fbf675f34de64dcebe343"
CORPUS_FILES = 201
CHUNK_COUNT = 5589
DECISION = "NO_SHIP"
REPLAY_AT_COMMIT = (
    f"the record is rebuilt by the code it was measured with: at {CODE_COMMIT[:7]} run the "
    "capsule's reproduction commands; since stage 1 the live chunk header differs from the "
    "pool's, so a rebuild with the live code cannot give the record's bytes"
)


@pytest.fixture(scope="module")
def published():
    return json.loads(REPORT.read_text(encoding="utf-8"))


def _replay_corpus_dir() -> Path:
    configured = os.environ.get(CORPUS_ENV)
    corpus_dir = Path(configured) if configured else DEFAULT_CORPUS
    if not corpus_dir.is_dir():
        source = CORPUS_ENV if configured else "default"
        guidance = f"check {CORPUS_ENV}" if configured else f"set {CORPUS_ENV}"
        pytest.skip(
            f"corpus dir {corpus_dir.resolve()} (from {source}) is not a directory; "
            f"{guidance} or provide {DEFAULT_CORPUS}"
        )
    return corpus_dir


@pytest.fixture(scope="module")
def rebuilt(published):
    """The whole report, rebuilt once from the corpus — at the record's commit only."""
    pytest.skip(REPLAY_AT_COMMIT)


def test_missing_corpus_skip_names_selected_path_and_source(monkeypatch, tmp_path):
    missing = tmp_path / "missing-corpus"
    monkeypatch.setenv(CORPUS_ENV, str(missing))
    with pytest.raises(pytest.skip.Exception) as skipped:
        _replay_corpus_dir()
    assert str(missing.resolve()) in str(skipped.value)
    assert f"from {CORPUS_ENV}" in str(skipped.value)
    assert f"check {CORPUS_ENV}" in str(skipped.value)

    monkeypatch.delenv(CORPUS_ENV)
    monkeypatch.setitem(globals(), "DEFAULT_CORPUS", missing)
    with pytest.raises(pytest.skip.Exception) as skipped:
        _replay_corpus_dir()
    assert str(missing.resolve()) in str(skipped.value)
    assert "from default" in str(skipped.value)


def test_report_bytes_are_pinned(published):
    raw = REPORT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REPORT_SHA256
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")

    def reject_constant(value):
        raise ValueError(f"non-finite JSON constant: {value}")

    assert json.loads(raw, parse_constant=reject_constant) == published
    assert published["schema_version"] == p1b.SCHEMA_VERSION
    assert published["evidence_class"] == "measured"


def test_inputs_are_pinned(published):
    provenance = published["provenance"]
    p1_bytes = p1_artifact.REPORT.read_bytes()
    assert provenance["p1_report"]["sha256"] == p1_artifact.REPORT_SHA256
    assert hashlib.sha256(p1_bytes).hexdigest() == p1_artifact.REPORT_SHA256

    for pool_name, scores_path, scores_digest, pool_digest in (
        ("H", p1_artifact.H_SCORES, p1_artifact.H_SCORES_SHA256, p1.H_POOL_SHA256),
        ("Hm", p1_artifact.HM_SCORES, p1_artifact.HM_SCORES_SHA256, p1.HM_POOL_SHA256),
    ):
        pool = provenance["pools"][pool_name]
        assert pool["scores_sha256"] == scores_digest
        assert hashlib.sha256(scores_path.read_bytes()).hexdigest() == scores_digest
        assert pool["pool_sha256"] == pool_digest
        assert pool["scores_code_commit"] == p1_artifact.SCORES_CODE_COMMIT
        assert pool["reranker"]["model"] == p1_artifact.RERANKER
        assert pool["parity"]["mismatched_case_ids"] == []

    corpus = provenance["corpus"]
    manifest_bytes = p1b.CORPUS_MANIFEST_PATH.read_bytes()
    manifest = json.loads(manifest_bytes)
    assert corpus["manifest_sha256"] == hashlib.sha256(manifest_bytes).hexdigest()
    assert corpus["corpus_sha256"] == CORPUS_SHA256 == manifest["corpus_sha256"]
    assert corpus["file_count"] == CORPUS_FILES
    assert corpus["chunk_count"] == CHUNK_COUNT
    chunking = published["config"]["chunking"]
    assert chunking["semantic_chunking"] is False
    assert chunking["structural_chunking"] is True
    assert chunking["contextual_headers"] is True
    assert chunking["chunk_count"] == CHUNK_COUNT
    assert published["config"]["window"] == p1b.EXPANSION_WINDOW
    assert published["config"]["max_chars"] == p1b.EXPANSION_MAX_CHARS


def test_code_digests_are_the_blobs_at_the_measurement_commit(published):
    code = published["provenance"]["code"]
    assert code["commit"] == CODE_COMMIT
    assert code["tree_clean"] is True
    files = code["files"]
    assert list(files) == list(p1b.CODE_PATHS)
    for rel, digest in files.items():
        blob = subprocess.check_output(["git", "show", f"{CODE_COMMIT}:{rel}"], cwd=ROOT)
        assert b"\r\n" not in blob, rel
        assert hashlib.sha256(blob).hexdigest() == digest, rel


def test_rebuilt_report_equals_the_published_json(rebuilt, published):
    assert rebuilt == published


def test_unexpanded_selections_reproduce_p1(published):
    reproduction = published["reproduction"]
    assert reproduction["reproduces_p1"] is True
    p1_report = json.loads(p1_artifact.REPORT.read_bytes())
    assert list(reproduction["checks"]) == ["H", "Hm"]
    for pool_name, names in (
        ("H", ("top_k_5", "rel_0.2", "p1_cv")),
        ("Hm", ("top_k_5", "rel_0.2")),
    ):
        checks = reproduction["checks"][pool_name]
        assert list(checks) == list(names)
        for name, check in checks.items():
            assert check["equal"] is True
            assert check["expected"] == check["observed"]
            if name == "p1_cv":
                expected = p1_report["h"]["cross_validation"]["aggregate"]
            else:
                cells = p1_report[pool_name.lower()]["cells"]
                expected = next(cell["aggregate"] for cell in cells if cell["name"] == name)
            assert check["expected"] == expected


def test_verdict_follows_from_the_published_arms(published):
    config = published["config"]
    h = published["h"]["arms"]
    hm = published["hm"]["arms"]
    control = h[p1b.CONTROL_ARM]["aggregate"]
    floor = config["review_floor"]

    def reaches_floor(aggregate):
        return (
            aggregate["context_recall"] >= floor["context_recall"]
            and aggregate["FULL"] >= floor["FULL"]
            and aggregate["MISS"] <= floor["MISS"]
        )

    def preserves_coverage(aggregate, baseline):
        return (
            aggregate["context_recall"] >= baseline["context_recall"]
            and aggregate["FULL"] >= baseline["FULL"]
            and aggregate["MISS"] <= baseline["MISS"]
        )

    for arm_name in (p1b.PRIMARY_ARM, p1b.CV_ARM):
        aggregate = h[arm_name]["aggregate"]
        # P1 uses exact per-case sums; non-equal aggregate decimals keep these comparisons sound.
        assert aggregate["context_precision"] != config["precision_gate"]
        assert aggregate["context_recall"] != floor["context_recall"]
        assert aggregate["context_recall"] != control["context_recall"]

    primary = h[p1b.PRIMARY_ARM]
    cv = h[p1b.CV_ARM]
    hm_control = hm[p1b.CONTROL_ARM]["aggregate"]
    hm_primary = hm[p1b.PRIMARY_ARM]
    conditions = {
        "precision_gate_met": primary["aggregate"]["context_precision"] >= config["precision_gate"],
        "review_floor_met": reaches_floor(primary["aggregate"]),
        "coverage_and_facts_met": preserves_coverage(primary["aggregate"], control)
        and not primary["fact_losses"],
        "held_out_check_met": cv["aggregate"]["context_precision"] >= config["precision_gate"]
        and reaches_floor(cv["aggregate"])
        and preserves_coverage(cv["aggregate"], control)
        and not cv["fact_losses"],
        "hm_check_met": preserves_coverage(hm_primary["aggregate"], hm_control)
        and not hm_primary["fact_losses"],
    }
    verdict = published["verdict"]
    for name, expected in conditions.items():
        assert verdict[name] is expected
    expected_losses = {
        "H": {
            arm: [loss["case_id"] for loss in h[arm]["fact_losses"]]
            for arm in (p1b.PRIMARY_ARM, p1b.CV_ARM)
        },
        "Hm": {p1b.PRIMARY_ARM: [loss["case_id"] for loss in hm_primary["fact_losses"]]},
    }
    assert verdict["fact_loss_cases"] == expected_losses
    assert published["reproduction"]["reproduces_p1"] is True
    assert verdict["decision"] == DECISION
    assert (verdict["decision"] == "SHIP_CANDIDATE") is all(conditions.values())
    assert verdict["headline"] == "rel_0.2+exp against top_k_5+exp on H"


def test_arm_kept_counts_follow_the_frozen_rules(published):
    p1_report = json.loads(p1_artifact.REPORT.read_bytes())
    h_arms = published["h"]["arms"]
    hm_arms = published["hm"]["arms"]
    assert list(h_arms) == [
        p1b.CONTROL_ARM,
        p1b.PRIMARY_ARM,
        p1b.CV_ARM,
        p1b.DIAGNOSTIC_ARM,
    ]
    assert list(hm_arms) == [p1b.CONTROL_ARM, p1b.PRIMARY_ARM, p1b.DIAGNOSTIC_ARM]
    for arms, count in ((h_arms, 100), (hm_arms, 15)):
        for name, arm in arms.items():
            assert len(arm["kept_counts"]) == len(arm["per_case"]) == count
            assert arm["kept_counts"] == [row["kept"] for row in arm["per_case"]]
            if name == p1b.CONTROL_ARM:
                assert arm["kept_counts"] == [5] * count
                assert "comparison" not in arm and "fact_losses" not in arm
            else:
                assert "comparison" in arm and "fact_losses" in arm
            if name == p1b.DIAGNOSTIC_ARM:
                assert arm["kept_counts"] == [3] * count
    cv_cases = p1_report["h"]["cross_validation"]["per_case"]
    assert [row["case_id"] for row in h_arms[p1b.CV_ARM]["per_case"]] == [
        row["case_id"] for row in cv_cases
    ]
    assert h_arms[p1b.CV_ARM]["kept_counts"] == [row["kept"] for row in cv_cases]


def test_hm_primary_equals_the_control_by_construction(published):
    arms = published["hm"]["arms"]
    control = arms[p1b.CONTROL_ARM]
    primary = arms[p1b.PRIMARY_ARM]
    assert primary["kept_counts"] == [5] * 15
    for field in (
        "aggregate",
        "diagnostic_aggregate",
        "mean_context_chars",
        "expanded_document_total",
        "per_case",
    ):
        assert primary[field] == control[field]


def test_expanded_controls_match_q1(published):
    q1 = published["q1_comparison"]
    assert q1["rows"] == p1b.Q1_ROWS
    assert list(q1["checks"]) == ["prod", "k3"]
    for name, arm_name in (("prod", p1b.CONTROL_ARM), ("k3", p1b.DIAGNOSTIC_ARM)):
        check = q1["checks"][name]
        assert check["arm"] == arm_name
        assert check["equal"] is True
        expected = q1["rows"][name]
        observed = published["h"]["arms"][arm_name]["aggregate"]
        assert abs(observed["context_precision"] - expected["context_precision"]) <= 0.0001
        assert abs(observed["context_recall"] - expected["context_recall"]) <= 0.001
        for field in ("FULL", "PART", "MISS"):
            assert observed[field] == expected[field]


def test_capsule_embeds_the_table_and_the_digests(published):
    capsule = CAPSULE.read_text(encoding="utf-8")
    assert p1b.render_table(published) in capsule
    corpus = published["provenance"]["corpus"]
    for digest in (
        REPORT_SHA256,
        CODE_COMMIT,
        CORPUS_SHA256,
        p1_artifact.REPORT_SHA256,
        p1_artifact.H_SCORES_SHA256,
        p1_artifact.HM_SCORES_SHA256,
        p1.H_POOL_SHA256,
        p1.HM_POOL_SHA256,
        corpus["manifest_sha256"],
        p1_artifact.SCORES_CODE_COMMIT,
    ):
        assert digest in capsule
    for phrase in (
        DECISION,
        "pre-registered",
        "agent_labelled",
        "optimistic",
        "by construction",
        "not re-run",
    ):
        assert phrase in capsule


def test_reproduction_commands_use_a_plain_fence():
    section = CAPSULE.read_text(encoding="utf-8").split("## Reproduction\n", 1)[1]
    assert section.splitlines()[1:5] == [
        "```",
        "python -m scripts.p1b_expanded_cut --corpus <aircargo corpus dir>",
        "python -m pytest tests/test_p1b_expanded_cut_artifact.py -q -p no:cacheprovider",
        "```",
    ]


def test_capsule_says_all_intervals_are_conditional():
    capsule = CAPSULE.read_text(encoding="utf-8")
    limits = capsule.split("## Scope and limits\n", 1)[1].split("## Provenance\n", 1)[0]
    assert "All intervals are conditional on this case set" in limits


def _report_numbers(published) -> tuple[list[float], set[int]]:
    decimals = []
    integers = set()

    def collect(value):
        if isinstance(value, dict):
            # The capsule may state these named list counts, including verdict loss counts.
            for name in ("lost_keyword_cases", "full_regressions", "fact_losses"):
                if isinstance(value.get(name), list):
                    integers.add(len(value[name]))
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, float):
            decimals.append(value)
        elif isinstance(value, int) and not isinstance(value, bool):
            integers.add(value)

    def collect_loss_list_lengths(value):
        if isinstance(value, dict):
            for item in value.values():
                collect_loss_list_lengths(item)
        elif isinstance(value, list):
            integers.add(len(value))

    collect(published)
    collect_loss_list_lengths(published["verdict"]["fact_loss_cases"])
    return decimals, integers


def test_capsule_quotes_only_report_numbers(published):
    capsule = CAPSULE.read_text(encoding="utf-8")
    decimals, integers = _report_numbers(published)
    assert capsule_defects(capsule, decimals=decimals, integers=integers) == []
    claims = numeric_claims("\n".join(prose_lines(capsule)))
    assert sum("." in claim for claim in claims) >= 12


def test_capsule_number_check_rejects_an_unreported_number(published):
    capsule = CAPSULE.read_text(encoding="utf-8")
    decimals, integers = _report_numbers(published)
    assert "precision 0.5975" in "\n".join(prose_lines(capsule))
    tick = 5976
    while any(f"{abs(value):.4f}" == f"{tick / 10000:.4f}" for value in decimals):
        tick += 1
    unreported_decimal = f"{tick / 10000:.4f}"
    changed = capsule.replace("precision 0.5975", f"precision {unreported_decimal}", 1)
    defects = capsule_defects(changed, decimals=decimals, integers=integers)
    assert any(f"prose quotes {unreported_decimal}," in defect for defect in defects)

    unreported_integer = next(
        value for value in range(21, max(integers) + 2) if value not in integers
    )
    changed = capsule + f"\nThe unrelated count is {unreported_integer}.\n"
    defects = capsule_defects(changed, decimals=decimals, integers=integers)
    assert any(f"prose quotes {unreported_integer}," in defect for defect in defects)


def test_evidence_index_row_points_at_the_capsule_report_and_test(published):
    rows = [
        line
        for line in INDEX.read_text(encoding="utf-8").splitlines()
        if "docs/evidence/p1b-expanded-cut.md" in line
    ]
    assert len(rows) == 1
    row = rows[0]
    assert "reports/p1b/p1b-expanded-cut.json" in row
    assert "tests/test_p1b_expanded_cut_artifact.py" in row
    assert DECISION in row
    decimals, integers = _report_numbers(published)
    assert capsule_defects(row, decimals=decimals, integers=integers) == []
