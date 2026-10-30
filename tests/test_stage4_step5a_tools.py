"""Stage 4, item 5a (docs/specs/stage4-step5a-int8-reranker.md): the blocks on a synthetic
archive with a stand-in scorer, their stand and gate, the series' stops, and the frozen reading of
speed, gold and outcome on hand-made blocks and rows."""

from __future__ import annotations

import gzip
import hashlib
import importlib.metadata
import importlib.util
import json
import re
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "reports/stage4-step5a/tools/int8_reranker.py"
EXPORT_TOOL = ROOT / "reports/stage4-step5a/tools/export_onnx.py"
MANIFEST = ROOT / "reports/stage4-step5a/onnx/manifest.json"


def _load():
    spec = importlib.util.spec_from_file_location("int8_reranker", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["int8_reranker"] = module
    spec.loader.exec_module(module)
    return module


ir = _load()
kc, nr = ir.kc, ir.nr
SETTINGS = {"retrieval_top_k": 20, "rrf_k": 60, "rrf_doc_key_chars": 200}
# The k-curve test's synthetic archive: sixty chunks, three to a document; at K = 20 the pool is
# the thirty candidates 0 to 29 and the five 29 to 25, the WixQA gold doc-9's chunks among them.
SOURCES = [f"doc-{i // 3}" for i in range(60)]
CHUNKS = [{"page_content": f"chunk {i}", "metadata": {"source": s}} for i, s in enumerate(SOURCES)]
VECTOR = list(range(20))
BM25 = list(range(10, 30))
SCORES = {m: m / 100 for m in range(30)}
CASE = {"gold_sources": ["doc-9"], "stratum": "s"}
# ConditionalQA and MultiHop-RAG read gold by evidence groups: doc-9's first five characters,
# which each of its chunks covers in this archive.
EVIDENCE = {
    "evidence_groups": [{"alternatives": [{"source_id": "doc-9", "start": 0, "end": 5}]}],
    "stratum": "s",
}
PLACES = SimpleNamespace(
    source=SOURCES,
    members=lambda documents: [d["metadata"]["chunk_index"] for d in documents],
    by_document=lambda members: {SOURCES[m]: [(0, 10)] for m in members},
)
QUIET = {"matched": [], "others_cpu": 12.5, "ollama": [], "load1": 1.5, "swap_mb": 2000.0}


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """block() sets these for its own process; a test's are put back after it."""
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")


def expand(members):
    """A stand-in expansion that joins nothing: each seed alone, in its order."""
    return [{"metadata": {"chunk_index": m}, "text": f"chunk {m}"} for m in members]


def ident(member):
    return [SOURCES[member], member]


def record(**change):
    """A retrieval record of stage 2's form whose five are the product's path."""
    top = kc.Selection(SETTINGS)(CHUNKS, VECTOR, BM25, SCORES, 20)
    out = {
        "case_id": "wixqa-0001",
        "index": 1,
        "question": "What does the warehouse say?",
        "reranker_ok": True,
        "lanes": {"vector": [ident(m) for m in VECTOR], "bm25": [ident(m) for m in BM25]},
        "pool": [[*ident(m), SCORES[m]] for m in top["pool"]],
        "ranked": [[*ident(m), s] for m, s in zip(top["five"], top["scores"], strict=True)],
        "expanded": [
            {"source": SOURCES[m], "chunk_index": m, "text": f"chunk {m}"} for m in top["five"]
        ],
    }
    out.update(change)
    return out


def make_runs(tmp_path, aircargo=31, others=2):
    """Stage 2's runs and chunk archives in miniature: aircargo's thirty-one, two of the rest."""
    runs, root = tmp_path / "runs", tmp_path / "data"
    for base, label in nr.LABELS.items():
        folder = runs / label / "retrieval"
        folder.mkdir(parents=True)
        (root / base).mkdir(parents=True)
        with gzip.open(root / base / "chunks.json.gz", "wt", encoding="utf-8") as handle:
            json.dump({"chunks": CHUNKS, "tenant_id": "t"}, handle)
        for i in range(1, (aircargo if base == "aircargo" else others) + 1):
            rec = record(case_id=f"{base}-{i:04d}", index=i)
            (folder / f"{i:03d}-{base}-{i:04d}.json").write_text(json.dumps(rec), encoding="utf-8")
    return runs, root


class Fake:
    """A stand-in scorer: each candidate's recorded score, shifted."""

    threads = 4

    def __init__(self, shift=0.0):
        self.shift = shift

    def __call__(self, pairs):
        return [SCORES[int(text.split()[1])] + self.shift for _, text in pairs]


def quiet(monkeypatch):
    facts = {"packages": {}, "snapshot": ir.SNAPSHOT, "files": {}, "python": "3"}
    monkeypatch.setattr(ir, "stand", lambda arm, models: (facts, []))
    monkeypatch.setattr(ir, "sample", lambda own: dict(QUIET))


def test_the_schedule_reads_fp32_then_abba_then_the_four_hundred_and_the_fallback_after():
    assert ir.SCHEDULE[1] == ("fp32", "thirty")
    timing = {v: [ir.SCHEDULE[n][0] for n in plan["timing"]] for v, plan in ir.VARIANTS.items()}
    assert timing == {
        "int8": ["pytorch", "int8", "int8", "pytorch"],
        "int8_u8u8": ["pytorch", "int8_u8u8", "int8_u8u8", "pytorch"],
    }
    assert ir.SCHEDULE[6] == ("int8", "all") and ir.SCHEDULE[11] == ("int8_u8u8", "all")
    assert [ir.VARIANTS[v]["quality"] for v in ir.VARIANTS] == [6, 11]
    assert sorted(ir.SCHEDULE) == list(range(1, 12)) and ir.FIDELITY == 1
    assert list(nr.LABELS) == ["wixqa", "conditionalqa", "multihoprag", "aircargo"]
    with pytest.raises(SystemExit, match="unknown command"):
        ir.main(["replay"])


def test_a_block_warms_on_aircargos_thirty_first_then_reads_the_first_thirty_or_all(tmp_path):
    runs, _ = make_runs(tmp_path)
    thirty = ir.questions_of("thirty", runs)
    assert [b for b, _ in thirty] == ["aircargo"] * 31
    assert thirty[0][1].name.startswith("031-") and thirty[1][1].name.startswith("001-")
    assert thirty[-1][1].name.startswith("030-")
    every = ir.questions_of("all", runs)
    assert every[0] == thirty[0]
    bases = ["wixqa"] * 2 + ["conditionalqa"] * 2 + ["multihoprag"] * 2 + ["aircargo"] * 31
    assert [b for b, _ in every[1:]] == bases


def test_the_pairs_are_the_question_with_each_candidates_archive_text_in_the_pools_order():
    rec = record()
    pairs = ir.pairs_of(rec, CHUNKS)
    assert pairs == [(rec["question"], f"chunk {p[1]}") for p in rec["pool"]]
    assert len(pairs) == 30
    rec["pool"][3] = ["doc-99", rec["pool"][3][1], 0.5]
    with pytest.raises(SystemExit, match="names no chunk"):
        ir.pairs_of(rec, CHUNKS)
    assert ir.pairs_of(record(pool=None), CHUNKS) == []


def _stand(tmp_path, monkeypatch, snapshot=ir.SNAPSHOT, installed=None, **manifest_change):
    models = tmp_path / "models"
    (models / "int8").mkdir(parents=True, exist_ok=True)
    (models / "int8" / "model.onnx").write_bytes(b"int8")
    files = {"int8/model.onnx": {"sha256": hashlib.sha256(b"int8").hexdigest(), "bytes": 4}}
    versions = dict.fromkeys(ir.RUNTIME, "1.0")
    manifest = {"max_length": None, "packages": versions, "files": files, **manifest_change}
    (models / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(ir, "MANIFEST_SHA256", ir.sha256(models / "manifest.json"))
    got = {**versions, **(installed or {})}
    monkeypatch.setattr(importlib.metadata, "version", lambda name: got[name])
    hub = types.ModuleType("huggingface_hub")
    hub.try_to_load_from_cache = lambda model, name: str(tmp_path / snapshot / name)
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    return models


def test_the_stand_is_the_manifests_versions_the_cached_snapshot_and_the_arms_files(
    tmp_path, monkeypatch
):
    models = _stand(tmp_path, monkeypatch)
    facts, reasons = ir.stand("int8", models)
    assert reasons == [] and facts["snapshot"] == ir.SNAPSHOT
    assert facts["files"] == {"int8/model.onnx": hashlib.sha256(b"int8").hexdigest()}
    assert facts["packages"] == dict.fromkeys(ir.RUNTIME, "1.0")
    assert ir.stand("pytorch", models)[0]["files"] == {}
    assert ir.stand("int8_u8u8", models) == (None, ["the export holds no int8_u8u8"])
    (models / "int8" / "model.onnx").write_bytes(b"int9")
    assert ir.stand("int8", models) == (None, ["int8/model.onnx is not the export's"])
    assert ir.stand("pytorch", models)[1] == []
    monkeypatch.setattr(ir, "MANIFEST_SHA256", "0" * 64)
    assert ir.stand("pytorch", models) == (
        None,
        ["the export's manifest is not the registered one"],
    )


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"installed": {"torch": "2.3.0"}}, "torch 2.3.0"),
        ({"snapshot": "0" * 40}, "the cached snapshot is not stage 2's"),
        ({"max_length": 512}, "the export did not read at the tokenizer's own limit"),
    ],
)
def test_another_version_snapshot_or_length_is_not_the_stand(tmp_path, monkeypatch, change, reason):
    models = _stand(tmp_path, monkeypatch, **change)
    assert ir.stand("pytorch", models) == (None, [reason])


