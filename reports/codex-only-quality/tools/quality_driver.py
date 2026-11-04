"""Offline registration only. Every request command deliberately refuses in task 19b-2.

Uses copy_verify's private config, plus:
  copy_receipt: absolute receipt JSON
  release: {root: absolute detached checkout, commit: full SHA, python: absolute interpreter}
  stands: {<key>: {env: absolute env file}}
  artifacts: {<label>: absolute file} for every ARTIFACTS entry below
  private_inputs also contains environment and assets (complete inventories).
Version artifacts are saved CLI version observations; registration never executes a CLI.
Each version JSON holds {version: nonempty string, executable_sha256: SHA-256}.
Helper verification/default receipts hold {passed: true, files: {repo path: SHA-256}}
and bind both extended helpers plus their deployment tests. shim_build is the
unchanged build_shim.py JSON output, binding the C# source to the installed exe.
--records/--series/registration.json is public. Private filenames are hashed; setting
values are restricted to an explicit nonsecret whitelist. Pending later-task artifacts
are enumerated, so this receipt alone never authorizes a request.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import importlib
import io
import json
import os
import re
import shutil

# Only fixed, offline git/Python commands; no shell.
import subprocess  # nosec B404
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Direct invocation and path-based test loading both use the sibling admission code.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import copy_verify as cv  # noqa: E402

ROOT = HERE.parents[2]
SPEC = "docs/specs/codex-only-quality.md"
STAGE5 = "reports/stage4-final/stage5/2057ad0/record.json"
ATTEMPT = "reports/generator-ceiling/attempt-02"
ARTIFACTS = (
    "shim_executable",
    "shim_build",
    "shim_config",
    "codex_executable",
    "codex_version",
    "claude_executable",
    "claude_version",
    "helper_verification",
    "unchanged_defaults",
)
HELPER_FILES = (
    "deploy/windows/write_env.py",
    "deploy/windows/prepare_postgres.py",
    "tests/test_windows_deployment.py",
    "tests/test_windows_service_start.py",
)
PUBLIC_FILES = (
    SPEC,
    "docs/specs/generator-ceiling.md",
    "docs/evidence/generator-ceiling-record.md",
    "reports/codex-only-quality/tools/copy_verify.py",
    "reports/codex-only-quality/tools/quality_driver.py",
    "reports/codex-only-quality/tools/quality_read.py",
    "reports/codex-only-quality/tools/capture_journal.py",
    "reports/codex-only-quality/tools/build_shim.py",
    "reports/codex-only-quality/tools/shim_check.py",
    "reports/codex-only-quality/tools/shim/CaptureShim.cs",
    "tests/test_codex_only_quality_register.py",
    "tests/test_codex_only_quality_capture.py",
    "tests/test_windows_deployment.py",
    "tests/test_windows_service_start.py",
    "deploy/windows/write_env.py",
    "deploy/windows/prepare_postgres.py",
    "deploy/windows/_support.py",
    "deploy/windows/start.py",
    "deploy/macos/start.py",
    "deploy/windows/requirements-win.lock",
    "docs/operations/windows-service.md",
    "config/providers.yml",
    "config/settings.py",
    "llm/providers/codex.py",
    "llm/providers/runtime.py",
    "llm/codex_wrapper.txt",
    "agent/graph.py",
    "agent/doc_grade.py",
    "agent/graph_stream.py",
    "agent/prompts.py",
    "api/routers/conversation.py",
    "api/routers/session_auth.py",
    "static/chat.inline.js",
    "reports/stage4-final/tools/common.py",
    "reports/stage4-final/tools/stand.py",
    "reports/stage4-final/tools/external/reading.py",
    "reports/stage4-final/tools/external/sent_gold.py",
    "evaluation/external_gold.py",
    "evaluation/external_parts.py",
    "evaluation/external_parts.json",
    "evaluation/external_bases.py",
    "evaluation/external_bases.json",
    "evaluation/power.py",
    "evaluation/curated_cases_aircargo.jsonl",
    "evaluation/aircargo_corpus.manifest.json",
    "scripts/external_base.py",
    "scripts/external_pilot.py",
    "scripts/corpus_manifest.py",
    "scripts/corpus_chunks.py",
    "scripts/production_index.py",
    cv.AIRCARGO_ANSWERS,
    cv.AIRCARGO_GENERATION,
    "reports/stage7/tools/arms_replay.py",
    "reports/stage2/tools/retrieval_summary.py",
    STAGE5,
    ATTEMPT + "/reading.json",
)
EXTRA_SETTINGS = ("hyde", "codex_reasoning_effort", "codex_timeout_sec", "streaming_rag_parity")

# Reviewed against graph.py: all LLM dispatch sites, including unreachable sites.
# The source pin also covers guards, edges, helper dispatch and loops, so adding an
# alias or changing an edge cannot silently retain the old maximum.
# Hash UTF-8 with normalized LF, independent of Python's version-specific AST fields.
GRAPH_SOURCE_SHA256 = "6b504f4dcb7ee2a7b8d05e88fc03293d2d1dd9d766fbda67fbbdebbe707d0727"
CALL_SITES = {
    "_generate_answer_text": ["_stream_llm_tokens", "_invoke_llm"],
    "_agentic_terminal_fields_with_eval": ["_invoke_llm"],
    "make_classify_complexity_node": ["_invoke_with_schema", "_invoke_llm"],
    "make_transform_query_node": ["_invoke_llm", "_invoke_llm"],
    "make_grade_docs_node": [
        "_invoke_with_schema",
        "_invoke_llm",
        "_invoke_with_schema",
        "_invoke_llm",
        "_invoke_llm",
    ],
    "make_generate_node": ["_generate_answer_text"],
    "make_verify_facts_node": ["_invoke_llm", "_invoke_with_schema", "_invoke_llm"],
    "make_evaluate_node": ["_invoke_llm"],
    "make_suggest_questions_node": ["_invoke_llm"],
    "make_rewrite_query_node": ["_invoke_llm"],
    "ConversationSession": ["generate_with_tools"],
}
REACHABLE = (
    ("transform_query", "fast", 1, "one transform; HyDE disabled"),
    ("grade_docs", "fast", 1, "one batch; Codex has no structured output or per-document fallback"),
    ("generate", "answer", 1, "one answer; provider adapter emits completed Codex reply"),
)
EXCLUDED = {
    "classification": "model_routing_enabled=false",
    "HyDE": "hyde=false",
    "verify/evaluate/suggest/agentic-eval": "codex-only guards return before dispatch",
    "rewrite/retry": "codex-only route returns only auto/human; no retry edge reachable",
    "tool loop": "answer target exists; _select_agentic_llm returns None",
}


def graph_sites(source: str) -> dict[str, list[str]]:
    result = {}
    names = {name for calls in CALL_SITES.values() for name in calls}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            calls = []
            for call in ast.walk(node):
                if isinstance(call, ast.Call):
                    name = (
                        call.func.id
                        if isinstance(call.func, ast.Name)
                        else call.func.attr
                        if isinstance(call.func, ast.Attribute)
                        else ""
                    )
                    if name in names:
                        calls.append((call.lineno, name))
            if calls:
                result[node.name] = [name for _, name in sorted(calls)]
    return result


def graph_bound(path: Path, settings: dict[str, Any], providers: dict[str, Any]) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    cv.require(graph_sites(source) == CALL_SITES, "graph LLM call sites changed")
    source_hash = cv.digest(source)
    cv.require(source_hash == GRAPH_SOURCE_SHA256, "graph control flow needs renewed review")
    cv.require(
        settings["llm_provider_profile"] == "codex-only"
        and settings["model_routing_enabled"] is False
        and settings["hyde"] is False
        and settings["streaming_rag_parity"] is False,
        "graph bound settings differ",
    )
    calls = [
        {
            "node": node,
            "target": target,
            "maximum": maximum,
            "reason": reason,
            "timeout_sec": providers[target]["timeout_sec"],
        }
        for node, target, maximum, reason in REACHABLE
    ]
    ceiling = sum(r["maximum"] * r["timeout_sec"] for r in calls) + 120
    cv.require(ceiling == 420, "question ceiling differs from reviewed 420 seconds")
    return {
        "source_lf_sha256": source_hash,
        "call_sites": CALL_SITES,
        "reachable": calls,
        "excluded": EXCLUDED,
        "maximum_calls": 3,
        "overhead_sec": 120,
        "ceiling_sec": ceiling,
    }


def compare_settings(effective: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    cv.require(reference.get("llm_provider_profile") == "local-first", "reference profile changed")
    expected = {**reference, "llm_provider_profile": "codex-only"}
    differing = [
        key for key, value in expected.items() if key not in effective or effective[key] != value
    ]
    cv.require(not differing, "effective setting differs: " + ", ".join(differing))
    return {
        "effective": {k: effective[k] for k in (*reference, *EXTRA_SETTINGS)},
        "diff": {"llm_provider_profile": {"from": "local-first", "to": "codex-only"}},
        "passed": True,
    }


def resolve_providers(path: Path, settings: dict[str, Any]) -> dict[str, Any]:
    import yaml  # type: ignore[import-untyped]

    configured = yaml.safe_load(path.read_text(encoding="utf-8"))
    profile = configured["routing_profiles"][settings["llm_provider_profile"]]
    cv.require("fallback" not in profile, "codex-only fallback refused")
    codex = [p for p in configured["providers"] if p["id"] == "codex"]
    cv.require(len(codex) == 1 and codex[0]["enabled"] is True, "Codex provider disabled")
    result = {}
    for target in ("fast", "strong", "answer"):
        value = profile[target]
        cv.require(
            value["provider"] == "codex" and value["model"] == "gpt-6-astra",
            "provider/model differs",
        )
        effort = value.get("effort", settings["codex_reasoning_effort"])
        timeout = value.get("timeout_sec", settings["codex_timeout_sec"])
        cv.require(
            effort == ("xhigh" if target == "answer" else "low")
            and type(timeout) in (int, float)
            and timeout == (180 if target == "answer" else 60),
            "provider effort/timeout differs",
        )
        if target == "answer":
            cv.require(
                "effort" not in value and "timeout_sec" not in value,
                "answer settings override differs",
            )
        result[target] = {
            "provider": value["provider"],
            "model": value["model"],
            "effort": effort,
            "timeout_sec": timeout,
            "effort_timeout_source": "settings" if target == "answer" else "providers.yml",
        }
    return result


def run_offline(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> bytes:
    # Fixed argv, no shell; trusted pinned local release only.
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=60, check=False)  # nosec B603
    cv.require(result.returncode == 0, "offline release inspection failed")
    return result.stdout


def release_files(release: dict[str, Any]) -> dict[str, Any]:
    root = cv.absolute(release["root"])
    commit = release["commit"]
    cv.require(re.fullmatch(r"[0-9a-f]{40}", commit), "full release commit required")
    git = shutil.which("git")
    cv.require(git, "git unavailable")

    def query(*args: str) -> bytes:
        return run_offline([str(git), *args], root)

    cv.require(
        query("rev-parse", "HEAD").decode().strip() == commit
        and query("rev-parse", "--abbrev-ref", "HEAD").strip() == b"HEAD",
        "release must be pinned and detached",
    )
    cv.require(
        not query("status", "--porcelain", "--untracked-files=all").strip(),
        "release checkout is dirty",
    )
    query("merge-base", "--is-ancestor", "6656251", commit)
    files = {}
    for entry in query("ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0"):
        if not entry:
            continue
        header, raw_name = entry.split(b"\t", 1)
        mode, kind, blob = header.decode().split()
        cv.require(
            mode in ("100644", "100755") and kind == "blob", "release symlink/submodule refused"
        )
        name = cv.relative(raw_name.decode("utf-8"))
        path = root / name
        cv.no_links(path)
        data = path.read_bytes()
        object_hash = hashlib.sha1(
            b"blob " + str(len(data)).encode() + b"\0" + data, usedforsecurity=False
        ).hexdigest()
        cv.require(object_hash == blob, "release bytes differ from commit")
        files[name] = cv.digest(data)
    cv.require(
        files
        and all(
            name in files
            for name in ("deploy/windows/start.py", "agent/graph.py", "config/settings.py")
        ),
        "release incomplete",
    )
    return {
        "commit": commit,
        "tree": query("rev-parse", "HEAD^{tree}").decode().strip(),
        "root_sha256": cv.digest(str(root.resolve())),
        "files": files,
    }


def settings_worker(release_root: Path, env_file: Path, fields: list[str]) -> dict[str, Any]:
    """Configuration-only worker: no get_settings (it creates dirs), provider or API."""
    sys.path.insert(0, str(release_root))
    from deploy.windows import start

    deployment = start.parse_service_env(env_file.read_bytes())
    environment = start.api_environment(deployment)
    os.environ.clear()
    os.environ.update(environment)
    from config import settings

    cv.require(
        Path(settings.__file__).resolve() == (release_root / "config/settings.py").resolve(),
        "settings import escaped release",
    )
    effective = settings.Settings()
    settings._apply_deployed_settings(effective)
    return {name: getattr(effective, name) for name in fields}


def effective_settings(
    config: dict[str, Any], key: str, reference: dict[str, Any]
) -> dict[str, Any]:
    release = config["release"]
    root = cv.absolute(release["root"])
    cv.require(not (root / ".env").exists(), "release .env refused")
    env = {
        k: os.environ[k]
        for k in ("PATH", "SystemRoot", "TEMP", "TMP", "USERPROFILE")
        if k in os.environ
    }
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    fields = list(dict.fromkeys([*reference, *EXTRA_SETTINGS]))
    output = run_offline(
        [
            str(cv.absolute(release["python"])),
            "-I",
            "-B",
            str(Path(__file__).resolve()),
            "--settings-worker",
            str(root),
            str(cv.absolute(config["stands"][key]["env"])),
            json.dumps(fields),
        ],
        root,
        env,
    )
    return cv.decode(output)


def table(values: list[dict[str, Any]], ids: list[str] | None = None) -> dict[str, Any]:
    found = {row["case_id"]: row for row in values}
    cv.require(len(found) == len(values), "duplicate case ids")
    if ids is not None:
        cv.require(set(found) == set(ids) and len(ids) == len(found), "case set differs")
    return found


def q_baseline(
    verdicts: dict[str, list[dict[str, Any]]], ids: dict[str, list[str]]
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in cv.KEYS:
        found = table(verdicts[key], ids[key])
        cv.require(
            len(ids[key]) == len(set(ids[key])) == 100,
            "Q case count differs",
        )
        flags = []
        # Historical exports sort by (run, case_id), not question dispatch order.
        # Pair by id and publish in the independently checked package input order.
        for ident in ids[key]:
            row = found[ident]
            cv.require(
                row.get("grade") in ("good", "partial_ok", "bad")
                and (
                    type(row.get("context_has_answer")) is bool
                    or (row.get("empty_answer") is True and row["grade"] == "bad")
                ),
                "invalid Q verdict",
            )
            flags.append(
                {
                    "case_id": row["case_id"],
                    "answered_good": row["grade"] == "good"
                    and row.get("context_has_answer") is True,
                }
            )
        result[key] = {
            "cases": flags,
            "answered_good": sum(r["answered_good"] for r in flags),
            "n": 100,
        }
    result["pooled"] = {"answered_good": sum(result[k]["answered_good"] for k in cv.KEYS), "n": 300}
    return result


def r_compare(
    key: str, expected: list[dict[str, Any]], reproduced: list[dict[str, Any]]
) -> dict[str, Any]:
    old, new = table(expected), table(reproduced)
    cv.require(len(old) == len(new) == 100 and set(old) == set(new), "R ids differ")
    rows = []
    for ident, previous in old.items():
        actual = new[ident]
        cv.require(type(actual.get("gold")) is bool, "invalid R gold flag")
        if actual["gold"]:
            cv.require(
                type(actual["hit"]) is int
                and actual["hit"] in (0, 1)
                and type(actual["fraction"]) in (int, float)
                and 0 <= actual["fraction"] <= 1,
                "invalid R reading",
            )
        else:
            cv.require(
                actual["hit"] is None and actual["fraction"] is None, "R no-gold reading differs"
            )
        cv.require(
            all(
                previous[name] == actual[name]
                for name in ("gold", "hit", "fraction", "prompt_sha256")
            ),
            "R casewise difference",
        )
        rows.append(
            {
                "case_id": ident,
                **{name: actual[name] for name in ("gold", "hit", "fraction", "prompt_sha256")},
                "matched": True,
            }
        )
    gold_n = sum(r["gold"] for r in rows)
    hits = sum(r["hit"] or 0 for r in rows)
    cv.require(
        (hits, gold_n) == {"wixqa": (67, 100), "conditionalqa": (58, 80)}[key],
        "R historical totals differ",
    )
    return {"passed": True, "cases": rows, "hits": hits, "n": gold_n}


def canonical_import(repo: Path, module: str, directory: str) -> Any:
    path = repo / directory
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(path))
    loaded = importlib.import_module(module)
    filename = loaded.__file__
    if filename is None:
        raise cv.Refusal("instrument has no source file")
    cv.require(
        Path(filename).resolve() == (path / (module + ".py")).resolve(),
        "instrument import escaped canonical repository",
    )
    return loaded


def load_packages(
    repo: Path, config: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    judge = canonical_import(repo, "chat_answer_judge", "scripts")
    cases_reader = canonical_import(repo, "stage2_cases", "reports/stage2/tools")
    cases_reader.AIRCARGO["aircargo"] = repo / "evaluation/curated_cases_aircargo.jsonl"
    packages, orders = {}, {}
    common = repo / "reports/stage4-final/tools/common.py"
    model = cv.constant(common, "SETTINGS")["ollama_model_name"]
    model_digest = cv.constant(common, "MODEL_DIGEST")
    for key in cv.KEYS:
        cases_file = (
            repo / "evaluation/curated_cases_aircargo.jsonl"
            if key == "aircargo"
            else cv.absolute(config["private_data_root"]) / key / "cases.jsonl"
        )
        ids = cases_reader.registered(key, cases_file)
        cv.require(len(ids) == 100 and len(set(ids)) == 100, "package selection differs")
        known = table(cv.rows(cases_file))
        old = table(cv.rows(repo / Path(cv.old_export(key)).with_suffix(".cases.jsonl")), ids)
        label = "stage5_aircargo_runs" if key == "aircargo" else "stage5_runs"
        runs = cv.absolute(config["private_inputs"][label]["root"])
        cv.require(not list(runs.rglob("._*")), "AppleDouble in package runs")
        generation = {
            name: cv.sha(cv.absolute(config["private_data_root"]) / key / name)
            for name in cv.SOURCE_FILES
        }
        gathered = []
        for batch in range(1, 11):
            folder = runs / f"final-answers-{key}-b{batch:02d}"
            launch = cv.read(folder / "launch.json")
            batch_ids = ids[(batch - 1) * 10 : batch * 10]
            cv.require(
                launch["status"] == "complete"
                and launch["cases"] == batch_ids
                and launch["code_sha"].startswith("138f3b3" if key == "aircargo" else "2057ad0")
                and launch["tenant"] == ("aircargo" if key == "aircargo" else "ext_" + key)
                and launch["model"] == model
                and launch["model_digest"] == model_digest
                and launch["cases_sha256"] == cv.sha(cases_file)
                and launch["corpus_sha256"] == generation,
                "package launch differs",
            )
            answers = judge.run_answers(folder)
            cv.require([r["case_id"] for r in answers] == batch_ids, "package parsed order differs")
            parsed = table(answers, batch_ids)
            cv.require(
                len(list((folder / "prompts").glob("*-stream.txt"))) == 10, "package prompts differ"
            )
            for ident in batch_ids:
                answer = parsed[ident]
                prompt = folder / "prompts" / cv.relative(answer["prompt_file"])
                raw = prompt.read_bytes()
                cv.require(
                    b"\r" not in raw
                    and cv.digest(raw) == answer["prompt_sha256"] == old[ident]["prompt_sha256"]
                    and answer["prompt_id"] == "QA_PROMPT_V4"
                    and answer["question"] == known[ident]["query"],
                    "package prompt/question differs",
                )
                gathered.append(answer)
        cv.require(len({r["question"] for r in gathered}) == 100, "duplicate package questions")
        packages[key], orders[key] = gathered, ids
    return packages, orders


def r_gate(repo: Path, config: dict[str, Any], packages: dict[str, Any]) -> dict[str, Any]:
    sent_gold = canonical_import(repo, "sent_gold", "reports/stage4-final/tools/external")
    historical = cv.read(repo / STAGE5)
    result = {}
    for key in cv.KEYS[:2]:
        reader = sent_gold.SentGold(key, cv.absolute(config["private_data_root"]))
        values = [
            {
                "case_id": r["case_id"],
                "prompt_sha256": r["prompt_sha256"],
                **reader.saved_point(reader.cases[r["case_id"]], r["documents"]),
            }
            for r in packages[key]
        ]
        result[key] = r_compare(key, historical["corpora"][key]["sent_cases"], values)
        result[key]["record_sha256"] = cv.sha(repo / STAGE5)
        result[key]["saved_prompts_sha256"] = cv.digest(
            cv.encoded([{k: r[k] for k in ("case_id", "prompt_sha256")} for r in packages[key]])
        )
    return {"passed": True, "keys": result, "pooled": {"hits": 125, "n": 180}}


def bind_attempt02(repo: Path, config: dict[str, Any], packages: dict[str, Any]) -> dict[str, Any]:
    verdicts = {}
    inputs = config["private_inputs"]
    runs_root = cv.absolute(inputs["attempt02_runs"]["root"])
    journals = cv.absolute(inputs["attempt02_journals"]["root"])
    for key in cv.KEYS:
        receipt = cv.read(repo / ATTEMPT / f"plans-{key}.json")
        export = cv.read(repo / ATTEMPT / f"ceiling-{key}-judge-m1.json")
        cv.require(
            receipt["key"] == export["base"] == key and export["status"] == "counted",
            "attempt-02 export refused",
        )
        run_files = {r["path"]: r["sha256"] for r in cv.tree_files(runs_root / key / "runs")}
        cv.require(run_files == receipt["answer_files"], "attempt-02 source runs differ")
        for metric, expected in receipt["plans"].items():
            cv.require(
                metric in ("m1", "m2", "bridge")
                and cv.sha(journals / key / metric / "plan.json") == expected,
                "attempt-02 plan differs",
            )
        cv.require({"m1", "bridge"} <= set(receipt["plans"]), "attempt-02 plans missing")
        cv.require(
            cv.sha(journals / key / "m1/plan.json") == export["provenance"]["plan_sha256"]
            and cv.sha(journals / key / "m1/verdicts.jsonl")
            == export["provenance"]["verdicts_sha256"],
            "attempt-02 judge journal differs",
        )
        seed = receipt["bridge_seed"]
        with (journals / key / "bridge/verdicts.jsonl").open("rb") as stream:
            prefix = stream.read(seed["bytes"])
        cv.require(
            len(prefix) == seed["bytes"] and cv.digest(prefix) == seed["sha256"],
            "attempt-02 bridge seed differs",
        )
        values = cv.rows(repo / ATTEMPT / f"ceiling-{key}-judge-m1.cases.jsonl")
        found = table(values, [r["case_id"] for r in packages[key]])
        for package in packages[key]:
            cv.require(
                found[package["case_id"]]["prompt_sha256"] == package["prompt_sha256"],
                "attempt-02 package prompt differs",
            )
        verdicts[key] = values
    return verdicts


def public_hashes(repo: Path) -> tuple[dict[str, str], list[str]]:
    pins = cv.historical_pins(repo)
    paths = set(PUBLIC_FILES) | set(pins)
    for key in cv.KEYS:
        paths.update(
            (
                f"{ATTEMPT}/plans-{key}.json",
                f"{ATTEMPT}/ceiling-{key}-judge-m1.json",
                f"{ATTEMPT}/ceiling-{key}-judge-m1.cases.jsonl",
            )
        )
    for folder in ("reports/codex-only-quality/tools", "reports/generator-ceiling/tools"):
        paths.update(
            p.relative_to(repo).as_posix()
            for p in (repo / folder).rglob("*")
            if p.is_file() and p.suffix in (".py", ".cs", ".txt")
        )
    # Bind every repository dependency actually imported by the offline readers.
    for module in list(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename:
            path = Path(filename).resolve()
            if path.is_relative_to(repo.resolve()) and path.suffix == ".py":
                paths.add(path.relative_to(repo.resolve()).as_posix())
    hashes, pending = {}, []
    for name in sorted(paths):
        path = repo / cv.relative(name)
        if not path.exists():
            pending.append(name)
            continue
        cv.no_links(path)
        value = cv.sha(path)
        cv.require(
            name not in pins or value == pins[name], "historical SHA-256 pin differs: " + name
        )
        hashes[name] = value
    return hashes, pending


def private_artifacts(config: dict[str, Any], repo: Path) -> dict[str, Any]:
    cv.require(
        set(ARTIFACTS) <= set(config["artifacts"])
        and {"environment", "assets"} <= set(config["private_inputs"]),
        "runtime evidence missing",
    )
    result = {}
    for name in ARTIFACTS:
        path = cv.absolute(config["artifacts"][name])
        cv.no_links(path)
        result[name] = {"path_sha256": cv.digest(str(path.resolve())), "sha256": cv.sha(path)}
    for label in ("helper_verification", "unchanged_defaults"):
        receipt = cv.read(cv.absolute(config["artifacts"][label]))
        cv.require(
            receipt.get("passed") is True
            and all(receipt["files"].get(name) == cv.sha(repo / name) for name in HELPER_FILES),
            "deployment helper verification refused",
        )
    build = cv.read(cv.absolute(config["artifacts"]["shim_build"]))
    cv.require(
        build["source_sha256"]
        == cv.sha(repo / "reports/codex-only-quality/tools/shim/CaptureShim.cs")
        and build["exe_sha256"] == result["shim_executable"]["sha256"],
        "shim build receipt differs",
    )
    shim = cv.absolute(config["artifacts"]["shim_executable"])
    shim_config = cv.absolute(config["artifacts"]["shim_config"])
    configured = cv.read(shim_config)
    cv.require(
        shim_config.resolve() == (shim.parent / "capture_shim.json").resolve()
        and cv.absolute(configured["real_exe"]).resolve()
        == cv.absolute(config["artifacts"]["codex_executable"]).resolve()
        and shim.resolve() != cv.absolute(configured["real_exe"]).resolve(),
        "shim configuration differs",
    )
    capture = cv.absolute(configured["capture_root"])
    cv.require(not capture.resolve().is_relative_to(repo.resolve()), "capture root is public")
    for cli in ("codex", "claude"):
        version = cv.read(cv.absolute(config["artifacts"][cli + "_version"]))
        cv.require(
            isinstance(version["version"], str)
            and bool(version["version"].strip())
            and version["executable_sha256"] == result[cli + "_executable"]["sha256"],
            "CLI version observation differs",
        )
        result[cli + "_version"]["version_sha256"] = cv.digest(version["version"])
    for key in cv.KEYS:
        path = cv.absolute(config["stands"][key]["env"])
        # Whole env file only; never individual credentials or their hashes.
        result["env_" + key] = {
            "path_sha256": cv.digest(str(path.resolve())),
            "sha256": cv.sha(path),
        }
    return result


def register(
    config_path: Path,
    private: Path,
    series: str,
    records: Path,
    repo: Path = ROOT,
    *,
    settings_reader: Callable[..., dict[str, Any]] = effective_settings,
) -> dict[str, Any]:
    cv.require(re.fullmatch(r"[A-Za-z0-9_-]+", series), "invalid series name")
    config_bytes = config_path.read_bytes()
    config = cv.decode(config_bytes)
    config_hash = cv.digest(config_bytes)
    target = records / series / "registration.json"
    cv.require(
        not private.resolve().is_relative_to(repo.resolve())
        and not repo.resolve().is_relative_to(private.resolve()),
        "private root overlaps repository",
    )
    cv.require(
        records.resolve().is_relative_to((repo / "reports/codex-only-quality").resolve()),
        "records must be under reports/codex-only-quality",
    )
    cv.require(not target.exists(), "registration already exists; preserve it")
    private_paths = [config_path, cv.absolute(config["copy_receipt"])]
    private_paths += [p for pair in cv.input_trees(config).values() for p in pair]
    private_paths += [cv.absolute(p) for p in config["artifacts"].values()]
    private_paths += [cv.absolute(config["stands"][k]["env"]) for k in cv.KEYS]
    cv.require(
        all(not p.resolve().is_relative_to(repo.resolve()) for p in private_paths),
        "private evidence is inside repository",
    )
    cv.admit_receipt(config_path, repo)
    hashes, pending = public_hashes(repo)
    release = release_files(config["release"])
    cv.require(
        all(release["files"].get(name) == cv.sha(repo / name) for name in HELPER_FILES[:2]),
        "pinned release lacks the verified deployment helpers",
    )
    runtime = private_artifacts(config, repo)
    release_root = cv.absolute(config["release"]["root"])
    reference = cv.constant(repo / "reports/stage4-final/tools/common.py", "SETTINGS")
    settings_results, providers_results, bounds = {}, {}, {}
    for key in cv.KEYS:
        effective = settings_reader(config, key, reference)
        settings_results[key] = compare_settings(effective, reference)
        providers_results[key] = resolve_providers(release_root / "config/providers.yml", effective)
        bounds[key] = graph_bound(
            release_root / "agent/graph.py", effective, providers_results[key]
        )
    packages, ids = load_packages(repo, config)
    baseline = q_baseline(bind_attempt02(repo, config, packages), ids)
    instrument_gate = r_gate(repo, config, packages)
    # Recheck after the readers, include their dependencies, and reject concurrent edits.
    final_hashes, pending = public_hashes(repo)
    cv.require(
        all(final_hashes.get(k) == v for k, v in hashes.items()),
        "registered file changed during registration",
    )
    cv.admit_receipt(config_path, repo)
    cv.require(
        cv.sha(config_path) == config_hash and runtime == private_artifacts(config, repo),
        "runtime evidence changed during registration",
    )
    result = {
        "schema_version": 1,
        "status": "registered-offline",
        "request_ready": False,
        "series": series,
        "config_sha256": config_hash,
        "private_root_sha256": cv.digest(str(private.resolve())),
        "copy_receipt_sha256": cv.sha(cv.absolute(config["copy_receipt"])),
        "files": final_hashes,
        "pending": pending,
        "release": release,
        "private_artifacts": runtime,
        "settings": settings_results,
        "providers": providers_results,
        "graph_bound": bounds,
        "q_baseline": baseline,
        "r_gate": instrument_gate,
    }
    cv.write(target, result)
    return result


def parser() -> argparse.ArgumentParser:
    result = cv.Parser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("register", "probe", "pilot", "run", "freeze", "grade", "export"):
        command = commands.add_parser(name)
        for option in ("config", "private", "records"):
            command.add_argument("--" + option, type=Path, required=True)
        command.add_argument("--series", required=True)
        if name in ("probe", "pilot", "run", "grade"):
            command.add_argument("--budget", type=int, default=600 if name == "grade" else 1080)
        if name in ("run", "freeze", "grade", "export"):
            command.add_argument("--key", choices=cv.KEYS, required=True)
        if name == "pilot":
            command.add_argument("--step", type=int, choices=(1, 5, 20), required=True)
        if name == "run":
            command.add_argument("--resume-infrastructure", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args_list = sys.argv[1:] if argv is None else argv
    worker = bool(args_list and args_list[0] == "--settings-worker")
    try:
        args = None if worker else parser().parse_args(args_list)
    except cv.Refusal:
        print("registration refused (invalid command arguments)", file=sys.stderr)
        return 1
    try:
        if worker:
            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                value = settings_worker(
                    Path(args_list[1]), Path(args_list[2]), json.loads(args_list[3])
                )
            print(json.dumps(value, allow_nan=False))
            return 0
        if args is None:
            raise cv.Refusal("missing registration arguments")
        if args.command != "register":
            print("not implemented in this task", file=sys.stderr)
            return 1
        register(args.config, args.private, args.series, args.records)
    except (Exception, SystemExit):
        print("registration refused (missing, changed or invalid evidence)", file=sys.stderr)
        return 1
    print("offline registration written; slow-answer threshold 180 s; question ceiling 420 s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
