"""MultiHop-RAG's retrieval by the official rule (docs/specs/multihop-official-retrieval.md): the
copied calculate_metrics on the rule's edge cases, the lists the tool builds and the frozen
reading, on synthetic rows."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/multihop-official/tools/multihop_official.py"


def _load():
    spec = importlib.util.spec_from_file_location("multihop_official", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["multihop_official"] = module
    spec.loader.exec_module(module)
    return module


mo = _load()


@pytest.fixture(autouse=True)
def _stage2_tools_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tool imports judge_export when a test asks for clusters or intervals; a test module
    that ends earlier, tests/test_judge_export.py, takes reports/stage2/tools off sys.path."""
    monkeypatch.syspath_prepend(str(ROOT / "reports" / "stage2" / "tools"))


FILLER = "filler text"
ZERO = {"Hits@10": 0.0, "Hits@4": 0.0, "MAP@10": 0.0, "MRR@10": 0.0}
ONE = {"Hits@10": 1.0, "Hits@4": 1.0, "MAP@10": 1.0, "MRR@10": 1.0}
# A synthetic pool of twelve chunks in fused order, each with its reranker score.
SCORES = [0.1, 0.9, 0.5, 0.7, 0.3, 0.8, 0.2, 0.6, 0.4, 0.05, 0.95, 0.65]
ORDER = [10, 1, 5, 3, 11, 7, 2, 8, 4, 6, 0, 9]


def scores(retrieved, gold):
    return mo.calculate_metrics([retrieved], [gold])


def test_a_hit_at_four_needs_a_fact_among_the_first_four():
    at_four = scores([FILLER] * 3 + ["fact a"], ["fact a"])
    assert at_four == {"Hits@10": 1.0, "Hits@4": 1.0, "MAP@10": 0.25, "MRR@10": 0.25}
    at_five = scores([FILLER] * 4 + ["fact a"], ["fact a"])
    assert at_five == {"Hits@10": 1.0, "Hits@4": 0.0, "MAP@10": 0.2, "MRR@10": 0.2}


def test_rank_ten_counts_and_rank_eleven_never():
    tenth = scores([FILLER] * 9 + ["fact a"], ["fact a"])
    assert (tenth["Hits@10"], tenth["Hits@4"], tenth["MRR@10"]) == (1.0, 0.0, 0.1)
    assert tenth["MAP@10"] == pytest.approx(0.1)
    for depth in (10, 11, 15):
        assert scores([FILLER] * depth + ["fact a"], ["fact a"]) == ZERO


def test_any_one_fact_of_several_is_a_hit():
    one = scores([FILLER, "fact b"], ["fact a", "fact b", "fact c"])
    assert (one["Hits@4"], one["Hits@10"], one["MRR@10"]) == (1.0, 1.0, 0.5)
    assert one["MAP@10"] == pytest.approx(0.5 / 3)


def test_the_match_is_case_sensitive_and_drops_only_spaces_and_newlines():
    assert scores(["xx Alpha\n Beta yy"], ["Alpha Beta"])["Hits@4"] == 1.0
    assert scores(["AlphaBeta"], ["Al pha\nBe ta"])["Hits@4"] == 1.0
    for text in ("alpha beta", "Alpha\tBeta", "Alpha\r\nBeta", "Alpha Beta", "Alpha-Beta"):
        assert scores([text], ["Alpha Beta"])["Hits@4"] == 0.0
    assert mo.normalise(" a\tb\r\n c d ") == "a\tb\rc d"


def test_a_fact_split_between_two_texts_is_not_found():
    assert scores(["one half of", "a fact"], ["one half of a fact"]) == ZERO


def test_map_counts_a_fact_once_at_the_first_text_that_holds_it():
    again = scores(["fact a", "fact a", "fact b"], ["fact a", "fact b"])
    assert again["MAP@10"] == pytest.approx((1 / 1 + 0 / 2 + 1 / 3) / 2)
    assert again["MRR@10"] == 1.0