def test_a_block_writes_a_head_a_line_a_question_and_an_end_and_its_gate_passes(
    tmp_path, monkeypatch
):
    runs, root = make_runs(tmp_path)
    quiet(monkeypatch)
    out = tmp_path / "out"
    assert ir.block(2, runs, root, tmp_path / "models", out, scorer=Fake()) == 0
    path = out / "blocks" / "02.jsonl"
    assert not (out / "blocks" / "02.partial.jsonl").exists()
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    head, body, end = lines[0], lines[1:-1], lines[-1]
    assert (head["block"], head["arm"], head["kind"], head["threads"]) == (
        2,
        "pytorch",
        "thirty",
        4,
    )
    assert head["tool_sha256"] == ir.sha256(TOOL) and head["beside"] == QUIET
    assert [q["warm_up"] for q in body] == [True] + [False] * 30
    assert [q["case_id"] for q in body[:2]] == ["aircargo-0031", "aircargo-0001"]
    assert all(q["pairs"] == 30 and len(q["scores"]) == 30 for q in body)
    assert all(q["others_cpu"] == 12.5 for q in body)
    assert end["done"] is True and "rss_peak_mib" in end
    assert ir.check(2, path, runs) == ([], 0.0)


def test_a_stand_not_the_registered_one_stops_the_block_before_any_question(tmp_path, monkeypatch):
    runs, root = make_runs(tmp_path)
    monkeypatch.setattr(ir, "stand", lambda arm, models: (None, ["torch 2.3.0"]))
    assert ir.block(3, runs, root, tmp_path / "models", tmp_path / "out", Fake()) == 6
    assert not (tmp_path / "out" / "blocks").exists()
    quiet(monkeypatch)
    two = SimpleNamespace(threads=2)
    assert ir.block(3, runs, root, tmp_path / "models", tmp_path / "out", two) == 6
    assert not (tmp_path / "out" / "blocks").exists()


