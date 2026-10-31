"""RAG_RERANKER_RUNTIME=onnx: the reranker in ONNX Runtime behind a setting (PLAN.md stage 4,
item 5a, the short live series).

ONNX is the default. Under the setting ``get_reranker()`` loads RAG_RERANKER_ONNX with the
model's own tokenizer, and ``predict`` scores as ``CrossEncoder.predict`` does: each text
stripped, a batch padded and truncated longest first, the sigmoid of logit 0, one float per pair
in the pairs' order. These tests stand in for ONNX Runtime and the tokenizer; the end-to-end test
with the real INT8 file is ``tests/test_reranker_onnx_e2e.py``.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from config import settings as settings_module
from config.settings import Settings
from vectordb import _base_manager


def test_the_runtime_defaults_to_onnx_and_reads_the_onnx_path(monkeypatch):
    monkeypatch.delenv("RAG_RERANKER_RUNTIME", raising=False)
    monkeypatch.delenv("RAG_RERANKER_ONNX", raising=False)
    settings = Settings()
    assert (settings.reranker_runtime, settings.reranker_onnx_path) == ("onnx", "")

    monkeypatch.setenv("RAG_RERANKER_RUNTIME", " ONNX ")
    monkeypatch.setenv("RAG_RERANKER_ONNX", " /models/int8/model.onnx ")
    settings = Settings()
    assert settings.reranker_runtime == "onnx"
    assert settings.reranker_onnx_path == "/models/int8/model.onnx"

    monkeypatch.setenv("RAG_RERANKER_RUNTIME", " ")
    assert Settings().reranker_runtime == "onnx"


@pytest.mark.parametrize(
    ("runtime", "named"), [("tensorrt", "RAG_RERANKER_RUNTIME"), ("onnx", "RAG_RERANKER_ONNX")]
)
def test_startup_refuses_an_unknown_runtime_and_onnx_without_a_file(
    monkeypatch, tmp_path, runtime, named
):
    monkeypatch.setenv("RAG_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")  # conftest empties it
    monkeypatch.setenv("RAG_RERANKER_RUNTIME", runtime)
    monkeypatch.setenv("RAG_RERANKER_ONNX", str(tmp_path / "missing.onnx"))
    with pytest.raises(RuntimeError, match=named) as refused:
        Settings().validate()
    if runtime == "onnx":
        assert repr(str(tmp_path / "missing.onnx")) in str(refused.value)


def test_default_runtime_refusal_names_export_and_explicit_torch_opt_out(monkeypatch):
    monkeypatch.delenv("RAG_RERANKER_RUNTIME", raising=False)
    monkeypatch.delenv("RAG_RERANKER_ONNX", raising=False)
    monkeypatch.setenv("RAG_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
    with pytest.raises(RuntimeError, match="RAG_RERANKER_ONNX") as refused:
        Settings().validate()
    assert "reports/stage4-step5a/tools/export_onnx.py" in str(refused.value)
    assert "RAG_RERANKER_RUNTIME=torch" in str(refused.value)
    assert "not the measured stage-4 package" in str(refused.value)
    assert "Got ''." in str(refused.value)
    monkeypatch.setenv("RAG_RERANKER_RUNTIME", "torch")
    Settings().validate()


def test_get_reranker_loads_the_onnx_file_under_the_setting(monkeypatch):
    import vectordb.onnx_reranker as onnx_reranker

    loaded: list[tuple[str, str]] = []

    class _Onnx:
        def __init__(self, model_name: str, onnx_path: str) -> None:
            loaded.append((model_name, onnx_path))

    def no_cross_encoder() -> None:
        raise AssertionError("the onnx runtime loaded the CrossEncoder")

    settings = SimpleNamespace(
        reranker_model="BAAI/bge-reranker-v2-m3",
        reranker_runtime="onnx",
        reranker_onnx_path="/models/int8/model.onnx",
        rag_device="cpu",
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    monkeypatch.setattr(onnx_reranker, "OnnxCrossEncoder", _Onnx)
    monkeypatch.setattr(_base_manager, "_load_cross_encoder", no_cross_encoder)
    monkeypatch.setattr(_base_manager, "_cached_reranker", None)

    reranker = _base_manager.get_reranker()

    assert isinstance(reranker, _Onnx)
    assert loaded == [("BAAI/bge-reranker-v2-m3", "/models/int8/model.onnx")]
    assert _base_manager.get_reranker() is reranker  # cached for the process
    assert len(loaded) == 1


def test_get_reranker_keeps_the_explicit_torch_cross_encoder(monkeypatch):
    created: list[str] = []

    class _CrossEncoder:
        def __init__(self, model_name: str, device: str) -> None:
            created.append(f"{model_name}:{device}")

    settings = SimpleNamespace(
        reranker_model="BAAI/bge-reranker-v2-m3",
        reranker_runtime="torch",
        reranker_onnx_path="/models/int8/model.onnx",
        rag_device="cpu",
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    monkeypatch.setattr(_base_manager, "_load_cross_encoder", lambda: _CrossEncoder)
    monkeypatch.setattr(_base_manager, "_cached_reranker", None)

    assert isinstance(_base_manager.get_reranker(), _CrossEncoder)
    assert created == ["BAAI/bge-reranker-v2-m3:cpu"]


def test_a_missing_file_raises_before_onnx_runtime_is_imported(monkeypatch, tmp_path):
    from vectordb.onnx_reranker import OnnxCrossEncoder

    monkeypatch.setitem(sys.modules, "onnxruntime", None)  # an import would raise
    with pytest.raises(FileNotFoundError, match="RAG_RERANKER_ONNX"):
        OnnxCrossEncoder("BAAI/bge-reranker-v2-m3", tmp_path / "missing.onnx")


class _Tokenizer:
    """Pairs become rows: each token id is the text's length, so a row tells its pair."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], list[str], dict[str, Any]]] = []

    def __call__(self, first: list[str], second: list[str], **kwargs: Any) -> dict[str, Any]:
        self.calls.append((list(first), list(second), kwargs))
        ids = np.array([[len(a), len(b)] for a, b in zip(first, second, strict=True)])
        return {
            "input_ids": ids.astype(np.int32),
            "attention_mask": np.ones_like(ids, dtype=np.int32),
            "token_type_ids": np.zeros_like(ids, dtype=np.int32),
        }


