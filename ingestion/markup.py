"""DOCX, HTML and PDF as markdown, so section chunking works on every format (PLAN.md stage 1).

Chunking cuts a document by its markdown headings (``structural_split``). Until stage 1 only a
markdown file had any: the DOCX reader kept paragraphs alone and dropped headings and tables,
the HTML reader joined every text node into one line, and a PDF was the text of its pages. The
converters here keep what the formats say about structure, by the formats' own rules and with
no word of any language:

- DOCX: the body in order; a paragraph is a heading by its outline level (the paragraph's or
  its style's, through ``basedOn``) or by a built-in heading style; numbered and bulleted
  paragraphs become list items; tables become markdown tables.
- HTML: ``h1``–``h6`` become headings, block elements paragraphs, list items list items,
  tables markdown tables; ``script``, ``style`` and the like are dropped.
- PDF: the outline (bookmarks) gives the headings — each one stands at the start of its line
  on its page, and a page that begins inside a section gets its section's heading path first.
  A PDF without an outline stays page text: font sizes differ from one document to the next,
  and a guess from them would be a rule for one corpus (docs/specs/stage1-fixes.md row 3).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from html.parser import HTMLParser
from typing import Any

# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def markdown_table(rows: Sequence[Sequence[str]]) -> str:
    """Rows of cells as a markdown table; the first row is the header."""
    cleaned = [[_cell(cell) for cell in row] for row in rows if any(str(c).strip() for c in row)]
    if not cleaned:
        return ""
    width = max(len(row) for row in cleaned)
    padded = [row + [""] * (width - len(row)) for row in cleaned]
    lines = ["| " + " | ".join(padded[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(row) + " |" for row in padded[1:]]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_HEADING_STYLE = re.compile(r"^heading\s*([1-9])$", re.IGNORECASE)


def _outline_level(element: Any) -> int | None:
    """The ``w:outlineLvl`` of a paragraph's or a style's properties, 0-based."""
    p_pr = element.find(f"{_W}pPr")
    if p_pr is None:
        return None
    level = p_pr.find(f"{_W}outlineLvl")
    if level is None:
        return None
    try:
        value = int(level.get(f"{_W}val"))
    except (TypeError, ValueError):
        return None
    return value if 0 <= value <= 8 else None


def _style_level(style: Any) -> int | None:
    """A heading level (1-based) from a paragraph style and the styles it is based on."""
    seen = 0
    while style is not None and seen < 10:
        level = _outline_level(style.element)
        if level is not None:
            return level + 1
        style_id = str(getattr(style, "style_id", "") or "")
        name = str(getattr(style, "name", "") or "")
        if name.strip().lower() == "title" or style_id.lower() == "title":
            return 1
        match = _HEADING_STYLE.match(name.strip()) or _HEADING_STYLE.match(style_id)
        if match:
            return int(match.group(1))
        style = getattr(style, "base_style", None)
        seen += 1
    return None


def _docx_paragraph(paragraph: Any) -> str:
    text = " ".join(paragraph.text.split())
    if not text:
        return ""
    level = _outline_level(paragraph._p)
    level = level + 1 if level is not None else _style_level(paragraph.style)
    if level is not None:
        return "#" * min(level, 6) + " " + text
    if _numbered(paragraph._p) or _style_numbered(paragraph.style):
        return "- " + text
    return text


def _numbered(element: Any) -> bool:
    p_pr = element.find(f"{_W}pPr")
    return p_pr is not None and p_pr.find(f"{_W}numPr") is not None


def _style_numbered(style: Any) -> bool:
    seen = 0
    while style is not None and seen < 10:
        if _numbered(style.element):
            return True
        style = getattr(style, "base_style", None)
        seen += 1
    return False


def _docx_table(table: Any) -> str:
    rows: list[list[str]] = []
    for row in table.rows:
        cells: list[str] = []
        previous = None
        for cell in row.cells:
            # A merged cell is returned once for every grid column it spans.
            if previous is not None and cell._tc is previous:
                continue
            previous = cell._tc
            cells.append(" ".join(cell.text.split()))
        rows.append(cells)
    return markdown_table(rows)


def docx_to_markdown(document: Any) -> str:
    """A python-docx ``Document`` as markdown: headings, list items, paragraphs, tables."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    blocks: list[str] = []
    for child in document.element.body.iterchildren():
        if child.tag == f"{_W}p":
            block = _docx_paragraph(Paragraph(child, document))
        elif child.tag == f"{_W}tbl":
            block = _docx_table(Table(child, document))
        else:
            continue
        if block:
            blocks.append(block)
    return _join_blocks(blocks)


def _join_blocks(blocks: Iterable[str]) -> str:
    """Blocks with an empty line between them; consecutive list items stay together."""
    out: list[str] = []
    for block in blocks:
        if out and _is_item(block) and _is_item(out[-1].split("\n")[-1]):
            out[-1] += "\n" + block
        else:
            out.append(block)
    return "\n\n".join(out)


def _is_item(line: str) -> bool:
    return line.lstrip().startswith(("- ", "1. "))


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_SKIP = {"script", "style", "noscript", "template", "head", "svg", "iframe", "object"}
_BLOCK = {
    "p",
    "div",
    "section",
    "article",
    "main",
    "header",
    "footer",
    "aside",
    "nav",
    "blockquote",
    "figure",
    "figcaption",
    "address",
    "dl",
    "dt",
    "dd",
    "form",
    "fieldset",
    "details",
    "summary",
    "hr",
    "body",
    "html",
}
_HEADINGS = {f"h{level}": level for level in range(1, 7)}
_VOID = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source"}