def _rewrite(path, how):
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    how(lines)
    path.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")


@pytest.mark.parametrize(
    ("how", "reason"),
    [
        (lambda lines: lines[0].update(block=4), "not the schedule's block"),
        (lambda lines: lines[0].update(tool_sha256="0" * 64), "another tool"),
        (lambda lines: lines.pop(), "no end line"),
        (lambda lines: lines.pop(5), "not the schedule's questions"),
        (lambda lines: lines[3].update(record_sha256="0" * 64), "not the schedule's questions"),
        (lambda lines: lines[3]["scores"].__setitem__(0, 1.5), "not a score a candidate"),
        (lambda lines: lines[3]["scores"].pop(), "not a score a candidate"),
        (lambda lines: lines[3].update(scores=[float("nan")] * 30), "not a score a candidate"),
        (lambda lines: lines[3].update(scores=None), "not a score a candidate"),
    ],
)
def test_the_gate_refuses_another_block_another_question_or_a_score_out_of_range(
    tmp_path, monkeypatch, how, reason
):
    runs, root = make_runs(tmp_path)
    quiet(monkeypatch)
    out = tmp_path / "out"
    ir.block(3, runs, root, tmp_path / "models", out, scorer=Fake(0.002))
    path = out / "blocks" / "03.jsonl"
    assert ir.check(3, path, runs)[0] == []
    _rewrite(path, how)
    reasons, _ = ir.check(3, path, runs)
    assert any(reason in r for r in reasons), reasons


def _series(tmp_path, monkeypatch, scorers, idle=True):
    runs, root = make_runs(tmp_path)
    quiet(monkeypatch)
    monkeypatch.setattr(ir, "idle", lambda first, own: idle)

    def launch(number, runs, root, models, out):
        scorer = scorers(number)
        if isinstance(scorer, int):
            return scorer
        return ir.block(number, runs, root, models, out, scorer=scorer)

    monkeypatch.setattr(ir, "launch", launch)
    return runs, root


def _log(out):
    return (out / "series.log").read_text(encoding="utf-8")


