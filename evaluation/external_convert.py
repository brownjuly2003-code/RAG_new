"""Markdown rendering of an external base's documents, with the place of every source element.

An external base (``evaluation/external_bases.json``) arrives as HTML or as lists of HTML-like
elements. The product reads Markdown: headings ``#``…``####`` become sections and the heading path
of each chunk (``vectordb._base_manager.structural_split``). This module turns a document into a
list of blocks and renders the blocks as Markdown. The conversion is registered by
``CONVERTER_VERSION``: a change of any rule below is a new version and a new index.

The rules, none of them specific to a base:

- A heading keeps its text and its depth. The depth is the explicit ``aria-level`` or ``level``
  attribute when it is an integer from 1 to 6, otherwise the number in the tag name.
- A paragraph is the text between two block boundaries; ``<br>`` is a line break inside it. ASCII
  whitespace collapses as HTML collapses it; other characters are kept as they are.
- A line break inside a paragraph, a list item or code is any break ``str.splitlines`` knows — the
  breaks the product's splitter reads — and is written as ``\n``: a rendered document holds no
  carriage return, so the loader's hash of its text is the SHA-256 of its file.
- A list item is ``- text`` or ``N. text`` at the depth of its list; an item opened and not yet
  written takes a block boundary as a line break.
- A table is one ``| a | b |`` line per row with a separator line after the first row; the block
  structure inside a cell is flattened to spaces.
- ``<pre>`` is a fenced block.
- Links, emphasis and other inline markup leave their text and nothing else. Images, frames,
  scripts, styles and drawings leave nothing: the pinned files carry no text for them.
- A line that the heading splitter would read as a heading or as a code fence, and that is
  neither, gets a leading backslash.

``render`` also returns, for every block that carries a key, the character range of its content
in the rendered text. Gold of an external base is addressed by these ranges
(``evaluation/external_gold.py``), never by a search for its text.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser

CONVERTER_VERSION = "external-markdown-v1"
NAME_LENGTH = 60

_BREAK = "\x00"
_ASCII_SPACE = re.compile(r"[ \t\n\r\f]+")
_HEADING_OR_FENCE = re.compile(r"(#{1,6}(\s|$)|```|~~~)")
_HEADING_TAG = re.compile(r"h[1-6]")
_SILENT = frozenset(
    "script style svg iframe video audio object noscript template head canvas math".split()
)
_BOUNDARY = frozenset(
    "address article aside blockquote body caption center dd details dialog dir div dl dt "
    "fieldset figcaption figure footer form header hgroup hr html legend main menu nav p "
    "section summary".split()
)
_IN_CELL = _BOUNDARY | frozenset("ul ol li table tr td th pre h1 h2 h3 h4 h5 h6".split())


@dataclass(frozen=True)
class Block:
    """One block of a document: a heading, a paragraph, a list item, a table row or code.

    ``level`` is the depth of a heading (1–6), the depth of a list item (1 and deeper) or the
    number of a row's table; ``ordinal`` is the number of an ordered item; ``cells`` are the cells
    of a row. ``key`` is the caller's name for the block: ``render`` reports the place of its
    content under that name.
    """

    kind: str
    text: str = ""
    level: int = 0
    ordinal: int | None = None
    cells: tuple[str, ...] = ()
    key: Hashable | None = None


def _one_line(text: str) -> str:
    return _ASCII_SPACE.sub(" ", text).strip()


def _lines(text: str) -> list[str]:
    return [line for line in (part.strip() for part in text.splitlines()) if line]


def _guard(line: str) -> str:
    return "\\" + line if _HEADING_OR_FENCE.match(line) else line


def render(blocks: Iterable[Block]) -> tuple[str, dict[Hashable, tuple[int, int]]]:
    """Markdown of the blocks and the character range of each keyed block's content.

    A block without text is not written and has no range. Consecutive list items stand on
    consecutive lines, and so do the rows of one table; any other two blocks are separated by an
    empty line.
    """
    parts: list[str] = []
    spans: dict[Hashable, tuple[int, int]] = {}
    size = 0
    previous: tuple[str, int] | None = None

    def write(text: str) -> None:
        nonlocal size
        parts.append(text)
        size += len(text)

    for block in blocks:
        kind = block.kind
        run = (kind, block.level if kind == "row" else 0)
        if kind == "heading":
            body = _one_line(block.text)
            prefix = "#" * block.level + " "
        elif kind == "row":
            cells = [_one_line(cell).replace("|", "\\|") for cell in block.cells]
            body = " | ".join(cells) if any(cells) else ""
            prefix = "| "
        elif kind == "code":
            code = [line.rstrip() for line in block.text.splitlines()]
            while code and not code[0]:
                del code[0]
            while code and not code[-1]:
                del code[-1]
            body = "\n".join(
                "\\" + line if line.lstrip().startswith(("```", "~~~")) else line for line in code
            )
            prefix = "```\n"
        elif kind == "item":
            marker = "- " if block.ordinal is None else f"{block.ordinal}. "
            indent = "  " * max(block.level - 1, 0)
            lines = _lines(block.text)
            pad = "\n" + indent + " " * len(marker)
            body = lines[0] + "".join(pad + _guard(line) for line in lines[1:]) if lines else ""
            prefix = indent + marker
        elif kind == "para":
            lines = _lines(block.text)
            body = "\n".join([lines[0], *map(_guard, lines[1:])]) if lines else ""
            prefix = "\\" if lines and _HEADING_OR_FENCE.match(lines[0]) else ""
        else:
            raise ValueError(f"unknown block kind: {kind}")
        if not body:
            continue
        if previous is not None:
            write("\n" if run == previous and kind in ("item", "row") else "\n\n")
        write(prefix)
        if block.key is not None:
            if block.key in spans:
                raise ValueError(f"block key repeated: {block.key!r}")
            spans[block.key] = (size, size + len(body))
        write(body)
        if kind == "row":
            write(" |")
            if run != previous:
                write("\n|" + " --- |" * len(block.cells))
        elif kind == "code":
            write("\n```")
        previous = run
    if parts:
        write("\n")
    return "".join(parts), spans


class _Blocks(HTMLParser):
    """HTML to blocks by the rules of the module docstring."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self._inline: list[str] = []
        self._silent: tuple[str, int] | None = None
        self._heading = 0
        self._lists: list[int | None] = []  # next ordinal of each open list, None for bullets
        self._items: list[list[int]] = []  # [list depth, ordinal or 0, written] of each open item
        self._tables = 0
        self._table_number = 0
        self._rows: list[tuple[str, ...]] = []
        self._cells: list[str] | None = None
        self._in_cell = False
        self._pre = 0
        self._code: list[str] = []

    def _take(self, *, one_line: bool = False) -> str:
        raw = "".join(self._inline)
        self._inline = []
        if one_line:
            return _one_line(raw.replace(_BREAK, " "))
        return "\n".join(_lines(_ASCII_SPACE.sub(" ", raw).replace(_BREAK, "\n")))

    def _flush(self) -> None:
        text = self._take()
        if not text:
            return
        if self._items and not self._items[-1][2]:
            depth, ordinal, _ = self._items[-1]
            self._items[-1][2] = 1
            self.blocks.append(Block("item", text, level=max(depth, 1), ordinal=ordinal or None))
        else:
            self.blocks.append(Block("para", text))

    def _boundary(self) -> None:
        if self._heading:
            self._inline.append(" ")
        elif self._items and not self._items[-1][2]:
            self._inline.append(_BREAK)
        else:
            self._flush()

    def _end_heading(self) -> None:
        text = self._take(one_line=True)
        if text:
            self.blocks.append(Block("heading", text, level=self._heading))
        self._heading = 0

    def _end_cell(self) -> None:
        if self._in_cell:
            assert self._cells is not None
            self._cells.append(self._take(one_line=True))
            self._in_cell = False

    def _end_row(self) -> None:
        self._end_cell()
        if self._cells:
            self._rows.append(tuple(self._cells))
        self._cells = None

    def _close_items(self, depth: int) -> None:
        while self._items and self._items[-1][0] >= depth:
            self._flush()
            self._items.pop()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._silent is not None:
            if tag == self._silent[0]:
                self._silent = (tag, self._silent[1] + 1)
            return
        if tag in _SILENT:
            self._silent = (tag, 1)
            return
        if self._pre:
            if tag == "br":
                self._code.append("\n")
            elif tag == "pre":
                self._pre += 1
            return
        if self._in_cell and not (self._tables == 1 and tag in ("tr", "td", "th")):
            # Inside a cell every structure is text: a nested table too.
            if tag == "table":
                self._tables += 1
            if tag == "br" or tag in _IN_CELL:
                self._inline.append(" ")
            return
        if tag == "br":
            self._inline.append(" " if self._heading else _BREAK)
        elif _HEADING_TAG.fullmatch(tag):
            if self._heading:
                self._end_heading()
            self._flush()
            declared = dict(attrs).get("aria-level") or dict(attrs).get("level") or ""
            self._heading = int(declared) if declared in tuple("123456") else int(tag[1])
        elif tag in ("ul", "ol"):
            self._flush()
            start = dict(attrs).get("start") or "1"
            self._lists.append((int(start) if start.isdigit() else 1) if tag == "ol" else None)
        elif tag == "li":
            depth = len(self._lists)
            self._close_items(depth)
            self._flush()
            ordinal = self._lists[-1] if self._lists else None
            if ordinal is not None:
                self._lists[-1] = ordinal + 1
            self._items.append([depth, ordinal or 0, 0])
        elif tag == "table":
            self._flush()
            self._tables = 1
            self._table_number += 1
            self._rows = []
            self._cells = None
        elif tag == "tr" and self._tables:
            self._end_row()
            self._cells = []
        elif tag in ("td", "th") and self._tables:
            self._end_cell()
            if self._cells is None:
                self._cells = []
            self._inline = []
            self._in_cell = True
        elif tag == "pre":
            self._flush()
            self._pre = 1
            self._code = []
        elif tag in _BOUNDARY:
            self._boundary()

    def handle_endtag(self, tag: str) -> None:
        if self._silent is not None:
            if tag == self._silent[0]:
                depth = self._silent[1] - 1
                self._silent = (tag, depth) if depth else None
            return
        if self._pre:
            if tag == "pre":
                self._pre -= 1
                if not self._pre:
                    self.blocks.append(Block("code", "".join(self._code)))
            return
        if self._in_cell and not (self._tables == 1 and tag in ("tr", "td", "th", "table")):
            if tag == "table":
                self._tables -= 1
            if tag in _IN_CELL:
                self._inline.append(" ")
            return
        if self._heading and _HEADING_TAG.fullmatch(tag):
            self._end_heading()
        elif tag in ("ul", "ol"):
            self._close_items(len(self._lists))
            self._flush()
            if self._lists:
                self._lists.pop()
        elif tag == "li":
            self._flush()
            if self._items and self._items[-1][0] == len(self._lists):
                self._items.pop()
        elif tag in ("td", "th") and self._tables:
            self._end_cell()
        elif tag == "tr" and self._tables:
            self._end_row()
        elif tag == "table" and self._tables:
            self._end_table()
        elif tag in _BOUNDARY:
            self._boundary()

    def _end_table(self) -> None:
        self._end_row()
        self._tables = 0
        self._flush()
        number = self._table_number
        self.blocks.extend(Block("row", cells=row, level=number) for row in self._rows)
        self._rows = []

    def handle_data(self, data: str) -> None:
        if self._silent is not None:
            return
        if self._pre:
            self._code.append(data)
        else:
            self._inline.append(data.replace(_BREAK, ""))

    def close(self) -> None:
        super().close()
        if self._pre:
            self.blocks.append(Block("code", "".join(self._code)))
            self._pre = 0
        if self._heading:
            self._end_heading()
        if self._tables:
            self._end_table()
        self._flush()


