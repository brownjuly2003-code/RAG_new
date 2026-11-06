"""Bundle 0: synthetic scores, documents and gold only; no services or private data."""

import copy
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/bundle0/tools/threshold_replay.py"
spec = importlib.util.spec_from_file_location("threshold_replay", TOOL)
tr = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tr
spec.loader.exec_module(tr)


@pytest.fixture
def tmp_path():
    # Inherit the workspace ACL: pytest's private-mode mkdir is inaccessible on this host.
    path = ROOT / ".tmp" / ("bundle0-test-" + uuid4().hex)
    path.mkdir(parents=True)
    return path


@pytest.mark.parametrize(
    "scores, threshold, expected",
    [
        ([0, 0.5, 1, 0.5], 0.5, [1, 2, 3]),
        ([0, 1], 0, [0, 1]),
        ([0, 1], 1, [1]),
        ([0.1, 0.2], 0.3, []),
        ([], 0, []),
    ],
)
def test_threshold_edges_ties_empty_and_original_order(scores, threshold, expected):
    assert tr.threshold_keep(scores, threshold) == expected


@pytest.mark.parametrize(
    "scores, expected",
    [
        ([1, 0.875, 0.25, 0.125, 0], [0, 1]),
        ([0.25, 1, 0.125, 0.875, 0], [1, 3]),
        ([1, 0.75, 0.5, 0.25, 0], [0, 1, 2, 3]),
        ([0.5] * 5, list(range(5))),
        ([1, 1, 0, 0, 0], [0, 1]),
        ([0], [0]),
        ([], []),
    ],
)
def test_largest_gap_and_longest_prefix_on_tied_gaps(scores, expected):
    assert tr.shape_keep(scores) == expected


@pytest.mark.parametrize("scores", [[float("nan")], [float("inf")], [-0.1], [1.1], [True]])
def test_invalid_scores_are_refused(scores):
    with pytest.raises(ValueError, match="score"):
        tr.shape_keep(scores)


def row(base="wixqa", h=True, arm=True, kept=1, gold=True):
    metric, secondary = tr.ar.nr.METRICS[base]

    def entry(hit, count):
        point = {metric: float(hit), secondary: float(hit)}
        return {
            "points": {"sent": point, "expanded": point},
            "unresolved": None,
            "documents": count,
            "sent_documents": count,
            "sent_est_tokens": 10 * count,
        }

    return {"base": base, "gold": gold, "H": entry(h, 5), "A": entry(arm, kept)}


def test_exact_mcnemar_keeps_empty_questions_and_counts_both_directions():
    rows = [row(h=True, arm=False, kept=0) for _ in range(6)]
    rows += [row(h=False, arm=True), row(), row(h=False, arm=False)]
    got = tr.comparison(rows, "A")
    assert got["sent"]["n"] == 9
    assert got["sent"]["b_h_only"] == 6
    assert got["sent"]["c_arm_only"] == 1
    assert got["sent"]["p"] == 0.125
    loss = tr.comparison(rows[:6], "A")["sent"]
    assert loss["p"] == 0.03125 and loss["reading"] == "loss"
    assert tr.comparison([row()], "A")["sent"]["p"] == 1


def candidate(p=0.05, zero=1, total=20):
    return {
        "per_base": {
            base: {
                "sent": {"n": 10, "p": p, "b_h_only": 6, "c_arm_only": 0},
                "unread": 0,
                "missing": 0,
                "usage": {"questions": total, "zero_kept": zero},
            }
            for base in tr.ar.DECIDING
        }
    }


def test_selection_checks_each_deciding_base_and_largest_grid_value():
    reads = {name: candidate() for name in tr.THRESHOLDS}
    names = list(tr.THRESHOLDS)
    reads[names[-1]]["per_base"]["wixqa"]["sent"]["p"] = 0.049999
    reads[names[-2]]["per_base"]["conditionalqa"]["usage"]["zero_kept"] = 2
    reads["A"] = candidate()
    chosen = tr.select(reads)
    assert chosen["threshold"] == tr.THRESHOLDS[names[-3]]
    assert chosen["A_eligible"] is True
    assert tr.eligible(candidate(p=0.05))
    assert not tr.eligible(candidate(p=0.049))
    assert not tr.eligible(candidate(total=0, zero=0))
    reads = {name: candidate(p=0.01) for name in tr.THRESHOLDS}
    reads["A"] = candidate(p=0.01)
    assert tr.select(reads)["threshold"] is None


