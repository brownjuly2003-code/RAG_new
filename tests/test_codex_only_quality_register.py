"""Synthetic offline admission contracts. Run on the Mac; no model or live index.

The integration fixture replaces only external boundaries (release Git inspection,
settings interpreter, package selection and Chroma transport). File verification,
historical pins, receipt binding, provider resolution, graph review, Q and R comparison
run normally. SentGold.saved_point has separate real-instrument synthetic coverage.
"""

from __future__ import annotations

import ast
import copy
import gzip
import importlib
import os
import shutil

# Standalone stdlib inventory subprocess only.
import subprocess  # nosec B404
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports/codex-only-quality/tools"
sys.path.insert(0, str(TOOLS))
import copy_verify as cv  # noqa: E402
import quality_driver as driver  # noqa: E402


def put(path: Path, value: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else cv.encoded(value))
    return path


def jsonl(path: Path, values: list[Any]) -> Path:
    return put(path, b"".join(cv.encoded(v).replace(b"\n", b"") + b"\n" for v in values))


def pin_spec(repo: Path, names: list[str]) -> None:
    put(
        repo / "docs/specs/generator-ceiling.md",
        (
            "## SHA-256 registration\n"
            + "".join(f"- `{name}` `{cv.sha(repo / name)}`\n" for name in names)
        ).encode(),
    )


def fake_collection(folder: Path, chunks: list[Any]) -> dict[str, Any]:
    return {"passed": True, "count": len(chunks)}


@pytest.fixture
def admission(tmp_path: Path) -> SimpleNamespace:
    repo, private = tmp_path / "repo", tmp_path / "private"
    data = private / "data"
    config: dict[str, Any] = {
        "schema_version": 1,
        "private_data_root": str(data),
        "bases": {},
        "private_inputs": {},
        "copy_receipt": str(private / "copy.json"),
    }
    archives, converted, pins, historical = {}, {}, [], {}
    for key in cv.KEYS:
        folder = data / key
        tenant = "aircargo" if key == "aircargo" else "ext_" + key
        docs = {"doc.md": b"Alpha beta gamma\n", "other.md": b"Other material\n"}
        for name, raw in docs.items():
            put(folder / "corpus" / name, raw)
        files = [
            {"name": n, "sha256": cv.digest(b), "bytes": len(b)} for n, b in sorted(docs.items())
        ]
        corpus_sha = cv.digest("".join(f"{r['name']} {r['sha256']}\n" for r in files))
        put(
            folder / "corpus.manifest.json",
            {
                "schema_version": 1,
                "name": tenant,
                "root": "<external>",
                "files": files,
                "file_count": 2,
                "corpus_sha256": corpus_sha,
            },
        )
        chunks: list[dict[str, Any]] = [
            {"page_content": b.decode(), "metadata": {"source": n}} for n, b in docs.items()
        ]
        payload = cv.encoded({"tenant_id": tenant, "chunks": chunks})
        archive = gzip.compress(payload, mtime=0)
        put(folder / "chunks.json.gz", archive)
        archives[key] = cv.digest(archive)
        cases_path = (
            repo / "evaluation/curated_cases_aircargo.jsonl"
            if key == "aircargo"
            else folder / "cases.jsonl"
        )
        jsonl(
            cases_path,
            [{"case_id": f"{key}-{i:03}", "query": f"Synthetic question {i}?"} for i in range(100)],
        )
        text_bytes = b"".join(
            len(c["page_content"].encode()).to_bytes(8, "big") + c["page_content"].encode()
            for c in chunks
        )
        put(
            folder / "chunks-report.json",
            {
                "tenant": tenant,
                "collection": "rag_docs_" + tenant,
                "corpus_sha256": corpus_sha,
                "archive_sha256": archives[key],
                "payload_sha256": cv.digest(payload),
                "archive_bytes": len(archive),
                "documents": 2,
                "chunks": 2,
            },
        )
        put(
            folder / "index/index-receipt.json",
            {
                "schema_version": 1,
                "corpus_sha256": archives[key],
                "texts_sha256": cv.digest(text_bytes),
                "collection_name": "rag_docs_" + tenant,
                "chunk_count": 2,
                "chromadb_version": "synthetic",
                "embedder_manifest": {
                    "backend": "local",
                    "model": "synthetic",
                    "revision_source": "hf_snapshot",
                    "revision": "a" * 40,
                    "normalize": True,
                    "dimension": 2,
                    "schema_version": 1,
                },
            },
        )
        put(folder / "index/chroma/chroma.sqlite3", b"synthetic index bytes; never opened")
        put(
            repo / cv.old_export(key),
            {"base": key, "provenance": {"prompt_id": "QA_PROMPT_V4"}},
        )
        pins.append(cv.old_export(key))
        provenance = {
            "cases_sha256": cv.sha(cases_path),
            "corpus_sha256": {name: cv.sha(folder / name) for name in cv.SOURCE_FILES},
            "code_sha": "138f3b3" if key == "aircargo" else "2057ad0",
        }
        measured = {"status": "counted", "base": key, "provenance": provenance}
        if key == "aircargo":
            put(repo / cv.AIRCARGO_ANSWERS, measured)
            put(
                repo / cv.AIRCARGO_GENERATION,
                ("CORPUS_SHA256 = " + repr(provenance["corpus_sha256"]) + "\n").encode(),
            )
        else:
            historical[key] = {"answers": measured}
        converted[key] = {
            "converted": {
                "cases_sha256": cv.sha(cases_path),
                "cases": 100,
                "corpus_sha256": corpus_sha,
                "documents": 2,
            }
        }
        inv = private / f"inventory-{key}.json"
        put(inv, cv.inventory(folder))
        config["bases"][key] = {"inventory": str(inv)}
    put(repo / "evaluation/external_bases.json", {"bases": converted})
    put(
        repo / "reports/stage7/tools/arms_replay.py",
        ("ARCHIVES = " + repr(archives) + "\n").encode(),
    )
    put(repo / cv.STAGE5_RECORD, {"corpora": historical})
    pins.append(cv.STAGE5_RECORD)
    pin_spec(repo, pins)
    for name in cv.PRIVATE_INPUTS:
        root, inv = private / name, private / f"inventory-{name}.json"
        put(root / "synthetic.json", {"fixture": True})
        put(inv, cv.inventory(root))
        config["private_inputs"][name] = {"root": str(root), "inventory": str(inv)}
    config_path = put(private / "config.json", config)
    return SimpleNamespace(
        repo=repo, private=private, data=data, config=config, config_path=config_path, pins=pins
    )


