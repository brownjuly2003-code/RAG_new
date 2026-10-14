from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from llm.providers.base import (
    LLMResponse,
    calculate_cost,
    estimate_tokens,
    flatten_messages,
    parse_structured_output,
)


def _with_timeout_kwargs(kwargs: dict[str, Any], timeout_sec: float) -> list[dict[str, Any]]:
    client_kwargs = {**(kwargs.get("client_kwargs") or {}), "timeout": timeout_sec}
    return [
        {**kwargs, "timeout": timeout_sec},
        {**kwargs, "request_timeout": timeout_sec},
        {**kwargs, "client_kwargs": client_kwargs},
        kwargs,
    ]


def _instantiate_with_timeout(cls: Any, *, timeout_sec: float, **kwargs: Any) -> Any:
    from utils.request_deadline import get_request_deadline

    deadline = get_request_deadline()
    if deadline is not None:
        deadline.check("ollama.client")
        timeout_sec = min(timeout_sec, deadline.remaining_sec())
    candidates = _with_timeout_kwargs(kwargs, timeout_sec)
    fields = getattr(cls, "model_fields", None)
    if fields is None:
        fields = getattr(cls, "__fields__", None)
    if isinstance(fields, dict):
        # Pydantic bindings can silently ignore unknown constructor arguments.
        # Select a declared field instead of treating construction as acceptance.
        for field, candidate in zip(
            ("timeout", "request_timeout", "client_kwargs"), candidates[:3], strict=True
        ):
            if field in fields:
                return cls(**candidate)
    last_type_error: TypeError | None = None
    for candidate in candidates:
        try:
            return cls(**candidate)
        except TypeError as exc:
            last_type_error = exc
    if last_type_error is not None:
        raise last_type_error
    return cls(**kwargs)