def test_two_facts_in_one_text_add_two_over_its_rank():
    both = scores([FILLER, FILLER, "fact a and fact b"], ["fact a", "fact b"])
    assert both["MAP@10"] == pytest.approx((2 / 3) / 2)
    assert both["MRR@10"] == pytest.approx(1 / 3)


def test_a_repeated_fact_is_found_once_and_divides_twice():
    assert scores(["fact a"], ["fact a", "fact a"])["MAP@10"] == 0.5
    assert scores(["fact a"], ["fact a", "fact  a"])["MAP@10"] == 0.5


def test_the_divisor_stops_at_ten_facts():
    facts = [f"fact {n}" for n in range(12)]
    assert scores([" ".join(facts)], facts)["MAP@10"] == pytest.approx(1.2)
    assert scores([" ".join(facts[:5])], facts)["MAP@10"] == pytest.approx(0.5)


def test_mrr_is_one_over_the_first_relevant_rank():
    late = scores([FILLER, FILLER, "fact a", "fact b"], ["fact a", "fact b"])
    assert late["MRR@10"] == pytest.approx(1 / 3)
    assert late["MAP@10"] == pytest.approx((1 / 3 + 1 / 4) / 2)


def test_over_questions_each_number_is_the_plain_mean():
    retrieved = [["fact a"], [FILLER] * 5 + ["fact b"]]
    gold = [["fact a"], ["fact b"]]
    whole = mo.calculate_metrics(retrieved, gold)
    assert (whole["Hits@10"], whole["Hits@4"]) == (1.0, 0.5)
    assert whole["MRR@10"] == pytest.approx((1 + 1 / 6) / 2)
    assert whole["MAP@10"] == pytest.approx((1 + 1 / 6) / 2)
    alone = [mo.calculate_metrics([r], [g]) for r, g in zip(retrieved, gold, strict=True)]
    for metric in mo.METRICS:
        assert sum(a[metric] for a in alone) / 2 == pytest.approx(whole[metric])


def test_an_empty_list_scores_zero_and_an_empty_gold_list_cannot_be_read():
    assert scores([], ["fact a"]) == ZERO
    with pytest.raises(ZeroDivisionError):
        scores(["fact a"], [])
    with pytest.raises(ZeroDivisionError):
        mo.calculate_metrics([], [])


def test_an_empty_or_blank_fact_matches_every_text():
    for blank in ("", " ", " \n "):
        assert scores([FILLER], [blank]) == ONE


def test_main_eval_skips_null_queries_before_it_reads_their_lists():
    null = {"question_type": mo.NULL_QUERY, "retrieval_list": [], "gold_list": []}
    kept = {
        "question_type": "inference_query",
        "retrieval_list": [{"text": FILLER}, {"text": "fact a"}],
        "gold_list": [{"fact": "fact a"}],
    }
    assert mo.official_eval([null, kept, null]) == scores([FILLER, "fact a"], ["fact a"])
    assert mo.official_eval([null]) is None


def test_the_numbers_print_as_main_eval_prints_them():
    printed = mo.printed({"Hits@4": 2 / 3, "MAP@10": 0.25})
    assert printed == {"Hits@4": "0.6667", "MAP@10": "0.2500"}


def test_the_substring_diagnostic_counts_distinct_facts_whole_in_the_first_k():
    texts = ["fact a", FILLER, "fact b"]
    gold = ["fact a", "fact  a", "fact b", "fact c"]
    assert mo.distinct_facts(gold) == ["facta", "factb", "factc"]
    assert [mo.substring_found(texts, gold, k) for k in (1, 2, 3, 10)] == [1, 1, 2, 2]


def test_the_reranker_order_keeps_ties_in_fused_order_and_puts_no_score_last():
    pool = [["a", 0, 0.5], ["b", 1, 0.9], ["c", 2, 0.5], ["d", 3, None], ["e", 4, 0.9]]
    pool.append(["f", 5, -1.0])
    order = [["b", 1], ["e", 4], ["a", 0], ["c", 2], ["f", 5], ["d", 3]]
    assert mo.reranker_order(pool) == order


