"""Frozen imports, registration pins and text-free V6 records."""

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIBRARY = HERE.parents[2]
# V6 tools are copied as a separate package; V6_PRODUCT_ROOT selects the saved stand.
ROOT = Path(os.environ.get("V6_PRODUCT_ROOT", HERE.parents[2])).resolve()
for directory in (ROOT, ROOT / "reports/stage2/tools", ROOT / "reports/stage4-final/tools"):
    sys.path.insert(0, str(directory))


def load(relative, name):
    path = ROOT / relative
    if not path.exists() and str(relative).startswith("reports/stage4-final/tools/external/"):
        path = LIBRARY / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


final = load("reports/stage4-final/tools/common.py", "common")
v5 = load("reports/answer-prompt-v5/tools/replay.py", "v6_frozen_replay")
v5_record = load("reports/answer-prompt-v5/tools/v5_record.py", "v6_frozen_record")
protocol = load("reports/stage4-final/tools/external/protocol.py", "v6_frozen_protocol")
KEYS = ("wixqa", "conditionalqa", "aircargo")
BASES = KEYS[:2]
STANDS = {"wixqa": "2057ad0", "conditionalqa": "2057ad0", "aircargo": "138f3b3"}
SOURCE_RUNS = {
    "wixqa": "/Users/julia/RAG_new_stage5/2057ad0/runs",
    "conditionalqa": "/Users/julia/RAG_new_stage5/2057ad0/runs",
    "aircargo": "/Users/julia/RAG_new_chat_138f3b3/final-answers",
}
JUDGE_SHA = "cdb2be82d3341afe0b1aba4e560f56eac4e2dec9cce69d0e038a18da4f2c7788"
SPEC = "docs/specs/answer-prompt-v6.md"
REGISTERED_VERSIONS = {"regex_version": "2026.5.9", "unidata_version": "14.0.0"}
MODEL = v5.MODEL
DIGEST = final.MODEL_DIGEST
# 100 V5-median streams + ten V4-median fallbacks + ten 120-s preloads,
# rounded up to a quarter hour. The shorter package prompt earns no speed credit.
FORECAST = dict.fromkeys(KEYS, 12600)
FROZEN = (
    "scripts/chat_answer_judge.py",
    "reports/answer-prompt-v5/tools/replay.py",
    "reports/answer-prompt-v5/tools/v5_record.py",
    "reports/answer-prompt-v4/tools/v4_record.py",
    "reports/answer-prompt-v4/tools/bridge_plan.py",
    "reports/stage2/tools/stage2_common.py",
    "reports/stage2/tools/judge_export.py",
    "reports/stage4-final/tools/common.py",
    "reports/stage4-final/tools/run.py",
    "reports/stage4-final/tools/stand.py",
    "reports/stage4-final/tools/judge.py",
    "reports/stage4-final/tools/external/protocol.py",
    "evaluation/external_parts.py",
    "evaluation/semantic_ruler.py",
)
require, read, rows, sha, write = final.require, final.read, final.rows, final.sha, final.write


def unicode_gate():
    import unicodedata

    import regex

    versions = {"regex_version": regex.__version__, "unidata_version": unicodedata.unidata_version}
    for field, expected in REGISTERED_VERSIONS.items():
        require(versions[field] == expected, field + " differs from registration")
    return versions


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tool_hashes():
    return {p.name: sha(p) for p in sorted(HERE.iterdir()) if p.is_file()}


def pins(spec_path):
    import re

    return dict(
        re.findall(r"^- `([^`]+)` `([0-9a-f]{64})`", Path(spec_path).read_text("utf-8"), re.M)
    )


def registration(spec_path):
    """Tools are copied beside an immutable registered spec, never into the saved stand."""
    text = Path(spec_path).read_text("utf-8")
    require("Status: **registered before V6's first request**" in text, "V6 is still a draft")
    held = pins(spec_path)
    require(
        set(FROZEN) | {"tests/test_answer_prompt_v6.py"} <= set(held), "registration pins missing"
    )
    for path, wanted in held.items():
        target = (
            HERE / Path(path).name
            if path.startswith("reports/answer-prompt-v6/tools/")
            else ROOT / path
        )
        if not target.exists() and path.startswith("reports/stage4-final/tools/external/"):
            target = LIBRARY / path
        if path == "tests/test_answer_prompt_v6.py":
            continue  # Checked on the registering checkout; absent from the historic stand.
        require(target.is_file() and sha(target) == wanted, "registered bytes differ: " + path)
    require(
        all(
            held.get("reports/answer-prompt-v6/tools/" + name) == value
            for name, value in tool_hashes().items()
        ),
        "unregistered V6 tool",
    )
    require(sha(ROOT / "scripts/chat_answer_judge.py") == JUDGE_SHA, "judge changed")
    return sha(spec_path)


def public(path, value, names=(), questions=()):
    from stage2_common import without_text

    without_text(value, names, questions)
    write(path, value)


def public_rows(path, values, names=(), questions=()):
    from stage2_common import without_text

    for value in values:
        without_text(value, names, questions)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(
        "".join(json.dumps(v, ensure_ascii=False) + "\n" for v in values).encode("utf-8")
    )


def unique(data):
    require(len({r["case_id"] for r in data}) == len(data), "duplicate case ids")
    return {r["case_id"]: r for r in data}


def outside(path):
    path = Path(path).resolve()
    require(
        not any(path.is_relative_to(p) or p.is_relative_to(path) for p in (ROOT, LIBRARY)),
        "private folder must be outside repository/stand/library",
    )
    return path


def plan_name(key, metric):
    return f"v6-bridge-{key}" if metric == "bridge" else f"v6-{key}-judge-{metric}"


def stand_receipt(value):
    """Only Ollama's process identity may change; retain every other receipt byte/value."""
    import copy

    held = copy.deepcopy(value)
    for server in held.get("server", {}).get("servers", []):
        server.pop("pid", None)
        server.pop("started", None)
    return held
