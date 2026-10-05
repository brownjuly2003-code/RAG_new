"""Markdown rendering of an external base's documents (plan step 1.5): rules, places, names."""

import pytest

from evaluation import external_convert as convert
from evaluation.external_convert import Block

BLOCKS = [
    Block("heading", "Leave  and\npay", level=1),
    Block("para", "First line\r\n# not a heading\n\n  second\u2028third  ", key="p"),
    Block("item", "one", level=1, key="i1"),
    Block("item", "two\n``` fence\nmore", level=2, ordinal=3, key="i2"),
    Block("para", "", key="empty"),
    Block("row", cells=("Rate", "Pay | net"), level=1, key="r1"),
    Block("row", cells=("A", ""), level=1, key="r2"),
    Block("row", cells=("B", "2"), level=2, key="r3"),
    Block("code", "\n  x = 1\n```\ny\n\n", key="c"),
    Block("heading", "Deep", level=5, key="h5"),
    Block("para", "## looks like one", key="g"),
]
RENDERED = (
    "# Leave and pay\n"
    "\n"
    "First line\n"
    "\\# not a heading\n"
    "second\n"
    "third\n"
    "\n"
    "- one\n"
    "  3. two\n"
    "     \\``` fence\n"
    "     more\n"
    "\n"
    "| Rate | Pay \\| net |\n"
    "| --- | --- |\n"
    "| A |  |\n"
    "\n"
    "| B | 2 |\n"
    "| --- | --- |\n"
    "\n"
    "```\n"
    "  x = 1\n"
    "\\```\n"
    "y\n"
    "```\n"
    "\n"
    "##### Deep\n"
    "\n"
    "\\## looks like one\n"
)
HTML = (
    '<div data-x="1"><h2 level="3">Set&nbsp;up <b>billing</b></h2>'
    "<p>Pay  the\n fee<br>today &amp; <a href='u'>here</a><img src='i' alt='pic'></p>"
    '<h4 class="t" aria-level="2">Second</h4><h3></h3>'
    "<ol start='4'><li>four<ul><li>inner <i>a</i></li><li><p>inner b</p><p>more b</p></li></ul>"
    "</li><li>five</li></ol>"
    "<table><thead><tr><th>Plan</th><th>Price</th></tr></thead>"
    "<tbody><tr><td>Basic<ul><li>x</li><li>y</li></ul></td><td>1</td></tr><tr><td>Pro<td>2</table>"
    "<table><tr><td>other</td></tr></table>"
    "<pre>line 1\n  line 2</pre><script>var a = '<b>no</b>';</script><style>p{}</style>"
    "tail text</div>"
)


def test_render_writes_the_blocks_and_gives_the_place_of_every_keyed_one() -> None:
    text, spans = convert.render(BLOCKS)

    assert text == RENDERED
    assert {key: text[start:end] for key, (start, end) in spans.items()} == {
        "p": "First line\n\\# not a heading\nsecond\nthird",
        "i1": "one",
        "i2": "two\n     \\``` fence\n     more",
        "r1": "Rate | Pay \\| net",
        "r2": "A | ",
        "r3": "B | 2",
        "c": "  x = 1\n\\```\ny",
        "h5": "Deep",
        "g": "## looks like one",
    }
    # A block without text is not written and has no place.
    assert "empty" not in spans
    assert "\r" not in text


def test_a_rendered_document_has_only_the_headings_it_was_given() -> None:
    # Lines of a paragraph, an item or code that start like a heading or a fence are guarded,
    # so the heading splitter reads the two headings and nothing else.
    assert convert.markdown_headings(RENDERED) == [(1, "Leave and pay"), (5, "Deep")]
    assert convert.markdown_headings("```\n# in code\n```\n# out\n~~~\n## in\n~~~\n#no\n#") == [
        (1, "out"),
        (1, ""),
    ]


