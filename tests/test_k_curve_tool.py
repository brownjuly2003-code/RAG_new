"""The K curve after expansion (docs/specs/k-curve-expanded.md): the selection through the
product's fusion and rerank cut on a synthetic archive, the checks, and the frozen reading on
hand-made rows."""

from __future__ import annotations

import importlib.util
import inspect
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/k-curve/tools/k_curve.py"


def _load():
    spec = importlib.util.spec_from_file_location("k_curve", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["k_curve"] = module
    spec.loader.exec_module(module)
    return module


kc = _load()
nr = kc.nr
SETTINGS = {"retrieval_top_k": 20, "rrf_k": 60, "rrf_doc_key_chars": 200}
# A synthetic archive: sixty chunks, three to a document.
SOURCES = [f"doc-{i // 3}" for i in range(60)]
CHUNKS = [{"page_content": f"chunk {i}", "metadata": {"source": s}} for i, s in enumerate(SOURCES)]
VECTOR = list(range(20))
BM25 = list(range(10, 30))
SCORES = {m: m / 100 for m in range(30)}
# The gold of the WixQA case: doc-9, the chunks 27, 28 and 29.
CASE = {"gold_sources": ["doc-9"], "stratum": "s"}
PLACES = SimpleNamespace(
    source=SOURCES,
    members=lambda documents: [d["metadata"]["chunk_index"] for d in documents],
)


def expand(members):
    """A stand-in expansion that joins nothing: each seed alone, in its order."""
    return [{"metadata": {"chunk_index": m}, "text": f"chunk {m}"} for m in members]


def ident(member):
    return [SOURCES[member], member]


def record(**change):
    """A retrieval record of stage 2's form over VECTOR and BM25 whose K = 20 is the product's
    path."""
    top = kc.Selection(SETTINGS)(CHUNKS, VECTOR, BM25, SCORES, 20)
    out = {
        "case_id": "wixqa-0001",
        "index": 1,
        "reranker_ok": True,
        "lanes": {"vector": [ident(m) for m in VECTOR], "bm25": [ident(m) for m in BM25]},
        "pool": [[*ident(m), SCORES[m]] for m in top["pool"]],
        "ranked": [[*ident(m), s] for m, s in zip(top["five"], top["scores"], strict=True)],
        "expanded": [
            {"source": SOURCES[m], "chunk_index": m, "text": f"chunk {m}"} for m in top["five"]
        ],
    }
    out.update(change)
    return out


def ask(rec, places=PLACES):
    return kc.question("wixqa", CASE, rec, CHUNKS, places, expand, kc.Selection(SETTINGS))


def test_the_pool_at_k_is_the_products_fusion_of_each_lanes_first_k():
    select = kc.Selection(SETTINGS)
    top = select(CHUNKS, VECTOR, BM25, SCORES, 20)
    # Both lanes' 10 to 19 lead, then the vector lane's own, then BM25's.
    assert top["pool"] == [*range(10, 20), *range(10), *range(20, 30)]
    assert top["five"] == [29, 28, 27, 26, 25]
    assert top["scores"] == [0.29, 0.28, 0.27, 0.26, 0.25]
    five = select(CHUNKS, VECTOR, BM25, SCORES, 5)
    # Equal fused scores keep the order the fusion met them in: the vector lane's first.
    assert five["pool"] == [0, 10, 1, 11, 2, 12, 3, 13, 4, 14]
    assert five["five"] == [14, 13, 12, 11, 10]


def test_a_tie_in_the_five_falls_by_the_k_pools_order_as_the_product_breaks_it():
    import retrieval_summary

    # B (40) leads the vector lane; A (41), second there, is BM25's twelfth too, so at 20 the
    # fusion puts A before B, and within the first ten of each A is the vector lane's alone.
    vector = [40, 41, 42, 43, 44, 45, *range(14)]
    bm25 = [*range(20, 31), 41, *range(31, 39)]
    scores = dict.fromkeys({*vector, *bm25}, 0.01)
    scores.update({42: 0.9, 43: 0.8, 44: 0.7, 45: 0.6, 40: 0.5, 41: 0.5})
    select = kc.Selection(SETTINGS)
    top = select(CHUNKS, vector, bm25, scores, 20)
    assert top["five"] == [42, 43, 44, 45, 41]
    assert select(CHUNKS, vector, bm25, scores, 10)["five"] == [42, 43, 44, 45, 40]
    # Stage 2's curve breaks the tie by the 20-pool's order: the two rules differ here.
    stage2 = {
        "pool": [[*ident(m), scores[m]] for m in top["pool"]],
        "lanes": {"vector": [ident(m) for m in vector], "bm25": [ident(m) for m in bm25]},
    }
    curve, outside = retrieval_summary.k_curve(stage2)
    assert outside == 0
    assert [m for _, m in curve[10 - 1]] == [42, 43, 44, 45, 41]


@pytest.mark.parametrize("score", [None, math.nan, math.inf, "0.5", True])
def test_a_candidate_without_a_recorded_finite_score_stops_the_selection(score):
    with pytest.raises(ValueError, match="no recorded finite score"):
        kc.Selection(SETTINGS)(CHUNKS, VECTOR, BM25, {**SCORES, 3: score}, 5)


def test_a_candidate_without_a_recorded_score_stops_the_selection():
    missing = {m: s for m, s in SCORES.items() if m != 3}
    with pytest.raises(ValueError, match="no recorded finite score"):
        kc.Selection(SETTINGS)(CHUNKS, VECTOR, BM25, missing, 5)


def test_a_question_reads_every_k_before_and_after_the_expansion():
    row = ask(record())
    assert [e["k"] for e in row["curve"]] == list(kc.KS)
    # Each K's five are its pool's highest, K + 5 to K + 9; doc-9 is among them from K = 18.
    assert [e["candidates"] for e in row["curve"]] == [2 * k if k <= 10 else 10 + k for k in kc.KS]
    assert [e["same_five"] for e in row["curve"]] == [max(0, k - 15) for k in kc.KS]
    for entry in row["curve"]:
        hit = float(entry["k"] >= 18)
        want = {"gold_article": hit, "gold_articles": hit}
        assert (entry["ranked"], entry["expanded"]) == (want, want)
    gold = {"gold_article": 1.0, "gold_articles": 1.0}
    assert row["points"] == {"ranked": gold, "expanded_ranked": gold}
    assert (row["case_id"], row["stratum"], row["unresolved"]) == ("wixqa-0001", "s", None)


def test_a_question_without_gold_keeps_only_what_stands_beside():
    rec = record(case_id="aircargo-0001")
    row = kc.question("aircargo", None, rec, CHUNKS, None, None, kc.Selection(SETTINGS))
    assert set(row) == {"case_id", "base", "index", "reranker_ok", "curve"}
    assert row["curve"][0] == {"k": 5, "candidates": 10, "same_five": 0}
    assert row["curve"][-1] == {"k": 20, "candidates": 30, "same_five": 5}


def test_a_record_without_lanes_is_the_vector_lane_alone_as_the_product_runs_it():
    # BM25 found nothing: no fusion ran, and the pool is the vector lane in its order.
    top = sorted(VECTOR, key=lambda m: -SCORES[m])[:5]
    rec = record(
        case_id="aircargo-0002",
        lanes=None,
        pool=[[*ident(m), SCORES[m]] for m in VECTOR],
        ranked=[[*ident(m), SCORES[m]] for m in top],
    )
    row = kc.question("aircargo", None, rec, CHUNKS, None, None, kc.Selection(SETTINGS))
    assert [e["candidates"] for e in row["curve"]] == list(kc.KS)
    assert [e["same_five"] for e in row["curve"]] == [max(0, k - 15) for k in kc.KS]


@pytest.mark.parametrize(
    ("key", "how", "message"),
    [
        ("ranked", lambda r: [r[1], r[0], *r[2:]], "not the recorded pool and five"),
        ("ranked", lambda r: [[*r[0][:2], r[0][2] + 0.001], *r[1:]], "pool and five"),
        ("pool", lambda p: [p[1], p[0], *p[2:]], "not the recorded pool and five"),
        ("pool", lambda p: [[*x[:2], None] if x[1] == 3 else x for x in p], "finite score"),
        ("lanes", lambda la: {**la, "vector": [["doc-99", 0], *la["vector"][1:]]}, "no chunk"),
        ("expanded", lambda e: [{**e[0], "text": "chunk 28"}, *e[1:]], "not the recorded one"),
        ("pool", lambda p: [], "holds no pool"),
    ],
)
def test_k_20_must_be_the_recorded_path_or_nothing_is_read(key, how, message):
    rec = record()
    rec[key] = how(rec[key])
    with pytest.raises(SystemExit, match=message):
        ask(rec)


def test_a_k_whose_expansion_cannot_be_read_leaves_the_question_out_of_every_k():
    def members(documents):
        seeds = [d["metadata"]["chunk_index"] for d in documents]
        if 22 in seeds:
            raise ValueError("a chunk that is read has no place in its document")
        return seeds

    row = ask(record(), SimpleNamespace(source=PLACES.source, members=members))
    # K = 13's five, 18 to 22, are the first to hold the chunk 22.
    assert row["unresolved"] == 13
    assert all("ranked" in e and "expanded" not in e for e in row["curve"])


def test_k_20s_recorded_expansion_unread_stops_where_the_export_read_it():
    def members(documents):
        raise ValueError("a chunk that is read has no place in its document")

    with pytest.raises(SystemExit, match="where the export read it"):
        ask(record(), SimpleNamespace(source=PLACES.source, members=members))


def test_check_four_holds_every_k_before_the_expansion_to_the_exports_k_curve():
    row = ask(record())
    curve = [
        {"gold_article": float(k >= 18), "gold_articles": float(k >= 18)} for k in range(1, 21)
    ]
    exported = {"wixqa-0001": {"k_curve": curve, "k20_is_ranked": True}}
    # A row without gold is not held to the curve.
    kc.against_export([row, {"case_id": "aircargo-0001"}], exported)
    altered = [*curve[:12], {"gold_article": 1.0, "gold_articles": 1.0}, *curve[13:]]
    for changed in (
        {"k_curve": altered, "k20_is_ranked": True},
        {"k_curve": curve, "k20_is_ranked": False},
        {"k_curve": None, "k20_is_ranked": True},
    ):
        with pytest.raises(SystemExit, match="not stage 2's"):
            kc.against_export([row], {"wixqa-0001": changed})


def made(base, misses=(), unresolved=None, reranker_ok=True):
    """A hand-made row: the primary metric is a hit at every K but those in misses, before and
    after the expansion alike; an unresolved row has no point after it."""
    first, second = nr.METRICS[base]
    curve = []
    for k in kc.KS:
        hit = k not in misses
        point = {first: float(hit), second: 1.0 if hit else 0.5}
        entry = {"k": k, "candidates": 2 * k, "same_five": 5 if k == kc.KMAX else 3}
        entry["ranked"] = point
        if unresolved is None:
            entry["expanded"] = point
        curve.append(entry)
    return {
        "case_id": f"{base}-x",
        "base": base,
        "reranker_ok": reranker_ok,
        "points": {},
        "unresolved": unresolved,
        "curve": curve,
    }


def beside(base="aircargo"):
    curve = [{"k": k, "candidates": 2 * k, "same_five": 3} for k in kc.KS]
    return {"case_id": f"{base}-y", "base": base, "reranker_ok": False, "curve": curve}


def test_a_pair_sets_k_against_20_by_the_no_reranker_points_exact_mcnemar():
    rows = (
        [made("wixqa", misses={5})] * 10
        + [made("wixqa", misses={20})]
        + [made("wixqa")] * 3
        + [made("wixqa", misses={5, 20})] * 2
    )
    got = kc.pair(rows, 5, "expanded")
    assert got["n"] == 16
    assert got["hits"] == {"k20": 13, "k": 4}
    assert (got["b_k20_only"], got["c_k_only"]) == (10, 1)
    assert got["p"] == round(nr.mcnemar(10, 1), 6)
    assert got["reading"] == "loss"
    assert got["gold_articles"] == {"k20": nr.mean([1.0] * 13 + [0.5] * 3), "k": 0.625}
    six = kc.pair(rows, 6, "expanded")
    assert (six["b_k20_only"], six["c_k_only"], six["reading"]) == (0, 3, "no detected difference")


def test_a_base_reads_the_questions_read_at_every_k_and_more_than_five_unread_are_not_evidence():
    read = [made("conditionalqa", misses={5})] * 20
    unread = [made("conditionalqa", unresolved=7)] * 5
    got = kc.summary("conditionalqa", [*read, *unread, beside("conditionalqa")])
    assert (got["questions"], got["reranker_ok"], got["with_gold"], got["unresolved"]) == (
        26,
        25,
        25,
        5,
    )
    first, last = got["curve"][0], got["curve"][-1]
    assert (first["expanded"]["n"], first["ranked"]["n"]) == (20, 20)
    assert first["expanded"]["reading"] == "loss"
    assert first["candidates"] == {"n": 26, "min": 10, "median": 10, "p90": 10.0, "max": 10}
    assert first["same_five_mean"] == 3.0 and last["same_five_mean"] == nr.mean([5] * 25 + [3])
    # K = 20 is the side every K is read against, not a comparison.
    assert set(last) == {"k", "candidates", "same_five_mean"}
    over = kc.summary("conditionalqa", [*read, *unread, made("conditionalqa", unresolved=9)])
    assert over["unresolved"] == 6
    assert all(p["expanded"] == kc.NOT_EVIDENCE for p in over["curve"][:-1])
    assert over["curve"][0]["ranked"]["n"] == 20
    aircargo = kc.summary("aircargo", [beside(), beside()])
    assert set(aircargo) == {"questions", "reranker_ok", "curve"}
    assert all(set(p) == {"k", "candidates", "same_five_mean"} for p in aircargo["curve"])


def test_the_pooled_curve_reads_the_three_bases_by_each_ones_primary_metric():
    rows = [made("wixqa", misses={5})] * 6 + [made("multihoprag", misses={5})] * 6
    rows += [made("conditionalqa", unresolved=5)]
    got = kc.pooled_curve(rows, not_evidence=False)
    assert [p["k"] for p in got] == list(kc.KS[:-1])
    assert (got[0]["expanded"]["n"], got[0]["expanded"]["b_k20_only"]) == (12, 12)
    assert got[0]["expanded"]["reading"] == "loss"
    assert "gold_articles" not in got[0]["expanded"]
    assert got[1]["expanded"]["reading"] == "no detected difference"
    assert kc.pooled_curve(rows, not_evidence=True)[0]["expanded"] == kc.NOT_EVIDENCE


QUIET, LOSS, GAIN = (
    {"reading": "no detected difference"},
    {"reading": "loss"},
    {"reading": "gain"},
)


def _curves(**at):
    """Per base and pooled: at[where] maps a K below 20 to its expanded pair, else QUIET."""

    def curve(where):
        return [{"k": k, "expanded": at.get(where, {}).get(k, QUIET)} for k in kc.KS[:-1]]

    return {b: {"curve": [*curve(b), {"k": kc.KMAX}]} for b in nr.METRICS}, curve("pooled")


def _smallest(**at):
    return kc.decision(*_curves(**at))["smallest_k_without_a_detected_loss"]


def test_the_smallest_k_without_a_detected_loss_is_read_from_the_top():
    assert _smallest() == 5
    assert kc.decision(*_curves(wixqa={5: LOSS})) == {
        "smallest_k_without_a_detected_loss": 6,
        "losses": {"wixqa": [5], "conditionalqa": [], "multihoprag": [], "pooled": []},
    }
    # A loss on one base or pooled vetoes its K, and every K below it.
    assert _smallest(wixqa={5: LOSS}, pooled={8: LOSS}) == 9
    assert _smallest(multihoprag={19: LOSS}) == 20
    # A gain vetoes nothing.
    assert _smallest(conditionalqa={5: GAIN, 12: GAIN}) == 5
    assert kc.decision(*_curves(wixqa={11: kc.NOT_EVIDENCE})) == kc.NOT_EVIDENCE
    assert kc.decision(*_curves(pooled={5: kc.NOT_EVIDENCE})) == kc.NOT_EVIDENCE


def _runs(tmp_path, base, **settings):
    run = tmp_path / nr.LABELS[base]
    run.mkdir()
    (run / "effective_settings.json").write_text(
        json.dumps({"all": {**SETTINGS, **settings}}), encoding="utf-8"
    )
    return tmp_path


def test_the_lanes_must_be_of_twenty(tmp_path):
    with pytest.raises(SystemExit, match="not of 20"):
        kc.base_rows("aircargo", _runs(tmp_path, "aircargo", retrieval_top_k=10), tmp_path, {})


def test_the_no_reranker_loading_builds_this_points_rows_and_gets_its_question_back(
    tmp_path, monkeypatch
):
    # The no-reranker point's loading makes a row a record through its module's question().
    assert "question(base, cases.get(" in inspect.getsource(nr.base_rows)
    runs, original = _runs(tmp_path, "aircargo"), nr.question
    rec = record(case_id="aircargo-0001")

    def loading(base, runs, root, manifest):
        row = nr.question(base, None, rec, CHUNKS, None, None)
        return [row], {"label": nr.LABELS[base], "settings": {"rrf_k": 60}}, set(), []

    monkeypatch.setattr(nr, "base_rows", loading)
    monkeypatch.setattr(nr, "export_rows", lambda label, manifest: {})
    rows, provenance, _, _ = kc.base_rows("aircargo", runs, tmp_path, {})
    assert nr.question is original
    assert rows[0]["curve"][-1] == {"k": 20, "candidates": 30, "same_five": 5}
    assert provenance["settings"] == {"rrf_k": 60, "retrieval_top_k": 20, "rrf_doc_key_chars": 200}

    def failing(base, runs, root, manifest):
        raise SystemExit("a check of the no-reranker point")

    monkeypatch.setattr(nr, "base_rows", failing)
    with pytest.raises(SystemExit):
        kc.base_rows("aircargo", runs, tmp_path, {})
    assert nr.question is original


def test_main_writes_ids_flags_and_numbers_and_refuses_a_record_with_text(tmp_path, monkeypatch):
    rows = {
        "wixqa": [made("wixqa", misses={5})] * 8 + [made("wixqa")] * 4,
        "conditionalqa": [made("conditionalqa")] * 3,
        "multihoprag": [made("multihoprag")] * 3,
        "aircargo": [beside()] * 2,
    }

    def loading(base, runs, root, manifest):
        provenance = {"label": nr.LABELS[base], "settings": {}}
        return rows[base], provenance, {"doc-1"}, ["What does chunk 1 say?"]

    monkeypatch.setattr(kc, "base_rows", loading)
    out = tmp_path / "out"
    assert kc.main(["runs", "data", str(out)]) == 0
    got = json.loads((out / "record.json").read_text(encoding="utf-8"))
    assert (got["spec"], got["stand_code_sha"], got["ks"]) == (kc.SPEC, nr.CODE_SHA, list(kc.KS))
    assert set(got["measure_code_sha256"]) == set(kc.MEASURE_CODE)
    assert got["decision"] == {
        "smallest_k_without_a_detected_loss": 6,
        "losses": {"wixqa": [5], "conditionalqa": [], "multihoprag": [], "pooled": [5]},
    }
    assert len((out / "rows.jsonl").read_text(encoding="utf-8").splitlines()) == 20
    rows["aircargo"] = [{**beside(), "case_id": "doc-1"}]
    with pytest.raises(SystemExit, match="refused"):
        kc.main(["runs", "data", str(tmp_path / "refused")])
    assert not (tmp_path / "refused").exists()


def test_the_tool_measures_what_the_spec_registers():
    spec = (ROOT / kc.SPEC).read_text(encoding="utf-8")
    for phrase in (
        "registered before the count",
        "Forecast, written before the count",
        "The smallest K without a detected loss",
        "5e308fe",
    ):
        assert phrase in spec, phrase
    assert (kc.KS, kc.KMAX, kc.MAX_UNREAD, nr.TOP) == (tuple(range(5, 21)), 20, 5, 5)
    assert kc.OUT == ROOT / "reports/k-curve/5e308fe"
    assert set(nr.MEASURE_CODE) < set(kc.MEASURE_CODE)
    assert all((ROOT / name).is_file() for name in kc.MEASURE_CODE)
