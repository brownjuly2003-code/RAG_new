"""Quiescent copy admission; inventory is standalone Python 3 (stdlib only).

Private config, schema_version=1:
  private_data_root: absolute directory containing the three base directories
  bases: {<key>: {inventory: absolute source-inventory JSON}}
  private_inputs: {stage5_runs, stage5_aircargo_runs, attempt02_runs,
                   attempt02_journals: {root: absolute directory, inventory: absolute JSON}}
The two stage5 roots directly contain final-answers-<key>-bNN directories.
The attempt02 runs root contains <key>/runs/final-answers-<key>-bNN.
Additional private input trees (e.g. installed assets) use the same format.
Inventory output MUST be outside its input tree. No source paths are published.
Verify uses canonical repository pins, never .cx_inputs or replacement data.
Only verify imports Chroma, after ALL copies and logical metadata pass; it does
not instantiate an embedder, query, rebuild, or create a collection.
"""

from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import math
import os
import re
import stat
import sys
import unicodedata
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

KEYS = ("wixqa", "conditionalqa", "aircargo")
PRIVATE_INPUTS = ("stage5_runs", "stage5_aircargo_runs", "attempt02_runs", "attempt02_journals")
SOURCE_FILES = ("corpus.manifest.json", "chunks-report.json", "index/index-receipt.json")
STAGE5_RECORD = "reports/stage4-final/stage5/2057ad0/record.json"
AIRCARGO_ANSWERS = "reports/stage4-final/138f3b3/final-answers.json"
AIRCARGO_GENERATION = "reports/stage4-step5a-live/tools/live5a_reader.py"
COPY_INSTRUMENTS = (
    "docs/specs/generator-ceiling.md",
    "reports/stage7/tools/arms_replay.py",
    "evaluation/external_bases.json",
    STAGE5_RECORD,
    AIRCARGO_ANSWERS,
    AIRCARGO_GENERATION,
)
# Repeated .parent also works for a standalone copy in a shallow directory.
ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCHEMA = 1


class Refusal(ValueError):
    """Public, data-free reason for exit 1."""


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise Refusal("invalid command arguments")


def require(ok: Any, reason: str) -> None:
    if not ok:
        raise Refusal(reason)


def digest(value: bytes | str) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def sha(path: Path) -> str:
    require(stat.S_ISREG(path.lstat().st_mode), "regular file required")
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def decode(raw: bytes) -> Any:
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)


def read(path: Path) -> Any:
    return decode(path.read_bytes())


def rows(path: Path) -> list[dict[str, Any]]:
    return [decode(line) for line in path.read_bytes().splitlines() if line.strip()]