class _Session:
    """Logit 0 is the second text's length less the first's; logit 1 must be ignored."""

    def __init__(self, path: str, providers: list[str]) -> None:
        self.path, self.providers = path, providers
        self.feeds: list[dict[str, Any]] = []

    def get_inputs(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(name="input_ids"), SimpleNamespace(name="attention_mask")]

    def get_outputs(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(name="logits")]

    def run(self, names: list[str], feed: dict[str, Any]) -> list[Any]:
        assert names == ["logits"]
        self.feeds.append(feed)
        ids = feed["input_ids"]
        logit = (ids[:, 1] - ids[:, 0]).astype(np.float64)
        return [np.stack([logit, np.full_like(logit, 99.0)], axis=1)]


@pytest.fixture
def fake_runtime(monkeypatch):
    tokenizer = _Tokenizer()
    names: list[str] = []

    def from_pretrained(name: str) -> _Tokenizer:
        names.append(name)
        return tokenizer

    ort = types.ModuleType("onnxruntime")
    ort.InferenceSession = _Session
    transformers = types.ModuleType("transformers")
    transformers.AutoTokenizer = SimpleNamespace(from_pretrained=from_pretrained)
    monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    return SimpleNamespace(tokenizer=tokenizer, names=names)


def test_predict_scores_as_the_cross_encoder_does(fake_runtime, tmp_path):
    from vectordb.onnx_reranker import OnnxCrossEncoder

    model = tmp_path / "model.onnx"
    model.write_bytes(b"onnx")
    reranker = OnnxCrossEncoder("BAAI/bge-reranker-v2-m3", model)
    pairs = [("  q ", " a longer text "), ("q", "ab"), ("query", "x")]

    scores = reranker.predict(pairs, batch_size=2)

    assert fake_runtime.names == ["BAAI/bge-reranker-v2-m3"]
    assert reranker.session.path == str(model)
    assert reranker.session.providers == ["CPUExecutionProvider"]
    # Two batches, every text stripped, the CrossEncoder's padding and truncation.
    assert [call[:2] for call in fake_runtime.tokenizer.calls] == [
        (["q", "q"], ["a longer text", "ab"]),
        (["query"], ["x"]),
    ]
    assert all(
        call[2]
        == {
            "padding": True,
            "truncation": "longest_first",
            "return_tensors": "np",
            "max_length": None,
        }
        for call in fake_runtime.tokenizer.calls
    )
    # Only the session's inputs are fed, as int64.
    assert all(
        sorted(feed) == ["attention_mask", "input_ids"]
        and all(value.dtype == np.int64 for value in feed.values())
        for feed in reranker.session.feeds
    )
    # The sigmoid of logit 0, one float32 per pair in the pairs' order.
    logits = np.array([13 - 1, 2 - 1, 1 - 5], dtype=np.float32)
    assert scores.dtype == np.float32
    assert scores.tolist() == pytest.approx((1 / (1 + np.exp(-logits))).tolist())
    assert reranker.predict(pairs).tolist() == pytest.approx(scores.tolist())  # one batch of 32
    assert reranker.predict([]).shape == (0,)


def test_the_retriever_ranks_by_the_onnx_scores(fake_runtime, tmp_path):
    """The product's rerank call takes predict's scores as it takes the CrossEncoder's."""
    from vectordb.onnx_reranker import OnnxCrossEncoder

    Document = _base_manager.Document
    model = tmp_path / "model.onnx"
    model.write_bytes(b"onnx")
    docs = [
        Document(page_content="short", metadata={"source": "a.md", "chunk_index": 0}),
        Document(page_content="a much longer text", metadata={"source": "b.md", "chunk_index": 0}),
        Document(page_content="medium text", metadata={"source": "c.md", "chunk_index": 0}),
    ]
    retriever = _base_manager.HybridRetriever(
        vector_store=SimpleNamespace(similarity_search=lambda query, k: []),
        chunks=docs,
        reranker=OnnxCrossEncoder("BAAI/bge-reranker-v2-m3", model),
        rerank_k=2,
    )

    scored, ok = retriever._rerank_scored_with_status("q", docs)

    assert ok is True
    assert [doc.metadata["source"] for doc, _ in scored] == ["b.md", "c.md"]
    assert all(isinstance(score, float) for _, score in scored)
