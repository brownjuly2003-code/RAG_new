"""The embeddable widget says honestly that an answer did not come and offers the
operator (ROADMAP, thread M, step 2's widget half; the session's decision on
Julia's «Реши, как оптимальнее», 2026-10-15).

Chromium opens ``/static/widget.html`` on a live uvicorn of ``api.app``; the
widget takes its token from ``/api/widget/bootstrap`` and asks ``/api/ask``,
whose real path — a real ``ConversationSession`` with a fake retriever and no
LLM, as production builds it, the real provider runtime, langchain-ollama and
the ollama client — reaches a fake Ollama server in this test. Before this
change the widget met the request's wall-time limit (HTTP 504) with «Не удалось
подключиться к сервису…», which was untrue, and the graph's own deadline with
the apology and nothing to do; ``/api/ask`` opens no ticket on either. Now both
say the answer did not come in time and offer «Повторить» and «Передать
оператору»; any other failure says the answer did not come. The button sends
``/api/escalate`` the question with the reason ``route=timeout`` /
``route=error``, as ``/api/ask`` names its own tickets, and fetches a new token
once when the old one expired during a long wait. Requires Python Playwright
and Chromium and skips without them; a skip is not evidence — run it with ``-rs``.
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
QUESTION = "Как подать претензию о повреждении груза?"
SECOND_QUESTION = "Какие документы приложить к претензии?"
ANSWER = "Претензию подают в письменной форме перевозчику [1]."
TIMEOUT_TEXT = "Ответ не пришёл вовремя. Повторите вопрос или передайте его оператору."
ERROR_TEXT = "Не удалось получить ответ. Повторите вопрос или передайте его оператору."
ESCALATED = "Запрос передан оператору."
# The limit a timeout test sets, and how long its model stays silent.
LIMIT_SEC = 8.0
SILENT_SEC = 60.0
SELF_EVAL_MARKER = "rating the quality of assistant answers"
SUGGESTIONS_MARKER = "propose 3 short follow-up questions"
PATH_ENV = ("STREAMING_RAG_PARITY", "STREAMING_QUALITY_EVAL", "LLM_PROVIDER_PROFILE")


def _reply(payload: dict[str, Any]) -> _fake_ollama.Reply:
    prompt = str(payload.get("prompt") or "")
    if SELF_EVAL_MARKER in prompt:
        return _fake_ollama.Reply(["85"])
    if SUGGESTIONS_MARKER in prompt:
        return _fake_ollama.Reply(["Какие документы приложить?"])
    if TIMEOUT_QUESTION in prompt:
        return _fake_ollama.Reply(["Поздно."], first_token_after=SILENT_SEC)
    return _fake_ollama.Reply([ANSWER])


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
def widget_stand(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[Callable[..., SimpleNamespace]]:
    """Start the widget's server with a request limit and an ask budget."""
    import api.app as api_app
    import config.settings as settings_mod
    from api.routers import conversation
    from services.escalation import EscalationOutcome
    from tracing import _base_trace

    stack = ExitStack()

    def start(request_timeout_sec: float, ask_budget_sec: float = 0.0) -> SimpleNamespace:
        fake = stack.enter_context(_fake_ollama.running(_reply))
        port = _free_port()
        base = f"http://127.0.0.1:{port}"
        data_dir = tmp_path / "widget-e2e-data"
        data_dir.mkdir()
        monkeypatch.setenv("RAG_ENV", "development")
        monkeypatch.setenv("AUTO_MIGRATE", "false")
        monkeypatch.setenv("OTEL_ENABLED", "false")
        # The widget page is opened on the API's own origin.
        monkeypatch.setenv("WIDGET_ALLOWED_ORIGINS", base)
        monkeypatch.setenv("WIDGET_TOKEN_TTL_SEC", "600")
        monkeypatch.setenv("JWT_SECRET", "dev-secret-change-in-production-test-32chars!!")
        monkeypatch.setenv("SESSION_SECRET_KEY", "dev-session-secret-key-change-me-32!!")
        monkeypatch.setenv("DB_ENCRYPTION_KEY", "dev-db-encryption-key")
        monkeypatch.setenv("DATA_DIR", str(data_dir))
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.setenv("ALLOW_ANONYMOUS_ADMIN", "1")
        monkeypatch.setenv("REQUEST_TIMEOUT_SEC", str(request_timeout_sec))
        monkeypatch.setenv("RAG_ASK_BUDGET_SEC", str(ask_budget_sec))
        for name in ("OLLAMA_REQUEST_TIMEOUT_SEC", "STREAMING_TIMEOUT_SEC", *PATH_ENV):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("OLLAMA_HOST", fake.url)
        settings_mod._settings = None
        settings = Settings()
        settings.tracing_db_path = tmp_path / "traces.db"
        settings.ollama_base_url = fake.url
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
                user_message=ESCALATED,
                source=str(kwargs.get("source") or "manual"),
            )

        monkeypatch.setattr(api_app, "_get_or_create_session", session_factory)
        monkeypatch.setattr(api_app, "log_audit", no_postgres)
        monkeypatch.setattr(conversation, "_persist_ask_messages", no_postgres)
        # The durable ticket store has its own tests; here it records the request.
        monkeypatch.setattr("services.escalation.create_escalation", record_escalation)
        monkeypatch.setattr(api_app, "initialize_vector_store", lambda: None)
        monkeypatch.setattr(api_app, "_run_alembic_upgrade", lambda: None)

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
        _wait_http_ok(f"{base}/api/health/live")
        return SimpleNamespace(base=base, fake=fake, escalations=escalations)

    with stack:
        yield start
    settings_mod._settings = None


