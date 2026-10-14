"""fit_context_docs: which documents a windowed model sees, and in what form."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.context_window import (
    _cut_to_tokens,
    _excerpt,
    fit_context_docs,
    prompt_input_limit,
    prompt_input_tokens,
)
from llm.providers.base import estimate_window_tokens

QUESTION = "Как подать претензию о повреждении груза?"


def _doc(index: int, paragraphs: int = 6) -> dict:
    body = "\n\n".join(
        f"Раздел {index}.{part}. Условия хранения груза на складе аэропорта и порядок выдачи "
        "получателю после оплаты сборов. Сроки бесплатного хранения указаны в тарифе перевозчика."
        for part in range(1, paragraphs + 1)
    )
    return {
        "page_content": body,
        "metadata": {"doc_id": f"doc-{index}", "source": f"rules-{index}.md"},
    }


def _build(docs: list[dict]) -> str:
    context = "\n\n".join(f"[Документ {i}]\n{doc['page_content']}" for i, doc in enumerate(docs, 1))
    return f"Отвечай только по документам.\n\n{context}\n\nВопрос: {QUESTION}"


def test_model_without_window_gets_every_document():
    docs = [_doc(i) for i in range(1, 6)]
    assert fit_context_docs(SimpleNamespace(), QUESTION, docs, _build, role="generate") is docs
    assert (
        fit_context_docs(
            SimpleNamespace(context_window=None), QUESTION, docs, _build, role="generate"
        )
        is docs
    )


def test_leading_documents_are_kept_whole_and_the_next_one_is_cut():
    llm = SimpleNamespace(context_window=2048)
    limit = prompt_input_limit(llm, "generate")
    docs = [_doc(i) for i in range(1, 6)]
    # The setup: two documents fit, a third does not.
    assert prompt_input_tokens(_build(docs[:2])) <= limit < prompt_input_tokens(_build(docs[:3]))

    fitted = fit_context_docs(llm, QUESTION, docs, _build, role="generate")

    assert fitted[:2] == docs[:2]
    assert len(fitted) == 3
    assert fitted[2]["metadata"] == docs[2]["metadata"]
    assert fitted[2]["page_content"].startswith("Раздел 3.1.")
    assert len(fitted[2]["page_content"]) < len(docs[2]["page_content"])
    assert prompt_input_tokens(_build(fitted)) <= limit


def test_role_output_budget_sets_the_room_left_for_documents():
    llm = SimpleNamespace(context_window=2048)
    docs = [_doc(i) for i in range(1, 6)]
    generate = fit_context_docs(llm, QUESTION, docs, _build, role="generate")
    evaluate = fit_context_docs(llm, QUESTION, docs, _build, role="evaluate")
    # evaluate reserves 128 output tokens, generate 1024.
    assert len(evaluate) > len(generate)


def test_instructions_that_do_not_fit_are_refused():
    llm = SimpleNamespace(context_window=1200)

    def huge_instructions(docs: list[dict]) -> str:
        return "Правило ответа. " * 400 + _build(docs)

    with pytest.raises(ValueError, match="input window"):
        fit_context_docs(llm, QUESTION, [_doc(1)], huge_instructions, role="generate")


def test_excerpt_keeps_the_paragraphs_that_share_the_question_terms():
    text = "\n\n".join(
        [
            "Тарифы на хранение грузов на складе меняются ежегодно. " * 6,
            "Претензия о повреждении груза подаётся в письменной форме в течение 14 дней.",
            "Опасные грузы принимаются только с декларацией отправителя. " * 6,
        ]
    )
    excerpt = _excerpt(text, QUESTION, 60)
    assert "Претензия о повреждении груза" in excerpt
    assert estimate_window_tokens(excerpt) <= 60


def test_faq_block_is_cut_at_the_matching_question_not_at_its_header():
    block = "\n".join(
        [
            "[Контекст: Справочник отправителя > Претензии и повреждения груза]",
            "Вопрос: Как упаковать хрупкий груз?",
            "Ответ: Используйте жёсткую тару и наполнитель. " * 8,
            "Вопрос: Как подать претензию о повреждении груза?",
            "Ответ: Направьте письменную претензию с актом осмотра в течение 14 дней.",
        ]
    )
    excerpt = _excerpt(block, QUESTION, 45)
    assert excerpt.startswith("Вопрос: Как подать претензию о повреждении груза?")
    assert "актом осмотра" in excerpt


def test_cut_to_tokens_returns_the_longest_fitting_prefix():
    text = "Груз принят на склад 14.10.2026, вес 1250 кг, мест 3. " * 10
    cut = _cut_to_tokens(text, 50)
    assert text.startswith(cut)
    assert estimate_window_tokens(cut) <= 50 < estimate_window_tokens(text[: len(cut) + 1])
