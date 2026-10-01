"""Single owner for the trace start/log/finish lifecycle."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

from utils.pii import redact_pii


class TraceLifecycleBackend(Protocol):
    """Storage operations required by :class:`TraceService`."""

    def start_trace(
        self,
        trace_id: str | None = None,
        tenant_id: str = "default",
        *,
        correlation_id: str | None = None,
    ) -> str: ...

    def log_step(self, trace_id: str, node_name: str, state: Any) -> None: ...

    def finish_trace(self, trace_id: str, final_state: Any) -> None: ...


class TraceService:
    """Own trace lifecycle delegation and pre-persistence PII redaction."""

    def __init__(
        self,
        backend: TraceLifecycleBackend,
        *,
        redact_text: Callable[[str], str] = redact_pii,
    ) -> None:
        self._backend = backend
        self._redact_text = redact_text

    def start_trace(
        self,
        trace_id: str | None = None,
        tenant_id: str = "default",
        *,
        correlation_id: str | None = None,
    ) -> str:
        return self._backend.start_trace(
            trace_id,
            tenant_id,
            correlation_id=correlation_id,
        )

    def log_step(self, trace_id: str, node_name: str, state: Any) -> None:
        state_to_dict = getattr(self._backend, "_state_to_dict", None)
        if not callable(state_to_dict):
            self._backend.log_step(trace_id, node_name, state)
            return

        safe_state = state_to_dict(state)
        # Normalise through JSON first, then redact the text leaves only.
        # Redacting the serialized document let the card-number pattern eat
        # the digits of a float (0.8999999761581421 has sixteen of them) and
        # the step became unreadable JSON (review F-T-59-1).
        normalised = json.loads(json.dumps(safe_state, ensure_ascii=False))
        redacted_state = self._redact_values(normalised)
        self._backend.log_step(trace_id, node_name, redacted_state)

    def _redact_values(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._redact_text(value)
        if isinstance(value, dict):
            return {
                (self._redact_text(key) if isinstance(key, str) else key): self._redact_values(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._redact_values(item) for item in value]
        return value

    def finish_trace(self, trace_id: str, final_state: Any) -> None:
        self._backend.finish_trace(trace_id, final_state)


__all__ = ["TraceLifecycleBackend", "TraceService"]
