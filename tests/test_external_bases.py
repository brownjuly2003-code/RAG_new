"""External bases (plan steps 1.5, 1.5c, 1.5d): registration, conversion, gold, the host steps.

Every fixture is written here: no text of a base is in the repository.
"""

import gzip
import io
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from evaluation import external_bases as bases
from evaluation import external_convert as convert
from evaluation import external_gold as gold
from scripts import external_base

LEAVE = "https://example.test/leave"
PAGES = [
    {
        "title": "Leave and pay",
        "url": LEAVE,
        "contents": [
            "<h1>Overview</h1>",
            "<p>You can take leave.</p>",
            "<li>one week</li>",
            "<li>two weeks</li>",
            "<h1>Pay</h1>",
            "<h2>Rates</h2>",
            "<tr>Weeks | Rate</tr>",
            "<tr>1 | 90%</tr>",
            "<p>You can take leave.</p>",
            "<p></p>",
            "<h2>Dates</h2>",
            "<li>one week</li>",
        ],
    },
    {
        "title": "Leave and pay!",
        "url": LEAVE + "-2",
        "contents": ["<h1>Only</h1>", "<p>Nothing here.</p>"],
    },
]
TRAIN = [
    {
        "id": "train-0",
        "url": LEAVE,
        "scenario": "I work full time.",
        "question": "Can I take leave?",
        "not_answerable": False,
        "answers": [["yes", []], ["one week", ["<li>one week</li>"]]],
        "evidences": [
            "<p>You can take leave.</p>",
            "<h2>Rates</h2>",
            "<tr>1 | 90%</tr>",
            "<h2>Rates</h2>",
        ],
    },
    {
        "id": "train-1",
        "url": LEAVE,
        "scenario": "I left.",
        "question": "What now?",
        "not_answerable": True,
        "answers": [],
        "evidences": [],
    },
]
DEV = [
    {
        "id": "dev-0",
        "url": LEAVE + "-2",
        "scenario": "I ask.",
        "question": "Is there anything?",
        "not_answerable": False,
        "answers": [["no", []]],
        "evidences": ["<p>Nothing here.</p>", "<p></p>", "<li>one week</li>"],
    },
]
LEAVE_MARKDOWN = (
    "# Leave and pay\n\n## Overview\n\nYou can take leave.\n\n- one week\n- two weeks\n\n"
    "## Pay\n\n### Rates\n\n| Weeks | Rate |\n| --- | --- |\n| 1 | 90% |\n\n"
    "You can take leave.\n\n### Dates\n\n- one week\n"
)
ARTICLES = [
    {
        "id": "a1",
        "title": "Set up billing",
        "url": "u1",
        "article_type": "article",
        "contents": "Set up billing\nPlansPay the fee today.BasicPro",
        "html_content": '<div><h2 level="3">Plans</h2><p>Pay the fee today.</p>'
        "<ul><li>Basic</li><li>Pro</li></ul></div>",
    },
    {
        "id": "a2",
        "title": "Request: dark mode",
        "url": "u2",
        "article_type": "feature_request",
        "contents": "Request: dark mode\nVote for it.",
        "html_content": "<p>Vote for it.</p><h4></h4>",
    },
]
MARKETS = "https://example.test/markets"
NEWS = [
    {
        "title": "Markets rise",
        "source": "The Daily",
        "published_at": "2023-10-01T08:30:00+00:00",
        "url": MARKETS,
        "author": "A",
        "category": "business",
        "body": "Stocks rose on Monday.\n\nAnalysts were surprised. Stocks rose on Monday.\n \n"
        "# Not a heading",
    },
    {
        "title": "Rain",
        "source": "Weather Now",
        "published_at": "2023-11-05T00:00:00+00:00",
        "url": "https://example.test/rain",
        "author": "B",
        "category": "weather",
        "body": "It rained in the north.",
    },
]
QUERIES = [
    {
        "query": "Which outlets reported a rise and rain?",
        "answer": "The Daily and Weather Now",
        "question_type": "comparison_query",
        "evidence_list": [
            {"url": MARKETS, "fact": "Stocks rose on Monday."},
            {"url": "https://example.test/rain", "fact": "It rained in the north."},
            {"url": MARKETS, "fact": "Stocks rose on Monday."},
            {"url": MARKETS, "fact": "Markets rise"},
        ],
    },
    {
        "query": "Who won?",
        "answer": "Insufficient information.",
        "question_type": "null_query",
        "evidence_list": [],
    },
]