def refresh(fixture: SimpleNamespace) -> None:
    for folder, inv in cv.input_trees(fixture.config).values():
        put(inv, cv.inventory(folder))
    put(fixture.config_path, fixture.config)
    put(
        Path(fixture.config["copy_receipt"]),
        cv.verify(fixture.config_path, fixture.repo, collection_reader=fake_collection),
    )


def test_inventory_standalone_deterministic_and_hashes_its_own_bytes(tmp_path: Path) -> None:
    script = tmp_path / "copy_verify.py"
    shutil.copyfile(TOOLS / "copy_verify.py", script)
    folder = tmp_path / "source"
    put(folder / "z.bin", b"\xff\x00")
    put(folder / "sub/a.txt", b"synthetic\n")
    out = tmp_path / "inventory.json"
    command = [
        sys.executable,
        "-I",
        "-S",
        str(script),
        "inventory",
        "--root",
        str(folder),
        "--out",
        str(out),
    ]
    # Synthetic, copied stdlib-only script, fixed argv.
    result = subprocess.run(command, capture_output=True, check=False)  # nosec B603
    assert result.returncode == 0
    expected = cv.inventory(folder)
    assert cv.read(out) == expected
    assert expected == cv.inventory(folder)
    assert expected["tool_sha256"] == cv.sha(script)
    assert [r["path"] for r in expected["files"]] == ["sub/a.txt", "z.bin"]
    assert b"\r" not in out.read_bytes()
    assert str(folder) not in out.read_text(encoding="utf-8")


@pytest.mark.parametrize("kind", ["file", "directory", "dangling"])
def test_inventory_refuses_symlinks(tmp_path: Path, kind: str) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = tmp_path / "target"
    if kind == "file":
        target.write_bytes(b"x")
    elif kind == "directory":
        target.mkdir()
    (root / "link").symlink_to(target, target_is_directory=kind == "directory")
    with pytest.raises(cv.Refusal, match="symlink"):
        cv.inventory(root)


def test_inventory_refuses_special_file_and_output_inside_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    # Executed on POSIX; Windows mypy does not expose this platform API.
    os.mkfifo(root / "fifo")  # type: ignore[attr-defined]
    with pytest.raises(cv.Refusal, match="special"):
        cv.inventory(root)
    assert cv.main(["inventory", "--root", str(root), "--out", str(root / "out.json")]) == 1


