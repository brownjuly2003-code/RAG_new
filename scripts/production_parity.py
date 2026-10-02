"""Bounded Chroma/exact comparison, with sequential real-model stages on the Mac.

Stages: prepare, transform, embed, retrieve, grade, verify. Saved provider replies
are replayed through ConversationSession; replay timings are NOT API latency.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import platform
from dataclasses import asdict
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace
from typing import Any

CONFIG = {
    "retrieval_strategy": "hybrid", "model_routing_enabled": False,
    "graph_retrieval": "off", "hyde": False, "agentic_mode": False,
    "retrieval_top_k": 20, "rerank_top_k": 5, "rrf_k": 60,
    "rrf_doc_key_chars": 200, "rerank_batch": 8,
    "parent_expansion": True, "parent_expansion_window": 2,
    "parent_expansion_max_chars": 3600, "ask_budget_sec": 0,
    "llm_role_params_json": "", "llm_max_calls_per_request": 24,
    "llm_max_input_tokens_per_request": 48000,
    "llm_max_output_tokens_per_request": 8000,
    "llm_max_total_tokens_per_request": 50000,
    "rag_device": "cpu", "embedding_backend": "local",
}
MODEL = "qwen2.5:7b"
DIGEST = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
RERANK_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
BASE_URL = "http://127.0.0.1:11434"


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def save_stage(path: Path, result: Any, identity: str) -> None:
    write_new(path, {"run_sha256": identity, "result": result, "result_sha256": digest(result)})


def load_stage(path: Path, identity: str) -> Any:
    record = read(path)
    if record["run_sha256"] != identity or record["result_sha256"] != digest(record["result"]):
        raise ValueError("Stage integrity mismatch")
    return record["result"]


def select_cases(cases: list[dict], count: int) -> list[dict]:
    ids = [case["case_id"] for case in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("Case IDs must be unique")
    if not 1 <= count <= len(cases):
        raise ValueError("Invalid case count")
    return sorted(cases, key=lambda c: hashlib.sha256(c["case_id"].encode()).hexdigest())[:count]


class ReplayCache:
    def __init__(self, root: Path, identity: str):
        self.root = root
        self.identity = identity
        self.failures: list[str] = []
        self.exceptions: list[Exception] = []

    def call(self, kind: str, request: Any, compute: Any = None, decode: Any = None) -> Any:
        key = digest({"run": self.identity, "request": request})
        path = self.root / f"{kind}-{key}.json"
        try:
            if path.exists():
                record = read(path)
                if record["key"] != key or record["value_sha256"] != digest(record["value"]):
                    raise ValueError("Cache integrity mismatch")
                value = record["value"]
            elif compute is None:
                raise RuntimeError(f"Replay cache miss: {kind}/{key}")
            else:
                value = compute()
                write_new(path, {"key": key, "request": request, "value": value,
                                 "value_sha256": digest(value)})
            return decode(value) if decode is not None else value
        except Exception as exc:
            self.failures.append(f"{kind}/{key}")
            self.exceptions.append(exc)
            raise

    def require_clean(self) -> None:
        if self.failures:
            failure = RuntimeError(f"Model/cache calls failed: {self.failures}")
            raise failure from self.exceptions[0]


def validate_vector(vector: list[float], dimension: int) -> None:
    if (len(vector) != dimension or not all(math.isfinite(v) for v in vector)
            or abs(math.sqrt(sum(v * v for v in vector)) - 1) > 1e-4):
        raise ValueError("Invalid query vector")


def differences(left: dict, right: dict) -> list[str]:
    return [key for key in (
        "vector", "pool", "ranked", "query_effective", "query_transform",
        "query_transform_hash", "sent_context_sha256",
    ) if left[key] != right[key]]


def source_identity(root: Path) -> str:
    files = {}
    for directory in ("agent", "config", "ingestion", "llm", "scripts", "utils", "vectordb"):
        for path in sorted((root / directory).rglob("*.py")):
            files[path.relative_to(root).as_posix()] = file_sha(path)
    return digest(files)


def runtime_identity() -> dict:
    versions = {}
    for name in ("numpy", "torch", "sentence-transformers", "transformers", "chromadb",
                 "langchain-ollama", "langgraph", "rank-bm25"):
        versions[name] = metadata.version(name)
    return {"python": platform.python_version(), "platform": platform.platform(),
            "packages": versions}


def prepare(args: Any) -> None:
    root = Path.cwd()
    cases_path = root / "evaluation/curated_cases_aircargo.jsonl"
    dataset_sha = file_sha(cases_path)
    if dataset_sha != read(cases_path.with_suffix(".manifest.json"))["dataset_sha256"]:
        raise ValueError("Dataset manifest mismatch")
    receipt_path = args.index / "index-receipt.json"
    receipt = read(receipt_path)
    archive = root / "evaluation/gr1b-4436d61-graph-chunks.json.gz"
    if file_sha(archive) != receipt["corpus_sha256"]:
        raise ValueError("Corpus mismatch")
    if file_sha(args.checkpoint) != receipt["checkpoint_sha256"]:
        raise ValueError("Checkpoint mismatch")
    if len(args.code_sha) != 40 or any(c not in "0123456789abcdef" for c in args.code_sha):
        raise ValueError("A full code SHA is required")
    cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines()]
    manifest = {
        "schema_version": 1, "code_sha": args.code_sha,
        "source_sha256": source_identity(root), "dataset_sha256": dataset_sha,
        "runtime": runtime_identity(),
        "selection": "first 30 ascending sha256(case_id)", "cases": select_cases(cases, 30),
        "config": CONFIG, "index": str(args.index.resolve()),
        "checkpoint": str(args.checkpoint.resolve()), "corpus": str(archive.resolve()),
        "index_receipt": receipt, "index_receipt_sha256": file_sha(receipt_path),
        "llm": {"model": MODEL, "digest": DIGEST, "provider": "OllamaProvider",
                "options": "production provider defaults plus graph role kwargs"},
        "reranker": {"model": "BAAI/bge-reranker-v2-m3", "revision": RERANK_REVISION},
        "limits": "staged deterministic replay; no live API latency or generated answers",
    }
    args.run.mkdir(parents=True, exist_ok=False)
    write_new(args.run / "manifest.json", manifest)


def configure(manifest: dict) -> Any:
    from config.settings import get_settings

    settings = get_settings()
    for key, value in manifest["config"].items():
        setattr(settings, key, value)
    settings.embedding_model_revision = manifest["index_receipt"]["embedder_manifest"]["revision"]
    return settings


def make_llm(cache: ReplayCache, live: bool, manifest: dict) -> Any:
    from llm.providers.base import LLMResponse, ProviderBackedLLM, StructuredOutputValidationError
    from llm.providers.ollama import OllamaProvider
    from llm.providers.pinned_ollama import resolve_ollama_digest

    identity = manifest["llm"]
    delegate = OllamaProvider(
        model_name=identity["model"], base_url=BASE_URL, timeout_sec=600,
        input_price_per_1m_tokens=0, output_price_per_1m_tokens=0,
    ) if live else None
    replies: list[Any] = []
    if live:
        # generate_with_schema calls self.generate; the instance wrapper captures that reply.
        bound_generate = delegate.generate

        def recording_generate(messages, *args, **kwargs):
            reply = bound_generate(messages, *args, **kwargs)
            replies.append(reply)
            return reply

        delegate.generate = recording_generate

    def decode(value):
        outcome = value.get("outcome") if isinstance(value, dict) else None
        if outcome == "response":
            return LLMResponse(**value["response"])
        if outcome == "structured_output_invalid":
            return StructuredOutputValidationError(value["error"]["message"])
        raise ValueError("Unknown cached llm outcome")

    class RecordedProvider:
        provider_id = "ollama"
        model_name = identity["model"]

        def call(self, method, messages, schema, kwargs):
            request = {"identity": identity, "method": method, "messages": messages,
                       "schema": schema, "kwargs": kwargs}

            def compute():
                if resolve_ollama_digest(BASE_URL, self.model_name) != identity["digest"]:
                    raise ValueError("LLM digest mismatch before request")
                start = len(replies)
                fn = getattr(delegate, method)
                try:
                    response = fn(messages, schema, **kwargs) if schema else fn(messages, **kwargs)
                except StructuredOutputValidationError as exc:
                    if resolve_ollama_digest(BASE_URL, self.model_name) != identity["digest"]:
                        raise ValueError("LLM digest mismatch after request") from exc
                    if len(replies) - start == 1:
                        return {"outcome": "structured_output_invalid",
                                "error": {"type": "StructuredOutputValidationError",
                                          "message": str(exc)},
                                "raw_response": asdict(replies[start])}
                    raise
                if resolve_ollama_digest(BASE_URL, self.model_name) != identity["digest"]:
                    raise ValueError("LLM digest mismatch after request")
                return {"outcome": "response", "response": asdict(response)}

            result = cache.call("llm", request, compute if live else None, decode)
            if isinstance(result, StructuredOutputValidationError):
                raise result
            return result

        def generate(self, messages, **kwargs):
            return self.call("generate", messages, None, kwargs)

        def generate_with_schema(self, messages, schema, **kwargs):
            return self.call("generate_with_schema", messages, schema, kwargs)

    return ProviderBackedLLM(RecordedProvider())


def unload_llm() -> None:
    import urllib.request

    request = urllib.request.Request(
        BASE_URL + "/api/generate", method="POST",
        data=json.dumps({"model": MODEL, "keep_alive": 0}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


def make_retriever(manifest: dict, cache: ReplayCache, arm: str, live: bool) -> tuple[Any, dict]:
    import chromadb
    import numpy as np
    from chromadb.config import Settings

    from vectordb._base_manager import Document, HybridRetriever
    from vectordb.embedder_manifest import EmbedderManifest, check_collection_manifest

    receipt = manifest["index_receipt"]
    with np.load(manifest["checkpoint"], allow_pickle=False) as data:
        matrix = data["embeddings"]
    payload = json.loads(gzip.decompress(Path(manifest["corpus"]).read_bytes()))
    chunks = [Document(page_content=c["page_content"], metadata=dict(c["metadata"], chunk_index=i))
              for i, c in enumerate(payload["chunks"])]
    client = chromadb.PersistentClient(
        path=str(Path(manifest["index"]) / "chroma"), settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_collection(receipt["collection_name"], embedding_function=None)
    status = check_collection_manifest(
        SimpleNamespace(_collection=collection),
        SimpleNamespace(manifest=EmbedderManifest(**receipt["embedder_manifest"])), tenant_id="aircargo",
    )
    if status["evidence_status"] != "eligible" or collection.count() != len(chunks):
        raise ValueError("Ineligible index")
    from vectordb import manager

    manager._index_manifest_status["aircargo"] = status
    probe: dict[str, Any] = {}

    class Store:
        def similarity_search(self, query, k):
            vector = cache.call("embedding", query)
            validate_vector(vector, receipt["embedder_manifest"]["dimension"])
            if arm == "chroma":
                result = collection.query(query_embeddings=[vector], n_results=k)
                ids = [int(item.removeprefix("chunk-")) for item in result["ids"][0]]
            else:
                ids = np.argsort(-(matrix @ np.asarray(vector, dtype=np.float32)), kind="stable")[:k]
            probe["vector"] = [int(i) for i in ids]
            return [chunks[i] for i in ids]

    encoder = None
    if live:
        from sentence_transformers import CrossEncoder

        snapshot = Path.home() / ".cache/huggingface/hub/models--BAAI--bge-reranker-v2-m3/snapshots"
        encoder = CrossEncoder(str(snapshot / manifest["reranker"]["revision"]), device="cpu")

    class Reranker:
        def predict(self, pairs, **kwargs):
            request = {"model": manifest["reranker"], "pairs": pairs, "kwargs": kwargs}

            def compute():
                values = np.asarray(encoder.predict(pairs, **kwargs)).reshape(-1).tolist()
                if len(values) != len(pairs) or not all(math.isfinite(v) for v in values):
                    raise ValueError("Invalid reranker scores")
                return values

            return cache.call("rerank", request, compute if live else None)

    cfg = manifest["config"]
    retriever = HybridRetriever(
        Store(), chunks, retrieval_k=cfg["retrieval_top_k"], rerank_k=cfg["rerank_top_k"],
        rrf_k=cfg["rrf_k"], doc_key_chars=cfg["rrf_doc_key_chars"], reranker=Reranker(),
        rerank_batch=cfg["rerank_batch"], parent_expansion=cfg["parent_expansion"],
        parent_expansion_window=cfg["parent_expansion_window"],
        parent_expansion_max_chars=cfg["parent_expansion_max_chars"],
    )
    if retriever._bm25 is None:
        raise ValueError("BM25 unavailable")
    original_rank = retriever._rerank_scored_with_status
    original_get = retriever.get_relevant_documents_with_path

    def ranked(query, docs):
        probe["pool"] = [d.metadata["chunk_index"] for d in docs]
        result, ok = original_rank(query, docs)
        if not ok:
            raise RuntimeError("Reranker fallback invalidates measurement")
        probe["ranked"] = [d.metadata["chunk_index"] for d, _ in result]
        return result, ok

    def retrieve(query):
        docs, path = original_get(query)
        probe["path"] = path
        return docs, path

    retriever._rerank_scored_with_status = ranked
    retriever.get_relevant_documents_with_path = retrieve
    return retriever, probe


def checked_state(state: dict, cache: ReplayCache) -> None:
    cache.require_clean()
    if state.get("error") or state.get("route") in ("timeout", "error", "error_escalation"):
        raise ValueError("Pipeline error: " + str(state.get("error_message")))
    if state.get("doc_grade_outcome") in ("grader_error", "partial_grader_error"):
        raise ValueError("Grader error invalidates measurement")


def export(case: dict, state: dict, probe: dict) -> dict:
    from scripts.ab_remote_contextual import production_case

    row = production_case(case, SimpleNamespace(ask=lambda *a, **kw: state), retrieval_only=True)
    return {**row, **probe}


def run_stage(args: Any, manifest: dict) -> None:
    from agent import graph
    from agent.state import create_initial_state

    configure(manifest)
    identity = digest(manifest)
    cache = ReplayCache(args.run / "cache", identity)
    cases = manifest["cases"]
    if args.limit:
        cases = cases[:args.limit]
    stage = args.stage
    if stage in ("transform", "grade"):
        llm = make_llm(cache, True, manifest)
    if stage == "embed":
        from vectordb._base_manager import get_embeddings

        embedder = get_embeddings(manifest["index_receipt"]["embedder_manifest"]["model_id"])
        if embedder.manifest.as_dict() != manifest["index_receipt"]["embedder_manifest"]:
            raise ValueError("Loaded query embedder mismatch")
    retrievers = {}
    if stage in ("retrieve", "verify"):
        # One encoder per process; the second arm shares it through the first retriever.
        retrievers["chroma"] = make_retriever(manifest, cache, "chroma", stage == "retrieve")
        retrievers["exact"] = make_retriever(manifest, cache, "exact", False)
        if stage == "retrieve":
            retrievers["exact"][0]._reranker = retrievers["chroma"][0]._reranker
    try:
        for case in cases:
            cid = case["case_id"]
            target = args.run / stage / (cid + ".json")
            if target.exists():
                if not args.resume:
                    raise FileExistsError("Stage output exists; explicit --resume required")
                load_stage(target, identity)
                continue
            if stage == "transform":
                state = create_initial_state(case["query"], tenant_id="aircargo")
                state = graph.make_classify_complexity_node(llm)(state)
                state = graph.make_transform_query_node(llm)(state)
                checked_state(state, cache)
                result = {"state": state}
            elif stage == "embed":
                state = load_stage(args.run / "transform" / (cid + ".json"), identity)["state"]
                query = state.get("hyde_query") or state["search_query"]
                vector = cache.call("embedding", query, lambda: embedder.embed_query(query))
                validate_vector(vector, embedder.manifest.dimension)
                result = {"query": query, "vector_sha256": digest(vector)}
            elif stage == "retrieve":
                state = load_stage(args.run / "transform" / (cid + ".json"), identity)["state"]
                result = {}
                for arm, (retriever, probe) in retrievers.items():
                    probe.clear()
                    retrieved = graph.make_retrieve_node(retriever)(dict(state))
                    checked_state(retrieved, cache)
                    if probe.get("path", {}).get("rerank_status") != "ok":
                        raise ValueError("Missing successful retrieval path")
                    result[arm] = export(case, retrieved, dict(probe))
            elif stage == "grade":
                result = {}
                for arm, row in load_stage(args.run / "retrieve" / (cid + ".json"), identity).items():
                    state = graph.make_grade_docs_node(llm)(row["state"])
                    checked_state(state, cache)
                    result[arm] = export(case, state, {k: row[k] for k in ("vector", "pool", "ranked", "path")})
            else:
                expected = load_stage(args.run / "grade" / (cid + ".json"), identity)
                result = {}
                for arm, (retriever, probe) in retrievers.items():
                    probe.clear()
                    session = graph.ConversationSession(retriever, make_llm(cache, False, manifest))
                    row = session.ask(case["query"], tenant_id="aircargo", retrieval_only=True)
                    checked_state(row, cache)
                    actual = export(case, row, dict(probe))
                    diff = differences(expected[arm], actual)
                    if diff:
                        raise ValueError(f"Session replay mismatch: {cid}/{arm}: {diff}")
                    result[arm] = actual
                result["chroma_exact_differences"] = differences(result["chroma"], result["exact"])
            save_stage(target, result, identity)
            print(f"{stage} {cid} DONE", flush=True)
    finally:
        if stage in ("transform", "grade"):
            unload_llm()
    if stage == "verify" and not args.limit:
        rows = [load_stage(args.run / "verify" / (c["case_id"] + ".json"), identity)
                for c in manifest["cases"]]
        write_new(args.run / "comparison.json", {
            "manifest_sha256": digest(manifest), "cases": len(rows),
            "session_replay_matches": len(rows) * 2,
            "divergences": {c["case_id"]: r["chroma_exact_differences"]
                            for c, r in zip(manifest["cases"], rows, strict=True)
                            if r["chroma_exact_differences"]},
            "latency_evidence": False,
        })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("prepare", "transform", "embed", "retrieve", "grade", "verify"), required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--code-sha")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    if args.limit is not None and not 1 <= args.limit <= 30:
        parser.error("--limit must be between 1 and 30")
    if args.stage == "prepare":
        if not all((args.index, args.checkpoint, args.code_sha)):
            parser.error("prepare requires --index, --checkpoint and --code-sha")
        prepare(args)
    else:
        manifest = read(args.run / "manifest.json")
        if source_identity(Path.cwd()) != manifest["source_sha256"]:
            raise ValueError("Source changed since registration")
        if runtime_identity() != manifest["runtime"]:
            raise ValueError("Runtime changed since registration")
        for path, expected in (
            (Path(manifest["corpus"]), manifest["index_receipt"]["corpus_sha256"]),
            (Path(manifest["checkpoint"]), manifest["index_receipt"]["checkpoint_sha256"]),
            (Path(manifest["index"]) / "index-receipt.json", manifest["index_receipt_sha256"]),
        ):
            if file_sha(path) != expected:
                raise ValueError("Input changed since registration")
        run_stage(args, manifest)
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
