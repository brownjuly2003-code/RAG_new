"""The corpus a published number was measured over must be re-identifiable from git.

The 201 documents live outside git (``data/*`` is ignored). What git holds is
the manifest: every file's name and SHA-256, plus an aggregate digest. These
tests pin the rules that digest depends on, and the verify command that names
drift instead of only reporting that the aggregate moved.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path

import pytest

from scripts import corpus_manifest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "evaluation" / "aircargo_corpus.manifest.json"
CORPUS_PATH = PROJECT_ROOT / "data" / "uploads" / "aircargo"

_GROUP_HEADERS = ("changed:", "missing:", "extra:")


def _build(root: Path, out: Path, *, name: str = "fixture") -> int:
    return corpus_manifest.main(
        ["build", "--root", str(root), "--name", name, "--out", str(out)]
    )


def _verify(manifest: Path, root: Path) -> int:
    return corpus_manifest.main(
        ["verify", "--manifest", str(manifest), "--root", str(root)]
    )


def _write_files(root: Path, files: list[tuple[str, bytes]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, payload in files:
        (root / name).write_bytes(payload)


def _names_under(text: str, group: str) -> list[str]:
    header = f"{group}:"
    names: list[str] = []
    in_group = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in _GROUP_HEADERS:
            in_group = stripped == header
            continue
        if in_group and stripped:
            names.append(stripped)
    return names


def test_build_is_byte_identical_across_two_runs(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    _write_files(
        root,
        [("b.md", b"bravo"), ("a.md", b"alpha"), ("c.md", b"charlie")],
    )
    first = tmp_path / "one.json"
    second = tmp_path / "two.json"

    assert _build(root, first) == 0
    assert _build(root, second) == 0

    assert first.read_bytes() == second.read_bytes()
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert set(payload) == {
        "corpus_sha256",
        "file_count",
        "files",
        "name",
        "root",
        "schema_version",
    }
    assert "created" not in payload
    assert "timestamp" not in payload
    assert "host" not in payload


def test_aggregate_digest_ignores_creation_order_and_hashes_crlf_as_bytes(
    tmp_path: Path,
) -> None:
    crlf = b"hello\r\nwindows\r\n"
    lf_normalised = crlf.replace(b"\r\n", b"\n")
    assert crlf != lf_normalised

    first = tmp_path / "created-z-first"
    second = tmp_path / "created-a-first"
    _write_files(
        first,
        [("z.md", b"zzz"), ("crlf.bin", crlf), ("a.md", b"aaa")],
    )
    _write_files(
        second,
        [("a.md", b"aaa"), ("crlf.bin", crlf), ("z.md", b"zzz")],
    )

    out_first = tmp_path / "first.json"
    out_second = tmp_path / "second.json"
    assert _build(first, out_first) == 0
    assert _build(second, out_second) == 0

    payload_first = json.loads(out_first.read_text(encoding="utf-8"))
    payload_second = json.loads(out_second.read_text(encoding="utf-8"))
    assert payload_first["corpus_sha256"] == payload_second["corpus_sha256"]
    assert [entry["name"] for entry in payload_first["files"]] == [
        "a.md",
        "crlf.bin",
        "z.md",
    ]

    crlf_entry = next(
        entry for entry in payload_first["files"] if entry["name"] == "crlf.bin"
    )
    raw_digest = hashlib.sha256(crlf).hexdigest()
    text_mode_digest = hashlib.sha256(lf_normalised).hexdigest()
    assert crlf_entry["sha256"] == raw_digest
    assert crlf_entry["sha256"] != text_mode_digest
    assert crlf_entry["bytes"] == len(crlf)
    assert hashlib.sha256((first / "crlf.bin").read_bytes()).hexdigest() == raw_digest


def test_verify_accepts_an_unchanged_fixture_corpus(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """FALSE-REJECT CONTROL: a corpus that still matches the manifest is accepted."""
    root = tmp_path / "corpus"
    _write_files(root, [("keep.md", b"keep"), ("other.md", b"other")])
    manifest = tmp_path / "manifest.json"
    assert _build(root, manifest) == 0
    capsys.readouterr()

    code = _verify(manifest, root)
    captured = capsys.readouterr()
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    assert code == 0
    assert payload["corpus_sha256"] in captured.out
    assert str(payload["file_count"]) in captured.out
    assert "changed:" not in captured.out + captured.err


def test_verify_names_changed_missing_and_extra_in_their_own_groups(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "corpus"
    _write_files(
        root,
        [
            ("keep.md", b"keep"),
            ("gone.md", b"gone"),
            ("dirty.md", b"clean"),
        ],
    )
    manifest = tmp_path / "manifest.json"
    assert _build(root, manifest) == 0
    capsys.readouterr()

    (root / "gone.md").unlink()
    (root / "dirty.md").write_bytes(b"dirty")
    (root / "bonus.md").write_bytes(b"bonus")

    code = _verify(manifest, root)
    captured = capsys.readouterr()
    text = captured.out + captured.err

    assert code != 0
    assert _names_under(text, "changed") == ["dirty.md"]
    assert _names_under(text, "missing") == ["gone.md"]
    assert _names_under(text, "extra") == ["bonus.md"]
    assert "keep.md" not in _names_under(text, "changed")
    assert "keep.md" not in _names_under(text, "missing")
    assert "keep.md" not in _names_under(text, "extra")


def test_checked_in_manifest_is_internally_consistent() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    names = [entry["name"] for entry in payload["files"]]
    digest_source = "".join(f"{entry['name']} {entry['sha256']}\n" for entry in payload["files"])

    assert payload["schema_version"] == 1
    assert payload["name"] == "aircargo"
    assert payload["root"] == "data/uploads/aircargo"
    assert payload["file_count"] == len(payload["files"]) == 201
    assert names == sorted(names)
    assert (
        hashlib.sha256(digest_source.encode("utf-8")).hexdigest()
        == payload["corpus_sha256"]
    )
    assert not Path(payload["root"]).is_absolute()


@pytest.mark.skipif(
    not CORPUS_PATH.is_dir(),
    reason="the corpus is gitignored, because CI has no corpus",
)
def test_verify_of_the_checked_in_manifest_against_the_local_corpus_passes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = corpus_manifest.main(
        ["verify", "--manifest", str(MANIFEST_PATH)]
    )
    captured = capsys.readouterr()
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert code == 0
    assert payload["corpus_sha256"] in captured.out
    assert str(payload["file_count"]) in captured.out


def test_in_repo_corpus_still_stores_a_repo_relative_root(tmp_path: Path) -> None:
    """FALSE-REJECT CONTROL: a corpus under the project keeps a relative POSIX root."""
    project = tmp_path / "repo"
    corpus = project / "data" / "uploads" / "aircargo"
    _write_files(corpus, [("doc.md", b"doc")])

    manifest = corpus_manifest.build_manifest(
        corpus, name="aircargo", project_root=project
    )

    assert manifest["root"] == "data/uploads/aircargo"
    assert not Path(manifest["root"]).is_absolute()
    assert ":" not in manifest["root"]


def test_external_corpus_manifest_does_not_embed_an_absolute_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Same bytes at two machine paths outside the project yield one manifest."""
    project = tmp_path / "repo"
    project.mkdir()
    machine_a = tmp_path / "machine-a" / "aircargo"
    machine_b = tmp_path / "machine-b" / "elsewhere" / "aircargo"
    _write_files(machine_a, [("doc.md", b"same")])
    _write_files(machine_b, [("doc.md", b"same")])

    first = corpus_manifest.build_manifest(
        machine_a, name="aircargo", project_root=project
    )
    second = corpus_manifest.build_manifest(
        machine_b, name="aircargo", project_root=project
    )

    assert first["root"] == second["root"] == corpus_manifest.EXTERNAL_ROOT
    assert not Path(first["root"]).is_absolute()
    assert ":" not in first["root"]
    assert corpus_manifest.dumps_manifest(first) == corpus_manifest.dumps_manifest(second)

    out = tmp_path / "external.json"
    corpus_manifest.write_manifest(out, first)
    capsys.readouterr()
    assert _verify(out, machine_a) == 0
    missing_root = corpus_manifest.main(["verify", "--manifest", str(out)])
    captured = capsys.readouterr()
    assert missing_root != 0
    assert "--root" in captured.out + captured.err


