"""Tests for scripts/rerank_score_capture.py (stdlib only, no torch/numpy/models)."""

import gzip
import hashlib
import json
import math

import pytest

from scripts import rerank_score_capture as capture


def _archive(tmp_path, rows):
    raw = json.dumps(rows, ensure_ascii=False).encode("utf-8")
    path = tmp_path / "pool.json.gz"
    path.write_bytes(gzip.compress(raw, mtime=0))
    return path, hashlib.sha256(raw).hexdigest()


def _row(case_id="c1", prerank=("a", "b", "c"), ranked=None, **extra):
    row = {
        "case_id": case_id,
        "query": "q",
        "rerank_k": 2,
        "prerank_cands": list(prerank),
        "cands": list(ranked) if ranked is not None else list(prerank),
    }
    row.update(extra)
    return row


def _sigmoid(values):
    return [1.0 / (1.0 + math.exp(-x)) for x in values]


class FakeReranker:
    def __init__(self, logits_by_text):
        self.logits_by_text = logits_by_text
        self.calls = []

    def predict(self, pairs, **kwargs):
        self.calls.append((pairs, kwargs))
        return [self.logits_by_text[text] for _, text in pairs]


def _code():
    return {"commit": "0" * 40, "tree_clean": True, "files": {}}


def test_load_pool_archive_returns_rows_and_digest(tmp_path):
    rows = [_row(), _row(case_id="c2")]
    path, digest = _archive(tmp_path, rows)
    assert capture.load_pool_archive(path, digest) == (rows, digest)


def test_load_pool_archive_rejects_invalid_archives(tmp_path):
    path, digest = _archive(tmp_path, [_row()])
    with pytest.raises(ValueError, match="sha256 mismatch"):
        capture.load_pool_archive(path, "0" * 64)
    missing = tmp_path / "missing.json.gz"
    with pytest.raises(ValueError, match="64 lowercase hex"):
        capture.load_pool_archive(missing, "not-hex")
    assert not missing.exists()
    path, digest = _archive(tmp_path, [_row(), _row()])
    with pytest.raises(ValueError, match="duplicate case_id"):
        capture.load_pool_archive(path, digest)
    path, digest = _archive(tmp_path, [_row(ranked=["a", "b", "d"])])
    with pytest.raises(ValueError, match="permutation of prerank_cands"):
        capture.load_pool_archive(path, digest)
    path, digest = _archive(tmp_path, [_row(prerank=())])
    with pytest.raises(ValueError, match="prerank_cands must be a non-empty"):
        capture.load_pool_archive(path, digest)
    path, digest = _archive(tmp_path, [_row(rerank_k=True)])
    with pytest.raises(ValueError, match="rerank_k"):
        capture.load_pool_archive(path, digest)
    path, digest = _archive(tmp_path, [])
    with pytest.raises(ValueError, match="non-empty list"):
        capture.load_pool_archive(path, digest)


def test_rerank_query_prefers_truthy_expanded_query():
    assert capture.rerank_query(_row(expanded_query="x")) == ("x", "expanded_query")
    assert capture.rerank_query(_row()) == ("q", "query")
    assert capture.rerank_query(_row(expanded_query=None)) == ("q", "query")
    assert capture.rerank_query(_row(expanded_query="")) == ("q", "query")


def test_probability_order_breaks_ties_by_original_position():
    assert capture.probability_order([0.5, 0.9, 0.5]) == [1, 0, 2]


def test_archive_order_assigns_lowest_unused_indices():
    assert capture.archive_order(["a", "b", "a"], ["a", "a", "b"]) == [0, 2, 1]
    with pytest.raises(ValueError, match="permutation of prerank"):
        capture.archive_order(["a", "b"], ["a", "a"])


def test_score_case_matches_archive_and_documents_predict_call():
    reranker = FakeReranker({"a": 1.0, "b": 3.0, "c": 2.0})
    activation = object()
    result = capture.score_case(
        reranker,
        _row(ranked=["b", "c", "a"]),
        batch_size=8,
        activation=activation,
        sigmoid=_sigmoid,
    )
    assert len(reranker.calls) == 1
    pairs, kwargs = reranker.calls[0]
    assert pairs == [("q", "a"), ("q", "b"), ("q", "c")]
    assert kwargs == {
        "batch_size": 8,
        "activation_fct": activation,
        "convert_to_numpy": True,
        "show_progress_bar": False,
    }
    assert result["logits"] == [1.0, 3.0, 2.0]
    assert result["probabilities"] == _sigmoid([1.0, 3.0, 2.0])
    assert result["fresh_order"] == [1, 2, 0]
    assert result["archive_order"] == [1, 2, 0]
    assert result["order_matches_archive"] is True
    assert result["top_k_matches_archive"] is True
    assert result["first_mismatch_rank"] is None
    assert result["rerank_query_field"] == "query"
    assert list(result) == [
        "case_id",
        "rerank_query_field",
        "n_candidates",
        "logits",
        "probabilities",
        "fresh_order",
        "archive_order",
        "order_matches_archive",
        "top_k",
        "top_k_matches_archive",
        "first_mismatch_rank",
        "mismatch_probability_gap",
        "seconds",
    ]


