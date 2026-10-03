"""Tests for request context isolation; see docs/specs/request-context-isolation.md."""

from __future__ import annotations

import asyncio
import contextvars
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

from llm.request_budget import get_llm_request_budget
from tests import test_ask_contract_route as contracts
from utils import request_deadline, request_executor
from utils.request_deadline import get_request_deadline

_MARKER: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_context_isolation_marker",
    default="unset",
)


@pytest.fixture(autouse=True)
def _single_worker_request_executor() -> Iterator[None]:
    """Pin the process-wide request executor to exactly one worker thread per test."""
    request_executor.reset_request_executor_for_tests()
    request_executor.get_request_executor(max_workers=1)
    try:
        yield
    finally:
        request_executor.reset_request_executor_for_tests()


def _run_via_submit_request(fn: Callable[[], object]) -> object:
    """Run fn through submit_request and wait for its result."""
    return request_executor.submit_request(fn).result(timeout=5)


def _run_via_run_on_request_executor(fn: Callable[[], object]) -> object:
    """Run fn through run_on_request_executor and wait for its result."""
    return request_executor.run_on_request_executor(fn, timeout_sec=5.0)


def _run_via_executor_submit(fn: Callable[[], object]) -> object:
    """Run fn through ThreadPoolExecutor.submit and wait for its result."""
    return request_executor.get_request_executor().submit(fn).result(timeout=5)


def _run_via_run_in_executor(fn: Callable[[], object]) -> object:
    """Run fn through loop.run_in_executor and wait for its result."""

    async def run() -> object:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(request_executor.get_request_executor(), fn)

    return asyncio.run(run())


_RUNNERS: dict[str, Callable[[Callable[[], object]], object]] = {
    "submit_request": _run_via_submit_request,
    "run_on_request_executor": _run_via_run_on_request_executor,
    "executor.submit": _run_via_executor_submit,
    "run_in_executor": _run_via_run_in_executor,
}


def _submit_request_from_marked_context(fn: Callable[[], object]) -> object:
    """Submit fn via submit_request while the marker is set in the calling thread."""
    token = _MARKER.set("from-submitter")
    try:
        return request_executor.submit_request(fn).result(timeout=5)
    finally:
        _MARKER.reset(token)


def _run_in_executor_from_marked_context(fn: Callable[[], object]) -> object:
    """Submit fn via run_in_executor with the marker set inside the coroutine."""

    async def run() -> object:
        token = _MARKER.set("from-submitter")
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(request_executor.get_request_executor(), fn)
        finally:
            _MARKER.reset(token)

    return asyncio.run(run())


_MARKED_SUBMITTERS: dict[str, Callable[[Callable[[], object]], object]] = {
    "submit_request": _submit_request_from_marked_context,
    "run_in_executor": _run_in_executor_from_marked_context,
}


@pytest.mark.parametrize("runner_name", sorted(_RUNNERS))
def test_submitted_callable_leaves_no_context_behind(runner_name: str) -> None:
    """A callable that sets a context var leaves nothing behind for the next callable."""
    runner = _RUNNERS[runner_name]

    def set_marker() -> str:
        _MARKER.set("leaked")
        return threading.current_thread().name

    def read_marker() -> tuple[object, str]:
        return (_MARKER.get(), threading.current_thread().name)

    first_thread = runner(set_marker)
    marker_value, second_thread = runner(read_marker)

    assert first_thread.startswith("rag-request"), first_thread
    assert second_thread == first_thread, (first_thread, second_thread)
    assert marker_value == "unset", marker_value


@pytest.mark.parametrize("submitter_name", sorted(_MARKED_SUBMITTERS))
def test_submitter_context_is_not_copied_into_callables(submitter_name: str) -> None:
    """A context var set in the submitting context stays invisible to the submitted callable."""
    submitter = _MARKED_SUBMITTERS[submitter_name]

    seen: dict[str, object] = {}

    def read_marker() -> None:
        seen["marker"] = _MARKER.get()

    submitter(read_marker)

    assert seen["marker"] == "unset", seen


def test_results_and_exceptions_reach_the_caller_unchanged() -> None:
    """A callable's return value and its raised ValueError reach the caller unchanged."""

    def payload() -> dict[str, int]:
        return {"answer": 42}

    expected = {"answer": 42}
    assert request_executor.submit_request(payload).result(timeout=5) == expected
    assert request_executor.run_on_request_executor(payload, timeout_sec=5.0) == expected

    boom = ValueError("boom from the worker thread")

    def failing() -> dict[str, int]:
        raise boom

    with pytest.raises(ValueError) as excinfo:
        request_executor.submit_request(failing).result(timeout=5)
    assert excinfo.value is boom


def _perform_successful_stream_request(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    tmp_path: Path,
) -> None:
    """Run one successful stream request so the worker thread binds a deadline and budget."""
    contracts._pipeline(monkeypatch, client, tmp_path, answers=list(contracts._DEFAULT_ANSWERS))
    app_settings = contracts.api_app.get_settings()
    monkeypatch.setattr(app_settings, "streaming_rag_parity", True, raising=False)
    monkeypatch.setattr(app_settings, "request_timeout_sec", 30.0, raising=False)
    monkeypatch.setattr(app_settings, "llm_max_calls_per_request", 24, raising=False)
    response = client.post(
        "/api/ask/stream",
        json={"question": "Summarize the policy"},
        headers={"Accept": "text/event-stream"},
    )
    assert response.status_code == 200, response.text
    events = contracts._parse_events(response.text)
    final = next(event for event in events if event["type"] == "result")
    assert final["answer"] == "Seed policy [1].", final["answer"]


def test_worker_thread_is_clean_after_a_stream_request(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    tmp_path: Path,
) -> None:
    """After a stream request the worker thread holds no request deadline and no LLM budget."""
    _perform_successful_stream_request(monkeypatch, client, tmp_path)

    seen: dict[str, object] = {}

    def probe() -> None:
        seen["deadline"] = get_request_deadline()
        seen["budget"] = get_llm_request_budget()

    request_executor.submit_request(probe).result(timeout=5)

    assert seen["deadline"] is None, seen
    assert seen["budget"] is None, seen


def test_sync_ask_answers_after_a_stream_request_whose_deadline_has_passed(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    tmp_path: Path,
) -> None:
    """A sync /api/ask still answers normally once an earlier stream's deadline has passed."""
    _perform_successful_stream_request(monkeypatch, client, tmp_path)

    real_monotonic = time.monotonic
    monkeypatch.setattr(
        request_deadline,
        "time",
        SimpleNamespace(monotonic=lambda: real_monotonic() + 86_400.0),
    )

    contracts._pipeline(monkeypatch, client, tmp_path, answers=list(contracts._DEFAULT_ANSWERS))
    body = contracts._ask(client)
    assert body["answer"] == "Seed policy [1].", body["answer"]
    assert body["route"] != "timeout", body["route"]
    assert body["trace_id"], body
    contracts._evidence(client, body["trace_id"])
