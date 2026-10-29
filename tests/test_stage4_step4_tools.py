"""Stage 4, step 4 (docs/specs/stage4-step4-prompt-budget.md): the answer prompt fitted through
the product's code at every window on a synthetic archive, the checks against stage 2's and V4's
records, and the frozen reading on hand-made rows."""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/stage4-step4/tools/prompt_budget.py"


def _load():
    spec = importlib.util.spec_from_file_location("prompt_budget", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["prompt_budget"] = module
    spec.loader.exec_module(module)
    return module


pb = _load()
nr = pb.nr
QUESTION = "How is a damage claim filed?"
# Stand-ins of the two answer prompts: stage 2's and the code's.
STAGE2 = "Answer from the context.\n\n{context_block}\n\nQuestion: {question}"
CODE = (
    "Answer only from the numbered context below; put [N] after each claim it supports.\n\n"
    "{context_block}\n\nQuestion: {question}\nAnswer:"
)
WORDS = ("cargo", "claim", "freight", "weight", "storage", "notice", "damage", "tariff")
# A synthetic archive: thirty chunks, three to a document, each about 420 estimated tokens, so
# the five fit whole at 4,096 and fewer of them below.
SOURCES = [f"doc-{i // 3}" for i in range(30)]
CHUNKS = [
    {
        "page_content": f"Part {i}. "
        + "\n\n".join(" ".join(WORDS[(i + p + k) % 8] for k in range(55)) + "." for p in range(5)),
        "metadata": {"source": s},
    }
    for i, s in enumerate(SOURCES)
]
RANKED = [3, 12, 18, 27, 24]
SCORES = [0.91, 0.82, 0.73, 0.64, 0.55]
# The gold of the WixQA case: doc-9, the fourth of the five.
CASE = {"gold_sources": ["doc-9"], "stratum": "s"}
PLACES = SimpleNamespace(
    source=SOURCES,
    members=lambda documents: [d["metadata"]["chunk_index"] for d in documents],
)
SETTINGS = {
    "rerank_top_k": 5,
    "parent_expansion": True,
    "parent_expansion_window": 2,
    "parent_expansion_max_chars": 8000,
    "chunk_overlap": 0,
}


def documents(members):
    """A stand-in expansion that joins nothing: each seed alone, in its order."""
    return [
        SimpleNamespace(
            page_content=CHUNKS[m]["page_content"],
            metadata={**CHUNKS[m]["metadata"], "chunk_index": m},
        )
        for m in members
    ]


def plain(docs):
    return [{"page_content": d.page_content, "metadata": d.metadata} for d in docs]


class At:
    """What a base's questions share, with the stand-in expansion."""

    def __init__(self, v4=None, stage2=STAGE2, code=CODE):
        self.stage2, self.code, self.v4, self.sources = stage2, code, v4, None

    def documents(self, chunks, members):
        assert chunks is CHUNKS
        return documents(members)


def fitted_at(template, window, docs):
    with pb.answer_prompt(template):
        return pb.fit(window, QUESTION, plain(docs))


def record(docs=None, **change):
    """A retrieval record of stage 2's form whose sent documents and prompt are stage 2's
    prompt fitted at 4,096 on the five."""
    docs = documents(RANKED) if docs is None else docs
    flat, fitted = fitted_at(STAGE2, pb.TODAY, docs)
    ranked = [
        [d.metadata["source"], d.metadata["chunk_index"], s]
        for d, s in zip(docs, SCORES, strict=True)
    ]
    out = {
        "case_id": "wixqa-0001",
        "index": 1,
        "question": QUESTION,
        "lanes": {"vector": [r[:2] for r in ranked], "bm25": []},
        "pool": ranked,
        "ranked": ranked,
        "expanded": [
            {"source": r[0], "chunk_index": r[1], "text": d.page_content}
            for r, d in zip(ranked, docs, strict=True)
        ],
        "sent": pb.sent(fitted, plain(docs)),
        "prompt": {"sha256": pb.digest(flat)},
    }
    out.update(change)
    return out


def v4_row(**change):
    """V4's row of the question: the same retrieval, and the code's prompt at 4,096."""
    flat, _ = fitted_at(CODE, pb.TODAY, documents(RANKED))
    out = {
        "ranked_scores": [round(s, 6) for s in SCORES],
        "expanded_chars": sum(len(CHUNKS[m]["page_content"]) for m in RANKED),
        "prompts": [{"sha256": pb.digest(flat)}],
    }
    out.update(change)
    return out


def ask(rec=None, at=None, base="wixqa", case=CASE):
    rec = record() if rec is None else rec
    return pb.question(base, case, rec, CHUNKS, PLACES, None, at or At())


def test_the_windows_step_down_from_todays_with_the_answers_output_budget_kept():
    from llm.role_params import generation_kwargs_for_role

    assert pb.WINDOWS == (4096, 3840, 3584, 3328, 3072, 2816, 2560, 2304)
    assert pb.TODAY == 4096
    assert pb.OUTPUT_BUDGET == generation_kwargs_for_role("generate")["max_tokens"] == 1024
    limits = [pb.input_limit(w) for w in pb.WINDOWS]
    assert limits == [2636, 2406, 2176, 1945, 1715, 1484, 1254, 1024]


def test_the_registry_is_read_from_source_as_a_literal_and_never_run():
    from agent.prompts import PROMPT_REGISTRY

    source = (ROOT / "agent/prompts.py").read_text(encoding="utf-8")
    assert pb.registry_of(source)["qa"] == PROMPT_REGISTRY["qa"]
    assert pb.registry_of('PROMPT_REGISTRY = {"qa": {"text": "x"}}\n') == {"qa": {"text": "x"}}
    with pytest.raises(ValueError):
        pb.registry_of('PROMPT_REGISTRY = {"qa": {"text": open("x").read()}}\n')
    with pytest.raises(SystemExit, match="no PROMPT_REGISTRY"):
        pb.registry_of("REGISTRY = {}\n")


def test_stage_2s_prompt_is_agent_prompts_at_the_stands_commit(monkeypatch):
    calls = []

    def shown(prompt_id):
        def run(args, **kwargs):
            calls.append(args)
            text = f'PROMPT_REGISTRY = {{"qa": {{"prompt_id": "{prompt_id}", "text": "t"}}}}\n'
            return SimpleNamespace(stdout=text.encode("utf-8"))

        return run

    monkeypatch.setattr(pb.subprocess, "run", shown("QA_PROMPT_V3"))
    assert pb.stage2_prompt() == "t"
    assert calls[0][-2:] == ["show", f"{nr.CODE_SHA}:agent/prompts.py"]
    monkeypatch.setattr(pb.subprocess, "run", shown("QA_PROMPT_V4"))
    with pytest.raises(SystemExit, match="not QA_PROMPT_V3"):
        pb.stage2_prompt()


def test_the_codes_prompt_is_v4_as_the_chat_resolves_it():
    from agent.prompts import PROMPT_REGISTRY

    assert PROMPT_REGISTRY["qa"]["prompt_id"] == pb.CODE_PROMPT_ID
    assert pb.code_prompt() == PROMPT_REGISTRY["qa"]["text"]


def test_the_override_holds_inside_the_block_only():
    from agent.prompt_registry import get_prompt
    from agent.prompts import PROMPT_REGISTRY

    with pb.answer_prompt(STAGE2):
        assert get_prompt("qa") == STAGE2
    assert get_prompt("qa") == PROMPT_REGISTRY["qa"]["text"]
    with pytest.raises(RuntimeError), pb.answer_prompt(STAGE2):
        raise RuntimeError
    assert get_prompt("qa") == PROMPT_REGISTRY["qa"]["text"]


def test_a_smaller_window_sends_fewer_documents_through_the_products_fitting():
    from llm.providers.base import estimate_window_tokens

    docs = documents(RANKED)
    counts = []
    for window in pb.WINDOWS:
        flat, fitted = fitted_at(CODE, window, docs)
        assert flat.startswith("USER:\nAnswer only from the numbered context below")
        assert estimate_window_tokens(flat) <= pb.input_limit(window)
        got = pb.sent(fitted, plain(docs))
        # Leading documents whole, the last one kept possibly cut.
        assert [d["chunk_index"] for d in got] == RANKED[: len(got)]
        assert not any(d["cut"] for d in got[:-1])
        counts.append(len(got))
    assert counts[0] == 5 and counts[-1] < 4
    assert counts == sorted(counts, reverse=True)


def test_a_question_reads_every_window_at_sent():
    row = ask(at=At(v4={"wixqa-0001": v4_row()}))
    assert [e["window"] for e in row["windows"]] == list(pb.WINDOWS)
    for entry in row["windows"]:
        # The gold is the fourth document: read at «sent» while four or more are sent.
        hit = float(entry["documents"] >= 4)
        assert entry["sent"] == {"gold_article": hit, "gold_articles": hit}
        assert entry["excerpt_pieces_missed"] == 0
    today = row["windows"][0]
    assert (today["documents"], today["cut"]) == (5, False)
    assert row["windows"][-1]["sent"]["gold_article"] == 0.0
    gold = {"gold_article": 1.0, "gold_articles": 1.0}
    assert row["points"] == {"ranked": gold, "expanded_ranked": gold, "sent": gold}
    assert (row["v4_same_retrieval"], row["v4_prompt_checked"]) == (True, True)
    assert (row["case_id"], row["stratum"], row["unresolved"]) == ("wixqa-0001", "s", None)


def test_a_question_without_gold_keeps_only_the_sizes():
    row = ask(base="aircargo", case=None)
    assert "points" not in row and "unresolved" not in row
    assert [set(e) for e in row["windows"]] == [
        {"window", "documents", "cut", "chars", "est_tokens"}
    ] * len(pb.WINDOWS)
    assert (row["v4_same_retrieval"], row["v4_prompt_checked"]) == (None, False)


def test_v4s_prompt_is_checked_only_where_v4_retrieved_what_the_record_holds():
    other = v4_row(ranked_scores=[0.9] * 5, prompts=[{"sha256": "0" * 64}])
    row = ask(at=At(v4={"wixqa-0001": other}))
    assert (row["v4_same_retrieval"], row["v4_prompt_checked"]) == (False, False)
    longer = v4_row(expanded_chars=1, prompts=[{"sha256": "0" * 64}])
    assert ask(at=At(v4={"wixqa-0001": longer}))["v4_prompt_checked"] is False
    assert pb.same_retrieval(record(), v4_row())
    rounded = [[*r[:2], r[2] + 4e-7] for r in record()["ranked"]]
    assert pb.same_retrieval(record(ranked=rounded), v4_row())


def _recorded_sent_changed():
    rec = record()
    rec["sent"][-1] = {**rec["sent"][-1], "cut": True}
    return rec


@pytest.mark.parametrize(
    ("make", "at", "message"),
    [
        (
            lambda: record(expanded=[{**e, "text": "other"} for e in record()["expanded"]]),
            None,
            "expansion is not the recorded one",
        ),
        (_recorded_sent_changed, None, "stage 2's prompt at 4096"),
        (lambda: record(prompt={"sha256": "0" * 64}), None, "stage 2's prompt at 4096"),
        (lambda: record(question=QUESTION + " Now?"), None, "stage 2's prompt at 4096"),
        (
            record,
            At(v4={"wixqa-0001": v4_row(prompts=[{"sha256": "0" * 64}])}),
            "not V4's run's",
        ),
        (record, At(stage2=CODE), "stage 2's prompt at 4096"),
    ],
)
def test_the_checks_stop_before_any_number(make, at, message):
    with pytest.raises(SystemExit, match=message):
        ask(make(), at)


def test_stage_2s_reading_unread_stops_where_the_export_read_it(monkeypatch):
    real = pb.retrieval_summary.coverage

    def unread(base, case, rec, places, sources, chunks):
        return {**real(base, case, rec, places, sources, chunks), "unresolved": "sent"}

    monkeypatch.setattr(pb.retrieval_summary, "coverage", unread)
    with pytest.raises(SystemExit, match="do not read"):
        ask()


def test_a_window_whose_sent_cannot_be_read_leaves_the_question_out(monkeypatch):
    real = pb.retrieval_summary.coverage

    def unread_below_four(base, case, rec, places, sources, chunks):
        got = real(base, case, rec, places, sources, chunks)
        if rec["pool"] is None and len(rec["sent"]) < 4:
            got["unresolved"] = "sent"
        return got

    monkeypatch.setattr(pb.retrieval_summary, "coverage", unread_below_four)
    row = ask()
    first = next(e["window"] for e in row["windows"] if e["documents"] < 4)
    assert row["unresolved"] == first
    assert all(("sent" in e) == (e["window"] > first) for e in row["windows"])


def test_the_recount_holds_stage_2s_sent_to_the_export():
    row = ask()
    exported = {"points": {"sent": row["points"]["sent"]}, "excerpt_pieces_missed": 0}
    pb.recount([row, {"case_id": "aircargo-1"}], {"wixqa-0001": exported})
    missed = {**exported, "excerpt_pieces_missed": 1}
    with pytest.raises(SystemExit, match="differs from the export"):
        pb.recount([row], {"wixqa-0001": missed})
    other = {**exported, "points": {"sent": {"gold_article": 0.0, "gold_articles": 0.0}}}
    with pytest.raises(SystemExit, match="differs from the export"):
        pb.recount([row], {"wixqa-0001": other})


def test_the_documents_are_the_no_reranker_points_expansion():
    expanded = pb.Documents(CHUNKS, SETTINGS).documents(RANKED)
    assert nr.described(expanded) == nr.Expansion(CHUNKS, SETTINGS)(RANKED)
    # The neighbours of the seed's own document are joined, and the seed's metadata kept.
    assert "Part 4." in expanded[0].page_content and "Part 2." not in expanded[0].page_content
    assert expanded[0].metadata["parent_expanded"] is True
    assert [d.metadata["chunk_index"] for d in expanded] == RANKED
    assert [d.metadata["source"] for d in expanded] == [SOURCES[m] for m in RANKED]


def hit(base, value):
    first, second = nr.METRICS[base]
    return {first: value, second: value}


def made(base, misses=(), unresolved=None, case_id="q"):
    """A hand-made row of a question with gold: read at «sent» at every window but misses."""
    windows = []
    for i, w in enumerate(pb.WINDOWS):
        entry = {
            "window": w,
            "documents": 5 - i // 2,
            "cut": i % 2 == 1,
            "chars": w,
            "est_tokens": w // 2,
        }
        if unresolved is None or w > unresolved:
            entry["sent"] = hit(base, float(w not in misses))
            entry["excerpt_pieces_missed"] = 0
        windows.append(entry)
    return {
        "case_id": f"{base}-{case_id}",
        "base": base,
        "index": 1,
        "v4_same_retrieval": True,
        "v4_prompt_checked": True,
        "windows": windows,
        "stratum": "s",
        "unresolved": unresolved,
        "points": {
            "ranked": hit(base, 1.0),
            "expanded_ranked": hit(base, 1.0),
            "sent": hit(base, 1.0),
        },
        "excerpt_pieces_missed": 0,
    }


def beside(case_id="aircargo-q"):
    """A hand-made row of a question without gold."""
    windows = [
        {"window": w, "documents": 3, "cut": False, "chars": w, "est_tokens": w // 2}
        for w in pb.WINDOWS
    ]
    return {
        "case_id": case_id,
        "base": "aircargo",
        "index": 1,
        "v4_same_retrieval": False,
        "v4_prompt_checked": False,
        "windows": windows,
    }


LOW = {3072, 2816, 2560, 2304}


def test_a_pair_sets_a_window_against_4096_by_the_no_reranker_points_exact_mcnemar():
    rows = [made("wixqa", misses=LOW)] * 8 + [made("wixqa")] * 4
    assert pb.pair(rows, 3328) == {
        "n": 12,
        "hits": {"today": 12, "window": 12},
        "b_today_only": 0,
        "c_window_only": 0,
        "p": 1.0,
        "reading": "no detected difference",
        "gold_articles": {"today": 1.0, "window": 1.0},
    }
    got = pb.pair(rows, 3072)
    assert (got["hits"], got["b_today_only"], got["c_window_only"]) == (
        {"today": 12, "window": 4},
        8,
        0,
    )
    assert (got["p"], got["reading"]) == (0.007812, "loss")


def test_a_base_reads_its_questions_read_at_every_window_and_more_than_five_unread_are_not_evidence():
    rows = [made("conditionalqa", misses=LOW)] * 8 + [made("conditionalqa", unresolved=2816)] * 5
    got = pb.summary("conditionalqa", rows + [beside()])
    assert (got["questions"], got["with_gold"], got["unresolved"]) == (14, 13, 5)
    by_window = {p["window"]: p for p in got["windows"]}
    assert "sent" not in by_window[4096]
    assert by_window[3072]["sent"]["n"] == 8
    assert by_window[3072]["sent"]["reading"] == "loss"
    assert by_window[3072]["input_limit"] == 1715
    assert by_window[3840]["shorter"] == 14
    assert by_window[3840]["est_tokens_saved"]["median"] == 128
    assert got["stage2_against_today"]["reading"] == "no detected difference"
    assert got["v4"] == {"same_retrieval": 13, "prompts_checked": 13}
    more = pb.summary("conditionalqa", rows + [made("conditionalqa", unresolved=2304)])
    assert all(p["sent"] == pb.NOT_EVIDENCE for p in more["windows"] if p["window"] != 4096)


def test_the_pooled_curve_reads_the_three_bases_by_each_ones_primary_metric():
    rows = (
        [made("wixqa", misses=LOW)] * 3
        + [made("conditionalqa", misses=LOW)] * 3
        + [made("multihoprag", misses=LOW)] * 3
        + [made("multihoprag", unresolved=3840)]
    )
    pooled = pb.pooled_windows(rows, False)
    assert [p["window"] for p in pooled] == list(pb.WINDOWS[1:])
    at = {p["window"]: p["sent"] for p in pooled}
    assert (at[3072]["n"], at[3072]["b_today_only"], at[3072]["reading"]) == (9, 9, "loss")
    assert at[3328]["reading"] == "no detected difference"
    assert "gold_articles" not in at[3072] and "evidence_recall" not in at[3072]
    assert all(p["sent"] == pb.NOT_EVIDENCE for p in pb.pooled_windows(rows, True))


LOSS = {"reading": "loss"}
GAIN = {"reading": "gain"}
NONE = {"reading": "no detected difference"}


def _curves(**marks):
    def curve(where):
        return [
            {"window": w, **({} if w == pb.TODAY else {"sent": marks.get(where, {}).get(w, NONE)})}
            for w in pb.WINDOWS
        ]

    return {b: {"windows": curve(b)} for b in nr.METRICS}, curve("pooled")[1:]


def _smallest(**marks):
    return pb.decision(*_curves(**marks))["smallest_window_without_a_detected_loss"]


def test_the_smallest_window_without_a_detected_loss_is_read_from_the_top():
    assert _smallest() == 2304
    assert pb.decision(*_curves(wixqa={3072: LOSS})) == {
        "smallest_window_without_a_detected_loss": 3328,
        "its_input_limit": 1945,
        "losses": {"wixqa": [3072], "conditionalqa": [], "multihoprag": [], "pooled": []},
    }
    # A loss on one base or pooled vetoes its window and every one below it, read from the top.
    assert _smallest(conditionalqa={2304: LOSS, 3328: LOSS}) == 3584
    assert _smallest(pooled={3840: LOSS}) == 4096
    # A gain vetoes nothing.
    assert _smallest(multihoprag={3840: GAIN, 2304: GAIN}) == 2304
    assert pb.decision(*_curves(wixqa={2560: pb.NOT_EVIDENCE})) == pb.NOT_EVIDENCE
    assert pb.decision(*_curves(pooled={3840: pb.NOT_EVIDENCE})) == pb.NOT_EVIDENCE


def _runs(tmp_path, base, **settings):
    run = tmp_path / nr.LABELS[base]
    run.mkdir()
    (run / "effective_settings.json").write_text(
        json.dumps({"all": {**SETTINGS, **settings}}), encoding="utf-8"
    )
    return tmp_path


def test_the_no_reranker_loading_builds_this_steps_rows_and_gets_its_question_back(
    tmp_path, monkeypatch
):
    # The no-reranker point's loading makes a row a record through its module's question().
    assert "question(base, cases.get(" in inspect.getsource(nr.base_rows)
    runs, original = _runs(tmp_path, "aircargo"), nr.question
    expanded = pb.Documents(CHUNKS, SETTINGS).documents(RANKED)
    rec = record(expanded, case_id="aircargo-0001")

    def loading(base, runs, root, manifest):
        row = nr.question(base, None, rec, CHUNKS, None, None)
        return [row], {"label": nr.LABELS[base]}, set(), []

    monkeypatch.setattr(nr, "base_rows", loading)
    monkeypatch.setattr(nr, "export_rows", lambda label, manifest: {})
    rows, provenance, _, _ = pb.base_rows("aircargo", runs, tmp_path, {}, (STAGE2, CODE))
    assert nr.question is original
    assert [e["window"] for e in rows[0]["windows"]] == list(pb.WINDOWS)
    assert rows[0]["v4_same_retrieval"] is None
    assert provenance["v4_rows_sha256"] == nr.sha256(pb.V4_ROWS / "v4-aircargo.cases.jsonl")

    def failing(base, runs, root, manifest):
        raise SystemExit("a check of the no-reranker point")

    monkeypatch.setattr(nr, "base_rows", failing)
    with pytest.raises(SystemExit):
        pb.base_rows("aircargo", runs, tmp_path, {}, (STAGE2, CODE))
    assert nr.question is original


def test_main_writes_ids_flags_and_numbers_and_refuses_a_record_with_text(tmp_path, monkeypatch):
    rows = {
        "wixqa": [made("wixqa", misses=LOW)] * 8 + [made("wixqa")] * 4,
        "conditionalqa": [made("conditionalqa")] * 3,
        "multihoprag": [made("multihoprag")] * 3,
        "aircargo": [beside()] * 2,
    }

    def loading(base, runs, root, manifest, prompts):
        assert prompts == (STAGE2, CODE)
        return rows[base], {"label": nr.LABELS[base]}, {"doc-1"}, ["What does chunk 1 say?"]

    monkeypatch.setattr(pb, "base_rows", loading)
    monkeypatch.setattr(pb, "stage2_prompt", lambda: STAGE2)
    monkeypatch.setattr(pb, "code_prompt", lambda: CODE)
    out = tmp_path / "out"
    assert pb.main(["runs", "data", str(out)]) == 0
    got = json.loads((out / "record.json").read_text(encoding="utf-8"))
    assert (got["spec"], got["stand_code_sha"]) == (pb.SPEC, nr.CODE_SHA)
    assert [w["window"] for w in got["windows"]] == list(pb.WINDOWS)
    assert got["prompts"]["code"] == {"prompt_id": "QA_PROMPT_V4", "sha256": pb.digest(CODE)}
    assert set(got["measure_code_sha256"]) == set(pb.MEASURE_CODE)
    assert got["decision"] == {
        "smallest_window_without_a_detected_loss": 3328,
        "its_input_limit": 1945,
        "losses": {
            "wixqa": [3072, 2816, 2560, 2304],
            "conditionalqa": [],
            "multihoprag": [],
            "pooled": [3072, 2816, 2560, 2304],
        },
    }
    assert len((out / "rows.jsonl").read_text(encoding="utf-8").splitlines()) == 20
    rows["aircargo"] = [beside(case_id="doc-1")]
    with pytest.raises(SystemExit, match="refused"):
        pb.main(["runs", "data", str(tmp_path / "refused")])
    assert not (tmp_path / "refused").exists()


def test_the_tool_measures_what_the_spec_registers():
    """The spec names the SHA-256 of the tool and of this test, and a later change shows here
    (a marked error fix updates it); the frozen values stand as it states them."""
    spec = (ROOT / pb.SPEC).read_text(encoding="utf-8")
    named = dict(re.findall(r"`((?:reports|tests)/[\w./-]+\.py)` `([0-9a-f]{64})`", spec))
    assert sorted(named) == [
        "reports/stage4-step4/tools/prompt_budget.py",
        "tests/test_stage4_step4_tools.py",
    ]
    for path, digest in named.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    for phrase in (
        "registered before the count",
        "Forecast, written before the count",
        "The smallest window without a detected loss",
        "5e308fe",
        "QA_PROMPT_V4",
    ):
        assert phrase in spec, phrase
    assert (pb.MAX_UNREAD, nr.TOP, pb.V4_BASES) == (5, 5, ("aircargo", "wixqa", "conditionalqa"))
    assert pb.OUT == ROOT / "reports/stage4-step4/5e308fe"
    assert set(nr.MEASURE_CODE) < set(pb.MEASURE_CODE)
    assert all((ROOT / name).is_file() for name in pb.MEASURE_CODE)