def test_render_of_nothing_is_an_empty_document() -> None:
    assert convert.render([]) == ("", {})
    assert convert.render([Block("para", " \n ", key=1), Block("row", cells=("", " "))]) == ("", {})


def test_render_refuses_a_repeated_key_and_an_unknown_kind() -> None:
    with pytest.raises(ValueError, match="block key repeated"):
        convert.render([Block("para", "a", key=1), Block("para", "b", key=1)])
    with pytest.raises(ValueError, match="unknown block kind"):
        convert.render([Block("quote", "a")])


def test_html_blocks_follow_the_registered_rules() -> None:
    assert convert.html_blocks(HTML) == [
        # the explicit level wins over the tag; the non-breaking space is kept
        Block("heading", "Set\xa0up billing", level=3),
        # ASCII whitespace collapses, <br> breaks the line, the image leaves nothing
        Block("para", "Pay the fee\ntoday & here"),
        Block("heading", "Second", level=2),
        Block("item", "four", level=1, ordinal=4),
        Block("item", "inner a", level=2),
        Block("item", "inner b\nmore b", level=2),
        Block("item", "five", level=1, ordinal=5),
        Block("row", cells=("Plan", "Price"), level=1),
        Block("row", cells=("Basic x y", "1"), level=1),
        Block("row", cells=("Pro", "2"), level=1),
        Block("row", cells=("other",), level=2),
        Block("code", "line 1\n  line 2"),
        Block("para", "tail text"),
    ]


@pytest.mark.parametrize(
    ("html", "blocks"),
    [
        ("<p>one<h2>Two<br>lines", [Block("para", "one"), Block("heading", "Two lines", level=2)]),
        (
            "<ul><li>a<li>b<br>c</ul>tail",
            [Block("item", "a", level=1), Block("item", "b\nc", level=1), Block("para", "tail")],
        ),
        ("<pre>code\n<b>bold</b>", [Block("code", "code\nbold")]),
        (
            "<table><tr><td>a<table><tr><td>in</td></tr></table>z</td><td>b</td></tr></table>",
            [Block("row", cells=("a in z", "b"), level=1)],
        ),
        (
            "<h2>A<div>B</div>C</h2><div>x<div>y</div></div>",
            [Block("heading", "A B C", level=2), Block("para", "x"), Block("para", "y")],
        ),
        ("<p>a&#8203;b &lt;tag&gt;</p>", [Block("para", "a\u200bb <tag>")]),
    ],
)
def test_html_blocks_read_what_a_fragment_leaves_open_or_nests(
    html: str, blocks: list[Block]
) -> None:
    assert convert.html_blocks(html) == blocks


def test_html_headings_are_read_without_the_converter() -> None:
    # The check of heading preservation: the same headings by another reading of the HTML.
    assert convert.html_headings(HTML) == ["Set\xa0up billing", "Second"]
    written = [block.text for block in convert.html_blocks(HTML) if block.kind == "heading"]
    assert written == convert.html_headings(HTML)
    assert convert.html_headings("<H3 class=x>R&amp;D <i>team</i></H3 >") == ["R&D team"]


def test_file_names_are_title_slugs_and_do_not_depend_on_the_order() -> None:
    titles = ["Set up billing", "Set up: billing!", "Ünïcode Tïtle", "日本語", "x" * 80, "Other"]
    ids = ["a", "b", "c", "d", "e", "f"]

    names = convert.file_names(titles, ids)

    assert names == [
        # documents that share a slug both carry the digest of their id
        "set-up-billing-ca978112.md",
        "set-up-billing-3e23e816.md",
        "unicode-title.md",
        "doc.md",
        "x" * convert.NAME_LENGTH + ".md",
        "other.md",
    ]
    assert convert.file_names(titles[::-1], ids[::-1])[::-1] == names
    with pytest.raises(ValueError, match="collide"):
        convert.file_names(["same", "same"], ["one", "one"])