def test_hidden_dotfiles_are_not_corpus_entries_and_do_not_move_the_digest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A macOS .DS_Store at the corpus root is a filesystem accident, not a document."""
    with_sidecar = tmp_path / "with-sidecar"
    clean = tmp_path / "clean"
    _write_files(
        with_sidecar,
        [("doc.md", b"doc"), (".DS_Store", b"mac junk"), (".hidden.md", b"nope")],
    )
    _write_files(clean, [("doc.md", b"doc")])

    out_sidecar = tmp_path / "sidecar.json"
    out_clean = tmp_path / "clean.json"
    assert _build(with_sidecar, out_sidecar) == 0
    sidecar_build = capsys.readouterr()
    assert _build(clean, out_clean) == 0
    capsys.readouterr()

    payload_sidecar = json.loads(out_sidecar.read_text(encoding="utf-8"))
    payload_clean = json.loads(out_clean.read_text(encoding="utf-8"))
    names = [entry["name"] for entry in payload_sidecar["files"]]

    assert names == ["doc.md"]
    assert payload_sidecar["file_count"] == 1
    assert payload_sidecar["corpus_sha256"] == payload_clean["corpus_sha256"]
    assert [entry["name"] for entry in payload_sidecar["files"]] == [
        entry["name"] for entry in payload_clean["files"]
    ]

    sidecar_build_text = sidecar_build.out + sidecar_build.err
    assert "skipped 2 hidden entries" in sidecar_build_text
    assert ".DS_Store" not in sidecar_build_text

    code = _verify(out_sidecar, with_sidecar)
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert code == 0
    assert "skipped 2 hidden entries" in text
    assert ".DS_Store" not in text
    assert ".hidden.md" not in _names_under(text, "extra")


def test_build_refuses_an_empty_corpus_and_does_not_write_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "empty-root"
    root.mkdir()
    (root / "subdir").mkdir()
    (root / ".DS_Store").write_bytes(b"mac junk")
    out = tmp_path / "must-not-exist.json"

    code = _build(root, out)
    captured = capsys.readouterr()
    text = captured.out + captured.err

    assert code != 0
    assert not out.exists()
    assert "no corpus files under" in text
    assert str(root) in text
    assert "hidden files and subdirectories are not corpus entries" in text


def test_verify_names_a_missing_directory_instead_of_every_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "corpus"
    _write_files(root, [("a.md", b"a"), ("b.md", b"b")])
    manifest = tmp_path / "manifest.json"
    assert _build(root, manifest) == 0
    capsys.readouterr()

    missing = tmp_path / "does_not_exist"
    code = _verify(manifest, missing)
    captured = capsys.readouterr()
    text = captured.out + captured.err

    assert code != 0
    assert "not a directory" in text
    assert str(missing) in text
    assert "missing:" not in text
    assert "a.md" not in text
    assert "b.md" not in text


def test_verify_rejects_unsupported_or_malformed_manifests(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "corpus"
    _write_files(root, [("a.md", b"a")])
    good = tmp_path / "good.json"
    assert _build(root, good) == 0
    capsys.readouterr()
    payload = json.loads(good.read_text(encoding="utf-8"))

    schema2 = tmp_path / "schema2.json"
    payload_schema2 = dict(payload)
    payload_schema2["schema_version"] = 2
    schema2.write_text(json.dumps(payload_schema2), encoding="utf-8")

    no_files = tmp_path / "nofiles.json"
    payload_no_files = dict(payload)
    del payload_no_files["files"]
    no_files.write_text(json.dumps(payload_no_files), encoding="utf-8")

    for path in (schema2, no_files):
        capsys.readouterr()
        code = _verify(path, root)
        captured = capsys.readouterr()
        text = captured.out + captured.err
        assert code != 0
        assert "unsupported or malformed manifest" in text
        assert "Traceback" not in text


def test_nfd_and_nfc_file_names_are_one_entry_and_one_digest(tmp_path: Path) -> None:
    nfc_name = unicodedata.normalize("NFC", "résumé.md")
    nfd_name = unicodedata.normalize("NFD", "résumé.md")
    assert nfc_name != nfd_name

    nfc_root = tmp_path / "nfc"
    nfd_root = tmp_path / "nfd"
    _write_files(nfc_root, [(nfc_name, b"cv")])
    _write_files(nfd_root, [(nfd_name, b"cv")])

    nfc_out = tmp_path / "nfc.json"
    nfd_out = tmp_path / "nfd.json"
    assert _build(nfc_root, nfc_out) == 0
    assert _build(nfd_root, nfd_out) == 0

    nfc_payload = json.loads(nfc_out.read_text(encoding="utf-8"))
    nfd_payload = json.loads(nfd_out.read_text(encoding="utf-8"))

    assert nfc_payload["file_count"] == nfd_payload["file_count"] == 1
    assert nfc_payload["files"][0]["name"] == nfc_name
    assert nfd_payload["files"][0]["name"] == nfc_name
    assert nfc_payload["corpus_sha256"] == nfd_payload["corpus_sha256"]
    assert corpus_manifest.entry_name(Path(nfd_name)) == nfc_name
