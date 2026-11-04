"""Offline registration and serial, durable probe/pilot/run request chunks.

Uses copy_verify's private config, plus:
  copy_receipt: absolute receipt JSON
  release: {root: absolute detached checkout, commit: full SHA, python: absolute interpreter}
  stands: {<key>: {app: absolute <private>/stands/<key>/app, env: absolute env file,
                  auth_file: absolute private JSON with admin_username/admin_password,
                  tenant: ext_wixqa|ext_conditionalqa|aircargo,
                  database: codex_quality_<series, '-' as '_'>_<key>}}
  capture_root: absolute private shim journal root (must match shim config)
  cw_home: absolute private Codex profile home (AGENTS.md hashed per chunk)
  artifacts: {<label>: absolute file} for every ARTIFACTS entry below
  private_inputs also contains environment and assets (complete inventories).
Version artifacts are saved CLI version observations; registration never executes a CLI.
Each version JSON holds {version: nonempty string, executable_sha256: SHA-256}.
Helper verification/default receipts hold {passed: true, files: {repo path: SHA-256}}
and bind both extended helpers plus their deployment tests. shim_build is the
unchanged build_shim.py JSON output, binding the C# source to the installed exe.
--records/--series/registration.json is public. Private filenames are hashed; setting
values are restricted to an explicit nonsecret whitelist. Pending later-task artifacts
are enumerated; request_ready is true exactly when pending is empty. Requests
also require committed registration/spec/files and fresh logical copy admission.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import copy
import hashlib
import importlib
import io
import json
import os
import re
import shutil

# Only fixed, offline git/Python commands; no shell.
import subprocess  # nosec B404 # Fixed local argv; never a shell.
import sys
import time
import uuid
from collections import Counter
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Direct invocation and path-based test loading both use the sibling admission code.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import copy_verify as cv  # noqa: E402
import stand_runtime as sr  # noqa: E402

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
    "reports/codex-only-quality/tools/quality_freeze.py",
    "reports/codex-only-quality/tools/capture_journal.py",
    "reports/codex-only-quality/tools/build_shim.py",
    "reports/codex-only-quality/tools/shim_check.py",
    "reports/codex-only-quality/tools/shim/CaptureShim.cs",
    "tests/test_codex_only_quality_register.py",
    "tests/test_codex_only_quality_capture.py",
    "tests/test_codex_only_quality_driver.py",
    "tests/test_codex_only_quality_freeze.py",
    "tests/test_codex_only_quality_read.py",
    "reports/codex-only-quality/tools/stand_runtime.py",
    "reports/codex-only-quality/tools/runtime_check.py",
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
CONVERSATION_SOURCE_SHA256 = "4813da8103e4080213b737ca1967fb5805926e172ddccb8798e9ffe104a825b0"
# Reviewed at the above source pins, under the registered codex-only settings.
# Neither candidate skips generate. Sparse sources + graph/graph_only provenance
# therefore cannot distinguish a missing capture from an early handover.
EARLY_HANDOVER_REVIEW = {
    "no_context": "make_grade_docs_node returns empty grades; grade_docs -> generate still runs",
    "fewer_than_two_documents": "_is_knowledge_gap is evaluated after generate, not before it",
}
# Only reviewed, positively identifiable no-answer-call paths belong here.
# The pinned release exposes none. Never infer absence from route=human alone.
EARLY_HANDOVER_PATHS: dict[str, dict[str, Any]] = {}


def review_handover_sources(release: Path) -> None:
    for name, expected in (
        ("agent/graph.py", GRAPH_SOURCE_SHA256),
        ("api/routers/conversation.py", CONVERSATION_SOURCE_SHA256),
    ):
        cv.require(
            cv.digest((release / name).read_text(encoding="utf-8")) == expected,
            "early handover source needs renewed review: " + name,
        )


def early_handover(result: dict[str, Any]) -> str | None:
    if result.get("route") != "human":
        return None
    return next(
        (
            name
            for name, fields in EARLY_HANDOVER_PATHS.items()
            if fields
            and all(field in result and result[field] == value for field, value in fields.items())
        ),
        None,
    )


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
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=60, check=False)  # nosec B603 # Fixed local Git/inspection argv; no shell.
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
        Path(filename).resolve() == (path / (module.replace(".", "/") + ".py")).resolve(),
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
    validate_runtime_config(config, private, series, repo)
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
    review_handover_sources(release_root)
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
    with stat_cache(private / series / "stat-cache.json", reuse=False):
        cv.admit_receipt(config_path, repo)
    cv.require(
        cv.sha(config_path) == config_hash and runtime == private_artifacts(config, repo),
        "runtime evidence changed during registration",
    )
    result = {
        "schema_version": 1,
        "status": "registered-offline",
        "request_ready": not pending,
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
        "stage5_references": cv.reference_files(config),
    }
    cv.write(target, result)
    return result


TERMINAL = {"accepted", "counted_out", "product_failure"}
RESULT_FIELDS = (
    "answer",
    "route",
    "sources",
    "citations",
    "session_id",
    "trace_id",
    "answer_provider",
    "answer_model",
    "quality_score",
    "answer_source",
    "generation_source",
    "events_source",
    "graph_nodes",
    "quality_source",
    "token_source",
)


def instruments(repo: Path) -> tuple[Any, Any, Any, Any]:
    directory = "reports/generator-ceiling/tools"
    common = canonical_import(repo, "ceiling_common", directory)
    route = canonical_import(repo, "ceiling_route", directory)
    answer = canonical_import(repo, "ceiling_answer", directory)
    journal = canonical_import(repo, "capture_journal", "reports/codex-only-quality/tools")
    return common, route, answer, journal


def stand_database(series: str, key: str) -> str:
    # The deployment helper accepts [a-z0-9_] only: attempt-01 -> attempt_01.
    return f"codex_quality_{series.replace('-', '_')}_{key}"


def validate_runtime_config(config: dict[str, Any], private: Path, series: str, repo: Path) -> None:
    cv.require(re.fullmatch(r"[A-Za-z0-9_-]+", series), "invalid series")
    cv.require(
        not private.resolve().is_relative_to(repo.resolve())
        and not repo.resolve().is_relative_to(private.resolve()),
        "private root overlaps repository",
    )
    cv.require(cv.absolute(config["release"]["python"]).is_file(), "release python missing")
    start = canonical_import(repo, "start", "deploy/windows")
    for field in ("capture_root", "cw_home"):
        path = cv.absolute(config[field])
        cv.no_links(path)
        cv.require(
            path.is_dir() and not path.resolve().is_relative_to(repo.resolve()),
            "private directory invalid",
        )
    cv.require((Path(config["cw_home"]) / "AGENTS.md").is_file(), "cw AGENTS missing")
    shim = cv.read(cv.absolute(config["artifacts"]["shim_config"]))
    cv.require(
        cv.absolute(shim["capture_root"]).resolve() == Path(config["capture_root"]).resolve(),
        "capture root differs",
    )
    for key in cv.KEYS:
        stand = config["stands"][key]
        app = cv.absolute(stand["app"])
        cv.require(
            app.resolve() == (private / "stands" / key / "app").resolve() and app.is_dir(),
            "stand app layout differs",
        )
        for field in ("env", "auth_file"):
            path = cv.absolute(stand[field])
            cv.no_links(path)
            cv.require(
                path.is_file() and not path.resolve().is_relative_to(repo.resolve()),
                "private file invalid",
            )
        cv.require(
            stand["tenant"] == ("aircargo" if key == "aircargo" else "ext_" + key)
            and stand["database"] == stand_database(series, key),
            "stand identity differs",
        )
        auth = cv.read(Path(stand["auth_file"]))
        cv.require(
            all(
                isinstance(auth.get(k), str) and auth[k]
                for k in ("admin_username", "admin_password")
            ),
            "private authentication invalid",
        )
        env = start.read_service_env(Path(stand["env"]))
        from urllib.parse import unquote, urlsplit

        cv.require(
            env.get("LLM_PROVIDER_PROFILE") == "codex-only"
            and env.get("ADMIN_DEFAULT_TENANT") == stand["tenant"]
            and unquote(urlsplit(env["DATABASE_URL"]).path.lstrip("/")) == stand["database"]
            and Path(env["CODEX_BINARY"]).resolve()
            == Path(config["artifacts"]["shim_executable"]).resolve()
            and Path(env["CODEX_HOME"]).resolve() == Path(config["cw_home"]).resolve(),
            "stand environment differs",
        )


def git_bytes(repo: Path, *arguments: str) -> bytes:
    git = shutil.which("git")
    cv.require(git, "git unavailable")
    return run_offline([str(git), *arguments], repo)


def committed_bytes(repo: Path, path: Path) -> bytes:
    name = path.resolve().relative_to(repo.resolve()).as_posix()
    cv.require(git_bytes(repo, "ls-files", "--error-unmatch", "--", name), "file untracked")
    git_bytes(repo, "diff", "--quiet", "HEAD", "--", name)
    committed = git_bytes(repo, "show", "HEAD:" + name)
    cv.require(committed == path.read_bytes(), "committed bytes differ")
    return committed


@contextlib.contextmanager
def stat_cache(path: Path, *, reuse: bool) -> Iterator[None]:
    """Reuse a file's hash while its size, mtime and file id are unchanged, as git's index
    does. It wraps copy_verify's sha because every inventory binds copy_verify's own bytes.
    Registration hashes in full (reuse=False) and seeds the series' cache; request chunks
    reuse it; frozen/offline work never enters. A refusal inside saves nothing."""
    rows: dict[str, list[Any]] = cv.read(path) if reuse and path.exists() else {}
    full = cv.sha

    def cached(file: Path) -> str:
        before = file.stat()
        stamp = [before.st_size, before.st_mtime_ns, before.st_ino]
        held = rows.get(str(file))
        if reuse and held is not None and held[:3] == stamp:
            return str(held[3])
        hashed = full(file)
        after = file.stat()
        if stamp == [after.st_size, after.st_mtime_ns, after.st_ino]:
            rows[str(file)] = [*stamp, hashed]
        return hashed

    cv.sha = cached  # type: ignore[assignment]  # Same signature; restored below.
    try:
        yield
    finally:
        cv.sha = full
    cv.write(path, rows)


def admit_chunk(
    args: Any, repo: Path, *, offline: bool = False
) -> tuple[dict[str, Any], dict[str, Any]]:
    cv.require(type(args.budget) is int and 1 <= args.budget <= 1080, "budget must be 1..1080")
    cv.require(re.fullmatch(r"[A-Za-z0-9_-]+", args.series), "invalid series")
    cv.require(
        args.records.resolve().is_relative_to((repo / "reports/codex-only-quality").resolve()),
        "public records outside registered repository",
    )
    path = args.records / args.series / "registration.json"
    registration = cv.decode(committed_bytes(repo, path))
    cv.require(
        registration.get("pending") == []
        and registration.get("request_ready") is True
        and registration["series"] == args.series,
        "registration not request ready",
    )
    cv.require(registration["files"] and SPEC in registration["files"], "registration lacks files")
    for name, digest in registration["files"].items():
        file = repo / cv.relative(name)
        cv.require(
            cv.sha(file) == digest and cv.digest(committed_bytes(repo, file)) == digest,
            "registered file differs",
        )
    cv.require(
        re.search(
            r"^Status: \*\*registered before the first request\*\*$",
            (repo / SPEC).read_text(encoding="utf-8"),
            re.M,
        ),
        "spec not registered",
    )
    cv.require(
        cv.sha(args.config) == registration["config_sha256"]
        and cv.digest(str(args.private.resolve())) == registration["private_root_sha256"],
        "private binding differs",
    )
    config = cv.read(args.config)
    validate_runtime_config(config, args.private, args.series, repo)
    review_handover_sources(cv.absolute(config["release"]["root"]))
    cv.require(
        cv.sha(Path(config["copy_receipt"])) == registration["copy_receipt_sha256"],
        "copy receipt changed",
    )
    data = cv.absolute(config["private_data_root"])
    # Request chunks reuse unchanged files' hashes; frozen/offline work hashes in full.
    hashes = (
        contextlib.nullcontext()
        if offline
        else stat_cache(args.private / args.series / "stat-cache.json", reuse=True)
    )
    with hashes:
        receipt = cv.admit_receipt(args.config, repo, runtime=True)
        # Every key's non-database gates still run before any Chroma client opens.
        logicals = {key: cv.logical_metadata(repo, key, data / key) for key in cv.KEYS}
    cv.require(
        registration["stage5_references"] == receipt["stage5_references"],
        "registered references differ",
    )
    for key in cv.KEYS:
        folder = data / key
        logical, chunks = logicals[key]
        if offline:
            # Frozen/offline work must never open Chroma. Immutable files are
            # still checked; only the admitted index runtime bookkeeping varies.
            expected = {k: v for k, v in receipt["logical"][key].items() if k != "collection"}
            cv.require(logical == expected, "logical copy differs")
            inventory = cv.inventory_entries(cv.read(Path(config["bases"][key]["inventory"])))

            def immutable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
                return [r for r in rows if not r["path"].startswith("index/chroma/")]

            cv.require(
                immutable(cv.tree_files(folder)) == immutable(inventory), "base input changed"
            )
        else:
            logical["collection"] = cv.check_collection(folder, chunks)
            cv.require(logical == receipt["logical"][key], "logical copy differs")
        app = cv.absolute(config["stands"][key]["app"])
        cv.require(
            git_bytes(app, "rev-parse", "HEAD").decode().strip()
            == registration["release"]["commit"]
            == config["release"]["commit"]
            and git_bytes(app, "rev-parse", "--abbrev-ref", "HEAD").strip() == b"HEAD"
            and not git_bytes(app, "status", "--porcelain", "--untracked-files=all").strip(),
            "stand release differs or is dirty",
        )
    paths = {
        k: Path(config["artifacts"][k])
        for k in ("shim_executable", "shim_config", "codex_executable")
    }
    paths.update({"env_" + k: Path(config["stands"][k]["env"]) for k in cv.KEYS})
    for label, artifact in paths.items():
        held = registration["private_artifacts"][label]
        cv.require(
            cv.sha(artifact) == held["sha256"]
            and cv.digest(str(artifact.resolve())) == held["path_sha256"],
            "private artifact differs",
        )
    return config, registration


def initial_state(registration: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "codex-quality-state/1",
        "registration_sha256": cv.digest(cv.encoded(registration)),
        "cases": {},
        "probe": False,
        "pilot_step": 0,
        "pilot_passed": False,
        "pilot_target": 0,
        "stops": [],
        "resumes": [],
        "chunks": [],
        "known_calls": [],
        "infrastructure_streak": 0,
        "pilot_seconds": 0.0,
        "remaining_seconds": 0.0,
        "retry_at": None,
    }


def add_stop(state: dict[str, Any], code: int, reason: str) -> None:
    if not any(
        s["code"] == code and s["reason"] == reason and not s.get("resolved")
        for s in state["stops"]
    ):
        state["stops"].append(
            {"id": uuid.uuid4().hex, "code": code, "reason": reason, "utc": sr.utc()}
        )


def state_gate(state: dict[str, Any], resume: bool) -> int:
    if any(s["code"] == 2 for s in state["stops"]):
        return 2
    infra = [s for s in state["stops"] if s["code"] == 5 and not s.get("resolved")]
    if infra and not resume:
        return 5
    if resume:
        for stop in infra:
            stop["resolved"] = sr.utc()
            state["resumes"].append({"utc": stop["resolved"], "stop_id": stop["id"]})
        if infra:
            state["infrastructure_streak"] = 0
    if state["retry_at"] and datetime.fromisoformat(state["retry_at"]) > datetime.now(timezone.utc):
        print("retry_at " + state["retry_at"])
        return 3
    return 0


def reduce_request(state: dict[str, Any], attempt: dict[str, Any]) -> None:
    """Idempotent reduction; unlike stage 5, no route redo or forecast refitting."""
    tag = attempt["key"] + ":" + attempt["case_id"]
    row = state["cases"].setdefault(
        tag,
        {"key": attempt["key"], "case_id": attempt["case_id"], "status": "pending", "attempts": []},
    )
    if any(a["id"] == attempt["id"] for a in row["attempts"]):
        return
    cv.require(row["status"] not in TERMINAL, "terminal case cannot be asked again")
    row["attempts"].append(attempt)
    state["known_calls"] = sorted(
        set(state["known_calls"]) | {c["folder"] for c in attempt["calls"]}
    )
    kind = attempt["classification"]
    if attempt["key"] != "probe":
        state["pilot_seconds" if attempt["pilot"] else "remaining_seconds"] += attempt["elapsed_s"]
    state["infrastructure_streak"] = (
        state["infrastructure_streak"] + 1 if kind == "infrastructure" else 0
    )
    if kind in TERMINAL:
        row["status"] = kind
        row["language"] = attempt["language"]
        if attempt["key"] == "probe" and kind == "accepted":
            state["probe"] = True
    if attempt.get("retry_at"):
        state["retry_at"] = max(state["retry_at"] or "", attempt["retry_at"])
    for stop in attempt.get("stops", []):
        add_stop(state, stop["code"], stop["reason"])
    cases = [r for r in state["cases"].values() if r["key"] in cv.KEYS]
    counted = [r for r in cases if r["status"] in {"counted_out", "product_failure"}]
    if len(counted) > 15 or any(sum(r["key"] == k for r in counted) > 5 for k in cv.KEYS):
        add_stop(state, 2, "counted_out_limit")
    if sum(r.get("language", {}).get("match") is False for r in cases) > 5:
        add_stop(state, 2, "language_limit")
    if state["infrastructure_streak"] >= 3:
        add_stop(state, 5, "three_infrastructure_attempts")


def check_pilot(state: dict[str, Any], selected: list[Any], step: int, answer: Any) -> bool:
    # The canonical gate sees terminal product failures as counted-out, and only
    # unresolved stops. Its forecast mutation is discarded: ours is fixed at 60 s.
    gate = copy.deepcopy(state)
    gate["stops"] = [s["reason"] for s in state["stops"] if not s.get("resolved")]
    for row in gate["cases"].values():
        if row["status"] == "product_failure":
            row["status"] = "counted_out"
    passed = answer.pilot_gate(gate, selected, step)
    if "pilot_failed" in gate["stops"]:
        add_stop(state, 2, "pilot_failed")
    if passed:
        state["pilot_step"] = max(state["pilot_step"], step)
        state["pilot_passed"] = state["pilot_step"] == 20
    return bool(passed)


class Chunk:
    def __init__(
        self,
        args: Any,
        repo: Path,
        config: dict[str, Any],
        registration: dict[str, Any],
        runtime: Any,
        started: float,
    ):
        self.args, self.repo, self.config, self.registration = args, repo, config, registration
        self.runtime, self.started = runtime, started
        self.folder, self.public = args.private / args.series, args.records / args.series
        self.common, self.route, self.answer, self.journal = instruments(repo)
        self.packages, self.orders = load_packages(repo, config)
        self.selected = self.answer.pilot(self.packages)
        path = self.folder / "state.json"
        self.state = cv.read(path) if path.exists() else initial_state(registration)
        cv.require(
            self.state["registration_sha256"] == cv.digest(cv.encoded(registration)),
            "state registration differs",
        )
        self.capture = Path(config["capture_root"])
        self.capture.joinpath("calls").mkdir(parents=True, exist_ok=True)
        self.drain_seconds = 60.0
        self.ceiling_override: float | None = None  # Tests only; no CLI/config override.
        self.dispatched = False

    def save(self) -> None:
        sr.atomic(self.folder / "state.json", self.state)

    def public_records(self) -> None:
        shared = {
            "stops": self.state["stops"],
            "resumes": self.state["resumes"],
            "chunks": self.state["chunks"],
            "retry_at": self.state["retry_at"],
            "pilot_seconds": self.state["pilot_seconds"],
            "remaining_seconds": self.state["remaining_seconds"],
            "forecast_s": 60,
            "slow_threshold_s": 180,
        }
        for key in (*cv.KEYS, "probe"):
            rows = [r for r in self.state["cases"].values() if r["key"] == key]
            attempts = [a for r in rows for a in r["attempts"]]
            total = 1 if key == "probe" else len(self.orders[key])
            statuses = Counter(r["status"] for r in rows)
            statuses["pending"] += total - len(rows)
            summaries = []
            for a in attempts:
                result = a["result"]
                summaries.append(
                    {
                        "id": a["id"],
                        "case_id": a["case_id"],
                        "classification": a["classification"],
                        "elapsed_s": a["elapsed_s"],
                        "cold": a["cold"],
                        "language": a["language"],
                        "calls_by_effort": dict(Counter(c["effort"] for c in a["calls"])),
                        "ticket_count": a["tickets"]["count"],
                        "session_sha256": cv.digest(str(result["session_id"]))
                        if result.get("session_id")
                        else None,
                        "ticket_sha256": [cv.digest(t["id"]) for t in a["tickets"]["rows"]],
                        "audited_absence": a.get("audited_absence", False),
                    }
                )
            value = {
                **shared,
                "key": key,
                "status_counts": dict(statuses),
                "attempts": summaries,
                "whole": statuses["pending"] == 0,
                "accepted": self.state["probe"] if key == "probe" else statuses["accepted"],
                "route_counts": dict(
                    Counter(safe_route(a["result"].get("route")) for a in attempts)
                ),
                "over_180": sum(a["elapsed_s"] > 180 for a in attempts),
                "infrastructure_attempts": sum(
                    a["classification"] == "infrastructure" for a in attempts
                ),
                "language_mismatches": sum(
                    r.get("language", {}).get("match") is False for r in rows
                ),
            }
            self.common.public_guard(value)
            self.common.write(
                self.public / ("probe.json" if key == "probe" else f"arm-{key}.json"), value
            )
        pilot = {
            **shared,
            "selected": [{"key": k, "case_id": cid} for k, cid in self.selected],
            "step": self.state["pilot_step"],
            "passed": self.state["pilot_passed"],
        }
        self.common.public_guard(pilot)
        self.common.write(self.public / "pilot.json", pilot)

    def names(self) -> set[str]:
        folders = list((self.capture / "calls").iterdir())
        if any(not p.is_dir() or p.is_symlink() for p in folders):
            raise sr.Stop(2, "invalid_call_folder")
        return {p.name for p in folders}

    def drain(self, names: set[str], *, before: set[str] | None = None) -> None:
        deadline = time.monotonic() + self.drain_seconds
        while True:
            if before is not None:
                names.update(self.names() - before)
            clean = True
            for name in names:
                call = self.journal.read_call(self.capture / "calls" / name)
                gone = self.runtime.call_gone(call)
                if gone and call.missing_end and call.start and not call.driver_end:
                    self.journal.write_driver_end(
                        call.folder, sr.utc(), "verified_process_tree_exit"
                    )
                if not gone:
                    clean = False
            if clean:
                return
            self.runtime.watch.check()
            if time.monotonic() >= deadline:
                self.runtime.stop()
                for name in names:
                    call = self.journal.read_call(self.capture / "calls" / name)
                    if (
                        call.start
                        and call.missing_end
                        and not call.driver_end
                        and self.runtime.call_gone(call)
                    ):
                        self.journal.write_driver_end(
                            call.folder, sr.utc(), "verified_exit_after_drain_timeout"
                        )
                raise sr.Stop(5, "drain_timeout")
            time.sleep(0.05)

    def before_question(self) -> set[str]:
        names = self.names()
        if names - set(self.state["known_calls"]):
            raise sr.Stop(2, "call_outside_question")
        self.drain(names)
        current = self.names()
        if current - set(self.state["known_calls"]):
            raise sr.Stop(2, "call_outside_question")
        return current

    def inspect(
        self, launch: dict[str, Any], response: dict[str, Any], names: set[str]
    ) -> dict[str, Any]:
        key = launch["key"]
        probe = key == "probe"
        records = [self.journal.read_call(self.capture / "calls" / name) for name in sorted(names)]
        reasons = self.journal.bind_calls(records, launch)
        bounds: Counter[str] = Counter()
        actual_key = cv.KEYS[0] if probe else key
        providers = self.registration["providers"][actual_key]
        for item in self.registration["graph_bound"][actual_key]["reachable"]:
            bounds[providers[item["target"]]["effort"]] += item["maximum"]
        if probe:
            bounds = Counter({"xhigh": 1})
        calls, answer_calls = [], []
        for call in records:
            try:
                active = (
                    cv.decode(call.start["active_case"].encode())
                    if call.start and isinstance(call.start.get("active_case"), str)
                    else {}
                )
                if not isinstance(active, dict):
                    active = {}
            except (ValueError, UnicodeError):
                active = {}
            if any(active.get(field) != launch[field] for field in ("attempt_id", "series")):
                reasons.append("attempt_binding")
            targets = ["answer"] if call.effort == "xhigh" else ["fast", "strong"]
            matched = [
                providers[target]
                for target in targets
                if providers[target]["model"] == call.model
                and providers[target]["effort"] == call.effort
            ]
            if not matched or call.effort not in bounds:
                reasons.append("wrong_profile_effort")
            if call.effort == "xhigh":
                if not probe and call.kind != "answer":
                    reasons.append("answer_not_v4")
                elif (
                    not probe
                    and self.journal.read_answer_prompt(call.prompt)[0] != launch["question"]
                ):
                    reasons.append("answer_question_differs")
                if probe and call.prompt != "Reply with exactly OK.":
                    reasons.append("probe_prompt")
                answer_calls.append(call)
            elif call.prompt:
                try:
                    self.journal.read_answer_prompt(call.prompt)
                except (ValueError, IndexError):
                    pass  # Auxiliary prompts normally have no V4 frame.
                else:
                    reasons.append("answer_wrong_effort")
            # Low captures have no target label; accept registered fast/strong.
            # If both match, use the larger timeout (conservative timeout proof).
            timeout = (
                max(p["timeout_sec"] for p in matched)
                if matched
                else providers["answer"]["timeout_sec"]
            )
            calls.append(
                {
                    "folder": call.folder.name,
                    "model": call.model,
                    "effort": call.effort or "invalid",
                    "classification": self.journal.classify_call(call, timeout),
                    "stdin_sha256": cv.sha(call.folder / "stdin.bin")
                    if (call.folder / "stdin.bin").exists()
                    else None,
                    "stdout_sha256": cv.sha(call.folder / "stdout.bin")
                    if (call.folder / "stdout.bin").exists()
                    else None,
                    "missing_end": call.missing_end,
                }
            )
        counts = Counter(c["effort"] for c in calls)
        if any(count > bounds[effort] for effort, count in counts.items()):
            reasons.append("call_bound")
        result = response.get("result") or {}
        if not isinstance(result, dict):
            result = {}
            response["error"] = "invalid_result"
        answer_text = result.get("text" if probe else "answer", "")
        classes = {c["classification"] for c in calls}
        fixed_failure = cv.constant(
            Path(self.config["release"]["root"]) / "agent/graph.py",
            "_GENERATION_PROVIDER_FAILURE_ANSWER",
        )
        outage = not probe and answer_text == fixed_failure
        handover = (
            early_handover(result) if not probe and not outage and not classes - {"ok"} else None
        )
        if not probe:
            for source in result.get("sources") or []:
                if isinstance(source, dict):
                    metadata = source.get("metadata")
                    for explicit in (source, metadata if isinstance(metadata, dict) else {}):
                        if (
                            "tenant_id" in explicit
                            and explicit["tenant_id"] != self.config["stands"][key]["tenant"]
                        ):
                            reasons.append("source_tenant_differs")
        # A complete, exit-0 capture rejected solely by the provider's acceptance
        # gate is counted-out only when the API displayed its fixed failure text.
        refusals = {"codex_tool_use", "codex_empty"}
        acceptance_refusal = bool(
            outage
            and len(answer_calls) == 1
            and answer_calls[0].output.reason in refusals
            and not answer_calls[0].errors
            and answer_calls[0].end
            and answer_calls[0].end.get("exit_code") == 0
            and answer_calls[0].end.get("capture_ok") is True
            and all(
                c is answer_calls[0] or calls[i]["classification"] == "ok"
                for i, c in enumerate(records)
            )
        )
        kind = "accepted"
        probe_infrastructure = probe and (
            not records or classes != {"ok"} or bool(response.get("error")) or not result
        )
        if probe_infrastructure:
            kind = "infrastructure"
        elif reasons:
            kind = "rule_stop"
        elif "usage_limit" in classes:
            kind = "infrastructure"
        elif "product_timeout" in classes:
            # The product shows its fixed failure text after its own timeout too:
            # terminal per the spec; retry_at below still covers its outage cache.
            kind = "product_failure"
        elif outage and not acceptance_refusal:
            kind = "infrastructure"
        elif (
            classes - {"ok"}
            and not acceptance_refusal
            or response.get("error")
            or not response.get("result")
            or not probe
            and response.get("http_status") != 200
        ):
            kind = "infrastructure"
        elif probe:
            if (
                not isinstance(answer_text, str)
                or answer_text not in {"OK", "OK."}
                or len(records) != 1
                or len(answer_calls) != 1
                or result.get("provider") != "codex"
                or result.get("model") != providers["answer"]["model"]
            ):
                kind = "rule_stop"
                reasons.append("probe_rejected")
        elif not answer_calls and not handover:
            kind = "infrastructure"
        elif not isinstance(answer_text, str) or not answer_text.strip() or acceptance_refusal:
            kind = "counted_out"
        language = (
            self.route.language(launch["question"], answer_text)
            if kind == "accepted" and not probe
            else {}
        )
        attempt = {
            **{k: v for k, v in launch.items() if k not in {"question", "before"}},
            "dispatch_utc": response.get("dispatch_utc", launch["dispatch_utc"]),
            "elapsed_s": response["elapsed_s"],
            "result_utc": response["result_utc"],
            "transport_error": response.get("error"),
            "clock_basis": response.get("clock_basis", "measured"),
            "http_status": response.get("http_status"),
            "result": result if probe else {f: result.get(f) for f in RESULT_FIELDS},
            "calls": calls,
            "answer_prompt_sha256": cv.digest(answer_calls[0].prompt)
            if answer_calls and answer_calls[0].prompt
            else None,
            "classification": kind,
            "language": language,
            "tickets": {"count": 0, "rows": []},
            "audited_absence": not probe and kind == "accepted" and not answer_calls,
            "early_handover": handover if not answer_calls and kind == "accepted" else None,
            "stops": [{"code": 2, "reason": "capture_binding_or_profile"}]
            if reasons and not probe_infrastructure
            else [],
            "capture_reasons": reasons,
        }
        if "usage_limit" in classes or outage:
            attempt["retry_at"] = (
                datetime.fromisoformat(response["result_utc"]) + timedelta(seconds=300)
            ).isoformat()
        if response.get("immediate"):
            attempt["classification"] = "infrastructure"
            attempt["stops"].append({"code": 5, "reason": response["error"]})
        if response.get("stop_code") == 2:
            attempt["classification"] = "rule_stop"
            attempt["stops"].append({"code": 2, "reason": response["error"]})
        return attempt

    def finish(self, launch: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
        names = self.names() - set(launch["before"])
        failure: sr.Stop | None = None
        try:
            self.drain(names, before=set(launch["before"]))
        except sr.Stop as error:
            failure = error
        attempt = self.inspect(launch, response, names)
        if failure:
            attempt["classification"] = "infrastructure" if failure.code == 5 else "rule_stop"
            attempt["stops"].append({"code": failure.code, "reason": failure.reason})
        if launch["key"] != "probe":
            try:
                attempt["tickets"] = self.runtime.tickets(
                    launch["key"], attempt["result"].get("session_id")
                )
            except Exception:
                attempt["classification"] = "infrastructure"
                attempt["stops"].append({"code": 5, "reason": "ticket_audit_failed"})
        if launch["key"] == "probe" and attempt["classification"] != "accepted":
            attempt["stops"].append(
                {
                    "code": 5 if attempt["classification"] == "infrastructure" else 2,
                    "reason": "probe_not_accepted",
                }
            )
        sr.atomic(self.folder / "attempts" / launch["id"] / "outcome.json", attempt)
        reduce_request(self.state, attempt)
        self.save()
        (self.capture / "active_case.json").unlink(missing_ok=True)
        return attempt

    def recover(self) -> None:
        known = {a["id"] for r in self.state["cases"].values() for a in r["attempts"]}
        for path in sorted((self.folder / "attempts").glob("*/launch.json")):
            launch = cv.read(path)
            if launch["id"] in known:
                continue
            cv.require(
                launch["series"] == self.args.series and launch["id"] == path.parent.name,
                "recovery binding differs",
            )
            outcome = path.parent / "outcome.json"
            if outcome.exists():
                reduce_request(self.state, cv.read(outcome))
                self.save()
            else:
                self.runtime.stop()
                response_path = path.parent / "response.json"
                response = (
                    cv.read(response_path)
                    if response_path.exists()
                    else {
                        "result": None,
                        "error": "interrupted_attempt",
                        "immediate": True,
                        "result_utc": sr.utc(),
                        "clock_basis": "dispatch_to_recovery_stop",
                        "elapsed_s": max(
                            0.0,
                            (
                                datetime.now(timezone.utc)
                                - datetime.fromisoformat(launch["dispatch_utc"])
                            ).total_seconds(),
                        ),
                    }
                )
                self.finish(launch, response)
        active = self.capture / "active_case.json"
        if active.exists():
            held = cv.read(active)
            if held.get("attempt_id") in {
                a["id"] for r in self.state["cases"].values() for a in r["attempts"]
            }:
                active.unlink()
            else:
                raise sr.Stop(2, "orphan_active_case")

    def admit_question(self, key: str, pilot: bool) -> float:
        actual = cv.KEYS[0] if key == "probe" else key
        ceiling = float(self.registration["graph_bound"][actual]["ceiling_sec"])
        if key != "probe" and self.state[
            "pilot_seconds" if pilot else "remaining_seconds"
        ] + ceiling > (3600 if pilot else 50400):
            raise sr.Stop(2, "request_clock_limit")
        if time.monotonic() - self.started + ceiling + 60 > self.args.budget:
            raise sr.Stop(3, "invocation_budget")
        return self.ceiling_override if self.ceiling_override is not None else ceiling

    def one(self, key: str, case: dict[str, Any], pilot: bool) -> None:
        if self.state["cases"].get(key + ":" + case["case_id"], {}).get("status") in TERMINAL:
            return
        ceiling = self.admit_question(key, pilot)
        cold = False
        if key != "probe":
            cold = self.runtime.ensure(key)
            self.runtime.login(key)
            ceiling = self.admit_question(key, pilot)  # Startup and login consume the chunk budget.
        elif self.runtime.stand:
            self.runtime.stop()
        before = self.before_question()
        ident = uuid.uuid4().hex
        active = {
            "key": key,
            "case_id": case["case_id"],
            "attempt_id": ident,
            "series": self.args.series,
        }
        launch = {
            **active,
            "id": ident,
            "question": case["question"],
            "pilot": pilot,
            "cold": cold,
            "before": sorted(before),
            "dispatch_utc": sr.utc(),
            "ceiling_s": ceiling,
        }
        target = self.folder / "attempts" / ident
        sr.atomic(target / "launch.json", launch)
        sr.atomic(self.capture / "active_case.json", active)
        started = time.monotonic()
        self.dispatched = True
        try:
            response = (
                self.runtime.probe(cv.KEYS[0], target / "probe-output.json", ceiling)
                if key == "probe"
                else self.runtime.ask(case["question"], target / "stream.sse", ceiling)
            )
        except sr.Stop as error:
            self.runtime.stop()
            response = {
                "result": None,
                "error": error.reason,
                "immediate": error.code == 5,
                "stop_code": error.code,
                "dispatch_utc": launch["dispatch_utc"],
                "result_utc": sr.utc(),
                "elapsed_s": time.monotonic() - started,
            }
            add_stop(self.state, error.code if error.code != 1 else 5, error.reason)
        except Exception:
            response = {
                "result": None,
                "error": "request_transport",
                "dispatch_utc": launch["dispatch_utc"],
                "result_utc": sr.utc(),
                "elapsed_s": time.monotonic() - started,
            }
        sr.atomic(target / "response.json", response)
        attempt = self.finish(launch, response)
        print(
            f"{key} {case['case_id']} {attempt['elapsed_s']:.3f}s {safe_route(attempt['result'].get('route'))} {attempt['classification']}"
        )
        if pilot and attempt["classification"] in TERMINAL:
            # Do not turn a recoverable infrastructure stop into a pilot rule stop.
            check_pilot(self.state, self.selected, self.state["pilot_target"], self.answer)
        self.save()
        code = state_gate(self.state, False)
        if code:
            raise sr.Stop(code, "state_stop" if code != 3 else "backoff")

    def work(self) -> int:
        command = self.args.command
        if command == "probe":
            if self.state["probe"]:
                print("probe already accepted")
                return 0
            self.one("probe", {"case_id": "probe", "question": "Reply with exactly OK."}, False)
            return 0
        cv.require(self.state["probe"], "accepted probe required")
        if command == "pilot":
            step = self.args.step
            cv.require(
                self.state["pilot_step"] >= {1: 0, 5: 1, 20: 5}[step], "earlier pilot gate required"
            )
            self.state["pilot_target"] = max(step, self.state["pilot_target"])
            self.save()
            work = self.selected[:step]
        else:
            if not self.state["pilot_passed"]:
                cv.require(
                    self.args.resume_infrastructure and self.state["pilot_target"] > 0,
                    "all twenty pilot cases must pass",
                )
                work = [
                    (k, cid)
                    for k, cid in self.selected[: self.state["pilot_target"]]
                    if k == self.args.key
                ]
            else:
                work = [(self.args.key, cid) for cid in self.orders[self.args.key]]
        for key, cid in work:
            self.one(key, table(self.packages[key])[cid], (key, cid) in self.selected)
        if command == "pilot" or not self.state["pilot_passed"]:
            # Call the canonical gate only absent an unresolved infrastructure stop.
            passed = check_pilot(self.state, self.selected, self.state["pilot_target"], self.answer)
            self.save()
            if not passed:
                code = 2 if any(s["code"] == 2 for s in self.state["stops"]) else 5
                raise sr.Stop(code, "pilot_pending" if code == 5 else "pilot_failed")
            if command == "run" and self.state["pilot_passed"]:
                for cid in self.orders[self.args.key]:
                    self.one(self.args.key, table(self.packages[self.args.key])[cid], False)
        pending = sum(
            self.state["cases"].get(k + ":" + cid, {}).get("status") not in TERMINAL
            for k, cid in work
        )
        if pending:
            print(f"pending {pending}")
            raise sr.Stop(5, "pending_infrastructure_cases")
        return 0


def safe_route(value: Any) -> str:
    return value if isinstance(value, str) and value in {"auto", "human"} else "other"


def request_chunk(
    args: Any, *, repo: Path = ROOT, runtime_factory: Callable[..., Any] | None = None
) -> int:
    started = time.monotonic()
    chunk: Chunk | None = None
    code, begun = 1, False
    try:
        # Budget and all path/evidence checks precede construction of a runtime.
        cv.require(type(args.budget) is int and 1 <= args.budget <= 1080, "budget must be 1..1080")
        cv.require(re.fullmatch(r"[A-Za-z0-9_-]+", args.series), "invalid series")
        cv.require(
            args.private.is_absolute()
            and not args.private.resolve().is_relative_to(repo.resolve())
            and not repo.resolve().is_relative_to(args.private.resolve()),
            "private root overlaps repository",
        )
        common, _, _, _ = instruments(repo)
        with common.serial_lock(args.private / args.series):
            config, registration = admit_chunk(args, repo)
            if runtime_factory is None:
                support = canonical_import(repo, "_support", "deploy/windows")
                runtime = sr.Runtime(
                    config, args.private / args.series, sr.WindowsSystem(support.detach)
                )
            else:
                runtime = runtime_factory(config, args.private / args.series)
            chunk = Chunk(args, repo, config, registration, runtime, started)
            try:
                agents = cv.sha(Path(config["cw_home"]) / "AGENTS.md")
                previous = (
                    chunk.state["chunks"][-1]["agents_sha256"] if chunk.state["chunks"] else None
                )
                observation: dict[str, Any] = {
                    "utc": sr.utc(),
                    "agents_sha256": agents,
                    "changed": previous is not None and agents != previous,
                    "ollama_observations": 0,
                    "sleep_suspend_events": [],
                }
                chunk.state["chunks"].append(observation)
                code = state_gate(chunk.state, getattr(args, "resume_infrastructure", False))
                chunk.save()
                if code:
                    return code
                runtime.preflight()
                begun = True
                runtime.begin()
                chunk.recover()
                code = state_gate(chunk.state, False)
                if not code:
                    code = chunk.work()
            except sr.Stop as error:
                code = error.code
                if code == 1:
                    observation["refusal_reason"] = error.reason
                if code in {2, 5}:
                    add_stop(chunk.state, code, error.reason)
            except (Exception, SystemExit):
                # Code 1 is exclusively a pre-request refusal, including mode gates.
                code = 5 if chunk.dispatched else 1
                if code == 5:
                    add_stop(chunk.state, 5, "chunk_runtime_failure")
            finally:
                keep_stand = code == 3 or (
                    code == 0
                    and (
                        args.command == "pilot" or args.command == "probe" and not chunk.dispatched
                    )
                )
                try:
                    if code != 1 and not keep_stand:
                        runtime.stop()
                    if begun:
                        runtime.end()
                except sr.Stop as error:
                    code = error.code
                    if code in {2, 5}:
                        add_stop(chunk.state, code, error.reason)
                        runtime.stop()
                chunk.state["chunks"][-1].update(
                    exit_code=code,
                    ollama_observations=len(runtime.watch.ollama),
                    sleep_suspend_events=runtime.watch.events,
                )
                chunk.save()
                chunk.public_records()
                for key in cv.KEYS:
                    attempts = [
                        a
                        for r in chunk.state["cases"].values()
                        if r["key"] == key
                        for a in r["attempts"]
                    ]
                    print(f"{key} over_180s={sum(a['elapsed_s'] > 180 for a in attempts)}")
                print(f"status code={code}")
        return code
    except (Exception, SystemExit):
        if chunk is not None and chunk.dispatched:
            add_stop(chunk.state, 5, "runtime_or_persistence_failure")
            with contextlib.suppress(Exception):
                chunk.runtime.stop()
                chunk.save()
                chunk.public_records()
            print("status code=5 (runtime or persistence failure)", file=sys.stderr)
            return 5
        print("request refused (missing, changed or invalid admission evidence)", file=sys.stderr)
        return 1


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
        if name in {"probe", "run"}:
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
        if args.command in {"probe", "pilot", "run"}:
            return request_chunk(args)
        if args.command != "register":
            import quality_freeze

            return quality_freeze.execute(args, ROOT)
        register(args.config, args.private, args.series, args.records)
    except (Exception, SystemExit):
        print("registration refused (missing, changed or invalid evidence)", file=sys.stderr)
        return 1
    print("offline registration written; slow-answer threshold 180 s; question ceiling 420 s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
