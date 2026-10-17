"""The contextual header of a chunk: one line before its text, naming its document and section.

Written as ``[document › section › subsection]`` — no word of any natural language, so a
corpus in any language gets the same kind of header (PLAN.md stage 1). Until stage 1 the
header was the Russian phrase «[Контекст: Из документа …, раздел: …]» on every corpus; that
form is still read (``LEGACY_PREFIX``), so the collections built before stage 1 stay readable
for rollback and for the records measured on them.

The document is named by its file. When the words of the file name stand in the first heading
in a row, or the other way round — a file named by the slug of its title — the longer of the
two stands once. A header
longer than ``LIMIT`` drops the outer section levels first, so the document and the heading
nearest to the text survive; until stage 1 the header was cut at its end, which lost the
nearest heading on 8–34 % of the chunks of the external bases.

The header is embedded with its chunk and read by the model in the prompt; the chunk's
metadata keeps it under ``contextual_header``, which is how a reader finds the line again.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import PurePath
from typing import Any

LIMIT = 200
SEPARATOR = " › "
ELISION = "…"
LEVELS = ("h1", "h2", "h3", "h4")
#: The header of the collections built before stage 1.
LEGACY_PREFIX = "[Контекст:"

_WORD = re.compile(r"[^\W_]+")
#: What the nearest heading keeps when the document's name and it alone exceed the limit.
_NEAREST_SHARE = 0.6


def _words(text: str) -> list[str]:
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _WORD.findall(plain.casefold())


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(limit - len(ELISION), 0)].rstrip() + ELISION


def heading_path(metadata: Mapping[str, Any] | None) -> list[str]:
    """The markdown headings h1–h4 that ``structural_split`` put in a chunk's metadata."""
    meta = metadata or {}
    return [" ".join(str(meta[level]).split()) for level in LEVELS if meta.get(level)]


def header_parts(source: str, headings: Sequence[str]) -> list[str]:
    """The document and its heading path, a title standing once."""
    name = " ".join(str(source or "").split())
    path = [heading for heading in (" ".join(str(h).split()) for h in headings) if heading]
    if not name:
        return path
    if path:
        file_words = _words(PurePath(name).stem)
        title_words = _words(path[0])
        shorter, longer = sorted((file_words, title_words), key=len)
        width = len(shorter)
        if width and any(
            longer[start : start + width] == shorter for start in range(len(longer) - width + 1)
        ):
            if len(title_words) >= len(file_words):
                return path
            return [name, *path[1:]]
    return [name, *path]


def compose(parts: Sequence[str], limit: int = LIMIT) -> str:
    """One header of at most ``limit`` characters; outer section levels go first."""
    items = [part for part in parts if part]
    if not items:
        return ""
    header = SEPARATOR.join(items)
    if len(header) <= limit:
        return header
    if len(items) == 1:
        return _clip(items[0], limit)
    document, inner = items[0], items[1:]
    while len(inner) > 1 and len(SEPARATOR.join([document, ELISION, *inner])) > limit:
        inner = inner[1:]
    kept = [document, ELISION, *inner] if len(inner) < len(items) - 1 else [document, *inner]
    header = SEPARATOR.join(kept)
    if len(header) <= limit:
        return header
    # The document and the nearest heading alone are too long: both are shortened, the
    # heading keeping the larger share.
    middle = SEPARATOR.join(kept[1:-1])
    fixed = len(SEPARATOR) * (len(kept) - 1) + len(middle)
    room = max(limit - fixed, 2 * len(ELISION))
    nearest = _clip(kept[-1], max(int(room * _NEAREST_SHARE), room - len(document)))
    document = _clip(document, room - len(nearest))
    return SEPARATOR.join([document, *kept[1:-1], nearest])


def for_chunk(metadata: Mapping[str, Any] | None, limit: int = LIMIT) -> str:
    """The header of a chunk from its metadata: its source and its heading path."""
    meta = metadata or {}
    return compose(header_parts(str(meta.get("source") or "unknown"), heading_path(meta)), limit)


def render(header: str) -> str:
    """The header as the first line of a chunk's text."""
    return f"[{header}]"


def split(text: str, metadata: Mapping[str, Any] | None = None) -> tuple[str, str]:
    """The header line of a chunk's text and the rest; ``("", text)`` when it has none.

    The line is found through the chunk's ``contextual_header`` metadata, or by the prefix of
    the header written before stage 1. A legacy header with no line break after it is left in
    place, as the readers did before.
    """
    header = (metadata or {}).get("contextual_header")
    if header:
        line = render(str(header))
        if text == line:
            return line, ""
        if text.startswith(line + "\n"):
            return line, text[len(line) + 1 :]
    if text.startswith(LEGACY_PREFIX):
        end = text.find("\n")
        if end != -1:
            return text[:end], text[end + 1 :]
    return "", text


def strip(text: str, metadata: Mapping[str, Any] | None = None) -> str:
    """A chunk's text without its header line."""
    return split(text, metadata)[1]


def is_header_line(line: str, metadata: Mapping[str, Any] | None = None) -> bool:
    """Whether one line of text is a chunk's header."""
    stripped = line.strip()
    header = (metadata or {}).get("contextual_header")
    if header and stripped == render(str(header)):
        return True
    return stripped.startswith(LEGACY_PREFIX)
