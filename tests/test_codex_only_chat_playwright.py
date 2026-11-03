"""Codex-only handover through the live app, real graph, CLI and SSE projection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests._fake_codex import ANSWER
from tests._fake_codex import fake_codex as fake_codex
from tests.test_chat_operator_offer_playwright import (
    HANDOVER_NOTE,
    SESSION_ID,
    STREAM_PATHS,
    _ask,
)
from tests.test_chat_operator_offer_playwright import chat_stand as chat_stand
from tests.test_codex_answer_e2e import QUESTION

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright  # noqa: E402


def test_codex_auto_has_handover_without_quality_or_automatic_ticket(chat_stand, fake_codex):
    grades = json.dumps({"grades": [{"index": i, "relevant": True} for i in range(1, 4)]})
    fake_codex.configure(
        prompt_events={
            '"grades"': [
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": grades},
                },
                {"type": "turn.completed", "usage": {}},
            ]
        }
    )
    with sync_playwright() as playwright:
        if not Path(playwright.chromium.executable_path).is_file():
            pytest.skip("Playwright Chromium is not installed")
        browser = playwright.chromium.launch()
        try:
            stand = chat_stand(600.0, codex=fake_codex)
            page = browser.new_page()
            streams = _ask(page, stand.base, QUESTION)
            message = page.locator(".message.bot", has=page.locator(".answer-handover"))
            message.wait_for(timeout=60_000)

            assert len(streams) == 1 and streams[0].endswith(STREAM_PATHS), streams
            expect(message).to_contain_text(ANSWER)
            expect(message.locator(".badge-route")).to_have_text("Маршрут: auto")
            expect(message.locator(".badge-quality")).to_have_count(0)
            expect(message.locator(".btn-escalate-action")).to_have_count(0)
            line = message.locator(".answer-handover")
            expect(line).to_be_visible()
            expect(line).to_contain_text(HANDOVER_NOTE)
            button = line.locator(".btn-handover")
            expect(button).to_have_text("Передать оператору")
            assert len(fake_codex.records()) == 3  # Transform, batch grade, answer; no judge.
            assert stand.escalations == []

            button.click()
            page.wait_for_selector("#escalateModal.active")
            assert stand.escalations == []
            page.click("#escalateConfirm")
            page.locator(".message.bot", has_text="Запрос передан оператору.").wait_for()
            (escalation,) = stand.escalations
            assert escalation["question"] == QUESTION
            assert escalation["reason"] == "route=auto"
            assert escalation["source"] == "manual"
            assert escalation["session_id"] == SESSION_ID
        finally:
            browser.close()
