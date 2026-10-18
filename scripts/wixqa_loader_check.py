"""WixQA's articles in their source HTML through the product's loader, against the connection.

Usage: python -m scripts.wixqa_loader_check --raw DIR --out FILE

PLAN.md stage 1, item 2 (loaders): the external bases were converted to markdown by the
connection's script (evaluation/external_convert.py), around the product's loader, so every
measurement read them at their best. Here each article's ``html_content`` is written to an
``.html`` file and read by ``ingestion.loader.DocumentLoader`` — what a customer uploading these
pages would get — and held to the measures the connection's conversion passed for all 6,221
articles (reports/external/36f1167/connection.json, wixqa.convert.counts):

- the visible text: the article's ``contents`` (the dataset's own text of the page, its title
  first) without the title, as the characters that are neither space nor control; whole when
  they all stand, in order, in the loader's text. Characters the loader adds beyond them are
  counted apart: markdown syntax, or text the page holds and ``contents`` does not;
- the headings: the texts of the page's h1-h6 (``external_convert.html_headings``) equal, in
  order, the loader's markdown headings, white space read as one space on both sides (the page
  writes some with a no-break space, the loader's text with a space);
- the table rows: the page's ``<tr>`` count equals the loader's table lines without the
  separator rows;
- the gold: the articles the questions of both strata name, whole.

An article whose page holds no text beyond its title yields no document — the loader skips an
empty file — and is counted apart; nothing of it can be lost.

The report holds counts and article ids only: the texts stay on the host
(evaluation/external_bases.json, "redistribution").
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from evaluation import external_convert as convert
from evaluation.external_gold import visible

SYNTAX = set("#|-*`>:.\\0123456789")


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def covered(target: str, text: str) -> tuple[int, int]:
    """How many characters of ``target`` stand in ``text`` in order, and how many characters of
    ``text`` outside them are not markdown syntax (exact when all of ``target`` stands)."""
    position = 0
    matched = [False] * len(text)
    for offset, char in enumerate(text):
        if position < len(target) and char == target[position]:
            matched[offset] = True
            position += 1
    if position < len(target):
        matcher = difflib.SequenceMatcher(None, target, text, autojunk=False)
        blocks = matcher.get_matching_blocks()
        matched = [False] * len(text)
        for block in blocks:
            matched[block.b : block.b + block.size] = [True] * block.size
        position = sum(block.size for block in blocks)
    beyond = sum(
        1 for offset, char in enumerate(text) if not matched[offset] and char not in SYNTAX
    )
    return position, beyond


def _spaced(text: str) -> str:
    return " ".join(text.split())


def table_rows(markdown: str) -> int:
    return sum(
        1
        for line in markdown.split("\n")
        if line.lstrip().startswith("|") and not re.fullmatch(r"[\s|:\-]+", line)
    )


def check(raw: Path) -> dict[str, Any]:
    from ingestion.loader import DocumentLoader

    inputs = (
        "wix_kb_corpus/wix_kb_corpus.jsonl",
        "wixqa_expertwritten/test.jsonl",
        "wixqa_simulated/test.jsonl",
    )
    articles = _lines(raw / "wix_kb_corpus/wix_kb_corpus.jsonl")
    gold = {
        article_id
        for stratum in ("expertwritten", "simulated")
        for row in _lines(raw / f"wixqa_{stratum}/test.jsonl")
        for article_id in row["article_ids"]
    }
    with tempfile.TemporaryDirectory() as folder:
        for index, article in enumerate(articles):
            (Path(folder) / f"{index:05d}.html").write_text(
                article["html_content"], encoding="utf-8"
            )
        loaded = {
            document.metadata["source"]: document.page_content
            for document in DocumentLoader(recursive=False).load_documents(folder)
        }
    rows = []
    for index, article in enumerate(articles):
        markdown = loaded.get(f"{index:05d}.html", "")
        title = visible(article["title"])[0]
        target = visible(article["contents"])[0]
        target = target[len(title) :] if target.startswith(title) else target
        text = visible(markdown)[0]
        held, beyond = covered(target, text)
        headings = [
            _spaced(heading.replace("\\", "")) for _, heading in convert.markdown_headings(markdown)
        ]
        rows.append(
            {
                "id": article["id"],
                "gold": article["id"] in gold,
                "chars": len(target),
                "held": held,
                "beyond_syntax": beyond,
                "loaded": f"{index:05d}.html" in loaded,
                "headings": headings
                == [_spaced(heading) for heading in convert.html_headings(article["html_content"])],
                "rows": table_rows(markdown)
                == len(re.findall(r"(?i)<tr\b", article["html_content"])),
            }
        )
    whole = [row for row in rows if row["held"] == row["chars"]]
    gold_rows = [row for row in rows if row["gold"]]
    # An article with no text beyond its title has nothing to lose: it is whole.
    worst = sorted(rows, key=lambda row: row["held"] / row["chars"] if row["chars"] else 1.0)[:10]
    return {
        "documents": len(rows),
        "loaded": len(loaded),
        "documents_without_text_beyond_title": sum(
            1 for row in rows if not row["loaded"] and row["chars"] == 0
        ),
        "documents_whole": len(whole),
        "visible_characters": sum(row["chars"] for row in rows),
        "visible_characters_held": sum(row["held"] for row in rows),
        "documents_with_text_beyond_contents": sum(row["beyond_syntax"] > 0 for row in rows),
        "documents_with_every_heading_in_order": sum(row["headings"] for row in rows),
        "documents_with_every_table_row": sum(row["rows"] for row in rows),
        "gold_articles": len(gold_rows),
        "gold_articles_whole": sum(row["held"] == row["chars"] for row in gold_rows),
        "gold_articles_with_every_heading_in_order": sum(row["headings"] for row in gold_rows),
        "least_held": [
            {"id": row["id"], "chars": row["chars"], "held": row["held"]} for row in worst
        ],
        "input_sha256": {
            name: hashlib.sha256((raw / name).read_bytes()).hexdigest() for name in inputs
        },
        "connection": {
            "documents_with_the_visible_text_of_contents": 6221,
            "documents_with_every_heading_in_order": 6221,
            "source": "reports/external/36f1167/connection.json",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report = check(args.raw)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    args.out.write_bytes(text.encode("utf-8"))
    print(json.dumps({k: v for k, v in report.items() if k != "least_held"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
