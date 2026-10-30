"""Stage 4, item 5a: the product's reranker as ONNX — FP32 and two INT8 variants.

docs/specs/stage4-step5a-int8-reranker.md. Preparation: run before the spec was registered, on
no question of stage 2. On the Mac, with the ML venv's interpreter and the onnx package from a
folder of its own:

  PYTHONPATH=/Users/julia/RAG_new_ort_site python reports/stage4-step5a/tools/export_onnx.py OUT

1. Loads BAAI/bge-reranker-v2-m3 as the product does (vectordb/_base_manager.get_reranker):
   sentence-transformers' CrossEncoder on the CPU, from the local Hugging Face cache only.
2. Exports its classifier with torch.onnx: opset 17, batch and length dynamic, inputs
   input_ids and attention_mask, output logits; the weights in one external file, OUT/fp32/.
3. Quantizes that file with onnxruntime.quantization.quantize_dynamic, all else its defaults:
   - OUT/int8/: QInt8 weights per channel with reduce_range — the remedy ONNX Runtime's
     documentation gives for AVX2 without VNNI, this Mac's CPU;
   - OUT/int8_u8u8/: QUInt8 weights per channel — its other remedy.
4. Scores 32 made-up pairs with the CrossEncoder and with each file in ONNX Runtime, and writes
   OUT/manifest.json: the versions, the files by SHA-256 and size, the pairs' largest score
   differences against the CrossEncoder and their seconds.
"""

import gc
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import statistics
import sys
import time
from pathlib import Path

MODEL = "BAAI/bge-reranker-v2-m3"
SNAPSHOT = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
OPSET = 17
THREADS = 4
BATCH = 32  # CrossEncoder.predict's default; the product sets none (RAG_RERANK_BATCH unset)
RUNS = 3
VARIANTS = {
    "int8": {"weight_type": "QInt8", "per_channel": True, "reduce_range": True},
    "int8_u8u8": {"weight_type": "QUInt8", "per_channel": True, "reduce_range": False},
}
PACKAGES = (
    "torch",
    "transformers",
    "tokenizers",
    "sentence-transformers",
    "onnx",
    "onnxruntime",
    "numpy",
    "protobuf",
    "ml_dtypes",
)
TOPICS = (
    ("the warehouse schedule", "графика склада"),
    ("the cargo manifest", "грузового манифеста"),
    ("the delayed invoice", "задержанного счёта"),
    ("the probation period", "испытательного срока"),
)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def synthetic():
    """32 made-up pairs, English and Russian by turns, of 2 to 16 sentences — the
    length of stage 2's pairs, 44 to 487 tokens: no corpus text."""
    pairs = []
    for i in range(32):
        en, ru = TOPICS[i % len(TOPICS)]
        if i % 2 == 0:
            question = f"When was step {i} of {en} done?"
            line = "The check of {t} ran on day {d}, and the report marks step {s} as done."
        else:
            question = f"Когда выполнен шаг {i} {ru}?"
            line = "Проверка {t} прошла в день {d}, и в отчёте шаг {s} отмечен как выполненный."
        topic = en if i % 2 == 0 else ru
        sentences = 2 + 2 * (i % 8)
        pairs.append(
            (question, " ".join(line.format(t=topic, d=d, s=i + d) for d in range(sentences)))
        )
    return pairs


def collate(tokenizer, batch, max_length):
    """sentence-transformers 2.7.0's CrossEncoder.smart_batching_collate_text_only, in numpy:
    each text stripped, the pairs padded to the longest, truncated longest first."""
    texts = [[q.strip() for q, _ in batch], [d.strip() for _, d in batch]]
    return tokenizer(
        *texts,
        padding=True,
        truncation="longest_first",
        return_tensors="np",
        max_length=max_length,
    )


def session(path):
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = THREADS
    return ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])


def ort_scores(model, tokenizer, pairs, max_length):
    """The CrossEncoder's predict on ONNX Runtime: batches of 32 in order, sigmoid of logit 0."""
    import numpy as np

    scores = []
    for start in range(0, len(pairs), BATCH):
        features = collate(tokenizer, pairs[start : start + BATCH], max_length)
        feed = {k: features[k].astype(np.int64) for k in ("input_ids", "attention_mask")}
        logits = model.run(["logits"], feed)[0][:, 0].astype(np.float32)
        scores += (1.0 / (1.0 + np.exp(-logits))).tolist()
    return scores


def timed(score):
    """A warm-up call, then RUNS timed calls: the scores and the median seconds."""
    score()
    seconds = []
    for _ in range(RUNS):
        started = time.perf_counter()
        got = score()
        seconds.append(time.perf_counter() - started)
    return got, round(statistics.median(seconds), 3)


def snapshot_of(model):
    from huggingface_hub import try_to_load_from_cache

    config = try_to_load_from_cache(model, "config.json")
    if not isinstance(config, str):
        raise SystemExit(f"{model} is not in the local cache")
    return Path(config).parent.name


