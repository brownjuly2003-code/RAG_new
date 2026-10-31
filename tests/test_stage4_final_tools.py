"""Final-package registration: synthetic files only, no Mac, model, HTTP or judge calls."""

import ast
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "reports/stage4-final/tools"


@pytest.fixture
def tools(monkeypatch):
    monkeypatch.syspath_prepend(str(TOOLS))
    modules = {}
    for name in ("common", "stand", "record", "run", "judge", "baseline", "runner", "raise_stand"):
        spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        modules[name] = module
    return SimpleNamespace(**modules)


def journal(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8", newline="\n")


def held(tools):
    c = tools.common
    arms = c.frozen("arms")
    return {
        "settings": {**c.SETTINGS, "reranker_onnx_path": c.ONNX},
        "prompt_id": c.PROMPT,
        "input_limit": 2176,
        "export_sha256": c.INT8,
        "cache_sha256": c.CACHE,
        "ollama": "0.33.2",
        "model_digest": c.MODEL_DIGEST,
        "rerank_batch": None,
        "batch_size": 32,
        "server": {"server_version": "0.33.2", "servers": [{"pid": 1, "started": "synthetic"}]},
        "environment": {
            "executable": c.PY,
            "versions": {"transformers": "4.44.2", "onnxruntime": "1.23.2", "tokenizers": "0.19.1"},
            "ort_version": "1.23.2",
            "ort_module": "synthetic/onnxruntime/__init__.py",
            "tokenizer_snapshot": arms.TOKENIZER_SNAPSHOT,
            "ort_intra_op_num_threads": 0,
            "offline": {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
        },
    }


@pytest.mark.parametrize(
    "key",
    [
        "retrieval_top_k",
        "ollama_context_window",
        "reranker_runtime",
        "ollama_model_name",
        "reranker_model",
        "rerank_top_k",
        "streaming_self_eval_mode",
        "rerank_batch",
        "rag_device",
        "parent_expansion",
        "hybrid_search",
        "llm_provider_profile",
        "model_routing_enabled",
        "request_timeout_sec",
        "streaming_timeout_sec",
        "ollama_request_timeout_sec",
        "reranker_onnx_path",
    ],
)
def test_every_registered_setting_is_required(tools, key):
    receipt = held(tools)
    tools.record.stand_gate(receipt)
    receipt["settings"][key] = "different"
    with pytest.raises(SystemExit, match="effective setting|ONNX path"):
        tools.record.stand_gate(receipt)


@pytest.mark.parametrize(
    "path,value",
    [
        (("prompt_id",), "QA_PROMPT_V3"),
        (("input_limit",), 2636),
        (("export_sha256",), "0" * 64),
        (("cache_sha256",), "0" * 64),
        (("ollama",), "0.33.1"),
        (("model_digest",), "7B"),
        (("rerank_batch",), 7),
        (("batch_size",), 7),
        (("environment", "executable"), "gate/python"),
        (("environment", "versions", "transformers"), "4.41.2"),
        (("environment", "versions", "tokenizers"), "0.19.0"),
        (("environment", "versions", "onnxruntime"), "1.23.1"),
        (("environment", "ort_version"), "1.23.1"),
        (("environment", "tokenizer_snapshot"), "another"),
        (("environment", "ort_intra_op_num_threads"), 4),
        (("environment", "offline", "HF_HUB_OFFLINE"), None),
        (("environment", "offline", "TRANSFORMERS_OFFLINE"), "0"),
        (("server", "servers"), []),
    ],
)
def test_stand_receipt_refuses_drift(tools, path, value):
    receipt = held(tools)
    target = receipt
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    with pytest.raises(SystemExit, match="NOT_EVIDENCE"):
        tools.record.stand_gate(receipt)


@pytest.mark.parametrize("variable", ["", "7", "32"])
def test_environment_refuses_even_a_redundant_batch_override(tools, monkeypatch, variable):
    arms = tools.common.frozen("arms")
    monkeypatch.setattr(arms, "environment", lambda: held(tools)["environment"])
    monkeypatch.setattr(tools.stand, "frozen", lambda _: arms)
    monkeypatch.setenv("RAG_RERANK_BATCH", variable)
    with pytest.raises(SystemExit, match="RAG_RERANK_BATCH"):
        tools.stand.environment()


def test_export_and_cache_files_are_read_only_and_both_checked(tools, tmp_path, monkeypatch):
    export, cache = tmp_path / "model.onnx", tmp_path / "config.ini"
    export.write_bytes(b"synthetic model")
    cache.write_bytes(b"cache-ram = 1024\n")
    monkeypatch.setattr(tools.stand, "INT8", tools.common.sha(export))
    monkeypatch.setattr(tools.stand, "CACHE", tools.common.sha(cache))
    tools.stand.files(export, cache)
    for path in (export, cache):
        saved = path.read_bytes()
        path.write_bytes(saved + b"!")
        with pytest.raises(SystemExit, match="digest differs"):
            tools.stand.files(export, cache)
        assert path.read_bytes() == saved + b"!"
        path.unlink()
        with pytest.raises(SystemExit, match="absent"):
            tools.stand.files(export, cache)
        path.write_bytes(saved)


def test_old_runtime_cannot_choose_model_settings_or_limits(tools, tmp_path, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL_NAME", "inherited-7b")
    env = tools.run.api_environment(
        {
            "DATABASE_URL": "private",
            "OLLAMA_MODEL_NAME": "qwen2.5:7b",
            "OLLAMA_CONTEXT_WINDOW": "4096",
            "RAG_RETRIEVAL_TOP_K": "20",
            "RAG_RERANKER_RUNTIME": "torch",
            "STREAMING_TIMEOUT_SEC": "1200",
            "PROVIDER_REGISTRY_PATH": "old.yml",
            "RAG_RERANK_BATCH": "7",
        },
        tmp_path,
        "wixqa",
        tmp_path / "index",
        tmp_path / "cases",
    )
    assert env["DATABASE_URL"] == "private"
    assert env["CHAT_TENANT"] == "ext_wixqa"
    assert env["RAG_RERANKER_ONNX"] == tools.common.ONNX
    assert env["HF_HUB_OFFLINE"] == env["TRANSFORMERS_OFFLINE"] == "1"
    for key in (
        "OLLAMA_MODEL_NAME",
        "OLLAMA_CONTEXT_WINDOW",
        "RAG_RETRIEVAL_TOP_K",
        "RAG_RERANKER_RUNTIME",
        "STREAMING_TIMEOUT_SEC",
        "PROVIDER_REGISTRY_PATH",
        "RAG_RERANK_BATCH",
    ):
        assert key not in env


@pytest.mark.parametrize("change", [None, "version", "tag", "digest", "servers", "dotenv"])
def test_stand_checks_the_actual_model_and_server_before_api_start(
    tools, tmp_path, monkeypatch, change
):
    from config import settings

    receipt = held(tools)
    monkeypatch.setattr(tools.stand, "ROOT", tmp_path)
    monkeypatch.setattr(tools.stand, "environment", lambda: receipt["environment"])
    monkeypatch.setattr(tools.stand, "files", lambda *a: None)
    monkeypatch.setattr(settings, "get_settings", lambda: SimpleNamespace(**receipt["settings"]))
    calls = []

    def ollama(path):
        calls.append(path)
        if path == "/api/version":
            return {"version": "old" if change == "version" else "0.33.2"}
        assert path == "/api/tags"
        return {
            "models": [
                {
                    "name": "7B" if change == "tag" else tools.common.SETTINGS["ollama_model_name"],
                    "digest": "old" if change == "digest" else tools.common.MODEL_DIGEST,
                }
            ]
        }

    monkeypatch.setattr(tools.stand, "frozen", lambda _: SimpleNamespace(ollama=ollama))
    if change == "servers":
        receipt["server"]["servers"] = []
    monkeypatch.setattr(
        tools.common, "load", lambda *a: SimpleNamespace(ollama=lambda: receipt["server"])
    )
    if change == "dotenv":
        (tmp_path / ".env").write_text("RAG_RETRIEVAL_TOP_K=20\n", "utf-8")
    if change is None:
        assert tools.stand.check() == receipt
        assert calls == ["/api/version", "/api/tags"]
    else:
        with pytest.raises(SystemExit, match="NOT_EVIDENCE"):
            tools.stand.check()
        if change == "dotenv":
            assert calls == []


@pytest.mark.parametrize("change", ["bytes", "absent", "sha", "empty"])
def test_stand_manifest_refuses_any_code_drift(tools, tmp_path, monkeypatch, change):
    monkeypatch.setattr(tools.run, "ROOT", tmp_path)
    path = tmp_path / "code.py"
    path.write_bytes(b"# synthetic\n")
    (tmp_path / "CODE_SHA").write_text("a" * 40, "utf-8")
    manifest = {"code_sha": "a" * 40, "files": {"code.py": tools.common.sha(path)}}
    tools.common.write(tmp_path / "STAND_FILES.json", manifest)
    assert tools.run.code_check() == "a" * 40
    if change == "bytes":
        path.write_bytes(b"changed\n")
    elif change == "absent":
        path.unlink()
    elif change == "sha":
        manifest["code_sha"] = "b" * 40
    else:
        manifest["files"] = {}
    tools.common.write(tmp_path / "STAND_FILES.json", manifest)
    with pytest.raises(SystemExit, match="stand"):
        tools.run.code_check()


def test_batch_refuses_taken_ports_before_starting_children(tools, tmp_path, monkeypatch):
    monkeypatch.setattr(tools.run, "code_check", lambda: "a" * 40)
    monkeypatch.setattr(tools.run, "frozen", lambda _: SimpleNamespace(port_free=lambda p: False))
    with pytest.raises(SystemExit, match="port is taken"):
        tools.run.batch(
            tmp_path / "run",
            "aircargo",
            tmp_path / "cases",
            ["q"],
            tmp_path,
            1,
            False,
            before={"reasons": [], "busy": False},
        )
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("change", ["archive", "receipt"])
def test_registered_corpus_must_match_before_index_copy(tools, tmp_path, monkeypatch, change):
    base = tmp_path / "aircargo"
    base.mkdir()
    archive, receipt = base / "chunks.json.gz", base / "receipt.json"
    archive.write_bytes(b"synthetic compressed chunks")
    receipt.write_bytes(b"synthetic generation")
    hashes = {"receipt.json": tools.common.sha(receipt)}
    monkeypatch.setitem(
        sys.modules, "stage2_common", SimpleNamespace(SOURCE_FILES=("receipt.json",))
    )
    monkeypatch.setattr(
        tools.run,
        "frozen",
        lambda _: SimpleNamespace(
            ARCHIVES={"aircargo": tools.common.sha(archive)},
        ),
    )
    monkeypatch.setattr(tools.run, "aircargo_hashes", lambda: hashes)
    assert tools.run.corpus("aircargo", tmp_path) == hashes
    # Freeze the original archive hash before changing bytes.
    expected = tools.common.sha(archive)
    monkeypatch.setattr(
        tools.run, "frozen", lambda _: SimpleNamespace(ARCHIVES={"aircargo": expected})
    )
    (archive if change == "archive" else receipt).write_bytes(b"changed")
    with pytest.raises(SystemExit, match="corpus archive differs|aircargo generation differs"):
        tools.run.corpus("aircargo", tmp_path)


def test_aircargo_hashes_read_the_real_frozen_assignment_without_import(tools):
    path = ROOT / "reports/stage4-step5a-live/tools/live5a_reader.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assignments = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "CORPUS_SHA256" for t in node.targets)
    ]
    assert len(assignments) == 1
    expected = ast.literal_eval(assignments[0])
    tools.common.frozen("cases")
    from stage2_common import SOURCE_FILES

    assert set(expected) == set(SOURCE_FILES)
    assert len(expected) == 3
    assert all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in expected.values())
    assert tools.run.aircargo_hashes() == expected


def test_aircargo_wrong_generation_reaches_the_real_corpus_refusal(tools, tmp_path):
    tools.common.frozen("cases")
    from stage2_common import SOURCE_FILES

    for name in (*SOURCE_FILES, "chunks.json.gz"):
        path = tmp_path / "aircargo" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic wrong generation")
    # No loader, hash or constant is replaced; an archive refusal cannot satisfy this check.
    with pytest.raises(SystemExit, match="aircargo generation differs"):
        tools.run.corpus("aircargo", tmp_path)


@pytest.mark.parametrize(
    "source",
    [
        "OTHER = {}",
        "def nested():\n    CORPUS_SHA256 = {}",
        "CORPUS_SHA256 = dict()",
        "CORPUS_SHA256 = []",
        "CORPUS_SHA256 = {'a': '0' * 64}",
        "CORPUS_SHA256 = " + repr({"a": "0" * 64, "b": "1" * 64}),
        "CORPUS_SHA256 = " + repr(dict.fromkeys("abcd", "0" * 64)),
        "CORPUS_SHA256 = " + repr({"a": "0" * 64, "b": "1" * 64, "c": "g" * 64}),
        "CORPUS_SHA256 = " + repr({"a": "0" * 64, "b": "1" * 64, "c": "2" * 63}),
        "CORPUS_SHA256 = " + repr({"a": "0" * 64, "b": "1" * 64, "c": 2}),
        "CORPUS_SHA256 = " + repr({"a": "0" * 64, "b": "1" * 64, 3: "2" * 64}),
        "CORPUS_SHA256 = {}\nCORPUS_SHA256 = {}",
        "CORPUS_SHA256 = {",
    ],
)
def test_aircargo_hash_reader_refuses_missing_or_malformed_literal(tools, tmp_path, source):
    path = tmp_path / "reader.py"
    path.write_text(source, encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit, match="aircargo corpus hashes"):
        tools.run.aircargo_hashes(path)


def test_aircargo_hash_reader_never_executes_the_source(tools, tmp_path):
    path = tmp_path / "reader.py"
    expected = {name: str(i) * 64 for i, name in enumerate("abc")}
    path.write_text(
        f"CORPUS_SHA256 = {expected!r}\nraise RuntimeError('must not run')\n",
        encoding="utf-8",
        newline="\n",
    )
    assert tools.run.aircargo_hashes(path) == expected
    path.unlink()
    with pytest.raises(SystemExit, match="aircargo corpus hashes"):
        tools.run.aircargo_hashes(path)


def test_all_final_tools_import_without_executing_live5a():
    # A fresh interpreter covers every entry, including api and external tools, without
    # cached modules concealing an import. The audit hook observes real loaders unchanged.
    script = """
import importlib.util
import sys
from pathlib import Path

tools = Path(sys.argv[1])
sys.path[:0] = [str(tools), str(tools / 'external'), str(tools.parents[2])]
def guard(event, args):
    if event == 'exec' and 'stage4-step5a-live' in Path(args[0].co_filename).parts:
        raise AssertionError('stage4-final imported a live5a module')
sys.addaudithook(guard)
paths = sorted(tools.rglob('*.py'))
for path in paths:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
print('IMPORTED', len(paths))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(TOOLS)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == f"IMPORTED {len(list(TOOLS.rglob('*.py')))}"


def make_run(tools, run, ids):
    from agent.prompts import build_qa_prompt
    from llm.providers.base import flatten_messages

    c = tools.common
    receipt = held(tools)
    run.mkdir(parents=True)
    c.write(run / "stand.json", receipt)
    c.write(run / "stand-after.json", receipt)
    c.write(
        run / "loaded.json",
        {k: receipt["environment"][k] for k in ("tokenizer_snapshot", "ort_intra_op_num_threads")},
    )
    c.write(
        run / "effective_settings.json",
        {
            "settings": {**receipt["settings"], "vectordb_chroma_dir": str(run / "chroma")},
        },
    )
    c.write(
        run / "launch.json",
        {
            "status": "complete",
            "runner_exit": 0,
            "cases": ids,
            "ollama_models_before": [],
            "preload": {"model": c.SETTINGS["ollama_model_name"], "options": {"num_ctx": 3584}},
            "preload_models": [{"name": c.SETTINGS["ollama_model_name"], "context_length": 3584}],
            "llama_pid": 20,
            "llama_pid_after": 20,
            "model": c.SETTINGS["ollama_model_name"],
            "model_digest": c.MODEL_DIGEST,
            "tenant": "aircargo",
            "code_sha": "f" * 40,
            "speed": False,
            "api_pid": 99,
            "cases_sha256": "synthetic",
            "corpus_sha256": {"synthetic": "digest"},
            "chroma_dir": str(run / "chroma"),
            "index_sha256": {"chroma.sqlite3": "synthetic"},
        },
    )
    (run / "api.log").write_text(
        json.dumps({"msg": "Tenant aircargo: Restored 30 chunks"}), "utf-8"
    )
    (run / "prompts").mkdir()
    stages, resources, samples = [], [], []
    for index, case_id in enumerate(ids, 1):
        t0 = index * 100
        question = f"Synthetic question {case_id}?"
        text = flatten_messages(
            [
                {
                    "role": "user",
                    "content": build_qa_prompt(
                        question,
                        [
                            {
                                "page_content": "Synthetic fact.",
                                "metadata": {"source": "synthetic.md"},
                            }
                        ],
                    ),
                }
            ]
        )
        prompt = f"{index:03d}-stream.txt"
        (run / "prompts" / prompt).write_text(text, "utf-8")
        c.write(
            run / "cases" / f"{index:02d}-{case_id}.json",
            {
                "case_id": case_id,
                "question": question,
                "answer": "Synthetic fact [1].",
                "tokens": 5,
                "http_status": 200,
                "t0_monotonic": t0,
                "first_token_sec": 10,
                "result_sec": 40,
                "total_sec": 50,
                "events": [{"type": "result", "route": "auto", "answer": "Synthetic fact [1]."}],
            },
        )
        for stage, end, fields in [
            (
                "hybrid.get_relevant_documents_with_path",
                4,
                {
                    "docs": 5,
                    "path": {"candidates": {"vector": 14, "bm25": 14}, "rerank_status": "ok"},
                },
            ),
            ("hybrid._rerank_scored_with_status", 3, {"docs": 5, "reranker_ok": True}),
            ("ollama.generate_stream", 30, {"prompt_file": prompt}),
        ]:
            stages.append(
                {"stage": stage, "event": "end", "monotonic": t0 + end, "wall_sec": 2, **fields}
            )
        for second in range(t0, t0 + 51, 5):
            resources.append(
                {"monotonic": second, "procs": [[99, 10, 1000, "Python"]], "largest": []}
            )
            samples.append(
                {
                    "monotonic": second,
                    "swap_mib": {"used": 300},
                    "procs": [{"pid": 20, "rss_mib": 2000, "mem_mib": 2500}],
                }
            )
    journal(run / "stages.jsonl", stages)
    journal(run / "resources.jsonl", resources)
    journal(run / "samples.jsonl", samples)
    return run


def test_real_file_readers_build_m1_from_the_sent_prompt(tools, tmp_path):
    from scripts import chat_answer_judge

    run = make_run(tools, tmp_path / "run", ["q1"])
    cases = tools.record.answer_run(run, ["q1"])
    assert cases[0]["path"]["candidates"] == {"vector": 14, "bm25": 14}
    plan = chat_answer_judge.build_plan({"run": run}, {}, retest=1)
    assert len(plan["items"]) == 2
    assert plan["items"][0]["prompt_sha256"] == cases[0]["prompts"][0]["sha256"]
    assert "Synthetic fact." in plan["items"][0]["message"]
    assert tools.record.memory(run, cases) == []
    assert cases[0]["mac_memory"]["llama_mem_mib"] == 2500


@pytest.mark.parametrize("broken_second", [False, True])
def test_runner_orders_requests_and_stops_before_the_next_on_a_broken_path(
    tools, tmp_path, monkeypatch, broken_second
):
    from auth import jwt_handler

    ids = ["q1", "q2", "q3"]
    run = make_run(tools, tmp_path / "run", ids)
    prepared = [tools.common.read(p) for p in sorted((run / "cases").glob("*.json"))]
    (run / "cases").rename(run / "prepared")
    cases_file = tmp_path / "questions.jsonl"
    journal(cases_file, [{"case_id": r["case_id"], "query": r["question"]} for r in prepared])
    calls = []

    def ask(question, cap, token):
        row = prepared[len(calls)]
        assert question == row["question"] and token == "synthetic-token"
        calls.append((row["case_id"], cap))
        if broken_second and len(calls) == 2:
            row["http_status"] = 500
        return row

    monkeypatch.setenv("CHAT_RUN_DIR", str(run))
    monkeypatch.setenv("CHAT_CASES_FILE", str(cases_file))
    monkeypatch.setenv("CHAT_TENANT", "aircargo")
    monkeypatch.setattr(sys, "argv", ["runner.py", ",".join(ids), "5000"])
    monkeypatch.setattr(tools.runner, "observation", lambda *a: None)
    monkeypatch.setattr(tools.runner.time, "monotonic", lambda: 0)
    monkeypatch.setattr(tools.runner, "load", lambda *a: SimpleNamespace(ask=ask, drain=lambda: 0))
    monkeypatch.setattr(jwt_handler, "create_access_token", lambda *a, **k: "synthetic-token")
    if broken_second:
        with pytest.raises(SystemExit, match="chat path broke"):
            tools.runner.main()
        assert calls == [("q1", 3600), ("q2", 3600)]
        assert len(list((run / "cases").glob("*.json"))) == 2
    else:
        tools.runner.main()
        assert calls == [("q1", 3600), ("q2", 3600), ("q3", 3600)]
        assert [c["case_id"] for c in tools.record.answer_run(run, ids)] == ids


@pytest.mark.parametrize("reason", ["operator", "deadline"])
def test_runner_stop_before_first_request(tools, tmp_path, monkeypatch, reason):
    run = tmp_path / "run"
    run.mkdir()
    tools.common.write(run / "launch.json", {"speed": False})
    if reason == "operator":
        (tmp_path / "STOP").touch()
    cases = tmp_path / "questions.jsonl"
    journal(cases, [{"case_id": "q1", "query": "Synthetic?"}])
    monkeypatch.setenv("CHAT_RUN_DIR", str(run))
    monkeypatch.setenv("CHAT_CASES_FILE", str(cases))
    monkeypatch.setattr(sys, "argv", ["runner.py", "q1", "5000"])
    monkeypatch.setattr(tools.runner.time, "monotonic", lambda: 6000 if reason == "deadline" else 0)
    # No ask method: bypassing either stop would fail before it could send a request.
    monkeypatch.setattr(tools.runner, "load", lambda *a: SimpleNamespace())
    with pytest.raises(SystemExit, match="operator stop|forecast reached"):
        tools.runner.main()
    assert list((run / "cases").iterdir()) == []


@pytest.mark.parametrize(
    "file,key,value,match",
    [
        ("launch.json", "status", "NOT_EVIDENCE", "incomplete"),
        ("launch.json", "runner_exit", 5, "incomplete"),
        ("launch.json", "ollama_models_before", ["model"], "unloaded"),
        ("launch.json", "cases", ["other"], "order"),
        ("launch.json", "monitor_failed", True, "monitor"),
        ("loaded.json", "tokenizer_snapshot", "other", "loaded environment"),
        ("stand-after.json", "cache_sha256", "other", "changed"),
    ],
)
def test_answer_admission_refuses_incomplete_or_changed_run(
    tools, tmp_path, file, key, value, match
):
    run = make_run(tools, tmp_path / "run", ["q1"])
    data = tools.common.read(run / file)
    data[key] = value
    tools.common.write(run / file, data)
    with pytest.raises(SystemExit, match=match):
        tools.record.answer_run(run, ["q1"])


def test_missing_setting_is_not_silently_accepted(tools, tmp_path):
    run = make_run(tools, tmp_path / "run", ["q1"])
    data = tools.common.read(run / "effective_settings.json")
    del data["settings"]["retrieval_top_k"]
    tools.common.write(run / "effective_settings.json", data)
    with pytest.raises(SystemExit, match="API settings"):
        tools.record.answer_run(run, ["q1"])


def test_api_must_use_the_copied_index(tools, tmp_path):
    run = make_run(tools, tmp_path / "run", ["q1"])
    settings = tools.common.read(run / "effective_settings.json")
    settings["settings"]["vectordb_chroma_dir"] = "different-index"
    tools.common.write(run / "effective_settings.json", settings)
    with pytest.raises(SystemExit, match="API index"):
        tools.record.answer_run(run, ["q1"])


@pytest.mark.parametrize("change", ["questions", "tenant", "corpus", "index"])
def test_reading_binds_the_question_file_corpus_and_index(tools, tmp_path, monkeypatch, change):
    path = tmp_path / "questions"
    path.write_bytes(b"synthetic")
    launch = {
        "cases_sha256": tools.common.sha(path),
        "tenant": "aircargo",
        "corpus_sha256": {"chunks": "digest"},
        "index_sha256": {"db": "digest"},
    }
    monkeypatch.setattr(tools.run, "corpus", lambda *a: {"chunks": "digest"})
    tools.record.provenance_gate(launch, "aircargo", path, tmp_path)
    key, value = {
        "questions": ("cases_sha256", "different"),
        "tenant": ("tenant", "wixqa"),
        "corpus": ("corpus_sha256", {"chunks": "different"}),
        "index": ("index_sha256", {}),
    }[change]
    launch[key] = value
    with pytest.raises(SystemExit):
        tools.record.provenance_gate(launch, "aircargo", path, tmp_path)


@pytest.mark.parametrize(
    "change",
    ["lane", "empty_lane", "rerank", "path", "drain", "timing", "cap", "prompt", "retrievals"],
)
def test_each_question_stops_on_a_broken_path(tools, tmp_path, change):
    run = make_run(tools, tmp_path / "run", ["q1"])
    case = tools.record.answer_run(run, ["q1"])[0]
    if change in ("lane", "empty_lane"):
        case["path"]["candidates"]["bm25"] = 20 if change == "lane" else 0
    else:
        key, value = {
            "rerank": ("reranker_ok", False),
            "path": ("path_breaks", ["broken"]),
            "drain": ("drain_error", "timeout"),
            "timing": ("result_sec", float("nan")),
            "cap": ("total_sec", 3600),
            "prompt": ("prompts", []),
            "retrievals": ("retrievals", 2),
        }[change]
        case[key] = value
    with pytest.raises(SystemExit):
        tools.record.case_gate(case)


@pytest.fixture
def hundred(tools, tmp_path, monkeypatch):
    ids = [f"q{n:03d}" for n in range(100)]
    path = tmp_path / "questions.jsonl"
    journal(path, [{"case_id": i, "query": f"Synthetic question {i}?"} for i in ids])
    monkeypatch.setattr(tools.record, "questions", lambda *_: (path, ids))
    monkeypatch.setattr(tools.run, "corpus", lambda *a: {"synthetic": "digest"})
    runs = tmp_path / "runs"
    for n in range(10):
        run = make_run(
            tools, runs / f"final-answers-aircargo-b{n + 1:02d}", ids[n * 10 : (n + 1) * 10]
        )
        launch = tools.common.read(run / "launch.json")
        launch["cases_sha256"] = tools.common.sha(path)
        tools.common.write(run / "launch.json", launch)
    return runs


def test_all_ten_batches_freeze_115_requests_and_15_bridge_copies(
    tools, hundred, tmp_path, v4_source
):
    private, receipt = tmp_path / "private", tmp_path / "plans.json"
    pin = tools.judge.make_plans(
        "aircargo", hundred, tmp_path, private, receipt, v4_source=v4_source[0], old_m1=v4_source[1]
    )
    assert pin["requests"] == {"m1": 115, "bridge": 15}
    assert "Synthetic question" not in receipt.read_text("utf-8")
    for metric in ("m1", "bridge"):
        assert pin["plans"][metric] == tools.common.sha(private / metric / "plan.json")
    assert (
        tools.common.read(private / "m1/plan.json")["reading"]["source"]
        == "docs/specs/handover-signal.md"
    )


def test_nine_batches_cannot_freeze_a_plan(tools, hundred, tmp_path):
    (hundred / "final-answers-aircargo-b10").rename(hundred / "unfinished")
    with pytest.raises(SystemExit, match="ten batches"):
        tools.judge.make_plans(
            "aircargo", hundred, tmp_path, tmp_path / "private", tmp_path / "plans.json"
        )
    assert not (tmp_path / "private").exists()


def test_receipt_must_be_committed_and_plan_bytes_must_match(tools, tmp_path, monkeypatch):
    tools.common.write(tmp_path / "private/m1/plan.json", {"items": []})
    receipt = tmp_path / "plans.json"
    tools.common.write(
        receipt, {"plans": {"m1": tools.common.sha(tmp_path / "private/m1/plan.json")}}
    )
    monkeypatch.setattr(tools.judge, "ROOT", tmp_path)
    committed = receipt.read_bytes()
    monkeypatch.setattr(tools.judge.subprocess, "check_output", lambda *a, **k: committed)
    tools.judge.committed(receipt, tmp_path / "private", "m1")
    tools.common.write(tmp_path / "private/m1/plan.json", {"items": ["changed"]})
    with pytest.raises(SystemExit, match="plan not"):
        tools.judge.committed(receipt, tmp_path / "private", "m1")
    receipt.write_bytes(committed + b" ")
    with pytest.raises(SystemExit, match="uncommitted"):
        tools.judge.committed(receipt, tmp_path / "private", "m1")


def test_judge_forecast_counts_requests_and_keeps_the_crossing_reply(tools, tmp_path, monkeypatch):
    clock, calls = [0], []
    monkeypatch.setattr(tools.judge.time, "monotonic", lambda: clock[0])

    def reply(*values):
        calls.append(values)
        clock[0] += 200
        return "paid reply"

    send = tools.judge.timed_sender(tmp_path, 1, reply)
    assert send("rules", "question") == "paid reply"
    clock[0] += 99999  # Sleep/usage-window waits are not request time.
    send = tools.judge.timed_sender(tmp_path, 1, reply)
    assert send("rules", "question") == "paid reply"
    assert tools.common.read(tmp_path / "grade-clock.json")["request_seconds"] == 400
    with pytest.raises(SystemExit, match="judge 3x forecast"):
        send("rules", "next")
    assert len(calls) == 2
    with pytest.raises(SystemExit, match="already stopped"):
        tools.judge.timed_sender(tmp_path, 1, reply)


@pytest.mark.parametrize(
    "cluster,newcombe,direction",
    [
        ((0.01, 0.2), (0.02, 0.3), "rises"),
        ((-0.3, -0.02), (-0.2, -0.01), "falls"),
        ((0.0, 0.2), (0.02, 0.3), "not detected"),
        ((0.01, 0.2), (-0.01, 0.3), "not detected"),
        ((0.01, 0.2), (-0.3, -0.01), "not detected"),
    ],
)
def test_v4_paired_rule_requires_both_intervals_on_the_same_side(
    tools, monkeypatch, cluster, newcombe, direction
):
    from evaluation import semantic_ruler

    v4 = tools.common.frozen("v4")
    monkeypatch.setattr(tools.record, "frozen", lambda _: v4)
    monkeypatch.setattr(v4, "newcombe", lambda *a: newcombe)
    monkeypatch.setattr(
        semantic_ruler, "cluster_summary", lambda *a: {"ci95": cluster, "clusters": 1}
    )
    result = tools.record.paired({"q": 0}, {"q": 1}, {"q": ["q"]})
    assert result["direction"] == direction
    assert result["read95"] == [min(cluster[0], newcombe[0]), max(cluster[1], newcombe[1])]


@pytest.mark.parametrize(
    "bad,good,m3,expected",
    [
        ("not detected", "not detected", "not detected", "holds"),
        ("rises", "rises", "rises", "harm detected"),
        ("falls", "falls", "rises", "harm detected"),
        ("falls", "rises", "falls", "harm detected"),
        ("falls", "not detected", "not detected", "gain detected"),
    ],
)
def test_three_quality_outcomes_and_harm_priority(tools, bad, good, m3, expected):
    values = [{"direction": d} for d in (bad, good, m3)]
    assert tools.record.outcome(*values) == expected
    assert tools.record.outcome(*values, admitted=False) == "NOT_EVIDENCE"


@pytest.fixture
def quality_inputs(tools, hundred, tmp_path):
    from evaluation import isolated_request
    from scripts import chat_answer_judge as answer

    measured = tools.record.answers(hundred, "aircargo", tmp_path)
    export = tools.common.frozen("export")
    reading = {"text": export.reading_text((ROOT / export.HANDOVER).read_text("utf-8"))}
    paths = []
    for name, module, code, prompt in (
        ("old_m1", answer, "4f48fed", "QA_PROMPT_V4"),
        ("new_m1", answer, "f" * 40, "QA_PROMPT_V4"),
    ):
        path = tmp_path / f"{name}.json"
        tools.common.write(
            path,
            {
                "status": "counted",
                "retest": {"passed": True},
                "base": "aircargo",
                "judge": "answers",
                "replies": {"admitted_cli": {"9.9.9": 115}},
                "provenance": {
                    "route": isolated_request.settings(module.SYSTEM_PROMPT),
                    "salt": module.SALT,
                    "instructions_sha256": answer._digest(module.INSTRUCTIONS),
                    "reading": reading,
                    "prompt_id": prompt,
                    "runs": {"batch": {"code_sha": code}},
                    "plan_sha256": "plan-digest",
                    "verdicts_sha256": "reply-digest",
                },
            },
        )
        journal(
            path.with_suffix(".cases.jsonl"),
            [
                {
                    "case_id": c["case_id"],
                    "grade": "good",
                    "prompt_sha256": c["prompts"][0]["sha256"],
                    "context_has_answer": True,
                }
                for c in measured["cases"]
            ],
        )
        paths.append(path)
    bridge = tmp_path / "bridge.json"
    tools.common.write(
        bridge,
        {
            "status": "counted",
            "retest": {"passed": True},
            "source_plan_sha256": "plan-digest",
            "source_verdicts_sha256": "reply-digest",
            "admitted_cli": {"old": ["9.9.8"], "new": ["9.9.9"]},
        },
    )
    return measured, [*paths, bridge]


def test_quality_pairs_all_100_and_requires_julia_only_for_bad_rising(tools, quality_inputs):
    measured, paths = quality_inputs
    result = tools.record.quality("aircargo", measured, *paths)
    assert result["outcome"] == "holds" and result["stage5"] == "follows"
    assert result["m1_bad"]["n"] == result["m3"]["n"] == 100
    assert len(result["input_sha256"]) == 5
    new_rows = tools.common.rows(paths[1].with_suffix(".cases.jsonl"))
    for row in new_rows:
        row["grade"] = "bad"
    journal(paths[1].with_suffix(".cases.jsonl"), new_rows)
    result = tools.record.quality("aircargo", measured, *paths)
    assert result["outcome"] == "harm detected"
    assert result["stage5"] == "wait for Julia's yes/no"


@pytest.mark.parametrize(
    "change",
    [
        "stability",
        "route",
        "salt",
        "rules",
        "reading",
        "stand",
        "prompt",
        "pair",
        "missing",
        "invalid",
        "duplicate",
    ],
)
def test_quality_refuses_unpaired_unstable_or_different_judging(tools, quality_inputs, change):
    measured, paths = quality_inputs
    path = paths[1]
    rec = tools.common.read(path)
    table = tools.common.rows(path.with_suffix(".cases.jsonl"))
    if change == "stability":
        rec["retest"]["passed"] = False
    elif change == "route":
        rec["provenance"]["route"]["effort"] = "low"
    elif change in ("salt", "rules", "reading", "stand"):
        key, value = {
            "salt": ("salt", "different"),
            "rules": ("instructions_sha256", "different"),
            "reading": ("reading", {"text": "different"}),
            "stand": ("runs", {"batch": {"code_sha": "old"}}),
        }[change]
        rec["provenance"][key] = value
    elif change == "prompt":
        table[0]["prompt_sha256"] = "different"
    elif change == "pair":
        table.pop()
    elif change == "duplicate":
        table.append(table[0])
    else:
        table[0]["grade"] = None if change == "missing" else "invented"
    tools.common.write(path, rec)
    journal(path.with_suffix(".cases.jsonl"), table)
    with pytest.raises(SystemExit):
        tools.record.quality("aircargo", measured, *paths)


def speed_cases():
    return [
        {"case_id": f"q{i}", "first_token_sec": i, "result_sec": i + 30, "total_sec": i + 35}
        for i in range(1, 31)
    ]


def test_exact_speed_intervals_sign_test_and_slo(tools):
    cases = speed_cases()
    record = tools.record.speed_read(cases, cases)
    assert record["times"]["first_token_sec"]["median"]["point"] == 15.5
    assert record["times"]["result_sec"]["p90"]["point"] == 57
    assert record["times"]["total_sec"]["p90"]["point"] == 62
    assert "decides nothing" in record["comparison"]
    assert record["times"]["result_sec"]["p90"]["ranks"][1] == 31
    assert record["times"]["result_sec"]["p90"]["ci95"][1] is None
    assert record["paired_19beeb1"]["result_sec"]["p_exact"] == 1
    assert record["slo_proposal_seconds"] == {"first_token_sec": 30, "result_sec": 60}
    assert tools.record.slo(60) == 60 and tools.record.slo(60.001) == 90
    old = {str(i): 10 for i in range(30)}
    for wins, expected in ((20, "not detected"), (21, "faster")):
        result = tools.record.sign(old, {str(i): 9 if i < wins else 11 for i in range(30)})
        assert result["direction"] == expected
    assert tools.record.sign({"q": 10}, {"q": 10})["ties"] == 1
    descriptive = tools.record.speed_read(cases, cases, cases)["item5_descriptive"]
    assert descriptive == {"first_token_sec": 15.5, "result_sec": 45.5}


@pytest.mark.parametrize(
    "key,value",
    [
        ("source", "other"),
        ("status", "NOT_EVIDENCE"),
        ("cases_sha256", "different"),
        ("input_sha256", {}),
    ],
)
def test_speed_refuses_a_baseline_from_other_questions_or_without_receipts(tools, key, value):
    baseline = {
        "source": "19beeb1",
        "status": "counted",
        "cases_sha256": "same",
        "input_sha256": {"runs.json": "digest"},
    }
    tools.record.baseline_gate(baseline, "19beeb1", "same")
    baseline[key] = value
    with pytest.raises(SystemExit):
        tools.record.baseline_gate(baseline, "19beeb1", "same")


@pytest.mark.parametrize("change", ["29", "duplicate", "nan", "disturbed", "baseline", "item5"])
def test_no_speed_proposal_from_an_unreadable_series(tools, change):
    cases, old, descriptive, reasons = speed_cases(), speed_cases(), None, []
    if change == "29":
        cases.pop()
    elif change == "duplicate":
        cases[-1] = cases[0]
    elif change == "nan":
        cases[0]["result_sec"] = float("nan")
    elif change == "disturbed":
        reasons = ["foreign Python >=512 MiB"]
    elif change == "baseline":
        old.pop()
    else:
        descriptive = list(reversed(cases))
    with pytest.raises(SystemExit):
        tools.record.speed_read(cases, old, descriptive, reasons)


@pytest.mark.parametrize("kind", ["foreign", "vm", "two_llamas", "gap", "missing_swap", "order"])
def test_sampler_catches_disturbance_and_missing_observation(tools, tmp_path, kind):
    run = make_run(tools, tmp_path / "run", ["q1"])
    samples = tools.common.rows(run / "samples.jsonl")
    resources = tools.common.rows(run / "resources.jsonl")
    if kind in ("foreign", "vm"):
        resources[0]["largest"] = [
            [8, 1, 512 * 2**20, "Python" if kind == "foreign" else "Virtualization"]
        ]
    elif kind == "two_llamas":
        samples[-1]["procs"][0]["pid"] = 21
    elif kind == "gap":
        resources = []
    elif kind == "order":
        resources.reverse()
    else:
        for sample in samples:
            sample["swap_mib"] = None
    journal(run / "samples.jsonl", samples)
    journal(run / "resources.jsonl", resources)
    assert tools.record.memory(run, tools.record.answer_run(run, ["q1"], completed=False))


def test_owned_observers_are_not_another_projects_job(tools, tmp_path):
    run = make_run(tools, tmp_path / "run", ["q1"])
    launch = tools.common.read(run / "launch.json")
    launch.update(supervisor_pid=3, runner_pid=4)
    tools.common.write(run / "launch.json", launch)
    resources = tools.common.rows(run / "resources.jsonl")
    for row in resources:
        row["largest"] = [[p, 0, 600 * 2**20, "Python"] for p in (3, 4)]
    journal(run / "resources.jsonl", resources)
    assert tools.record.memory(run, tools.record.answer_run(run, ["q1"], completed=False)) == []
    sample = {"loadavg": "{ 0.1 0.2 0.3 }", "procs": [], "largest": [[3, 0, 600 * 2**20, "Python"]]}
    assert tools.run.idle(sample, [], False, [], own_pids=(3,)) == []


@pytest.mark.parametrize("kind", ["load", "model", "lock", "jobs", "python", "vm"])
def test_idle_check_refuses_other_work(tools, kind):
    sample = {"loadavg": "{ 0.1 0.2 0.3 }", "procs": [], "largest": []}
    if kind == "load":
        sample["loadavg"] = "{ 1.0 2.0 3.0 }"
    if kind in ("python", "vm"):
        sample["largest"] = [[1, 1, 512 * 2**20, "Python" if kind == "python" else "qemu"]]
    assert tools.run.idle(
        sample, ["model"] if kind == "model" else [], kind == "lock", [8] if kind == "jobs" else []
    )
    if kind == "load":
        assert tools.run.idle(sample, [], False, [], check_load=False) == []


def test_baseline_adapter_cannot_use_the_wrong_rerun_or_missing_times(tools, tmp_path):
    path = tmp_path / "runs.json"
    cases = [{"case": c["case_id"], "http": 200, **c} for c in speed_cases()]
    data = {
        "schema": "chat-live/v1",
        "code_sha": "19beeb1" + "0" * 33,
        "dataset": {"sha256": "dataset"},
        "runs": [
            {
                "label": "qwen3-4b-instruct-q30-r2",
                "status": "complete",
                "runner_exit": 0,
                "model_digest": tools.common.MODEL_DIGEST,
                "cases": cases,
            }
        ],
    }
    tools.common.write(path, data)
    ids = [c["case"] for c in cases]
    result = tools.baseline.extract("19beeb1", path, ids, "dataset")
    assert result["cases"] == speed_cases()
    data["runs"][0]["cases"][0]["result_sec"] = None
    tools.common.write(path, data)
    with pytest.raises(SystemExit, match="timing missing"):
        tools.baseline.extract("19beeb1", path, ids, "dataset")
    data["runs"][0]["label"] = "qwen3-4b-instruct-q30"
    tools.common.write(path, data)
    with pytest.raises(SystemExit, match="one idle rerun"):
        tools.baseline.extract("19beeb1", path, ids, "dataset")


def test_forecasts_caps_and_fixed_pin_lists(tools):
    assert tools.common.forecast(100, 10) == 31800
    assert tools.common.forecast(30, 1) == 9180
    assert tools.common.forecast(30, 1, tools.common.MAX_REASK) == 10980
    expected = {p.relative_to(ROOT).as_posix() for p in TOOLS.glob("*.py")}
    expected.add("tests/test_stage4_final_tools.py")
    for name in ("stage4-item6-final-aircargo.md", "stage4-item7-final-speed.md"):
        text = (ROOT / "docs/specs" / name).read_text("utf-8")
        assert re.search(
            r"Status: \*\*(draft — to be cold-read and registered|registered before the run)\*\*",
            text,
        )
        pins = re.findall(r"`([^`]+)` `([0-9a-f]{64})`", text)
        assert len(pins) == len(expected) and {p for p, _ in pins} == expected
        for path, digest in pins:
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path


@pytest.mark.parametrize("change", [None, "options", "window", "pid"])
def test_preload_uses_product_settings_and_binds_the_runner(tools, tmp_path, change):
    settings = held(tools)["settings"]
    calls = []

    def ollama(path, payload=None, **kwargs):
        calls.append((path, payload))
        if path == "/api/generate":
            assert payload["options"] == {"num_ctx": settings["ollama_context_window"]}
            if change == "options":
                payload.pop("options")
        return {
            "models": [
                {
                    "name": settings["ollama_model_name"],
                    "context_length": 4096 if change == "window" else 3584,
                }
            ]
        }

    sampler = SimpleNamespace(LOG="unused", sample=lambda _: {"procs": [{"pid": 20}]})
    if change in ("options", "window"):
        with pytest.raises(SystemExit, match="num_ctx|context_length"):
            tools.run.preload(SimpleNamespace(ollama=ollama), sampler, settings)
    else:
        launch = tools.run.preload(SimpleNamespace(ollama=ollama), sampler, settings)
        assert launch["llama_pid"] == 20
        assert [p for p, _ in calls] == ["/api/generate", "/api/ps"]
        run = make_run(tools, tmp_path / "run", ["q1"])
        if change == "pid":
            held_launch = tools.common.read(run / "launch.json")
            held_launch["llama_pid_after"] = 21
            tools.common.write(run / "launch.json", held_launch)
            with pytest.raises(SystemExit, match="pid changed"):
                tools.record.answer_run(run, ["q1"])


@pytest.mark.parametrize(
    "speed,clears,resident",
    [(False, False, False), (True, False, False), (True, True, False), (False, False, True)],
)
def test_idle_wait_is_bounded_logged_and_quality_can_proceed_busy(
    tools, tmp_path, monkeypatch, speed, clears, resident
):
    clock, readings = [0], []
    monkeypatch.setattr(tools.run.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(tools.run.time, "sleep", lambda sec: clock.__setitem__(0, clock[0] + sec))

    def sample():
        readings.append(clock[0])
        return {
            "reasons": []
            if clears and clock[0] == 60
            else ["a model is resident" if resident else "another job"]
        }

    monkeypatch.setattr(tools.run, "idle_check", sample)
    log = tmp_path / "wait.json"
    if (speed and not clears) or resident:
        with pytest.raises(SystemExit, match="still busy|model is resident"):
            tools.run.wait_idle(log, 10000, speed)
    else:
        before = tools.run.wait_idle(log, 10000, speed)
        assert before["busy"] is (not clears)
    assert readings == list(range(0, 61 if clears else 1801, 60))
    assert len(tools.common.read(log)["readings"]) == len(readings)
    assert list(tmp_path.iterdir()) == [log]


@pytest.mark.parametrize("never", [False, True])
def test_unload_waits_for_both_ps_and_process_before_idle_after(
    tools, tmp_path, monkeypatch, never
):
    clock, calls = [0], []
    monkeypatch.setattr(tools.run.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(tools.run.time, "sleep", lambda sec: clock.__setitem__(0, clock[0] + sec))

    def ollama(path, payload=None, **kwargs):
        calls.append(path)
        return {"models": [{"name": "model"}] if never or clock[0] < 1 else []}

    sampler = SimpleNamespace(
        LOG="unused", sample=lambda _: {"procs": [{"pid": 20}] if never or clock[0] < 2 else []}
    )
    sup = SimpleNamespace(ollama=ollama, now=lambda: str(clock[0]))
    if never:
        with pytest.raises(SystemExit, match="unload did not finish"):
            tools.run.unload(sup, sampler, "model", tmp_path / "unload.json")
        assert clock[0] == 60
    else:
        tools.run.unload(sup, sampler, "model", tmp_path / "unload.json")
        assert clock[0] == 2
        assert tools.common.read(tmp_path / "unload.json")[-1] == {
            "at": "2",
            "models": [],
            "pids": [],
        }
    assert calls.count("/api/generate") == 1
    # The actual cleanup must wait before its post-run idle reading.
    source = (TOOLS / "run.py").read_text("utf-8")
    assert source.index('unload(sup, sampler, launch["model"]') < source.index(
        'write(run / "idle-after.json"'
    )


@pytest.mark.parametrize("dirty", [b"", b" M tracked.py\n", b"M  tracked.py\n"])
def test_archive_ignores_untracked_but_refuses_tracked_edits(tools, monkeypatch, dirty):
    calls = []

    def git(command, **kwargs):
        calls.append(command)
        if command[1] == "status":
            assert command == ["git", "status", "--porcelain", "--untracked-files=no"]
            return dirty  # Untracked files are excluded by git; archive cannot contain them.
        raise RuntimeError("reached HEAD check")

    monkeypatch.setattr(sys, "argv", ["raise_stand.py", "a" * 40])
    monkeypatch.setattr(tools.raise_stand.subprocess, "check_output", git)
    with pytest.raises(
        SystemExit if dirty else RuntimeError, match="dirty checkout" if dirty else "HEAD check"
    ):
        tools.raise_stand.main()
    assert len(calls) == (1 if dirty else 2)


def verdict_reply(item, cli="9.9.9", bad=False):
    from evaluation import isolated_request as isolated

    return {
        "item_id": item["item_id"],
        "message_sha256": item["message_sha256"],
        "status": "valid",
        "model": isolated.MODEL,
        "session": {
            "cli_version": cli,
            "model": isolated.MODEL,
            "loaded": {k: [] for k in isolated.LOADED},
            "builtin": {"plugins": [], "agents": []},
            "turns": 1,
        },
        "raw_text": json.dumps(
            {
                "claims_total": 1,
                "claims_supported": 0 if bad else 1,
                "context_has_answer": True,
                "answers_question": "full",
                "citations_supported": 1,
                "reference": "none",
                "defect": "none",
                "note": "synthetic",
            }
        ),
    }


@pytest.fixture
def v4_source(tools, hundred, tmp_path):
    from scripts import chat_answer_judge as answer

    source = tmp_path / "v4-private"
    runs = {p.name: p for p in hundred.iterdir()}
    plan = answer.build_plan(runs, {}, retest=15)
    for record in plan["runs"].values():
        record["code_sha"] = "4f48fed" + "0" * 33
    export = tools.common.frozen("export")
    plan["reading"] = {"text": export.reading_text((ROOT / export.HANDOVER).read_text("utf-8"))}
    tools.common.write(source / "plan.json", plan)
    journal(source / "verdicts.jsonl", [verdict_reply(i) for i in plan["items"]])
    old = tmp_path / "v4.json"
    tools.common.write(
        old,
        {
            "status": "counted",
            "retest": {"passed": True},
            "base": "aircargo",
            "judge": "answers",
            "provenance": {
                **{
                    k: plan[k]
                    for k in (
                        "route",
                        "salt",
                        "instructions_sha256",
                        "reading",
                        "prompt_id",
                        "runs",
                    )
                },
                "plan_sha256": tools.common.sha(source / "plan.json"),
                "verdicts_sha256": tools.common.sha(source / "verdicts.jsonl"),
            },
        },
    )
    journal(
        old.with_suffix(".cases.jsonl"),
        [
            {"case_id": i["case_id"], "context_has_answer": True}
            for i in plan["items"]
            if "retest_of" not in i
        ],
    )
    return source, old


@pytest.mark.parametrize("bad", [False, True])
def test_bridge_keeps_original_bytes_grades_only_copies_and_reads_stability(
    tools, hundred, tmp_path, v4_source, bad
):
    from scripts import chat_answer_judge as answer

    private, receipt = tmp_path / "private", tmp_path / "receipt.json"
    pin = tools.judge.make_plans(
        "aircargo", hundred, tmp_path, private, receipt, v4_source=v4_source[0], old_m1=v4_source[1]
    )
    bridge = private / "bridge"
    plan = tools.common.read(bridge / "plan.json")
    original = (bridge / "verdicts.jsonl").read_bytes()
    source_lines = (v4_source[0] / "verdicts.jsonl").read_bytes().splitlines(keepends=True)
    assert all(line in source_lines for line in original.splitlines(keepends=True))
    assert len(answer._vouched(plan, tools.common.rows(bridge / "verdicts.jsonl"))) == 15
    copies = [i for i in plan["items"] if "retest_of" in i]
    with (bridge / "verdicts.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
        for item in copies:
            stream.write(json.dumps(verdict_reply(item, cli="9.9.10", bad=bad)) + "\n")
    result = tools.judge.bridge_export(bridge, pin, tmp_path / "bridge.json")
    assert result["status"] == ("NOT_EVIDENCE" if bad else "counted")
    assert result["retest"]["pairs"] == 15
    assert result["admitted_cli"] == {"old": ["9.9.9"], "new": ["9.9.10"]}
    assert (bridge / "verdicts.jsonl").read_bytes().startswith(original)


@pytest.mark.parametrize("change", ["plan", "verdicts", "missing"])
def test_laptop_inputs_refuse_missing_or_changed_private_files(tools, tmp_path, v4_source, change):
    source, old = v4_source
    tools.judge.inputs(tmp_path, source, old)
    target = source / ("plan.json" if change == "plan" else "verdicts.jsonl")
    if change == "missing":
        target.unlink()
    else:
        target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises((SystemExit, OSError)):
        tools.judge.inputs(tmp_path, source, old)


@pytest.mark.parametrize("losses,expected", [(0, "holds"), (4, "holds"), (5, "harm detected")])
def test_m3_reads_the_same_field_at_v4_ceiling(tools, quality_inputs, losses, expected):
    measured, paths = quality_inputs
    table = tools.common.rows(paths[1].with_suffix(".cases.jsonl"))
    for row in table[:losses]:
        row["context_has_answer"] = False
    journal(paths[1].with_suffix(".cases.jsonl"), table)
    result = tools.record.quality("aircargo", measured, *paths)
    assert result["m3_old_ceiling"]["hits"] == result["m3_old_ceiling"]["n"] == 100
    assert result["outcome"] == expected
    assert result["m3"]["direction"] != "rises"
    assert result["stage5"] == "follows"


@pytest.mark.parametrize(
    "change", ["bridge", "bridge_plan", "bridge_replies", "ceiling", "missing_m3"]
)
def test_quality_cannot_read_a_failed_bridge_or_another_m3_instrument(
    tools, quality_inputs, change
):
    measured, paths = quality_inputs
    if change.startswith("bridge"):
        value = tools.common.read(paths[2])
        if change == "bridge":
            value["retest"]["passed"] = False
        elif change == "bridge_replies":
            value["source_verdicts_sha256"] = "other"
        else:
            value["source_plan_sha256"] = "other"
        tools.common.write(paths[2], value)
    else:
        path = paths[0 if change == "ceiling" else 1].with_suffix(".cases.jsonl")
        table = tools.common.rows(path)
        table[0]["context_has_answer"] = False if change == "ceiling" else None
        journal(path, table)
    with pytest.raises(SystemExit):
        tools.record.quality("aircargo", measured, *paths)


@pytest.mark.parametrize("disturbed", [0, 1, 6, 7])
def test_reask_selection_is_external_and_bounded(tools, disturbed):
    first = [
        {**c, "disturbed": ["foreign job"] if n < disturbed else []}
        for n, c in enumerate(speed_cases())
    ]
    ids = [c["case_id"] for c in first]
    # Fast disturbed questions repeat; a very slow clean one is retained.
    first[-1]["result_sec"] = 3500
    first[-1]["total_sec"] = 3590
    again = [
        {**c, "disturbed": [], "result_sec": 999, "total_sec": 1000} for c in first[:disturbed]
    ]
    if disturbed > 6:
        with pytest.raises(SystemExit, match="more than 6"):
            tools.record.select_attempts(first + again, ids)
    else:
        selected = tools.record.select_attempts(first + again, ids)
        assert selected[:disturbed] == again
        assert selected[disturbed:] == first[disturbed:]
        assert selected[-1]["result_sec"] == 3500
        assert first[0]["result_sec"] == 31


def test_second_disturbance_wrong_order_or_missing_reask_refuses(tools):
    first = [
        {**c, "disturbed": ["foreign job"] if n in (1, 3) else []}
        for n, c in enumerate(speed_cases())
    ]
    ids = [c["case_id"] for c in first]
    again = [{**first[n], "disturbed": []} for n in (1, 3)]
    for wrong in (
        again[:1],
        list(reversed(again)),
        [again[0], {**again[1], "disturbed": ["foreign job"]}],
    ):
        with pytest.raises(SystemExit, match="re-ask order|disturbed twice"):
            tools.record.select_attempts(first + wrong, ids)


def test_speed_prompt_pairing_uses_attempt_time_and_runner_reasks_after_30(
    tools, tmp_path, monkeypatch
):
    from auth import jwt_handler

    ids = [f"q{n}" for n in range(30)]
    run = make_run(tools, tmp_path / "run", ids + [ids[1], ids[3]])
    launch = tools.common.read(run / "launch.json")
    launch.update(speed=True, cases=ids)
    tools.common.write(run / "launch.json", launch)
    resources = tools.common.rows(run / "resources.jsonl")
    for row in resources:
        if row["monotonic"] in (200, 400):
            row["job_pids"] = [500]
    journal(run / "resources.jsonl", resources)
    prepared = [tools.common.read(p) for p in sorted((run / "cases").glob("*.json"))]
    (run / "cases").rename(run / "prepared")
    casefile = tmp_path / "questions.jsonl"
    journal(casefile, [{"case_id": c["case_id"], "query": c["question"]} for c in prepared[:30]])
    calls = []

    def ask(question, cap, token):
        row = prepared[len(calls)]
        assert question == row["question"]
        calls.append(row["case_id"])
        return row

    monkeypatch.setenv("CHAT_RUN_DIR", str(run))
    monkeypatch.setenv("CHAT_CASES_FILE", str(casefile))
    monkeypatch.setenv("CHAT_TENANT", "aircargo")
    monkeypatch.setattr(sys, "argv", ["runner.py", ",".join(ids), "99999"])
    monkeypatch.setattr(tools.runner.time, "monotonic", lambda: 0)
    monkeypatch.setattr(tools.runner, "observation", lambda *a: None)
    monkeypatch.setattr(tools.runner, "load", lambda *a: SimpleNamespace(ask=ask, drain=lambda: 0))
    monkeypatch.setattr(jwt_handler, "create_access_token", lambda *a, **k: "synthetic")
    tools.runner.main()
    assert calls == ids + [ids[1], ids[3]]
    attempts = tools.record.answer_run(run, ids, all_attempts=True)
    assert len(attempts) == 32
    selected = tools.record.select_attempts(attempts, ids)
    assert selected[1]["index"] == 31 and selected[3]["index"] == 32
    assert [c["index"] for c in attempts if c["disturbed"]] == [2, 4]
    assert len({c["prompts"][0]["file"] for c in attempts}) == 32


@pytest.mark.parametrize("speed", [False, True])
def test_busy_start_logs_without_a_speed_run_but_quality_starts(
    tools, tmp_path, monkeypatch, speed
):
    clock, calls = [0], []
    monkeypatch.setattr(tools.run.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(tools.run.time, "sleep", lambda sec: clock.__setitem__(0, clock[0] + sec))
    monkeypatch.setattr(tools.run, "idle_check", lambda: {"reasons": ["another job"]})
    monkeypatch.setattr(
        tools.run, "questions", lambda *a: (tmp_path / "questions", [str(n) for n in range(100)])
    )

    def batch(*args, **kwargs):
        calls.append(kwargs["before"])
        raise RuntimeError("quality proceeds")

    monkeypatch.setattr(tools.run, "batch", batch)
    out = tmp_path / "run"
    monkeypatch.setattr(
        sys,
        "argv",
        ["run.py", "speed" if speed else "answers", "--out", str(out), "--exclusive-owned-work"],
    )
    with pytest.raises(
        SystemExit if speed else RuntimeError, match="still busy" if speed else "quality proceeds"
    ):
        tools.run.main()
    assert not out.exists()
    assert len(list(tmp_path.iterdir())) == 1
    assert len(calls) == (0 if speed else 1)
    if calls:
        assert calls[0]["busy"] is True


def test_speed_requires_the_exclusive_work_declaration_before_waiting(tools, tmp_path, monkeypatch):
    monkeypatch.setattr(
        tools.run, "questions", lambda *a: (tmp_path / "questions", [str(n) for n in range(100)])
    )
    monkeypatch.setattr(
        tools.run, "wait_idle", lambda *a: pytest.fail("must refuse before any Mac observation")
    )
    monkeypatch.setattr(sys, "argv", ["run.py", "speed", "--out", str(tmp_path / "run")])
    with pytest.raises(SystemExit, match="exclusive owned work"):
        tools.run.main()
    assert list(tmp_path.iterdir()) == []


def test_completed_paid_reply_is_journalled_and_exportable_after_clock_stop(
    tools, tmp_path, monkeypatch
):
    from evaluation import isolated_request as isolated
    from scripts import chat_answer_judge as answer

    run = make_run(tools, tmp_path / "run", ["q1", "q2"])
    plan = answer.build_plan({"run": run}, {}, retest=1)
    folder = tmp_path / "judge"
    tools.common.write(folder / "plan.json", plan)
    export = tools.common.frozen("export")
    export.add_reading(folder, (ROOT / export.HANDOVER).read_text("utf-8"), "synthetic")
    plan = tools.common.read(folder / "plan.json")
    clock = [0]
    monkeypatch.setattr(tools.judge.time, "monotonic", lambda: clock[0])

    def reply(*args):
        clock[0] += 400
        row = verdict_reply(plan["items"][0])
        return isolated.IsolatedReply(row["raw_text"], isolated.MODEL, {}, 400, row["session"])

    send = tools.judge.timed_sender(folder, 1, reply)
    with pytest.raises(SystemExit, match="judge 3x forecast"):
        answer.run_plan(plan, folder, send)
    replies = tools.common.rows(folder / "verdicts.jsonl")
    assert len(replies) == 1 and replies[0]["status"] == "valid"
    # Exercise the wrapper's export branch despite its stop marker, with the real exporter.
    monkeypatch.setattr(tools.judge, "committed", lambda *a: {"base": "aircargo"})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "judge.py",
            "export",
            "--base",
            "aircargo",
            "--metric",
            "m1",
            "--private",
            str(tmp_path / "private"),
            "--receipt",
            str(tmp_path / "receipt"),
            "--runs",
            str(tmp_path),
            "--out",
            str(tmp_path / "out"),
        ],
    )
    (tmp_path / "private").mkdir()
    folder.rename(tmp_path / "private/m1")
    tools.judge.main()
    result = tools.common.read(tmp_path / "out/final-aircargo-m1.json")
    assert result["requests_valid"] == 1
    assert result["status"] == "NOT_EVIDENCE"


def test_partial_live_observation_is_excluded_by_its_flushed_checkpoint(tools, tmp_path):
    run = make_run(tools, tmp_path / "run", ["q1"])
    checkpoint = {
        name: (run / (name + ".jsonl")).stat().st_size for name in ("resources", "samples")
    }
    for name in checkpoint:
        with (run / (name + ".jsonl")).open("ab") as stream:
            stream.write(b'{"partial":')
    cases = tools.record.answer_run(run, ["q1"], completed=False, checkpoint=checkpoint)
    assert tools.record.memory(run, cases, checkpoint=checkpoint) == []
    with pytest.raises(ValueError):
        tools.record.memory(run, cases)  # A finished corrupt journal is never silently repaired.


def test_bridge_receipt_protects_the_original_reply_prefix(
    tools, hundred, tmp_path, v4_source, monkeypatch
):
    private, receipt = tmp_path / "private", tmp_path / "receipt.json"
    tools.judge.make_plans(
        "aircargo", hundred, tmp_path, private, receipt, v4_source=v4_source[0], old_m1=v4_source[1]
    )
    committed = receipt.read_bytes()
    monkeypatch.setattr(tools.judge, "ROOT", tmp_path)
    monkeypatch.setattr(tools.judge.subprocess, "check_output", lambda *a, **k: committed)
    tools.judge.committed(receipt, private, "bridge")
    path = private / "bridge/verdicts.jsonl"
    path.write_bytes(b" " + path.read_bytes())
    with pytest.raises(SystemExit, match="bridge replies changed"):
        tools.judge.committed(receipt, private, "bridge")
