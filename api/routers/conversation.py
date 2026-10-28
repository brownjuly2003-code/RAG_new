"""Conversation ask/chat endpoints."""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import json as _json
import logging
import re
import time
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from api._shared import app_module as _app_module
from api.correlation import get_current_tenant, get_request_id
from api.rate_limit import limiter
from auth.dependencies import get_current_user
from config.settings import TIME_LIMIT_CEILING_SEC
from monitoring import prometheus as prometheus_metrics
from services.pipeline import pipeline_runner
from utils.background_tasks import spawn_tracked

router = APIRouter()
logger = logging.getLogger(__name__)

# Plan §4.4: terminal routes that must carry a durable ticket (or explicit failure).
_TERMINAL_ESCALATE_ROUTES = frozenset({"human", "error", "error_escalation"})

# --- Resolution kernel shadow journeys (plan 2026-08-23, phase A) ------------
# Off unless RESOLUTION_SHADOW_JOURNEYS names a journey. The shadow observes
# the same question the legacy pipeline just answered and writes an evidence
# bundle to the trace. Separate, off-by-default projection allowlists may
# project clarification or verified answers; without them the caller receives the
# same object unchanged. Before this seam existed the kernel had no production
# caller at all, which is finding FIN-01 of the 2026-08-24 audit.
_shadow_observers: dict[str, Any] = {}
_shadow_observers_key: tuple[Any, tuple[str, ...], tuple[str, ...]] | None = None

# The observers are built once and reused, so the sink cannot close over a
# per-request trace id. It reads it from here instead. Without this the
# evidence would land under the kernel's own correlation UUID -- a trace
# nobody can reach from the answer it belongs to, which would leave the
# Evidence tab in phase A.3 with nothing to attach to.
_shadow_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "resolution_shadow_trace_id", default=""
)

# Same reason, for the same reason: the cached sink is the only place a shadow
# result surfaces -- `run_legacy_ask_shadow` returns the legacy response, not
# the observation -- so phase A.1b collects results here to persist them after
# the request path is done with them. `None` means nobody is collecting, which
# is what every caller that only wants the trace step gets.
_shadow_collect: contextvars.ContextVar[list[Any] | None] = contextvars.ContextVar(
    "resolution_shadow_collect", default=None
)