def test_the_series_runs_the_blocks_in_order_and_resumes_at_the_first_without_a_file(
    tmp_path, monkeypatch
):
    runs, root = _series(tmp_path, monkeypatch, lambda n: Fake(0.004 if n in (3, 4, 6) else 0))
    out, models = tmp_path / "out", tmp_path / "models"
    out.mkdir()
    (out / "stop").touch()
    assert ir.series(runs, root, models, out, 6) == 3
    (out / "stop").unlink()
    assert ir.series(runs, root, models, out, 6) == 0
    assert sorted(p.name for p in (out / "blocks").glob("*.jsonl")) == [
        f"{n:02d}.jsonl" for n in range(1, 7)
    ]
    log = _log(out)
    assert "block 1 fp32 thirty, attempt 1" in log and log.rstrip().endswith("SERIES_DONE")
    assert "block 3 read: largest difference from the record 4.000e-03" in log
    assert ir.series(runs, root, models, out, 6) == 0
    assert json.loads((out / "series.json").read_text(encoding="utf-8"))["attempts"] == {
        str(n): 1 for n in range(1, 7)
    }
    _rewrite(out / "blocks" / "03.jsonl", lambda lines: lines.pop(4))
    assert ir.series(runs, root, models, out, 6) == 8
    assert "block 3 kept but failing: not the schedule's questions" in _log(out)


@pytest.mark.parametrize(("number", "shift"), [(1, 0.0011), (2, 2e-6)])
def test_a_pytorch_block_off_the_record_or_an_fp32_one_past_its_tolerance_stops_the_series(
    tmp_path, monkeypatch, number, shift
):
    runs, root = _series(tmp_path, monkeypatch, lambda n: Fake(shift if n == number else 0))
    out, models = tmp_path / "out", tmp_path / "models"
    assert ir.series(runs, root, models, out, 6) == 7
    assert f"block {number} fidelity" in _log(out)
    assert (out / "blocks" / f"{number:02d}.jsonl").exists()
    assert not (out / "blocks" / f"{number + 1:02d}.jsonl").exists()
    # The stop holds on a second start.
    assert ir.series(runs, root, models, out, 6) == 7
    assert _log(out).count(f"block {number} fidelity") == 2


def test_a_failed_block_is_tried_again_once_and_then_ends_the_series(tmp_path, monkeypatch):
    runs, root = _series(tmp_path, monkeypatch, lambda n: 1 if n == 2 else Fake())
    out, models = tmp_path / "out", tmp_path / "models"
    assert ir.series(runs, root, models, out, 6) == 8
    assert ir.series(runs, root, models, out, 6) == 8
    assert ir.series(runs, root, models, out, 6) == 9
    assert "block 2 failed: exit 1" in _log(out) and "block 2 failed twice" in _log(out)


@pytest.mark.parametrize(("code", "want"), [(5, 5), (6, 6)])
def test_a_slow_block_or_a_wrong_stand_keep_their_exit(tmp_path, monkeypatch, code, want):
    runs, root = _series(tmp_path, monkeypatch, lambda n: Fake())

    def launch(number, runs, root, models, out):
        (out / "blocks" / f"{number:02d}.partial.jsonl").write_text("{}\n", encoding="utf-8")
        return code

    monkeypatch.setattr(ir, "launch", launch)
    out = tmp_path / "out"
    assert ir.series(runs, root, tmp_path / "models", out, 6) == want
    assert [p.name for p in (out / "rejected").iterdir()] == ["01-1-01.partial.jsonl"]


def test_a_block_file_failing_its_gate_is_put_aside(tmp_path, monkeypatch):
    runs, root = _series(tmp_path, monkeypatch, lambda n: Fake())

    def launch(number, runs, root, models, out):
        ir.block(number, runs, root, models, out, scorer=Fake())
        _rewrite(out / "blocks" / f"{number:02d}.jsonl", lambda lines: lines.pop(4))
        return 0

    monkeypatch.setattr(ir, "launch", launch)
    out = tmp_path / "out"
    assert ir.series(runs, root, tmp_path / "models", out, 6) == 8
    assert not (out / "blocks" / "01.jsonl").exists()
    assert [p.name for p in (out / "rejected").iterdir()] == ["01-1-01.jsonl"]
    assert "block 1 failed: not the schedule's questions" in _log(out)


def test_the_mac_not_idle_within_the_hour_or_another_tool_ends_the_series(tmp_path, monkeypatch):
    runs, root = _series(tmp_path, monkeypatch, lambda n: Fake(), idle=False)
    out = tmp_path / "out"
    assert ir.series(runs, root, tmp_path / "models", out, 6) == 4
    assert "the Mac not idle within an hour" in _log(out) and not (out / "series.json").exists()
    (out / "series.json").write_text(
        json.dumps({"tool_sha256": "0" * 64, "attempts": {}}), encoding="utf-8"
    )
    assert ir.series(runs, root, tmp_path / "models", out, 6) == 6
    assert "another tool started this series" in _log(out)


class Hung:
    """A stand-in block process that never ends unless it is killed."""

    last = None

    def __init__(self, command, **kwargs):
        self.command, self.returncode = command, None
        Hung.last = self

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9

    def wait(self):
        return self.returncode