@pytest.mark.parametrize("base", tr.ar.DECIDING)
def test_detected_gain_on_deciding_base_is_eligible(base):
    reading = candidate()
    reading["per_base"][base] = tr.comparison(
        [row(base=base, h=False, arm=True) for _ in range(6)], "A"
    )
    sent = reading["per_base"][base]["sent"]
    assert sent["p"] == 0.03125
    assert sent["c_arm_only"] == 6 and sent["b_h_only"] == 0
    assert tr.eligible(reading)
    chosen = tr.select({name: reading for name in (*tr.THRESHOLDS, "A")})
    assert chosen["threshold"] == max(tr.THRESHOLDS.values())
    assert chosen["A_eligible"] is True


@pytest.mark.parametrize("base", tr.ar.DECIDING)
def test_detected_loss_on_deciding_base_is_not_eligible(base):
    reading = candidate()
    reading["per_base"][base] = tr.comparison(
        [row(base=base, h=True, arm=False) for _ in range(6)], "A"
    )
    sent = reading["per_base"][base]["sent"]
    assert sent["p"] == 0.03125
    assert sent["b_h_only"] == 6 and sent["c_arm_only"] == 0
    assert not tr.eligible(reading)
    chosen = tr.select({name: reading for name in (*tr.THRESHOLDS, "A")})
    assert chosen["threshold"] is None
    assert chosen["A_eligible"] is False


def test_usage_denominators_include_questions_without_gold_and_empty_keep():
    rows = [row(kept=0, arm=False), row(kept=2, gold=False)]
    got = tr.comparison(rows, "A")
    assert got["sent"]["n"] == 1
    assert got["usage"]["questions"] == 2
    assert got["usage"]["zero_kept"] == 1
    assert got["usage"]["sent_documents"] == {"mean": 1, "median": 1}
    assert got["usage"]["sent_est_tokens"] == {"mean": 10, "median": 10}
    rows[0]["A"] = None
    assert tr.comparison(rows, "A")["sent"] == tr.ar.NOT_EVIDENCE


@pytest.mark.parametrize("field", ["points", "sent_documents", "prompt"])
def test_parity_refuses_a_changed_h(field):
    reference = {"label": "p2-wixqa", "case_id": "q0", **row()}
    reference["H"]["prompt"] = {"sha256": "a" * 64}
    actual = copy.deepcopy(reference)
    tr.parity_gate(actual, reference)
    actual["H"][field] = None
    with pytest.raises(tr.ParityError):
        tr.parity_gate(actual, reference)


@pytest.mark.parametrize(
    "payload",
    [{"nested": {"text": "synthetic body"}}, {"page_content": "x"}, {"source": "doc.md"}],
)
def test_text_fields_are_refused_before_any_output(tmp_path, payload):
    with pytest.raises(SystemExit, match="text"):
        tr.write_results(tmp_path / "out", payload, [], set(), [])
    assert not (tmp_path / "out").exists()


def test_stage2_text_guard_is_used_and_outputs_are_lf(tmp_path):
    with pytest.raises(SystemExit, match="text"):
        tr.write_results(tmp_path / "bad", {"case_id": "secret.md"}, [], {"secret.md"}, [])
    with pytest.raises(SystemExit, match="text"):
        tr.write_results(
            tmp_path / "bad", {}, [{"case_id": "a private question"}], set(), ["private question"]
        )
    tr.write_results(tmp_path / "good", {"n": 1}, [{"case_id": "q0"}], set(), [])
    assert json.loads((tmp_path / "good/record.json").read_bytes()) == {"n": 1}
    assert b"\r" not in (tmp_path / "good/rows.jsonl").read_bytes()


def test_grader_uses_product_parser_and_preserves_order():
    assert tr.grade_keep('{"grades":[false,true,false,true,false]}', 5) == [1, 3]
    assert tr.grade_keep("malformed", 5) == []  # Codex batch fails closed.