def test_score_case_reports_first_mismatch_and_top_k_difference():
    reranker = FakeReranker({"a": 1.0, "b": 3.0, "c": 2.0})
    result = capture.score_case(
        reranker,
        _row(ranked=["c", "b", "a"]),
        batch_size=4,
        activation=None,
        sigmoid=_sigmoid,
    )
    assert result["order_matches_archive"] is False
    assert result["first_mismatch_rank"] == 1
    assert result["mismatch_probability_gap"] > 0
    assert result["top_k_matches_archive"] is False
    result = capture.score_case(
        reranker,
        _row(rerank_k=1, ranked=["b", "a", "c"]),
        batch_size=4,
        activation=None,
        sigmoid=_sigmoid,
    )
    assert result["top_k_matches_archive"] is True
    assert result["order_matches_archive"] is False


def test_score_case_rejects_invalid_logits_and_probabilities():
    nan_reranker = FakeReranker({"a": float("nan"), "b": 3.0, "c": 2.0})
    with pytest.raises(ValueError, match="non-finite logit"):
        capture.score_case(
            nan_reranker,
            _row(),
            batch_size=4,
            activation=None,
            sigmoid=_sigmoid,
        )

    class Short:
        def predict(self, pairs, **kwargs):
            return [0.0] * (len(pairs) - 1)

    with pytest.raises(ValueError, match="logits"):
        capture.score_case(Short(), _row(), batch_size=4, activation=None, sigmoid=_sigmoid)

    with pytest.raises(ValueError, match="sigmoid returned invalid"):
        capture.score_case(
            FakeReranker({"a": 1.0, "b": 3.0, "c": 2.0}),
            _row(),
            batch_size=4,
            activation=None,
            sigmoid=lambda values: [1.5] * len(values),
        )


def test_build_scores_report_limit_log_and_full_parity(tmp_path):
    reranker = FakeReranker({"a": 1.0, "b": 3.0, "c": 2.0, "x": 5.0, "y": 1.0, "z": 3.0})
    rows = [
        _row(ranked=["b", "c", "a"]),
        _row(case_id="c2", prerank=("x", "y", "z"), ranked=["z", "x", "y"]),
    ]
    path, digest = _archive(tmp_path, rows)
    lines = []
    limited = capture.build_scores_report(
        rows=rows,
        pool_sha256=digest,
        archive_path=path,
        reranker=reranker,
        batch_size=8,
        activation=None,
        sigmoid=_sigmoid,
        environment={},
        code=_code(),
        limit=1,
        log=lines.append,
    )
    assert limited["complete"] is False
    assert limited["cases_scored"] == 1
    assert len(lines) == 1
    assert lines[0].startswith("[scores] 1/1 ")
    report = capture.build_scores_report(
        rows=rows,
        pool_sha256=digest,
        archive_path=path,
        reranker=reranker,
        batch_size=8,
        activation=None,
        sigmoid=_sigmoid,
        environment={},
        code=_code(),
        log=lines.append,
    )
    assert report["complete"] is True
    assert report["cases_total"] == 2
    assert report["cases_scored"] == 2
    assert report["parity"] == {
        "order_matches": 1,
        "top_k_matches": 1,
        "mismatched_case_ids": ["c2"],
    }
    assert list(report) == [
        "schema_version",
        "evidence_class",
        "complete",
        "cases_total",
        "cases_scored",
        "parity",
        "provenance",
        "timing",
        "per_case",
    ]
    assert report["provenance"]["pool_sha256"] == digest
    assert report["provenance"]["archive_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert report["timing"]["total_seconds"] == round(
        sum(case["seconds"] for case in report["per_case"]), 3
    )


def test_build_scores_report_rejects_invalid_arguments(tmp_path):
    rows = [_row()]
    path, digest = _archive(tmp_path, rows)

    def build(**overrides):
        settings = {
            "rows": rows,
            "pool_sha256": digest,
            "archive_path": path,
            "reranker": FakeReranker({}),
            "batch_size": 4,
            "activation": None,
            "sigmoid": _sigmoid,
            "environment": {},
            "code": _code(),
        }
        settings.update(overrides)
        return capture.build_scores_report(**settings)

    with pytest.raises(ValueError, match="limit"):
        build(limit=0)
    with pytest.raises(ValueError, match="batch_size"):
        build(batch_size=0)
    with pytest.raises(ValueError, match="batch_size"):
        build(batch_size=True)


def test_write_report_writes_once_and_rejects_nan(tmp_path):
    path = tmp_path / "reports" / "scores.json"
    report = {"schema_version": capture.SCHEMA_VERSION, "seconds": 0.123}
    capture.write_report(path, report)
    text = path.read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert not text.endswith("\n\n")
    assert json.loads(text) == report
    with pytest.raises(FileExistsError):
        capture.write_report(path, {"other": 1})
    assert path.read_text(encoding="utf-8") == text
    nan_path = tmp_path / "reports" / "nan.json"
    with pytest.raises(ValueError):
        capture.write_report(nan_path, {"bad": float("nan")})
    assert not nan_path.exists()


def test_main_refuses_existing_output_before_reading_archive(tmp_path):
    out = tmp_path / "report.json"
    out.write_text("keep\n", encoding="utf-8")
    code = capture.main(
        [
            "--archive",
            str(tmp_path / "missing.json.gz"),
            "--expected-sha256",
            "0" * 64,
            "--out",
            str(out),
        ]
    )
    assert code == 2
    assert out.read_text(encoding="utf-8") == "keep\n"
