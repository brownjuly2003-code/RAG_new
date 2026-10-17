"""The repeatable audit of PLAN.md stage 1: what in the chat's code is bound to a language or a corpus."""

from __future__ import annotations

from pathlib import Path

from scripts import universality_audit as audit

SAMPLE = '''
"""Ответ модели: a docstring is not a finding."""
import re


def answer(text):
    label = "Источник"
    if re.search(r"достав\\w*", text):
        return label
    stop = ["don't", "can't", "won't", "isn't"]
    return "air cargo" if text in stop else text
'''


def test_the_audit_finds_each_kind_once_and_skips_docstrings(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    module = tmp_path / "agent" / "sample.py"
    module.parent.mkdir()
    module.write_text(SAMPLE, encoding="utf-8")

    found = audit.audit_file(module)

    by_kind = {finding.kind: finding for finding in found}
    assert sorted(f.kind for f in found) == ["cyrillic", "cyrillic", "domain", "regex", "words"]
    assert {f.text for f in found if f.kind == "cyrillic"} == {"Источник", "достав\\w*"}
    assert by_kind["regex"].text == "достав\\w*"
    # A word that is also an identifier reads as a key; these four are not identifiers.
    assert by_kind["words"].text == "don't, can't, won't, isn't"
    assert by_kind["domain"].text == "air cargo"
    assert {f.key for f in found} >= {"agent/sample.py::answer::regex"}


def test_the_header_module_writes_no_word_and_reads_only_the_old_prefix() -> None:
    found = audit.audit_file(audit.ROOT / "vectordb" / "contextual_header.py")

    assert [(f.kind, f.scope, f.text) for f in found if f.kind != "regex"] == [
        ("cyrillic", "<module>", "[Контекст:")
    ]


def test_the_loader_formats_name_a_reader_for_each_extension() -> None:
    formats = audit.loader_formats()

    assert {".md", ".docx", ".html", ".pdf"} <= set(formats)
    assert all(formats.values())