def export(cross_encoder, pairs, raw):
    """torch.onnx's export of the classifier on a padded batch of two pairs, into raw/."""
    import torch

    class Logits(torch.nn.Module):
        def __init__(self, inner):
            super().__init__()
            self.inner = inner

        def forward(self, input_ids, attention_mask):
            return self.inner(input_ids=input_ids, attention_mask=attention_mask).logits

    features = collate(cross_encoder.tokenizer, pairs, cross_encoder.max_length)
    if features["attention_mask"].all():
        raise SystemExit("the export's batch must hold padding")
    args = tuple(torch.from_numpy(features[k]).long() for k in ("input_ids", "attention_mask"))
    raw.mkdir(parents=True)
    with torch.no_grad():
        torch.onnx.export(
            Logits(cross_encoder.model.eval()),
            args,
            str(raw / "model.onnx"),
            input_names=["input_ids", "attention_mask"],
            output_names=["logits"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "length"},
                "attention_mask": {0: "batch", 1: "length"},
                "logits": {0: "batch"},
            },
            opset_version=OPSET,
            do_constant_folding=True,
        )


def one_file(raw, target):
    """The exported model again, its weights in one external file beside it."""
    import onnx

    model = onnx.load(str(raw / "model.onnx"))
    target.parent.mkdir(parents=True)
    onnx.save_model(
        model,
        str(target),
        save_as_external_data=True,
        all_tensors_to_one_file=True,
        location=target.name + ".data",
    )
    del model
    gc.collect()
    onnx.checker.check_model(str(target))


def quantize(source, target, variant):
    from onnxruntime.quantization import QuantType, quantize_dynamic

    target.parent.mkdir(parents=True)
    quantize_dynamic(
        source,
        target,
        per_channel=variant["per_channel"],
        reduce_range=variant["reduce_range"],
        weight_type=getattr(QuantType, variant["weight_type"]),
    )


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out = Path(argv[0])
    if out.exists():
        raise SystemExit(f"{out} exists")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import torch
    from sentence_transformers import CrossEncoder

    if snapshot_of(MODEL) != SNAPSHOT:
        raise SystemExit("the cached snapshot is not the one stage 2 ran")
    torch.set_num_threads(THREADS)
    pairs = synthetic()
    cross_encoder = CrossEncoder(MODEL, device="cpu")
    tokenizer, max_length = cross_encoder.tokenizer, cross_encoder.max_length
    reference, torch_seconds = timed(
        lambda ce=cross_encoder: [float(s) for s in ce.predict(pairs, batch_size=BATCH)]
    )
    ours = collate(tokenizer, pairs, max_length)
    theirs = cross_encoder.smart_batching_collate_text_only(pairs)
    same_inputs = sorted(ours) == sorted(theirs) and all(
        (ours[k] == theirs[k].numpy()).all() for k in ours
    )
    lengths = ours["attention_mask"].sum(axis=1).tolist()
    export(cross_encoder, [pairs[0], pairs[7]], out / "raw")
    del cross_encoder
    gc.collect()
    one_file(out / "raw", out / "fp32" / "model.onnx")
    shutil.rmtree(out / "raw")
    for name, variant in VARIANTS.items():
        quantize(out / "fp32" / "model.onnx", out / name / "model.onnx", variant)
    arms = {}
    for name in ("fp32", *VARIANTS):
        model = session(out / name / "model.onnx")
        scores, seconds = timed(lambda m=model: ort_scores(m, tokenizer, pairs, max_length))
        diffs = [abs(a - b) for a, b in zip(scores, reference, strict=True)]
        order = sorted(range(len(pairs)), key=lambda k: -scores[k])
        arms[name] = {
            "max_abs_diff": max(diffs),
            "median_abs_diff": statistics.median(diffs),
            "same_order": order == sorted(range(len(pairs)), key=lambda k: -reference[k]),
            "seconds": seconds,
        }
        del model
        gc.collect()
    files = {
        str(p.relative_to(out)): {"sha256": sha256(p), "bytes": p.stat().st_size}
        for p in sorted(out.rglob("*"))
        if p.is_file()
    }
    manifest = {
        "spec": "docs/specs/stage4-step5a-int8-reranker.md",
        "tool_sha256": sha256(Path(__file__)),
        "model": MODEL,
        "snapshot": SNAPSHOT,
        "opset": OPSET,
        "threads": THREADS,
        "batch": BATCH,
        "max_length": max_length,
        "variants": VARIANTS,
        "python": sys.version.split()[0],
        "macos": platform.mac_ver()[0],
        "machine": platform.machine(),
        "packages": {n: importlib.metadata.version(n) for n in PACKAGES},
        "files": files,
        "synthetic": {
            "pairs": len(pairs),
            "tokens": [min(lengths), max(lengths)],
            "same_inputs_as_sentence_transformers": bool(same_inputs),
            "torch_seconds": torch_seconds,
            "arms": arms,
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(manifest["synthetic"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