def test_verify_exact_copy_and_receipt_is_hash_only(admission: SimpleNamespace) -> None:
    result = cv.verify(admission.config_path, admission.repo, collection_reader=fake_collection)
    assert result["passed"] is True
    assert all(result["logical"][key]["chunk_count"] == 2 for key in cv.KEYS)
    output = cv.encoded(result).decode()
    for private_text in (str(admission.private), "doc.md", "Alpha beta", "chroma.sqlite3"):
        assert private_text not in output
    put(Path(admission.config["copy_receipt"]), result)
    assert cv.admit_receipt(admission.config_path, admission.repo) == result


@pytest.mark.parametrize(
    "failure", [None, "count", "ids", "documents", "metadata", "embedding", "manifest", "version"]
)
def test_collection_reads_existing_content_without_creating_or_embedding(
    admission: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
) -> None:
    folder = admission.data / "wixqa"
    _, chunks = cv.logical_metadata(admission.repo, "wixqa", folder)
    receipt = cv.read(folder / "index/index-receipt.json")
    manifest = receipt["embedder_manifest"]
    found: dict[str, Any] = {
        "ids": [f"chunk-{i:08d}" for i in range(len(chunks))],
        "documents": [c["page_content"] for c in chunks],
        "metadatas": [dict(c["metadata"], chunk_index=i) for i, c in enumerate(chunks)],
        "embeddings": [[1.0, 0.0] for _ in chunks],
    }
    if failure == "ids":
        found["ids"][0] = "wrong"
    elif failure == "documents":
        found["documents"][0] = "wrong"
    elif failure == "metadata":
        found["metadatas"][0]["chunk_index"] = 99
    elif failure == "embedding":
        found["embeddings"][0] = [0.0, 0.0]
    elif failure == "manifest":
        manifest = {**manifest, "dimension": 3}
    collection = SimpleNamespace(
        count=lambda: len(chunks) + int(failure == "count"),
        metadata={"embedder_manifest": cv.encoded(manifest).decode()},
        get=lambda **kwargs: found,
    )

    def get_collection(name: str, *, embedding_function: Any) -> SimpleNamespace:
        assert name == receipt["collection_name"] and embedding_function is None
        return collection

    monkeypatch.setitem(
        sys.modules,
        "chromadb",
        SimpleNamespace(
            __version__="wrong" if failure == "version" else "synthetic",
            PersistentClient=lambda **kwargs: SimpleNamespace(get_collection=get_collection),
        ),
    )
    monkeypatch.setitem(
        sys.modules, "chromadb.config", SimpleNamespace(Settings=lambda **kwargs: kwargs)
    )
    if failure is None:
        assert cv.check_collection(folder, chunks) == {"passed": True, "count": 2}
    else:
        with pytest.raises(cv.Refusal, match="mismatch"):
            cv.check_collection(folder, chunks)


def test_verify_records_index_bookkeeping_but_refuses_other_writes(
    admission: SimpleNamespace,
) -> None:
    def bookkeeping(folder: Path, chunks: list[Any]) -> dict[str, Any]:
        put(folder / "index/chroma/runtime", b"bookkeeping")
        return fake_collection(folder, chunks)

    value = cv.verify(admission.config_path, admission.repo, collection_reader=bookkeeping)
    assert value["trees"]["wixqa"]["pre"] != value["trees"]["wixqa"]["post"]
    put(Path(admission.config["copy_receipt"]), value)
    assert cv.admit_receipt(admission.config_path, admission.repo)["passed"]
    refresh(admission)

    def changed_corpus(folder: Path, chunks: list[Any]) -> dict[str, Any]:
        put(folder / "corpus/doc.md", b"changed during inspection")
        return fake_collection(folder, chunks)

    with pytest.raises(cv.Refusal, match="non-index"):
        cv.verify(admission.config_path, admission.repo, collection_reader=changed_corpus)


@pytest.mark.parametrize("change", ["extra", "missing", "changed", "private_input"])
def test_verify_refuses_tree_changes_before_any_index_open(
    admission: SimpleNamespace, change: str
) -> None:
    folder = admission.data / "aircargo"
    if change == "extra":
        put(folder / "extra", b"extra")
    elif change == "missing":
        (folder / "corpus/doc.md").unlink()
    elif change == "changed":
        (folder / "index/chroma/chroma.sqlite3").write_bytes(b"different")
    else:
        put(
            Path(admission.config["private_inputs"]["attempt02_journals"]["root"]) / "extra",
            b"extra",
        )

    def must_not_open(*args: Any) -> dict[str, Any]:
        raise AssertionError("index opened before inventory gate")

    with pytest.raises(cv.Refusal, match="whole-tree"):
        cv.verify(admission.config_path, admission.repo, collection_reader=must_not_open)