def _dump(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def _lines(rows: list[dict]) -> bytes:
    return "".join(json.dumps(row) + "\n" for row in rows).encode("utf-8")


RAW = {
    "conditionalqa": {
        "v1_0/documents.json": _dump(PAGES),
        "v1_0/train.json": _dump(TRAIN),
        "v1_0/dev.json": _dump(DEV),
    },
    "wixqa": {
        "wix_kb_corpus/wix_kb_corpus.jsonl": _lines(ARTICLES),
        "wixqa_expertwritten/test.jsonl": _lines(
            [{"question": "How do I pay?", "answer": "Pay.", "article_ids": ["a1", "a1", "a2"]}]
        ),
        "wixqa_simulated/test.jsonl": _lines(
            [{"question": "Is it dark?", "answer": "Vote.", "article_ids": ["a2"]}]
        ),
    },
    "multihoprag": {"corpus.json": _dump(NEWS), "MultiHopRAG.json": _dump(QUERIES)},
}


def _shown(document: bases.Document, alternative: dict) -> str:
    source = gold.Source.read(document.name, document.markdown)
    return source.text[alternative["start"] : alternative["end"]]


def test_the_registration_pins_every_file_of_every_base() -> None:
    registered = bases.registration()

    assert registered["converter_version"] == convert.CONVERTER_VERSION
    assert registered["match_rule"] == gold.MATCH_RULE
    assert set(registered["bases"]) == {"conditionalqa", "wixqa", "multihoprag"}
    assert "no question, evidence string, document" in registered["redistribution"]
    tenants = set()
    for base in registered["bases"].values():
        assert re.fullmatch(r"[0-9a-f]{40}", base["revision"])
        assert base["url"].startswith("https://") and "{revision}" in base["url"]
        assert base["collection"] == "rag_docs_" + base["tenant"]
        assert base["license"] and base["citation"] and base["labels"]
        tenants.add(base["tenant"])
        for entry in base["files"]:
            assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) and entry["bytes"] > 0
        converted = base["converted"]
        assert converted["documents"] > 0 and converted["cases"] > 0
        assert re.fullmatch(r"[0-9a-f]{64}", converted["corpus_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", converted["cases_sha256"])
    assert len(tenants) == 3 and all(tenant.startswith("ext_") for tenant in tenants)
    # The answers of ConditionalQA come with a use restriction: it is written where it is read.
    assert "ONLY be used for NLP research" in registered["bases"]["conditionalqa"]["license"]
    assert registered["bases"]["multihoprag"]["labels"].startswith("llm_labelled")


def test_the_registered_chunking_is_the_product_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from config.settings import Settings

    for name in (
        "RAG_STRUCTURAL_CHUNKING",
        "RAG_CONTEXTUAL_HEADERS",
        "RAG_CHUNK_SIZE",
        "RAG_CHUNK_OVERLAP",
        "CHUNK_SIZE",
        "CHUNK_OVERLAP",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings()

    # Structural chunking goes first in select_chunks, so the semantic flag is not registered.
    chunking = bases.registration()["chunking"]
    assert set(chunking) == {
        "chunk_size",
        "chunk_overlap",
        "structural_chunking",
        "contextual_headers",
    }
    assert {key: getattr(settings, key) for key in chunking} == chunking


def test_read_raw_refuses_a_file_that_differs_from_the_registration(tmp_path: Path) -> None:
    data = b"pinned"
    (tmp_path / "v1").mkdir()
    (tmp_path / "v1" / "file.json").write_bytes(data)
    base = {"files": [{"path": "v1/file.json", "bytes": 6, "sha256": bases.sha256(data)}]}

    assert bases.read_raw(base, tmp_path) == {"v1/file.json": data}
    (tmp_path / "v1" / "file.json").write_bytes(b"pinneD")
    with pytest.raises(ValueError, match="differs from the registration: v1/file.json"):
        bases.read_raw(base, tmp_path)
    with pytest.raises(ValueError, match="unregistered base"):
        bases.convert_base("squad", {})


def test_conditionalqa_pages_and_their_evidence_places() -> None:
    documents, cases, counts = bases.convert_base("conditionalqa", RAW["conditionalqa"])

    # Two titles with one slug: both names carry the digest of the page address.
    assert [document.name for document in documents] == [
        f"leave-and-pay-{bases.sha256(LEAVE.encode())[:8]}.md",
        f"leave-and-pay-{bases.sha256((LEAVE + '-2').encode())[:8]}.md",
    ]
    assert documents[0].markdown == LEAVE_MARKDOWN
    first, second, third = cases
    assert first["case_id"] == "conditionalqa-train-0"
    assert first["query"] == "I work full time. Can I take leave?"
    assert (first["split"], first["stratum"], first["conditional"]) == ("train", "answerable", True)
    assert first["reference_answers"] == ["yes", "one week"]
    assert first["document"] == documents[0].name
    # The string given twice is one group; the paragraph that stands twice has two alternatives.
    paragraph, heading, row = first["evidence_groups"]
    assert [_shown(documents[0], alternative) for alternative in paragraph["alternatives"]] == [
        "Youcantakeleave.",
        "Youcantakeleave.",
    ]
    assert [
        (a["element"], a["tag"], a["part"], a["section"], a["same_section"], a["same_part"])
        for a in paragraph["alternatives"]
    ] == [(1, "p", 0, 0, False, False), (8, "p", 4, 5, True, True)]
    assert paragraph["alternatives"][0]["start"] < paragraph["alternatives"][1]["start"]
    assert [_shown(documents[0], group["alternatives"][0]) for group in (heading, row)] == [
        "Rates",
        "1|90%",
    ]
    assert "same_section" not in heading["alternatives"][0]
    assert (second["stratum"], second["evidence_groups"], second["gold_sources"]) == (
        "not_answerable",
        [],
        [],
    )
    # An evidence string that is not an element with text of the question's page is unresolved.
    assert (third["split"], third["unresolved_evidence"], len(third["evidence_groups"])) == (
        "dev",
        2,
        1,
    )
    assert {
        key: counts[key]
        for key in (
            "documents",
            "elements",
            "elements_without_text",
            "questions",
            "questions_answerable",
            "evidence_references",
            "evidence_strings_repeated_in_a_question",
            "evidence_groups",
            "evidence_unresolved",
            "evidence_groups_with_several_places",
            "alternatives",
            "document_strings_with_several_places",
            "several_places_one_beside_other_evidence",
            "several_places_none_beside_other_evidence",
            "questions_with_evidence_in_several_parts",
            "evidence_groups_by_tag",
        )
    } == {
        "documents": 2,
        "elements": {"h1": 3, "h2": 2, "li": 3, "p": 4, "tr": 2},
        "elements_without_text": 1,
        "questions": 3,
        "questions_answerable": 2,
        "evidence_references": 7,
        "evidence_strings_repeated_in_a_question": 1,
        "evidence_groups": 4,
        "evidence_unresolved": 2,
        "evidence_groups_with_several_places": 1,
        "alternatives": 5,
        "document_strings_with_several_places": 1,
        "several_places_one_beside_other_evidence": 1,
        "several_places_none_beside_other_evidence": 0,
        "questions_with_evidence_in_several_parts": 0,
        "evidence_groups_by_tag": {"h2": 1, "p": 2, "tr": 1},
    }


def test_wixqa_articles_keep_their_headings_and_their_text() -> None:
    documents, cases, counts = bases.convert_base("wixqa", RAW["wixqa"])

    assert [(document.name, document.document_id) for document in documents] == [
        ("set-up-billing.md", "a1"),
        ("request-dark-mode.md", "a2"),
    ]
    assert documents[0].markdown == (
        "# Set up billing\n\n### Plans\n\nPay the fee today.\n\n- Basic\n- Pro\n"
    )
    assert cases == [
        {
            "case_id": "wixqa-expertwritten-000",
            "base": "wixqa",
            "stratum": "expertwritten",
            "query": "How do I pay?",
            "gold_sources": ["set-up-billing.md", "request-dark-mode.md"],
            "reference_answers": ["Pay."],
        },
        {
            "case_id": "wixqa-simulated-000",
            "base": "wixqa",
            "stratum": "simulated",
            "query": "Is it dark?",
            "gold_sources": ["request-dark-mode.md"],
            "reference_answers": ["Vote."],
        },
    ]
    assert counts == {
        "documents": 2,
        "documents_by_type": {"article": 1, "feature_request": 1},
        "blocks": {"heading": 1, "item": 2, "para": 2},
        "headings_in_html": 1,
        "headings_written": 1,
        "headings_written_by_level": {"level_3": 1},
        "documents_with_every_heading_in_order": 2,
        "documents_with_the_visible_text_of_contents": 2,
        "questions": {
            "expertwritten": {"questions": 1, "gold_articles_2": 1},
            "simulated": {"questions": 1, "gold_articles_1": 1},
        },
    }


def test_multihoprag_articles_carry_source_and_date_and_facts_have_places() -> None:
    documents, cases, counts = bases.convert_base("multihoprag", RAW["multihoprag"])

    assert documents[0].name == "markets-rise.md"
    # Source, date and title are one heading: the heading path takes them into every chunk.
    assert documents[0].markdown == (
        "# The Daily, 2023-10-01: Markets rise\n\nStocks rose on Monday.\n\n"
        "Analysts were surprised. Stocks rose on Monday.\n\n\\# Not a heading\n"
    )
    asked, null = cases
    assert asked["case_id"] == "multihoprag-0000" and asked["stratum"] == "comparison_query"
    assert asked["gold_sources"] == ["markets-rise.md", "rain.md"]
    # The sentence named twice is one group with its two places; a "fact" that stands only in
    # the heading has no place in the body.
    stocks, rain = asked["evidence_groups"]
    assert [_shown(documents[0], alternative) for alternative in stocks["alternatives"]] == [
        "StocksroseonMonday.",
        "StocksroseonMonday.",
    ]
    assert [alternative["source_id"] for alternative in rain["alternatives"]] == ["rain.md"]
    assert asked["unresolved_evidence"] == 1
    assert (null["stratum"], null["gold_sources"], null["evidence_groups"]) == (
        "null_query",
        [],
        [],
    )
    assert counts == {
        "documents": 2,
        "alternatives": 3,
        "evidence_groups": 2,
        "evidence_groups_with_several_places": 1,
        "evidence_places_differ_from_verbatim_count": 0,
        "evidence_references": 4,
        "evidence_unresolved": 1,
        "questions": 2,
        "questions_by_type": {"comparison_query": 1, "null_query": 1},
        "questions_by_gold_documents": {"gold_documents_0": 1, "gold_documents_2": 1},
    }


@pytest.fixture
def host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """A registration of the three bases with the fixture files, and those files on disk."""
    registered = json.loads(bases.REGISTRATION.read_text(encoding="utf-8"))
    for name, files in RAW.items():
        base = registered["bases"][name]
        base["url"] = "https://example.test/{revision}/{path}"
        base["files"] = [
            {"path": path, "bytes": len(data), "sha256": bases.sha256(data)}
            for path, data in files.items()
        ]
        del base["converted"]
        for path, data in files.items():
            target = tmp_path / "raw" / name / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    registration = tmp_path / "registration.json"
    registration.write_text(json.dumps(registered), encoding="utf-8")
    monkeypatch.setattr(bases, "REGISTRATION", registration)
    return SimpleNamespace(raw=tmp_path / "raw", out=tmp_path / "out", registration=registration)


def test_fetch_keeps_equal_files_and_refuses_a_download_that_differs(
    host: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    served = {"body": RAW["multihoprag"]["corpus.json"]}

    def urlopen(url: str, timeout: float) -> io.BytesIO:
        asked.append(url)
        return io.BytesIO(served["body"])

    monkeypatch.setattr(external_base.urllib.request, "urlopen", urlopen)

    assert external_base.fetch("multihoprag", host.raw)["downloaded"] == 0
    corpus = host.raw / "multihoprag" / "corpus.json"
    corpus.unlink()
    assert external_base.fetch("multihoprag", host.raw)["downloaded"] == 1
    revision = bases.registration()["bases"]["multihoprag"]["revision"]
    assert asked == [f"https://example.test/{revision}/corpus.json"]
    assert corpus.read_bytes() == served["body"]
    corpus.unlink()
    served["body"] = b"another file"
    with pytest.raises(ValueError, match="downloaded file differs from the registration"):
        external_base.fetch("multihoprag", host.raw)
    assert not corpus.exists()


def test_convert_writes_the_corpus_the_cases_and_a_report_of_counts(host: SimpleNamespace) -> None:
    report = external_base.convert_step("multihoprag", host.raw, host.out)

    names = sorted(path.name for path in (host.out / "corpus").iterdir())
    assert names == ["markets-rise.md", "rain.md"]
    markdown = (host.out / "corpus" / "markets-rise.md").read_bytes()
    assert markdown.startswith(b"# The Daily, 2023-10-01: Markets rise\n") and b"\r" not in markdown
    manifest = json.loads((host.out / "corpus.manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "ext_multihoprag" and manifest["file_count"] == 2
    cases = (host.out / "cases.jsonl").read_bytes()
    assert report["cases_sha256"] == bases.sha256(cases) and report["cases"] == 2
    assert report["corpus_sha256"] == manifest["corpus_sha256"]
    assert report["converter_version"] == convert.CONVERTER_VERSION
    assert json.loads((host.out / "convert-report.json").read_text(encoding="utf-8")) == report
    # The report is what may leave the host: counts and digests, no text of the base.
    written = json.dumps(report)
    assert "Stocks" not in written and "Which outlets" not in written
    # The same conversion again gives the same files; a file of another conversion is refused.
    assert external_base.convert_step("multihoprag", host.raw, host.out) == report
    (host.out / "corpus" / "stale.md").write_text("old", encoding="utf-8")
    with pytest.raises(ValueError, match="files of another conversion"):
        external_base.convert_step("multihoprag", host.raw, host.out)


def test_convert_refuses_a_result_that_differs_from_the_registered_one(
    host: SimpleNamespace,
) -> None:
    report = external_base.convert_step("wixqa", host.raw, host.out)
    registered = json.loads(host.registration.read_text(encoding="utf-8"))
    expected = {key: report[key] for key in ("documents", "corpus_sha256", "cases", "cases_sha256")}
    registered["bases"]["wixqa"]["converted"] = expected
    host.registration.write_text(json.dumps(registered), encoding="utf-8")

    assert external_base.convert_step("wixqa", host.raw, host.out) == report
    registered["bases"]["wixqa"]["converted"] = {**expected, "cases_sha256": "0" * 64}
    host.registration.write_text(json.dumps(registered), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from the registered one"):
        external_base.convert_step("wixqa", host.raw, host.out)


def test_chunks_and_preserve_measure_the_product_ingestion(
    host: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    from config import settings as settings_module

    settings = SimpleNamespace(
        chunk_size=800,
        chunk_overlap=200,
        structural_chunking=True,
        semantic_chunking=True,
        contextual_headers=True,
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    for name in RAW:
        external_base.convert_step(name, host.raw, host.out / name)

    chunked = external_base.chunks_step("conditionalqa", host.out / "conditionalqa")

    archive = (host.out / "conditionalqa" / "chunks.json.gz").read_bytes()
    payload = json.loads(gzip.decompress(archive))
    assert chunked["archive_sha256"] == bases.sha256(archive)
    assert chunked["payload_sha256"] == bases.sha256(gzip.decompress(archive))
    assert payload["tenant_id"] == "ext_conditionalqa" == chunked["tenant"]
    # The page of three sections and the page of one.
    assert chunked["chunks"] == len(payload["chunks"]) == 4 and chunked["documents"] == 2
    name = f"leave-and-pay-{bases.sha256(LEAVE.encode())[:8]}.md"
    first = next(chunk for chunk in payload["chunks"] if chunk["metadata"]["source"] == name)
    # The loader's facts about the host are replaced: the archive is the same on any host.
    assert first["metadata"]["file_path"] == name
    assert first["metadata"]["mtime"] == bases.registration()["registered"] + "T00:00:00"
    assert first["metadata"]["content_hash"] == bases.sha256(LEAVE_MARKDOWN.encode("utf-8"))
    assert (first["metadata"]["h1"], first["metadata"]["h2"]) == ("Leave and pay", "Overview")
    assert first["page_content"].startswith(
        f"[Контекст: Из документа {name}, раздел: Leave and pay › Overview]\n# Leave and pay"
    )
    # The non-breaking space of the page is a space in the chunk, not a lost character.
    assert "You can take leave." in first["page_content"]
    again = external_base.chunks_step("conditionalqa", host.out / "conditionalqa")
    assert {**again, "seconds": None} == {**chunked, "seconds": None}

    report = external_base.preserve_step("conditionalqa", host.out / "conditionalqa")

    assert report["chunks_without_a_place"] == 0
    assert report["visible_characters_in_no_chunk"] == 0
    assert report["documents_without_chunks"] == 0
    assert report["alternatives"] == {"whole": 5, "split": 0, "lost": 0}
    assert report["alternatives_by_tag"]["p"] == {"whole": 3, "split": 0, "lost": 0}
    assert report["evidence_groups"] == {"whole": 4, "split": 0, "lost": 0}
    assert report["questions_with_evidence"] == {"worst_group_whole": 2}
    assert report["heading_lines_of_split_depth"] == 7
    assert report["heading_lines_absent_from_chunk_paths"] == 0
    assert report["chunks_whose_header_is_not_the_source_and_the_heading_path"] == 0
    assert report["heading_paths_cut_by_the_header_limit"] == 0
    assert report["gold_documents"] == 2 and report["gold_documents_without_chunks"] == 0
    details = (host.out / "conditionalqa" / "preserve-cases.jsonl").read_text(encoding="utf-8")
    assert json.loads(details.splitlines()[0]) == {
        "case_id": "conditionalqa-train-0",
        "evidence_groups": [
            {"state": "whole", "alternatives": ["whole", "whole"]},
            {"state": "whole", "alternatives": ["whole"]},
            {"state": "whole", "alternatives": ["whole"]},
        ],
    }
    # A corpus changed after the conversion is not measured.
    (host.out / "conditionalqa" / "corpus" / name).write_text("# Other\n", encoding="utf-8")
    with pytest.raises(ValueError, match="the corpus differs from its manifest"):
        external_base.preserve_step("conditionalqa", host.out / "conditionalqa")
    settings.chunk_size = 500
    with pytest.raises(ValueError, match="settings differ from the registered chunking"):
        external_base.chunks_step("wixqa", host.out / "wixqa")
