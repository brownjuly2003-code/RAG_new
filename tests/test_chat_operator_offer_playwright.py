"""The web chat offers the operator when an answer did not come in time or was
routed to a human (ROADMAP, thread M, step 2; Julia, 2026-10-15).

Chromium drives ``/static/chat.html`` against a live uvicorn of ``api.app``.
The chat's stream runs its real path — a real ``ConversationSession`` with a
fake retriever and no LLM, as production builds it, the real provider runtime,
langchain-ollama and the ollama client — to a fake Ollama server in this test.
The timeout is reached for real: the test sets ``REQUEST_TIMEOUT_SEC`` to 8 s
and the model stays silent past it, so the stream's read times out, the graph
fallback finds the deadline spent and the client gets the apology routed
``timeout``, as the chat on the production Mac did on 2026-10-14. An answer
the model scores 40, below the threshold of 80, comes back routed ``human``.
Neither opens a ticket by itself; the button does, through the chat's operator
dialog and ``/api/escalate``. An answer scored 90 is routed ``auto`` and carries
the handover line instead: on this Mac no automatic signal tells a bad answer
from a good one (PLAN.md stage 3, outcome C, 2026-10-26), so every answer says
it may be wrong and offers the operator through the same dialog. Requires Python Playwright and Chromium and skips
without them; a skip is not evidence — run it with ``-rs``.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import uvicorn

from agent import graph
from config.settings import Settings
from tests import _fake_ollama

pytest.importorskip("playwright.sync_api")
pytest.importorskip("langchain_ollama")
from playwright.sync_api import Page, expect, sync_playwright  # noqa: E402

SESSION_ID = "11111111-2222-4333-8444-555555555555"
TIMEOUT_QUESTION = "Сколько дней груз хранится на складе бесплатно?"
HUMAN_QUESTION = "Как подать претензию о повреждении груза?"
HUMAN_ANSWER = "Претензию подают в письменной форме перевозчику [1]."
AUTO_QUESTION = "Куда отправить акт о повреждении груза?"
AUTO_ANSWER = "Акт отправляют перевозчику вместе с претензией [1]."
HANDOVER_NOTE = "Ответ составлен автоматически и может ошибаться."
# The limit the timeout test sets, and how long its model stays silent.
REQUEST_LIMIT_SEC = 8.0
SILENT_SEC = 60.0
SELF_EVAL_MARKER = "rating the quality of assistant answers"
SUGGESTIONS_MARKER = "propose 3 short follow-up questions"
# The chat streams from /api/chat/stream when the health check reports streaming on,
# from /api/ask/stream otherwise (this stand has no Postgres, so health is 503): one handler.
STREAM_PATHS = ("/api/chat/stream", "/api/ask/stream")
PATH_ENV = ("STREAMING_RAG_PARITY", "STREAMING_QUALITY_EVAL", "LLM_PROVIDER_PROFILE")


def _reply(payload: dict[str, Any]) -> _fake_ollama.Reply:
    prompt = str(payload.get("prompt") or "")
    if SELF_EVAL_MARKER in prompt:
        return _fake_ollama.Reply(["90" if AUTO_QUESTION in prompt else "40"])
    if SUGGESTIONS_MARKER in prompt:
        return _fake_ollama.Reply(["Какие документы приложить?"])
    if TIMEOUT_QUESTION in prompt:
        return _fake_ollama.Reply(["Поздно."], first_token_after=SILENT_SEC)
    if AUTO_QUESTION in prompt:
        return _fake_ollama.Reply([AUTO_ANSWER])
    return _fake_ollama.Reply([HUMAN_ANSWER])


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_http_ok(url: str, *, timeout_sec: float = 30.0) -> None:
    import urllib.request

    deadline = time.monotonic() + timeout_sec
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:  # noqa: S310
                if 200 <= int(resp.status) < 500:
                    return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(0.1)
    raise RuntimeError(f"server not ready at {url}: {last_err}")


@pytest.fixture
def chat_stand(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[Callable[..., SimpleNamespace]]:
    """Start the chat's server with a request limit, and the model's replies if given;
    returns its URL and records."""
    import api.app as api_app
    import config.settings as settings_mod
    from api.routers import conversation
    from services.escalation import EscalationOutcome
    from tracing import _base_trace

    stack = ExitStack()

    def start(
        request_timeout_sec: float,
        reply: Callable[[dict[str, Any]], _fake_ollama.Reply] = _reply,
        *,
        codex: Any = None,
    ) -> SimpleNamespace:
        fake = codex if codex is not None else stack.enter_context(_fake_ollama.running(reply))
        data_dir = tmp_path / "chat-e2e-data"
        data_dir.mkdir()
        monkeypatch.setenv("RAG_ENV", "development")
        monkeypatch.setenv("AUTO_MIGRATE", "false")
        monkeypatch.setenv("OTEL_ENABLED", "false")
        monkeypatch.setenv("JWT_SECRET", "dev-secret-change-in-production-test-32chars!!")
        monkeypatch.setenv("SESSION_SECRET_KEY", "dev-session-secret-key-change-me-32!!")
        monkeypatch.setenv("DB_ENCRYPTION_KEY", "dev-db-encryption-key")
        monkeypatch.setenv("DATA_DIR", str(data_dir))
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.setenv("ALLOW_ANONYMOUS_ADMIN", "1")
        # The stand on the Mac serves the chat with streaming on.
        monkeypatch.setenv("STREAMING_ENABLED", "true")
        monkeypatch.setenv("REQUEST_TIMEOUT_SEC", str(request_timeout_sec))
        for name in ("OLLAMA_REQUEST_TIMEOUT_SEC", "STREAMING_TIMEOUT_SEC", *PATH_ENV):
            monkeypatch.delenv(name, raising=False)
        if codex is None:
            monkeypatch.setenv("OLLAMA_HOST", fake.url)
        settings_mod._settings = None
        # The local-provider cases exercise the legacy stream and its timeout fallback.
        settings = Settings(retrieval_strategy="hybrid")
        settings.tracing_db_path = tmp_path / "traces.db"
        if codex is None:
            settings.ollama_base_url = fake.url
        else:
            settings.llm_provider_profile = "codex-only"
            settings.codex_binary = str(codex.binary)
            settings.codex_home = str(codex.root)
            settings.agentic_mode = False
            settings.model_routing_enabled = False
            settings.hyde = False
            settings.llm_cache_enabled = False
            settings.online_evaluators_enabled = False
        monkeypatch.setattr(settings_mod, "get_settings", lambda: settings)
        monkeypatch.setattr(graph, "get_settings", lambda: settings)
        monkeypatch.setattr(api_app, "get_settings", lambda: settings)
        monkeypatch.setattr(graph, "_default_breaker", None)
        _base_trace._init_db()

        documents = [
            SimpleNamespace(
                page_content=f"Раздел {i}. Претензия о повреждении груза подаётся письменно.",
                metadata={"source": f"rules-{i}.md", "doc_id": f"doc-{i}", "title": f"Правила {i}"},
            )
            for i in range(1, 4)
        ]
        retriever = SimpleNamespace(get_relevant_documents=lambda query: documents)
        session = graph.ConversationSession(retriever, None)

        async def session_factory(*args: Any, **kwargs: Any) -> tuple[str, Any]:
            return SESSION_ID, session

        async def no_postgres(**kwargs: Any) -> None:
            return None

        escalations: list[dict[str, Any]] = []

        async def record_escalation(**kwargs: Any) -> EscalationOutcome:
            escalations.append(kwargs)
            return EscalationOutcome(
                ticket_id="T-1",
                delivery_state="delivered",
                durable=True,
                already_existed=False,
                user_message="Запрос передан оператору.",
                source=str(kwargs.get("source") or "manual"),
            )

        monkeypatch.setattr(api_app, "_get_or_create_session", session_factory)
        monkeypatch.setattr(api_app, "log_audit", no_postgres)
        monkeypatch.setattr(conversation, "_persist_ask_messages", no_postgres)
        if codex is not None:
            monkeypatch.setattr(conversation, "_admit_durable_turn", no_postgres)
        # The durable ticket store has its own tests; here it records the request.
        monkeypatch.setattr("services.escalation.create_escalation", record_escalation)
        monkeypatch.setattr(api_app, "initialize_vector_store", lambda: None)
        monkeypatch.setattr(api_app, "_run_alembic_upgrade", lambda: None)

        port = _free_port()
        server = uvicorn.Server(
            uvicorn.Config(
                api_app.app, host="127.0.0.1", port=port, log_level="warning", access_log=False
            )
        )
        server.install_signal_handlers = False
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        def stop() -> None:
            server.should_exit = True
            thread.join(timeout=10)

        stack.callback(stop)
        base = f"http://127.0.0.1:{port}"
        _wait_http_ok(f"{base}/api/health/live")
        return SimpleNamespace(base=base, fake=fake, escalations=escalations)

    with stack:
        yield start
    settings_mod._settings = None


def _ask(page: Page, base: str, question: str) -> list[str]:
    """Send ``question`` from the chat; returns the stream URLs the chat calls."""
    streams: list[str] = []
    page.on("request", lambda r: streams.append(r.url) if r.url.endswith("/stream") else None)
    page.goto(f"{base}/static/chat.html")
    # The health check tells the chat which streaming route to use.
    expect(page.locator("#statusText")).not_to_have_text("Подключение...")
    page.fill("#questionInput", question)
    page.press("#questionInput", "Enter")
    return streams


def _escalate(page: Page, message: Any) -> None:
    message.locator(".btn-escalate-action").click()
    page.wait_for_selector("#escalateModal.active")
    page.click("#escalateConfirm")
    page.locator(".message.bot", has_text="Запрос передан оператору.").wait_for()


def _expect_actions_shown(message: Any) -> None:
    # The actions row is transparent until hover unless the message carries actions.
    expect(message.locator(".msg-actions")).to_have_css("opacity", "1")


def test_timeout_offers_retry_and_the_operator(chat_stand) -> None:
    stand = chat_stand(REQUEST_LIMIT_SEC)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            started = time.monotonic()
            streams = _ask(page, stand.base, TIMEOUT_QUESTION)
            message = page.locator(".message.bot", has=page.locator(".btn-escalate-action"))
            message.wait_for(timeout=(REQUEST_LIMIT_SEC + 30) * 1000)
            elapsed = time.monotonic() - started

            assert len(streams) == 1 and streams[0].endswith(STREAM_PATHS), streams
            # The deadline was reached for real, not the model's silence waited out.
            assert REQUEST_LIMIT_SEC <= elapsed < SILENT_SEC, elapsed
            assert "слишком много времени" in message.inner_text()
            assert message.locator(".badge-route").inner_text() == "Маршрут: timeout"
            # The operator is offered once: by the action, not again by the handover line.
            assert message.locator(".answer-handover").count() == 0
            assert message.locator(".btn-retry").inner_text() == "Повторить"
            assert message.locator(".btn-escalate-action").inner_text() == "Передать оператору"
            _expect_actions_shown(message)
            # The model was asked and never answered within the limit.
            answer_requests = [
                r
                for r in stand.fake.requests
                if TIMEOUT_QUESTION in str(r["payload"].get("prompt"))
            ]
            assert len(answer_requests) == 1 and answer_requests[0]["sent_after"] == []
            assert stand.escalations == []

            _escalate(page, message)
        finally:
            browser.close()

    assert len(stand.escalations) == 1, stand.escalations
    escalation = stand.escalations[0]
    assert escalation["question"] == TIMEOUT_QUESTION
    assert escalation["reason"] == "route=timeout"
    assert escalation["source"] == "manual"


def test_human_answer_offers_the_operator_without_a_ticket(chat_stand) -> None:
    # A limit no fake answer comes near: this test is about the route, not the time.
    stand = chat_stand(600.0)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            streams = _ask(page, stand.base, HUMAN_QUESTION)
            message = page.locator(".message.bot", has=page.locator(".btn-escalate-action"))
            message.wait_for(timeout=60_000)

            assert len(streams) == 1 and streams[0].endswith(STREAM_PATHS), streams
            assert HUMAN_ANSWER in message.inner_text()
            assert message.locator(".badge-route").inner_text() == "Маршрут: human"
            assert message.locator(".btn-escalate-action").inner_text() == "Передать оператору"
            assert message.locator(".btn-retry").count() == 0
            assert message.locator(".answer-handover").count() == 0
            _expect_actions_shown(message)
            # The chat opens no ticket on its own for a `human` answer.
            assert stand.escalations == []

            _escalate(page, message)
        finally:
            browser.close()

    assert len(stand.escalations) == 1, stand.escalations
    escalation = stand.escalations[0]
    assert escalation["question"] == HUMAN_QUESTION
    assert escalation["reason"] == "route=human"
    assert escalation["session_id"] == SESSION_ID


@pytest.mark.parametrize(
    ("route", "detail", "text"),
    [
        ("timeout", "Request deadline exceeded waiting for graph", "Ответ не пришёл вовремя"),
        ("error", "Graph pipeline failed", "Не удалось получить ответ"),
    ],
    ids=["timeout", "error"],
)
def test_stream_error_offers_retry_and_the_operator(chat_stand, route, detail, text) -> None:
    """The client's branch for the stream's ``error`` event, routed ``timeout`` or ``error``.

    The server sends those events on the graph-parity path, off in production,
    and routes ``timeout`` when the deadline is spent before retrieval — none of
    it reachable for real here. The stream is replaced by the events exactly as
    ``api/routers/conversation.py`` writes them; the real timeout is the first test.
    """
    stand = chat_stand(600.0)
    events = [
        {"type": "status", "node": "processing"},
        {"type": "error", "detail": detail, "route": route, "generation_source": "graph_only"},
    ]
    body = "".join("data: " + json.dumps(event) + "\n\n" for event in events)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.route(
                "**/api/*/stream",
                lambda r: r.fulfill(status=200, content_type="text/event-stream", body=body),
            )
            _ask(page, stand.base, TIMEOUT_QUESTION)
            message = page.locator(".message.bot", has=page.locator(".btn-escalate-action"))
            message.wait_for(timeout=30_000)

            assert text in message.inner_text()
            assert message.locator(".btn-retry").inner_text() == "Повторить"
            _expect_actions_shown(message)

            _escalate(page, message)
        finally:
            browser.close()

    assert [(e["question"], e["reason"]) for e in stand.escalations] == [
        (TIMEOUT_QUESTION, f"route={route}")
    ]


def test_every_other_answer_carries_the_handover_line(chat_stand) -> None:
    stand = chat_stand(600.0)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            streams = _ask(page, stand.base, AUTO_QUESTION)
            message = page.locator(".message.bot", has=page.locator(".answer-handover"))
            message.wait_for(timeout=60_000)

            assert len(streams) == 1 and streams[0].endswith(STREAM_PATHS), streams
            assert AUTO_ANSWER in message.inner_text()
            assert message.locator(".badge-route").inner_text() == "Маршрут: auto"
            line = message.locator(".answer-handover")
            # Shown at once, not on hover: the line is outside the hidden actions row.
            expect(line).to_be_visible()
            expect(line).to_contain_text(HANDOVER_NOTE)
            expect(line.locator(".btn-handover")).to_have_text("Передать оператору")
            assert message.locator(".btn-escalate-action").count() == 0
            assert stand.escalations == []

            line.locator(".btn-handover").click()
            page.wait_for_selector("#escalateModal.active")
            expect(page.locator("#escalateCancel")).to_be_focused()
            page.click("#escalateConfirm")
            page.locator(".message.bot", has_text="Запрос передан оператору.").wait_for()
            # The operator's own reply offers the operator no second time.
            confirmed = page.locator(".message.bot", has_text="Запрос передан оператору.")
            assert confirmed.locator(".answer-handover").count() == 0
        finally:
            browser.close()

    assert len(stand.escalations) == 1, stand.escalations
    escalation = stand.escalations[0]
    assert escalation["question"] == AUTO_QUESTION
    assert escalation["reason"] == "route=auto"
    assert escalation["source"] == "manual"
    assert escalation["session_id"] == SESSION_ID