@pytest.mark.parametrize("part", ["corpus", "receipt", "tenant", "cases", "embedding"])
def test_verify_refuses_logical_mismatch_even_with_fresh_inventory(
    admission: SimpleNamespace, part: str
) -> None:
    folder = admission.data / "wixqa"
    if part == "corpus":
        put(folder / "corpus/doc.md", b"changed")
    elif part == "cases":
        put(folder / "cases.jsonl", b"{}\n")
    elif part == "tenant":
        report = cv.read(folder / "chunks-report.json")
        report["tenant"] = "wrong"
        put(folder / "chunks-report.json", report)
    else:
        receipt = cv.read(folder / "index/index-receipt.json")
        if part == "receipt":
            receipt["chunk_count"] += 1
        else:
            receipt["embedder_manifest"]["normalize"] = False
        put(folder / "index/index-receipt.json", receipt)
    put(Path(admission.config["bases"]["wixqa"]["inventory"]), cv.inventory(folder))
    with pytest.raises(cv.Refusal):
        cv.verify(admission.config_path, admission.repo, collection_reader=fake_collection)


@pytest.mark.parametrize(
    "change", ["failed", "schema", "tool", "stale", "logical", "inventory", "instrument", "count"]
)
def test_admit_receipt_refuses_each_broken_binding(admission: SimpleNamespace, change: str) -> None:
    refresh(admission)
    path = Path(admission.config["copy_receipt"])
    receipt = cv.read(path)
    if change == "failed":
        receipt["passed"] = False
    elif change == "schema":
        receipt["schema_version"] = 42
    elif change == "tool":
        receipt["tool_sha256"] = "0" * 64
    elif change == "stale":
        put(admission.data / "wixqa/corpus/doc.md", b"changed")
    elif change == "logical":
        receipt["logical"]["wixqa"]["passed"] = False
    elif change == "instrument":
        put(admission.repo / cv.AIRCARGO_GENERATION, b"CORPUS_SHA256 = {}\n")
    elif change == "count":
        receipt["logical"]["wixqa"]["collection"]["count"] += 1
    else:
        put(Path(admission.config["bases"]["wixqa"]["inventory"]), {})
    put(path, receipt)
    with pytest.raises(cv.Refusal):
        cv.admit_receipt(admission.config_path, admission.repo)


def settings() -> dict[str, Any]:
    return {
        **cv.constant(ROOT / "reports/stage4-final/tools/common.py", "SETTINGS"),
        "llm_provider_profile": "codex-only",
        "hyde": False,
        "streaming_rag_parity": False,
        "codex_reasoning_effort": "xhigh",
        "codex_timeout_sec": 180,
    }


def test_all_settings_including_inactive_keys_are_compared() -> None:
    reference = cv.constant(ROOT / "reports/stage4-final/tools/common.py", "SETTINGS")
    effective = settings()
    assert driver.compare_settings(effective, reference)["passed"]
    for key in reference:
        changed = {**effective, key: "changed"}
        with pytest.raises(cv.Refusal, match="effective setting"):
            driver.compare_settings(changed, reference)


def test_graph_call_table_and_maximum_match_reviewed_code() -> None:
    effective = settings()
    providers = driver.resolve_providers(ROOT / "config/providers.yml", effective)
    bound = driver.graph_bound(ROOT / "agent/graph.py", effective, providers)
    assert bound["maximum_calls"] == 3
    assert bound["ceiling_sec"] == 420
    assert [r["timeout_sec"] for r in bound["reachable"]] == [60, 60, 180]
    assert (
        driver.graph_sites((ROOT / "agent/graph.py").read_text(encoding="utf-8"))
        == driver.CALL_SITES
    )


@pytest.mark.parametrize("mutation", ["call", "edge", "loop"])
def test_graph_change_requires_new_review(tmp_path: Path, mutation: str) -> None:
    source = (ROOT / "agent/graph.py").read_text(encoding="utf-8")
    if mutation == "call":
        source += '\ndef new_call(llm):\n    return _invoke_llm(llm, "synthetic")\n'
    elif mutation == "edge":
        source = source.replace(
            'workflow.add_edge("grade_docs", "generate")',
            'workflow.add_edge("grade_docs", "rewrite_query")',
        )
    else:
        source += (
            '\ndef retry_forever(llm):\n    while True:\n        _invoke_llm(llm, "synthetic")\n'
        )
    path = put(tmp_path / "graph.py", source.encode())
    with pytest.raises(cv.Refusal, match="graph"):
        driver.graph_bound(
            path, settings(), driver.resolve_providers(ROOT / "config/providers.yml", settings())
        )


