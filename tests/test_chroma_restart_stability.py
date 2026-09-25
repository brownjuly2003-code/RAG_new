"""Stand-in tests for the production-path Chroma restart measurement."""

import gzip
import json
from types import SimpleNamespace

import numpy as np
import pytest

from scripts import chroma_restart_stability as measurement
from scripts.pgvector_cold_start import text_digest


def _inputs(tmp_path):
    archive = tmp_path / "chunks.json.gz"
    chunks = [
        {"page_content": "first", "metadata": {"source": "one"}},
        {"page_content": "second", "metadata": {"source": "two"}},
    ]
    with gzip.open(archive, "wb") as stream:
        stream.write(json.dumps({"chunks": chunks}).encode())
    vectors = tmp_path / "vectors.npz"
    np.savez(vectors, embeddings=np.ones((2, 1024), dtype="float32"))
    queries = tmp_path / "queries.npy"
    np.save(queries, np.ones((2, 1024), dtype="float32"))
    cases = [tmp_path / "cases-one.jsonl", tmp_path / "cases-two.jsonl"]
    for index, path in enumerate(cases):
        path.write_text(json.dumps({"query": f"query {index}"}) + "\n", encoding="utf-8")
    return archive, vectors, queries, cases, text_digest(["first", "second"])


def _modules(calls, *, telemetry=False, second_pass_change=False):
    class Document:
        def __init__(self, page_content, metadata):
            self.page_content = page_content
            self.metadata = metadata

    class Store:
        def __init__(self):
            self._collection = SimpleNamespace(
                count=lambda: 2, configuration={"hnsw": {"space": "l2"}}
            )
            self._client = SimpleNamespace(
                get_settings=lambda: SimpleNamespace(anonymized_telemetry=telemetry)
            )

    class Chroma:
        @classmethod
        def from_documents(cls, **kwargs):
            calls.append(("build", kwargs))
            kwargs["embedding"].embed_documents([d.page_content for d in kwargs["documents"][:1]])
            kwargs["embedding"].embed_documents([d.page_content for d in kwargs["documents"][1:]])
            return Store()

        def __new__(cls, **kwargs):
            calls.append(("reopen", kwargs))
            return Store()

    class Retriever:
        def __init__(self, **kwargs):
            calls.append(("retriever", kwargs))
            self.calls = 0

        def get_vector_documents(self, query):
            self.calls += 1
            index = int(query[-1])
            if second_pass_change and self.calls > 2 and index == 0:
                index = 1
            return [Document("", {"chunk_index": index})]

        def get_relevant_documents(self, query):
            return [Document("", {"chunk_index": int(query[-1])})]

    def restore(store, tenant):
        calls.append(("restore", tenant))
        return [Document("first", {"chunk_index": 0}), Document("second", {"chunk_index": 1})]

    modules = {
        "langchain_core.documents": SimpleNamespace(Document=Document),
        "langchain_chroma": SimpleNamespace(Chroma=Chroma),
        "vectordb.manager": SimpleNamespace(_restore_chunks_from_store=restore),
        "vectordb._base_manager": SimpleNamespace(HybridRetriever=Retriever),
        "config.settings": SimpleNamespace(
            get_settings=lambda: SimpleNamespace(retrieval_top_k=1, rrf_k=60, rrf_doc_key_chars=200)
        ),
    }
    return modules.__getitem__


def test_adapter_lengths_and_unknown_inputs():
    adapter = measurement.VectorAdapter(["a", "b"], [[1, 2], [3, 4]], ["q"], [[5, 6]])
    assert adapter.embed_documents(["b", "a"]) == [[3, 4], [1, 2]]
    assert adapter.embed_documents(["a"]) == [[1, 2]]
    assert adapter.embed_query("q") == [5, 6]
    assert adapter.document_call_lengths == [2, 1]
    with pytest.raises(KeyError):
        adapter.embed_documents(["missing"])
    with pytest.raises(KeyError):
        adapter.embed_query("missing")


