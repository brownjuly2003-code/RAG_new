"""Runner tests with stand-in input checks, processes and clocks."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import chroma_restart_stability_run as runner


def _answers():
    return {"vector": [[0], [1]], "candidates": [[0, 1], [1, 0]]}


def _build():
    return {
        "build_ms": 250,
        "embed_documents_call_lengths": [2],
        "collection_count": 2,
        "restored_chunk_count": 2,
        "hnsw": {"space": "l2"},
        "chroma_log_max_seq_id": 10,
        "chroma_vector_persisted_seq_id": 7,
        "settings": {"retrieval_top_k": 1, "rrf_k": 60, "rrf_doc_key_chars": 200},
        "answers": _answers(),
    }


def _trial():
    return {"restored_chunk_count": 2, "settings": _build()["settings"], "answers": _answers()}


def _harness(tmp_path, **overrides):
    calls = []

    def load(*args):
        calls.append(("load", args))
        return {
            "texts": ["a", "b"],
            "cases": [{"query": "q0"}, {"query": "q1"}],
            "text_digest": "digest",
            "input_sha256": {"archive": "hash"},
        }

    def code():
        calls.append(("code",))
        return "a" * 40

    def mkdir(path):
        calls.append(("mkdir", path))
        path.mkdir()

    def spawn(args, **kwargs):
        calls.append(("spawn", args, kwargs))
        payload = _build() if args[3] == "build" else _trial()
        return SimpleNamespace(returncode=0, stdout="diagnostic\n" + json.dumps(payload) + "\n")

    def remove(path):
        calls.append(("remove", path))
        path.rmdir()

    options = dict(
        vectors_path=tmp_path / "vectors.npz",
        queries_path=tmp_path / "queries.npy",
        temp_dir=tmp_path,
        platform_name="darwin",
        environ={"ANONYMIZED_TELEMETRY": "False", "FROM_RUNNER": "yes"},
        input_loader=load,
        code_base_provider=code,
        directory_creator=mkdir,
        remove_dir=remove,
        spawner=spawn,
        token_hex=lambda count: "0123456789abcdef",
        source_sha_provider=lambda commit: {path: "hash" for path in runner.SOURCE_FILES},
        versions_provider=lambda: {"numpy": "2", "chromadb": "1.5.9"},
        host_reader=lambda name: "host-value",
        load_reader=lambda: (1.0, 2.0, 3.0),
        utc_now=lambda: "2026-09-25T00:00:00Z",
        clock=iter(range(100)).__next__,
    )
    options.update(overrides)
    return calls, options


def test_valid_reference_inputs_are_accepted_and_processes_are_sequential(tmp_path):
    calls, options = _harness(tmp_path)
    output = tmp_path / "out.json"
    report = runner.run_measurement(output, **options)
    assert [item[0] for item in calls[:3]] == ["load", "code", "mkdir"]
    assert len([item for item in calls if item[0] == "spawn"]) == 8
    assert [item[1][3] for item in calls if item[0] == "spawn"] == ["build"] + ["trial"] * 7
    assert [item[1][5] for item in calls if item[0] == "spawn" and item[1][3] == "trial"] == [
        str(index) for index in range(7)
    ]
    assert calls[-1][0] == "remove"
    assert report["status"] == "measured"
    assert report["input_sha256"] == {"archive": "hash"}
    assert report["source_sha256"] == {path: "hash" for path in runner.SOURCE_FILES}
    assert report["build"]["unpersisted_tail"] == 3
    assert not calls[2][1].exists()
    raw = output.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert '\n  "status"' in raw
    assert json.loads(raw) == report


def test_relative_input_paths_are_resolved_before_loading_and_spawning(tmp_path, monkeypatch):
    launch_dir = tmp_path / "launch"
    launch_dir.mkdir()
    monkeypatch.chdir(launch_dir)
    expected_vectors = Path("v.npz").resolve()
    expected_queries = Path("q.npy").resolve()
    calls, options = _harness(tmp_path, vectors_path="v.npz", queries_path="q.npy")

    runner.run_measurement(tmp_path / "out.json", **options)

    load_args = next(item[1] for item in calls if item[0] == "load")
    assert load_args[1:3] == (expected_vectors, expected_queries)
    children = [item[1] for item in calls if item[0] == "spawn"]
    assert len(children) == 8
    for args in children:
        assert args[args.index("--vectors") + 1] == str(expected_vectors)
        assert args[args.index("--queries") + 1] == str(expected_queries)


@pytest.mark.parametrize(
    "platform_name,environ",
    [
        ("win32", {"ANONYMIZED_TELEMETRY": "False"}),
        ("darwin", {}),
        ("darwin", {"ANONYMIZED_TELEMETRY": "True"}),
    ],
)
def test_mode_preflight_has_no_side_effects(tmp_path, platform_name, environ):
    calls, options = _harness(tmp_path, platform_name=platform_name, environ=environ)
    with pytest.raises(ValueError):
        runner.run_measurement(tmp_path / "out.json", **options)
    assert calls == []


def test_existing_output_is_refused_before_input_checks(tmp_path):
    calls, options = _harness(tmp_path)
    output = tmp_path / "out.json"
    output.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError):
        runner.run_measurement(output, **options)
    assert calls == []
    assert output.read_text(encoding="utf-8") == "existing"


def test_d1_input_failure_precedes_git_directory_and_process(tmp_path):
    calls, options = _harness(tmp_path)

    def fail(*args):
        calls.append(("load", args))
        raise ValueError("input D.1 did not use: queries.npy")

    options["input_loader"] = fail
    with pytest.raises(ValueError, match="queries.npy"):
        runner.run_measurement(tmp_path / "out.json", **options)
    assert [item[0] for item in calls] == ["load"]


def test_git_check_precedes_directory_and_process(tmp_path):
    calls, options = _harness(tmp_path)

    def fail():
        calls.append(("code",))
        raise RuntimeError("tracked git worktree must be clean")

    options["code_base_provider"] = fail
    with pytest.raises(RuntimeError, match="clean"):
        runner.run_measurement(tmp_path / "out.json", **options)
    assert [item[0] for item in calls] == ["load", "code"]


def test_child_command_environment_timeout_and_last_json_line(tmp_path):
    calls, options = _harness(tmp_path)
    runner.run_measurement(tmp_path / "out.json", **options)
    for _, args, kwargs in (item for item in calls if item[0] == "spawn"):
        assert args[:3] == [sys.executable, "-m", "scripts.chroma_restart_stability"]
        assert kwargs["cwd"] == runner.ROOT
        assert kwargs["timeout"] == 900
        assert kwargs["env"]["ANONYMIZED_TELEMETRY"] == "False"
        assert kwargs["env"]["FROM_RUNNER"] == "yes"


@pytest.mark.parametrize("failure", ["exit", "timeout", "json", "array"])
def test_child_failure_removes_directory_without_report(tmp_path, failure):
    calls, options = _harness(tmp_path)
    original = options["spawner"]

    def fail(args, **kwargs):
        if args[3] == "trial" and args[5] == "2":
            if failure == "timeout":
                raise subprocess.TimeoutExpired(args, 900)
            if failure == "exit":
                return SimpleNamespace(returncode=2, stdout="{}\n")
            return SimpleNamespace(returncode=0, stdout="[]\n" if failure == "array" else "no")
        return original(args, **kwargs)

    options["spawner"] = fail
    output = tmp_path / "out.json"
    with pytest.raises((RuntimeError, ValueError)):
        runner.run_measurement(output, **options)
    assert calls[-1][0] == "remove"
    assert not calls[-1][1].exists()
    assert not output.exists()


def test_build_import_error_stderr_is_reported_and_cleaned_up(tmp_path):
    calls, options = _harness(tmp_path)

    def fail(args, **kwargs):
        calls.append(("spawn", args, kwargs))
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="Traceback (most recent call last):\nImportError: x",
        )

    options["spawner"] = fail
    output = tmp_path / "out.json"
    with pytest.raises(RuntimeError, match="ImportError: x") as error:
        runner.run_measurement(output, **options)
    assert "Traceback (most recent call last): | ImportError: x" in str(error.value)
    assert calls[-1][0] == "remove"
    assert not calls[-1][1].exists()
    assert not output.exists()


def test_invalid_child_json_includes_only_stderr_tail():
    stderr = "earlier detail\n" + "x" * 2100 + "\nImportError: x"

    def spawn(args, **kwargs):
        return SimpleNamespace(returncode=0, stdout="not JSON", stderr=stderr)

    with pytest.raises(ValueError, match="invalid child JSON object") as error:
        runner._run_child(["child"], "build", spawn, {}, iter((1.0, 1.1)).__next__)
    message = str(error.value)
    assert "earlier detail" not in message
    assert message.endswith(stderr[-2000:].replace("\n", " | "))
    assert "\n" not in message


def test_cleanup_failed_report_is_not_evidence(tmp_path):
    calls, options = _harness(tmp_path, remove_dir=lambda path: calls.append(("remove", path)))
    report = runner.run_measurement(tmp_path / "out.json", **options)
    assert report["status"] == "cleanup_failed"
    assert calls[-1][1].exists()


def test_invalid_report_json_leaves_no_output(tmp_path):
    calls, options = _harness(tmp_path, host_reader=lambda _: float("nan"))
    output = tmp_path / "out.json"
    with pytest.raises(ValueError, match="Out of range float values"):
        runner.run_measurement(output, **options)
    assert calls[-1][0] == "remove"
    assert not output.exists()


def test_source_hashes_are_from_git_show_at_commit():
    seen = []

    def git(args, **kwargs):
        seen.append((args, kwargs))
        return SimpleNamespace(stdout=args[-1].encode())

    result = runner._source_sha256("a" * 40, git_runner=git)
    assert set(result) == set(runner.SOURCE_FILES)
    for path in runner.SOURCE_FILES:
        assert result[path] == hashlib.sha256(f"{'a' * 40}:{path}".encode()).hexdigest()
    assert all(args[:2] == ["git", "show"] for args, _ in seen)
    assert all(kwargs["cwd"] == runner.ROOT for _, kwargs in seen)


def test_versions_include_all_pinned_packages(monkeypatch):
    seen = []

    def version(name):
        seen.append(name)
        return "1"

    monkeypatch.setattr(runner.importlib.metadata, "version", version)
    assert runner._versions() == {name: "1" for name in seen}
    assert seen == ["numpy", "chromadb", "langchain-chroma", "langchain-core", "rank-bm25"]


def test_cli_failure_is_one_line_and_exits_one(tmp_path, capsys):
    def fail(*args, **kwargs):
        raise ValueError("input D.1 did not use: queries.npy")

    assert (
        runner.main(
            ["--vectors", "v", "--queries", "q", "--output", str(tmp_path / "out.json")],
            measurement_fn=fail,
        )
        == 1
    )
    assert capsys.readouterr().out.splitlines() == ["input D.1 did not use: queries.npy"]
    assert not Path(tmp_path / "out.json").exists()