def q_rows() -> dict[str, list[dict[str, Any]]]:
    return {
        key: [
            {
                "case_id": f"{key}-{i:03}",
                "grade": "good",
                "context_has_answer": i % 2 == 0,
                "prompt_sha256": cv.digest(f"prompt-{key}-{i}"),
            }
            for i in range(100)
        ]
        for key in cv.KEYS
    }


def test_q_counts_good_answers_excluding_good_declines() -> None:
    verdicts = q_rows()
    verdicts["wixqa"][0]["grade"] = "partial_ok"
    verdicts["conditionalqa"][0]["grade"] = "bad"
    ids = {key: [r["case_id"] for r in values] for key, values in verdicts.items()}
    result = driver.q_baseline(verdicts, ids)
    assert result["pooled"] == {"answered_good": 148, "n": 300}
    assert result["aircargo"]["answered_good"] == 50
    assert result["aircargo"]["cases"][1]["answered_good"] is False


def test_q_pairs_export_order_by_id_and_keeps_package_order() -> None:
    verdicts = q_rows()
    ids = {key: [r["case_id"] for r in values] for key, values in verdicts.items()}
    verdicts["wixqa"].reverse()
    result = driver.q_baseline(verdicts, ids)
    assert [r["case_id"] for r in result["wixqa"]["cases"]] == ids["wixqa"]
    assert result["pooled"]["answered_good"] == 150


def r_rows(key: str) -> list[dict[str, Any]]:
    hits, n = (67, 100) if key == "wixqa" else (58, 80)
    return [
        {
            "case_id": f"{key}-{i:03}",
            "gold": i < n,
            "hit": int(i < hits) if i < n else None,
            "fraction": float(i < hits) if i < n else None,
            "prompt_sha256": cv.digest(f"prompt-{key}-{i}"),
        }
        for i in range(100)
    ]


def test_r_rejects_casewise_difference_with_unchanged_totals() -> None:
    expected = r_rows("wixqa")
    changed = copy.deepcopy(expected)
    for field in ("hit", "fraction"):
        changed[0][field], changed[99][field] = changed[99][field], changed[0][field]
    assert sum(r["hit"] for r in changed) == sum(r["hit"] for r in expected)
    with pytest.raises(cv.Refusal, match="casewise"):
        driver.r_compare("wixqa", expected, changed)


