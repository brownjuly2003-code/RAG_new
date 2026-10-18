"""scripts/wixqa_loader_check.py: source HTML through the product loader, held to the text."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import wixqa_loader_check

PAGE = (
    "<div><div>Open the <b>Settings</b> panel.</div></div>"
    # The page writes a heading with a no-break space; the loader's text has a space.
    "<h3>Fees\u00a0due</h3><ul><li>Monthly: 5</li><li>Yearly: 50</li></ul>"
    "<table><tr><th>Plan</th><th>Price</th></tr><tr><td>Basic</td><td>5</td></tr></table>"
)
CONTENTS = "Billing basics\nOpen the Settings panel.\nFees due\nMonthly: 5\nYearly: 50\nPlan Price\nBasic 5"


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_the_loader_holds_every_visible_character_heading_and_row(tmp_path: Path) -> None:
    raw = tmp_path / "wixqa"
    articles = [
        {"id": "a1", "title": "Billing basics", "contents": CONTENTS, "html_content": PAGE},
        # A page whose text the dataset's contents do not hold whole: one word is missing
        # from the HTML.
        {
            "id": "a2",
            "title": "Short",
            "contents": "Short\nThe quick brown fox",
            "html_content": "<p>The brown fox</p>",
        },
        # A page with nothing beyond its title: the loader makes no document of it.
        {"id": "a3", "title": "Empty", "contents": "Empty", "html_content": "<div></div>"},
    ]
    _write(raw / "wix_kb_corpus/wix_kb_corpus.jsonl", articles)
    _write(raw / "wixqa_expertwritten/test.jsonl", [{"article_ids": ["a1"]}])
    _write(raw / "wixqa_simulated/test.jsonl", [{"article_ids": ["a1", "a2"]}])

    report = wixqa_loader_check.check(raw)

    assert report["documents"] == 3 and report["loaded"] == 2
    assert report["documents_without_text_beyond_title"] == 1
    assert report["documents_whole"] == 2
    assert report["documents_with_every_heading_in_order"] == 3
    assert report["documents_with_every_table_row"] == 3
    assert report["gold_articles"] == 2 and report["gold_articles_whole"] == 1
    assert report["documents_with_text_beyond_contents"] == 0
    assert report["least_held"][0]["id"] == "a2"
    assert report["least_held"][0]["held"] < report["least_held"][0]["chars"]
