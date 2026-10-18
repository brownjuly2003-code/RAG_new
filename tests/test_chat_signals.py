"""scripts/chat_signals.py: the handover signals on chat answers, through the widget's own nodes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.prompts import build_qa_prompt
from config.settings import get_settings
from llm.providers.base import flatten_messages
from scripts import chat_signals as signals

DOCS = [
    {
        "page_content": "[Fees › Storage]\nStorage costs ten a day.",
        "metadata": {"source": "fees.md"},
    },
    {"page_content": "Claims are filed within 14 days.", "metadata": {"source": "claims.md"}},
]
QUESTION = "How much is storage?"


def _run(folder: Path) -> Path:
    """Two answered cases as the stand records them: prompts, cases, the rerank before each."""
    (folder / "prompts").mkdir(parents=True)
    (folder / "cases").mkdir()
    (folder / "launch.json").write_text(json.dumps({"code_sha": "abc", "tenant": "toy"}), "utf-8")
    cases = [
        ("q1", QUESTION, "Storage costs ten a day [1].", 100, ["fees.md", "claims.md"]),
        ("q2", "Who signs the claim?", "По имеющимся данным ответить нельзя.", 60, ["claims.md"]),
    ]
    stages = []
    for index, (case_id, question, answer, quality, ranked) in enumerate(cases, start=1):
        name = f"{2 * index - 1:03d}-stream.txt"
        prompt = flatten_messages([{"role": "user", "content": build_qa_prompt(question, DOCS)}])
        (folder / "prompts" / name).write_text(prompt, "utf-8")
        result = {
            "type": "result",
            "answer": answer,
            "route": "auto",
            "quality_score": quality,
            "quality_source": "llm",
        }
        row = {"case_id": case_id, "question": question, "answer": answer, "events": [result]}
        (folder / "cases" / f"{index:02d}-{case_id}.json").write_text(json.dumps(row), "utf-8")
        stages.append(
            {
                "stage": "hybrid._rerank_scored_with_status",
                "event": "end",
                "reranker_ok": True,
                "scores": [0.91, 0.12][: len(ranked)],
                "sources": ranked,
            }
        )
        stages.append({"stage": "ollama.generate_stream", "event": "start", "prompt_file": name})
    (folder / "stages.jsonl").write_text("".join(json.dumps(s) + "\n" for s in stages), "utf-8")
    return folder


def test_the_plan_freezes_the_signals_without_a_model_and_holds_no_text(tmp_path: Path) -> None:
    plan = signals.build_plan({"toy": _run(tmp_path / "run")}, "abc")

    first, second = plan["items"]
    assert (first["S1"], first["S1p"], first["S5"]) == (False, False, False)
    assert first["S7"] == {"status": "ok", "top_score": 0.91}
    # The second answer declines in the V2 prompt's words and scored 60; its prompt holds two
    # documents but the rerank recorded one: S7 does not read a score it cannot tie to them.
    assert (second["S1"], second["S1p"], second["S5"]) == (True, True, True)
    assert second["S7"] == {"status": "order_differs", "top_score": None}
    text = json.dumps(plan, ensure_ascii=False)
    for secret in (QUESTION, "Storage costs ten a day", "ответить нельзя."):
        assert secret not in text


def test_the_model_signals_come_from_the_widget_nodes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import agent.graph as graph

    monkeypatch.setattr(graph, "trace_llm_call", lambda **kwargs: None)
    monkeypatch.setattr(graph, "log_step", lambda trace_id, node_name, state: None)

    class FakeModel:
        """The 4B's three replies: the batch grade, the claims, one claim's verdict."""

        def __init__(self) -> None:
            self.replies = iter(
                [
                    json.dumps(
                        {
                            "grades": [
                                {"index": 1, "relevant": True},
                                {"index": 2, "relevant": False},
                            ]
                        }
                    ),
                    "- Storage costs ten a day.",
                    "SUPPORTED: Storage costs ten a day.",
                ]
            )

        def invoke(self, prompt: str, **kwargs: object) -> str:
            return next(self.replies)

    plan = signals.build_plan({"toy": _run(tmp_path / "run")}, "abc")
    item = plan["items"][0]
    prompt = (tmp_path / "run" / "prompts" / item["prompt_file"]).read_text("utf-8")
    model = FakeModel()
    route, min_relevance = signals._route_node(get_settings())

    row = signals.model_signals(
        item,
        QUESTION,
        "Storage costs ten a day [1].",
        signals._documents(prompt),
        graph.make_grade_docs_node(model),
        graph.make_verify_facts_node(model),
        route,
        min_relevance,
    )

    assert row["S2"]["grounding_status"] == "verified" and not row["S2"]["marked"]
    assert row["S3"] == {"claims": [{"supported": True, "cited": True}], "marked": False}
    assert (row["S4"]["kept"], row["S4"]["documents"], row["S4"]["relevance"]) == (1, 2, 0.5)
    assert row["S4"]["marked"]
    # Half the documents kept is below the route's relevance floor: the first pass retries.
    assert row["S6"]["route"] == "retry" and row["S6"]["marked"]
    assert row["node_errors"] == []


def test_the_summary_counts_what_each_signal_catches(tmp_path: Path) -> None:
    plan = signals.build_plan({"toy": _run(tmp_path / "run")}, "abc")
    rows = [
        {
            "kind": "answer",
            "item": 1,
            "S2": {"marked": False},
            "S3": {"marked": False},
            "S4": {"marked": True},
            "S6": {"marked": True},
            "seconds": {"total": 120.0},
        }
    ]
    judged = {("toy", "q1"): ("good", False), ("toy", "q2"): ("good", True)}

    summary = signals.summarize(plan, rows, judged=judged, s7_threshold=0.5)

    assert summary["with_model_signals"] == 1 and summary["added_seconds_median"] == 120.0
    s5 = summary["signals"]["S5"]
    # The decline needs a person though the judge calls it good: S5 catches it, marks no other.
    assert (s5["target"], s5["caught"], s5["over_marked"]) == (1, 1, 0)
    assert summary["signals"]["S4"]["computed"] == 1
    assert summary["signals"]["S4"]["over_marked"] == 1
    assert summary["signals"]["S7"] == {
        "computed": 1,
        "marked": 0,
        "target": 0,
        "caught": 0,
        "caught_wilson95": None,
        "good_not_declining": 1,
        "over_marked": 0,
        "over_marked_wilson95": [0.0, 0.7935],
    }


def test_wilson_bounds() -> None:
    assert signals.wilson(0, 0) is None
    low, high = signals.wilson(10, 20)
    assert low < 0.5 < high
