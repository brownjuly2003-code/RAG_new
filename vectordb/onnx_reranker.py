"""The reranker's cross-encoder in ONNX Runtime, behind ``RAG_RERANKER_RUNTIME=onnx``.

PLAN.md stage 4, item 5a: on stage 2's pools an INT8 export of bge-reranker-v2-m3 kept the
gold (141 to 144 of 250 after parent expansion) and reranked aircargo's thirty 1.751 times
faster than PyTorch on the idle Mac, but its five differs from PyTorch's on 307 of the 400
(docs/evidence/stage4-step5a-record.md). PyTorch stays the default; this class serves the
chat only when the setting names it.

The scores are ``CrossEncoder.predict``'s: each text stripped, a batch's pairs padded to the
longest and truncated longest first at the tokenizer's own limit, the sigmoid of logit 0, one
score per pair in the pairs' order. An FP32 export scored this way matched PyTorch's scores to
5.126e-06 (item 5a, block 1). An INT8 file quantizes its activations per batch, so a pair's
score depends on the batch it is scored in.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

# CrossEncoder.predict's default batch; the product passes none unless RAG_RERANK_BATCH is set.
DEFAULT_BATCH = 32


class OnnxCrossEncoder:
    """``predict`` as the product calls a CrossEncoder's, on an ONNX export of the same model.

    The tokenizer is the model's own (``model_name``, as ``RAG_RERANKER_MODEL`` names it). The
    session's inputs are fed from the tokenizer's outputs of the same names, as int64; its first
    output holds the logits. ONNX Runtime's CPU provider with its default threads.
    """

    runtime = "onnx"

    def __init__(self, model_name: str, onnx_path: str | Path) -> None:
        path = Path(onnx_path)
        if not path.is_file():
            raise FileNotFoundError(f"RAG_RERANKER_ONNX names no file: {path}")
        import onnxruntime as ort
        from transformers import AutoTokenizer

        self.model_name = model_name
        self.path = path
        # Accept the configured reranker's unpinned revision, matching the PyTorch CrossEncoder path.
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)  # nosec B615
        self.session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        self._inputs = [item.name for item in self.session.get_inputs()]
        self._output = self.session.get_outputs()[0].name

    def predict(
        self, sentences: Sequence[Sequence[str]], batch_size: int = DEFAULT_BATCH, **_: Any
    ) -> Any:
        """One float32 score per (query, text) pair, in the pairs' order."""
        import numpy as np

        pairs = list(sentences)
        step = batch_size if batch_size and batch_size > 0 else DEFAULT_BATCH
        scores = []
        for start in range(0, len(pairs), step):
            batch = pairs[start : start + step]
            features = self.tokenizer(
                [query.strip() for query, _ in batch],
                [text.strip() for _, text in batch],
                padding=True,
                truncation="longest_first",
                return_tensors="np",
                max_length=None,
            )
            feed = {name: np.asarray(features[name], dtype=np.int64) for name in self._inputs}
            logits = np.asarray(self.session.run([self._output], feed)[0], dtype=np.float32)
            scores.append(1.0 / (1.0 + np.exp(-logits[:, 0])))
        if not scores:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(scores).astype(np.float32)