def _open(page: Page, base: str) -> list[tuple[str, int]]:
    """Open the widget; returns the API calls it makes, as (path, status)."""
    calls: list[tuple[str, int]] = []
    page.on(
        "response",
        lambda r: calls.append((r.url.removeprefix(base), r.status)) if "/api/" in r.url else None,
    )
    page.goto(f"{base}/static/widget.html")
    expect(page.locator("#input")).to_be_visible()
    return calls


def _ask(page: Page, question: str) -> None:
    page.fill("#input", question)
    page.press("#input", "Enter")


def _offer(page: Page) -> Any:
    return page.locator(".widget-msg.assistant", has=page.locator(".widget-escalate"))


def _escalate(page: Page, message: Any) -> None:
    message.locator(".widget-escalate").click()
    page.locator(".widget-msg.assistant", has_text=ESCALATED).wait_for()
    expect(message.locator(".widget-actions")).to_have_count(0)


def _expect_offer(message: Any, text: str) -> None:
    expect(message).to_contain_text(text)
    expect(message.locator(".widget-retry")).to_have_text("Повторить")
    expect(message.locator(".widget-escalate")).to_have_text("Передать оператору")
    expect(message.locator(".widget-actions")).to_be_visible()


def test_wall_time_limit_offers_retry_and_the_operator(widget_stand) -> None:
    stand = widget_stand(LIMIT_SEC)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            calls = _open(page, stand.base)
            started = time.monotonic()
            with page.expect_response("**/api/widget/bootstrap") as bootstrap:
                _ask(page, TIMEOUT_QUESTION)
            session_id = bootstrap.value.json()["session_id"]
            message = _offer(page)
            message.wait_for(timeout=(LIMIT_SEC + 30) * 1000)
            elapsed = time.monotonic() - started

            # The request's own limit ended it, not the model's silence waited out.
            assert ("/api/ask", 504) in calls, calls
            assert LIMIT_SEC <= elapsed < SILENT_SEC, elapsed
            _expect_offer(message, TIMEOUT_TEXT)
            expect(page.locator(".widget-msg", has_text="Не удалось подключиться")).to_have_count(0)
            answer_requests = [
                r
                for r in stand.fake.requests
                if TIMEOUT_QUESTION in str(r["payload"].get("prompt"))
            ]
            assert len(answer_requests) == 1 and answer_requests[0]["sent_after"] == []
            # /api/ask opens no ticket on a timeout.
            assert stand.escalations == []

            _escalate(page, message)
        finally:
            browser.close()

    assert len(stand.escalations) == 1, stand.escalations
    escalation = stand.escalations[0]
    assert escalation["question"] == TIMEOUT_QUESTION
    assert escalation["reason"] == "route=timeout"
    assert escalation["source"] == "manual"
    assert escalation["session_id"] == session_id


