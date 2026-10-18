"""DOCX, HTML and PDF read as markdown, so section chunking cuts them by section.

docs/specs/stage1-fixes.md rows 1-3: the DOCX reader kept paragraphs alone and dropped headings
and tables, the HTML reader joined every text node into one line, and a PDF was the text of its
pages — section chunking found no heading in any of them.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ingestion import markup
from ingestion.loader import DocumentLoader


def _paths(document: Any) -> set[tuple[str, ...]]:
    """The heading paths section chunking gives the document's chunks."""
    from vectordb._base_manager import structural_split

    levels = ("h1", "h2", "h3", "h4")
    return {
        tuple(chunk.metadata[level] for level in levels if chunk.metadata.get(level))
        for chunk in structural_split([document], 800, 200)
    }


def test_a_docx_keeps_its_headings_lists_and_tables(tmp_path: Path) -> None:
    docx = pytest.importorskip("docx")
    from docx.enum.style import WD_STYLE_TYPE

    document = docx.Document()
    document.add_heading("Guide", level=1)
    document.add_paragraph("Plans differ in price.")
    # A heading by the style it is based on, not by its own name.
    custom = document.styles.add_style("Fee heading", WD_STYLE_TYPE.PARAGRAPH)
    custom.base_style = document.styles["Heading 2"]
    document.add_paragraph("Fees", style="Fee heading")
    document.add_paragraph("monthly", style="List Bullet")
    document.add_paragraph("yearly", style="List Bullet")
    table = document.add_table(rows=3, cols=2)
    for row, texts in zip(table.rows, [("Plan", "Price"), ("Basic", "5 | 6")], strict=False):
        for cell, text in zip(row.cells, texts, strict=True):
            cell.text = text
    merged = table.cell(2, 0).merge(table.cell(2, 1))
    merged.text = "Pro"
    document.save(str(tmp_path / "guide.docx"))

    [loaded] = DocumentLoader().load_documents(tmp_path)

    assert loaded.page_content == (
        "# Guide\n\nPlans differ in price.\n\n## Fees\n\n- monthly\n- yearly\n\n"
        "| Plan | Price |\n|---|---|\n| Basic | 5 \\| 6 |\n| Pro |  |"
    )
    assert _paths(loaded) == {("Guide",), ("Guide", "Fees")}


HTML = """<html><head><title>T</title><style>p {}</style></head><body>
<nav><a href="/">Home</a></nav>
<h1>Guide</h1><p>Plans differ <b>in price</b>.</p>
<h2>Fees</h2>
<ul><li>monthly<ul><li>first day</li></ul></li><li>yearly</li></ul>
<table><tr><th>Plan</th><th>Price</th></tr>
<tr><td>Basic</td><td>5<table><tr><td>or 6</td></tr></table></td></tr></table>
<h3></h3><pre>a = 1
b = 2</pre><script>var x = "<h1>no</h1>";</script>
</body></html>"""


def test_an_html_page_keeps_its_headings_lists_tables_and_code(tmp_path: Path) -> None:
    (tmp_path / "guide.html").write_text(HTML, encoding="utf-8")

    [loaded] = DocumentLoader().load_documents(tmp_path)

    assert loaded.page_content == (
        "Home\n\n# Guide\n\nPlans differ in price.\n\n## Fees\n\n"
        "- monthly\n  - first day\n- yearly\n\n"
        "| Plan | Price |\n|---|---|\n| Basic | 5 or 6 |\n\n"
        "```\na = 1\nb = 2\n```"
    )
    assert loaded.metadata["file_type"] == "html"
    assert ("Guide", "Fees") in _paths(loaded)


class _Reader:
    def __init__(self, outline: list[Any]) -> None:
        self.outline = outline

    @staticmethod
    def get_destination_page_number(item: Any) -> int:
        return int(item.page)


def _item(title: str, page: int) -> SimpleNamespace:
    return SimpleNamespace(title=title, page=page)


def test_a_pdf_outline_puts_headings_into_its_pages() -> None:
    reader = _Reader(
        [_item("Guide", 0), [_item("Fees", 1), _item("Refunds", 2)], _item("Annex", 3)]
    )
    pages = [
        "Guide\nIntro text.",
        "Running title\n  Fees \nThe fee is monthly.",
        "More about fees.\nRefunds\nNone.",
        "Last page.",
    ]

    assert markup.pdf_pages_as_markdown(reader, pages) == [
        "# Guide\nIntro text.",
        # The page begins with text inside "Guide": it carries that heading first.
        "# Guide\nRunning title\n## Fees\nThe fee is monthly.",
        "# Guide\n## Fees\nMore about fees.\n## Refunds\nNone.",
        # A title the page does not hold as a line goes first on its page.
        "# Annex\nLast page.",
    ]
    assert markup.pdf_pages_as_markdown(_Reader([]), pages) == pages


def _pdf(path: Path, pages: list[list[str]]) -> None:
    """A PDF of text lines in a standard font, with the outline Guide › Fees."""
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    font = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )
    for lines in pages:
        page = writer.add_blank_page(612, 792)
        content = DecodedStreamObject()
        operators = ["BT", "/F1 12 Tf", "16 TL", "72 720 Td"]
        operators += [f"({line}) Tj T*" for line in lines]
        content.set_data("\n".join([*operators, "ET"]).encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(content)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
    guide = writer.add_outline_item("Guide", 0)
    writer.add_outline_item("Fees", 1, parent=guide)
    with path.open("wb") as handle:
        writer.write(handle)


def test_a_pdf_with_an_outline_is_chunked_by_its_sections(tmp_path: Path) -> None:
    pytest.importorskip("pypdf")
    _pdf(
        tmp_path / "guide.pdf",
        [["Guide", "Plans differ in price."], ["Fees", "The fee is monthly."], ["More on fees."]],
    )

    loaded = DocumentLoader().load_documents(tmp_path)

    lines = [[line.strip() for line in d.page_content.splitlines() if line.strip()] for d in loaded]
    assert lines == [
        ["# Guide", "Plans differ in price."],
        ["# Guide", "## Fees", "The fee is monthly."],
        ["# Guide", "## Fees", "More on fees."],
    ]
    assert [d.metadata["page"] for d in loaded] == [1, 2, 3]
    assert _paths(loaded[2]) == {("Guide", "Fees")}