def _resolution_shadow_observers(
    journeys: tuple[str, ...],
    retriever: Any,
    response_journeys: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build the observers once and reuse them; rebuild if the wiring changes.

    Keyed on the retriever identity as well as the journey list because the
    app swaps its retriever on reindex, and a shadow holding the old one would
    silently gather policy evidence from a stale index. `response_journeys`
    is part of the key for the same reason: it decides which pinned contract
    an observer is built against.
    """
    global _shadow_observers, _shadow_observers_key
    key = (id(retriever), journeys, response_journeys)
    if _shadow_observers_key != key:
        from resolution.composition import build_shadow_observers

        _shadow_observers = build_shadow_observers(
            journeys=journeys,
            retriever=retriever,
            sink=_record_shadow_evidence,
            response_journeys=response_journeys,
        )
        _shadow_observers_key = key
    return _shadow_observers


def _record_shadow_evidence(result: Any) -> None:
    """Write one full or minimal shadow outcome into the legacy answer's trace."""
    from resolution.composition import ShadowProducerOutcome
    from tracing import log_step

    is_minimal = isinstance(result, ShadowProducerOutcome)
    if not is_minimal:
        collected = _shadow_collect.get()
        if collected is not None:
            collected.append(result)
    trace_id = _shadow_trace_id.get()
    if not trace_id:
        logger.warning("shadow evidence has no trace to attach to, dropped")
        return
    if is_minimal:
        log_step(
            trace_id,
            "resolution_shadow",
            {
                "journey": result.journey,
                "outcome": result.outcome,
                "terminal_state": (
                    "" if result.terminal_state is None else result.terminal_state.value
                ),
                "reason_codes": list(result.reason_codes),
            },
        )
        return
    export = result.evidence_export
    checks = None
    try:
        from evaluation.resolution.stepwise_judge import grade_evidence_export
        from resolution.composition import load_shipment_contract, load_shipment_response_contract

        contract = (
            load_shipment_response_contract()
            if export.contract.version == "0.2.0"
            else load_shipment_contract()
        )
        judged_at = datetime.now(UTC)
        grade = grade_evidence_export(export, contract=contract, as_of=judged_at)
        checks = {
            "method": "contract_rules_only",
            "as_of": judged_at.isoformat(),
            "status": grade.status.value,
            "steps": [
                {
                    "name": step.name,
                    "status": step.status.value,
                    "reason_codes": list(step.reason_codes),
                }
                for step in grade.steps
            ],
        }
    except Exception:
        logger.warning("shipment-status stepwise grading failed", exc_info=True)
        checks = {
            "method": "contract_rules_only",
            "status": "unavailable",
            "steps": [
                {
                    "name": "judge",
                    "status": "unavailable",
                    "reason_codes": ["stepwise_grading_failed"],
                }
            ],
        }
    state = {
        "journey": "shipment-status",
        "outcome": "journey_recorded",
        "evidence": export.as_dict(),
        "terminal_state": result.terminal_state.value,
        "reason_codes": list(result.reason_codes),
        # The kernel's own case/correlation identity, kept alongside the
        # legacy trace id rather than instead of it.
        "case_id": str(export.case_id),
        "kernel_correlation_id": str(export.correlation_id),
        # The shadow's own answer, recorded for comparison only. It is
        # never returned to anyone.
        "shadow_response_text": result.response_text,
    }
    if checks is not None:
        state["stepwise_checks"] = checks
    log_step(
        trace_id,
        "resolution_shadow",
        state,
    )


def _record_shadow_producer_failure(journey: str) -> None:
    from resolution.composition import ShadowProducerOutcome

    _record_shadow_evidence(
        ShadowProducerOutcome(journey=journey, outcome="producer_failure")
    )


# A shadow may cost the answer a little time; it may not cost it forever.
# Connecting to a database that is not there does not fail fast -- it hangs,
# and without this bound every /api/ask running a shadow would hang with it.
# That is exactly the failure a shadow is forbidden to cause, and it is not
# hypothetical: it is what the phase A.5 end-to-end tests did the first time
# this write was wired in.
_SHADOW_PERSIST_TIMEOUT_SECONDS = 2.0


async def _persist_shadow_evidence(results: list[Any]) -> None:
    """Write each shadow result into the resolution tables (phase A.1b).

    The trace makes the evidence visible; this makes it queryable, which is
    what the Evidence tab in A.3 reads. Every failure is swallowed: the answer
    has already gone out, and a database that is down is not a reason to turn
    an answered question into a 500. It is a reason for a warning in the log.
    """
    if not results:
        return
    try:
        from db.engine import async_session
        from resolution.persistence import persist_shipment_shadow
    except Exception:
        logger.warning("resolution persistence is unavailable", exc_info=True)
        return
    for result in results:
        try:
            await asyncio.wait_for(
                persist_shipment_shadow(async_session, result.evidence_export),
                timeout=_SHADOW_PERSIST_TIMEOUT_SECONDS,
            )
        except (TimeoutError, asyncio.TimeoutError):
            logger.warning(
                "shadow evidence persistence timed out after %ss",
                _SHADOW_PERSIST_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.warning("shadow evidence was not persisted", exc_info=True)


def _run_resolution_shadows(
    *,
    response: Any,
    tenant_id: str,
    session_id: str,
    correlation_id: str,
    question: str,
    trace_id: str = "",
    collect: list[Any] | None = None,
) -> Any:
    """Run enabled shadows and return the legacy response object untouched.

    Every failure path returns `response` unchanged: a shadow is not allowed
    to turn an answered question into an error.

    `collect`, when given, receives each shadow result so the caller can
    persist it afterwards. It stays optional so that running a shadow for the
    trace alone remains exactly what it was.
    """
    token = _shadow_trace_id.set(trace_id or correlation_id)
    collect_token = _shadow_collect.set(collect)
    journeys: tuple[str, ...] = ()
    try:
        _app = _app_module()
        journeys = tuple(getattr(_app.get_settings(), "resolution_shadow_journeys", ()) or ())
        if not journeys:
            return response
        response_journeys = tuple(
            getattr(_app.get_settings(), "resolution_response_journeys", ()) or ()
        )
        retriever = getattr(_app, "_retriever", None)
        if retriever is None:
            for journey in journeys:
                _record_shadow_producer_failure(journey)
            return response

        from resolution.application.shipment_status import run_legacy_ask_shadow

        observers = _resolution_shadow_observers(journeys, retriever, response_journeys)
        for journey in journeys:
            observer = observers.get(journey)
            if observer is None:
                _record_shadow_producer_failure(journey)
                continue
            response = run_legacy_ask_shadow(
                response=response,
                tenant_id=tenant_id,
                session_id=session_id,
                correlation_id=correlation_id,
                question=question,
                observer=observer,
            )
    except Exception:
        logger.warning("resolution shadow wiring failed", exc_info=True)
        for journey in journeys:
            try:
                _record_shadow_producer_failure(journey)
            except Exception:
                logger.warning("resolution shadow failure outcome was not recorded", exc_info=True)
    finally:
        _shadow_trace_id.reset(token)
        _shadow_collect.reset(collect_token)
    return response


# --- Durable session turns (plan 2026-08-23, phase A.2) ----------------------
# Off unless SESSION_DURABLE_TURNS is set. With it on, /api/ask admits a
# durable turn before it answers and ends that turn when it is done, so a
# session runs one turn at a time and its message pair is written by the
# transaction that marks the turn terminal -- not by the best-effort write
# below, which has always been able to lose a pair without anyone noticing.
#
# What that changes observably: a second request arriving while the first is
# still running is refused with the 503 this endpoint already uses for
# saturation, instead of racing the first one into an interleaved history.
#
# What it deliberately does not do: replay a committed response body. That is
# REL-03D, frozen in ROADMAP.md until a design partner asks for it, so a turn
# stores the digest of its terminal message pair and no payload. A repeat of a
# request whose turn already ended is answered on the pre-A.2 path rather than
# served from storage that does not exist.
_TURN_IDENTITY_DOMAIN = "api-ask-turn-v1"
_TURN_DB_TIMEOUT_FALLBACK_SECONDS = 2.0

# Built once against the application engine and reused; tests replace it.
_session_turn_service: Any | None = None


@dataclass(slots=True)
class _DurableTurn:
    """An admitted turn, and whether anything has ended it yet."""

    service: Any
    tenant_id: str
    session_id: uuid.UUID
    turn_id: str
    turn_epoch: int
    request_digest: str
    settled: bool = False


def _durable_turns_enabled() -> bool:
    return bool(getattr(_app_module().get_settings(), "session_durable_turns", False))


def _durable_turn_service() -> Any | None:
    """Return the shared `SessionService`, or None if it cannot be built."""
    global _session_turn_service
    if _session_turn_service is None:
        try:
            from db.engine import async_session
            from services.session import SessionService

            _session_turn_service = SessionService(async_session)
        except Exception:
            logger.warning("durable session turns are unavailable", exc_info=True)
            return None
    return _session_turn_service


def _durable_turn_identity(
    *,
    tenant_id: str,
    session_id: str,
    expected_version: int,
    question: str,
    confirm: bool,
) -> tuple[str, str]:
    """Derive the turn's idempotency key and request digest from the request.

    Derived rather than taken from a header on purpose: an `Idempotency-Key`
    contract belongs to the durable-HTTP work frozen in `ROADMAP.md`, and A.2
    needs neither a new header nor a client that knows about one.

    The digest says *what was asked*. The turn id is that digest bound to the
    session version it extends, which is what makes the two cases behave
    differently: a duplicate of a request still in flight lands on the same
    turn id and is refused instead of starting a second turn, while a
    different question -- or the same question after the previous turn ended
    and moved the version -- gets an id of its own. A turn that aborted
    therefore cannot lock its session out of ever asking again, which is the
    failure a content-free key would have introduced.
    """
    request_digest = hashlib.sha256(
        _json.dumps(
            {
                "domain": _TURN_IDENTITY_DOMAIN,
                "tenant_id": tenant_id,
                "session_id": session_id,
                "question": question,
                "confirm": bool(confirm),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    turn_id = "ask-" + hashlib.sha256(
        f"{_TURN_IDENTITY_DOMAIN}:{int(expected_version)}:{request_digest}".encode()
    ).hexdigest()
    return turn_id, request_digest


def _durable_turn_timeout() -> float:
    return float(
        getattr(
            _app_module().get_settings(),
            "db_persist_timeout_sec",
            _TURN_DB_TIMEOUT_FALLBACK_SECONDS,
        )
    )


def _session_busy(reason: str) -> HTTPException:
    """The 503 that says this session is already answering something."""
    try:
        prometheus_metrics.record_pipeline_rejection(reason)
    except Exception:
        pass
    return HTTPException(
        status_code=503,
        detail="This session already has a request in flight - retry in a moment",
    )


async def _admit_durable_turn(
    *,
    tenant_id: str,
    session_id: str,
    question: str,
    confirm: bool,
) -> _DurableTurn | None:
    """Admit a durable turn for this request, or answer without one.

    Returns None whenever the durable path cannot be taken: the flag is off,
    the service or the session row is not there, the database did not answer
    in time, or this exact request already has a turn that ended. `/api/ask`
    then behaves as it did before A.2. That is the only acceptable failure
    mode for a flag that is off in production -- a database problem may not
    turn an answerable question into an error.

    It raises 503 for the one case that is a decision rather than a failure:
    this session already has a turn in flight, so answering now would
    interleave two turns into one history.
    """
    if not _durable_turns_enabled():
        return None
    service = _durable_turn_service()
    if service is None:
        return None
    try:
        session_uuid = uuid.UUID(str(session_id))
    except (TypeError, ValueError, AttributeError):
        return None

    from services.session import (
        SessionNotFound,
        SessionTurnActive,
        SessionTurnIdempotencyConflict,
        SessionVersionConflict,
        TurnStatus,
    )

    settings = _app_module().get_settings()
    timeout = _durable_turn_timeout()
    deadline_at = datetime.now(UTC) + timedelta(
        seconds=float(getattr(settings, "request_timeout_sec", TIME_LIMIT_CEILING_SEC))
        + float(getattr(settings, "session_turn_deadline_margin_sec", 15.0))
    )

    try:
        expected_version = await asyncio.wait_for(
            service.current_version(tenant_id=tenant_id, session_id=session_uuid),
            timeout=timeout,
        )
        turn_id, request_digest = _durable_turn_identity(
            tenant_id=tenant_id,
            session_id=str(session_id),
            expected_version=expected_version,
            question=question,
            confirm=confirm,
        )
        outcome = await asyncio.wait_for(
            service.admit_turn(
                tenant_id=tenant_id,
                session_id=session_uuid,
                turn_id=turn_id,
                request_digest=request_digest,
                expected_version=expected_version,
                deadline_at=deadline_at,
            ),
            timeout=timeout,
        )
    except SessionTurnActive:
        raise _session_busy("session_turn_active") from None
    except SessionVersionConflict:
        # Another turn committed between the version read and this admission.
        # Not an error in the data -- a race, and the loser retries.
        raise _session_busy("session_version_conflict") from None
    except SessionTurnIdempotencyConflict:
        # Unreachable while the turn id is derived from the digest it is bound
        # to; kept because reaching it would mean the derivation changed.
        logger.warning("durable turn id is bound to another request digest")
        return None
    except SessionNotFound:
        # The session row is not there: the bootstrap in api/app.py fell back
        # to memory. Nothing durable to hang a turn on.
        return None
    except (TimeoutError, asyncio.TimeoutError):
        logger.warning("durable turn admission timed out after %ss", timeout)
        return None
    except Exception:
        logger.warning("durable turn admission failed", exc_info=True)
        return None

    turn = outcome.turn
    if not outcome.admitted:
        if turn.status == TurnStatus.RUNNING:
            raise _session_busy("session_turn_duplicate")
        # The same request already has a terminal turn. Replaying its response
        # body is REL-03D and frozen, so answer it again without a turn rather
        # than pretend a stored answer exists.
        return None

    return _DurableTurn(
        service=service,
        tenant_id=tenant_id,
        session_id=session_uuid,
        turn_id=turn.turn_id,
        turn_epoch=turn.turn_epoch,
        request_digest=turn.request_digest,
    )


async def _commit_durable_turn(turn: _DurableTurn, *, question: str, answer: str) -> bool:
    """End the turn, writing its message pair in the same transaction.

    True means the pair is durable, which is what tells `/api/ask` to skip the
    best-effort write it would otherwise do. A turn that cannot commit is left
    to expire on its deadline rather than half-written: the answer has already
    gone out, and falling back to the best-effort write here would risk the
    pair landing twice for one turn.
    """
    if turn.settled:
        return False
    if not question or not answer:
        # `commit_turn` refuses an empty side of the pair, and it is right to:
        # a turn whose answer is empty has nothing to make durable.
        await _abort_durable_turn(turn)
        return False
    timeout = _durable_turn_timeout()
    try:
        await asyncio.wait_for(
            turn.service.commit_turn(
                tenant_id=turn.tenant_id,
                session_id=turn.session_id,
                turn_id=turn.turn_id,
                turn_epoch=turn.turn_epoch,
                request_digest=turn.request_digest,
                user_content=question,
                assistant_content=answer,
            ),
            timeout=timeout,
        )
    except (TimeoutError, asyncio.TimeoutError):
        turn.settled = True
        logger.warning("durable turn commit timed out after %ss", timeout)
        _record_turn_persist_failure()
        return False
    except Exception:
        turn.settled = True
        logger.warning("durable turn commit failed", exc_info=True)
        _record_turn_persist_failure()
        return False
    turn.settled = True
    return True


def _record_turn_persist_failure() -> None:
    try:
        prometheus_metrics.record_message_persist_failure("ask_turn_commit")
    except Exception:
        pass


async def _abort_durable_turn(turn: _DurableTurn) -> None:
    """Mark the turn terminal after a failure, so the session is not stuck.

    Without this a failed request leaves a RUNNING turn holding its session
    until the deadline elapses, and every retry in that window is refused.
    Failures here are swallowed: `admit_turn` expires a turn past its deadline
    on the next admission, so the deadline is the backstop and this is only
    the fast path to it.
    """
    if turn.settled:
        return
    turn.settled = True
    try:
        await asyncio.wait_for(
            turn.service.abort_turn(
                tenant_id=turn.tenant_id,
                session_id=turn.session_id,
                turn_id=turn.turn_id,
                turn_epoch=turn.turn_epoch,
            ),
            timeout=_durable_turn_timeout(),
        )
    except Exception:
        logger.warning("durable turn abort failed; deadline will expire it", exc_info=True)


async def _settle_durable_turn(slot: list[_DurableTurn]) -> None:
    """Abort whatever the request left running, whichever way it left."""
    for turn in slot:
        if not turn.settled:
            await _abort_durable_turn(turn)


def _release_pipeline_capacity(semaphore: Any) -> None:
    """Drop inflight gauge + release the pipeline semaphore (best-effort)."""
    pipeline_runner.release_capacity(semaphore)


def _hold_capacity_until_future_done(
    *,
    loop: asyncio.AbstractEventLoop,
    fut: Any,
    semaphore: Any,
) -> None:
    """Keep pipeline capacity until a thread-pool future finishes (3.1a / 3.1f)."""
    pipeline_runner.hold_capacity_until_future_done(
        loop=loop,
        fut=fut,
        semaphore=semaphore,
        release_capacity=_release_pipeline_capacity,
    )


def _resolve_stream_terminal(
    *,
    stream_answer: str,
    graph_result: dict[str, Any] | None,
    graph_appended_history: bool,
) -> tuple[str, bool, str]:
    """Pick the single terminal answer and history policy for /api/ask/stream (plan §4.1).

    When graph parity returns a non-empty answer, that answer is authoritative for
    the SSE result, DB persist, and history — not a second stream-side mutation.
    Tokens already sent for UX may differ; the final ``result`` event is graph-owned.

    Returns:
        (terminal_answer, skip_stream_history_append, answer_source)
        answer_source is ``"graph"`` or ``"stream"``.
    """
    if isinstance(graph_result, dict) and graph_result:
        graph_answer = str(graph_result.get("answer") or "").strip()
        if graph_answer:
            # Graph owns terminal semantics; never double-append stream text.
            return graph_answer, True, "graph"
        # Graph ran but empty answer (timeout/conflict shell): keep stream text,
        # still skip stream history if graph already mutated the session.
        return stream_answer, bool(graph_appended_history), "stream"
    return stream_answer, bool(graph_appended_history), "stream"


def _chunk_text_for_sse(text: str, *, chunk_size: int = 48) -> list[str]:
    """Split a finished answer into SSE token chunks (UX only; not a second LLM)."""
    body = str(text or "")
    if not body:
        return []
    size = max(1, int(chunk_size))
    return [body[i : i + size] for i in range(0, len(body), size)]


def _fit_stream_prompt(
    window_owner: Any,
    question: str,
    docs: list[dict[str, Any]],
    chat_history: list[dict[str, str]],
) -> tuple[str, list[dict[str, Any]]]:
    """Direct-stream prompt and the documents it holds, fitted to the model window.

    Oldest history turns go first while the top document does not fit beside
    them; then the leading documents are kept (see ``fit_context_docs``). A
    model without a declared window gets the prompt unchanged.
    """
    from agent.context_window import (  # noqa: PLC0415
        fit_context_docs,
        prompt_input_limit,
        prompt_input_tokens,
    )
    from agent.prompts import build_conversational_qa_prompt, build_qa_prompt  # noqa: PLC0415

    history = list(chat_history or [])

    def build(selected: list[dict[str, Any]]) -> str:
        if history:
            return build_conversational_qa_prompt(
                question=question, context_docs=selected, chat_history=history
            )
        return build_qa_prompt(question=question, context_docs=selected)

    limit = prompt_input_limit(window_owner, "generate")
    while history and limit is not None and prompt_input_tokens(build(docs[:1])) > limit:
        history = history[1:]
    fitted = fit_context_docs(window_owner, question, docs, build, role="generate")
    return build(fitted), fitted


def _graph_result_sources_and_citations(
    graph_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build sources/citations lists from a graph ask result."""
    sources: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    graph_citations_raw = graph_result.get("citations") or []
    if graph_citations_raw:
        citations = [
            {
                "index": int(item.get("index") or 0),
                "doc_id": str(item.get("doc_id") or ""),
                "title": str(item.get("title") or ""),
                "excerpt": str(item.get("excerpt") or ""),
            }
            for item in graph_citations_raw
            if isinstance(item, dict)
        ]
    graph_graded = graph_result.get("graded_docs") or graph_result.get("context_docs") or []
    if graph_graded:
        for idx, item in enumerate(graph_graded, start=1):
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata", {}) or {}
            content = item.get("page_content", "") or ""
            sources.append(
                {
                    "source": metadata.get("source") or metadata.get("file_name") or "",
                    "page_content": content,
                }
            )
            if not graph_citations_raw:
                citations.append(
                    {
                        "index": idx,
                        "doc_id": str(
                            metadata.get("doc_id")
                            or metadata.get("id")
                            or metadata.get("source")
                            or metadata.get("file_name")
                            or f"doc_{idx}"
                        ),
                        "title": str(
                            metadata.get("title")
                            or metadata.get("source")
                            or metadata.get("file_name")
                            or metadata.get("doc_id")
                            or f"doc_{idx}"
                        ),
                        "excerpt": str(content)[:300],
                    }
                )
    return sources, citations


def _append_stream_history(
    session: Any,
    *,
    question: str,
    answer: str,
) -> None:
    """Exactly one user+assistant pair on the in-memory session history."""
    if hasattr(session, "_history"):
        session._history.append({"role": "user", "content": question})
        session._history.append({"role": "assistant", "content": answer})
        max_history = getattr(session, "_max_history", 20)
        if len(session._history) > max_history * 2:
            session._history = session._history[-(max_history * 2) :]
    elif isinstance(session, dict):
        session.setdefault("history", [])
        session["history"].append({"role": "user", "content": question})
        session["history"].append({"role": "assistant", "content": answer})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(default=None, max_length=100)
    confirm: Optional[bool] = None
    tenant_id: str = Field(
        default="default",
        max_length=50,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )

    @field_validator("session_id")
    @classmethod
    def _validate_session_id(cls, value: Optional[str]) -> Optional[str]:
        """Reject malformed session UUIDs at the API boundary (422)."""
        if value is None:
            return None
        raw = value.strip()
        if not raw:
            return None
        try:
            return uuid.UUID(raw).hex
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("session_id must be a valid UUID") from exc


class SourceInfo(BaseModel):
    source: str = ""
    page_content: str = ""


class Citation(BaseModel):
    index: int
    doc_id: str = ""
    title: str = ""
    excerpt: str = ""


class AskResponse(BaseModel):
    answer: str
    quality_score: int = 50
    route: str = "auto"
    sources: list[SourceInfo] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    session_id: str = ""
    trace_id: str = ""
    suggested_questions: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    action_summary: str = ""
    cached: bool = False
    # Plan §4.3: durable escalation identity (only set on human/error handoff paths).
    ticket_id: str | None = None
    delivery_state: str | None = None


def _project_resolution_clarification(
    *,
    response: AskResponse,
    results: list[Any],
    journeys: tuple[str, ...],
) -> AskResponse:
    """Let one explicitly enabled clarification terminal own the response."""
    if "shipment-status" not in journeys:
        return response
    try:
        from resolution.contracts import TerminalOutcome

        result = next(
            (
                item
                for item in results
                if item.terminal_state is TerminalOutcome.CLARIFICATION_REQUIRED
                and item.reason_codes == ("SHIPMENT_ID_REQUIRED",)
                and item.response_text
            ),
            None,
        )
        if result is None:
            return response
        return response.model_copy(
            update={
                "answer": result.response_text,
                "quality_score": 0,
                "route": TerminalOutcome.CLARIFICATION_REQUIRED.value,
                "sources": [],
                "citations": [],
                "suggested_questions": [],
                "requires_confirmation": False,
                "action_summary": "",
                "cached": False,
                "ticket_id": None,
                "delivery_state": None,
            }
        )
    except Exception:
        logger.warning("resolution clarification projection failed", exc_info=True)
        return response


def _project_resolution_response(
    *,
    response: AskResponse,
    results: list[Any],
    journeys: tuple[str, ...],
) -> AskResponse:
    try:
        if not journeys:  # projection disabled
            return response
        from resolution.application.shipment_status import (
            _SHIPMENT_RESPONSE_CONTRACT_DIGEST,
            ClaimCandidate,
            ShipmentShadowResult,
            ShipmentStatusShadowLoop,
        )
        from resolution.composition import load_shipment_response_contract
        from resolution.contracts import TerminalOutcome, contract_digest

        verified = [
            item
            for item in results
            if isinstance(item, ShipmentShadowResult)
            and item.terminal_state == TerminalOutcome.VERIFIED
        ]
        if not verified:
            return response
        result = verified[0]
        export = result.evidence_export
        if export.terminal_state != TerminalOutcome.VERIFIED:
            return response
        if result.reason_codes or export.reason_codes:
            return response
        if export.source_observation is None or export.policy is None:
            return response
        if export.policy.decision != "allow":
            return response
        if not export.claim_links or not export.postcondition_versions:
            return response
        if any(item.result != "pass" for item in export.postcondition_versions):
            return response
        contract = export.contract
        if (
            contract.schema_identity != "resolution-contract/v0.1"
            or contract.contract_id != "aircargo.shipment-status"
            or contract.version != "0.2.0"
            or contract.digest != _SHIPMENT_RESPONSE_CONTRACT_DIGEST
        ):
            return response
        pinned = load_shipment_response_contract()
        if contract_digest(pinned) != _SHIPMENT_RESPONSE_CONTRACT_DIGEST:
            return response
        if pinned.response_shape is None:
            return response
        claim_ids = [link.claim_id for link in export.claim_links]
        if len(set(claim_ids)) != len(claim_ids):
            return response
        candidates = tuple(
            ClaimCandidate(
                claim_id=link.claim_id,
                text=link.text,
                evidence_requirement_ids=link.evidence_requirement_ids,
            )
            for link in export.claim_links
        )
        recompiled = ShipmentStatusShadowLoop._compile_claims(
            candidates=candidates,
            source_observation=export.source_observation,
            policy=export.policy,
        )
        if recompiled is None or recompiled != export.claim_links:
            return response
        fields = pinned.response_shape.fields
        field_claim_ids = {field.claim_id for field in fields}
        if any(claim_id not in field_claim_ids for claim_id in claim_ids):
            return response
        texts_by_claim = {link.claim_id: link.text for link in recompiled}
        parts: list[str] = []
        for field in fields:
            text = texts_by_claim.get(field.claim_id)
            if text is None:
                return response
            parts.append(text)
        answer = "Fixture TMS. AI assistance. " + " ".join(parts)
        return response.model_copy(
            update={
                "answer": answer,
                "quality_score": 0,
                "route": "verified",
                "sources": [],
                "citations": [],
                "suggested_questions": [],
                "requires_confirmation": False,
                "action_summary": "",
                "cached": False,
                "ticket_id": None,
                "delivery_state": None,
            }
        )
    except Exception:
        logger.warning("verified resolution projection failed", exc_info=True)
        return response


def _replace_latest_session_answer(session: Any, *, question: str, answer: str) -> None:
    """Keep in-memory history aligned with the response the endpoint returns."""
    history = (
        getattr(session, "_history", None)
        if hasattr(session, "_history")
        else session.get("history")
        if isinstance(session, dict)
        else None
    )
    if (
        isinstance(history, list)
        and len(history) >= 2
        and history[-2] == {"role": "user", "content": question}
        and isinstance(history[-1], dict)
        and history[-1].get("role") == "assistant"
    ):
        history[-1] = {"role": "assistant", "content": answer}


async def _persist_ask_messages(
    session_id: str,
    tenant_id: str,
    question: str,
    answer: str,
    path: str,
) -> None:
    """Persist ask messages only when Session is owned by ``tenant_id``.

    Shared by sync / SSE / fallback paths so foreign or missing owners never
    receive a write. Ownership rejection is silent (no write); a real DB
    failure puts this tenant -- and only this tenant -- in cooldown.
    """
    _app = _app_module()
    if _app._db_cooldown.blocked(tenant_id):
        return
    try:
        session_uuid = uuid.UUID(str(session_id))
    except (TypeError, ValueError, AttributeError):
        return

    try:
        from sqlalchemy import select

        from db.engine import async_session as db_session_factory
        from db.models import Message
        from db.models import Session as DBSession

        settings = _app.get_settings()
        timeout = float(getattr(settings, "db_persist_timeout_sec", 2.0))
        async with db_session_factory() as db:
            owned = await asyncio.wait_for(
                db.execute(
                    select(DBSession.id)
                    .where(DBSession.id == session_uuid)
                    .where(DBSession.tenant_id == tenant_id)
                ),
                timeout=timeout,
            )
            if owned.scalar_one_or_none() is None:
                return
            db.add(
                Message(
                    session_id=session_uuid,
                    tenant_id=tenant_id,
                    role="user",
                    content=question,
                )
            )
            db.add(
                Message(
                    session_id=session_uuid,
                    tenant_id=tenant_id,
                    role="assistant",
                    content=answer,
                )
            )
            await asyncio.wait_for(db.commit(), timeout=timeout)
            _app._db_cooldown.clear(tenant_id)
    except Exception as exc:
        _app._db_cooldown.record_failure(tenant_id)
        try:
            prometheus_metrics.record_message_persist_failure(path)
        except Exception:
            pass
        logger.warning("Failed to persist messages (%s): %s", path, exc)


@router.post("/ask", response_model=AskResponse)
@limiter.limit("60/minute")
async def ask(
    request: Request,
    body: AskRequest,
    _user: dict = Depends(get_current_user),
) -> AskResponse:
    """Ask a question to the RAG assistant."""
    # A durable turn (phase A.2) has to end on every way out of the handler,
    # including the ones that raise, so the handler hands it back through this
    # slot and the cleanup lives here. Wrapping the four hundred lines below in
    # a try/finally would say the same thing and bury the change that says it.
    turn_slot: list[_DurableTurn] = []
    try:
        return await _answer_ask(request, body, _user, turn_slot)
    finally:
        await _settle_durable_turn(turn_slot)


async def _answer_ask(
    request: Request,
    body: AskRequest,
    _user: dict,
    turn_slot: list[_DurableTurn],
) -> AskResponse:
    _app = _app_module()
    t0 = time.monotonic()
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is empty")

    settings = _app.get_settings()
    timeout = float(getattr(settings, "request_timeout_sec", TIME_LIMIT_CEILING_SEC))
    request_id = get_request_id()
    logger.info(
        "req_id=%s /api/ask effective_timeouts request=%.3fs "
        "ask_budget=%.3fs ollama_mistral=%.3fs gracekelly=%.3fs "
        "profile=%s",
        request_id or "-",
        timeout,
        float(getattr(settings, "ask_budget_sec", 0.0) or 0.0),
        float(getattr(settings, "ollama_request_timeout_sec", TIME_LIMIT_CEILING_SEC)),
        float(getattr(settings, "gracekelly_request_timeout_sec", 30.0)),
        str(getattr(settings, "llm_provider_profile", "local-first")),
        extra={"trace_id": request_id},
    )

    tenant = get_current_tenant() or _user.get("tenant", "default")
    session_started_at = time.monotonic()
    logger.info(
        "req_id=%s /api/ask session_setup boundary=start monotonic=%.6f",
        request_id or "-",
        session_started_at,
        extra={"trace_id": request_id},
    )
    try:
        session_id, session = await _app._get_or_create_session(body.session_id, tenant)
    finally:
        session_finished_at = time.monotonic()
        logger.info(
            "req_id=%s /api/ask session_setup boundary=end monotonic=%.6f elapsed=%.6fs",
            request_id or "-",
            session_finished_at,
            session_finished_at - session_started_at,
            extra={"trace_id": request_id},
        )

    durable_turn = await _admit_durable_turn(
        tenant_id=tenant,
        session_id=session_id,
        question=question,
        confirm=bool(body.confirm),
    )
    if durable_turn is not None:
        turn_slot.append(durable_turn)

    cache_enabled = bool(getattr(settings, "llm_cache_enabled", False))
    if cache_enabled:
        # Cache applies to history-less first turns only. A follow-up inside a
        # dialog ("а сколько это стоит?") depends on conversation context, so
        # caching it — or serving it from cache — would leak answers across
        # unrelated dialogs. The key itself is versioned by tenant, active
        # index, effective prompts, model route, and normalized query (§9.1c).
        session_history = (
            getattr(session, "_history", None)
            if hasattr(session, "_history")
            else session.get("history")
            if isinstance(session, dict)
            else None
        )
        if session_history:
            cache_enabled = False
    llm_cache_key: str | None = None
    if cache_enabled:
        llm_cache_key = _app._cache_key(
            tenant,
            question,
            user_id=str(_user.get("sub", "anonymous")),
            session_id=session_id,
            settings=settings,
        )
        # Fail closed: if any required identity cannot be resolved safely,
        # skip both cache lookup and cache write for this request.
        if not llm_cache_key:
            cache_enabled = False
    cache_hit = False
    # Provenance for the QUALITY_SCORE metric; cached replays keep their
    # original "llm" provenance, agentic unmeasured paths report "unmeasured".
    quality_source = "llm"

    if hasattr(session, "ask"):
        if cache_enabled:
            cached_payload = _app.cache_json_get(llm_cache_key)
            if isinstance(cached_payload, dict) and cached_payload.get("answer"):
                try:
                    prometheus_metrics.LLM_CACHE_HITS.labels(tenant=tenant).inc()
                except Exception:
                    pass

                answer = str(cached_payload.get("answer") or "")
                cached_sources = []
                for item in cached_payload.get("sources", [])[:5]:
                    if not isinstance(item, dict):
                        continue
                    cached_sources.append(
                        SourceInfo(
                            source=item.get("source", ""),
                            page_content=item.get("page_content", ""),
                        )
                    )
                cached_citations = []
                for item in cached_payload.get("citations", []):
                    if not isinstance(item, dict):
                        continue
                    cached_citations.append(
                        Citation(
                            index=int(item.get("index") or 0),
                            doc_id=str(item.get("doc_id") or ""),
                            title=str(item.get("title") or ""),
                            excerpt=str(item.get("excerpt") or ""),
                        )
                    )
                if not cached_citations:
                    for idx, source in enumerate(cached_sources, start=1):
                        cached_citations.append(
                            Citation(
                                index=idx,
                                doc_id=source.source or f"doc_{idx}",
                                title=source.source or f"doc_{idx}",
                                excerpt=(source.page_content or "")[:300],
                            )
                        )

                if hasattr(session, "_history"):
                    session._history.append({"role": "user", "content": question})
                    session._history.append({"role": "assistant", "content": answer})
                    max_history = getattr(session, "_max_history", 20)
                    if len(session._history) > max_history * 2:
                        session._history = session._history[-(max_history * 2) :]
                elif isinstance(session, dict):
                    session["history"].append({"role": "user", "content": question})
                    session["history"].append({"role": "assistant", "content": answer})

                response = AskResponse(
                    answer=answer,
                    quality_score=int(cached_payload.get("quality_score") or 50),
                    route=str(cached_payload.get("route") or "auto"),
                    sources=cached_sources,
                    citations=cached_citations,
                    session_id=session_id,
                    trace_id="",
                    suggested_questions=cached_payload.get("suggested_questions") or [],
                    cached=True,
                )
                cache_hit = True
            else:
                try:
                    prometheus_metrics.LLM_CACHE_MISSES.labels(tenant=tenant).inc()
                except Exception:
                    pass

        if not cache_hit:
            acquire_timeout = float(getattr(settings, "pipeline_acquire_timeout_sec", 0.5))
            ask_kwargs: dict[str, Any] = {
                "trace_id": request_id,
                "tenant_id": tenant,
                "confirm": body.confirm,
                "user_id": _user.get("sub", "anonymous"),
                "session_id": session_id,
                # Cooperative provider deadline matches outer wait_for wall (§3.1b).
                "deadline_sec": float(timeout),
            }
            semaphore = _app._get_pipeline_semaphore()
            try:
                await asyncio.wait_for(semaphore.acquire(), timeout=acquire_timeout)
            except asyncio.TimeoutError:
                try:
                    prometheus_metrics.record_pipeline_rejection("busy")
                except Exception:
                    pass
                logger.warning(
                    "req_id=%s /api/ask rejected: pipeline pool saturated",
                    request_id or "-",
                )
                raise HTTPException(
                    status_code=503,
                    detail="Server is busy processing other requests - retry in a moment",
                ) from None
            # Hold pipeline capacity until the underlying worker finishes.
            # asyncio.wait_for only cancels the wait — not the thread (REL-01 / §3.1a).
            capacity_held_for_orphan = False
            try:
                prometheus_metrics.INFLIGHT_PIPELINES.inc()
                try:
                    from utils.request_executor import get_request_executor

                    try:
                        result = await pipeline_runner.run_sync_with_deadline(
                            executor=get_request_executor(),
                            operation=lambda: session.ask(question, **ask_kwargs),
                            timeout=timeout,
                            semaphore=semaphore,
                            release_capacity=_release_pipeline_capacity,
                        )
                    except asyncio.TimeoutError:
                        # PipelineRunner keeps semaphore + inflight until worker end.
                        capacity_held_for_orphan = True
                        try:
                            prometheus_metrics.record_request_timeout("/api/ask")
                        except Exception:
                            pass
                        outer_timeout_at = time.monotonic()
                        logger.warning(
                            "req_id=%s /api/ask exceeded timeout=%.1fs "
                            "outer_timeout_monotonic=%.6f capacity_held_until_done=1",
                            request_id or "-",
                            timeout,
                            outer_timeout_at,
                            extra={"trace_id": request_id},
                        )
                        raise HTTPException(
                            status_code=504,
                            detail=f"Request exceeded {timeout:.0f}s wall-time limit",
                        ) from None

                    answer = result.get("answer") or ""
                    quality = result.get("quality_score") or 50
                    route = result.get("route") or "auto"
                    quality_source = str(result.get("quality_source") or "llm")

                    sources_list = []
                    citations_list = []
                    docs = result.get("graded_docs") or result.get("context_docs") or []
                    for idx, doc in enumerate(docs, start=1):
                        if isinstance(doc, dict):
                            metadata = doc.get("metadata", {}) or {}
                            src = metadata.get("source") or metadata.get("file_name") or ""
                            content = doc.get("page_content", "")
                        else:
                            metadata = getattr(doc, "metadata", {}) or {}
                            src = metadata.get("source") or metadata.get("file_name") or ""
                            content = getattr(doc, "page_content", "")
                        sources_list.append(SourceInfo(source=src, page_content=content))
                        citations_list.append(
                            Citation(
                                index=idx,
                                doc_id=str(
                                    metadata.get("doc_id")
                                    or metadata.get("id")
                                    or src
                                    or f"doc_{idx}"
                                ),
                                title=str(
                                    metadata.get("title")
                                    or src
                                    or metadata.get("file_name")
                                    or f"doc_{idx}"
                                ),
                                excerpt=str(content or "")[:300],
                            )
                        )
                    if result.get("citations"):
                        citations_list = [
                            Citation(
                                index=int(item.get("index") or 0),
                                doc_id=str(item.get("doc_id") or ""),
                                title=str(item.get("title") or ""),
                                excerpt=str(item.get("excerpt") or ""),
                            )
                            for item in result.get("citations", [])
                            if isinstance(item, dict)
                        ]

                    # Pass through graph-owned escalation identity when present
                    # (handle_error / agentic create_ticket); otherwise §4.4
                    # auto-escalates terminal human/error on the normal path.
                    ticket_id = result.get("ticket_id")
                    delivery_state = result.get("delivery_state")
                    if ticket_id is not None:
                        ticket_id = str(ticket_id) or None
                    if delivery_state is not None:
                        delivery_state = str(delivery_state) or None

                    route_norm = str(route or "auto").strip().lower() or "auto"
                    if route_norm in _TERMINAL_ESCALATE_ROUTES and not ticket_id:
                        from services.escalation import create_escalation

                        try:
                            esc = await create_escalation(
                                tenant_id=tenant or "default",
                                session_id=session_id,
                                question=question,
                                source="human_route",
                                ai_draft=answer or None,
                                reason=f"route={route_norm}",
                                trace_id=str(result.get("trace_id") or request_id or ""),
                                project_root=Path(getattr(_app, "PROJECT_ROOT", Path("."))),
                            )
                            ticket_id = esc.ticket_id
                            delivery_state = esc.delivery_state
                            # Keep the pipeline answer (AI draft). Never inject a
                            # false "передан оператору" claim when durable failed.
                            # Operator-facing copy lives on the ticket / ai_draft.
                        except Exception as esc_exc:
                            logger.error(
                                "Auto-escalation on route=%s failed: %s",
                                route_norm,
                                esc_exc,
                                exc_info=True,
                            )
                            ticket_id = None
                            delivery_state = "failed"

                    response = AskResponse(
                        answer=answer,
                        quality_score=quality,
                        route=route,
                        sources=sources_list,
                        citations=citations_list,
                        session_id=session_id,
                        trace_id=result.get("trace_id") or "",
                        suggested_questions=result.get("suggested_questions") or [],
                        requires_confirmation=bool(result.get("requires_confirmation")),
                        action_summary=str(result.get("action_summary") or ""),
                        ticket_id=ticket_id,
                        delivery_state=delivery_state,
                    )
                    if (
                        cache_enabled
                        and response.answer
                        and response.route == "auto"
                        and not response.requires_confirmation
                        and not result.get("tool_calls")
                    ):
                        _app.cache_json_set(
                            llm_cache_key,
                            {
                                "answer": response.answer,
                                "quality_score": response.quality_score,
                                "route": response.route,
                                "sources": [source.model_dump() for source in response.sources],
                                "suggested_questions": response.suggested_questions,
                            },
                            ttl_seconds=int(getattr(settings, "llm_cache_ttl_seconds", 3600)),
                        )
                except HTTPException:
                    raise
                except Exception as exc:
                    logger.error("Pipeline error in /ask: %s", exc, exc_info=True)
                    # Plan §4.3: single idempotent escalation service — claim
                    # operator handoff only after durable ticket insert.
                    from services.escalation import create_escalation

                    draft = (
                        f"Запрос пользователя: {question}\n\n"
                        "Черновик ответа: Произошла техническая ошибка "
                        "при обработке запроса. Пожалуйста, ответьте "
                        "пользователю вручную."
                    )
                    esc = await create_escalation(
                        tenant_id=tenant or "default",
                        session_id=session_id,
                        question=question,
                        source="pipeline_error",
                        ai_draft=draft,
                        reason="pipeline_exception",
                        trace_id=request_id or "",
                        project_root=Path(getattr(_app, "PROJECT_ROOT", Path("."))),
                    )
                    answer = esc.user_message
                    if hasattr(session, "_history"):
                        session._history.append({"role": "user", "content": question})
                        session._history.append({"role": "assistant", "content": answer})
                    elif isinstance(session, dict):
                        session["history"].append({"role": "user", "content": question})
                        session["history"].append({"role": "assistant", "content": answer})
                    response = AskResponse(
                        answer=answer,
                        quality_score=0,
                        route="human" if esc.durable else "error",
                        sources=[],
                        citations=[],
                        session_id=session_id,
                        trace_id=request_id or "",
                        suggested_questions=[],
                        ticket_id=esc.ticket_id,
                        delivery_state=esc.delivery_state,
                    )
            finally:
                # On outer timeout the done-callback owns release (capacity hold).
                if not capacity_held_for_orphan:
                    _release_pipeline_capacity(semaphore)
    else:
        session["history"].append({"role": "user", "content": question})
        fallback_answer = f"[DEMO] Pipeline not available. Question received: {question}"
        session["history"].append({"role": "assistant", "content": fallback_answer})
        response = AskResponse(
            answer=fallback_answer,
            quality_score=0,
            route="human",
            sources=[],
            citations=[],
            session_id=session_id,
            trace_id="",
            suggested_questions=[],
        )

    clarification_journeys = tuple(getattr(settings, "resolution_clarification_journeys", ()) or ())
    response_journeys = tuple(getattr(settings, "resolution_response_journeys", ()) or ())
    shadow_results: list[Any] = []
    if clarification_journeys or response_journeys:
        response = _run_resolution_shadows(
            response=response,
            tenant_id=tenant,
            session_id=session_id,
            correlation_id=request_id or "",
            question=question,
            trace_id=getattr(response, "trace_id", "") or request_id or "",
            collect=shadow_results,
        )
        projected_response = _project_resolution_clarification(
            response=response,
            results=shadow_results,
            journeys=clarification_journeys,
        )
        if projected_response is response:
            projected_response = _project_resolution_response(
                response=response,
                results=shadow_results,
                journeys=response_journeys,
            )
        if projected_response is not response:
            response = projected_response
            quality_source = "unmeasured"
            _replace_latest_session_answer(session, question=question, answer=response.answer)

    # A durable turn owns its own write: `commit_turn` puts the pair and the
    # turn's terminal state in one transaction. Only the pre-A.2 path falls
    # through to the best-effort write, and a commit that failed does not fall
    # back to it -- one turn may not write its pair twice.
    committed = False
    if durable_turn is not None:
        committed = await _commit_durable_turn(
            durable_turn,
            question=question,
            answer=response.answer,
        )
    if durable_turn is None:
        await _persist_ask_messages(
            session_id=session_id,
            tenant_id=tenant,
            question=question,
            answer=response.answer,
            path="ask",
        )
    else:
        logger.debug(
            "req_id=%s /api/ask durable turn %s committed=%s",
            request_id or "-",
            durable_turn.turn_id,
            committed,
        )

    await _app.log_audit(
        actor=_user.get("sub", "anonymous"),
        action="ask",
        resource=f"session:{session_id}",
        tenant_id=tenant,
        detail={
            "question_length": len(body.question),
            "tenant": tenant,
        },
        ip_address=request.client.host if request.client else None,
    )
    duration = time.monotonic() - t0
    prometheus_metrics.REQUEST_DURATION.observe(duration)
    prometheus_metrics.REQUEST_COUNT.labels(route=response.route).inc()
    if response.quality_score:
        prometheus_metrics.QUALITY_SCORE.observe(response.quality_score)
        try:
            prometheus_metrics.record_quality_score_source(quality_source)
        except Exception:
            pass
    if response.route == "human":
        prometheus_metrics.ESCALATION_TOTAL.inc()
    prometheus_metrics.ACTIVE_SESSIONS.set(len(_app._sessions))
    if response.citations:
        spawn_tracked(_app._record_citation_stats(tenant, list(response.citations)))
    if not clarification_journeys and not response_journeys:
        response = _run_resolution_shadows(
            response=response,
            tenant_id=tenant,
            session_id=session_id,
            correlation_id=request_id or "",
            question=question,
            trace_id=getattr(response, "trace_id", "") or request_id or "",
            collect=shadow_results,
        )
    await _persist_shadow_evidence(shadow_results)
    return JSONResponse(
        content=response.model_dump(),
        media_type="application/json; charset=utf-8",
    )


@router.post("/chat")
@limiter.limit("60/minute")
async def chat(
    request: Request,
    body: AskRequest,
    _user: dict = Depends(get_current_user),
) -> AskResponse:
    return await ask(request, body, _user)


@router.post("/ask/stream")
@limiter.limit("60/minute")
async def ask_stream(
    request: Request,
    body: AskRequest,
    _user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """SSE endpoint с реальным стримингом токенов из Ollama."""
    _app = _app_module()

    # The session's refusals (404, 503) are HTTP errors and must come before the
    # first byte: raised inside the generator they found the response already
    # started, and the client got a stream that ended after ``status``.
    tenant = get_current_tenant() or _user.get("tenant", "default")
    session_id, session = await _app._get_or_create_session(body.session_id, tenant)

    async def event_generator() -> AsyncGenerator[str, None]:
        yield "data: " + _json.dumps({"type": "status", "node": "processing"}) + "\n\n"

        question = (body.question or "").strip()

        if not question:
            yield (
                "data: "
                + _json.dumps(
                    {
                        "type": "error",
                        "detail": "question is required",
                    }
                )
                + "\n\n"
            )
            return

        await _app.log_audit(
            actor=_user.get("sub", "anonymous"),
            action="ask",
            resource=f"session:{session_id}",
            tenant_id=tenant,
            detail={
                "question_length": len(body.question),
                "tenant": tenant,
            },
            ip_address=request.client.host if request.client else None,
        )

        # The except-branch below reuses graph_task/_session_ask; they must exist
        # even when the failure happens before their full initialization,
        # otherwise the fallback itself dies with NameError and the SSE stream
        # ends without a result event.
        graph_task: asyncio.Future | None = None
        request_id = get_request_id()
        settings_pre = _app.get_settings()
        request_timeout = float(
            getattr(settings_pre, "request_timeout_sec", TIME_LIMIT_CEILING_SEC)
        )
        capacity_held_for_orphan = False
        loop = asyncio.get_running_loop()

        def _session_ask() -> Any:
            """Parity/fallback full-graph ask with cooperative deadline kwargs."""
            return session.ask(
                question,
                trace_id=request_id,
                tenant_id=tenant,
                confirm=body.confirm,
                user_id=_user.get("sub", "anonymous"),
                session_id=session_id,
                deadline_sec=request_timeout,
            )

        # Streaming consumes the same retriever/LLM resources as /api/ask —
        # it must respect the same bounded-concurrency pool instead of
        # bypassing it (archive/docs/audits/fable_com.md F-3).
        semaphore = _app._get_pipeline_semaphore()
        acquire_timeout = float(getattr(settings_pre, "pipeline_acquire_timeout_sec", 0.5))
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=acquire_timeout)
        except asyncio.TimeoutError:
            try:
                prometheus_metrics.record_pipeline_rejection("busy")
            except Exception:
                pass
            yield (
                "data: "
                + _json.dumps(
                    {
                        "type": "error",
                        "detail": "Server is busy processing other requests - retry in a moment",
                    }
                )
                + "\n\n"
            )
            return
        try:
            prometheus_metrics.INFLIGHT_PIPELINES.inc()
        except Exception:
            pass

        # Bind deadline + LLM budget for stream-side provider work (3.1f).
        # Parity worker reuses the same budget object via ContextVar install.
        from llm.request_budget import (
            bind_llm_request_budget_from_settings,
            clear_llm_request_budget,
            get_llm_request_budget,
            set_llm_request_budget,
        )
        from utils.request_deadline import (
            RequestDeadlineExceeded,
            bind_request_deadline,
            check_request_deadline,
            clear_request_deadline,
            set_request_deadline,
        )
        from utils.request_executor import get_request_executor

        stream_deadline_obj = bind_request_deadline(request_timeout, source="ask_stream")
        stream_budget_obj = bind_llm_request_budget_from_settings(settings_pre, source="ask_stream")

        def _session_ask_with_shared_limits() -> Any:
            if stream_deadline_obj is not None:
                set_request_deadline(stream_deadline_obj)
            if stream_budget_obj is not None:
                set_llm_request_budget(stream_budget_obj)
            return _session_ask()

        try:
            prompt = ""
            stream_retrieved = False
            docs: list[Any] = []
            plain_docs: list[dict[str, Any]] = []
            chat_history: list[dict[str, str]] = []
            # Plan §4.1–4.2: STREAMING_RAG_PARITY=true → single graph generation
            # (session.ask only). SSE tokens are UX chunks of the graph answer —
            # not a second LLM stream. Off by default keeps legacy direct stream.
            graph_parity_enabled = bool(getattr(settings_pre, "streaming_rag_parity", False))
            graph_parity_timeout = float(
                getattr(settings_pre, "request_timeout_sec", TIME_LIMIT_CEILING_SEC)
            )
            history_pre_len = (
                len(getattr(session, "_history", [])) if hasattr(session, "_history") else None
            )
            settings = _app.get_settings()

            if graph_parity_enabled and (
                hasattr(session, "iter_ask_events") or hasattr(session, "ask")
            ):
                # --- 4.2/4.7 single graph path (no parallel stream LLM) ---
                # Prefer iter_ask_events (§4.7): real LangGraph node status SSE.
                # Fall back to session.ask for test doubles without event stream.
                graph_result: dict[str, Any] | None = None
                graph_nodes: list[str] = []
                use_events = callable(getattr(session, "iter_ask_events", None))

                # Plan §4.8: live provider tokens from generate (when available).
                provider_tokens_seen = False
                token_start_emitted = False

                if use_events:
                    event_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

                    def _session_events_worker() -> None:
                        try:
                            if stream_deadline_obj is not None:
                                from utils.request_deadline import (  # noqa: PLC0415
                                    set_request_deadline,
                                )

                                set_request_deadline(stream_deadline_obj)
                            if stream_budget_obj is not None:
                                from llm.request_budget import (  # noqa: PLC0415
                                    set_llm_request_budget,
                                )

                                set_llm_request_budget(stream_budget_obj)
                            for ev in session.iter_ask_events(
                                question,
                                tenant_id=tenant,
                                user_id=str(_user.get("sub") or "anonymous"),
                                session_id=session_id,
                                trace_id=request_id,
                                confirm=body.confirm,
                            ):
                                loop.call_soon_threadsafe(event_queue.put_nowait, ("event", ev))
                            loop.call_soon_threadsafe(event_queue.put_nowait, ("done", None))
                        except Exception as worker_exc:  # noqa: BLE001
                            loop.call_soon_threadsafe(event_queue.put_nowait, ("error", worker_exc))

                    graph_task = pipeline_runner.submit_stream_graph(
                        loop=loop,
                        executor=get_request_executor(),
                        operation=_session_events_worker,
                    )
                    try:
                        while True:
                            try:
                                kind, payload = await pipeline_runner.wait_stream_queue_event(
                                    queue=event_queue,
                                    timeout=graph_parity_timeout,
                                    fut=graph_task,
                                    semaphore=semaphore,
                                    release_capacity=_release_pipeline_capacity,
                                    loop=loop,
                                )
                            except asyncio.TimeoutError:
                                logger.warning(
                                    "Streaming graph events exceeded %.1fs timeout; "
                                    "holding pipeline capacity until orphan completes",
                                    graph_parity_timeout,
                                )
                                capacity_held_for_orphan = True
                                try:
                                    prometheus_metrics.record_request_timeout("/api/ask/stream")
                                except Exception:
                                    pass
                                yield (
                                    "data: "
                                    + _json.dumps(
                                        {
                                            "type": "error",
                                            "detail": "Request deadline exceeded waiting for graph",
                                            "route": "timeout",
                                            "generation_source": "graph_only",
                                        }
                                    )
                                    + "\n\n"
                                )
                                return

                            if kind == "error":
                                logger.warning("Streaming graph event path failed: %s", payload)
                                yield (
                                    "data: "
                                    + _json.dumps(
                                        {
                                            "type": "error",
                                            "detail": "Graph pipeline failed",
                                            "route": "error",
                                            "generation_source": "graph_only",
                                        }
                                    )
                                    + "\n\n"
                                )
                                return
                            if kind == "done":
                                break
                            if not isinstance(payload, dict):
                                continue
                            if payload.get("type") == "status":
                                node_name = str(payload.get("node") or "unknown")
                                graph_nodes.append(node_name)
                                yield (
                                    "data: "
                                    + _json.dumps(
                                        {
                                            "type": "status",
                                            "node": node_name,
                                            "source": "graph",
                                            "phase": str(payload.get("phase") or "end"),
                                        }
                                    )
                                    + "\n\n"
                                )
                            elif payload.get("type") == "token":
                                # Live provider tokens from generate (§4.8).
                                token_text = str(payload.get("token") or "")
                                if not token_text:
                                    continue
                                token_source = str(
                                    payload.get("token_source") or "provider_generate"
                                )
                                if not token_start_emitted:
                                    token_start_emitted = True
                                    yield (
                                        "data: "
                                        + _json.dumps(
                                            {
                                                "type": "token_start",
                                                "source": "graph",
                                                "token_source": token_source,
                                            }
                                        )
                                        + "\n\n"
                                    )
                                if token_source == "provider_generate":
                                    provider_tokens_seen = True
                                yield (
                                    "data: "
                                    + _json.dumps(
                                        {
                                            "type": "token",
                                            "token": token_text,
                                            "source": "graph",
                                            "token_source": token_source,
                                        }
                                    )
                                    + "\n\n"
                                )
                            elif payload.get("type") == "pipeline_result":
                                state = payload.get("state")
                                if isinstance(state, dict):
                                    graph_result = state
                                nodes = payload.get("nodes")
                                if isinstance(nodes, list):
                                    for n in nodes:
                                        name = str(n)
                                        if name and name not in graph_nodes:
                                            graph_nodes.append(name)
                    except Exception as graph_exc:
                        logger.warning("Streaming graph event path failed: %s", graph_exc)
                        yield (
                            "data: "
                            + _json.dumps(
                                {
                                    "type": "error",
                                    "detail": "Graph pipeline failed",
                                    "route": "error",
                                    "generation_source": "graph_only",
                                }
                            )
                            + "\n\n"
                        )
                        return
                else:
                    # Legacy §4.2 ask-only path (test doubles without events).
                    graph_task = pipeline_runner.submit_stream_graph(
                        loop=loop,
                        executor=get_request_executor(),
                        operation=_session_ask_with_shared_limits,
                    )
                    try:
                        graph_result = await pipeline_runner.wait_stream_future_result(
                            fut=graph_task,
                            timeout=graph_parity_timeout,
                            semaphore=semaphore,
                            release_capacity=_release_pipeline_capacity,
                            loop=loop,
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            "Streaming graph path exceeded %.1fs timeout; "
                            "holding pipeline capacity until orphan completes",
                            graph_parity_timeout,
                        )
                        capacity_held_for_orphan = True
                        try:
                            prometheus_metrics.record_request_timeout("/api/ask/stream")
                        except Exception:
                            pass
                        yield (
                            "data: "
                            + _json.dumps(
                                {
                                    "type": "error",
                                    "detail": "Request deadline exceeded waiting for graph",
                                    "route": "timeout",
                                    "generation_source": "graph_only",
                                }
                            )
                            + "\n\n"
                        )
                        return
                    except Exception as graph_exc:
                        logger.warning("Streaming graph path failed: %s", graph_exc)
                        yield (
                            "data: "
                            + _json.dumps(
                                {
                                    "type": "error",
                                    "detail": "Graph pipeline failed",
                                    "route": "error",
                                    "generation_source": "graph_only",
                                }
                            )
                            + "\n\n"
                        )
                        return

                if not isinstance(graph_result, dict):
                    yield (
                        "data: "
                        + _json.dumps(
                            {
                                "type": "error",
                                "detail": "Graph pipeline returned no result",
                                "route": "error",
                                "generation_source": "graph_only",
                            }
                        )
                        + "\n\n"
                    )
                    return

                graph_appended_history = False
                if (
                    history_pre_len is not None
                    and hasattr(session, "_history")
                    and len(session._history) > history_pre_len
                ):
                    graph_appended_history = True

                terminal_answer = str(graph_result.get("answer") or "")
                # Plan §4.8: if live provider tokens already streamed, do not
                # re-chunk the finished answer. Else §4.7 UX chunk fallback.
                if provider_tokens_seen:
                    token_source_final = "provider_generate"
                else:
                    token_source_final = "graph_answer_chunks"
                    if not token_start_emitted:
                        yield (
                            "data: "
                            + _json.dumps(
                                {
                                    "type": "token_start",
                                    "source": "graph",
                                    "token_source": token_source_final,
                                }
                            )
                            + "\n\n"
                        )
                    for chunk in _chunk_text_for_sse(terminal_answer):
                        yield (
                            "data: "
                            + _json.dumps(
                                {
                                    "type": "token",
                                    "token": chunk,
                                    "source": "graph",
                                    "token_source": token_source_final,
                                }
                            )
                            + "\n\n"
                        )

                if not graph_appended_history:
                    _append_stream_history(
                        session,
                        question=question,
                        answer=terminal_answer,
                    )

                quality = int(graph_result.get("quality_score") or 0)
                quality_source = str(graph_result.get("quality_source") or "llm")
                route = str(graph_result.get("route") or "human")
                trace_id_value = str(graph_result.get("trace_id") or "")
                suggested_questions = list(graph_result.get("suggested_questions") or [])
                sources, citations = _graph_result_sources_and_citations(graph_result)

                await _persist_ask_messages(
                    session_id=session_id,
                    tenant_id=tenant,
                    question=question,
                    answer=terminal_answer,
                    path="stream",
                )
                try:
                    prometheus_metrics.record_quality_score_source(quality_source)
                except Exception:
                    pass
                yield (
                    "data: "
                    + _json.dumps(
                        {
                            "type": "result",
                            "answer": terminal_answer,
                            "answer_source": "graph",
                            "generation_source": "graph_only",
                            "events_source": "graph" if use_events else "ask",
                            "token_source": token_source_final,
                            "graph_nodes": graph_nodes,
                            "quality_score": quality,
                            "quality_source": quality_source,
                            "route": route,
                            "session_id": session_id,
                            "sources": sources,
                            "citations": citations,
                            "trace_id": trace_id_value,
                            "suggested_questions": suggested_questions,
                        }
                    )
                    + "\n\n"
                )
                return

            # --- Legacy direct stream (parity off): single stream LLM path ---
            if hasattr(session, "_retriever") and session._retriever is not None:
                # Cooperative deadline (plan §3.1g): refuse stream retrieve after wall.
                try:
                    check_request_deadline("stream.retrieve")
                except RequestDeadlineExceeded as deadline_exc:
                    logger.warning(
                        "Streaming retrieve refused after deadline: %s",
                        deadline_exc,
                    )
                    try:
                        prometheus_metrics.record_request_timeout("/api/ask/stream")
                    except Exception:
                        pass
                    yield (
                        "data: "
                        + _json.dumps(
                            {
                                "type": "error",
                                "detail": "Request deadline exceeded before retrieval",
                                "route": "timeout",
                            }
                        )
                        + "\n\n"
                    )
                    return
                docs = await asyncio.get_running_loop().run_in_executor(
                    None,
                    session._retriever.get_relevant_documents,
                    question,
                )

                if hasattr(session, "history"):
                    chat_history = session.history
                elif isinstance(session, dict):
                    chat_history = session.get("history", [])

                plain_docs = []
                for doc in docs[:5]:
                    if hasattr(doc, "page_content"):
                        plain_docs.append(
                            {
                                "page_content": getattr(doc, "page_content", ""),
                                "metadata": getattr(doc, "metadata", {}) or {},
                            }
                        )
                    elif isinstance(doc, dict):
                        plain_docs.append(doc)
                stream_retrieved = True

            settings = _app.get_settings()
            full_answer = ""
            streaming_llm: Any = getattr(session, "_llm", None)
            if (
                not (
                    streaming_llm is not None
                    and callable(getattr(streaming_llm, "generate_stream", None))
                )
                and _app._build_provider_runtime is not None
            ):
                try:
                    runtime = _app._build_provider_runtime(settings)
                except Exception as runtime_exc:
                    logger.warning("Streaming runtime unavailable: %s", runtime_exc)
                else:
                    for candidate in (runtime.strong, runtime.fast):
                        if callable(getattr(candidate, "generate_stream", None)):
                            streaming_llm = candidate
                            break

            uses_provider_stream = streaming_llm is not None and callable(
                getattr(streaming_llm, "generate_stream", None)
            )
            # The raw Ollama fallback sends num_ctx from settings.
            window_owner = (
                streaming_llm
                if uses_provider_stream
                else SimpleNamespace(
                    context_window=int(getattr(settings, "ollama_context_window", 4096))
                )
            )
            if stream_retrieved:
                # The model sees only what fits its input window; the sources,
                # citations and self-eval below describe that same view.
                prompt, plain_docs = _fit_stream_prompt(
                    window_owner, question, plain_docs, chat_history
                )
                docs = plain_docs
            if not prompt:
                raise RuntimeError("streaming prompt unavailable")
            from llm.role_params import generation_kwargs_for_role  # noqa: PLC0415

            stream_params = generation_kwargs_for_role("generate")

            # Wall-clock budget for the token loop: without it a wedged model
            # holds the SSE connection (and now a pipeline slot) forever.
            stream_deadline = time.monotonic() + float(
                getattr(settings, "streaming_timeout_sec", TIME_LIMIT_CEILING_SEC)
            )
            stream_truncated = False
            yield "data: " + _json.dumps({"type": "token_start"}) + "\n\n"
            try:
                if uses_provider_stream:
                    async for token in streaming_llm.generate_stream(
                        [{"role": "user", "content": prompt}],
                        **stream_params,
                    ):
                        full_answer += token
                        yield (
                            "data: "
                            + _json.dumps(
                                {
                                    "type": "token",
                                    "token": token,
                                }
                            )
                            + "\n\n"
                        )
                        if time.monotonic() > stream_deadline:
                            stream_truncated = True
                            break
                else:
                    async for token in _app._stream_ollama(
                        prompt,
                        settings.ollama_model_name,
                        settings.ollama_base_url,
                        options={
                            "num_ctx": window_owner.context_window,
                            "num_predict": int(stream_params["max_tokens"]),
                            "temperature": float(stream_params["temperature"]),
                        },
                    ):
                        full_answer += token
                        yield (
                            "data: "
                            + _json.dumps(
                                {
                                    "type": "token",
                                    "token": token,
                                }
                            )
                            + "\n\n"
                        )
                        if time.monotonic() > stream_deadline:
                            stream_truncated = True
                            break
            except Exception as exc:
                logger.warning("Streaming error in /ask/stream: %s", exc)
                if not full_answer:
                    raise
            if stream_truncated:
                try:
                    prometheus_metrics.record_request_timeout("/api/ask/stream")
                except Exception:
                    pass
                logger.warning(
                    "Streaming exceeded %.0fs budget; answer truncated",
                    float(getattr(settings, "streaming_timeout_sec", TIME_LIMIT_CEILING_SEC)),
                )

            if not full_answer:
                raise RuntimeError("empty streaming answer")

            sources = []
            citations = []
            for idx, doc in enumerate(docs, start=1):
                if hasattr(doc, "page_content"):
                    metadata = getattr(doc, "metadata", {}) or {}
                    sources.append(
                        {
                            "source": metadata.get("source") or metadata.get("file_name") or "",
                            "page_content": getattr(doc, "page_content", ""),
                        }
                    )
                elif isinstance(doc, dict):
                    metadata = doc.get("metadata", {}) or {}
                    sources.append(
                        {
                            "source": metadata.get("source") or metadata.get("file_name") or "",
                            "page_content": doc.get("page_content", ""),
                        }
                    )
                else:
                    metadata = {}
                citations.append(
                    {
                        "index": idx,
                        "doc_id": str(
                            metadata.get("doc_id")
                            or metadata.get("id")
                            or metadata.get("source")
                            or metadata.get("file_name")
                            or f"doc_{idx}"
                        ),
                        "title": str(
                            metadata.get("title")
                            or metadata.get("source")
                            or metadata.get("file_name")
                            or metadata.get("doc_id")
                            or f"doc_{idx}"
                        ),
                        "excerpt": str(sources[-1]["page_content"] if sources else "")[:300],
                    }
                )

            # Cheap RAG parity (archive/docs/audits/fable_com.md F-3): one self-eval call over the
            # docs the stream actually used replaces the length heuristic, so
            # streamed answers stop reporting a synthetic quality of 70/40.
            heuristic_quality = 70 if len(full_answer.strip()) > 20 or sources else 40
            quality = heuristic_quality
            quality_source = "heuristic"
            if bool(getattr(settings, "streaming_quality_eval", True)):
                try:
                    from agent.graph import (  # noqa: PLC0415
                        LocalOllamaLLM,
                        _invoke_llm,
                        _parse_int_score,
                    )
                    from agent.prompts import build_self_eval_prompt  # noqa: PLC0415

                    eval_llm = getattr(session, "_llm", None)
                    if eval_llm is None and callable(getattr(streaming_llm, "invoke", None)):
                        eval_llm = streaming_llm
                    if eval_llm is None:
                        eval_llm = LocalOllamaLLM(model_name=settings.ollama_model_name)

                    from agent.context_window import fit_context_docs  # noqa: PLC0415

                    answer_for_eval = re.sub(r"\s*\[\d+\]", "", full_answer)
                    answer_for_eval = re.sub(r"\s{2,}", " ", answer_for_eval).strip()

                    def _eval_prompt(selected: list[dict[str, Any]]) -> str:
                        return build_self_eval_prompt(
                            question=question, answer=answer_for_eval, context_docs=selected
                        )

                    eval_prompt = _eval_prompt(
                        fit_context_docs(
                            eval_llm,
                            question + " " + answer_for_eval,
                            plain_docs,
                            _eval_prompt,
                            role="evaluate",
                        )
                    )
                    # Evaluate-role limits: the context above was fitted to them.
                    raw_eval = await asyncio.get_running_loop().run_in_executor(
                        None, lambda: _invoke_llm(eval_llm, eval_prompt, role="evaluate")
                    )
                    # "llm" provenance only when the model actually returned a
                    # numeric score; an unparseable reply keeps the heuristic
                    # quality AND its routing threshold (quality_threshold only
                    # applies to genuine LLM scores).
                    parsed_eval = _parse_int_score(raw_eval, default=-1)
                    if parsed_eval != -1:
                        quality = parsed_eval
                        quality_source = "llm"
                    else:
                        logger.warning(
                            "Streaming self-eval returned no numeric score; keeping heuristic quality"
                        )
                except Exception as eval_exc:
                    logger.warning(
                        "Streaming self-eval failed, falling back to heuristic quality: %s",
                        eval_exc,
                    )
            if quality_source == "llm":
                route = (
                    "auto"
                    if quality >= int(getattr(settings, "quality_threshold", 80))
                    else "human"
                )
            else:
                route = "auto" if quality >= 70 else "human"
            suggested_questions = []
            if route == "auto":
                try:
                    from agent.prompts import build_suggested_questions_prompt  # noqa: PLC0415

                    # The model that wrote the answer, as for the self-eval above:
                    # OLLAMA_MODEL_NAME may name another, and loading a second
                    # model per answer swaps an 8-GB host.
                    question_llm = getattr(session, "_llm", None)
                    if question_llm is None and callable(getattr(streaming_llm, "invoke", None)):
                        question_llm = streaming_llm
                    if question_llm is None:
                        from agent.graph import LocalOllamaLLM  # noqa: PLC0415

                        question_llm = LocalOllamaLLM(model_name=settings.ollama_model_name)

                    context_snippet = "\n\n".join(
                        source.get("page_content", "")
                        for source in sources[:2]
                        if source.get("page_content")
                    )[:500]
                    prompt = build_suggested_questions_prompt(
                        question=question,
                        answer=full_answer,
                        context_snippet=context_snippet,
                    )
                    raw_questions = await asyncio.get_running_loop().run_in_executor(
                        None,
                        question_llm.invoke,
                        prompt,
                    )
                    suggested_questions = [
                        re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
                        for line in raw_questions.strip().splitlines()
                        if line.strip()
                    ][:3]
                except Exception as suggest_exc:
                    logger.warning(
                        "Failed to generate streaming suggested questions: %s",
                        suggest_exc,
                    )
            trace_id_value = ""
            graph_appended_history = False
            graph_result = None
            if graph_task is not None:
                try:
                    graph_result = await pipeline_runner.wait_stream_future_result(
                        fut=graph_task,
                        timeout=graph_parity_timeout,
                        semaphore=semaphore,
                        release_capacity=_release_pipeline_capacity,
                        loop=loop,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Streaming RAG parity task exceeded %.1fs timeout; "
                        "holding pipeline capacity until orphan completes",
                        graph_parity_timeout,
                    )
                    # Thread work is not cancellable; hold capacity until done (3.1f).
                    # PipelineRunner already performed the single orphan handoff.
                    capacity_held_for_orphan = True
                    graph_result = None
                except Exception as graph_exc:
                    logger.warning("Streaming RAG parity task failed: %s", graph_exc)
                    graph_result = None
                # session.ask appends turns to session._history itself (see
                # ConversationSession._append_history). Detect growth so we do
                # not double-append after a successful graph mutation (plan §4.1).
                if (
                    history_pre_len is not None
                    and hasattr(session, "_history")
                    and len(session._history) > history_pre_len
                ):
                    graph_appended_history = True

            terminal_answer, skip_stream_history, answer_source = _resolve_stream_terminal(
                stream_answer=full_answer,
                graph_result=graph_result if isinstance(graph_result, dict) else None,
                graph_appended_history=graph_appended_history,
            )

            if not skip_stream_history:
                _append_stream_history(
                    session,
                    question=question,
                    answer=terminal_answer,
                )

            if isinstance(graph_result, dict) and graph_result:
                if graph_result.get("quality_score") is not None:
                    quality = int(graph_result["quality_score"])
                    quality_source = str(graph_result.get("quality_source") or "llm")
                if graph_result.get("route"):
                    route = str(graph_result["route"])
                if graph_result.get("trace_id"):
                    trace_id_value = str(graph_result["trace_id"])
                if graph_result.get("suggested_questions"):
                    suggested_questions = list(graph_result["suggested_questions"])
                graph_citations_raw = graph_result.get("citations") or []
                if graph_citations_raw:
                    citations = [
                        {
                            "index": int(item.get("index") or 0),
                            "doc_id": str(item.get("doc_id") or ""),
                            "title": str(item.get("title") or ""),
                            "excerpt": str(item.get("excerpt") or ""),
                        }
                        for item in graph_citations_raw
                        if isinstance(item, dict)
                    ]
                graph_graded = (
                    graph_result.get("graded_docs") or graph_result.get("context_docs") or []
                )
                if graph_graded:
                    sources = []
                    for item in graph_graded:
                        metadata = item.get("metadata", {}) if isinstance(item, dict) else {}
                        content = item.get("page_content", "") if isinstance(item, dict) else ""
                        sources.append(
                            {
                                "source": metadata.get("source") or metadata.get("file_name") or "",
                                "page_content": content,
                            }
                        )

            await _persist_ask_messages(
                session_id=session_id,
                tenant_id=tenant,
                question=question,
                answer=terminal_answer,
                path="stream",
            )
            try:
                prometheus_metrics.record_quality_score_source(quality_source)
            except Exception:
                pass
            yield (
                "data: "
                + _json.dumps(
                    {
                        "type": "result",
                        "answer": terminal_answer,
                        "answer_source": answer_source,
                        "generation_source": "stream",
                        "quality_score": quality,
                        "quality_source": quality_source,
                        "route": route,
                        "session_id": session_id,
                        "sources": sources,
                        "citations": citations,
                        "trace_id": trace_id_value,
                        "suggested_questions": suggested_questions,
                    }
                )
                + "\n\n"
            )
        except Exception as exc:
            logger.warning(
                "SSE streaming path failed, fallback to sync pipeline: %s", exc, exc_info=True
            )
            try:
                # If we already kicked off the parity graph in parallel, reuse
                # its result instead of running session.ask twice.
                result: dict[str, Any] | None = None
                if graph_task is not None:
                    try:
                        result = await graph_task
                    except Exception as parity_exc:
                        logger.warning("Streaming parity task failed in fallback: %s", parity_exc)
                        result = None
                if result is None and hasattr(session, "ask"):
                    # Graph fallback still routes executor submission through
                    # PipelineRunner; direct-await preserves no-new-deadline.
                    result = await pipeline_runner.submit_stream_graph(
                        loop=loop,
                        executor=get_request_executor(),
                        operation=_session_ask_with_shared_limits,
                    )
                if result is not None:
                    answer = result.get("answer") or "Не удалось получить ответ."
                    quality = result.get("quality_score") or 50
                    quality_source = str(result.get("quality_source") or "llm")
                    route = result.get("route") or "auto"
                    raw_sources = result.get("graded_docs") or result.get("context_docs") or []
                    sources = []
                    citations = []
                    for idx, item in enumerate(raw_sources, start=1):
                        metadata = item.get("metadata", {}) if isinstance(item, dict) else {}
                        content = item.get("page_content", "") if isinstance(item, dict) else ""
                        sources.append(
                            {
                                "source": metadata.get("source") or metadata.get("file_name") or "",
                                "page_content": content,
                            }
                        )
                        citations.append(
                            {
                                "index": idx,
                                "doc_id": str(
                                    metadata.get("doc_id")
                                    or metadata.get("id")
                                    or metadata.get("source")
                                    or metadata.get("file_name")
                                    or f"doc_{idx}"
                                ),
                                "title": str(
                                    metadata.get("title")
                                    or metadata.get("source")
                                    or metadata.get("file_name")
                                    or metadata.get("doc_id")
                                    or f"doc_{idx}"
                                ),
                                "excerpt": str(content or "")[:300],
                            }
                        )
                    if result.get("citations"):
                        citations = [
                            {
                                "index": int(item.get("index") or 0),
                                "doc_id": str(item.get("doc_id") or ""),
                                "title": str(item.get("title") or ""),
                                "excerpt": str(item.get("excerpt") or ""),
                            }
                            for item in result.get("citations", [])
                            if isinstance(item, dict)
                        ]
                    trace_id = result.get("trace_id") or ""
                    suggested_questions = result.get("suggested_questions") or []
                else:
                    answer = "Сессия не инициализирована."
                    session["history"].append({"role": "user", "content": question})
                    session["history"].append({"role": "assistant", "content": answer})
                    quality, route, sources, citations, trace_id, suggested_questions = (
                        0,
                        "human",
                        [],
                        [],
                        "",
                        [],
                    )
                    quality_source = "heuristic"

                await _persist_ask_messages(
                    session_id=session_id,
                    tenant_id=tenant,
                    question=question,
                    answer=answer,
                    path="stream_fallback",
                )

                try:
                    if quality:
                        prometheus_metrics.record_quality_score_source(quality_source)
                except Exception:
                    pass
                yield (
                    "data: "
                    + _json.dumps(
                        {
                            "type": "result",
                            "answer": answer,
                            "quality_score": quality,
                            "quality_source": quality_source,
                            "route": route,
                            "session_id": session_id,
                            "sources": sources,
                            "citations": citations,
                            "trace_id": trace_id,
                            "suggested_questions": suggested_questions,
                        }
                    )
                    + "\n\n"
                )
            except Exception as sync_exc:
                logger.error("SSE fallback error: %s", sync_exc, exc_info=True)
                yield (
                    "data: "
                    + _json.dumps(
                        {
                            "type": "result",
                            "answer": "Ошибка обработки запроса.",
                            "quality_score": 0,
                            "route": "human",
                            "session_id": session_id,
                            "sources": [],
                            "citations": [],
                            "trace_id": "",
                            "suggested_questions": [],
                        }
                    )
                    + "\n\n"
                )
        finally:
            # Clear stream-side ContextVars. Do not clear a shared budget object
            # mid-orphan: worker may still charge against it until done.
            try:
                clear_request_deadline()
            except Exception:
                pass
            try:
                # Only clear if we still own the stream context binding.
                if get_llm_request_budget() is stream_budget_obj:
                    clear_llm_request_budget()
            except Exception:
                pass
            # Runs on normal completion, errors, and client disconnect
            # (GeneratorExit) — the pipeline slot must never leak.
            if capacity_held_for_orphan:
                pass  # done-callback owns release
            elif graph_task is not None and not graph_task.done():
                # Disconnect / early exit while parity still running.
                capacity_held_for_orphan = True
                _hold_capacity_until_future_done(
                    loop=loop,
                    fut=graph_task,
                    semaphore=semaphore,
                )
            else:
                _release_pipeline_capacity(semaphore)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/stream")
@limiter.limit("60/minute")
async def chat_stream(
    request: Request,
    body: AskRequest,
    _user: dict = Depends(get_current_user),
) -> StreamingResponse:
    return await ask_stream(request, body, _user)