def chunks():
    return [
        {"page_content": f"header {i}\nbody {i}", "metadata": {"source": f"doc-{i % 3}.md"}}
        for i in range(len(SCORES))
    ]


def record(case_id, archive, size=len(SCORES)):
    pool = [[archive[i]["metadata"]["source"], i, SCORES[i]] for i in range(size)]
    ranked = sorted(pool, key=lambda p: p[2], reverse=True)[:5]
    expanded = [{"source": r[0], "chunk_index": r[1], "text": f"expanded {r[1]}"} for r in ranked]
    return {
        "case_id": case_id,
        "lanes": None,
        "pool": pool,
        "reranker_ok": True,
        "ranked": ranked,
        "expanded": expanded,
    }


def test_the_first_ten_are_the_scored_pool_in_the_reranker_order_from_the_kept_five():
    archive = chunks()
    full = record("multihoprag-0001", archive)
    assert [ident[1] for ident in mo.first_ten(full)] == ORDER[:10]
    assert len(mo.first_ten(record("multihoprag-0001", archive, size=7))) == 7
    unscored = full["pool"][:-1] + [[*full["pool"][-1][:2], None]]
    for change in (
        {"reranker_ok": False},
        {"pool": []},
        {"pool": unscored},
        {"ranked": full["ranked"][1:] + full["ranked"][:1]},
    ):
        with pytest.raises(SystemExit):
            mo.first_ten({**full, **change})


