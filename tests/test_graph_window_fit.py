"""Graph nodes fit their prompts into a local model's input window.

The fakes declare ``context_window`` like OllamaProvider does; every recorded
prompt is checked against the limit its role leaves after the output budget.
"""

from __future__ import annotations

from typing import Any

import pytest

import agent.graph as graph
from agent.context_window import prompt_input_tokens
from agent.prompts import build_doc_grade_batch_prompt, build_doc_grade_prompt
from agent.state import create_initial_state
from llm.providers.base import LLMResponse, window_input_limit

QUESTION = "Как подать претензию о повреждении груза?"
_SENTENCES = (
    "Груз принимается к перевозке после проверки документов и взвешивания.",
    "Отправитель отвечает за правильность сведений в авиагрузовой накладной.",
    "Опасные грузы декларируются отдельно и упаковываются по инструкции.",
    "Хранение на складе сверх бесплатного срока оплачивается по тарифу.",
    "Претензия о повреждении груза подаётся в письменной форме.",
)


def _doc(index: int) -> dict:
    paragraphs = [
        f"Раздел {index}.{part}. " + " ".join(_SENTENCES[(index + part + k) % 5] for k in range(5))
        for part in range(1, 9)
    ]
    return {
        "page_content": "\n\n".join(paragraphs),
        "metadata": {"source": f"rules-{index}.md", "doc_id": f"doc-{index}"},
    }


@pytest.fixture(autouse=True)
def _quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph, "log_step", lambda *args, **kwargs: None)
    monkeypatch.setattr(graph, "trace_llm_call", lambda **kwargs: None)


