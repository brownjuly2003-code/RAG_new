"""Fit prompts into a local model's input window without losing instructions.

A model with a declared ``context_window`` (Ollama) receives num_ctx and refuses
prompts it cannot hold; the callers here shrink the context first. Sizes come
from ``estimate_window_tokens``, calibrated on the Qwen2.5 tokenizer. Models
without a declared window are left untouched.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from llm.providers.base import estimate_window_tokens, flatten_messages, window_input_limit
from llm.role_params import generation_kwargs_for_role
from vectordb import contextual_header

EXCERPT_GAP = "\n\n[…]\n\n"


def prompt_input_tokens(prompt: str, schema: dict[str, Any] | None = None) -> int:
    """Estimated tokens of the prompt as the provider will send it."""
    messages = [{"role": "user", "content": prompt}]
    if schema is not None:
        # Same system turn as OllamaProvider.generate_with_schema.
        messages.insert(
            0,
            {
                "role": "system",
                "content": (
                    "Return only valid JSON that matches this JSON Schema exactly.\n"
                    + json.dumps(schema, ensure_ascii=False)
                ),
            },
        )
    return estimate_window_tokens(flatten_messages(messages))


def prompt_input_limit(llm: Any, role: str) -> int | None:
    """Prompt tokens the model's window leaves after the role's output budget."""
    window = getattr(llm, "context_window", None)
    if not isinstance(window, int) or isinstance(window, bool) or window <= 0:
        return None
    return window_input_limit(window, int(generation_kwargs_for_role(role)["max_tokens"]))


def _query_terms(question: str) -> set[str]:
    return {word[:4] for word in re.findall(r"\w+", question.lower()) if len(word) > 2}


def _cut_to_tokens(text: str, max_tokens: int) -> str:
    """Longest prefix of ``text`` whose estimate fits ``max_tokens``."""
    if estimate_window_tokens(text) <= max_tokens:
        return text
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if estimate_window_tokens(text[:middle]) <= max_tokens:
            low = middle
        else:
            high = middle - 1
    return text[:low]


def _excerpt(
    text: str, question: str, max_tokens: int, metadata: dict[str, Any] | None = None
) -> str:
    """Paragraphs of ``text`` that share the most terms with ``question``, in order."""
    if max_tokens <= 0:
        return ""
    if estimate_window_tokens(text) <= max_tokens:
        return text
    terms = _query_terms(question)
    blocks = re.split(r"\n\s*\n", text)
    ranked = sorted(range(len(blocks)), key=lambda i: (-len(terms & _query_terms(blocks[i])), i))
    chosen: dict[int, str] = {}
    for index in ranked:
        parts = {**chosen, index: blocks[index]}
        candidate = EXCERPT_GAP.join(parts[i] for i in sorted(parts))
        if estimate_window_tokens(candidate) <= max_tokens:
            chosen = parts
        elif not chosen:
            # Shorten the best block before admitting less relevant paragraphs.
            # Keep an FAQ question with its following answer; skip long headers.
            lines = blocks[index].splitlines(keepends=True)
            candidates = [
                i
                for i, line in enumerate(lines)
                if line.strip() and not contextual_header.is_header_line(line, metadata)
            ]
            line_index = (
                max(
                    candidates,
                    key=lambda i: (
                        len(terms & _query_terms(lines[i])),
                        lines[i].rstrip().endswith("?"),
                        -i,
                    ),
                )
                if candidates
                else 0
            )
            chosen[index] = _cut_to_tokens("".join(lines[line_index:]), max_tokens)
    return EXCERPT_GAP.join(chosen[i] for i in sorted(chosen))


def fit_all_context_docs(
    llm: Any,
    question: str,
    docs: list[dict[str, Any]],
    build_prompt: Callable[[list[dict[str, Any]]], str],
    *,
    role: str,
    schema: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """A view of every document, in order, that fits the window (for grading).

    Each document gets an equal share of the room left by the instructions and
    labels, cut to its paragraphs closest to the question, so the grader still
    judges all of them under their original indices.
    """
    limit = prompt_input_limit(llm, role)
    if limit is None or prompt_input_tokens(build_prompt(docs), schema) <= limit:
        return docs
    empty = [{**doc, "page_content": ""} for doc in docs]
    available = limit - prompt_input_tokens(build_prompt(empty), schema)
    if available < len(docs):
        raise ValueError("Document labels and instructions exceed the model input window")

    def pack(budget: int) -> list[dict[str, Any]]:
        share, extra = divmod(budget, len(docs))
        return [
            {
                **doc,
                "page_content": _excerpt(
                    str(doc.get("page_content") or ""),
                    question,
                    share + (index < extra),
                    doc.get("metadata"),
                ),
            }
            for index, doc in enumerate(docs)
        ]

    views = pack(available)
    if prompt_input_tokens(build_prompt(views), schema) <= limit:
        return views
    # A builder that is not additive in its documents: search for the largest
    # share that is measured to fit.
    fitted, low, high = empty, 0, available - 1
    while low <= high:
        middle = (low + high) // 2
        candidate = pack(middle)
        if prompt_input_tokens(build_prompt(candidate), schema) <= limit:
            fitted, low = candidate, middle + 1
        else:
            high = middle - 1
    return fitted


def fit_context_docs(
    llm: Any,
    question: str,
    docs: list[dict[str, Any]],
    build_prompt: Callable[[list[dict[str, Any]]], str],
    *,
    role: str,
    schema: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Leading documents that fit the window, in rank order.

    Whole documents are kept while they fit; the first one that does not is cut
    to its paragraphs closest to the question, and the rest are dropped, so the
    citation indices of the kept prefix do not move.
    """
    limit = prompt_input_limit(llm, role)
    if limit is None or prompt_input_tokens(build_prompt(docs), schema) <= limit:
        return docs
    if prompt_input_tokens(build_prompt([]), schema) > limit:
        raise ValueError("Question and instructions exceed the model input window")
    packed: list[dict[str, Any]] = []
    for doc in docs:
        if prompt_input_tokens(build_prompt([*packed, doc]), schema) <= limit:
            packed.append(doc)
            continue
        empty_doc = {**doc, "page_content": ""}
        remaining = limit - prompt_input_tokens(build_prompt([*packed, empty_doc]), schema)
        text = _excerpt(
            str(doc.get("page_content") or ""), question, remaining, doc.get("metadata")
        )
        if text.strip():
            view = {**doc, "page_content": text}
            if prompt_input_tokens(build_prompt([*packed, view]), schema) <= limit:
                packed.append(view)
        break
    return packed
