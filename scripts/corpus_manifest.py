"""Build and verify a git-checked-in manifest of a measured corpus.

A published number names this digest. Re-deriving it depends on six rules,
which are therefore written down here rather than left as an implementation
detail:

- File content is hashed as raw bytes (binary mode), never text mode. This
  machine is Windows and the corpus came from macOS; text mode would
  translate line endings and change the digest.
- Entries are sorted by name with a plain byte/codepoint sort, not a locale
  one.
- The aggregate ``corpus_sha256`` is SHA-256 over the concatenation of
  ``"<name> <sha256>\\n"`` lines in that sorted order.
- Hidden files (names starting with ``.``) are not corpus entries. A macOS
  re-copy that drops ``.DS_Store`` must not move the published digest.
- File names are normalised to Unicode NFC before hashing and comparison.
  macOS returns directory entries in NFD; Windows and Linux store whatever
  was written (usually NFC). The same document must not produce two
  digests because of that.
- Only regular files directly in ``--root`` are corpus entries;
  subdirectories are not walked.

The stored ``root`` is a repo-relative POSIX path when the corpus sits under
the project. When it does not, the field is the stable placeholder
``<external>`` — never an absolute path — so two machines building the same
bytes produce a byte-identical manifest.

    python scripts/corpus_manifest.py build --root data/uploads/aircargo \\
        --name aircargo --out evaluation/aircargo_corpus.manifest.json
    python scripts/corpus_manifest.py verify --manifest \\
        evaluation/aircargo_corpus.manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = 1
EXTERNAL_ROOT = "<external>"
_CHUNK_SIZE = 1024 * 1024
_REQUIRED_MANIFEST_KEYS = ("root", "file_count", "corpus_sha256", "files")


class FileRecord(TypedDict):
    name: str
    sha256: str
    bytes: int


class CorpusManifest(TypedDict):
    schema_version: int
    name: str
    root: str
    file_count: int
    corpus_sha256: str
    files: list[FileRecord]


@dataclass(frozen=True, slots=True)
class CorpusDiff:
    changed: tuple[str, ...]
    missing: tuple[str, ...]
    extra: tuple[str, ...]

    def ok(self) -> bool:
        return not (self.changed or self.missing or self.extra)


def _open_binary(path: Path):
    return path.open("rb")


def hash_file(path: Path) -> tuple[str, int]:
    """Return ``(sha256 hex, size)`` of ``path`` read as raw bytes."""
    digest = hashlib.sha256()
    size = 0
    with _open_binary(path) as handle:
        while True:
            chunk = handle.read(_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def entry_name(path: Path) -> str:
    """Return the NFC-normalised file name used in the digest and in comparisons."""
    return unicodedata.normalize("NFC", path.name)


def list_corpus_files(root: Path) -> tuple[list[Path], int]:
    """Return ``(regular non-hidden files, count of leading-dot entries)``.

    Names starting with ``.`` are skipped whether they are files or directories.
    Non-hidden subdirectories are not walked and are not counted as skipped.
    """
    if not root.is_dir():
        return [], 0
    files: list[Path] = []
    skipped = 0
    for path in root.iterdir():
        if path.name.startswith("."):
            skipped += 1
            continue
        if path.is_file():
            files.append(path)
    files.sort(key=entry_name)
    return files, skipped


def stored_root(root: Path, *, project_root: Path = PROJECT_ROOT) -> str:
    resolved = root.resolve()
    project = project_root.resolve()
    if resolved.is_relative_to(project):
        return resolved.relative_to(project).as_posix()
    return EXTERNAL_ROOT


def aggregate_digest(files: Sequence[Mapping[str, object]]) -> str:
    payload = "".join(f"{entry['name']} {entry['sha256']}\n" for entry in files)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_manifest(root: Path, *, name: str, project_root: Path = PROJECT_ROOT) -> CorpusManifest:
    records: list[FileRecord] = []
    files, _skipped = list_corpus_files(root)
    for path in files:
        digest, size = hash_file(path)
        records.append({"name": entry_name(path), "sha256": digest, "bytes": size})
    records.sort(key=lambda record: record["name"])
    return {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "root": stored_root(root, project_root=project_root),
        "file_count": len(records),
        "corpus_sha256": aggregate_digest(records),
        "files": records,
    }


def dumps_manifest(manifest: Mapping[str, object]) -> bytes:
    text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return text.encode("utf-8")


def write_manifest(path: Path, manifest: Mapping[str, object]) -> None:
    path.write_bytes(dumps_manifest(manifest))


def load_manifest(path: Path) -> CorpusManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"unsupported or malformed manifest: {path}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported or malformed manifest: {path}")
    if any(key not in payload for key in _REQUIRED_MANIFEST_KEYS):
        raise ValueError(f"unsupported or malformed manifest: {path}")
    if not isinstance(payload["files"], list):
        raise ValueError(f"unsupported or malformed manifest: {path}")
    return cast(CorpusManifest, payload)


def resolve_corpus_root(
    manifest: Mapping[str, object],
    root: Path | None,
    *,
    project_root: Path = PROJECT_ROOT,
) -> Path:
    if root is not None:
        return root
    stored = str(manifest["root"])
    if stored == EXTERNAL_ROOT or Path(stored).is_absolute():
        raise ValueError(
            "manifest root is not repo-relative; pass --root to the local corpus directory"
        )
    return project_root / stored


def diff_corpus(manifest: Mapping[str, object], root: Path) -> CorpusDiff:
    expected = {entry["name"]: entry for entry in manifest["files"]}
    files, _skipped = list_corpus_files(root)
    actual_records = {}
    for path in files:
        name = entry_name(path)
        actual_records[name] = {"name": name, "sha256": hash_file(path)[0]}
    missing = tuple(sorted(name for name in expected if name not in actual_records))
    extra = tuple(sorted(name for name in actual_records if name not in expected))
    changed = tuple(
        sorted(
            name
            for name in expected.keys() & actual_records.keys()
            if actual_records[name]["sha256"] != expected[name]["sha256"]
        )
    )
    return CorpusDiff(changed=changed, missing=missing, extra=extra)


def format_diff(diff: CorpusDiff) -> str:
    lines: list[str] = []
    for group, names in (
        ("changed", diff.changed),
        ("missing", diff.missing),
        ("extra", diff.extra),
    ):
        lines.append(f"{group}:")
        lines.extend(f"  {name}" for name in names)
    return "\n".join(lines) + "\n"


def _success_line(manifest: Mapping[str, object], skipped: int) -> str:
    return (
        f"{manifest['corpus_sha256']}  {manifest['file_count']} "
        f"(skipped {skipped} hidden entries)"
    )


def command_build(args: argparse.Namespace) -> int:
    root = Path(args.root)
    if not root.is_dir():
        print(f"corpus root is not a directory: {root}", file=sys.stderr)
        return 1
    manifest = build_manifest(root, name=args.name)
    if manifest["file_count"] == 0:
        print(
            f"no corpus files under {root} "
            "(hidden files and subdirectories are not corpus entries)",
            file=sys.stderr,
        )
        return 1
    write_manifest(Path(args.out), manifest)
    _files, skipped = list_corpus_files(root)
    print(_success_line(manifest, skipped))
    return 0


def command_verify(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    if not manifest_path.is_file():
        print(f"missing manifest: {manifest_path}", file=sys.stderr)
        return 1
    try:
        manifest = load_manifest(manifest_path)
        root = resolve_corpus_root(
            manifest, Path(args.root) if args.root is not None else None
        )
    except (ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"corpus root is not a directory: {root}", file=sys.stderr)
        return 1
    diff = diff_corpus(manifest, root)
    if not diff.ok():
        print(format_diff(diff), end="")
        return 1
    _files, skipped = list_corpus_files(root)
    print(_success_line(manifest, skipped))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="write a reproducible corpus manifest")
    build.add_argument("--root", required=True, help="corpus directory")
    build.add_argument("--name", required=True, help="corpus name stored in the manifest")
    build.add_argument("--out", required=True, help="manifest path to write")

    verify = subparsers.add_parser(
        "verify", help="check a local corpus directory against a manifest"
    )
    verify.add_argument("--manifest", required=True, help="checked-in manifest")
    verify.add_argument(
        "--root",
        default=None,
        help="corpus directory (defaults to the root recorded in the manifest)",
    )

    args = parser.parse_args(argv)
    handlers = {"build": command_build, "verify": command_verify}
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
