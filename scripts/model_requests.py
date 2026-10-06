"""What a collector run asked the model, without the texts.

A run of the collector keeps every model request in its replay cache (`RUN/cache/llm-*.json`).
`extract` reads a cache and writes one row a request: its route (with a JSON schema or as plain
text), what it asks (a batch of documents, one document, anything else), the options the request
carried, the outcome, and SHA-256 digests in place of the prompt and of the reply. `summary`
counts one such file. `compare` takes two and counts the requests both runs made, how many of
them got the same reply, and how many documents the grading kept in one run only.

The grading of the product asks in steps (`agent/graph.py`, `make_grade_docs_node`): the whole
batch with a schema; the same batch as text when the reply is not one grade a document; then
every document on its own, with a schema and, when that reply is no verdict, as text. A request
with a schema carries no options of its own; a request as text carries the options of its role.
`verdicts` reads the rows of a document the way the product reads the replies.

Usage:
  python -m scripts.model_requests extract --cache RUN/cache [--out FILE]
  python -m scripts.model_requests summary --file FILE
  python -m scripts.model_requests compare --first FILE --second FILE
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

VERSION = "model-requests/v1"
BATCH, DOCUMENT, OTHER = "batch", "document", "other"
SCHEMA, TEXT = "schema", "text"
# A batch prompt opens every document with such a line (`build_doc_grade_batch_prompt`).
OPENS_DOCUMENT = re.compile(r"^\[(\d+)\] source=", re.MULTILINE)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _prompt(request: Mapping[str, Any]) -> str:
    return "\n".join(str(message.get("content")) for message in request["messages"])


def _asks(request: Mapping[str, Any]) -> str:
    properties = sorted((request.get("schema") or {}).get("properties") or {})
    if properties == ["grades"]:
        return BATCH
    return DOCUMENT if "relevant" in properties else OTHER


def _documents(prompt: str) -> int:
    """Documents a batch prompt lists: its opening lines numbered from one, in order."""
    count = 0
    for found in OPENS_DOCUMENT.finditer(prompt):
        if int(found.group(1)) == count + 1:
            count += 1
    return count


def _json(text: Any) -> Any:
    """A reply as text read as JSON: the whole of it, else its outermost braces."""
    if not isinstance(text, str):
        return None
    for candidate in (text.strip(), (re.search(r"\{.*\}", text, flags=re.DOTALL) or [""])[0]):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _grades(reply: Any) -> int | None:
    """Grades a batch reply holds; None when it holds no list of them."""
    if isinstance(reply, dict):
        reply = reply.get("grades") or reply.get("documents") or reply.get("results")
    return len(reply) if isinstance(reply, list) else None


def extract(cache: Path) -> dict[str, Any]:
    """One row a model request of the cache; the texts are replaced by their digests."""
    entries = [
        json.loads(path.read_text(encoding="utf-8")) for path in sorted(cache.glob("llm-*.json"))
    ]
    if not entries:
        raise ValueError(f"no model request in {cache}")
    # A request as text asks what the request with a schema and the same prompt asks.
    asked = {
        digest(_prompt(entry["request"])): _asks(entry["request"])
        for entry in entries
        if entry["request"].get("schema")
    }
    rows = []
    for entry in entries:
        request, value = entry["request"], entry["value"]
        prompt = _prompt(request)
        route = SCHEMA if request.get("schema") else TEXT
        answered = value["outcome"] == "response"
        reply = value["response"] if answered else value.get("raw_response") or {}
        text = reply.get("text")
        row: dict[str, Any] = {
            "asks": asked.get(digest(prompt), OTHER),
            "route": route,
            "prompt_sha256": digest(prompt),
            "prompt_chars": len(prompt),
            "options": request.get("kwargs") or {},
            "outcome": value["outcome"],
            "reply_sha256": digest(text) if isinstance(text, str) else None,
            "latency_ms": reply.get("latency_ms"),
        }
        structured = reply.get("structured_output") if answered and route == SCHEMA else None
        if row["asks"] == BATCH:
            row["documents"] = _documents(prompt)
            row["grades"] = _grades(structured if route == SCHEMA else _json(text))
        elif row["asks"] == DOCUMENT and route == SCHEMA:
            relevant = structured.get("relevant") if isinstance(structured, dict) else None
            row["relevant"] = relevant if isinstance(relevant, bool) else None
        elif row["asks"] == DOCUMENT:
            row["yes"] = isinstance(text, str) and text.strip().upper().startswith("YES")
        rows.append(row)
    rows.sort(key=lambda row: (row["asks"], row["route"], row["prompt_sha256"], dump(row)))
    manifest = cache.parent / "manifest.json"
    return {
        "version": VERSION,
        "run_manifest_sha256": (
            hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() else None
        ),
        "models": [
            json.loads(identity)
            for identity in sorted({dump(entry["request"]["identity"]) for entry in entries})
        ],
        "rows": rows,
    }


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def write(document: Mapping[str, Any]) -> str:
    """The file: a header and one row a line, so that two files compare line by line."""
    head = {key: value for key, value in document.items() if key != "rows"}
    lines = [dump(head)[:-1] + ', "rows": [']
    lines += [dump(row) + "," for row in document["rows"][:-1]]
    lines += [dump(row) for row in document["rows"][-1:]]
    return "\n".join([*lines, "]}"]) + "\n"


def _by(rows: Sequence[Mapping[str, Any]], asks: str, route: str) -> dict[str, Mapping[str, Any]]:
    return {
        row["prompt_sha256"]: row for row in rows if row["asks"] == asks and row["route"] == route
    }


def verdicts(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Every document the run graded on its own: kept or not, and the route that said so."""
    again = _by(rows, DOCUMENT, TEXT)
    found = {}
    for prompt, row in _by(rows, DOCUMENT, SCHEMA).items():
        if isinstance(row["relevant"], bool):
            found[prompt] = {"kept": row["relevant"], "route": SCHEMA}
        elif prompt in again:
            found[prompt] = {"kept": bool(again[prompt]["yes"]), "route": TEXT}
        else:
            # The product drops a document whose grading failed (fail-closed).
            found[prompt] = {"kept": False, "route": None}
    return found


def summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Counts of one run: what was asked on which route, and what the grading got back."""
    batches = _by(rows, BATCH, SCHEMA)
    batches_again = _by(rows, BATCH, TEXT)
    documents = _by(rows, DOCUMENT, SCHEMA)
    graded = verdicts(rows)

    def enough(row: Mapping[str, Any] | None) -> bool:
        return row is not None and row["grades"] == row["documents"]

    def by_grades(found: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
        counted = Counter(
            "none" if row["grades"] is None else str(row["grades"]) for row in found.values()
        )
        return dict(sorted(counted.items()))

    seconds: Counter[str] = Counter()
    for row in rows:
        seconds[f"{row['asks']}/{row['route']}"] += (row["latency_ms"] or 0) / 1000
    return {
        "requests": dict(sorted(Counter(f"{row['asks']}/{row['route']}" for row in rows).items())),
        "seconds": {name: round(value, 1) for name, value in sorted(seconds.items())},
        "options": {
            route: sorted({dump(row["options"]) for row in rows if row["route"] == route})
            for route in (SCHEMA, TEXT)
        },
        "batches": len(batches),
        "batches_asked_again_as_text": sum(prompt in batches_again for prompt in batches),
        "batch_documents": sum(row["documents"] for row in batches.values()),
        "batch_documents_by_count": dict(
            sorted(Counter(str(row["documents"]) for row in batches.values()).items())
        ),
        "batch_replies_by_grades": {
            SCHEMA: by_grades(batches),
            TEXT: by_grades(batches_again),
        },
        "batches_with_a_grade_a_document": sum(
            enough(row) or enough(batches_again.get(prompt)) for prompt, row in batches.items()
        ),
        "documents_asked_one_by_one": len(documents),
        "documents_with_a_structured_verdict": sum(
            isinstance(row["relevant"], bool) for row in documents.values()
        ),
        "documents_asked_again_as_text": sum(v["route"] == TEXT for v in graded.values()),
        "documents_kept": sum(v["kept"] for v in graded.values()),
        "documents_dropped": sum(not v["kept"] for v in graded.values()),
    }


def compare(
    first: Sequence[Mapping[str, Any]], second: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Requests two runs share, replies that repeat, and documents graded differently."""
    requests = []
    for asks in (BATCH, DOCUMENT, OTHER):
        for route in (SCHEMA, TEXT):
            one, two = _by(first, asks, route), _by(second, asks, route)
            shared = [prompt for prompt in one if prompt in two]
            if not one and not two:
                continue
            requests.append(
                {
                    "asks": asks,
                    "route": route,
                    "first": len(one),
                    "second": len(two),
                    "shared": len(shared),
                    "same_reply": sum(
                        one[prompt]["reply_sha256"] == two[prompt]["reply_sha256"]
                        for prompt in shared
                    ),
                    "same_options": sum(
                        one[prompt]["options"] == two[prompt]["options"] for prompt in shared
                    ),
                }
            )
    one, two = verdicts(first), verdicts(second)
    shared = [prompt for prompt in one if prompt in two]
    routes = Counter(
        (
            "same" if one[p]["kept"] == two[p]["kept"] else "first" if one[p]["kept"] else "second",
            str(one[p]["route"]),
            str(two[p]["route"]),
        )
        for p in shared
    )
    return {
        "requests": requests,
        "documents": {
            "shared": len(shared),
            "same_verdict": sum(one[p]["kept"] == two[p]["kept"] for p in shared),
            "kept_by_the_first_only": sum(one[p]["kept"] and not two[p]["kept"] for p in shared),
            "kept_by_the_second_only": sum(two[p]["kept"] and not one[p]["kept"] for p in shared),
            "kept_by_the_first": sum(one[p]["kept"] for p in shared),
            "kept_by_the_second": sum(two[p]["kept"] for p in shared),
            "by_route": [
                {"verdict": verdict, "first_route": a, "second_route": b, "documents": count}
                for (verdict, a, b), count in sorted(routes.items())
            ],
        },
    }


def read(path: Path) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("version") != VERSION:
        raise ValueError(f"{path}: not a file of {VERSION}")
    rows: list[dict[str, Any]] = document["rows"]
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    extracting = commands.add_parser("extract")
    extracting.add_argument("--cache", type=Path, required=True)
    extracting.add_argument("--out", type=Path)
    counting = commands.add_parser("summary")
    counting.add_argument("--file", type=Path, required=True)
    comparing = commands.add_parser("compare")
    comparing.add_argument("--first", type=Path, required=True)
    comparing.add_argument("--second", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "extract":
        text = write(extract(args.cache))
        if args.out is None:
            sys.stdout.write(text)
        else:
            args.out.write_text(text, encoding="utf-8", newline="\n")
        return 0
    if args.command == "summary":
        print(json.dumps(summary(read(args.file)), indent=1, sort_keys=True))
        return 0
    print(json.dumps(compare(read(args.first), read(args.second)), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