def html_blocks(html: str) -> list[Block]:
    """The blocks of an HTML fragment, in document order."""
    parser = _Blocks()
    parser.feed(html)
    parser.close()
    return parser.blocks


def html_headings(html: str) -> list[str]:
    """Heading texts of an HTML fragment read without the converter: the check of its headings."""
    found = []
    for inner in re.findall(r"(?is)<h[1-6]\b[^>]*>(.*?)</h[1-6]\s*>", html):
        text = _one_line(unescape(re.sub(r"(?s)<[^>]*>", " ", inner)))
        if text:
            found.append(text)
    return found


def markdown_headings(markdown: str) -> list[tuple[int, str]]:
    """Depth and text of the heading lines of a rendered document, outside its code fences.

    The lines the product's heading splitter reads as headings, and the deeper ones it leaves
    in the text: it splits on depths 1 to 4.
    """
    found = []
    fence = ""
    for line in markdown.split("\n"):
        line = line.strip()
        if fence:
            if line.startswith(fence):
                fence = ""
            continue
        if line.startswith("```") and line.count("```") == 1:
            fence = "```"
        elif line.startswith("~~~"):
            fence = "~~~"
        else:
            match = re.fullmatch(r"(#{1,6})(?: (.*))?", line)
            if match:
                found.append((len(match[1]), (match[2] or "").strip()))
    return found


def slug(title: str) -> str:
    """A file-name stem of a title: ASCII letters and digits, lower case, hyphens between."""
    plain = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")
    return stem[:NAME_LENGTH].strip("-") or "doc"


def file_names(titles: Sequence[str], document_ids: Sequence[str]) -> list[str]:
    """One ``.md`` name per document, the same whatever the order of the documents.

    A name is the slug of the title. Documents whose slugs coincide all get eight hex digits of
    the SHA-256 of their document id after the slug, so no name depends on the others' order.
    """
    stems = [slug(title) for title in titles]
    count = Counter(stems)
    names = [
        f"{stem}-{hashlib.sha256(document_id.encode('utf-8')).hexdigest()[:8]}.md"
        if count[stem] > 1
        else f"{stem}.md"
        for stem, document_id in zip(stems, document_ids, strict=True)
    ]
    if len(set(names)) != len(names):
        raise ValueError("document names collide after the digest suffix")
    return names