@pytest.mark.parametrize("head", [False, True])
def test_launch_kills_a_block_whose_head_line_or_next_question_does_not_come(
    tmp_path, monkeypatch, head
):
    out = tmp_path / "out"
    (out / "blocks").mkdir(parents=True)
    if head:
        (out / "blocks" / "03.partial.jsonl").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(ir.subprocess, "Popen", Hung)
    monkeypatch.setattr(ir, "POLL", 0.01)
    monkeypatch.setattr(ir, "START_LIMIT", 60 if head else 0.05)
    monkeypatch.setattr(ir, "QUESTION_LIMIT", 0.05 if head else 60)
    started = time.monotonic()
    assert ir.launch(3, Path("r"), Path("d"), Path("m"), out) == ir.EXIT["slow"]
    assert time.monotonic() - started < 30
    assert Hung.last.returncode == -9
    assert Hung.last.command[1:] == ["-u", str(TOOL), "block", "3", "r", "d", "m", str(out)]


def test_launch_returns_the_blocks_own_exit(tmp_path, monkeypatch):
    class Ended(Hung):
        def __init__(self, command, **kwargs):
            super().__init__(command, **kwargs)
            self.returncode = 6

    (tmp_path / "blocks").mkdir()
    monkeypatch.setattr(ir.subprocess, "Popen", Ended)
    assert ir.launch(3, Path("r"), Path("d"), Path("m"), tmp_path) == 6


def test_idle_reads_the_pattern_ollama_the_lock_the_others_cpu_and_the_first_blocks_load(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(ir, "CI_LOCK", tmp_path / "lock")
    monkeypatch.setattr(ir, "IDLE_LIMIT", 0)
    monkeypatch.setattr(ir.os, "getloadavg", lambda: (1.6, 1.9, 1.7))
    for change, want in [
        ({}, True),
        ({"matched": ["pytest"]}, False),
        ({"ollama": ["qwen3:4b"]}, False),
        ({"others_cpu": 100.1}, False),
        ({"others_cpu": 100.0}, True),
    ]:
        monkeypatch.setattr(ir, "sample", lambda own, c=change: {**QUIET, **c})
        assert ir.idle(True, set()) is want, change
    monkeypatch.setattr(ir.os, "getloadavg", lambda: (1.6, 2.0, 1.7))
    assert ir.idle(True, set()) is False and ir.idle(False, set()) is True
    (tmp_path / "lock").touch()
    assert ir.idle(False, set()) is False


def test_a_sample_reads_ps_without_the_blocks_own_processes(monkeypatch):
    listing = "\n".join(
        [
            "  101  400.0 python int8_reranker.py block 3",
            "  102   0.0 python int8_reranker.py series",
            "  200   30.5 /usr/bin/python -m pytest tests",
            "  201   12.0 /Applications/Chrome Helper (Renderer)",
            "  202    1.0 llama-server --model x",
        ]
    )

    def run(command, **kwargs):
        out = listing if command[0] == "ps" else "total = 6144.00M  used = 4240.00M  free = 1.0M"
        return SimpleNamespace(stdout=out)

    monkeypatch.setattr(ir.subprocess, "run", run)
    monkeypatch.setattr(ir, "ollama_models", lambda: [])
    got = ir.sample({101, 102})
    assert got["matched"] == ["llama-server", "pytest"]
    assert got["others_cpu"] == 43.5 and got["swap_mb"] == 4240.0
    assert ir.disturbed(got) and not ir.disturbed(QUIET)
    assert ir.PATTERN.search(str(TOOL)) is None


def _timed(seconds):
    return {
        "questions": [{"case_id": f"q{i}", "seconds": s, **QUIET} for i, s in enumerate(seconds)]
    }


def test_speed_sets_the_two_pytorch_blocks_mean_against_the_variants_two_by_the_sign_test():
    fast = [17.0] * 21 + [40.0] * 9
    blocks = {2: _timed([30.0] * 30), 3: _timed(fast), 4: _timed(fast), 5: _timed([32.0] * 30)}
    got = ir.speed(blocks, "int8")
    assert (got["readable"], got["faster"], got["slower"]) == (30, 21, 9)
    assert got["p"] == round(nr.mcnemar(21, 9), 6) and got["reading"] == "faster"
    assert got["ratio_median"] == round(31.0 / 17.0, 4) and got["saved_sec_median"] == 14.0
    assert got["block_sec_median"] == {"2": 30.0, "3": 17.0, "4": 17.0, "5": 32.0}
    twenty = [17.0] * 20 + [40.0] * 10
    assert ir.speed({**blocks, 3: _timed(twenty), 4: _timed(twenty)}, "int8")["reading"] == (
        "no detected difference"
    )
    slow = {**blocks, 3: _timed([40.0] * 30), 4: _timed([40.0] * 30)}
    assert ir.speed(slow, "int8")["reading"] == "slower"
    assert ir.speed({2: blocks[2]}, "int8") is None
    zero = {**blocks, 3: _timed([0.0] * 30), 4: _timed([0.0] * 30)}
    assert ir.speed(zero, "int8")["ratio_median"] is None


def test_a_question_disturbed_in_any_of_the_four_blocks_is_not_read_and_under_25_none_is():
    blocks = {n: _timed([30.0 if n in (2, 5) else 17.0] * 30) for n in (2, 3, 4, 5)}
    for i in range(6):
        blocks[(2, 3, 4, 5)[i % 4]]["questions"][i]["others_cpu"] = 150.0
    got = ir.speed(blocks, "int8")
    assert got["readable"] == 24 and got["disturbed"] == [f"q{i}" for i in range(6)]
    assert got["reading"] == ir.NOT_EVIDENCE
    blocks[3]["questions"][5]["others_cpu"] = 10.0
    got = ir.speed(blocks, "int8")
    assert (got["readable"], got["reading"]) == (25, "faster")


def ask(rec, scored, case=CASE, places=PLACES):
    return ir.question("wixqa", case, rec, CHUNKS, places, expand, kc.Selection(SETTINGS), scored)


def test_a_question_takes_each_blocks_five_through_the_products_selection_and_expansion():
    rec = record()
    pool = [p[1] for p in rec["pool"]]
    same = [SCORES[m] for m in pool]
    # Block 6 drops the gold document's three chunks, 27 to 29, below every other candidate.
    dropped = [0.0 if m in (27, 28, 29) else SCORES[m] + 0.0005 for m in pool]
    row = ask(rec, {"wixqa-0001": {1: same, 6: dropped}})
    assert row["blocks"]["1"] == {
        "max_abs_diff": 0.0,
        "shared_of_five": 5,
        "same_five": True,
        "same_order": True,
    }
    assert row["blocks"]["6"]["shared_of_five"] == 2 and not row["blocks"]["6"]["same_five"]
    assert row["blocks"]["6"]["max_abs_diff"] == pytest.approx(0.29)
    hit = {"gold_article": 1.0, "gold_articles": 1.0}
    miss = {"gold_article": 0.0, "gold_articles": 0.0}
    assert row["points"] == {
        "ranked": hit,
        "expanded_ranked": hit,
        "int8": miss,
        "expanded_int8": miss,
    }
    assert row["unresolved"] == [] and row["stratum"] == "s"
    bare = ir.question("aircargo", None, rec, CHUNKS, None, None, kc.Selection(SETTINGS), {})
    assert bare["blocks"] == {} and "points" not in bare


def test_a_variants_five_whose_expansion_cannot_be_read_is_left_out_of_its_pair():
    def members(documents):
        seeds = [d["metadata"]["chunk_index"] for d in documents]
        if 24 in seeds:
            raise ValueError("a chunk that is read has no place in its document")
        return seeds

    rec = record()
    dropped = [0.0 if p[1] in (27, 28, 29) else SCORES[p[1]] for p in rec["pool"]]
    places = SimpleNamespace(source=SOURCES, members=members)
    row = ask(rec, {"wixqa-0001": {6: dropped}}, places=places)
    assert row["unresolved"] == ["int8"] and set(row["points"]) == {"ranked", "expanded_ranked"}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r.update(pool=[]), "holds no pool"),
        (lambda r: r["ranked"].reverse(), "not the recorded five"),
        (lambda r: r.update(expanded=r["expanded"][:4]), "not the recorded one"),
    ],
)
def test_the_recorded_scores_must_give_the_recorded_five_and_its_expansion(change, message):
    rec = record()
    change(rec)
    with pytest.raises(SystemExit, match=message):
        ask(rec, {})


