"""List what ties the loading and chat path to a language, a domain or a file format.

Usage: python -m scripts.universality_audit [--json OUT]

The audit of PLAN.md stage 1, step 1, in a form that can be run again: it walks the Python
modules of loading, chunking, headers, the index, retrieval, prompts and the API
(``SCOPE``) and lists

    cyrillic   string literals with Cyrillic letters (docstrings and comments are not code)
    regex      the patterns of re.compile / re.search / re.sub and the like
    words      literal collections of four or more words (a hand-made word list)
    domain     literals that name the aircargo domain (``DOMAIN_TERMS``)

and the readers of ``ingestion/loader.py`` by file format. Each finding is keyed by file,
function and kind, not by line, so a key survives an edit elsewhere in the file. The outcome
of each key — fixed, a limitation with its reason, or not text the model or the customer
reads — is in docs/specs/stage1-fixes.md.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

SCOPE = ("agent", "api", "config", "ingestion", "llm", "services", "vectordb")

#: The aircargo domain in its own words: an audit term list, not product code.
DOMAIN_TERMS = (
    "aircargo",
    "air cargo",
    "awb",
    "cargo",
    "shipment",
    "груз",
    "авиа",
    "накладн",
    "отправк",
)

_CYRILLIC = re.compile(r"[А-Яа-яЁё]")
_WORD = re.compile(r"^[^\W\d_][\w .'’-]*$")
_RE_FUNCTIONS = {
    "compile",
    "search",
    "match",
    "fullmatch",
    "findall",
    "finditer",
    "sub",
    "subn",
    "split",
}


@dataclass(frozen=True)
class Finding:
    kind: str
    path: str
    scope: str
    line: int
    text: str

    @property
    def key(self) -> str:
        return f"{self.path}::{self.scope}::{self.kind}"


def _docstrings(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    ids.add(id(body[0].value))
    return ids


def _scopes(tree: ast.AST) -> dict[int, str]:
    """The innermost function or class of every node, by node id."""
    names: dict[int, str] = {}

    def visit(node: ast.AST, name: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = name
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                inner = f"{name}.{child.name}" if name != "<module>" else child.name
            names[id(child)] = inner
            visit(child, inner)

    visit(tree, "<module>")
    return names


def _short(text: str, limit: int = 90) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _strings(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        return [
            part.value
            for part in node.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        ]
    return []


def audit_file(path: Path) -> list[Finding]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    docstrings = _docstrings(tree)
    scopes = _scopes(tree)
    relative = path.relative_to(ROOT).as_posix()
    found: list[Finding] = []
    seen_joined: set[int] = set()

    for node in ast.walk(tree):
        scope = scopes.get(id(node), "<module>")
        if isinstance(node, ast.JoinedStr):
            for part in node.values:
                seen_joined.add(id(part))
        if isinstance(node, (ast.Constant, ast.JoinedStr)) and id(node) not in docstrings:
            if id(node) in seen_joined:
                continue
            text = "".join(_strings(node))
            if not text:
                continue
            if _CYRILLIC.search(text):
                found.append(Finding("cyrillic", relative, scope, node.lineno, _short(text)))
            lowered = text.lower()
            for term in DOMAIN_TERMS:
                if term in lowered:
                    found.append(Finding("domain", relative, scope, node.lineno, _short(text)))
                    break
        elif isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "re"
                and func.attr in _RE_FUNCTIONS
                and node.args
            ):
                pattern = "".join(_strings(node.args[0])) or ast.unparse(node.args[0])
                found.append(Finding("regex", relative, scope, node.lineno, _short(pattern)))
        elif isinstance(node, (ast.List, ast.Set, ast.Tuple)):
            words = [
                element.value
                for element in node.elts
                if isinstance(element, ast.Constant)
                and isinstance(element.value, str)
                and _WORD.match(element.value)
                and " " not in element.value.strip()
                and not element.value.isidentifier()
            ]
            if len(words) >= 4:
                found.append(
                    Finding("words", relative, scope, node.lineno, _short(", ".join(words)))
                )
    return found


def _files() -> Iterator[Path]:
    for package in SCOPE:
        yield from sorted((ROOT / package).rglob("*.py"))


def loader_formats() -> dict[str, str]:
    """The reader of each supported extension in ingestion/loader.py, by function name."""
    tree = ast.parse((ROOT / "ingestion" / "loader.py").read_text(encoding="utf-8"))
    readers: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_load_file":
            for statement in ast.walk(node):
                if not isinstance(statement, ast.If):
                    continue
                extensions = [
                    element.value
                    for element in ast.walk(statement.test)
                    if isinstance(element, ast.Constant) and isinstance(element.value, str)
                ]
                methods = [
                    inner.func.attr
                    for inner in ast.walk(statement.body[-1])
                    if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute)
                ]
                reader = methods[0] if methods else "inline"
                for extension in extensions:
                    readers.setdefault(extension, reader)
    return dict(sorted(readers.items()))


def run() -> dict[str, Any]:
    findings = [finding for path in _files() for finding in audit_file(path)]
    by_key: dict[str, list[Finding]] = {}
    for finding in findings:
        by_key.setdefault(finding.key, []).append(finding)
    return {
        "scope": list(SCOPE),
        "domain_terms": list(DOMAIN_TERMS),
        "loader_formats": loader_formats(),
        "counts": {
            kind: sum(1 for finding in findings if finding.kind == kind)
            for kind in ("cyrillic", "regex", "words", "domain")
        },
        "keys": {key: [asdict(item) for item in items] for key, items in sorted(by_key.items())},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, help="write the full report here")
    args = parser.parse_args(argv)
    report = run()
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report["counts"], ensure_ascii=False))
    print(json.dumps(report["loader_formats"], ensure_ascii=False))
    for key, items in report["keys"].items():
        first = items[0]
        print(f"{key}  x{len(items)}  L{first['line']}  {first['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
