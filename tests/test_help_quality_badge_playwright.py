"""The help page calls the «Качество» badge the model's own self-evaluation, not calibrated
(PLAN.md stage 6, item 6; the audit of 2026-10-30, F2).

The classic self-evaluation scored 2 of the 17 bad aircargo answers below its threshold
(docs/evidence/handover-signal-v4-aircargo.md, PLAN.md stage 3, outcome C), so «Чем выше
число, тем безопаснее автоматический ответ» promised a calibration the number does not have.
Chromium opens ``/static/help.html`` from a live uvicorn of ``api.app`` and reads the badge's
paragraph as the client sees it. Requires Python Playwright and Chromium and skips without
them; a skip is not evidence — run it with ``-rs``.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright  # noqa: E402

OLD_CLAIM = "Чем выше число, тем безопаснее автоматический ответ"


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
def help_stand(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[str]:
    """The app served by uvicorn, as the chat's stand serves it; returns its URL."""
    import api.app as api_app
    import config.settings as settings_mod
    from config.settings import Settings

    data_dir = tmp_path / "help-e2e-data"
    data_dir.mkdir()
    monkeypatch.setenv("RAG_ENV", "development")
    monkeypatch.setenv("AUTO_MIGRATE", "false")
    monkeypatch.setenv("OTEL_ENABLED", "false")
    monkeypatch.setenv("JWT_SECRET", "dev-secret-change-in-production-test-32chars!!")
    monkeypatch.setenv("SESSION_SECRET_KEY", "dev-session-secret-key-change-me-32!!")
    monkeypatch.setenv("DB_ENCRYPTION_KEY", "dev-db-encryption-key")
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    settings_mod._settings = None
    settings = Settings()
    settings.tracing_db_path = tmp_path / "traces.db"
    monkeypatch.setattr(settings_mod, "get_settings", lambda: settings)
    monkeypatch.setattr(api_app, "get_settings", lambda: settings)
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
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_http_ok(f"{base}/api/health/live")
        yield base
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def test_the_help_page_calls_the_quality_badge_an_uncalibrated_self_evaluation(
    help_stand: str,
) -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(f"{help_stand}/static/help.html")
            badges = page.locator(
                "section", has=page.get_by_role("heading", name="Что означают бейджи")
            )
            quality = badges.locator("p", has=page.locator(".badge-quality", has_text="Качество"))
            expect(quality).to_have_count(1)
            expect(quality).to_contain_text("самооценка модели")
            expect(quality).to_contain_text("Число не откалибровано")
            expect(quality).to_contain_text("не означает вероятность правильного ответа")
            expect(quality).to_contain_text("Ответ с высоким числом тоже может ошибаться")
            expect(quality).to_contain_text("«Передать оператору»")
            expect(page.locator("body")).not_to_contain_text(OLD_CLAIM)
        finally:
            browser.close()
