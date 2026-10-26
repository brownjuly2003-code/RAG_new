"""The no-reranker point (docs/specs/no-rerank-point.md): the spec's frozen reading on hand-made
rows."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/no-rerank/tools/no_rerank_point.py"


def _load():
    spec = importlib.util.spec_from_file_location("no_rerank_point", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["no_rerank_point"] = module
    spec.loader.exec_module(module)
    return module


nr = _load()


def row(base, ranked, fused, expanded_ranked=None, expanded_fused=None, reproduced=True):
    first, second = nr.METRICS[base]

    def point(hit):
        return {first: float(hit), second: 1.0 if hit else 0.5}

    points = {"ranked": point(ranked), "fused": point(fused)}
    points["expanded_ranked"] = point(ranked if expanded_ranked is None else expanded_ranked)
    points["expanded_fused"] = point(fused if expanded_fused is None else expanded_fused)
    return {"base": base, "points": points, "expansion_reproduced": reproduced}


def test_mcnemar_is_the_exact_two_sided_binomial():
    assert nr.mcnemar(0, 0) == 1.0
    assert nr.mcnemar(5, 0) == pytest.approx(0.0625)
    assert nr.mcnemar(0, 5) == pytest.approx(0.0625)
    assert nr.mcnemar(10, 1) == pytest.approx(2 * 12 / 2**11)
    assert nr.mcnemar(3, 3) == 1.0


def test_the_reading_needs_both_a_direction_and_p_below_alpha():
    assert nr.reading(10, 1, nr.mcnemar(10, 1)) == "loss"
    assert nr.reading(1, 10, nr.mcnemar(1, 10)) == "gain"
    assert nr.reading(5, 0, nr.mcnemar(5, 0)) == "no detected difference"
    assert nr.reading(4, 4, nr.mcnemar(4, 4)) == "no detected difference"


def test_a_pair_counts_discordant_questions_read_at_both_points():
    rows = (
        [row("wixqa", True, False)] * 10
        + [row("wixqa", False, True)]
        + [row("wixqa", True, True)] * 3
        + [row("wixqa", False, False)] * 2
    )
    unread = row("wixqa", True, False)
    del unread["points"]["fused"]
    got = nr.pair([*rows, unread], "ranked", "fused")
    assert got["n"] == 16
    assert got["hits"] == {"ranked": 13, "fused": 4}
    assert (got["b_reranker_only"], got["c_fused_only"]) == (10, 1)
    assert got["reading"] == "loss"
    assert got["gold_articles"] == {"ranked": nr.mean([1.0] * 13 + [0.5] * 3), "fused": 0.625}


def test_a_pooled_pair_mixes_bases_by_each_ones_primary_metric_and_drops_the_second():
    rows = [row("wixqa", True, False), row("conditionalqa", False, True)]
    got = nr.pair(rows, "ranked", "fused")
    assert (got["b_reranker_only"], got["c_fused_only"]) == (1, 1)
    assert "gold_articles" not in got and "evidence_recall" not in got


def test_the_expanded_pair_reads_reproduced_questions_or_is_not_evidence():
    rows = [row("conditionalqa", True, True, True, False)] * 3
    rows += [row("conditionalqa", True, True, True, True, reproduced=False)]
    got = nr.pairs(rows, not_evidence=False)
    assert got["expanded"]["n"] == 3
    assert got["expanded"]["b_reranker_only"] == 3
    assert got["ranked"]["n"] == 4
    assert nr.pairs(rows, not_evidence=True)["expanded"] == nr.NOT_EVIDENCE


def _base(reading):
    return {"expanded": {"reading": reading}}


def test_the_decision_is_read_at_the_expanded_pair():
    keep = {b: _base("no detected difference") for b in nr.METRICS}
    assert nr.verdict(keep, _base("gain")) == nr.KEEP
    assert nr.verdict({**keep, "multihoprag": _base("loss")}, _base("no detected difference")) == (
        nr.EARNS
    )
    assert nr.verdict(keep, _base("loss")) == nr.EARNS
    assert nr.verdict({**keep, "wixqa": {"expanded": nr.NOT_EVIDENCE}}, _base("gain")) == (
        nr.NOT_EVIDENCE
    )
    assert nr.verdict(keep, {"expanded": nr.NOT_EVIDENCE}) == nr.NOT_EVIDENCE


def test_the_tool_reads_the_stand_and_settings_the_spec_names():
    spec = (ROOT / nr.SPEC).read_text(encoding="utf-8")
    assert "registered before the count" in spec
    assert nr.CODE_SHA.startswith("5e308fe") and "5e308fe" in spec
    assert set(nr.LABELS.values()) == {
        "p2-wixqa",
        "p2-conditionalqa",
        "p2-multihoprag",
        "p2-aircargo",
    }
    assert (nr.TOP, nr.ALPHA, nr.MAX_UNREPRODUCED) == (5, 0.05, 5)
    assert nr.EXPORT == ROOT / "reports/stage2/retrieval-20261021"
