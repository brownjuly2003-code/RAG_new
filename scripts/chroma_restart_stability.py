"""Build and reopen one Chroma collection on production's write and read paths."""

from __future__ import annotations

import ast
import gzip
import importlib
import json
import math
import time
from collections.abc import Mapping
from pathlib import Path

import numpy as np

from scripts.pgvector_cold_start import _ArgumentParser, read_log_positions, text_digest

SCHEMA_VERSION = "chroma-restart-stability-v1"
COLLECTION = "restart_aircargo"
TENANT = "aircargo"
EXPECTED_CHUNKS = 5589
EXPECTED_CASES = 115
DIM = 1024
TRIALS = 7
PATHS = ("vector", "candidates")


class VectorAdapter:
    """Serve precomputed document and query vectors by their original text."""

    def __init__(self, texts, vectors, queries, query_vectors):
        if len(texts) != len(vectors) or len(queries) != len(query_vectors):
            raise ValueError("vector row counts differ from their texts")
        if len(set(texts)) != len(texts) or len(set(queries)) != len(queries):
            raise ValueError("vector lookup texts must be unique")
        self._documents = {text: list(row) for text, row in zip(texts, vectors, strict=True)}
        self._queries = {
            query: list(row) for query, row in zip(queries, query_vectors, strict=True)
        }
        self.document_call_lengths: list[int] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_call_lengths.append(len(texts))
        return [self._documents[text] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._queries[text]


def _load_process_inputs(
    archive,
    vectors_path,
    queries_path,
    case_files,
    expected_digest,
    expected_chunks,
    expected_cases,
):
    with gzip.open(archive, "rb") as stream:
        chunks = json.loads(stream.read())["chunks"]
    texts = [chunk["page_content"] for chunk in chunks]
    if len(texts) != expected_chunks or text_digest(texts) != expected_digest:
        raise ValueError("archive count or text digest mismatch")
    cases = [
        json.loads(line)["query"]
        for path in case_files
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(cases) != expected_cases:
        raise ValueError("case count mismatch")
    with np.load(vectors_path, allow_pickle=False) as cache:
        vectors = cache["embeddings"]
    query_vectors = np.load(queries_path, allow_pickle=False)
    if vectors.shape != (expected_chunks, DIM) or query_vectors.shape != (expected_cases, DIM):
        raise ValueError("embedding shape mismatch")
    if not np.isfinite(vectors).all() or not np.isfinite(query_vectors).all():
        raise ValueError("embeddings must be finite")
    adapter = VectorAdapter(texts, vectors.tolist(), cases, query_vectors.tolist())
    return chunks, cases, adapter


def _settings(importer):
    settings = importer("config.settings").get_settings()
    return settings, {
        "retrieval_top_k": settings.retrieval_top_k,
        "rrf_k": settings.rrf_k,
        "rrf_doc_key_chars": settings.rrf_doc_key_chars,
    }


def _retriever(store, expected_digest, expected_chunks, importer):
    manager = importer("vectordb.manager")
    base_manager = importer("vectordb._base_manager")
    chunks = manager._restore_chunks_from_store(store, TENANT)
    if chunks is None or len(chunks) != expected_chunks:
        raise ValueError("restored chunk count mismatch")
    if text_digest([chunk.page_content for chunk in chunks]) != expected_digest:
        raise ValueError("restored text digest mismatch")
    settings, values = _settings(importer)
    retriever = base_manager.HybridRetriever(
        vector_store=store,
        chunks=chunks,
        retrieval_k=settings.retrieval_top_k,
        rerank_k=1000000,
        rrf_k=settings.rrf_k,
        doc_key_chars=settings.rrf_doc_key_chars,
        reranker=None,
        use_bm25=True,
        parent_expansion=False,
    )
    return retriever, values, len(chunks)


def _answer_pass(retriever, cases, retrieval_top_k, *, check=True):
    answers = {path: [] for path in PATHS}
    for index, query in enumerate(cases):
        vector = [d.metadata["chunk_index"] for d in retriever.get_vector_documents(query)]
        candidates = [d.metadata["chunk_index"] for d in retriever.get_relevant_documents(query)]
        if check and (
            len(vector) != retrieval_top_k
            or any(type(value) is not int for value in vector)
            or len(set(vector)) != len(vector)
        ):
            raise ValueError(f"vector case {index}: expected distinct retrieval_top_k indexes")
        if check and (
            any(type(value) is not int for value in candidates)
            or len(set(candidates)) != len(candidates)
            or not set(vector).issubset(candidates)
        ):
            raise ValueError(f"candidates case {index}: invalid or missing vector indexes")
        answers["vector"].append(vector)
        answers["candidates"].append(candidates)
    return answers


def answer_cases(retriever, cases, retrieval_top_k):
    first = _answer_pass(retriever, cases, retrieval_top_k)
    second = _answer_pass(retriever, cases, retrieval_top_k, check=False)
    for path in PATHS:
        for index, (before, after) in enumerate(zip(first[path], second[path], strict=True)):
            if before != after:
                raise ValueError(f"{path} case {index}: second pass changed")
    return first


def _hnsw(store):
    configuration = getattr(store._collection, "configuration", None)
    if configuration is None:
        return None
    if hasattr(configuration, "to_json"):
        configuration = configuration.to_json()
    elif hasattr(configuration, "model_dump"):
        configuration = configuration.model_dump()
    if isinstance(configuration, str):
        configuration = json.loads(configuration)
    if not isinstance(configuration, Mapping):
        raise ValueError("collection configuration is invalid")
    return configuration.get("hnsw")


def build_collection(
    chroma_dir,
    archive,
    vectors_path,
    queries_path,
    case_files,
    expected_digest,
    *,
    importer=importlib.import_module,
    clock=time.perf_counter,
    log_reader=read_log_positions,
    expected_chunks=EXPECTED_CHUNKS,
    expected_cases=EXPECTED_CASES,
):
    chunks, cases, adapter = _load_process_inputs(
        archive,
        vectors_path,
        queries_path,
        case_files,
        expected_digest,
        expected_chunks,
        expected_cases,
    )
    document_cls = importer("langchain_core.documents").Document
    chroma_cls = importer("langchain_chroma").Chroma
    docs = [
        document_cls(
            page_content=chunk["page_content"], metadata={**chunk["metadata"], "chunk_index": index}
        )
        for index, chunk in enumerate(chunks)
    ]
    started = clock()
    store = chroma_cls.from_documents(
        documents=docs,
        embedding=adapter,
        persist_directory=str(chroma_dir),
        collection_name=COLLECTION,
    )
    if store._client.get_settings().anonymized_telemetry is not False:
        raise ValueError("telemetry is enabled")
    build_ms = 1000 * (clock() - started)
    count = store._collection.count()
    if count != expected_chunks:
        raise ValueError("collection count mismatch")
    hnsw = _hnsw(store)
    positions = log_reader(chroma_dir)
    retriever, settings, restored_count = _retriever(
        store, expected_digest, expected_chunks, importer
    )
    answers = answer_cases(retriever, cases, settings["retrieval_top_k"])
    return {
        "build_ms": build_ms,
        "embed_documents_call_lengths": adapter.document_call_lengths,
        "collection_count": count,
        "restored_chunk_count": restored_count,
        "hnsw": hnsw,
        **positions,
        "settings": settings,
        "answers": answers,
    }


def run_trial(
    chroma_dir,
    archive,
    vectors_path,
    queries_path,
    case_files,
    expected_digest,
    *,
    importer=importlib.import_module,
    expected_chunks=EXPECTED_CHUNKS,
    expected_cases=EXPECTED_CASES,
):
    _, cases, adapter = _load_process_inputs(
        archive,
        vectors_path,
        queries_path,
        case_files,
        expected_digest,
        expected_chunks,
        expected_cases,
    )
    chroma_cls = importer("langchain_chroma").Chroma
    store = chroma_cls(
        persist_directory=str(chroma_dir),
        embedding_function=adapter,
        collection_name=COLLECTION,
    )
    if store._client.get_settings().anonymized_telemetry is not False:
        raise ValueError("telemetry is enabled")
    retriever, settings, restored_count = _retriever(
        store, expected_digest, expected_chunks, importer
    )
    return {
        "restored_chunk_count": restored_count,
        "settings": settings,
        "answers": answer_cases(retriever, cases, settings["retrieval_top_k"]),
    }


def validate_answers(answers, case_count, retrieval_top_k):
    if not isinstance(answers, dict) or set(answers) != set(PATHS):
        raise ValueError("invalid answer paths")
    if any(
        not isinstance(answers[path], list) or len(answers[path]) != case_count for path in PATHS
    ):
        raise ValueError("invalid answer case count")
    for index in range(case_count):
        vector = answers["vector"][index]
        candidates = answers["candidates"][index]
        if (
            not isinstance(vector, list)
            or len(vector) != retrieval_top_k
            or any(type(value) is not int for value in vector)
            or len(set(vector)) != len(vector)
        ):
            raise ValueError(f"vector case {index}: invalid child answer")
        if (
            not isinstance(candidates, list)
            or any(type(value) is not int for value in candidates)
            or len(set(candidates)) != len(candidates)
            or not set(vector).issubset(candidates)
        ):
            raise ValueError(f"candidates case {index}: invalid child answer")


def validate_build_record(record, expected_chunks, case_count):
    if not isinstance(record, dict):
        raise ValueError("invalid build result")
    count = record.get("collection_count")
    lengths = record.get("embed_documents_call_lengths")
    build_ms = record.get("build_ms")
    highest = record.get("chroma_log_max_seq_id")
    persisted = record.get("chroma_vector_persisted_seq_id")
    settings = record.get("settings")
    if (
        type(count) is not int
        or count != expected_chunks
        or not isinstance(lengths, list)
        or any(type(value) is not int or value < 0 for value in lengths)
        or sum(lengths) != expected_chunks
        or isinstance(build_ms, bool)
        or not isinstance(build_ms, (int, float))
        or not math.isfinite(build_ms)
        or build_ms < 0
        or type(highest) is not int
        or highest < 0
        or type(persisted) is not int
        or persisted < 0
        or persisted > highest
        or type(record.get("restored_chunk_count")) is not int
        or record["restored_chunk_count"] != expected_chunks
        or not isinstance(settings, dict)
        or set(settings) != {"retrieval_top_k", "rrf_k", "rrf_doc_key_chars"}
        or type(settings["retrieval_top_k"]) is not int
        or settings["retrieval_top_k"] < 1
        or type(settings["rrf_k"]) is not int
        or type(settings["rrf_doc_key_chars"]) is not int
    ):
        raise ValueError("invalid build result")
    validate_answers(record.get("answers"), case_count, settings["retrieval_top_k"])
    json.dumps(record.get("hnsw"), allow_nan=False)
    return record


def validate_trial_record(record, expected_chunks, case_count, settings):
    if (
        not isinstance(record, dict)
        or type(record.get("restored_chunk_count")) is not int
        or record["restored_chunk_count"] != expected_chunks
        or record.get("settings") != settings
    ):
        raise ValueError("invalid trial result")
    validate_answers(record.get("answers"), case_count, settings["retrieval_top_k"])
    return record


def _variation(reference, trials, indexes):
    rows = []
    for index in indexes:
        differing = [
            case
            for case, (left, right) in enumerate(zip(reference, trials[index], strict=True))
            if left != right
        ]
        rows.append({"trial": index, "differing_cases": differing})
    return {
        "trials": rows,
        "distinct_cases": len({case for row in rows for case in row["differing_cases"]}),
    }


def compare_answers(build_answers, trial_answers):
    """Compare ordered answers and candidate sets without reading process state."""
    if len(trial_answers) != TRIALS:
        raise ValueError("seven trial answers are required")
    case_count = len(build_answers["vector"])
    if any(len(record[path]) != case_count for record in trial_answers for path in PATHS):
        raise ValueError("trial answer case count mismatch")
    build_vs = {
        path: _variation(
            build_answers[path], [record[path] for record in trial_answers], range(TRIALS)
        )
        for path in PATHS
    }
    trial0_vs = {
        path: _variation(
            trial_answers[0][path], [record[path] for record in trial_answers], range(1, TRIALS)
        )
        for path in PATHS
    }
    candidate_sets = _variation(
        [set(row) for row in build_answers["candidates"]],
        [[set(row) for row in record["candidates"]] for record in trial_answers],
        range(TRIALS),
    )
    return {
        "build_vs_trials": build_vs,
        "trial0_vs_later": trial0_vs,
        "candidate_sets_vs_build": candidate_sets,
    }


def build_report(context, build, trials, *, directory_removed):
    if len(trials) != TRIALS or [row["trial"] for row in trials] != list(range(TRIALS)):
        raise ValueError("incomplete trial records")
    trial_answers = [row["answers"] for row in trials]
    comparisons = compare_answers(build["answers"], trial_answers)
    differences = []
    for trial in range(1, TRIALS):
        record = {"trial": trial}
        for path in PATHS:
            record[path] = [
                {"case_index": case, "answer": trial_answers[trial][path][case]}
                for case in comparisons["build_vs_trials"][path]["trials"][trial]["differing_cases"]
            ]
        differences.append(record)
    build_facts = {key: value for key, value in build.items() if key != "answers"}
    build_facts["unpersisted_tail"] = (
        build["chroma_log_max_seq_id"] - build["chroma_vector_persisted_seq_id"]
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "measured" if directory_removed else "cleanup_failed",
        **context,
        "collection_name": COLLECTION,
        "chunk_count": build["collection_count"],
        "case_count": len(build["answers"]["vector"]),
        "trial_count": TRIALS,
        "settings": build["settings"],
        "build": build_facts,
        "trials": [
            {key: value for key, value in row.items() if key != "answers"} for row in trials
        ],
        "comparison": comparisons,
        "answers": {
            "build": build["answers"],
            "trial_0": trial_answers[0],
            "trial_differences": differences,
        },
        "cleanup": {"directory_removed": directory_removed},
    }


def _function(source, name):
    matches = [
        node
        for node in ast.parse(source).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    if len(matches) != 1:
        raise ValueError(f"missing function {name}")
    return matches[0]


def assert_staged_build_call(source):
    node = _function(source, "build_staged_collection")
    calls = [
        call
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "from_documents"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "chroma_cls"
    ]
    expected = {"documents", "embedding", "persist_directory", "collection_name"}
    if len(calls) != 1 or calls[0].args or {key.arg for key in calls[0].keywords} != expected:
        raise ValueError("build_staged_collection from_documents call changed")


def assert_reopen_call(source):
    node = _function(source, "get_retriever")
    calls = [
        call
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "chroma_cls"
    ]
    expected = {"persist_directory", "embedding_function", "collection_name"}
    if len(calls) != 1 or calls[0].args or {key.arg for key in calls[0].keywords} != expected:
        raise ValueError("get_retriever chroma_cls call changed")


def assert_chunk_index_stamp(source):
    node = _function(source, "_build_vector_store_result")
    found = [
        assignment
        for assignment in ast.walk(node)
        if isinstance(assignment, ast.Assign)
        and isinstance(assignment.value, ast.Name)
        and assignment.value.id == "index"
        for target in assignment.targets
        if isinstance(target, ast.Subscript)
        and isinstance(target.value, ast.Name)
        and target.value.id == "metadata"
        and isinstance(target.slice, ast.Constant)
        and target.slice.value == "chunk_index"
    ]
    if len(found) != 1:
        raise ValueError("_build_vector_store_result chunk_index stamp changed")


def main(argv=None):
    parser = _ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True, parser_class=_ArgumentParser)
    for mode in ("build", "trial"):
        child = modes.add_parser(mode)
        if mode == "trial":
            child.add_argument("--trial-index", required=True)
        for option in ("directory", "archive", "vectors", "queries", "text-digest"):
            child.add_argument("--" + option, required=True)
        child.add_argument("--cases", action="append", required=True)
    step = "arguments"
    try:
        args = parser.parse_args(argv)
        step = args.mode
        if len(args.cases) != 2:
            raise ValueError("two case files are required")
        function = build_collection if args.mode == "build" else run_trial
        result = function(
            args.directory,
            args.archive,
            args.vectors,
            args.queries,
            args.cases,
            args.text_digest,
        )
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({"error": f"{step}: {type(exc).__name__}: {exc}"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