def test_g_requires_exact_input_and_one_complete_bound_capture():
    from agent.prompts import build_doc_grade_batch_prompt

    docs = [SimpleNamespace(page_content="Synthetic body", metadata={"source": "d0"})]
    prompt = build_doc_grade_batch_prompt(
        "Synthetic question?",
        [{"page_content": docs[0].page_content, "metadata": docs[0].metadata}],
    ).strip()
    call = SimpleNamespace(
        start={"active_case": json.dumps({"key": "wixqa", "case_id": "q0"})},
        prompt=prompt,
        errors=[],
        stop_reasons=[],
        driver_errors=[],
        spawned={},
        end={"exit_code": 0, "capture_ok": True},
        output=SimpleNamespace(accepted=True, text='{"grades":[true]}'),
    )
    args = ("wixqa", "q0", "Synthetic question?", docs)
    assert tr.recorded_grade([call], *args) == ([0], "matched")
    assert tr.recorded_grade([call, call], *args) == (None, "ambiguous")
    call.end = None
    assert tr.recorded_grade([call], *args) == (None, "incomplete")
    call.prompt += " changed document"
    assert tr.recorded_grade([call], *args) == (None, "unmatched")


def test_real_replay_on_synthetic_pool_and_gold():
    ar = tr.ar
    chunks = [
        {"page_content": f"[d{i}]\nSynthetic document {i}.", "metadata": {"source": f"d{i}"}}
        for i in range(6)
    ]
    settings = {
        "retrieval_top_k": 14,
        "rerank_top_k": 5,
        "rrf_k": 60,
        "rrf_doc_key_chars": 200,
        "chunk_overlap": 0,
        "parent_expansion_window": 0,
        "parent_expansion_max_chars": 3600,
    }
    inputs = {
        "label": "p2-wixqa",
        "base": "wixqa",
        "chunks": chunks,
        "settings": settings,
        "tenant": "synthetic",
        "cases": {"q0": {"gold_sources": ["d4"]}},
        "gold_of": {
            "places": SimpleNamespace(source=[f"d{i}" for i in range(6)]),
            "sources": None,
            "chunks": chunks,
        },
    }
    record = {
        "case_id": "q0",
        "index": 0,
        "question": "Synthetic question?",
        "lanes": {"vector": [[f"d{i}", i] for i in range(6)], "bm25": []},
    }
    machine = ar.new_machine(inputs, None)
    # Obtain the product's fusion order; no index or model is consulted.
    pool = machine.hybrid._rrf_merge(machine.docs, [])
    scored = {
        "pool": [d.metadata["chunk_index"] for d in pool],
        "scores": [0.9375, 0.875, 0.25, 0.125, 0.0625, 0],
        "five": list(range(5)),
    }
    builder = ar.Builder()
    actual = tr.control_row(inputs, record, scored, machine, builder)
    assert actual["H"]["points"]["sent"]["gold_article"] == 1
    result = tr.evaluate_question(inputs, record, scored, machine, builder, actual, [])
    assert result["H"] == actual["H"]
    assert result["A"]["points"]["sent"]["gold_article"] == 0
    assert result["A"]["kept_indices"] == [0, 1]
    assert result["T20"]["documents"] == result["T20"]["sent_documents"] == 0
    assert result["T20"]["points"]["sent"]["gold_article"] == 0
    assert result["T00"]["points"] == result["H"]["points"]
    assert result["G"] is None


def test_missing_frozen_input_refuses_before_replay(tmp_path):
    with pytest.raises(SystemExit, match="frozen input"):
        tr.require_hash(tmp_path / "absent.jsonl", "0" * 64)


def test_registered_hashes_and_rules():
    text = (ROOT / tr.SPEC).read_text(encoding="utf-8")
    for path in (TOOL, Path(__file__)):
        assert f"`{path.relative_to(ROOT).as_posix()}` `{tr.ar.sha256(path)}`" in text
    assert list(tr.THRESHOLDS.values()) == [i / 20 for i in range(21)]
    for path, digest in tr.FROZEN.items():
        assert f"`{path}` `{digest}`" in text