def test_a_block_that_scored_another_pool_stops_the_reading():
    with pytest.raises(SystemExit, match="scored another pool"):
        ask(record(), {"wixqa-0001": {6: [0.5] * 3}})


def made(base, pytorch, variant, unresolved=False):
    """A hand-made row with gold: hits by the primary metric at PyTorch's and block 6's fives."""
    first, second = nr.METRICS[base]

    def point(hit):
        return {first: float(hit), second: 1.0 if hit else 0.0}

    points = {"ranked": point(pytorch), "expanded_ranked": point(pytorch)}
    if not unresolved:
        points.update(int8=point(variant), expanded_int8=point(variant))
    entry = {"max_abs_diff": 0.01, "shared_of_five": 5, "same_five": True, "same_order": True}
    return {
        "case_id": f"{base}-x",
        "base": base,
        "blocks": {"6": entry},
        "points": points,
        "unresolved": ["int8"] if unresolved else [],
    }


def _rows(lost=0, gained=0, base="wixqa", unresolved=0):
    rows = [made(b, True, True) for b in nr.METRICS for _ in range(10)]
    rows += [made(base, True, False)] * lost + [made(base, False, True)] * gained
    rows += [made(base, True, True, unresolved=True)] * unresolved
    return rows


def test_the_gold_reads_a_loss_by_exact_mcnemar_on_a_base_or_pooled_or_a_net_loss_above_two():
    holds = ir.quality(_rows(lost=2), "int8")
    assert holds["reading"] == "holds"
    pooled = holds["pooled"]["expanded"]
    assert (pooled["n"], pooled["b_pytorch_only"], pooled["c_variant_only"]) == (32, 2, 0)
    assert pooled["hits"] == {"pytorch": 32, "int8": 30}
    assert holds["bases"]["wixqa"]["with_gold"] == 12
    assert ir.quality(_rows(lost=3), "int8")["reading"] == "loss"
    assert ir.quality(_rows(lost=3, gained=1), "int8")["reading"] == "holds"
    six = ir.quality(_rows(lost=6, base="multihoprag"), "int8")
    assert six["bases"]["multihoprag"]["expanded"]["reading"] == "loss"
    assert six["reading"] == "loss"
    gain = ir.quality(_rows(gained=6), "int8")
    assert gain["bases"]["wixqa"]["expanded"]["reading"] == "gain" and gain["reading"] == "holds"
    assert ir.quality(_rows(), "int8_u8u8") is None


