"""Stage 7, step 1 (docs/specs/stage7-step1-arms-m3.md): the arms H, S and P through the
product's retrievers on a synthetic archive, the parity gate and its one-byte refusals, the
M3 pairs at their edges, gate G1, the context-judge plan and its read-back, and what the spec
freezes."""

from __future__ import annotations

import copy
import functools
import hashlib
import importlib.util
import json
import math
import re
import sys
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/stage7/tools/arms_replay.py"


def _load():
    spec = importlib.util.spec_from_file_location("arms_replay", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["arms_replay"] = module
    spec.loader.exec_module(module)
    return module


ar = _load()
nr = ar.nr


def piece(source, headings, body, seam=0):
    """A chunk as the chunker writes it: its header line first, the seam it recorded."""
    header = " › ".join([source, *headings])
    metadata = {"source": source, "contextual_header": header, "seam_overlap": seam}
    metadata.update(zip(("h1", "h2"), headings, strict=False))
    return {"page_content": f"[{header}]\n{body}", "metadata": metadata}


# A synthetic archive: i.md, a lone chunk; a.md, five chunks of Rules (1-3 cut over two
# seams, of 20 and 19 characters) and one of Fees; b.md, two chunks of Notes; six fillers.
CHUNKS = [
    piece("i.md", ["Intro"], "An opening note stands alone here."),
    piece("a.md", ["Guide", "Rules"], "Rule one opens here and the seam alpha words"),
    piece("a.md", ["Guide", "Rules"], "the seam alpha words go on to the seam beta words", 20),
    piece("a.md", ["Guide", "Rules"], "the seam beta words end the rules.", 19),
    piece("a.md", ["Guide", "Rules"], "A fourth rules piece stands alone."),
    piece("a.md", ["Guide", "Rules"], "A fifth rules piece closes the section."),
    piece("a.md", ["Guide", "Fees"], "Fees are paid in advance."),
    piece("b.md", ["Notes"], "Notes begin with a remark."),
    piece("b.md", ["Notes"], "Notes end with a reminder."),
    *(piece(f"f-{i}.md", ["Filler"], f"Filler text number {i}.") for i in range(9, 15)),
]
NAMES = {c["metadata"]["source"] for c in CHUNKS}
SETTINGS = {
    "retrieval_top_k": 20,
    "rerank_top_k": 5,
    "rrf_k": 60,
    # Masked, as the runs' effective_settings.json hold it.
    "rrf_doc_key_chars": "<set>",
    "chunk_overlap": 200,
    "parent_expansion_window": 2,
    "parent_expansion_max_chars": 3600,
}
VECTOR = [2, 7, 0, 9, 10, 11, 12]
BM25 = [2, 4, 8, 13, 14]
FILLERS = {m: (m - 8) / 100 for m in range(9, 15)}
# "one": a steep five, of which P1b keeps three; "two": a flat five, all kept, P is H;
# "three": a flat five without chunk 4, where S's section run of chunk 2 reaches chunk 5 and
# H's expansion, two chunks a side, stops at chunk 4; i.md second, so S's coherence keeps it.
SCORES = {
    "one": {2: 0.95, 7: 0.6, 4: 0.5, 0: 0.15, 8: 0.12, **FILLERS},
    "two": {7: 0.9, 0: 0.8, 2: 0.7, 4: 0.6, 8: 0.5, **FILLERS},
    "three": {**FILLERS, 2: 0.9, 0: 0.85, 7: 0.8, 8: 0.75, 9: 0.7, 4: 0.001},
}
RULES = "[a.md › Guide › Rules]\n"
# Chunks 1-3 under one header, each seam once.
RUN_123 = (
    RULES
    + "Rule one opens here and the seam alpha words go on to the seam beta words end the rules."
)
SECTION_45 = RULES + "A fourth rules piece stands alone.\n\nA fifth rules piece closes the section."
HYBRID_456 = SECTION_45 + "\n\nFees are paid in advance."
NOTES_78 = "[b.md › Notes]\nNotes begin with a remark.\n\nNotes end with a reminder."
KINDS = ("one", "two", "one", "two")


@functools.cache
def chat():
    """The chat's prompt builder, as the replay reads it: V3 and V4 at V4's input limit."""
    return ar.Builder()


def machine():
    return ar.Replay(CHUNKS, SETTINGS, "acme", None)


def ident(member):
    return [CHUNKS[member]["metadata"]["source"], member]


def recorded(replay, case_id, index, question, kind):
    """Stage 2's retrieval record of a question over VECTOR and BM25 (live_retrieval.py's
    form): its lists, and what the product gave on them under V3."""
    docs = replay.docs
    merged = replay.hybrid._rrf_merge([docs[m] for m in VECTOR], [docs[m] for m in BM25])
    scores = SCORES[kind]
    record = {
        "case_id": case_id,
        "index": index,
        "question": question,
        "lanes": {"vector": [ident(m) for m in VECTOR], "bm25": [ident(m) for m in BM25]},
        "pool": [[*ident(m), scores[m]] for m in (d.metadata["chunk_index"] for d in merged)],
    }
    got, path, clean = replay.h(record)
    assert clean and path["rerank_status"] == "ok"
    flat, sent = chat()("v3", question, got)
    five = [d.metadata["chunk_index"] for d in got]
    record.update(
        path=json.loads(json.dumps(path)),
        ranked=[[*ident(m), s] for m, s in zip(five, path["rerank_scores"], strict=True)],
        expanded=ar.described(got),
        sent=sent,
        prompt={
            "sha256": ar.digest(flat),
            "chars": len(flat),
            "est_tokens": chat().estimate(flat),
            "text": flat,
        },
    )
    return record


class Spans:
    """A base read by its documents: chunk m stands at [100 m, 100 m + 100) of its source."""

    def __init__(self, chunks):
        self.source = [c["metadata"]["source"] for c in chunks]

    def by_document(self, members):
        held = {}
        for m in dict.fromkeys(members):
            held.setdefault(self.source[m], []).append((100 * m, 100 * m + 100))
        return held


def gold_case(base, case_id):
    """WixQA's gold: the article i.md, chunk 0, which the steep five's P and S leave out.
    ConditionalQA's: a span of chunk 5, which every arm sends. MultiHop-RAG's: one of chunk 6,
    the Fees chunk that only the hybrid expansion joins."""
    if base == "wixqa":
        return {"case_id": case_id, "gold_sources": ["i.md"], "stratum": "s"}
    at = 5 if base == "conditionalqa" else 6
    alternatives = [{"source_id": "a.md", "start": 100 * at + 10, "end": 100 * at + 20}]
    return {"case_id": case_id, "evidence_groups": [{"alternatives": alternatives}], "stratum": "s"}


def run_of(label, tmp_path, kinds=KINDS):
    """One run's inputs as run_inputs gives them, over the synthetic archive; V4's saved
    prompts written under tmp_path/v4 as V4's runs hold them."""
    from scripts.external_pilot import Places

    base = ar.LABELS[label]
    replay = machine()
    records, committed, cases, v4, gold_of = [], {}, {}, {}, None
    if base in nr.METRICS:
        places = Places(CHUNKS, None, 200, 2) if base == "wixqa" else Spans(CHUNKS)
        gold_of = {"places": places, "sources": None if base == "wixqa" else {}, "chunks": CHUNKS}
    for index, kind in enumerate(kinds, 1):
        case_id = f"{label}-{index:03d}"
        question = f"Which rule holds in {label}, case {index}?"
        record = recorded(replay, case_id, index, question, kind)
        records.append(record)
        committed[case_id] = {"case_id": case_id, "prompt": {"sha256": record["prompt"]["sha256"]}}
        docs, _, _ = replay.h(record)
        if gold_of is not None:
            cases[case_id] = gold_case(base, case_id)
            members = ar.members_of("H", docs, CHUNKS, SETTINGS)
            got, missed = ar.points(base, cases[case_id], record["sent"], members, gold_of)
            committed[case_id].update(points=got, excerpt_pieces_missed=missed)
        if label in ar.V4_KEYS:
            flat = chat()("v4", question, docs)[0]
            run, name = f"v4-{ar.V4_KEYS[label]}-b01", f"{index:03d}-stream.txt"
            path = tmp_path / "v4" / run / "prompts" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(flat.encode("utf-8"))
            v4[case_id] = {
                "case_id": case_id,
                "run": run,
                "answered": True,
                "prompts": [{"file": name, "sha256": ar.digest(flat)}],
            }
    return {
        "label": label,
        "base": base,
        "tenant": "acme",
        "launch": {
            "status": "complete",
            "code_sha": ar.CODE_SHA,
            "tenant": "acme",
            "cases_file": f"/cases/{label}.jsonl",
        },
        "records": records,
        "committed": committed,
        "chunks": CHUNKS,
        "names": NAMES,
        "cases": cases,
        "gold_of": gold_of,
        "settings": SETTINGS,
        "batch": None,
        "provenance": {"label": label, "base": base, "records": len(records)},
        "questions": [r["question"] for r in records],
        "v4": v4,
        "v4_runs": tmp_path / "v4",
    }


def test_the_stand_ins_give_the_recorded_lists_and_refuse_another_pool():
    lane = ar.Lane(6)
    lane.set([4, 1, 3])
    scores = lane.get_scores(["any", "tokens"])
    assert scores == [0.0, 2.0, 0.0, 1.0, 3.0, 0.0] and lane.calls == 1
    # BM25's own cut gives the lane back in its order, and no chunk at zero.
    top = sorted(range(6), key=lambda i: scores[i], reverse=True)[:20]
    assert [i for i in top if scores[i] > 0] == [4, 1, 3]
    reranker = ar.Recorded()
    reranker.expect("q", ["a", "b"], [0.9, 0.1])
    assert reranker.predict([("q", "a"), ("q", "b")]) == [0.9, 0.1]
    with pytest.raises(ValueError, match="not the recorded one"):
        reranker.predict([("q", "b"), ("q", "a")])
    assert reranker.refused and reranker.calls == 2


def test_h_gives_its_record_back_and_the_gate_holds_it_to_the_export_and_to_v4(tmp_path):
    inputs = run_of("p2-wixqa", tmp_path, kinds=("one",))
    [record] = inputs["records"]
    row, h = ar.h_parity(inputs, record, machine(), chat())
    assert row == {
        "label": "p2-wixqa",
        "case_id": "p2-wixqa-001",
        "index": 1,
        "v4_saved": True,
        "breaks": [],
    }
    # The five by the recorded scores; the parent expansion over the archive, window 2.
    assert [d.metadata["chunk_index"] for d in h["docs"]] == [2, 7, 4, 0, 8]
    assert h["docs"][0].page_content == RUN_123
    assert h["docs"][2].page_content == HYBRID_456
    assert ar.members_of("H", h["docs"], CHUNKS, SETTINGS) == [[1, 2, 3], [7], [4, 5, 6], [0], [8]]
    assert inputs["committed"]["p2-wixqa-001"]["points"] == {
        "expanded": {"gold_article": 1.0, "gold_articles": 1.0},
        "sent": {"gold_article": 1.0, "gold_articles": 1.0},
    }
    saved = tmp_path / "v4" / "v4-wixqa-b01" / "prompts" / "001-stream.txt"
    assert h["flat"] == saved.read_bytes().decode("utf-8")
    assert chat().marks["v4"] in h["flat"] and chat().marks["v3"] in record["prompt"]["text"]
    assert [s["cut"] for s in h["sent"]] == [False] * 5


def test_a_record_without_lanes_is_the_vector_lane_alone_as_the_product_runs_it():
    replay = machine()
    scores = SCORES["one"]
    record = {"question": "q", "lanes": None, "pool": [[*ident(m), scores[m]] for m in VECTOR]}
    docs, path, clean = replay.h(record)
    assert clean and path["candidates"] == {"vector": 7, "bm25": 0, "merged": 7}
    assert [d.metadata["chunk_index"] for d in docs] == [2, 7, 0, 12, 11]


def _flip(text):
    """The text with its last character changed: one byte apart."""
    return text[:-1] + ("x" if text[-1] != "x" else "y")


def _saved(inputs):
    row = inputs["v4"]["p2-wixqa-001"]
    return row, Path(inputs["v4_runs"]) / row["run"] / "prompts" / row["prompts"][0]["file"]


def _resave(inputs, change, *, rehash):
    row, path = _saved(inputs)
    path.write_bytes(change(path.read_bytes()))
    if rehash:
        row["prompts"][0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def _record_text(inputs, record):
    record["prompt"]["text"] = _flip(record["prompt"]["text"])


def _record_sha(inputs, record):
    record["prompt"]["sha256"] = _flip(record["prompt"]["sha256"])


def _export_sha(inputs, record):
    prompt = inputs["committed"][record["case_id"]]["prompt"]
    prompt["sha256"] = _flip(prompt["sha256"])


def _sent_text(inputs, record):
    record["sent"][0]["text"] = _flip(record["sent"][0]["text"])


def _sent_cut(inputs, record):
    record["sent"][-1]["cut"] = True


def _expanded_text(inputs, record):
    record["expanded"][2]["text"] = _flip(record["expanded"][2]["text"])


def _ranked_score(inputs, record):
    record["ranked"][0][2] = 0.96


def _ranked_order(inputs, record):
    record["ranked"][1], record["ranked"][2] = record["ranked"][2], record["ranked"][1]


def _path_count(inputs, record):
    record["path"]["retained_contexts"] = 4


def _pool_score(inputs, record):
    record["pool"] = [[s, m, 0.16 if m == 0 else x] for s, m, x in record["pool"]]


def _pool_order(inputs, record):
    record["pool"][0], record["pool"][1] = record["pool"][1], record["pool"][0]


def _lane_cut(inputs, record):
    record["lanes"]["vector"] = record["lanes"]["vector"][:-1]


def _v4_byte_rehashed(inputs, record):
    _resave(inputs, lambda data: data[:-1] + b"#", rehash=True)


def _v4_byte(inputs, record):
    _resave(inputs, lambda data: data[:-1] + b"#", rehash=False)


def _v4_crlf_rehashed(inputs, record):
    _resave(inputs, lambda data: data.replace(b"\n", b"\r\n"), rehash=True)


def _v4_missing(inputs, record):
    _saved(inputs)[1].unlink()


def _export_points(inputs, record):
    inputs["committed"][record["case_id"]]["points"]["sent"]["gold_article"] = 0.0


def _export_missed(inputs, record):
    inputs["committed"][record["case_id"]]["excerpt_pieces_missed"] = 1


@pytest.mark.parametrize(
    ("edit", "breaks"),
    [
        (_record_text, {"v3_prompt"}),
        (_record_sha, {"v3_sha256"}),
        (_export_sha, {"v3_sha256"}),
        (_sent_text, {"v3_sent"}),
        (_sent_cut, {"v3_sent"}),
        (_expanded_text, {"expanded"}),
        (_ranked_score, {"ranked"}),
        (_ranked_order, {"ranked"}),
        (_path_count, {"retained_contexts"}),
        (_pool_score, {"rerank_scores", "ranked"}),
        (_v4_byte_rehashed, {"v4_prompt"}),
        (_v4_byte, {"v4_saved"}),
        (_v4_crlf_rehashed, {"v4_saved"}),
        (_v4_missing, {"v4_saved"}),
        (_export_points, {"recount"}),
        (_export_missed, {"recount"}),
    ],
)
def test_the_gate_refuses_a_record_or_a_saved_prompt_one_byte_apart(tmp_path, edit, breaks):
    inputs = run_of("p2-wixqa", tmp_path, kinds=("one",))
    record = inputs["records"][0]
    edit(inputs, record)
    row, _ = ar.h_parity(inputs, record, machine(), chat())
    assert set(row["breaks"]) == breaks


@pytest.mark.parametrize("edit", [_pool_order, _lane_cut])
def test_a_pool_the_lanes_do_not_fuse_into_is_refused_by_the_cross_encoders_stand_in(
    tmp_path, edit
):
    inputs = run_of("p2-wixqa", tmp_path, kinds=("one",))
    record = inputs["records"][0]
    edit(inputs, record)
    row, _ = ar.h_parity(inputs, record, machine(), chat())
    assert {"stand_ins", "rerank_status"} <= set(row["breaks"])


@pytest.mark.parametrize("score", [math.nan, math.inf, None, True])
def test_a_candidate_without_a_recorded_finite_score_breaks_the_stand_ins(tmp_path, score):
    inputs = run_of("p2-wixqa", tmp_path, kinds=("one",))
    record = inputs["records"][0]
    record["pool"][3][2] = score
    row, h = ar.h_parity(inputs, record, machine(), chat())
    assert row["breaks"] == ["stand_ins"] and h is None


def test_s_reads_hs_pool_keeps_the_coherent_five_and_joins_each_section_run_once():
    from ingestion.entity_graph_loading import ENTITY_GRAPH_NO_DATABASE

    replay = machine()
    replay.build_graph()
    assert replay.graph["entity_graph_status"] == ENTITY_GRAPH_NO_DATABASE
    assert len(replay.graph["digest"]) == 64
    record = recorded(replay, "c-1", 1, "Which rule holds?", "one")
    docs, path, clean = replay.s(record)
    assert clean and path["kind"] == "structural" and path["rerank_status"] == "ok"
    assert path["candidates"] == {**record["path"]["candidates"], "entity": 0}
    # i.md's lone chunk is a weak section of its own: coherence drops it.
    assert [d.metadata["chunk_index"] for d in docs] == [2, 7, 4, 8]
    assert [d["reason"] for d in path["dropped"]] == ["weak_singleton_section"]
    assert docs[0].page_content == RUN_123
    # Chunk 6 is another section's: S's run ends at chunk 5, where H's expansion goes on.
    assert docs[2].page_content == SECTION_45
    assert path["expanded_contexts"] == 2
    assert ar.members_of("S", docs, CHUNKS, SETTINGS) == [[1, 2, 3], [7], [4, 5], [8]]
    flat_five = recorded(replay, "c-2", 2, "Which note holds?", "two")
    docs, path, _ = replay.s(flat_five)
    # A singleton that is not weak stays, after the sections holding more of the five.
    assert [d.metadata["chunk_index"] for d in docs] == [7, 2, 4, 8, 0]


@pytest.mark.parametrize(
    ("text", "seed"),
    [
        # Chunks 1 and 3 without chunk 2: no run of the document.
        (
            RULES
            + "Rule one opens here and the seam alpha words\n\nthe seam beta words end the rules.",
            1,
        ),
        # Before stage 7: every piece with its header, each seam twice.
        (
            CHUNKS[1]["page_content"] + "\n\n" + CHUNKS[2]["page_content"],
            2,
        ),
        (NOTES_78 + " and more", 7),
    ],
)
def test_a_text_that_is_no_section_run_of_its_seed_is_unresolved(text, seed):
    with pytest.raises(ValueError, match="not a section run"):
        ar.run_members(text, seed, CHUNKS, 200)


def test_a_section_run_is_read_back_to_its_chunks():
    assert ar.run_members(RUN_123, 2, CHUNKS, 200) == [1, 2, 3]
    assert ar.run_members(RUN_123, 3, CHUNKS, 200) == [1, 2, 3]
    assert ar.run_members(SECTION_45, 4, CHUNKS, 200) == [4, 5]
    assert ar.run_members(CHUNKS[6]["page_content"], 6, CHUNKS, 200) == [6]


def test_p_keeps_p1bs_count_of_hs_five_and_expands_only_those():
    from scripts.p1_adaptive_k import kept_count

    replay = machine()
    record = recorded(replay, "c-1", 1, "Which rule holds?", "one")
    h_docs, path, _ = replay.h(record)
    scores = path["rerank_scores"]
    assert ar.kept(scores) == kept_count("rel", 0.2, scores, scores) == 3
    docs, k = replay.p(h_docs, scores)
    # Chunk 8 was the fifth of H's five; P drops it as a seed, and chunk 7 joins it.
    assert k == 3 and [d.page_content for d in docs] == [RUN_123, NOTES_78, HYBRID_456]
    assert ar.members_of("P", docs, CHUNKS, SETTINGS) == [[1, 2, 3], [7, 8], [4, 5, 6]]
    flat_five = recorded(replay, "c-2", 2, "Which note holds?", "two")
    h_docs, path, _ = replay.h(flat_five)
    assert replay.p(h_docs, path["rerank_scores"]) == (h_docs, 5)


@pytest.mark.parametrize(
    ("scores", "kept"),
    [
        # 0.1 is 0.2 of the first exactly: kept.
        ([0.5, 0.1, 0.0999, 0.05, 0.0], 2),
        ([0.9, 0.8, 0.7, 0.6, 0.5], 5),
        ([0.9, 0.17, 0.1, 0.0, 0.0], 1),
    ],
)
def test_p1bs_rule_keeps_the_candidates_within_a_fifth_of_the_first(scores, kept):
    assert ar.kept(scores) == kept


def rows_of(base, hits):
    """Rows of one base, a question to each (H's hit, the arm's hit), read alike at «sent»
    and «expanded»; S and P hit alike."""
    metric, second = nr.METRICS[base]

    def entry(hit):
        point = {metric: float(hit), second: float(hit)}
        return {"unresolved": None, "points": {"sent": point, "expanded": point}}

    return [
        {"base": base, "gold": True, "H": entry(h), "S": entry(a), "P": entry(a)} for h, a in hits
    ]


@pytest.mark.parametrize(
    ("b", "c", "p", "reading"),
    [
        (6, 0, 0.03125, "loss"),
        (0, 6, 0.03125, "gain"),
        (5, 0, 0.0625, "no detected difference"),
        (6, 1, 0.125, "no detected difference"),
        (0, 0, 1.0, "no detected difference"),
    ],
)
def test_an_arm_is_read_against_h_by_the_exact_mcnemar_at_its_edges(b, c, p, reading):
    hits = [(True, False)] * b + [(False, True)] * c + [(True, True)] * 3
    got = ar.pair(rows_of("wixqa", hits), "S", "sent")
    assert (got["n"], got["b_h_only"], got["c_arm_only"]) == (b + c + 3, b, c)
    assert (got["p"], got["reading"]) == (p, reading)
    assert got["hits"] == {"H": b + 3, "S": c + 3}
    assert got["gold_articles"] == {
        "H": round((b + 3) / (b + c + 3), 4),
        "S": round((c + 3) / (b + c + 3), 4),
    }


def test_a_question_is_read_only_with_gold_and_both_points_resolved():
    rows = rows_of("wixqa", [(True, False)] * 6)
    rows[0]["gold"] = False
    rows[1]["S"]["unresolved"] = "members"
    rows[2]["H"]["unresolved"] = "points"
    rows[3]["S"] = None
    got = ar.pair(rows, "S", "sent")
    assert (got["n"], got["b_h_only"]) == (2, 2)
    assert ar.unread(rows, "S") == 3 and ar.unread(rows, "P") == 1


def test_a_base_past_five_unread_or_without_a_graph_is_not_evidence_and_so_is_its_pool():
    rows = [row for base in ar.EXTERNAL for row in rows_of(base, [(True, True)] * 8)]
    wixqa = [r for r in rows if r["base"] == "wixqa"]
    for row in wixqa[:6]:
        row["P"]["unresolved"] = "points"
    conditionalqa = [r for r in rows if r["base"] == "conditionalqa"]
    for row in conditionalqa[:5]:
        row["S"]["unresolved"] = "points"
    got = ar.external(rows, {"multihoprag": {"error": "ValueError"}})
    p, s = got["P"], got["S"]
    assert p["per_base"]["wixqa"]["unread"] == 6
    assert p["per_base"]["wixqa"]["sent"] == p["per_base"]["wixqa"]["expanded"] == ar.NOT_EVIDENCE
    assert p["pooled"]["deciding"]["sent"] == p["pooled"]["all_three"]["sent"] == ar.NOT_EVIDENCE
    assert p["per_base"]["multihoprag"]["sent"]["n"] == 8
    # Five unread are still read; S has no graph on MultiHop-RAG: that base and the pool of
    # three are not evidence, the deciding pool is.
    assert s["per_base"]["conditionalqa"]["sent"]["n"] == 3
    assert s["per_base"]["multihoprag"]["unread"] is None
    assert (
        s["per_base"]["multihoprag"]["sent"] == s["pooled"]["all_three"]["sent"] == ar.NOT_EVIDENCE
    )
    assert s["pooled"]["deciding"]["sent"]["n"] == 11


def test_multihop_rag_is_printed_and_stops_nothing():
    rows = rows_of("wixqa", [(True, True)] * 4) + rows_of("multihoprag", [(True, False)] * 7)
    got = ar.external(rows, {})
    assert got["S"]["per_base"]["multihoprag"]["sent"]["reading"] == "loss"
    assert got["S"]["pooled"]["all_three"]["sent"]["reading"] == "loss"
    stops = ar.external_stops(got["S"])
    assert set(stops) == {"conditionalqa", "wixqa", "pooled_deciding"}
    assert ar.standing(stops) == "open"


@pytest.mark.parametrize(
    ("b", "c", "above"),
    [
        # Detected (p = 0.031, 0.016, 0.013) but within the MDE: 6 < 2.8·√6, 7 < 2.8·√7, ...
        (0, 6, False),
        (0, 7, False),
        (2, 12, False),
        # ... and past it: 8 > 2.8·√8, 10 > 2.8·√12, 12 > 2.8·√16.
        (0, 8, True),
        (1, 11, True),
        (2, 14, True),
        (8, 0, False),
        (0, 0, False),
    ],
)
def test_a_gain_qualifies_only_past_the_mde_and_the_margin_holds_a_detection(b, c, above):
    assert ar.above_mde(b, c) is above
    if above:
        assert nr.mcnemar(b, c) <= 0.008


def reading(name, b=0, c=0):
    return {"reading": name, "n": 100, "b_h_only": b, "c_arm_only": c}


LOSS, SAME = reading("loss", b=6), reading("no detected difference")
# Detected gains: six to none within the MDE; eight to none and fourteen to two past it.
SMALL, GAIN, WIDE = reading("gain", c=6), reading("gain", c=8), reading("gain", b=2, c=14)
BROAD, BROAD_POOL = reading("gain", c=24), reading("gain", b=6, c=24)
NE = ar.NOT_EVIDENCE


def flat(b, c):
    return reading("no detected difference", b=b, c=c)


EXTERNAL_STOPS = ("conditionalqa", "wixqa", "pooled_deciding")
AIRCARGO_STOPS = ("aircargo_full", "aircargo_full_or_partial")


def stops_of(planned=(), **arms):
    """Each arm's stop readings as the flow holds them: the external bases', and aircargo's for
    an arm the judge read; a reading not named detects no difference. An unread base leaves its
    pool unread too, as external() does."""
    return {
        arm: {
            where: arms.get(arm, {}).get(where, SAME)
            for where in EXTERNAL_STOPS + (AIRCARGO_STOPS if arm in planned else ())
        }
        for arm in ar.ARMS
    }


@pytest.mark.parametrize(
    ("stops", "standings", "gains", "arm"),
    [
        # S's pool gains, but it loses WixQA: a loss at any stop reading stops it.
        (
            stops_of(
                S={"wixqa": LOSS, "conditionalqa": BROAD, "pooled_deciding": BROAD_POOL},
                P={"pooled_deciding": GAIN},
            ),
            {"S": "stopped", "P": "open"},
            {"S": ["conditionalqa", "pooled_deciding"], "P": ["pooled_deciding"]},
            "P",
        ),
        (
            stops_of(
                S={"conditionalqa": GAIN, "pooled_deciding": WIDE}, P={"pooled_deciding": GAIN}
            ),
            {"S": "open", "P": "open"},
            {"S": ["conditionalqa", "pooled_deciding"], "P": ["pooled_deciding"]},
            "S",
        ),
        (
            stops_of(S={"pooled_deciding": GAIN}, P={"pooled_deciding": GAIN}),
            {"S": "open", "P": "open"},
            {"S": ["pooled_deciding"], "P": ["pooled_deciding"]},
            "P",
        ),
        (
            stops_of(S={"wixqa": NE, "pooled_deciding": NE}, P={"pooled_deciding": GAIN}),
            {"S": NE, "P": "open"},
            {"S": [], "P": ["pooled_deciding"]},
            "P",
        ),
        # judged: the planned arm holds aircargo.
        (
            stops_of(planned=("S",), S={"pooled_deciding": GAIN}),
            {"S": "open", "P": "open"},
            {"S": ["pooled_deciding"], "P": []},
            "S",
        ),
    ],
)
def test_gate_g1_opens_answers_only_to_the_best_arm_with_a_pooled_gain_past_the_mde(
    stops, standings, gains, arm
):
    got = ar.decision(stops)
    assert (got["standings"], got["gains"], got["arm"]) == (standings, gains, arm)
    assert got["reading"] == f"{arm} opens answers"
    assert arm in ar.candidates(stops)


@pytest.mark.parametrize(
    ("stops", "standings", "reading_"),
    [
        # No loss and no gain anywhere: the prompts an arm changes do not open answers.
        (stops_of(), {"S": "open", "P": "open"}, "H stays"),
        # A gain at one base beside a flat pool, or a falling one (the cold read's: WixQA six to
        # none, ConditionalQA ten to three, the pool ten to nine): not «вместе».
        (
            stops_of(P={"wixqa": GAIN, "conditionalqa": flat(6, 1), "pooled_deciding": flat(6, 9)}),
            {"S": "open", "P": "open"},
            "H stays",
        ),
        (
            stops_of(
                P={"wixqa": SMALL, "conditionalqa": flat(10, 3), "pooled_deciding": flat(10, 9)}
            ),
            {"S": "open", "P": "open"},
            "H stays",
        ),
        # A pooled gain the sample only just detects.
        (stops_of(S={"pooled_deciding": SMALL}), {"S": "open", "P": "open"}, "H stays"),
        # judged: an aircargo loss stops the planned arm.
        (
            stops_of(planned=("P",), P={"pooled_deciding": GAIN, "aircargo_full_or_partial": LOSS}),
            {"S": "open", "P": "stopped"},
            "H stays",
        ),
        # judged: the planned arm left unread on aircargo.
        (
            stops_of(
                planned=("P",),
                P={"pooled_deciding": GAIN, "aircargo_full": NE, "aircargo_full_or_partial": NE},
            ),
            {"S": "open", "P": NE},
            NE,
        ),
        (
            stops_of(
                S={"wixqa": NE, "pooled_deciding": NE},
                P={"conditionalqa": LOSS, "pooled_deciding": LOSS},
            ),
            {"S": NE, "P": "stopped"},
            NE,
        ),
        (
            stops_of(
                S={"wixqa": NE, "pooled_deciding": NE},
                P={"conditionalqa": NE, "pooled_deciding": NE},
            ),
            {"S": NE, "P": NE},
            NE,
        ),
    ],
)
def test_without_a_qualifying_gain_h_stays_or_the_gate_is_not_evidence(stops, standings, reading_):
    got = ar.decision(stops)
    assert (got["standings"], got["arm"], got["reading"]) == (standings, None, reading_)
    assert ar.candidates(stops) == []


def test_the_judge_reads_hs_prompts_and_each_open_arms_other_prompts_once():
    def row(label, case_id, h, s, p):
        return {
            "label": label,
            "case_id": case_id,
            **{arm: {"prompt": {"sha256": sha}} for arm, sha in (("H", h), ("S", s), ("P", p))},
        }

    rows = [
        row("p2-aircargo", "a", "h1", "h1", "p1"),
        row("p2-aircargo", "b", "h2", "s2", "s2"),
        row("p2-aircargo-gr", "c", "h3", "s3", "h3"),
        row("p2-wixqa", "d", "h4", "s4", "p4"),
    ]

    def planned(open_arms):
        runs = ar.judge_runs(rows, open_arms)
        return {name: [(r["case_id"], arm) for r, arm in taken] for name, taken in runs.items()}

    assert planned(["S", "P"]) == {
        "H-p2-aircargo": [("a", "H"), ("b", "H")],
        "S-p2-aircargo": [("b", "S")],
        "P-p2-aircargo": [("a", "P")],
        "H-p2-aircargo-gr": [("c", "H")],
        "S-p2-aircargo-gr": [("c", "S")],
    }
    # An arm stopped on the external bases is not judged: P's prompt of b is new then.
    assert planned(["P"]) == {
        "H-p2-aircargo": [("a", "H"), ("b", "H")],
        "P-p2-aircargo": [("a", "P"), ("b", "P")],
        "H-p2-aircargo-gr": [("c", "H")],
    }


def test_a_plan_once_written_is_frozen(tmp_path):
    files = {"plan.json": "{}\n", "runs/x/launch.json": "{}\n"}
    ar.put_tree(tmp_path / "judge", files)
    ar.put_tree(tmp_path / "judge", files)
    with pytest.raises(SystemExit, match="frozen once written"):
        ar.put_tree(tmp_path / "judge", {**files, "plan.json": '{"items": []}\n'})
    with pytest.raises(SystemExit, match="frozen once written"):
        ar.put_tree(tmp_path / "judge", {"plan.json": "{}\n"})


CONTROL_ENV = (
    "RAG_RETRIEVAL_TOP_K",
    "OLLAMA_CONTEXT_WINDOW",
    "RAG_RERANKER_RUNTIME",
    "EXPERIMENT_ID",
)


def _replay_args(tmp_path):
    return [
        "replay",
        "--runs",
        str(tmp_path / "runs"),
        "--data-root",
        str(tmp_path / "data"),
        "--v4-runs",
        str(tmp_path / "v4"),
        "--out",
        str(tmp_path / "out"),
        "--private",
        str(tmp_path / "private"),
    ]


def _fake_runs(monkeypatch, tmp_path, kinds=None):
    """The five runs over the synthetic archive, each of KINDS unless kinds names a label's
    fives; V4's questions are the fixture's, not the 300."""
    kinds = kinds or {}
    # The checkout's control as the code gives it, whatever the shell running the test sets.
    for name in CONTROL_ENV:
        monkeypatch.delenv(name, raising=False)
    runs = {label: run_of(label, tmp_path, kinds.get(label, KINDS)) for label in ar.LABELS}
    monkeypatch.setattr(ar, "run_inputs", lambda label, args, manifest: runs[label])
    monkeypatch.setattr(ar, "export_manifest", lambda: {})
    monkeypatch.setattr(ar, "V4_SAVED", sum(len(runs[label]["v4"]) for label in ar.V4_KEYS))
    monkeypatch.setattr(nr, "git_head", lambda: "0" * 40)
    return runs


def _lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _verdicts(plan, level_of):
    """A clean session's valid reply to every request of the plan."""
    from evaluation import isolated_request as isolated

    model = plan["route"]["model"]
    session = {
        "cli_version": "9.9.9",
        "model": model,
        "loaded": {kind: [] for kind in isolated.LOADED},
        "builtin": {"plugins": [], "agents": []},
        "turns": 1,
    }
    rows = []
    for item in plan["items"]:
        level = level_of(item)
        verdict = {
            "context_answer": level,
            "documents_with_answer": [] if level == "none" else [1],
            "note": "",
        }
        rows.append(
            {
                "item_id": item["item_id"],
                "message_sha256": item["message_sha256"],
                "status": "valid",
                "model": model,
                "session": session,
                "raw_text": json.dumps(verdict),
            }
        )
    return rows


def _replay_judging_open_arms(tmp_path):
    """The fixture's arms gain nowhere, so G1 plans no judge; to read the judge's half the replay
    plans it for every arm without a loss, as if each had gained."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            ar, "candidates", lambda stops: [a for a in ar.ARMS if ar.standing(stops[a]) == "open"]
        )
        return ar.main(_replay_args(tmp_path))


def test_without_a_detected_gain_the_replay_plans_no_judge_and_h_stays(tmp_path, monkeypatch):
    _fake_runs(monkeypatch, tmp_path)
    out = tmp_path / "out"
    assert ar.main(_replay_args(tmp_path)) == 0
    record = json.loads((out / "record.json").read_text(encoding="utf-8"))
    assert record["judge"] is None and not (tmp_path / "private").exists()
    assert record["control"] == ar.CONTROL
    assert record["decision"] == {
        "standings": {"S": "open", "P": "open"},
        "gains": {"S": [], "P": []},
        "arm": None,
        "reading": "H stays",
    }
    with pytest.raises(SystemExit, match="planned no judge"):
        ar.main(["judged", "--plan", str(tmp_path / "private" / "judge"), "--record", str(out)])


# S's section run of chunk 2 reaches chunk 5, ConditionalQA's gold, where H's expansion stops at
# chunk 4: S gains all eight ConditionalQA questions; on WixQA every arm sends i.md.
GAINS = {"p2-wixqa": ("three",) * 4, "p2-conditionalqa": ("three",) * 8}


def _judge(private, out, level_of):
    """The plan's verdicts written as level_of grades each request, and judged's output."""
    plan = json.loads((private / "judge" / "plan.json").read_text(encoding="utf-8"))
    (private / "judge" / "verdicts.jsonl").write_text(
        "".join(json.dumps(v) + "\n" for v in _verdicts(plan, level_of)), "utf-8", newline="\n"
    )
    assert ar.main(["judged", "--plan", str(private / "judge"), "--record", str(out)]) == 0
    return json.loads((out / "judged.json").read_text(encoding="utf-8"))


def test_a_true_gain_plans_the_judge_for_that_arm_alone_and_judged_opens_answers_to_it(
    tmp_path, monkeypatch
):
    _fake_runs(monkeypatch, tmp_path, GAINS)
    out, private = tmp_path / "out", tmp_path / "private"
    assert ar.main(_replay_args(tmp_path)) == 0
    record = json.loads((out / "record.json").read_text(encoding="utf-8"))
    s = record["external"]["S"]["per_base"]
    got = s["conditionalqa"]["sent"]
    assert (got["n"], got["b_h_only"], got["c_arm_only"], got["reading"]) == (8, 0, 8, "gain")
    assert s["wixqa"]["sent"]["reading"] == "no detected difference"
    pooled = record["stops"]["S"]["pooled_deciding"]
    assert (pooled["n"], pooled["b_h_only"], pooled["c_arm_only"], pooled["reading"]) == (
        12,
        0,
        8,
        "gain",
    )
    assert record["stops"]["P"]["pooled_deciding"]["reading"] == "no detected difference"
    assert record["decision"] == "pending the aircargo context judge"
    judge = record["judge"]
    assert judge["arms"] == ["S"]
    assert set(judge["by_run"]) == {
        "H-p2-aircargo",
        "S-p2-aircargo",
        "H-p2-aircargo-gr",
        "S-p2-aircargo-gr",
    }
    # The judge finds the answer in every context: S holds aircargo and opens answers.
    judged = _judge(private, out, lambda item: "full")
    assert judged["stability"]["passed"] is True
    assert judged["decision"] == {
        "standings": {"S": "open", "P": "open"},
        "gains": {"S": ["conditionalqa", "pooled_deciding"], "P": []},
        "arm": "S",
        "reading": "S opens answers",
    }
    # None of the answer in S's contexts: aircargo stops S, and H stays.
    judged = _judge(private, out, lambda item: "none" if item["run"].startswith("S-") else "full")
    assert judged["stops"]["S"]["aircargo_full"]["reading"] == "loss"
    assert judged["decision"]["standings"] == {"S": "stopped", "P": "open"}
    assert (judged["decision"]["arm"], judged["decision"]["reading"]) == (None, "H stays")


def test_s_without_a_graph_of_aircargo_is_not_planned_and_the_replay_reads_not_evidence(
    tmp_path, monkeypatch
):
    runs = _fake_runs(monkeypatch, tmp_path, GAINS)
    for label in ar.AIRCARGO:
        runs[label]["tenant"] = "unsectioned"
    real = ar.structural_projection

    def projection(docs, tenant):
        if tenant == "unsectioned":
            raise ValueError("no graph")
        return real(docs, tenant)

    monkeypatch.setattr(ar, "structural_projection", projection)
    out = tmp_path / "out"
    assert ar.main(_replay_args(tmp_path)) == 0
    record = json.loads((out / "record.json").read_text(encoding="utf-8"))
    assert record["labels"]["p2-aircargo"]["graph"] == {"error": "ValueError"}
    assert record["labels"]["p2-aircargo"]["S"] is None
    assert record["stops"]["S"]["pooled_deciding"]["reading"] == "gain"
    assert {record["stops"]["S"][f"aircargo_{name}"] for name in ar.HITS} == {ar.NOT_EVIDENCE}
    assert record["judge"] is None and not (tmp_path / "private").exists()
    assert record["decision"] == {
        "standings": {"S": ar.NOT_EVIDENCE, "P": "open"},
        "gains": {"S": ["conditionalqa", "pooled_deciding"], "P": []},
        "arm": None,
        "reading": ar.NOT_EVIDENCE,
    }


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("RAG_RETRIEVAL_TOP_K", "10"),
        ("OLLAMA_CONTEXT_WINDOW", "8192"),
        ("RAG_RERANKER_RUNTIME", "onnx"),
        ("EXPERIMENT_ID", "stage7"),
    ],
)
def test_a_checkout_whose_control_is_not_the_specs_stops_the_replay(
    tmp_path, monkeypatch, name, value
):
    _fake_runs(monkeypatch, tmp_path)
    monkeypatch.setenv(name, value)
    with pytest.raises(SystemExit, match="the checkout's control"):
        ar.main(_replay_args(tmp_path))
    assert not (tmp_path / "out").exists() and not (tmp_path / "private").exists()


def test_v4s_questions_are_all_read_or_the_replay_stops(tmp_path, monkeypatch):
    runs = _fake_runs(monkeypatch, tmp_path)
    monkeypatch.setattr(ar, "V4_SAVED", 13)
    with pytest.raises(SystemExit, match="12 of V4's questions read, not the 13"):
        ar.main(_replay_args(tmp_path))
    v4 = runs["p2-aircargo"]["v4"]
    v4["p2-aircargo-099"] = {**v4["p2-aircargo-001"], "case_id": "p2-aircargo-099"}
    with pytest.raises(SystemExit, match="a question V4 answered is not among the records"):
        ar.main(_replay_args(tmp_path))
    assert not (tmp_path / "out").exists()


def test_a_record_refused_after_the_plan_is_built_leaves_no_plan(tmp_path, monkeypatch):
    runs = _fake_runs(monkeypatch, tmp_path, GAINS)
    # A document named like the replay's decision: the record alone would carry it.
    runs["p2-wixqa"]["names"] = NAMES | {"pending the aircargo context judge"}
    with pytest.raises(SystemExit, match="refused"):
        ar.main(_replay_args(tmp_path))
    private = tmp_path / "private"
    assert not (tmp_path / "out").exists()
    assert not (private / "runs").exists() and not (private / "judge").exists()


def test_the_replay_writes_numbers_and_one_frozen_plan_and_judged_completes_gate_g1(
    tmp_path, monkeypatch
):
    _fake_runs(monkeypatch, tmp_path)
    out, private = tmp_path / "out", tmp_path / "private"
    assert _replay_judging_open_arms(tmp_path) == 0
    record = json.loads((out / "record.json").read_text(encoding="utf-8"))
    rows = _lines(out / "rows.jsonl")
    assert record["parity"] == {
        "questions": 20,
        "passed": 20,
        "v4_saved": 12,
        "v4_byte_equal": 12,
        "breaks": {},
    }
    assert len(rows) == 20 and len(_lines(out / "parity.jsonl")) == 20
    # WixQA: the steep fives' S and P leave i.md out; ConditionalQA: every arm sends chunk 5.
    wixqa = record["external"]["S"]["per_base"]["wixqa"]["sent"]
    assert (wixqa["n"], wixqa["b_h_only"], wixqa["c_arm_only"], wixqa["reading"]) == (
        4,
        2,
        0,
        "no detected difference",
    )
    assert record["external"]["S"]["per_base"]["multihoprag"]["sent"]["b_h_only"] == 4
    assert record["external"]["P"]["per_base"]["multihoprag"]["sent"]["b_h_only"] == 0
    assert record["external"]["P"]["pooled"]["deciding"]["sent"]["n"] == 8
    assert record["changed_on_v4"] == {"S": 12, "P": 6}
    assert record["labels"]["p2-aircargo"]["P"]["kept"] == {"3": 2, "5": 2}
    assert record["labels"]["p2-aircargo"]["S"]["seeds"] == {"4": 2, "5": 2}
    assert record["decision"] == "pending the aircargo context judge"
    judge = record["judge"]
    assert (judge["arms"], judge["requests"], judge["first_requests"], judge["retests"]) == (
        ["S", "P"],
        35,
        20,
        15,
    )
    assert judge["by_run"] == {
        "H-p2-aircargo": 4,
        "S-p2-aircargo": 4,
        "P-p2-aircargo": 2,
        "H-p2-aircargo-gr": 4,
        "S-p2-aircargo-gr": 4,
        "P-p2-aircargo-gr": 2,
    }
    plan_text = (private / "judge" / "plan.json").read_bytes().decode("utf-8")
    assert judge["plan_sha256"] == ar.digest(plan_text)
    plan = json.loads(plan_text)
    assert plan["prompt_id"] == "QA_PROMPT_V4" and set(plan["runs"]) == set(judge["by_run"])
    # The record holds ids, flags and numbers; the texts stand under PRIVATE alone.
    held = (out / "record.json").read_text(encoding="utf-8") + (out / "rows.jsonl").read_text(
        encoding="utf-8"
    )
    assert "Which rule holds" not in held and "a.md" not in held
    # A second replay finds the same plan there and leaves it as it is.
    assert _replay_judging_open_arms(tmp_path) == 0
    assert (private / "judge" / "plan.json").read_bytes().decode("utf-8") == plan_text

    # The judge finds the answer in H's prompts and P's, in none of S's.
    verdicts = _verdicts(plan, lambda item: "none" if item["run"].startswith("S-") else "full")
    (private / "judge" / "verdicts.jsonl").write_text(
        "".join(json.dumps(v) + "\n" for v in verdicts), "utf-8", newline="\n"
    )
    assert ar.main(["judged", "--plan", str(private / "judge"), "--record", str(out)]) == 0
    judged = json.loads((out / "judged.json").read_text(encoding="utf-8"))
    assert judged["counted"] == 35 and judged["stability"]["passed"] is True
    s, p = judged["aircargo"]["S"], judged["aircargo"]["P"]
    assert s["missing"] == p["missing"] == 0
    pooled = s["full"]["pooled"]
    assert (pooled["n"], pooled["b_h_only"], pooled["c_arm_only"], pooled["p"]) == (
        8,
        8,
        0,
        0.007812,
    )
    assert pooled["reading"] == s["full_or_partial"]["pooled"]["reading"] == "loss"
    assert s["full"]["p2-aircargo"]["n"] == s["full"]["p2-aircargo-gr"]["n"] == 4
    assert p["full"]["pooled"]["reading"] == "no detected difference"
    assert judged["stops"]["S"]["aircargo_full"]["reading"] == "loss"
    # S loses aircargo; P holds it but gains nowhere, so no arm opens answers.
    assert judged["decision"]["standings"] == {"S": "stopped", "P": "open"}
    assert (judged["decision"]["arm"], judged["decision"]["reading"]) == (None, "H stays")


def test_a_judge_without_stable_retests_leaves_the_aircargo_reading_not_evidence(
    tmp_path, monkeypatch
):
    _fake_runs(monkeypatch, tmp_path)
    out, private = tmp_path / "out", tmp_path / "private"
    assert _replay_judging_open_arms(tmp_path) == 0
    plan = json.loads((private / "judge" / "plan.json").read_text(encoding="utf-8"))
    # Each retest two steps from its first: the judge does not repeat itself.
    verdicts = _verdicts(plan, lambda item: "none" if "retest_of" in item else "full")
    (private / "judge" / "verdicts.jsonl").write_text(
        "".join(json.dumps(v) + "\n" for v in verdicts), "utf-8", newline="\n"
    )
    assert ar.main(["judged", "--plan", str(private / "judge"), "--record", str(out)]) == 0
    judged = json.loads((out / "judged.json").read_text(encoding="utf-8"))
    assert judged["stability"]["passed"] is False
    assert {judged["stops"][arm]["aircargo_full"] for arm in ar.ARMS} == {ar.NOT_EVIDENCE}
    assert judged["decision"]["arm"] is None
    assert judged["decision"]["reading"] == ar.NOT_EVIDENCE


def test_a_plan_other_than_the_one_the_replay_froze_is_refused(tmp_path, monkeypatch):
    _fake_runs(monkeypatch, tmp_path)
    out, private = tmp_path / "out", tmp_path / "private"
    assert _replay_judging_open_arms(tmp_path) == 0
    path = private / "judge" / "plan.json"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(SystemExit, match="not the plan the replay froze"):
        ar.main(["judged", "--plan", str(private / "judge"), "--record", str(out)])


def test_a_parity_break_writes_the_parity_rows_alone_and_reads_no_arm(tmp_path, monkeypatch):
    runs = _fake_runs(monkeypatch, tmp_path)
    record = runs["p2-conditionalqa"]["records"][1]
    record["prompt"]["text"] = _flip(record["prompt"]["text"])
    out = tmp_path / "out"
    assert ar.main(_replay_args(tmp_path)) == 3
    parity = _lines(out / "parity.jsonl")
    assert len(parity) == 20
    assert [(r["case_id"], r["breaks"]) for r in parity if r["breaks"]] == [
        ("p2-conditionalqa-002", ["v3_prompt"])
    ]
    assert not (out / "record.json").exists() and not (out / "rows.jsonl").exists()
    assert not (tmp_path / "private").exists()


def test_a_record_that_would_name_a_document_of_a_base_is_refused(tmp_path, monkeypatch):
    runs = _fake_runs(monkeypatch, tmp_path)
    # A base whose document is named like a run: every parity row would carry the name.
    runs["p2-wixqa"]["names"] = NAMES | {"p2-wixqa"}
    with pytest.raises(SystemExit, match="refused"):
        ar.main(_replay_args(tmp_path))
    assert not (tmp_path / "out").exists()


def test_the_tool_reads_what_the_spec_registers():
    """Registered before the run: the spec names the SHA-256 of the tool and of this test, and a
    later change shows here."""
    spec = (ROOT / ar.SPEC).read_text(encoding="utf-8")
    for phrase in (
        "**registered before the run**",
        "larger than the MDE",
        "c − b > 2.8·√(b + c)",
        "stage 7 closes with «H stays»",
        "aircargo stops an arm and qualifies none",
        "the larger c − b at the two deciding bases pooled",
        "H's replayed prompts equal V4's saved prompts byte for byte",
        "The context judge's plan, written before its first request",
        "E stops: its probe's gate G2, the extraction cost, failed at the first look on 2026-10-29",
        "`EXPERIMENT_ID`",
        "SHA list of the run:",
        "5e308fe",
        "4f48fed",
    ):
        assert phrase in spec, phrase
    named = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    assert sorted(named) == [
        "reports/stage7/tools/arms_replay.py",
        "tests/test_stage7_arms_replay.py",
    ]
    for path, sha in named.items():
        assert ar.sha256(ROOT / path) == sha, path
    for sha in (ar.EXPORT_MANIFEST_SHA256, ar.V4_RECORD_SHA256, *ar.ARCHIVES.values()):
        assert sha in spec, sha
    # Gate G1 and the control, as the spec registers them.
    assert (ar.QUALIFIES_AT, ar.MDE_Z, ar.V4_SAVED) == ("pooled_deciding", Fraction(14, 5), 300)
    assert ar.CONTROL == {
        "retrieval_top_k": 20,
        "ollama_context_window": 4096,
        "reranker_runtime": "torch",
    }
    frozen = (ar.KMAX, ar.TOP, ar.WINDOW, ar.LIMIT, ar.REL, ar.MAX_UNREAD, ar.MAX_MISSING)
    assert frozen == (20, 5, 4096, 2636, 0.2, 5, 5)
    assert (ar.ARMS, ar.DECIDING, ar.AIRCARGO) == (
        ("S", "P"),
        ("conditionalqa", "wixqa"),
        ("p2-aircargo", "p2-aircargo-gr"),
    )
    assert ar.HITS == {"full": ("full",), "full_or_partial": ("full", "partial")}
    assert set(ar.LABELS) == {*nr.LABELS.values(), "p2-aircargo-gr"}
    assert (ar.CODE_SHA, ar.V4_STAND) == (
        "5e308fe48cca0955c3007057a574a425f71e2a6a",
        "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1",
    )
    # The frozen inputs are the committed ones.
    assert ar.sha256(ar.EXPORT / "manifest.json") == ar.EXPORT_MANIFEST_SHA256
    assert ar.sha256(ar.V4_DIR / "v4-record.json") == ar.V4_RECORD_SHA256
    for label, base in ar.LABELS.items():
        exported = json.loads((ar.EXPORT / f"{label}.json").read_text(encoding="utf-8"))
        assert exported["provenance"]["archive_sha256"] == ar.ARCHIVES[base]
    assert ar.RECORD == ROOT / "reports/stage7/5e308fe"
    assert set(nr.MEASURE_CODE) < set(ar.MEASURE_CODE)
    assert all((ROOT / name).is_file() for name in ar.MEASURE_CODE)


def test_the_fixture_archive_is_copied_and_never_changed_by_a_replay():
    before = copy.deepcopy(CHUNKS)
    replay = machine()
    replay.build_graph()
    record = recorded(replay, "c-1", 1, "Which rule holds?", "one")
    replay.s(record)
    replay.p(replay.h(record)[0], record["path"]["rerank_scores"])
    assert CHUNKS == before