def test_real_saved_point_uses_ranges_and_refuses_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for directory in (
        "reports/stage2/tools",
        "reports/stage4-final/tools",
        "reports/stage4-final/tools/external",
    ):
        monkeypatch.syspath_prepend(str(ROOT / directory))
    # Other historical-tool tests may have used these unqualified module names.
    for name in ("common", "protocol", "sent_gold", "retrieval_summary"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    sent = importlib.import_module("sent_gold")
    from evaluation import external_gold as gold
    from scripts.external_pilot import Places

    reader = sent.SentGold.__new__(sent.SentGold)
    reader.base = "conditionalqa"
    reader.chunks = [{"page_content": "Alpha beta", "metadata": {"source": "doc.md"}}]
    reader.sources = {"doc.md": gold.Source.read("doc.md", "Alpha beta gamma")}
    reader.places = Places(reader.chunks, reader.sources, 0, 1)
    case = {"evidence_groups": [{"alternatives": [{"source_id": "doc.md", "start": 0, "end": 9}]}]}
    assert reader.saved_point(case, [("doc.md", "Alpha beta")]) == {
        "gold": True,
        "hit": 1,
        "fraction": 1,
    }
    assert reader.saved_point(case, [("doc.md", "beta")])["hit"] == 0
    with pytest.raises(SystemExit, match="unplaceable"):
        reader.saved_point(case, [("doc.md", "missing passage")])
    with pytest.raises(SystemExit, match="unresolved"):
        reader.saved_point({**case, "unresolved_evidence": True}, [("doc.md", "Alpha beta")])


@pytest.mark.parametrize("failure", [None, "order", "question", "prompt"])
def test_package_admission_checks_original_order_questions_and_prompt_hashes(
    admission: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
) -> None:
    f = admission
    common_name = "reports/stage4-final/tools/common.py"
    put(f.repo / common_name, (ROOT / common_name).read_bytes())
    model_digest = cv.constant(f.repo / common_name, "MODEL_DIGEST")
    parsed: dict[Path, list[dict[str, Any]]] = {}
    orders: dict[str, list[str]] = {}
    for key in cv.KEYS:
        cases_path = (
            f.repo / "evaluation/curated_cases_aircargo.jsonl"
            if key == "aircargo"
            else f.data / key / "cases.jsonl"
        )
        known = cv.rows(cases_path)
        orders[key] = [row["case_id"] for row in known]
        label = "stage5_aircargo_runs" if key == "aircargo" else "stage5_runs"
        runs = Path(f.config["private_inputs"][label]["root"])
        exported = []
        for batch in range(10):
            folder = runs / f"final-answers-{key}-b{batch + 1:02d}"
            batch_cases = known[batch * 10 : (batch + 1) * 10]
            put(
                folder / "launch.json",
                {
                    "status": "complete",
                    "cases": [c["case_id"] for c in batch_cases],
                    "code_sha": "138f3b3" if key == "aircargo" else "2057ad0",
                    "tenant": key if key == "aircargo" else "ext_" + key,
                    "model": settings()["ollama_model_name"],
                    "model_digest": model_digest,
                    "cases_sha256": cv.sha(cases_path),
                    "corpus_sha256": {n: cv.sha(f.data / key / n) for n in cv.SOURCE_FILES},
                },
            )
            parsed[folder] = []
            for i, case in enumerate(batch_cases):
                prompt = put(folder / "prompts" / f"{i:03}-stream.txt", case["query"].encode())
                answer = {
                    "case_id": case["case_id"],
                    "question": case["query"],
                    "prompt_file": prompt.name,
                    "prompt_sha256": cv.sha(prompt),
                    "prompt_id": "QA_PROMPT_V4",
                }
                parsed[folder].append(answer)
                exported.append({"case_id": case["case_id"], "prompt_sha256": cv.sha(prompt)})
        jsonl((f.repo / cv.old_export(key)).with_suffix(".cases.jsonl"), exported)
    judge = SimpleNamespace(run_answers=lambda folder: parsed[folder])
    reader = SimpleNamespace(AIRCARGO={}, registered=lambda key, path: orders[key])
    monkeypatch.setattr(
        driver,
        "canonical_import",
        lambda repo, name, path: judge if name == "chat_answer_judge" else reader,
    )
    first_folder = next(iter(parsed))
    if failure == "order":
        parsed[first_folder].reverse()
    elif failure == "question":
        parsed[first_folder][0]["question"] = "Another synthetic question"
    elif failure == "prompt":
        put(first_folder / "prompts/000-stream.txt", b"changed")
    if failure is None:
        _, actual = driver.load_packages(f.repo, f.config)
        assert actual == orders
    else:
        with pytest.raises(cv.Refusal, match="package"):
            driver.load_packages(f.repo, f.config)


@pytest.fixture
def registration(admission: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    f = admission
    for name in (
        "config/providers.yml",
        "agent/graph.py",
        "reports/stage4-final/tools/common.py",
        "reports/codex-only-quality/tools/shim/CaptureShim.cs",
        *driver.HELPER_FILES,
    ):
        put(f.repo / name, (ROOT / name).read_bytes())
    f.config["release"] = {"root": str(f.repo), "commit": "a" * 40, "python": sys.executable}
    f.config["stands"] = {
        key: {"env": str(put(f.private / f"{key}.env", b"LLM_PROVIDER_PROFILE=codex-only\n"))}
        for key in cv.KEYS
    }
    f.config["artifacts"] = {
        name: str(put(f.private / name, {"passed": True})) for name in driver.ARTIFACTS
    }
    artifacts = f.config["artifacts"]
    artifacts["shim_config"] = str(f.private / "capture_shim.json")
    put(
        Path(artifacts["shim_config"]),
        {
            "real_exe": artifacts["codex_executable"],
            "capture_root": str(f.private / "capture"),
        },
    )
    put(
        Path(artifacts["shim_build"]),
        {
            "source_sha256": cv.sha(
                f.repo / "reports/codex-only-quality/tools/shim/CaptureShim.cs"
            ),
            "exe_sha256": cv.sha(Path(artifacts["shim_executable"])),
        },
    )
    for label in ("helper_verification", "unchanged_defaults"):
        put(
            Path(artifacts[label]),
            {
                "passed": True,
                "files": {name: cv.sha(f.repo / name) for name in driver.HELPER_FILES},
            },
        )
    for cli in ("codex", "claude"):
        put(
            Path(artifacts[cli + "_version"]),
            {
                "version": "synthetic 1.0",
                "executable_sha256": cv.sha(Path(artifacts[cli + "_executable"])),
            },
        )
    for name in ("environment", "assets"):
        root, inv = f.private / name, f.private / (name + "-inventory.json")
        put(root / "synthetic", b"fixture")
        f.config["private_inputs"][name] = {"root": str(root), "inventory": str(inv)}
    f.verdicts = q_rows()
    f.packages = copy.deepcopy(f.verdicts)
    f.ids = {key: [r["case_id"] for r in values] for key, values in f.verdicts.items()}
    f.expected_r = {key: r_rows(key) for key in cv.KEYS[:2]}
    historical = cv.read(f.repo / driver.STAGE5)
    for key, values in f.expected_r.items():
        historical["corpora"][key]["sent_cases"] = values
    put(f.repo / driver.STAGE5, historical)
    pin_spec(f.repo, f.pins)
    runs = Path(f.config["private_inputs"]["attempt02_runs"]["root"])
    journals = Path(f.config["private_inputs"]["attempt02_journals"]["root"])
    for key in cv.KEYS:
        put(runs / key / "runs/final-answers-synthetic/launch.json", {"fixture": True})
        for metric in ("m1", "bridge"):
            put(journals / key / metric / "plan.json", {"fixture": metric})
            put(journals / key / metric / "verdicts.jsonl", b"{}\n")
        put(
            f.repo / driver.ATTEMPT / f"plans-{key}.json",
            {
                "key": key,
                "answer_files": {
                    r["path"]: r["sha256"] for r in cv.tree_files(runs / key / "runs")
                },
                "plans": {m: cv.sha(journals / key / m / "plan.json") for m in ("m1", "bridge")},
                "bridge_seed": {"bytes": 3, "sha256": cv.digest(b"{}\n")},
            },
        )
        put(
            f.repo / driver.ATTEMPT / f"ceiling-{key}-judge-m1.json",
            {
                "base": key,
                "status": "counted",
                "provenance": {
                    "plan_sha256": cv.sha(journals / key / "m1/plan.json"),
                    "verdicts_sha256": cv.sha(journals / key / "m1/verdicts.jsonl"),
                },
            },
        )
        jsonl(f.repo / driver.ATTEMPT / f"ceiling-{key}-judge-m1.cases.jsonl", f.verdicts[key])
    released_helpers = {name: cv.sha(f.repo / name) for name in driver.HELPER_FILES[:2]}
    monkeypatch.setattr(
        driver,
        "release_files",
        lambda release: {
            "commit": release["commit"],
            "files": released_helpers,
        },
    )
    monkeypatch.setattr(driver, "load_packages", lambda *args: (f.packages, f.ids))

    def gate(repo: Path, config: dict[str, Any], packages: dict[str, Any]) -> dict[str, Any]:
        historical = cv.read(repo / driver.STAGE5)
        return {
            "passed": True,
            "keys": {
                key: driver.r_compare(
                    key, historical["corpora"][key]["sent_cases"], f.expected_r[key]
                )
                for key in cv.KEYS[:2]
            },
        }

    monkeypatch.setattr(driver, "r_gate", gate)
    f.effective = settings()
    f.invoke = lambda: driver.register(
        f.config_path,
        f.private,
        "synthetic",
        f.repo / "reports/codex-only-quality",
        f.repo,
        settings_reader=lambda *args: f.effective,
    )
    refresh(f)
    return f


def test_register_writes_baselines_hashes_and_pending_names(registration: SimpleNamespace) -> None:
    f = registration
    result = f.invoke()
    assert result["q_baseline"]["pooled"] == {"answered_good": 150, "n": 300}
    assert result["r_gate"]["passed"]
    assert "reports/codex-only-quality/tools/quality_read.py" in result["pending"]
    assert result["files"]["agent/graph.py"] == cv.sha(f.repo / "agent/graph.py")
    assert result["request_ready"] is False
    output = cv.encoded(result).decode()
    assert str(f.private) not in output and str(f.repo) not in output
    with pytest.raises(cv.Refusal, match="already exists"):
        f.invoke()


@pytest.mark.parametrize(
    "failure",
    [
        "copy_missing",
        "copy_failed",
        "pin",
        "settings",
        "provider",
        "graph",
        "q",
        "r",
        "journal",
        "helper",
        "helper_hash",
        "shim_build",
        "shim_config",
        "cli_version",
        "release",
    ],
)
def test_register_refuses_failed_condition(
    registration: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    f = registration
    if failure == "copy_missing":
        Path(f.config["copy_receipt"]).unlink()
    elif failure == "copy_failed":
        value = cv.read(Path(f.config["copy_receipt"]))
        value["passed"] = False
        put(Path(f.config["copy_receipt"]), value)
    elif failure == "pin":
        put(f.repo / driver.STAGE5, {})
    elif failure == "settings":
        f.effective["retrieval_top_k"] += 1
    elif failure == "provider":
        path = f.repo / "config/providers.yml"
        put(path, path.read_bytes().replace(b"timeout_sec: 60", b"timeout_sec: 61"))
    elif failure == "graph":
        path = f.repo / "agent/graph.py"
        put(path, path.read_bytes() + b'\ndef new_call(llm):\n    _invoke_llm(llm, "x")\n')
    elif failure == "q":
        values = f.verdicts["wixqa"]
        values[0]["context_has_answer"] = "true"
        jsonl(f.repo / driver.ATTEMPT / "ceiling-wixqa-judge-m1.cases.jsonl", values)
    elif failure == "r":
        for field in ("hit", "fraction"):
            f.expected_r["wixqa"][0][field], f.expected_r["wixqa"][99][field] = (
                f.expected_r["wixqa"][99][field],
                f.expected_r["wixqa"][0][field],
            )
    elif failure == "journal":
        put(
            Path(f.config["private_inputs"]["attempt02_journals"]["root"])
            / "wixqa/m1/verdicts.jsonl",
            b"changed\n",
        )
        refresh(f)  # fresh copy evidence cannot bypass the historical journal hash
    elif failure == "helper":
        put(Path(f.config["artifacts"]["helper_verification"]), {"passed": False})
    elif failure == "helper_hash":
        value = cv.read(Path(f.config["artifacts"]["unchanged_defaults"]))
        value["files"][driver.HELPER_FILES[0]] = "0" * 64
        put(Path(f.config["artifacts"]["unchanged_defaults"]), value)
    elif failure in ("shim_build", "shim_config", "cli_version"):
        label = "codex_version" if failure == "cli_version" else failure
        path = Path(f.config["artifacts"][label])
        value = cv.read(path)
        field = {
            "shim_build": "exe_sha256",
            "shim_config": "real_exe",
            "cli_version": "executable_sha256",
        }[failure]
        value[field] = "changed"
        put(path, value)
    else:

        def refuse_release(*args: Any) -> dict[str, Any]:
            raise cv.Refusal("release checkout is dirty")

        monkeypatch.setattr(driver, "release_files", refuse_release)
    with pytest.raises((cv.Refusal, OSError)):
        f.invoke()
    assert not (f.repo / "reports/codex-only-quality/synthetic/registration.json").exists()


@pytest.mark.parametrize(
    "command,extra",
    [
        ("probe", []),
        ("pilot", ["--step", "1"]),
        ("run", ["--key", "wixqa"]),
        ("freeze", ["--key", "wixqa"]),
        ("grade", ["--key", "wixqa"]),
        ("export", ["--key", "wixqa"]),
    ],
)
def test_future_commands_refuse_without_reading_inputs(
    command: str, extra: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        driver.main(
            [
                command,
                "--config",
                "absent",
                "--private",
                "absent",
                "--records",
                "absent",
                "--series",
                "synthetic",
                *extra,
            ]
        )
        == 1
    )
    assert "not implemented in this task" in capsys.readouterr().err


def test_new_tools_never_use_dynamic_execution() -> None:
    for filename in ("copy_verify.py", "quality_driver.py"):
        tree = ast.parse((TOOLS / filename).read_text(encoding="utf-8"))
        assert not any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in {"exec", "eval"}
            for n in ast.walk(tree)
        )


def test_cli_preconditions_use_one_and_keep_legacy_errors_private(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cv.main(["verify"]) == 1
    assert driver.main(["register"]) == 1

    def legacy_failure(*args: Any) -> None:
        raise SystemExit("private path and external passage must not escape")

    monkeypatch.setattr(driver, "register", legacy_failure)
    assert (
        driver.main(
            [
                "register",
                "--config",
                "synthetic",
                "--private",
                "synthetic",
                "--records",
                "synthetic",
                "--series",
                "synthetic",
            ]
        )
        == 1
    )
    assert "external passage" not in capsys.readouterr().err