def test_graph_deadline_apology_offers_retry_and_the_operator(widget_stand) -> None:
    # The graph's budget ends the answer before the request's limit: a 200 routed timeout.
    stand = widget_stand(600.0, ask_budget_sec=LIMIT_SEC)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            calls = _open(page, stand.base)
            with page.expect_response("**/api/ask", timeout=(LIMIT_SEC + 30) * 1000) as asked:
                _ask(page, TIMEOUT_QUESTION)
            data = asked.value.json()
            message = _offer(page)
            message.wait_for()

            assert (data["route"], data["ticket_id"]) == ("timeout", None), data
            assert ("/api/ask", 200) in calls, calls
            _expect_offer(message, data["answer"])
            assert "слишком много времени" in data["answer"]
            assert stand.escalations == []

            _escalate(page, message)
        finally:
            browser.close()

    assert [(e["question"], e["reason"], e["session_id"]) for e in stand.escalations] == [
        (TIMEOUT_QUESTION, "route=timeout", SESSION_ID)
    ]


def _fail(route: Any, status: int) -> None:
    route.fulfill(status=status, content_type="application/json", body=json.dumps({"detail": "x"}))


def test_failed_answer_offers_retry_and_the_operator(widget_stand) -> None:
    """Any other failure of ``/api/ask``, injected: a 500 and then a token that expired.

    The retry reaches the real path and gets the answer; the operator's first
    call meets a 401, as after a wait longer than ``WIDGET_TOKEN_TTL_SEC``, and
    the widget fetches a new token for the same session and calls again.
    """
    stand = widget_stand(600.0)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            calls = _open(page, stand.base)
            page.route("**/api/ask", lambda r: _fail(r, 500), times=1)
            _ask(page, QUESTION)
            message = _offer(page)
            message.wait_for(timeout=30_000)
            _expect_offer(message, ERROR_TEXT)

            with page.expect_response("**/api/ask", timeout=60_000) as retried:
                message.locator(".widget-retry").click()
            answer = retried.value.json()
            page.locator(".widget-msg.assistant", has_text=ANSWER).wait_for()
            expect(page.locator(".widget-msg.assistant", has_text=ERROR_TEXT)).to_have_count(0)
            expect(page.locator(".widget-msg.user", has_text=QUESTION)).to_have_count(2)
            expect(page.locator(".widget-actions")).to_have_count(0)
            # The graph routes the fake model's answer by its own checks; a `human` answer
            # is ticketed by /api/ask itself, so the widget adds no button to it.
            assert answer["route"] in {"auto", "human"}, answer
            opened = [(e["source"], e["reason"]) for e in stand.escalations]
            assert opened == (
                [("human_route", "route=human")] if answer["route"] == "human" else []
            )

            page.route("**/api/ask", lambda r: _fail(r, 500), times=1)
            page.route("**/api/escalate", lambda r: _fail(r, 401), times=1)
            _ask(page, SECOND_QUESTION)
            message = _offer(page)
            message.wait_for(timeout=30_000)
            _expect_offer(message, ERROR_TEXT)
            _escalate(page, message)
        finally:
            browser.close()

    bootstraps = [status for path, status in calls if path == "/api/widget/bootstrap"]
    assert bootstraps == [200, 200], calls
    manual = [e for e in stand.escalations if e["source"] == "manual"]
    assert [(e["question"], e["reason"], e["session_id"]) for e in manual] == [
        (SECOND_QUESTION, "route=error", SESSION_ID)
    ]