def test_more_than_five_unread_on_a_base_make_the_gold_not_evidence():
    five = ir.quality(_rows(unresolved=5, base="conditionalqa"), "int8")
    assert five["bases"]["conditionalqa"]["unresolved"] == 5 and five["reading"] == "holds"
    assert five["bases"]["conditionalqa"]["expanded"]["n"] == 10
    six = ir.quality(_rows(unresolved=6, base="conditionalqa"), "int8")
    assert six["bases"]["conditionalqa"]["expanded"] == ir.NOT_EVIDENCE
    assert six["pooled"]["expanded"] == ir.NOT_EVIDENCE and six["reading"] == ir.NOT_EVIDENCE


def _reading(gold, pace, ratio=1.8):
    return {"quality": {"reading": gold}, "speed": {"reading": pace, "ratio_median": ratio}}


def test_the_outcome_reads_the_export_then_int8_and_its_fallback_only_after_a_loss():
    holds = {"reading": "holds"}
    assert ir.outcome(None, {}) == "pending"
    assert ir.outcome({"reading": "fails"}, {}) == ir.NOT_EVIDENCE
    passes = ir.outcome(holds, {"int8": _reading("holds", "faster")})
    assert passes == {"variant": "int8", "passes": True, "speed": "faster", "ratio_median": 1.8}
    same = ir.outcome(holds, {"int8": _reading("holds", "no detected difference")})
    assert same["passes"] is False
    lost = {"int8": _reading("loss", "faster"), "int8_u8u8": {"quality": None, "speed": None}}
    assert ir.outcome(holds, lost) == "pending"
    fallback = {**lost, "int8_u8u8": _reading("holds", "faster", 1.3)}
    assert ir.outcome(holds, fallback)["variant"] == "int8_u8u8"
    both = {**lost, "int8_u8u8": _reading("loss", "faster")}
    assert ir.outcome(holds, both) == {"variant": None, "passes": False}
    assert ir.outcome(holds, {"int8": _reading("holds", ir.NOT_EVIDENCE)}) == ir.NOT_EVIDENCE
    assert ir.outcome(holds, {"int8": _reading(ir.NOT_EVIDENCE, "faster")}) == ir.NOT_EVIDENCE
    # A loss of the gold sends the reading to the fallback whatever INT8's speed reads.
    unread = {**fallback, "int8": _reading("loss", ir.NOT_EVIDENCE)}
    assert ir.outcome(holds, unread)["variant"] == "int8_u8u8"
    assert ir.outcome(holds, {"int8": {"quality": holds, "speed": None}}) == "pending"