def test_the_pinned_file_is_held_to_its_registered_size_and_sha(tmp_path):
    rows = [{"query": "synthetic question", "question_type": mo.NULL_QUERY, "evidence_list": []}]
    data = json.dumps(rows).encode("utf-8")
    path = tmp_path / mo.RAW_FILE
    path.write_bytes(data)
    entry = {"path": mo.RAW_FILE, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    registered = {"bases": {mo.BASE: {"files": [{"path": "corpus.json"}, entry]}}}
    assert mo.pinned_rows(path, registered) == (rows, entry)
    for wrong in ({"bytes": len(data) + 1}, {"sha256": "0" * 64}):
        other = {"bases": {mo.BASE: {"files": [{**entry, **wrong}]}}}
        with pytest.raises(SystemExit, match="NOT_EVIDENCE"):
            mo.pinned_rows(path, other)


def pinned():
    evidence = [
        {"url": "u1", "fact": "fact a"},
        {"url": "u2", "fact": "fact b"},
        {"url": "u1", "fact": "fact a"},
    ]
    return [
        {"query": "synthetic question zero", "question_type": mo.NULL_QUERY, "evidence_list": []},
        {
            "query": "synthetic question one",
            "question_type": "inference_query",
            "evidence_list": evidence,
        },
    ]


def cases():
    return {
        "multihoprag-0000": {
            "case_id": "multihoprag-0000",
            "query": "synthetic question zero",
            "stratum": mo.NULL_QUERY,
            "evidence_groups": [],
            "unresolved_evidence": 0,
        },
        "multihoprag-0001": {
            "case_id": "multihoprag-0001",
            "query": "synthetic question one",
            "stratum": "inference_query",
            "evidence_groups": [{"alternatives": []}, {"alternatives": []}],
            "unresolved_evidence": 0,
        },
    }


def test_a_case_takes_its_row_of_the_pinned_file_and_its_facts_as_they_stand():
    rows, by_id = pinned(), cases()
    facts = ["fact a", "fact b", "fact a"]
    assert mo.gold_facts(by_id["multihoprag-0001"], rows) == (1, "inference_query", facts)
    assert mo.gold_facts(by_id["multihoprag-0000"], rows) == (0, mo.NULL_QUERY, [])
    placed_one = {"evidence_groups": [{"alternatives": []}], "unresolved_evidence": 1}
    assert mo.gold_facts({**by_id["multihoprag-0001"], **placed_one}, rows)[2] == facts
    for change in (
        {"query": "another synthetic question"},
        {"stratum": mo.NULL_QUERY},
        {"unresolved_evidence": 1},
    ):
        with pytest.raises(SystemExit):
            mo.gold_facts({**by_id["multihoprag-0001"], **change}, rows)


def test_the_official_input_is_the_reranker_order_of_chunk_texts_in_the_pinned_order():
    archive, rows, by_id = chunks(), pinned(), cases()
    kept, null = record("multihoprag-0001", archive), record("multihoprag-0000", archive, size=6)
    exported = {r["case_id"]: {"pool": mo.pool_ranks(r["lanes"], r["pool"])} for r in (kept, null)}
    data = mo.entries([kept, null], by_id, archive, rows, exported)
    assert [e["case_id"] for e in data] == ["multihoprag-0000", "multihoprag-0001"]
    first, second = data
    assert first["question_type"] == mo.NULL_QUERY
    assert first["members"] == first["retrieval_list"] == first["expanded_list"] == []
    assert first["gold_list"] == []
    texts = [archive[i]["page_content"] for i in ORDER[:10]]
    assert second["members"] == ORDER[:10]
    assert [m["text"] for m in second["retrieval_list"]] == texts
    assert [m["text"] for m in second["expanded_list"]] == [f"expanded {i}" for i in ORDER[:5]]
    assert [m["fact"] for m in second["gold_list"]] == ["fact a", "fact b", "fact a"]
    assert mo.official_eval(data) == mo.calculate_metrics([texts], [["fact a", "fact b", "fact a"]])
    moved = {**exported, "multihoprag-0000": {"pool": exported["multihoprag-0000"]["pool"][::-1]}}
    with pytest.raises(SystemExit):
        mo.entries([kept, null], by_id, archive, rows, moved)


def fake_read_gold(base, case, members, places):
    """Stage 2's two metrics as if each evidence group stood in one chunk, case["need"]."""
    if places == "unplaced" and len(members) > 5:
        raise ValueError("a chunk that is read has no place in its document")
    held = [m for m in case["need"] if m in members]
    return {
        "all_evidence_coverage": float(len(held) == len(case["need"])),
        "evidence_recall": len(held) / len(case["need"]),
    }


def test_a_question_row_holds_both_lists_numbers_and_stage_2s_metrics(monkeypatch):
    from scripts import external_pilot

    monkeypatch.setattr(external_pilot, "read_gold", fake_read_gold)
    texts = [FILLER, "fact a here"] + [FILLER] * 5 + ["and fact b", FILLER, FILLER]
    facts = ["fact a", "fact b", "fact a"]
    entry = {
        "case_id": "multihoprag-0001",
        "raw_index": 1,
        "question_type": "inference_query",
        "members": list(range(20, 30)),
        "retrieval_list": [{"text": text} for text in texts],
        "expanded_list": [{"text": "fact b, expanded"}, {"text": FILLER}],
        "gold_list": [{"fact": fact} for fact in facts],
    }
    case = {"need": [21, 27], "evidence_groups": [{"alternatives": []}, {"alternatives": []}]}
    exported = {"points": {"ranked": {"all_evidence_coverage": 0.0, "evidence_recall": 0.5}}}
    row = mo.question(entry, case, None, exported)
    assert row["official"] == mo.calculate_metrics([texts], [facts])
    assert row["official"]["MAP@10"] == pytest.approx((1 / 2 + 1 / 8) / 3)
    assert (row["facts"], row["distinct"], row["facts_empty"], row["groups"]) == (3, 2, 0, 2)
    assert (row["listed"], row["evaluated"], row["stratum"]) == (10, True, "inference_query")
    assert row["substring_found"] == {"@4": 1, "@10": 2}
    assert row["range"]["@4"] == {"all_evidence_coverage": 0.0, "evidence_recall": 0.5}
    assert row["range"]["@10"] == {"all_evidence_coverage": 1.0, "evidence_recall": 1.0}
    assert row["official_expanded"]["MRR@10"] == 1.0
    with pytest.raises(SystemExit, match="recount"):
        mo.question(entry, case, None, {"points": {"ranked": row["range"]["@10"]}})
    with pytest.raises(SystemExit, match="no place"):
        mo.question(entry, case, "unplaced", exported)


def hand(case, hits, found, ranges):
    """A row of question() by hand: the official Hits@4 and Hits@10; how many of two distinct
    facts stand whole in the first 4 and 10; stage 2's (evidence_recall, all_evidence_coverage)
    at 4 and 10."""
    official = {
        "Hits@10": float(hits[1]),
        "Hits@4": float(hits[0]),
        "MAP@10": 0.25 * hits[1],
        "MRR@10": 0.5 * hits[1],
    }
    return {
        "case_id": case,
        "official": official,
        "official_expanded": official,
        "distinct": 2,
        "substring_found": {"@4": found[0], "@10": found[1]},
        "range": {
            at: {"evidence_recall": recall, "all_evidence_coverage": whole}
            for at, (recall, whole) in zip(("@4", "@10"), ranges, strict=True)
        },
    }


ROWS = [
    hand("c1", (1, 1), (2, 2), ((1.0, 1.0), (1.0, 1.0))),
    hand("c2", (1, 1), (1, 1), ((0.0, 0.0), (0.5, 0.0))),
    hand("c3", (0, 1), (0, 1), ((0.5, 0.0), (0.5, 0.0))),
    hand("c4", (0, 0), (0, 0), ((0.0, 0.0), (0.0, 0.0))),
]
FAMILIES = {"c1": ["cluster:0"], "c2": ["cluster:0"], "c3": ["cluster:1"], "c4": ["cluster:2"]}
HITS = ("substring_any", "substring_all", "range_any", "range_all")


def test_discordant_questions_part_the_two_matchings_at_four():
    assert mo.discordant(ROWS) == {"substring_only": 1, "range_only": 1}


def test_beside_counts_any_and_all_by_both_matchings_at_each_k():
    out = mo.beside(ROWS, FAMILIES)
    assert {name: out["@4"][name]["hits"] for name in HITS} == dict(
        zip(HITS, (2, 1, 2, 1), strict=True)
    )
    assert {name: out["@10"][name]["hits"] for name in HITS} == dict(
        zip(HITS, (3, 1, 3, 1), strict=True)
    )
    assert out["@4"]["evidence_recall"]["mean"] == pytest.approx(0.375)
    assert out["@10"]["evidence_recall"]["mean"] == pytest.approx(0.5)
    for entry in out["@4"].values():
        assert (entry["n"], entry["clusters"]) == (4, 3) and entry["read95"]


def test_a_share_reads_the_wider_interval_and_a_mean_its_clusters():
    share = mo.interval({"c1": 1, "c2": 1, "c3": 0, "c4": 1}, FAMILIES, True)
    wider = max((share["wilson95"], share["cluster95"]), key=lambda span: span[1] - span[0])
    assert (share["n"], share["hits"], share["share"], share["read95"]) == (4, 3, 0.75, wider)
    mean = mo.interval({"c1": 0.5, "c2": 1.0, "c3": 0.0, "c4": 0.5}, FAMILIES, False)
    assert (mean["n"], mean["mean"], mean["clusters"]) == (4, 0.5, 3)
    assert mean["read95"] == mean["cluster95"]


def test_the_official_numbers_carry_intervals_and_the_frozen_reading():
    metrics = {"Hits@10": 0.75, "Hits@4": 0.5, "MAP@10": 0.1875, "MRR@10": 0.375}
    out = mo.official_numbers(metrics, ROWS, "official", FAMILIES, True)
    assert out["printed"] == {
        "Hits@10": "0.7500",
        "Hits@4": "0.5000",
        "MAP@10": "0.1875",
        "MRR@10": "0.3750",
    }
    assert out["intervals"]["Hits@4"]["hits"] == 2
    assert out["intervals"]["MAP@10"]["mean"] == 0.1875
    for metric in mo.METRICS:
        read95 = out["intervals"][metric]["read95"]
        assert out["readings"][metric] == mo.reading(read95, mo.band(metric))
    assert "readings" not in mo.official_numbers(
        metrics, ROWS, "official_expanded", FAMILIES, False
    )


def test_the_clusters_join_questions_that_share_a_gold_document():
    families = mo.families_of(
        [
            {"case_id": "c1", "gold_sources": ["d1"]},
            {"case_id": "c2", "gold_sources": ["d1", "d2"]},
            {"case_id": "c3", "gold_sources": ["d2"]},
            {"case_id": "c4", "gold_sources": ["d3"]},
        ]
    )
    assert families["c1"] == families["c2"] == families["c3"] != families["c4"]
    assert all(len(f) == 1 and f[0].startswith("cluster:") for f in families.values())


def test_stage_2s_own_points_are_read_from_the_export():
    def point(whole, recall):
        return {"all_evidence_coverage": whole, "evidence_recall": recall}

    exported = {
        "c1": {"points": {name: point(1.0, 1.0) for name in mo.POINTS}},
        "c2": {
            "points": {
                "ranked": point(0.0, 0.5),
                "expanded": point(0.0, 0.0),
                "sent": point(0.0, 0.5),
            }
        },
        "c9": {"points": {}},
    }
    out = mo.committed_points(exported, ["c1", "c2"])
    assert out["ranked"] == {"n": 2, "all_evidence": 1, "any_evidence": 2, "evidence_recall": 0.75}
    assert out["expanded"] == {"n": 2, "all_evidence": 1, "any_evidence": 1, "evidence_recall": 0.5}


def test_the_bands_are_the_published_rows():
    assert (len(mo.PAPER), len(mo.SCRIPT)) == (4, 2)
    assert mo.band("Hits@4") == (0.6169, 0.6661)
    assert mo.band("Hits@10") == (0.7059, 0.749)
    assert mo.band("MRR@10") == (0.5477, 0.6029)
    assert mo.band("MAP@10") == (0.2619, 0.2687)


def test_a_reading_needs_the_whole_interval_past_the_band():
    band = mo.band("Hits@4")
    assert mo.reading([0.6662, 0.9], band) == mo.ABOVE
    assert mo.reading([0.6661, 0.9], band) == mo.APART
    assert mo.reading([0.3, 0.6168], band) == mo.BELOW
    assert mo.reading([0.3, 0.6169], band) == mo.APART
    assert mo.reading([0.5, 0.7], band) == mo.APART


def test_the_tool_names_the_rule_the_stand_and_the_lists_the_spec_registers():
    spec = (ROOT / mo.SPEC).read_text(encoding="utf-8")
    assert "registered before the count" in spec
    assert mo.OFFICIAL["commit"] == "c1c1287aa60a94acf9c4d20c891c9cd611a0f6e8"
    for value in (mo.OFFICIAL["commit"], mo.OFFICIAL["sha256"], "5e308fe", mo.OFFICIAL["path"]):
        assert value in spec
    assert mo.CODE_SHA.startswith("5e308fe") and mo.LABEL == "p2-multihoprag"
    assert (mo.KS, mo.DEPTH, mo.TOP, mo.WITH_GOLD) == ((4, 10), 10, 5, 70)
    assert mo.METRICS == ("Hits@10", "Hits@4", "MAP@10", "MRR@10")
    assert mo.EXPORT == ROOT / "reports/stage2/retrieval-20261021"
    for metric in mo.METRICS:
        assert all(f"{value:.4f}" in spec for value in mo.band(metric))
    for word in (mo.ABOVE, mo.BELOW, mo.APART):
        assert f"«{word}»" in spec