def encoded(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    require(not temporary.exists() and not temporary.is_symlink(), "output temporary exists")
    with temporary.open("xb") as stream:
        stream.write(encoded(value))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def literal(node: ast.AST) -> Any:
    """Read data assignments without executing source or using eval/literal_eval."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        values = [literal(item) for item in node.elts]
        return tuple(values) if isinstance(node, ast.Tuple) else values
    if isinstance(node, ast.Dict):
        require(all(key is not None for key in node.keys), "unpacked registered constant")
        return unique_object(
            [
                (literal(k), literal(v))
                for k, v in zip(node.keys, node.values, strict=True)
                if k is not None
            ]
        )
    raise Refusal("nonliteral registered constant")


def constant(path: Path, name: str) -> Any:
    values = []
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == name for t in targets):
                if node.value is None:
                    raise Refusal("constant has no value")
                values.append(literal(node.value))
    require(len(values) == 1, "registered constant absent or ambiguous")
    return values[0]


def relative(name: str) -> str:
    path = PurePosixPath(name)
    require(
        bool(name)
        and bool(path.parts)
        and not path.is_absolute()
        and path.as_posix() == name
        and not any(p in (".", "..") for p in path.parts)
        and "\\" not in name
        and ":" not in name,
        "unsafe relative path",
    )
    return name


def absolute(value: str) -> Path:
    path = Path(value)
    require(path.is_absolute(), "absolute private path required")
    return path


def no_links(path: Path) -> None:
    for part in (path, *path.parents):
        info = part.lstat()
        require(
            not stat.S_ISLNK(info.st_mode)
            and not (
                getattr(info, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            ),
            "symlink or reparse point refused",
        )


def tree_files(root: Path) -> list[dict[str, Any]]:
    no_links(root)
    require(root.is_dir(), "input directory missing")
    result = []
    stack = [root]
    while stack:
        for path in stack.pop().iterdir():
            info = path.lstat()
            require(
                not stat.S_ISLNK(info.st_mode)
                and not (
                    getattr(info, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                ),
                "symlink or reparse point refused",
            )
            if stat.S_ISDIR(info.st_mode):
                stack.append(path)
            else:
                require(stat.S_ISREG(info.st_mode), "special file refused")
                name = relative(path.relative_to(root).as_posix())
                hashed = sha(path)
                after = path.stat()
                require(
                    (info.st_size, info.st_mtime_ns, info.st_ino)
                    == (after.st_size, after.st_mtime_ns, after.st_ino),
                    "input changed during hashing",
                )
                result.append({"path": name, "size": info.st_size, "sha256": hashed})
    return sorted(result, key=lambda item: item["path"])


def inventory(root: Path) -> dict[str, Any]:
    return {"schema_version": SCHEMA, "tool_sha256": sha(Path(__file__)), "files": tree_files(root)}


def inventory_entries(value: dict[str, Any]) -> list[dict[str, Any]]:
    require(
        value.get("schema_version") == SCHEMA and value.get("tool_sha256") == sha(Path(__file__)),
        "inventory tool/schema mismatch",
    )
    files = value["files"]
    require(isinstance(files, list), "invalid inventory files")
    names = []
    for row in files:
        require(set(row) == {"path", "size", "sha256"}, "invalid inventory entry")
        names.append(relative(row["path"]))
        require(
            type(row["size"]) is int
            and row["size"] >= 0
            and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]),
            "invalid inventory hash/size",
        )
    require(names == sorted(set(names)), "inventory order/duplicates refused")
    return files


def public_tree(files: list[dict[str, Any]]) -> dict[str, Any]:
    return {digest(r["path"]): {"size": r["size"], "sha256": r["sha256"]} for r in files}


def old_export(key: str) -> str:
    return (
        f"reports/stage4-final/stage5/2057ad0/stage5-{key}-m1.json"
        if key != "aircargo"
        else "reports/stage4-final/138f3b3/final-aircargo-m1.json"
    )


def historical_pins(repo: Path) -> dict[str, str]:
    text = (repo / "docs/specs/generator-ceiling.md").read_text(encoding="utf-8")
    pairs = re.findall(r"^- `([^`]+)` `([0-9a-f]{64})`", text, re.M)
    require(bool(pairs), "historical SHA-256 registration absent")
    return unique_object(pairs)


def pinned(repo: Path, name: str, pins: dict[str, str]) -> Path:
    path = repo / relative(name)
    require(name in pins and sha(path) == pins[name], "historical file pin mismatch")
    return path


def input_trees(config: dict[str, Any]) -> dict[str, tuple[Path, Path]]:
    require(
        config.get("schema_version") == SCHEMA and set(config["bases"]) == set(KEYS),
        "copy config schema/keys differ",
    )
    root = absolute(config["private_data_root"])
    result = {key: (root / key, absolute(config["bases"][key]["inventory"])) for key in KEYS}
    inputs = config["private_inputs"]
    require(set(PRIVATE_INPUTS) <= set(inputs), "private input inventories missing")
    for name, item in inputs.items():
        require(re.fullmatch(r"[a-z0-9_]+", name) and name not in result, "invalid input label")
        result[name] = (absolute(item["root"]), absolute(item["inventory"]))
    for name, (folder, inv) in result.items():
        require(not inv.resolve().is_relative_to(folder.resolve()), "inventory is inside input")
        for other, (target, _) in result.items():
            require(
                name == other or not folder.resolve().is_relative_to(target.resolve()),
                "input trees overlap",
            )
    return result


def logical_metadata(repo: Path, key: str, folder: Path) -> tuple[dict[str, Any], list[Any]]:
    """All non-database gates run before ANY Chroma client is opened."""
    pins = historical_pins(repo)
    if key == "aircargo":
        historical = read(repo / AIRCARGO_ANSWERS)
        evidence = {AIRCARGO_ANSWERS: sha(repo / AIRCARGO_ANSWERS)}
        evidence[AIRCARGO_GENERATION] = sha(repo / AIRCARGO_GENERATION)
    else:
        historical = read(pinned(repo, STAGE5_RECORD, pins))["corpora"][key]["answers"]
        evidence = {STAGE5_RECORD: sha(repo / STAGE5_RECORD)}
    provenance = historical["provenance"]
    require(
        historical["status"] == "counted"
        and historical["base"] == key
        and provenance["code_sha"].startswith("138f3b3" if key == "aircargo" else "2057ad0"),
        "stage 5 answer provenance mismatch",
    )
    generation = {name: sha(folder / name) for name in SOURCE_FILES}
    require(provenance["corpus_sha256"] == generation, "stage 5 generation mismatch")
    if key == "aircargo":
        require(
            generation == constant(repo / AIRCARGO_GENERATION, "CORPUS_SHA256"),
            "aircargo frozen generation mismatch",
        )
    archive_sha = sha(folder / "chunks.json.gz")
    archives = constant(repo / "reports/stage7/tools/arms_replay.py", "ARCHIVES")
    require(archive_sha == archives[key], "stage 5 chunk archive mismatch")
    manifest = read(folder / "corpus.manifest.json")
    require(manifest["schema_version"] == 1, "corpus manifest schema mismatch")
    entries = manifest["files"]
    names = [r["name"] for r in entries]
    require(names == sorted(set(names)), "corpus manifest duplicate/order mismatch")
    actual = [
        {"name": unicodedata.normalize("NFC", r["path"]), "bytes": r["size"], "sha256": r["sha256"]}
        for r in tree_files(folder / "corpus")
        # corpus_manifest.py uses only non-hidden immediate files. The whole-tree
        # inventory above still covers hidden files and subdirectories in full.
        if not r["path"].startswith(".") and "/" not in r["path"]
    ]
    actual.sort(key=lambda r: r["name"])
    require(actual == entries and len(actual) == manifest["file_count"], "corpus manifest mismatch")
    require(
        digest("".join(f"{r['name']} {r['sha256']}\n" for r in entries))
        == manifest["corpus_sha256"],
        "corpus aggregate mismatch",
    )
    cases = (
        repo / "evaluation/curated_cases_aircargo.jsonl"
        if key == "aircargo"
        else folder / "cases.jsonl"
    )
    require(sha(cases) == provenance["cases_sha256"], "stage 5 cases mismatch")
    case_rows = rows(cases)
    require(len({r["case_id"] for r in case_rows}) == len(case_rows) > 0, "case ids invalid")
    if key != "aircargo":
        converted = read(repo / "evaluation/external_bases.json")["bases"][key]["converted"]
        require(
            sha(cases) == converted["cases_sha256"]
            and len(case_rows) == converted["cases"]
            and manifest["corpus_sha256"] == converted["corpus_sha256"]
            and manifest["file_count"] == converted["documents"],
            "converted base mismatch",
        )
    payload_raw = gzip.decompress((folder / "chunks.json.gz").read_bytes())
    payload = decode(payload_raw)
    chunks = payload["chunks"]
    report = read(folder / "chunks-report.json")
    receipt = read(folder / "index/index-receipt.json")
    tenant = "aircargo" if key == "aircargo" else "ext_" + key
    collection = "rag_docs_" + tenant
    require(payload["tenant_id"] == report["tenant"] == tenant, "tenant mismatch")
    require(report["collection"] == receipt["collection_name"] == collection, "collection mismatch")
    require(
        report["corpus_sha256"] == manifest["corpus_sha256"]
        and report["archive_sha256"] == receipt["corpus_sha256"] == archive_sha
        and report["payload_sha256"] == digest(payload_raw)
        and report["archive_bytes"] == (folder / "chunks.json.gz").stat().st_size
        and report["documents"] == manifest["file_count"]
        and report["chunks"] == receipt["chunk_count"] == len(chunks) > 0,
        "chunk/index receipt mismatch",
    )
    texts = hashlib.sha256()
    for chunk in chunks:
        raw = chunk["page_content"].encode("utf-8")
        texts.update(len(raw).to_bytes(8, "big"))
        texts.update(raw)
        require(chunk["metadata"]["source"] in names, "chunk source missing")
    require(
        texts.hexdigest() == receipt["texts_sha256"] and receipt["schema_version"] == 1,
        "index texts/schema mismatch",
    )
    embedding = receipt["embedder_manifest"]
    require(
        embedding["backend"] == "local"
        and embedding["revision_source"] == "hf_snapshot"
        and re.fullmatch(r"[0-9a-f]{40}", embedding["revision"])
        and embedding["normalize"] is True
        and type(embedding["dimension"]) is int
        and embedding["dimension"] > 0
        and embedding["schema_version"] == 1,
        "embedding manifest mismatch",
    )
    require((folder / "index/chroma/chroma.sqlite3").is_file(), "existing index missing")
    return {
        "passed": True,
        "generation": generation,
        "evidence_sha256": evidence,
        "archive_sha256": archive_sha,
        "cases_sha256": sha(cases),
        "cases": len(case_rows),
        "chunk_count": len(chunks),
        "tenant_sha256": digest(tenant),
        "collection_sha256": digest(collection),
        "embedding_sha256": digest(encoded(embedding)),
    }, chunks


def check_collection(folder: Path, chunks: list[Any]) -> dict[str, Any]:
    import chromadb
    from chromadb.config import Settings

    receipt = read(folder / "index/index-receipt.json")
    require(chromadb.__version__ == receipt["chromadb_version"], "Chroma version mismatch")
    client = chromadb.PersistentClient(
        path=str(folder / "index/chroma"),
        settings=Settings(anonymized_telemetry=False, allow_reset=False),
    )
    collection = client.get_collection(receipt["collection_name"], embedding_function=None)
    require(collection.count() == len(chunks), "collection count mismatch")
    require(
        decode((collection.metadata or {})["embedder_manifest"].encode())
        == receipt["embedder_manifest"],
        "collection embedding manifest mismatch",
    )
    dimension = receipt["embedder_manifest"]["dimension"]
    for start in range(0, len(chunks), 256):
        wanted = {f"chunk-{i:08d}": i for i in range(start, min(start + 256, len(chunks)))}
        found = collection.get(ids=list(wanted), include=["documents", "metadatas", "embeddings"])
        require(
            set(found["ids"]) == set(wanted) and len(found["ids"]) == len(wanted),
            "collection ids mismatch",
        )
        for pos, ident in enumerate(found["ids"]):
            index = wanted[ident]
            require(
                found["documents"][pos] == chunks[index]["page_content"]
                and found["metadatas"][pos] == dict(chunks[index]["metadata"], chunk_index=index),
                "collection contents mismatch",
            )
            vector = found["embeddings"][pos]
            require(
                len(vector) == dimension
                and all(math.isfinite(v) for v in vector)
                and abs(math.sqrt(sum(float(v) ** 2 for v in vector)) - 1) <= 1e-4,
                "collection embedding values mismatch",
            )
    return {"passed": True, "count": len(chunks)}


def verify(
    config_path: Path,
    repo: Path = ROOT,
    *,
    collection_reader: Callable[..., dict[str, Any]] = check_collection,
) -> dict[str, Any]:
    config_bytes = config_path.read_bytes()
    config = decode(config_bytes)
    trees = input_trees(config)
    admitted: dict[str, Any] = {}
    # Complete the byte gates for every input before doing any logical/index read.
    for name, (folder, inv) in trees.items():
        require(
            not folder.resolve().is_relative_to(repo.resolve())
            and not repo.resolve().is_relative_to(folder.resolve()),
            "private input overlaps repository",
        )
        expected = inventory_entries(read(inv))
        actual = tree_files(folder)
        require(actual == expected and bool(actual), "whole-tree inventory mismatch: " + name)
        admitted[name] = {
            "root_sha256": digest(str(folder.resolve())),
            "inventory_sha256": sha(inv),
            "pre": public_tree(actual),
            "post": public_tree(actual),
        }
    logical: dict[str, Any] = {}
    chunks_by_key = {}
    for key in KEYS:
        logical[key], chunks_by_key[key] = logical_metadata(repo, key, trees[key][0])
    instruments = {name: sha(repo / name) for name in COPY_INSTRUMENTS}
    for key in KEYS:
        logical[key]["collection"] = collection_reader(trees[key][0], chunks_by_key[key])
        require(logical[key]["collection"]["passed"] is True, "collection check refused")
    for name, (folder, _) in trees.items():
        after = tree_files(folder)
        admitted[name]["post"] = public_tree(after)
        before = admitted[name]["pre"]
        if name in KEYS:
            # Chroma may update its runtime files; only those changes are recorded.
            chroma_hashes = {
                digest(r["path"]) for r in after if r["path"].startswith("index/chroma/")
            }
            chroma_hashes |= {
                digest(r["path"])
                for r in inventory_entries(read(trees[name][1]))
                if r["path"].startswith("index/chroma/")
            }
            require(
                {k: v for k, v in before.items() if k not in chroma_hashes}
                == {k: v for k, v in admitted[name]["post"].items() if k not in chroma_hashes},
                "non-index input changed during verification",
            )
        else:
            require(before == admitted[name]["post"], "private input changed during verification")
    require(sha(config_path) == digest(config_bytes), "config changed during verification")
    require(
        instruments == {name: sha(repo / name) for name in COPY_INSTRUMENTS},
        "copy instruments changed during verification",
    )
    return {
        "schema_version": SCHEMA,
        "passed": True,
        "config_sha256": digest(config_bytes),
        "tool_sha256": sha(Path(__file__)),
        "instruments": instruments,
        "trees": admitted,
        "logical": logical,
    }


def admit_receipt(config_path: Path, repo: Path = ROOT, *, runtime: bool = False) -> dict[str, Any]:
    """Registration checks whole trees; request chunks allow Chroma bookkeeping.

    Runtime callers must additionally run logical_metadata/check_collection for
    every base. Immutable private input trees remain pinned in both modes.
    """
    config = read(config_path)
    receipt = read(absolute(config["copy_receipt"]))
    require(
        receipt.get("passed") is True
        and receipt.get("schema_version") == SCHEMA
        and receipt.get("config_sha256") == sha(config_path)
        and receipt.get("tool_sha256") == sha(Path(__file__)),
        "copy receipt refused",
    )
    require(
        receipt["instruments"] == {name: sha(repo / name) for name in COPY_INSTRUMENTS},
        "copy instrument receipt is stale",
    )
    trees = input_trees(config)
    require(
        set(receipt["trees"]) == set(trees) and set(receipt["logical"]) == set(KEYS),
        "copy receipt inputs differ",
    )
    for name, (folder, inv) in trees.items():
        held = receipt["trees"][name]
        require(
            held["root_sha256"] == digest(str(folder.resolve()))
            and held["inventory_sha256"] == sha(inv)
            and held["pre"] == public_tree(inventory_entries(read(inv)))
            and (runtime and name in KEYS or held["post"] == public_tree(tree_files(folder))),
            "copy receipt is stale",
        )
    for key in KEYS:
        require(
            receipt["logical"][key]["passed"] is True
            and receipt["logical"][key]["collection"]["passed"] is True
            and receipt["logical"][key]["collection"]["count"]
            == receipt["logical"][key]["chunk_count"],
            "copy logical receipt refused",
        )
    return receipt


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    # Also accept the spec's original spelling: copy_verify.py --config ... --out ...
    if args_list and args_list[0].startswith("--") and args_list[0] != "--help":
        args_list.insert(0, "verify")
    parser = Parser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--root", type=Path, required=True)
    inv.add_argument("--out", type=Path, required=True)
    check = sub.add_parser("verify")
    check.add_argument("--config", type=Path, required=True)
    check.add_argument("--out", type=Path, required=True)
    try:
        # argparse's successful --help exit is kept outside the evidence handler.
        args = parser.parse_args(args_list)
    except Refusal:
        print("copy admission refused (invalid command arguments)", file=sys.stderr)
        return 1
    try:
        if args.command == "inventory":
            require(
                not args.out.resolve().is_relative_to(args.root.resolve()),
                "inventory output overlaps input",
            )
            result = inventory(args.root)
        else:
            config = read(args.config)
            for folder, inv_path in input_trees(config).values():
                require(
                    not args.out.resolve().is_relative_to(folder.resolve())
                    and args.out.resolve() != inv_path.resolve(),
                    "receipt output overlaps input",
                )
            require(args.out.resolve() != args.config.resolve(), "receipt overwrites config")
            result = verify(args.config)
        write(args.out, result)
    except (Exception, SystemExit):
        # Never expose an exception containing a private filename or text.
        print("copy admission refused (missing, changed or invalid evidence)", file=sys.stderr)
        return 1
    print("copy inventory written" if args.command == "inventory" else "copy admission passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