def test_build_uses_production_calls_and_records_facts(tmp_path):
    archive, vectors, queries, cases, digest = _inputs(tmp_path)
    calls = []
    result = measurement.build_collection(
        tmp_path / "store",
        archive,
        vectors,
        queries,
        cases,
        digest,
        importer=_modules(calls),
        clock=iter((1.0, 1.25)).__next__,
        log_reader=lambda _: {"chroma_log_max_seq_id": 10, "chroma_vector_persisted_seq_id": 7},
        expected_chunks=2,
        expected_cases=2,
    )
    build = calls[0][1]
    assert set(build) == {
        "documents",
        "embedding",
        "persist_directory",
        "collection_name",
        "collection_configuration",
    }
    assert build["collection_configuration"] == {"hnsw": {"sync_threshold": 1}}
    assert build["collection_name"] == "restart_aircargo"
    assert [d.metadata["chunk_index"] for d in build["documents"]] == [0, 1]
    assert build["documents"][0].metadata["source"] == "one"
    assert ("restore", "aircargo") in calls
    retriever = next(value for kind, value in calls if kind == "retriever")
    assert set(retriever) == {
        "vector_store",
        "chunks",
        "retrieval_k",
        "rerank_k",
        "rrf_k",
        "doc_key_chars",
        "reranker",
        "use_bm25",
        "parent_expansion",
    }
    assert retriever["retrieval_k"] == 1
    assert retriever["rerank_k"] == 1000000
    assert retriever["reranker"] is None
    assert retriever["use_bm25"] is True
    assert retriever["parent_expansion"] is False
    assert result["build_ms"] == 250
    assert result["embed_documents_call_lengths"] == [1, 1]
    assert result["collection_count"] == 2
    assert result["hnsw"] == {"space": "l2"}
    assert result["chroma_log_max_seq_id"] == 10
    assert result["answers"]["vector"] == [[0], [1]]


def test_build_rejects_enabled_telemetry(tmp_path):
    archive, vectors, queries, cases, digest = _inputs(tmp_path)
    calls = []
    with pytest.raises(ValueError, match="telemetry is enabled"):
        measurement.build_collection(
            tmp_path / "store",
            archive,
            vectors,
            queries,
            cases,
            digest,
            importer=_modules(calls, telemetry=True),
            clock=iter((1.0, 1.25)).__next__,
            log_reader=lambda _: {"chroma_log_max_seq_id": 10, "chroma_vector_persisted_seq_id": 7},
            expected_chunks=2,
            expected_cases=2,
        )
    assert calls[0][0] == "build"


def test_trial_reopens_and_checks_telemetry_and_restore(tmp_path):
    archive, vectors, queries, cases, digest = _inputs(tmp_path)
    calls = []
    result = measurement.run_trial(
        tmp_path / "store",
        archive,
        vectors,
        queries,
        cases,
        digest,
        importer=_modules(calls),
        expected_chunks=2,
        expected_cases=2,
    )
    assert set(calls[0][1]) == {"persist_directory", "embedding_function", "collection_name"}
    assert calls[0][1]["collection_name"] == "restart_aircargo"
    assert result["restored_chunk_count"] == 2
    assert result["answers"]["candidates"] == [[0], [1]]
    with pytest.raises(ValueError, match="telemetry"):
        measurement.run_trial(
            tmp_path / "store",
            archive,
            vectors,
            queries,
            cases,
            digest,
            importer=_modules([], telemetry=True),
            expected_chunks=2,
            expected_cases=2,
        )
    with pytest.raises(ValueError, match="vector case 0"):
        measurement.run_trial(
            tmp_path / "store",
            archive,
            vectors,
            queries,
            cases,
            digest,
            importer=_modules([], second_pass_change=True),
            expected_chunks=2,
            expected_cases=2,
        )


