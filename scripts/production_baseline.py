"""Staged H/Hm production Chroma baseline capture, without generation or metrics.

Run each stage in a separate process: prepare, transform, embed, retrieve, grade.
Model failures exclude a case; integrity and environment failures abort the run.

prepare registers H and Hm, or the case file --cases names under --subset: of such a file
the run keeps the ids and the questions and none of the labels. --set moves one of the two
candidate counts of the control (retrieval_top_k, rerank_top_k) and nothing else, so an arm
of a pilot is the registered collection with one number changed.

--base NAME --base-dir DIR --selection NAME registers a run on an external base in place of
aircargo: the archive, the corpus and its manifest are those of DIR, as
scripts/external_base.py wrote them; the tenant is the base's; and the questions are one
registered selection of the base (evaluation/external_parts.json), read from
DIR/selections/NAME.questions.jsonl. A selection of a part that acceptance has not opened is
refused, so no run reads a locked part.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import http.client
import json
import math
import platform
import re
import sys
import time
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx

from evaluation.devset_sources import corpus_directory, read_sources
from evaluation.judge_contract import _validate_chunk_address
from llm.providers.base import ProviderUnavailable
from llm.providers.pinned_ollama import OllamaUnreachable
from scripts import production_parity as parity
from vectordb import contextual_header

STAGES = ("prepare", "transform", "embed", "retrieve", "grade")
ARCHIVE = "gr1b-4436d61-graph-chunks"
PROVENANCE_FIELDS = (
    "corpus_sha256",
    "code_sha",
    "config",
    "model",
    "reranker",
    "graph_digest",
    "entity_graph_status",
    "cached_contexts",
    "raw_judge_replies",
    "bootstrap_seed",
    "host",
    "ingestion_snapshot_id",
    "chunker_version",
    "effective_queries",
    "routing_mode",
    "generator_fingerprint",
    "embedder_manifest",
    "embedder_load_check",
    "fact_matcher_version",
    "judge_model",
    "judge_revision",
    "rubric_version",
    "label_migration_report",
    "residency_mode",
    "peak_host_rss",
    "peak_rss_bytes",
    "ledger_entry",
    "metrics",
    "stage_aborts",
)
DECIDING_METRICS = (
    "sent_precision",
    "all_evidence_coverage",
    "precision_at_5",
    "evidence_recall_pool",
    "fact_coverage",
    "abstention_correct",
    "faithfulness",
    "answer_fact_coverage",
    "citation_correctness",
    "citation_presence",
    "action_correct",
    "critical_errors",
    "context_precision",
    "retrieve_p95",
)
T65 = "N/A: filled by T-65"
TASK = "T-68/2.5a"
SETTABLE = ("retrieval_top_k", "rerank_top_k")


class IntegrityError(ValueError):
    """A registered input or replay contract no longer holds."""


class ModelFailure(RuntimeError):
    """A single model-side case failure, eligible for recorded exclusion."""


class BaselineCache(parity.ReplayCache):
    def __init__(self, root: Path, identity: str):
        super().__init__(root, identity)
        self.calls: list[dict[str, Any]] = []

    def call(self, kind: str, request: Any, compute: Any = None, decode: Any = None) -> Any:
        def model_call():
            try:
                return compute()
            except Exception as exc:
                if isinstance(exc, IntegrityError):
                    raise
                if isinstance(
                    exc,
                    (
                        OllamaUnreachable,
                        ProviderUnavailable,
                        OSError,
                        urllib.error.URLError,
                        http.client.HTTPException,
                        httpx.TransportError,
                    ),
                ):
                    raise IntegrityError(f"{kind} environment: {exc}") from exc
                if isinstance(exc, ValueError) and "digest mismatch" in str(exc):
                    raise IntegrityError(str(exc)) from exc
                raise ModelFailure(f"{kind}: {type(exc).__name__}: {exc}") from exc

        try:
            result = super().call(
                kind, request, model_call if compute is not None else None, decode
            )
        except (IntegrityError, ModelFailure):
            raise
        except Exception as exc:
            raise IntegrityError(f"{kind} cache: {exc}") from exc
        key = parity.digest({"run": self.identity, "request": request})
        self.calls.append(
            {
                "kind": kind,
                "request_sha256": parity.digest(request),
                "cache_file": f"cache/{kind}-{key}.json",
            }
        )
        return result

    def require_clean(self) -> None:
        # Production nodes catch model errors. Preserve the actual cache cause.
        for exc in self.exceptions:
            if not isinstance(exc, ModelFailure):
                raise IntegrityError(str(exc)) from exc
        if self.exceptions:
            raise self.exceptions[0]


def make_llm(cache: BaselineCache, manifest: dict) -> Any:
    from llm.providers import pinned_ollama

    resolve = pinned_ollama.resolve_ollama_digest

    def checked_digest(*args, **kwargs):
        try:
            digest = resolve(*args, **kwargs)
            if digest != manifest["llm"]["digest"]:
                raise ValueError("LLM digest mismatch")
            return digest
        except Exception as exc:
            raise IntegrityError(f"LLM digest identity unavailable: {exc}") from exc

    # parity captures this resolver locally at construction; restore the module immediately.
    with patch.object(pinned_ollama, "resolve_ollama_digest", checked_digest):
        return parity.make_llm(cache, True, manifest)


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class AddressBook:
    def __init__(self, manifest: dict, sources: dict[str, str], chunker_version: str):
        self.revisions = {entry["name"]: entry["sha256"] for entry in manifest["files"]}
        self.sources = sources
        self.chunker_version = chunker_version

    def check_metadata(self, metadata: dict) -> bool:
        source = metadata.get("source")
        revision = self.revisions.get(source)
        content_hash = metadata.get("content_hash")
        if content_hash and revision and content_hash != revision:
            raise IntegrityError(f"source revision mismatch: {source}")
        return bool(revision and content_hash == revision)

    def document(self, doc: dict, seed: dict | None = None) -> dict:
        seed = seed if seed is not None else doc
        metadata = seed.get("metadata") or {}
        text = doc["page_content"]
        record = {
            "text": text,
            "text_sha256": text_sha(text),
            "metadata": doc.get("metadata") or {},
            "chunk_address": None,
            "address_reason": "address_unresolved",
        }
        if not self.check_metadata(metadata):
            return record
        source = metadata["source"]
        address = {
            "source_id": source,
            "source_revision": self.revisions[source],
            "chunker_version": self.chunker_version,
        }
        headings = [
            metadata[key].strip()
            for key in ("h1", "h2", "h3", "h4")
            if isinstance(metadata.get(key), str) and metadata[key].strip()
        ]
        if headings:
            address["section_path"] = headings
        else:
            body = contextual_header.strip(seed["page_content"], metadata)
            header = metadata.get("contextual_header")
            if header and body.startswith(str(header) + "\n"):
                body = body[len(str(header)) + 1 :]
            source_text = self.sources.get(source, "")
            start = source_text.find(body) if body else -1
            if start < 0 or source_text.find(body, start + 1) >= 0:
                return record
            address.update(char_start=start, char_end=start + len(body))
        _validate_chunk_address(address)
        return {**record, "chunk_address": address, "address_reason": None}


def load_address_book(manifest: dict) -> tuple[AddressBook, list[dict]]:
    sources = read_sources(manifest["source_manifest"], Path(manifest["source_directory"]))
    book = AddressBook(manifest["source_manifest"], sources, manifest["chunker_version"])
    payload = json.loads(gzip.decompress(Path(manifest["corpus"]).read_bytes()))
    if "base" in manifest and payload.get("tenant_id") != manifest["base"]["tenant"]:
        raise IntegrityError("The archive belongs to another tenant")
    chunks = payload["chunks"]
    for chunk in chunks:
        book.check_metadata(chunk.get("metadata") or {})
    return book, chunks


def given_settings(pairs: list[str]) -> dict[str, int]:
    """--set key=value: only the two candidate counts of the control may be moved."""
    settings: dict[str, int] = {}
    for pair in pairs:
        key, _, value = pair.partition("=")
        if key not in SETTABLE or key in settings:
            raise IntegrityError(f"Setting is not registered or is repeated: {pair}")
        if not (value.isascii() and value.isdigit() and 1 <= int(value) <= 200):
            raise IntegrityError(f"Setting needs a whole number from 1 to 200: {pair}")
        settings[key] = int(value)
    return settings


def case_file(path: Path, subset: str) -> tuple[dict, list[dict]]:
    """A case file other than H and Hm; its labels stay in the file, out of the run."""
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", subset) or subset in ("H", "Hm"):
        raise IntegrityError("A case file needs a subset name of its own")
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        cases = [
            {
                "case_id": row["case_id"],
                "query": row.get("query", row.get("question")),
                "subset": subset,
            }
            for row in rows
        ]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise IntegrityError(f"Case file unreadable: {type(exc).__name__}: {exc}") from exc
    if not cases or any(not isinstance(c["query"], str) or not c["query"].strip() for c in cases):
        raise IntegrityError("Every case needs a question")
    dataset = {"path": str(path.resolve()), "sha256": parity.file_sha(path), "count": len(cases)}
    return {subset: dataset}, cases


def external_base(name: str, directory: Path, selection: str) -> tuple[dict, Path]:
    """What a run on an external base registers, and the question file of its selection.

    The questions are one registered selection of the base and no other list: the file is held
    to the ids of the selection, in their order, and to the questions of the registered
    conversion. A selection of a locked part is refused.
    """
    from evaluation import external_bases as bases
    from evaluation import external_parts as parts

    try:
        converted = bases.registration()
        drawn = parts.registration()
        if name not in converted["bases"] or selection not in drawn["selections"].get(name, {}):
            raise IntegrityError(f"Unregistered external base or selection: {name}/{selection}")
        base = converted["bases"][name]
        chosen = drawn["selections"][name][selection]
        ids = parts.read(drawn, name, selection=selection)
        query = {c["case_id"]: c["query"] for c in parts.load_cases(directory, name, converted)}
        questions = directory / "selections" / f"{selection}.questions.jsonl"
        rows = [json.loads(line) for line in questions.read_text(encoding="utf-8").splitlines()]
        if [(row["case_id"], row["query"]) for row in rows] != [(cid, query[cid]) for cid in ids]:
            raise IntegrityError("The question file is not the registered selection")
    except IntegrityError:
        raise
    except parts.Locked as exc:
        raise IntegrityError(str(exc)) from exc
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise IntegrityError(f"External base unreadable: {type(exc).__name__}: {exc}") from exc
    block = {
        "name": name,
        "tenant": base["tenant"],
        "collection": base["collection"],
        "revision": base["revision"],
        "corpus_sha256": base["converted"]["corpus_sha256"],
        "directory": str(directory.resolve()),
        "selection": selection,
        "part": chosen["rule"]["part"],
        "cases_sha256": chosen["cases_sha256"],
        "registrations": {
            path.name: {"path": str(path.resolve()), "sha256": parity.file_sha(path)}
            for path in (bases.REGISTRATION, parts.REGISTRATION)
        },
    }
    return block, questions


def registered_sets(root: Path) -> tuple[dict, list[dict]]:
    """H and Hm as registered: every case of both files, whole rows, in file order."""
    datasets = {}
    cases = []
    for subset, filename, count in (
        ("H", "curated_cases_aircargo.jsonl", 100),
        ("Hm", "curated_cases_aircargo_gr_multihop.jsonl", 15),
    ):
        path = root / "evaluation" / filename
        dataset_sha = parity.file_sha(path)
        if (
            subset == "H"
            and dataset_sha != parity.read(path.with_suffix(".manifest.json"))["dataset_sha256"]
        ):
            raise IntegrityError("Dataset manifest mismatch")
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if len(rows) != count:
            raise IntegrityError(f"{subset} requires {count} cases")
        cases.extend({**case, "subset": subset} for case in rows)
        datasets[subset] = {"path": str(path.resolve()), "sha256": dataset_sha, "count": count}
        if subset == "H":
            dataset_manifest = path.with_suffix(".manifest.json")
            datasets[subset].update(
                manifest_path=str(dataset_manifest.resolve()),
                manifest_sha256=parity.file_sha(dataset_manifest),
            )
    return datasets, cases


def prepare(args: Any) -> None:
    cases_path = getattr(args, "cases", None)
    subset = getattr(args, "subset", None)
    if (cases_path is None) != (subset is None):
        raise IntegrityError("--cases and --subset name one case file together")
    settings = given_settings(getattr(args, "settings", None) or [])
    named = [getattr(args, key, None) for key in ("base", "base_dir", "selection")]
    block = None
    if any(value is not None for value in named):
        if None in named or cases_path is not None or getattr(args, "task", None) is None:
            raise IntegrityError(
                "--base, --base-dir, --selection and --task name one run on an external base;"
                " its questions are the selection's, not a --cases file"
            )
        block, cases_path = external_base(*named)
        subset = block["selection"]
    task = getattr(args, "task", None) or TASK
    if args.run.exists():
        if not args.resume:
            raise FileExistsError("Run exists; explicit --resume required")
        manifest = load_manifest(args.run)
        if (
            manifest["index"] != str(args.index.resolve())
            or manifest["checkpoint"] != str(args.checkpoint.resolve())
            or manifest["code_sha"] != args.code_sha
            or manifest.get("config_overrides", {}) != settings
            or manifest.get("base") != block
            or manifest["ledger_entry"]["task"] != task
            or sorted(manifest["datasets"]) != ([subset] if cases_path else ["H", "Hm"])
            or (cases_path and manifest["datasets"][subset]["path"] != str(cases_path.resolve()))
        ):
            raise IntegrityError("Prepare registration mismatch")
        validate_inputs(manifest)
        for case in manifest["cases"]:
            target = args.run / "prepare" / (case["case_id"] + ".json")
            if target.exists():
                parity.load_stage(target, parity.digest(manifest))
            else:
                parity.save_stage(target, {"status": "ok", "case": case}, parity.digest(manifest))
        return
    root = Path.cwd()
    if cases_path is None:
        datasets, cases = registered_sets(root)
        selection = "all H then Hm in file order"
    else:
        datasets, cases = case_file(cases_path, subset)
        selection = f"all {subset} in file order; case_id and question only"
    ids = [c["case_id"] for c in cases]
    if len(set(ids)) != len(ids) or any(
        not isinstance(cid, str) or not cid or cid in (".", "..") or "/" in cid or "\\" in cid
        for cid in ids
    ):
        raise IntegrityError("Case IDs must be unique safe filenames")
    if len(args.code_sha) != 40 or any(c not in "0123456789abcdef" for c in args.code_sha):
        raise IntegrityError("A full code SHA is required")
    receipt_path = args.index / "index-receipt.json"
    receipt = parity.read(receipt_path)
    if block is None:
        archive = root / "evaluation" / (ARCHIVE + ".json.gz")
        source_manifest_path = root / "evaluation/aircargo_corpus.manifest.json"
        source_directory = corpus_directory()
        chunker_version = ARCHIVE + ":" + receipt["corpus_sha256"]
    else:
        folder = Path(block["directory"])
        archive = folder / "chunks.json.gz"
        source_manifest_path = folder / "corpus.manifest.json"
        source_directory = folder / "corpus"
        chunker_version = block["tenant"] + "-chunks:" + receipt["corpus_sha256"]
    for path, expected in (
        (archive, receipt["corpus_sha256"]),
        (args.checkpoint, receipt["checkpoint_sha256"]),
    ):
        if parity.file_sha(path) != expected:
            raise IntegrityError("Corpus/checkpoint mismatch")
    source_manifest = parity.read(source_manifest_path)
    if block is not None and (
        receipt.get("collection_name") != block["collection"]
        or source_manifest.get("corpus_sha256") != block["corpus_sha256"]
    ):
        raise IntegrityError("The index or the corpus is not the registered base's")
    config = {**parity.CONFIG, **settings}
    manifest = {
        "schema_version": 1,
        "code_sha": args.code_sha,
        "source_sha256": parity.source_identity(root),
        "runtime": parity.runtime_identity(),
        "datasets": datasets,
        "cases": cases,
        "selection": selection,
        "config": config,
        "index": str(args.index.resolve()),
        "checkpoint": str(args.checkpoint.resolve()),
        "corpus": str(archive.resolve()),
        "index_receipt": receipt,
        "index_receipt_sha256": parity.file_sha(receipt_path),
        "source_manifest": source_manifest,
        "source_manifest_path": str(source_manifest_path.resolve()),
        "source_manifest_sha256": parity.file_sha(source_manifest_path),
        "source_directory": str(source_directory.resolve()),
        "chunker_version": chunker_version,
        "llm": {"model": parity.MODEL, "digest": parity.DIGEST, "provider": "OllamaProvider"},
        "reranker": {"model": "BAAI/bge-reranker-v2-m3", "revision": parity.RERANK_REVISION},
        "ledger_entry": {
            "task": task,
            "config_sha256": parity.digest(config),
            "datasets": datasets,
            "status": "registered",
            "file": "ledger-entry.json",
        },
    }
    if settings:
        manifest["config_overrides"] = settings
    if block is not None:
        manifest["base"] = block
    load_address_book(manifest)
    args.run.mkdir(parents=True, exist_ok=False)
    parity.write_new(args.run / "manifest.json", manifest)
    parity.write_new(args.run / "registration.json", {"manifest_sha256": parity.digest(manifest)})
    parity.save_stage(
        args.run / "ledger-entry.json", manifest["ledger_entry"], parity.digest(manifest)
    )
    for case in cases:
        parity.save_stage(
            args.run / "prepare" / (case["case_id"] + ".json"),
            {"status": "ok", "case": case},
            parity.digest(manifest),
        )


def load_manifest(run: Path) -> dict:
    try:
        manifest = parity.read(run / "manifest.json")
    except FileNotFoundError as exc:
        if not (run / "registration.json").exists():
            raise  # never prepared: a usage error, not a stop
        raise IntegrityError("Manifest integrity mismatch") from exc
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise IntegrityError("Manifest integrity mismatch") from exc
    try:
        registered = parity.read(run / "registration.json")["manifest_sha256"]
        if registered != parity.digest(manifest):
            raise IntegrityError("Manifest integrity mismatch")
    except IntegrityError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise IntegrityError("Manifest integrity mismatch") from exc
    return manifest


def load_case(path: Path, identity: str, run: Path) -> dict:
    try:
        row = parity.load_stage(path, identity)
    except FileNotFoundError:
        raise
    except (ValueError, KeyError, TypeError) as exc:
        raise IntegrityError(f"Stage record integrity mismatch: {path}") from exc
    for call in row.get("model_calls", []):
        cache_path = run / call["cache_file"]
        try:
            record = parity.read(cache_path)
            key = parity.digest({"run": identity, "request": record["request"]})
            if (
                record["key"] != key
                or record["value_sha256"] != parity.digest(record["value"])
                or call["request_sha256"] != parity.digest(record["request"])
                or cache_path.name != f"{call['kind']}-{key}.json"
            ):
                raise IntegrityError("Referenced cache integrity mismatch")
        except IntegrityError:
            raise
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise IntegrityError(f"Referenced cache integrity mismatch: {cache_path.name}") from exc
    return row


def validate_inputs(manifest: dict) -> None:
    try:
        if parity.source_identity(Path.cwd()) != manifest["source_sha256"]:
            raise IntegrityError("Source changed since registration")
        if parity.runtime_identity() != manifest["runtime"]:
            raise IntegrityError("Runtime changed since registration")
        expected_inputs = [
            (Path(manifest["corpus"]), manifest["index_receipt"]["corpus_sha256"]),
            (
                Path(manifest["checkpoint"]),
                manifest["index_receipt"]["checkpoint_sha256"],
            ),
            (
                Path(manifest["index"]) / "index-receipt.json",
                manifest["index_receipt_sha256"],
            ),
            (
                Path(manifest["source_manifest_path"]),
                manifest["source_manifest_sha256"],
            ),
        ]
        expected_inputs.extend(
            (Path(d["path"]), d["sha256"]) for d in manifest["datasets"].values()
        )
        expected_inputs.extend(
            (Path(d["manifest_path"]), d["manifest_sha256"])
            for d in manifest["datasets"].values()
            if "manifest_path" in d
        )
        expected_inputs.extend(
            (Path(d["path"]), d["sha256"])
            for d in manifest.get("base", {}).get("registrations", {}).values()
        )
        for path, expected in expected_inputs:
            if parity.file_sha(path) != expected:
                raise IntegrityError(f"Input changed since registration: {path}")
        load_address_book(manifest)
    except IntegrityError:
        raise
    except Exception as exc:
        raise IntegrityError(f"Input check failed: {type(exc).__name__}: {exc}") from exc


def make_retriever(manifest: dict, cache: BaselineCache) -> tuple[Any, dict]:
    retriever, probe = parity.make_retriever(manifest, cache, "chroma", True)
    original_expand = retriever._expand_parents
    original_rank = retriever._rerank_scored_with_status
    original_search = retriever._vector_store.similarity_search
    original_merge = retriever._rrf_merge

    def merge(vector_results, lexical_results, *more):
        # The lexical lane as it enters the fusion. An empty lane is not merged at all.
        probe["bm25"] = [d.metadata["chunk_index"] for d in lexical_results]
        return original_merge(vector_results, lexical_results, *more)

    def vector_search(*args, **kwargs):
        try:
            result = original_search(*args, **kwargs)
        except Exception as exc:
            probe["vector_error"] = exc
            raise
        probe["vector_query_ok"] = True
        return result

    def expand(docs):
        started = time.perf_counter()
        result = original_expand(docs)
        probe["expansion_ms"] = (time.perf_counter() - started) * 1000
        probe["expanded"] = [
            {"page_content": d.page_content, "metadata": d.metadata} for d in result
        ]
        return result

    def ranked(query, docs):
        try:
            result, ok = original_rank(query, docs)
        except RuntimeError as exc:
            if "Reranker fallback" not in str(exc):
                raise
            cache.require_clean()
            raise ModelFailure(str(exc)) from exc
        probe.setdefault("bm25", [])
        probe["ranked_scores"] = [score for _, score in result]
        probe["seeds"] = [
            {"page_content": d.page_content, "metadata": d.metadata} for d, _ in result
        ]
        return result, ok

    retriever._expand_parents = expand
    retriever._rerank_scored_with_status = ranked
    retriever._vector_store.similarity_search = vector_search
    retriever._rrf_merge = merge
    return retriever, probe


def checked_state(state: dict, cache: BaselineCache) -> None:
    cache.require_clean()
    try:
        parity.checked_state(state, cache)
    except ValueError as exc:
        raise ModelFailure(str(exc)) from exc


def peak_rss() -> int | None:
    try:
        import resource
    except ImportError:
        return None

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if platform.system() == "Darwin" else value * 1024)


def documents(row: dict, book: AddressBook, chunks: list[dict]) -> list[dict]:
    result = []
    for text, metadata in zip(row["cands"], row["cand_metadata"], strict=True):
        index = metadata.get("chunk_index")
        seed = chunks[index] if type(index) is int and 0 <= index < len(chunks) else None
        result.append(book.document({"page_content": text, "metadata": metadata}, seed))
    return result


def archive_abort(run: Path, stage: str) -> None:
    marker = run / (stage + ".abort.json")
    if not marker.exists():
        return
    history = run / "aborts"
    history.mkdir(exist_ok=True)
    number = 1
    while (history / f"{stage}-{number}.json").exists():
        number += 1
    marker.rename(history / f"{stage}-{number}.json")


def require_no_aborts(run: Path, stages: tuple[str, ...]) -> None:
    for stage in stages:
        marker = run / (stage + ".abort.json")
        if marker.exists():
            stop = parity.read(marker)
            raise IntegrityError(f"Open abort at {stage}: {stop['reason']}")


def check_start(args: Any) -> None:
    marker = args.run / f"{args.stage}.abort.json"
    if marker.exists() and not args.resume:
        raise FileExistsError("Stage aborted; explicit --resume required")
    require_no_aborts(args.run, STAGES[: STAGES.index(args.stage)])


def registered_identity(run: Path) -> str:
    try:
        registered = parity.read(run / "registration.json")["manifest_sha256"]
        if (
            isinstance(registered, str)
            and len(registered) == 64
            and all(c in "0123456789abcdef" for c in registered)
        ):
            return registered
    except Exception:
        pass
    return "N/A: registration unreadable"


def record_stop(
    run: Path, stage: str, exc: Exception, identity: str, streak_records: list[dict]
) -> None:
    archive_abort(run, stage)
    parity.write_new(
        run / f"{stage}.abort.json",
        {
            "stage": stage,
            "reason": str(exc),
            "error_type": type(exc).__name__,
            "cause_type": type(exc.__cause__).__name__ if exc.__cause__ else None,
            "run_sha256": identity,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "streak_records": streak_records,
        },
    )
    for row in streak_records:
        target = run / stage / (row["case_id"] + ".json")
        if target.exists():
            target.unlink()


def run_stage(args: Any, manifest: dict) -> None:
    stage = args.stage
    if stage not in STAGES[1:]:
        raise ValueError("Invalid processing stage")
    identity = parity.digest(manifest)
    check_start(args)
    streak: list[dict] = []
    progress = {"started": False}
    try:
        _run_stage(args, manifest, streak, progress)
    except Exception as exc:
        if not progress["started"] and isinstance(exc, (FileExistsError, FileNotFoundError)):
            raise
        record_stop(args.run, stage, exc, identity, streak if len(streak) >= 3 else [])
        raise
    if args.resume:
        archive_abort(args.run, stage)
    if stage == "grade":
        report(args.run, manifest, args.resume)


def _run_stage(args: Any, manifest: dict, streak: list[dict], progress: dict) -> None:
    from agent import graph
    from agent.state import create_initial_state

    if args.stage not in STAGES[1:]:
        raise ValueError("Invalid processing stage")
    parity.configure(manifest)
    book, chunks = load_address_book(manifest)
    identity = parity.digest(manifest)
    stage = args.stage
    # Check all existing records before loading a model or issuing any request.
    pending = []
    previous_rows = {}
    for case in manifest["cases"]:
        target = args.run / stage / (case["case_id"] + ".json")
        if target.exists():
            if not args.resume:
                raise FileExistsError("Stage output exists; explicit --resume required")
            load_case(target, identity, args.run)
        else:
            pending.append(case)
    if stage != "transform":
        previous_stage = STAGES[STAGES.index(stage) - 1]
        active = []
        for case in pending:
            cid = case["case_id"]
            previous = load_case(args.run / previous_stage / (cid + ".json"), identity, args.run)
            if previous["status"] == "excluded":
                parity.save_stage(args.run / stage / (cid + ".json"), previous, identity)
            else:
                previous_rows[cid] = previous
                active.append(case)
        pending = active
    if not pending:
        return
    # The preflight is done: from here on, a failure is a stop, not a refusal.
    progress["started"] = True
    cache = BaselineCache(args.run / "cache", identity)
    llm = None
    pending_ids = {case["case_id"] for case in pending}
    try:
        if stage in ("transform", "grade"):
            llm = make_llm(cache, manifest)
        if stage == "embed":
            from vectordb._base_manager import get_embeddings

            embedder = get_embeddings(manifest["index_receipt"]["embedder_manifest"]["model_id"])
            if embedder.manifest.as_dict() != manifest["index_receipt"]["embedder_manifest"]:
                raise IntegrityError("Loaded query embedder mismatch")
        if stage == "retrieve":
            retriever, probe = make_retriever(manifest, cache)
        for case in manifest["cases"]:
            cid = case["case_id"]
            target = args.run / stage / (cid + ".json")
            if cid not in pending_ids:
                row = load_case(target, identity, args.run)
                if row["status"] != "excluded":
                    streak.clear()
                elif row["exclusion"]["stage"] == stage:
                    if (
                        streak
                        and streak[-1]["exclusion"]["error_type"] != row["exclusion"]["error_type"]
                    ):
                        streak.clear()
                    streak.append(row)
                # An exclusion forwarded from an earlier stage neither extends nor breaks a streak.
                continue
            cache.failures.clear()
            cache.exceptions.clear()
            cache.calls.clear()
            previous = previous_rows.get(cid)
            started = time.perf_counter()
            timings = dict(previous.get("timings_ms", {})) if previous else {}
            try:
                if stage == "transform":
                    state = create_initial_state(case["query"], tenant_id=parity.tenant(manifest))
                    state = graph.make_classify_complexity_node(llm)(state)
                    state = graph.make_transform_query_node(llm)(state)
                    checked_state(state, cache)
                    result = parity.export(case, state, {})
                    result["routing_mode"] = "hybrid; graph off; model routing off; single-turn"
                elif stage == "embed":
                    state = previous["state"]
                    query = state.get("hyde_query") or state["search_query"]
                    vector = cache.call("embedding", query, lambda: embedder.embed_query(query))
                    parity.validate_vector(vector, embedder.manifest.dimension)
                    result = {
                        **previous,
                        "query": query,
                        "vector_sha256": parity.digest(vector),
                        "embedder_load_check": "eligible: exact manifest match",
                    }
                elif stage == "retrieve":
                    state = previous["state"]
                    query = state.get("hyde_query") or state["search_query"]
                    vector = cache.call("embedding", query)
                    if previous["query"] != query or previous["vector_sha256"] != parity.digest(
                        vector
                    ):
                        raise IntegrityError("Embedding stage/cache mismatch")
                    probe.clear()
                    routes = []
                    original_log = graph.log_step

                    def traced(trace_id, name, payload, *a, **kw):
                        if name == "retrieval_route":
                            routes.append(payload)
                        return original_log(trace_id, name, payload, *a, **kw)

                    graph.log_step = traced
                    try:
                        state = graph.make_retrieve_node(retriever)(dict(state))
                    finally:
                        graph.log_step = original_log
                    if "vector_error" in probe:
                        raise IntegrityError("Chroma vector query failed") from probe[
                            "vector_error"
                        ]
                    if not probe.get("vector_query_ok"):
                        raise IntegrityError("Missing successful vector query confirmation")
                    checked_state(state, cache)
                    if probe.get("path", {}).get("rerank_status") != "ok":
                        raise ModelFailure("Missing successful retrieval path / reranker fallback")
                    result = parity.export(case, state, dict(probe))
                    result["routing"] = (
                        routes[-1]
                        if routes
                        else {
                            "configured": "hybrid",
                            "selected": "hybrid",
                            "effective": state.get("retrieval_strategy"),
                            "reason": "N/A: retrieval route trace missing",
                        }
                    )
                    result["routing_mode"] = previous["routing_mode"]
                    result["embedder_load_check"] = previous["embedder_load_check"]
                    result["documents"] = documents(result, book, chunks)
                    result["expanded_documents"] = [
                        book.document(d, chunks[d["metadata"]["chunk_index"]])
                        for d in probe.get("expanded", [])
                    ]
                    if not result["expanded_documents"]:
                        result["expanded_documents"] = result["documents"]
                    result["seed_documents"] = [book.document(d) for d in probe.get("seeds", [])]
                    timings.update(probe["path"]["timings_ms"])
                    timings["expansion"] = probe.get("expansion_ms", 0.0)
                else:
                    state = graph.make_grade_docs_node(llm)(previous["state"])
                    checked_state(state, cache)
                    result = {**previous, **parity.export(case, state, {})}
                    result["documents"] = documents(result, book, chunks)
                timings[stage] = (time.perf_counter() - started) * 1000
                result.update(
                    status="ok",
                    timings_ms=timings,
                    model_calls=(previous.get("model_calls", []) if previous else []) + cache.calls,
                    host=platform.node(),
                )
            except ModelFailure as exc:
                timings[stage] = (time.perf_counter() - started) * 1000
                result = {
                    **(previous or {}),
                    "case_id": cid,
                    "status": "excluded",
                    "exclusion": {
                        "case_id": cid,
                        "subset": case["subset"],
                        "stage": stage,
                        "reason": str(exc),
                        "error_type": type(exc.__cause__ or exc).__name__,
                    },
                    "timings_ms": timings,
                    "query_effective": previous.get("query_effective", "N/A: transform failed")
                    if previous
                    else "N/A: transform failed",
                    "query_transform": previous.get("query_transform")
                    if previous
                    else "N/A: transform failed",
                    "query_transform_hash": previous.get("query_transform_hash")
                    if previous
                    else "N/A: transform failed",
                    "routing_mode": "hybrid; graph off; model routing off; single-turn",
                    "model_calls": (previous.get("model_calls", []) if previous else [])
                    + cache.calls,
                    "host": platform.node(),
                }
            rss_by_stage = dict(previous.get("peak_rss_by_stage", {})) if previous else {}
            rss_by_stage[stage] = peak_rss()
            rss_values = [value for value in rss_by_stage.values() if value is not None]
            if previous and previous.get("peak_rss_bytes") is not None:
                rss_values.append(previous["peak_rss_bytes"])
            result["peak_rss_by_stage"] = rss_by_stage
            result["peak_rss_bytes"] = max(rss_values, default=None)
            if result["status"] == "excluded" and result["exclusion"]["stage"] == stage:
                error_type = result["exclusion"]["error_type"]
                if streak and streak[-1]["exclusion"]["error_type"] != error_type:
                    streak.clear()
                streak.append(result)
                if len(streak) >= 3:
                    raise IntegrityError(
                        f"{stage}: consecutive exclusions — environment suspected ({error_type})"
                    )
            else:
                streak.clear()
            parity.save_stage(target, result, identity)
            print(f"{stage} {cid} {result['status']}", flush=True)
    finally:
        if llm is not None:
            stage_error = sys.exc_info()[1]
            try:
                parity.unload_llm()
            except Exception as exc:
                if stage_error is None:
                    raise IntegrityError(f"LLM unload environment: {exc}") from exc


def percentiles(values: list[float]) -> dict:
    values = sorted(values)

    def percentile(p):
        position = (len(values) - 1) * p
        low, high = math.floor(position), math.ceil(position)
        return values[low] + (values[high] - values[low]) * (position - low)

    return {"n": len(values), "p50": percentile(0.5), "p95": percentile(0.95)}


def report(run: Path, manifest: dict, resume: bool) -> None:
    require_no_aborts(run, STAGES)
    identity = parity.digest(manifest)
    target = run / "report.json"
    if target.exists():
        if not resume:
            raise FileExistsError("Report exists; explicit --resume required")
        parity.load_stage(target, identity)
        return
    rows = [
        load_case(run / "grade" / (c["case_id"] + ".json"), identity, run)
        for c in manifest["cases"]
    ]
    valid = [(c, r) for c, r in zip(manifest["cases"], rows, strict=True) if r["status"] == "ok"]
    timings: dict[str, list[float]] = {}
    for row in rows:
        for stage, duration in row["timings_ms"].items():
            timings.setdefault(stage, []).append(duration)
    rss_values = [
        value
        for row in rows
        for value in [row.get("peak_rss_bytes"), *row.get("peak_rss_by_stage", {}).values()]
        if value is not None
    ]
    provenance = {
        "corpus_sha256": manifest["source_manifest"].get("corpus_sha256", "N/A: fixture manifest"),
        "archive_sha256": manifest["index_receipt"]["corpus_sha256"],
        "code_sha": manifest["code_sha"],
        "datasets": manifest["datasets"],
        "config": {**manifest["config"], "RAG_RERANK_BATCH": manifest["config"]["rerank_batch"]},
        "model": manifest["llm"],
        "reranker": manifest["reranker"],
        "graph_digest": "N/A: graph off",
        "entity_graph_status": "N/A: graph off",
        "cached_contexts": [
            {
                "case_id": c["case_id"],
                "file": "grade/" + c["case_id"] + ".json",
                "sent_context_sha256": r["sent_context_sha256"],
            }
            for c, r in valid
        ],
        "raw_judge_replies": T65
        + "; production LLM replies retained in per-case model_calls cache files",
        "bootstrap_seed": T65,
        "host": sorted({r["host"] for r in rows}),
        "runtime": manifest["runtime"],
        "ingestion_snapshot_id": manifest["index_receipt"]["corpus_sha256"],
        "chunker_version": manifest["chunker_version"],
        "effective_queries": [
            {
                "case_id": c["case_id"],
                "query_effective": r.get("query_effective", "N/A: excluded before transform"),
                "query_transform": r.get("query_transform", "N/A: excluded before transform"),
                "query_transform_hash": r.get(
                    "query_transform_hash", "N/A: excluded before transform"
                ),
                "routing_mode": r.get(
                    "routing_mode", "hybrid; graph off; model routing off; single-turn"
                ),
            }
            for c, r in zip(manifest["cases"], rows, strict=True)
        ],
        "routing_mode": "hybrid; graph off; model routing off; single-turn",
        "generator_fingerprint": "N/A: no generation",
        "embedder_manifest": manifest["index_receipt"]["embedder_manifest"],
        "embedder_load_check": [r["embedder_load_check"] for _, r in valid]
        or "N/A: no eligible cases",
        "fact_matcher_version": T65,
        "judge_model": T65,
        "judge_revision": T65,
        "rubric_version": T65,
        "label_migration_report": "N/A: unchanged registered corpus; no label migration",
        "residency_mode": "separate stage processes; LLM unloaded after transform and grade; CPU embed/rerank",
        "peak_host_rss": "N/A: collector process peak measured; external Ollama/host peak requires T-65 monitoring",
        "peak_rss_bytes": max(rss_values) if rss_values else "N/A: resource module unavailable",
        "peak_rss_scope": "collector process only; excludes external Ollama",
        "ledger_entry": manifest["ledger_entry"],
        "metrics": {
            name: {field: T65 for field in ("n", "clusters", "MDE", "achieved_power")}
            for name in DECIDING_METRICS
        },
        "stage_aborts": [
            {
                "stage": stop["stage"],
                "reason": stop["reason"],
                "error_type": stop["error_type"],
                "streak_case_ids": [row["case_id"] for row in stop["streak_records"]],
            }
            for path in sorted((run / "aborts").glob("*.json"))
            for stop in [parity.read(path)]
        ],
    }
    if "base" in manifest:
        provenance["base"] = manifest["base"]
    parity.save_stage(
        target,
        {
            "manifest_sha256": identity,
            "provenance": provenance,
            "total_cases": len(rows),
            "denominator": len(valid),
            "denominators": {
                subset: sum(c["subset"] == subset for c, _ in valid)
                for subset in dict.fromkeys(c["subset"] for c in manifest["cases"])
            },
            "exclusions": [r["exclusion"] for r in rows if r["status"] == "excluded"],
            "documents_without_address": sum(
                d["chunk_address"] is None for _, r in valid for d in r["documents"]
            ),
            "expanded_documents_without_address": sum(
                d["chunk_address"] is None for _, r in valid for d in r["expanded_documents"]
            ),
            "timings_ms": {stage: percentiles(values) for stage, values in timings.items()},
            "timing_scope": "one run on one host, not speed evidence; failed attempts included",
            "latency_evidence": False,
            "quality_metrics": "N/A: collection only; filled by T-65",
        },
        identity,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--code-sha")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--subset")
    parser.add_argument("--task")
    parser.add_argument("--set", action="append", default=[], dest="settings", metavar="KEY=VALUE")
    parser.add_argument("--base", help="a registered external base, in place of aircargo")
    parser.add_argument("--base-dir", type=Path, help="the directory of the converted base")
    parser.add_argument("--selection", help="a registered selection of the base")
    args = parser.parse_args(argv)
    arm = (args.cases, args.subset, args.task, args.settings)
    if args.stage == "prepare":
        if not all((args.index, args.checkpoint, args.code_sha)):
            parser.error("prepare requires --index, --checkpoint and --code-sha")
        prepare(args)
    elif any(arm) or args.base or args.base_dir or args.selection:
        parser.error("--cases, --subset, --task, --set and the --base options belong to prepare")
    else:
        check_start(args)
        try:
            manifest = load_manifest(args.run)
            validate_inputs(manifest)
        except IntegrityError as exc:
            record_stop(args.run, args.stage, exc, registered_identity(args.run), [])
            raise
        run_stage(args, manifest)
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