def test_read_writes_ids_flags_and_numbers_and_refuses_a_record_with_text(tmp_path, monkeypatch):
    runs, root = _series(tmp_path, monkeypatch, lambda n: Fake(0.0005 if n == 1 else 0))
    out, models = tmp_path / "out", tmp_path / "models"
    models.mkdir()
    (models / "manifest.json").write_text("{}", encoding="utf-8")
    assert ir.series(runs, root, models, out, 6) == 0
    real = ir.question

    def loading(base, runs, root, manifest, scored):
        rows = []
        for path in ir.files_of(runs, base):
            rec = json.loads(path.read_text(encoding="utf-8"))
            case = {"wixqa": CASE, "aircargo": None}.get(base, EVIDENCE)
            select = kc.Selection(SETTINGS)
            rows.append(real(base, case, rec, CHUNKS, PLACES, expand, select, scored))
        return rows, {"label": nr.LABELS[base]}, {"doc-1"}, ["What does the warehouse say?"]

    monkeypatch.setattr(ir, "base_rows", loading)
    target = tmp_path / "record"
    assert ir.read(runs, root, models, out, target) == 0
    got = json.loads((target / "record.json").read_text(encoding="utf-8"))
    assert got["spec"] == ir.SPEC and got["stand_code_sha"] == nr.CODE_SHA
    assert set(got["measure_code_sha256"]) == set(ir.MEASURE_CODE)
    fidelity = got["fidelity"]
    assert (fidelity["reading"], fidelity["questions"], fidelity["same_order"]) == ("holds", 30, 30)
    assert fidelity["max_abs_diff"]["max"] == pytest.approx(0.0005)
    assert got["variants"]["int8"]["quality"]["reading"] == "holds"
    assert got["variants"]["int8"]["quality"]["pooled"]["expanded"]["n"] == 6
    assert got["variants"]["int8"]["speed"]["readable"] == 30
    assert got["variants"]["int8_u8u8"] == {"speed": None, "quality": None}
    assert got["outcome"]["variant"] == "int8"
    assert sorted(got["blocks"]) == [str(n) for n in range(1, 7)]
    assert got["blocks"]["6"]["arm"] == "int8" and got["blocks"]["6"]["seconds"]["n"] == 37
    assert got["by_base"]["wixqa"] == {"6": got["by_base"]["wixqa"]["6"]}
    assert got["by_base"]["aircargo"]["1"]["questions"] == 30
    assert got["attempts"] == {str(n): 1 for n in range(1, 7)} and got["rejected"] == []
    assert len((target / "rows.jsonl").read_text(encoding="utf-8").splitlines()) == 37
    monkeypatch.setattr(ir, "base_rows", lambda *a: (*loading(*a)[:2], {"aircargo-0001"}, []))
    with pytest.raises(SystemExit, match="refused"):
        ir.read(runs, root, models, out, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()


def _sha_lines(spec):
    return dict(re.findall(r"- `([^`]+)` `([0-9a-f]{64})`", spec))


def test_the_tool_measures_what_the_spec_registers():
    spec = (ROOT / ir.SPEC).read_text(encoding="utf-8")
    for phrase in (
        "registered before the first question was scored in ONNX",
        "Forecast, written before the first question was scored",
        "5e308fe",
    ):
        assert phrase in spec, phrase
    constants = (ir.THREADS, ir.BATCH, ir.THIRTY, ir.MIN_READABLE, ir.MAX_UNREAD, ir.NET_LOSS)
    assert constants == (4, 32, 30, 25, 5, 2)
    assert ir.TOLERANCE == {"pytorch": 1e-6, "fp32": 1e-3}
    limits = (ir.START_LIMIT, ir.QUESTION_LIMIT, ir.IDLE_LIMIT, ir.BUSY, ir.LOAD_LIMIT)
    assert limits == (900, 300, 3600, 100.0, 2.0)
    assert ir.EXIT == {
        "stop": 3,
        "idle": 4,
        "slow": 5,
        "stand": 6,
        "fidelity": 7,
        "gate": 8,
        "twice": 9,
    }
    assert set(nr.MEASURE_CODE) < set(ir.MEASURE_CODE)
    assert all((ROOT / name).is_file() for name in ir.MEASURE_CODE)
    listed = _sha_lines(spec)
    for name in (
        "reports/stage4-step5a/tools/int8_reranker.py",
        "reports/stage4-step5a/tools/export_onnx.py",
        "tests/test_stage4_step5a_tools.py",
        "reports/stage4-step5a/onnx/manifest.json",
    ):
        assert listed[name] == hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), name


def test_the_export_is_the_one_its_committed_manifest_names():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert ir.MANIFEST_SHA256 == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert manifest["tool_sha256"] == hashlib.sha256(EXPORT_TOOL.read_bytes()).hexdigest()
    assert (manifest["model"], manifest["snapshot"], manifest["spec"]) == (
        ir.MODEL,
        ir.SNAPSHOT,
        ir.SPEC,
    )
    assert (manifest["threads"], manifest["batch"], manifest["opset"]) == (4, 32, 17)
    assert manifest["max_length"] is None
    assert manifest["variants"] == {
        "int8": {"weight_type": "QInt8", "per_channel": True, "reduce_range": True},
        "int8_u8u8": {"weight_type": "QUInt8", "per_channel": True, "reduce_range": False},
    }
    assert set(manifest["files"]) == {
        "fp32/model.onnx",
        "fp32/model.onnx.data",
        "int8/model.onnx",
        "int8_u8u8/model.onnx",
    }
    assert set(ir.RUNTIME) <= set(manifest["packages"])
    synthetic = manifest["synthetic"]
    assert synthetic["same_inputs_as_sentence_transformers"] is True
    assert synthetic["arms"]["fp32"]["max_abs_diff"] <= ir.TOLERANCE["fp32"]
