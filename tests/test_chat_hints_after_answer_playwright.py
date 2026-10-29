"""The chat shows an answer, and gives the input back, before the model has written its
suggested questions; they come after it on the same stream and join the same answer
(PLAN.md stage 4, item 4).

The stand of ``tests/test_chat_operator_offer_playwright.py``: Chromium drives
``/static/chat.html`` against a live uvicorn of ``api.app``, and the chat's stream runs
its real path to a fake Ollama. The model answers at once and scores the first answer
90, routed ``auto``; the call that writes its suggested questions stays silent for
``HINTS_AFTER_SEC``. While it is silent the answer is on screen with its route and
handover line, the send button is enabled, and a second question — scored 40, routed
``human``, so it gets no suggestions — is asked and answered. Then the suggestions
appear under the first answer, where ``addMessage`` puts them, and a click on one asks
it. Before, the chat drew nothing until the suggestions were written: 13 s of the 4B's
answer on the Mac (``reports/chat-live-4b/19beeb1``). Requires Python Playwright and
Chromium and skips without them; a skip is not evidence — run it with ``-rs``.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests import _fake_ollama

pytest.importorskip("playwright.sync_api")
pytest.importorskip("langchain_ollama")
from playwright.sync_api import expect, sync_playwright  # noqa: E402

from tests.test_chat_operator_offer_playwright import (  # noqa: E402
    SELF_EVAL_MARKER,
    STREAM_PATHS,
    SUGGESTIONS_MARKER,
    _ask,
)
from tests.test_chat_operator_offer_playwright import chat_stand as chat_stand  # noqa: E402

FIRST_QUESTION = "Куда отправить акт о повреждении груза?"
SECOND_QUESTION = "Как подать претензию о повреждении груза?"
HINTS = ["Какие документы приложить к акту?", "Сколько ждать ответа перевозчика?"]
QUESTIONS = (FIRST_QUESTION, SECOND_QUESTION, HINTS[0])
ANSWERS = {
    FIRST_QUESTION: "Акт отправляют перевозчику вместе с претензией [1].",
    SECOND_QUESTION: "Претензию подают в письменной форме перевозчику [1].",
    HINTS[0]: "К акту прикладывают накладную и фотографии груза [1].",
}
# How long the model stays silent before it writes the suggested questions.
HINTS_AFTER_SEC = 15.0


def _reply(payload: dict[str, Any]) -> _fake_ollama.Reply:
    prompt = str(payload.get("prompt") or "")
    if SUGGESTIONS_MARKER in prompt:
        return _fake_ollama.Reply(["\n".join(HINTS)], first_token_after=HINTS_AFTER_SEC)
    # The question a prompt is about comes after the conversation's history.
    current = max(QUESTIONS, key=prompt.rfind)
    if SELF_EVAL_MARKER in prompt:
        return _fake_ollama.Reply(["90" if current == FIRST_QUESTION else "40"])
    return _fake_ollama.Reply([ANSWERS[current]])


def _hints_calls(stand: Any) -> list[dict[str, Any]]:
    return [r for r in stand.fake.requests if SUGGESTIONS_MARKER in str(r["payload"].get("prompt"))]


def _answer(page: Any, question: str) -> Any:
    """The answer as the result event draws it: the streamed bubble carries no badges."""
    text = ANSWERS[question].removesuffix(" [1].")
    return page.locator(".message.bot", has=page.locator(".badge-route"), has_text=text)


def test_the_answer_and_the_input_come_before_the_suggested_questions(chat_stand) -> None:
    stand = chat_stand(600.0, reply=_reply)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            streams = _ask(page, stand.base, FIRST_QUESTION)
            first = _answer(page, FIRST_QUESTION)
            first.wait_for(timeout=60_000)

            # On screen while the model has not answered the suggestions' call.
            assert all(r["sent_after"] == [] for r in _hints_calls(stand)), _hints_calls(stand)
            assert first.locator(".badge-route").inner_text() == "Маршрут: auto"
            expect(first.locator(".answer-handover")).to_be_visible()
            assert first.locator(".suggested-questions").count() == 0
            expect(page.locator("#sendBtn")).to_be_enabled()

            # The input is back: a second question is taken while that call is silent.
            page.fill("#questionInput", SECOND_QUESTION)
            page.press("#questionInput", "Enter")
            expect(page.locator(".message.user", has_text=SECOND_QUESTION)).to_be_visible()
            assert all(r["sent_after"] == [] for r in _hints_calls(stand)), _hints_calls(stand)
            second = _answer(page, SECOND_QUESTION)
            second.wait_for(timeout=60_000)
            assert second.locator(".badge-route").inner_text() == "Маршрут: human"

            # The suggestions join the first answer, under its sources and above its
            # feedback, and no other message.
            chips = first.locator(".suggested-questions .btn-suggested")
            expect(chips).to_have_text(HINTS, timeout=(HINTS_AFTER_SEC + 30) * 1000)
            assert page.locator(".suggested-questions").count() == 1
            order = ".message-sources + .suggested-questions + .msg-feedback"
            assert first.locator(order).count() == 1
            assert len(_hints_calls(stand)) == 1

            # A suggestion that came late asks itself on a click, as one drawn with its answer.
            chips.first.click()
            expect(page.locator(".message.user", has_text=HINTS[0])).to_be_visible()
            _answer(page, HINTS[0]).wait_for(timeout=60_000)
        finally:
            browser.close()

    assert len(streams) == 3 and all(s.endswith(STREAM_PATHS) for s in streams), streams
    assert len(_hints_calls(stand)) == 1