class OllamaProvider:
    def __init__(
        self,
        *,
        model_name: str,
        base_url: str,
        timeout_sec: float,
        input_price_per_1m_tokens: float,
        output_price_per_1m_tokens: float,
    ) -> None:
        self.provider_id = "ollama"
        self.model_name = model_name
        self._base_url = base_url
        self._timeout_sec = timeout_sec
        self._input_price_per_1m_tokens = input_price_per_1m_tokens
        self._output_price_per_1m_tokens = output_price_per_1m_tokens
        self.supports_tool_use = False
        self.supports_structured_output = False
        self.supports_streaming = False
        self.supports_batch = False

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        _ = tools
        prompt = flatten_messages(messages)
        started = time.perf_counter()

        # Plan §3.1d: optional role generation params (ignored if constructor rejects).
        gen_kwargs: dict[str, Any] = {}
        if kwargs.get("temperature") is not None:
            gen_kwargs["temperature"] = float(kwargs["temperature"])
        if kwargs.get("max_tokens") is not None:
            # LangChain Ollama uses num_predict for completion length.
            gen_kwargs["num_predict"] = int(kwargs["max_tokens"])

        def _make(cls: Any) -> Any:
            base = {
                "model": self.model_name,
                "base_url": self._base_url,
                **gen_kwargs,
            }
            try:
                return _instantiate_with_timeout(
                    cls,
                    timeout_sec=self._timeout_sec,
                    **base,
                )
            except TypeError:
                # Older bindings may not accept temperature/num_predict.
                return _instantiate_with_timeout(
                    cls,
                    timeout_sec=self._timeout_sec,
                    model=self.model_name,
                    base_url=self._base_url,
                )

        try:
            from langchain_ollama import (
                OllamaLLM as ollama_llm_cls,  # type: ignore[import-not-found]
            )

            llm = _make(ollama_llm_cls)
        except ImportError:
            from langchain_community.llms import Ollama as community_ollama_cls

            llm = _make(community_ollama_cls)

        from utils.request_deadline import check_request_deadline, get_request_deadline

        if get_request_deadline() is None:
            text = str(llm.invoke(prompt))
        else:
            # LangChain invoke aggregates a token stream. Socket read timeouts
            # reset on each chunk, so periodic tokens alone can outlive the wall.
            # Observe that same stream and close it when the request expires.
            chunks: list[str] = []
            stream = llm.stream(prompt)
            try:
                for chunk in stream:
                    check_request_deadline("ollama.generate.chunk")
                    chunks.append(str(chunk))
                check_request_deadline("ollama.generate")
                text = "".join(chunks)
            finally:
                close = getattr(stream, "close", None)
                if callable(close):
                    close()
        input_tokens = estimate_tokens(prompt)
        output_tokens = estimate_tokens(text)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return LLMResponse(
            text=text,
            provider=self.provider_id,
            model=self.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=calculate_cost(
                input_tokens,
                output_tokens,
                input_price_per_1m_tokens=self._input_price_per_1m_tokens,
                output_price_per_1m_tokens=self._output_price_per_1m_tokens,
            ),
            latency_ms=latency_ms,
            metadata={},
        )

    def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> LLMResponse:
        _ = kwargs
        prompt = flatten_messages(messages)
        started = time.perf_counter()

        try:
            from langchain_ollama import (
                ChatOllama as chat_ollama_cls,  # type: ignore[import-not-found]
            )

            chat = _instantiate_with_timeout(
                chat_ollama_cls,
                timeout_sec=self._timeout_sec,
                model=self.model_name,
                base_url=self._base_url,
            )
        except ImportError:
            from langchain_community.chat_models import ChatOllama as community_chat_cls

            chat = _instantiate_with_timeout(
                community_chat_cls,
                timeout_sec=self._timeout_sec,
                model=self.model_name,
                base_url=self._base_url,
            )

        response = chat.bind_tools(tools).invoke(prompt)
        content = getattr(response, "content", "")
        if isinstance(content, list):
            text = "\n".join(
                str(item.get("text") or "")
                for item in content
                if isinstance(item, dict)
            ).strip()
        else:
            text = str(content or "").strip()
        tool_calls = getattr(response, "tool_calls", None)
        if not isinstance(tool_calls, list):
            tool_calls = None
        response_metadata = getattr(response, "response_metadata", None)
        finish_reason = None
        if isinstance(response_metadata, dict):
            finish_reason = str(
                response_metadata.get("done_reason")
                or response_metadata.get("finish_reason")
                or ""
            ).strip() or None

        output_basis = text or json.dumps(tool_calls or [], ensure_ascii=False)
        return LLMResponse(
            text=text,
            provider=self.provider_id,
            model=self.model_name,
            input_tokens=estimate_tokens(prompt),
            output_tokens=estimate_tokens(output_basis),
            cost_usd=calculate_cost(
                estimate_tokens(prompt),
                estimate_tokens(output_basis),
                input_price_per_1m_tokens=self._input_price_per_1m_tokens,
                output_price_per_1m_tokens=self._output_price_per_1m_tokens,
            ),
            latency_ms=int((time.perf_counter() - started) * 1000),
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            metadata=response_metadata if isinstance(response_metadata, dict) else {},
        )

    def generate_with_schema(
        self,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        **kwargs: Any,
    ) -> LLMResponse:
        response = self.generate(
            [
                {
                    "role": "system",
                    "content": (
                        "Return only valid JSON that matches this JSON Schema exactly.\n"
                        f"{json.dumps(schema, ensure_ascii=False)}"
                    ),
                },
                *messages,
            ],
            **kwargs,
        )
        response.structured_output = parse_structured_output(response.text, schema)
        return response

    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        _ = kwargs
        prompt = flatten_messages(messages)

        try:
            from langchain_ollama import (
                OllamaLLM as ollama_llm_cls,  # type: ignore[import-not-found]
            )

            llm = _instantiate_with_timeout(
                ollama_llm_cls,
                timeout_sec=self._timeout_sec,
                model=self.model_name,
                base_url=self._base_url,
            )
        except ImportError:
            from langchain_community.llms import Ollama as community_ollama_cls

            llm = _instantiate_with_timeout(
                community_ollama_cls,
                timeout_sec=self._timeout_sec,
                model=self.model_name,
                base_url=self._base_url,
            )

        async for chunk in llm.astream(prompt):
            if isinstance(chunk, str):
                text = chunk
            else:
                content = getattr(chunk, "content", chunk)
                if isinstance(content, list):
                    text = "\n".join(
                        str(item.get("text") or "")
                        for item in content
                        if isinstance(item, dict)
                    )
                else:
                    text = str(content or "")
            if text:
                yield text