def test_answer_checks_short_vector_and_missing_candidate():
    def doc(index):
        return SimpleNamespace(metadata={"chunk_index": index})

    retriever = SimpleNamespace(
        get_vector_documents=lambda _: [], get_relevant_documents=lambda _: [doc(0)]
    )
    with pytest.raises(ValueError, match="vector case 0"):
        measurement.answer_cases(retriever, ["q"], 1)
    retriever.get_vector_documents = lambda _: [doc(0)]
    retriever.get_relevant_documents = lambda _: [doc(1)]
    with pytest.raises(ValueError, match="candidates case 0"):
        measurement.answer_cases(retriever, ["q"], 1)


def test_comparison_counts_order_and_sets_separately():
    build = {"vector": [[1, 2], [3, 4]], "candidates": [[1, 2, 5], [3, 4]]}
    trials = [{"vector": [[1, 2], [3, 4]], "candidates": [[2, 1, 5], [3, 4]]}]
    trials += [{"vector": [[2, 1], [3, 4]], "candidates": [[1, 2, 6], [3, 4]]}]
    trials += [trials[0]] * 5
    result = measurement.compare_answers(build, trials)
    assert result["build_vs_trials"]["candidates"]["trials"][0]["differing_cases"] == [0]
    assert result["candidate_sets_vs_build"]["trials"][0]["differing_cases"] == []
    assert result["candidate_sets_vs_build"]["trials"][1]["differing_cases"] == [0]
    assert result["trial0_vs_later"]["vector"]["trials"][0] == {"trial": 1, "differing_cases": [0]}
    assert result["build_vs_trials"]["vector"]["distinct_cases"] == 1


def test_report_status_full_answers_and_difference_only():
    answers = {"vector": [[0]], "candidates": [[0, 1]]}
    trial = {"vector": [[0]], "candidates": [[1, 0]]}
    records = [{"trial": 0, "restored_chunk_count": 2, "answers": trial}]
    records += [{"trial": 1, "restored_chunk_count": 2, "answers": trial}]
    records += [
        {"trial": index, "restored_chunk_count": 2, "answers": answers} for index in range(2, 7)
    ]
    context = {
        "code_commit": "a" * 40,
        "input_sha256": {},
        "source_sha256": {},
        "versions": {},
        "python": "3.11",
        "platform": "darwin",
        "host": {},
        "load_average_start": [0.0, 0.0, 0.0],
        "start_utc": "start",
        "end_utc": "end",
    }
    build = {
        "answers": answers,
        "build_ms": 1,
        "embed_documents_call_lengths": [2],
        "collection_count": 2,
        "hnsw": None,
        "chroma_log_max_seq_id": 10,
        "chroma_vector_persisted_seq_id": 7,
        "settings": {"retrieval_top_k": 1, "rrf_k": 60, "rrf_doc_key_chars": 200},
    }
    report = measurement.build_report(context, build, records, directory_removed=True)
    assert report["schema_version"] == "chroma-restart-stability-v1"
    assert report["status"] == "measured"
    assert report["build"]["unpersisted_tail"] == 3
    assert report["answers"]["build"] == answers
    assert report["answers"]["trial_0"] == trial
    assert report["answers"]["trial_differences"][0]["candidates"] == [
        {"case_index": 0, "answer": [1, 0]}
    ]
    assert "answers" not in report["trials"][1]
    assert (
        measurement.build_report(context, build, records, directory_removed=False)["status"]
        == "cleanup_failed"
    )


def test_child_main_last_line_and_failure(monkeypatch, capsys):
    monkeypatch.setattr(measurement, "build_collection", lambda *args, **kwargs: {"build_ms": 1})
    args = [
        "build",
        "--directory",
        "store",
        "--archive",
        "a",
        "--vectors",
        "v",
        "--queries",
        "q",
        "--cases",
        "c1",
        "--cases",
        "c2",
        "--text-digest",
        "d",
    ]
    assert measurement.main(args) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1]) == {"build_ms": 1}
    monkeypatch.setattr(measurement, "build_collection", lambda *args, **kwargs: 1 / 0)
    assert measurement.main(args) == 1
    assert "error" in json.loads(capsys.readouterr().out.splitlines()[-1])