class _WindowedLLM:
    context_window = 4096

    def __init__(self, replies: list[str] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._replies = list(replies or [])

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        self.calls.append((prompt, kwargs))
        return self._replies.pop(0) if self._replies else "YES"


def _assert_fits(prompt: str, kwargs: dict[str, Any], schema: dict | None = None) -> None:
    assert prompt_input_tokens(prompt, schema) <= window_input_limit(4096, kwargs["max_tokens"])


def test_generate_keeps_instructions_and_leading_documents_within_the_window():
    llm = _WindowedLLM(["Претензию подают письменно [1]."])
    state = create_initial_state(question=QUESTION, trace_id="window-generate")
    docs = [_doc(i) for i in range(1, 6)]
    state["graded_docs"] = docs

    out = graph.make_generate_node(llm, llm)(state)

    assert not out.get("error")
    ((prompt, kwargs),) = llm.calls
    _assert_fits(prompt, kwargs)
    assert kwargs["max_tokens"] == 1024
    assert "You are a support assistant" in prompt and QUESTION in prompt
    seen = out["generation_context_docs"]
    assert 1 <= len(seen) < 5
    assert seen[0] == docs[0]
    assert [c["doc_id"] for c in out["citations"]] == [f"doc-{i}" for i in range(1, len(seen) + 1)]
    assert "rules-5.md" not in prompt
    # The graded documents themselves are not rewritten.
    assert state["graded_docs"] == [_doc(i) for i in range(1, 6)]


def test_generate_drops_old_history_before_the_top_document():
    llm = _WindowedLLM(["Ответ [1]."])
    state = create_initial_state(question=QUESTION, trace_id="window-history")
    state["graded_docs"] = [_doc(1)]
    state["chat_history"] = [
        {
            "role": "user" if turn % 2 == 0 else "assistant",
            "content": f"Реплика {turn}. " + " ".join(_SENTENCES) * 6,
        }
        for turn in range(6)
    ]

    out = graph.make_generate_node(llm, llm)(state)

    ((prompt, kwargs),) = llm.calls
    _assert_fits(prompt, kwargs)
    assert "Реплика 5." in prompt and "Реплика 1." not in prompt
    assert out["generation_context_docs"] == [_doc(1)]


def test_model_without_window_gets_the_whole_context():
    calls: list[str] = []

    class _Plain:
        def invoke(self, prompt: str, **kwargs: Any) -> str:
            calls.append(prompt)
            return "Ответ [1]."

    state = create_initial_state(question=QUESTION, trace_id="window-none")
    state["graded_docs"] = [_doc(i) for i in range(1, 6)]

    out = graph.make_generate_node(_Plain(), _Plain())(state)

    assert "rules-5.md" in calls[0]
    assert len(out["generation_context_docs"]) == 5


def test_batch_grading_shows_every_document_within_the_window():
    seen: list[tuple[str, dict, dict]] = []

    class _Grader(_WindowedLLM):
        supports_structured_output = True

        def generate_with_schema(self, messages, schema, **kwargs):
            seen.append((messages[0]["content"], schema, kwargs))
            grades = [{"index": i, "relevant": True} for i in range(1, 6)]
            return LLMResponse(
                text="{}", provider="t", model="t", structured_output={"grades": grades}
            )

    state = create_initial_state(question=QUESTION, trace_id="window-grade")
    docs = [_doc(i) for i in range(1, 6)]
    state["context_docs"] = docs

    out = graph.make_grade_docs_node(_Grader())(state)

    ((prompt, schema, kwargs),) = seen
    assert kwargs["max_tokens"] == 256 and kwargs["temperature"] == 0.0
    _assert_fits(prompt, kwargs, schema)
    assert all(f"[{i}] source=rules-{i}.md" in prompt for i in range(1, 6))
    # Grading sees views; generation gets the full documents back.
    assert out["graded_docs"] == docs


def test_single_document_grading_fits_each_prompt():
    llm = _WindowedLLM(["???"] + ["YES"] * 5)
    state = create_initial_state(question=QUESTION, trace_id="window-grade-single")
    state["context_docs"] = [
        {**_doc(i), "page_content": _doc(i)["page_content"] * 4} for i in (1, 2)
    ]

    out = graph.make_grade_docs_node(llm)(state)

    batch, *singles = llm.calls
    assert len(singles) == 2
    for prompt, kwargs in llm.calls:
        _assert_fits(prompt, kwargs)
    assert len(out["graded_docs"]) == 2


def test_batch_over_the_window_is_graded_one_document_at_a_time():
    docs = [_doc(i) for i in range(1, 31)]
    empty = [{**doc, "page_content": ""} for doc in docs]
    limit = window_input_limit(900, 256)
    # The batch leaves less than a token per document; one document fits.
    batch_floor = prompt_input_tokens(
        build_doc_grade_batch_prompt(question=QUESTION, documents=empty)
    )
    assert limit - batch_floor < len(docs)
    assert limit > prompt_input_tokens(build_doc_grade_prompt(question=QUESTION, document=empty[0]))
    llm = _WindowedLLM()
    llm.context_window = 900
    state = create_initial_state(question=QUESTION, trace_id="window-grade-fallback")
    state["context_docs"] = docs

    out = graph.make_grade_docs_node(llm)(state)

    assert len(llm.calls) == len(docs)
    assert all(prompt_input_tokens(prompt) <= limit for prompt, _ in llm.calls)
    assert out["graded_docs"] == docs
    assert not out.get("error")


def test_a_grading_prompt_that_cannot_fit_the_window_is_a_node_error():
    doc = _doc(1)
    assert window_input_limit(512, 256) < prompt_input_tokens(
        build_doc_grade_prompt(question=QUESTION, document={**doc, "page_content": ""})
    )
    llm = _WindowedLLM()
    llm.context_window = 512
    state = create_initial_state(question=QUESTION, trace_id="window-grade-refused")
    state["context_docs"] = [doc]

    out = graph.make_grade_docs_node(llm)(state)

    # Not a document rejected by fail-closed grading: the request escalates.
    assert out["error"] is True and out["error_node"] == "grade_docs"
    assert "input window" in out["error_message"]
    assert llm.calls == []


@pytest.mark.parametrize("window", [4096, None])
def test_a_batch_prompt_that_cannot_be_built_is_a_node_error(
    monkeypatch: pytest.MonkeyPatch, window: int | None
):
    def broken(**kwargs: Any) -> str:
        raise RuntimeError("broken batch template")

    monkeypatch.setattr(graph, "build_doc_grade_batch_prompt", broken)
    llm = _WindowedLLM()
    llm.context_window = window  # type: ignore[assignment]
    state = create_initial_state(question=QUESTION, trace_id="window-grade-broken")
    state["context_docs"] = [_doc(1), _doc(2)]

    out = graph.make_grade_docs_node(llm)(state)

    assert out["error"] is True and out["error_node"] == "grade_docs"
    assert "broken batch template" in out["error_message"]
    assert llm.calls == []


def test_verify_facts_checks_claims_against_the_generator_view():
    llm = _WindowedLLM(
        [
            "- Претензия подаётся в письменной форме.",
            "SUPPORTED: Претензия о повреждении груза подаётся в письменной форме.",
        ]
    )
    state = create_initial_state(question=QUESTION, trace_id="window-verify")
    state["answer"] = "Претензия подаётся в письменной форме [1]."
    state["graded_docs"] = [{**_doc(1), "page_content": _doc(1)["page_content"] + " UNSEEN_TAIL"}]
    state["generation_context_docs"] = [_doc(1)]

    out = graph.make_verify_facts_node(llm)(state)

    _extract, (verify_prompt, kwargs) = llm.calls
    assert "UNSEEN_TAIL" not in verify_prompt
    _assert_fits(verify_prompt, kwargs)
    assert len(out["claims"]) == 1


def test_verify_facts_fits_long_evidence_to_the_verifier_window():
    llm = _WindowedLLM(["- Претензия подаётся в письменной форме.", "SUPPORTED: да"])
    state = create_initial_state(question=QUESTION, trace_id="window-verify-long")
    state["answer"] = "Претензия подаётся в письменной форме [1]."
    state["generation_context_docs"] = [_doc(i) for i in range(1, 6)]

    graph.make_verify_facts_node(llm)(state)

    for prompt, kwargs in llm.calls:
        _assert_fits(prompt, kwargs)


def test_evaluate_judges_the_generator_view_within_its_window(monkeypatch: pytest.MonkeyPatch):
    import types

    judge = _WindowedLLM(['{"score": 90, "reason": "ok"}'])
    monkeypatch.setattr(
        graph,
        "resolve_judge_llm",
        lambda **kwargs: types.SimpleNamespace(
            ok=True,
            judge_llm=judge,
            independent=True,
            reason="test",
            judge_provider="test",
            judge_model="test",
        ),
    )
    state = create_initial_state(question=QUESTION, trace_id="window-eval")
    state["answer"] = "Претензия подаётся в письменной форме [1]."
    state["graded_docs"] = [{"page_content": "UNSEEN_ORIGINAL " * 600}]
    state["generation_context_docs"] = [_doc(i) for i in range(1, 6)]

    out = graph.make_evaluate_node(judge, judge)(state)

    ((prompt, kwargs),) = judge.calls
    assert out["quality_score"] == 90
    assert "UNSEEN_ORIGINAL" not in prompt and "Раздел 1.1." in prompt
    _assert_fits(prompt, kwargs)


def test_rewrite_clears_the_previous_generation_view():
    llm = _WindowedLLM(["претензия повреждение груза"])
    state = create_initial_state(question=QUESTION, trace_id="window-rewrite")
    state["answer"] = "Не знаю."
    state["generation_context_docs"] = [_doc(1)]

    out = graph.make_rewrite_query_node(llm)(state)

    assert out["generation_context_docs"] is None


def test_structured_calls_carry_the_role_budget():
    seen: list[dict] = []

    class _Schema:
        def generate_with_schema(self, messages, schema, **kwargs):
            seen.append(kwargs)
            return LLMResponse(text="{}", provider="t", model="t", structured_output={"ok": True})

    schema = {"type": "object"}
    assert graph._invoke_with_schema(_Schema(), "p", schema, role="grade") == {"ok": True}
    assert graph._invoke_with_schema(_Schema(), "p", schema, role="verify", x=1)
    graph._invoke_with_schema(_Schema(), "p", schema)
    assert seen == [
        {"temperature": 0.0, "max_tokens": 256},
        {"temperature": 0.0, "max_tokens": 512, "x": 1},
        {},
    ]