class _HtmlToMarkdown(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._text: list[str] = []
        self._skip = 0
        self._prefix = ""
        self._lists: list[str] = []
        self._pre = 0
        self._rows: list[list[str]] | None = None
        self._cell: list[str] | None = None
        self._nested = 0

    # The text of the current block, before it is closed.
    def _flush(self) -> None:
        raw = "".join(self._text)
        self._text = []
        if self._pre:
            return
        text = " ".join(raw.split())
        if text:
            self.blocks.append(self._prefix + text)
        self._prefix = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        if self._rows is not None:
            if tag == "table":
                self._nested += 1
            elif self._nested or tag == "br":
                if self._cell is not None:
                    self._cell.append(" ")
            elif tag == "tr":
                self._rows.append([])
            elif tag in {"td", "th"}:
                self._cell = []
            return
        if tag == "table":
            self._flush()
            self._rows = []
        elif tag in _HEADINGS:
            self._flush()
            self._prefix = "#" * _HEADINGS[tag] + " "
        elif tag in {"ul", "ol"}:
            self._flush()
            self._lists.append(tag)
        elif tag == "li":
            self._flush()
            depth = max(len(self._lists) - 1, 0)
            marker = "1." if self._lists and self._lists[-1] == "ol" else "-"
            self._prefix = "  " * depth + marker + " "
        elif tag == "pre":
            self._flush()
            self._pre += 1
        elif tag == "br":
            if self._pre:
                self._text.append("\n")
            else:
                self._flush()
        elif tag in _BLOCK:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self._skip = max(self._skip - 1, 0)
            return
        if self._skip:
            return
        if self._rows is not None:
            if tag == "table" and self._nested:
                # A table inside a cell is read as the cell's text.
                self._nested -= 1
            elif tag == "table":
                table = markdown_table(self._rows)
                self._rows = self._cell = None
                if table:
                    self.blocks.append(table)
            elif tag in {"td", "th"} and self._cell is not None and not self._nested:
                if not self._rows:
                    self._rows.append([])
                self._rows[-1].append("".join(self._cell))
                self._cell = None
            return
        if tag == "pre" and self._pre:
            self._pre -= 1
            code = "".join(self._text).strip("\n")
            self._text = []
            if code.strip():
                self.blocks.append("```\n" + code + "\n```")
        elif tag in {"ul", "ol"}:
            self._flush()
            if self._lists:
                self._lists.pop()
        elif tag in _HEADINGS or tag == "li":
            self._flush()
            self._prefix = ""
        elif tag in _BLOCK:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._rows is not None:
            if self._cell is not None:
                self._cell.append(data)
            return
        self._text.append(data)

    def close(self) -> None:
        super().close()
        self._flush()


def html_to_markdown(html: str) -> str:
    """An HTML page as markdown: headings, paragraphs, list items, tables and code blocks."""
    parser = _HtmlToMarkdown()
    parser.feed(html)
    parser.close()
    return _join_blocks(parser.blocks)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


def _outline_entries(reader: Any) -> list[tuple[int, int, str]]:
    """(page index, depth from 1, title) of every outline item, in outline order."""
    entries: list[tuple[int, int, str]] = []

    def walk(items: Any, depth: int) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item, depth + 1)
                continue
            title = " ".join(str(getattr(item, "title", "") or "").split())
            if not title:
                continue
            try:
                page = reader.get_destination_page_number(item)
            except Exception:
                continue
            if page is not None and page >= 0:
                entries.append((int(page), depth, title))

    try:
        walk(reader.outline, 1)
    except Exception:
        return []
    return entries


def _place_heading(text: str, heading: str, title: str) -> str | None:
    """The page text with the title's line made a heading; None when no line is the title."""
    words = r"\s+".join(map(re.escape, title.split()))
    match = re.compile(r"^[ \t]*" + words + r"[ \t]*$", re.M).search(text)
    if match is None:
        return None
    return text[: match.start()] + heading + text[match.end() :]


def pdf_pages_as_markdown(reader: Any, pages: Sequence[str]) -> list[str]:
    """The text of each page with the outline's headings in it.

    A heading stands where its title stands on its page, or first on that page; a page that
    begins inside a section starts with the heading path of that section, so its chunks carry
    it. Without an outline the pages come back as they are.
    """
    entries = _outline_entries(reader)
    if not entries:
        return list(pages)
    by_page: dict[int, list[tuple[int, str]]] = {}
    for page, depth, title in entries:
        by_page.setdefault(page, []).append((depth, title))
    out: list[str] = []
    path: list[tuple[int, str]] = []
    for index, text in enumerate(pages):
        opening = list(path)
        page_text = text
        unplaced: list[str] = []
        for depth, title in by_page.get(index, []):
            level = min(depth, 6)
            heading = "#" * level + " " + title
            placed = _place_heading(page_text, heading, title)
            if placed is None:
                unplaced.append(heading)
            else:
                page_text = placed
            path = [item for item in path if item[0] < level] + [(level, title)]
        if unplaced:
            page_text = "\n".join(unplaced) + "\n" + page_text
        # Each page is chunked on its own: it carries the levels of its path above its first
        # heading — all of them when it begins with text.
        first = page_text.lstrip().split("\n", 1)[0]
        first_level = len(first) - len(first.lstrip("#")) if first.startswith("#") else 7
        carried = [(level, title) for level, title in opening if level < first_level]
        if carried:
            prefix = "\n".join("#" * level + " " + title for level, title in carried)
            page_text = prefix + "\n" + page_text
        out.append(page_text)
    return out
