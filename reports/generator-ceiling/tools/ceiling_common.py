"""Shared contracts. Imports do not inspect private data or start providers."""

import argparse
import contextlib
import functools
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SPEC = ROOT / "docs/specs/generator-ceiling.md"
KEYS = ("wixqa", "conditionalqa", "aircargo")
BASES = KEYS[:2]
STANDS = dict(zip(KEYS, ("2057ad0", "2057ad0", "138f3b3"), strict=True))
PUBLIC = ROOT / "reports/generator-ceiling"
STRATA = ("answer in context", "not in context", "no gold")
EXPECTED = {"wixqa": (67, 33, 0), "conditionalqa": (58, 22, 20), "aircargo": (99, 1, 0)}
INPUT_PINS = {
    "reports/stage4-final/stage5/2057ad0/record.json": "6ae0d6e1a48b468ceb6fc5cade58bd961a41ea5e8e1c379467ce9dde354f3c1b",
    "reports/stage4-final/stage5/2057ad0/stage5-wixqa-m1.json": "4b7a0cd04ca057f442e7416c5dc8f377cc8e54a8b471e115e99741df20a629a8",
    "reports/stage4-final/stage5/2057ad0/stage5-wixqa-m1.cases.jsonl": "40888f0500e1be401bbf28ce1d3776bb06bb1ba066d5a98ea36e304336d9f71e",
    "reports/stage4-final/stage5/2057ad0/stage5-wixqa-m2.json": "b5f0611281d4a3cf486ab17d51d2bfa5c1c397f8a3119d1868cd8d4fd968028d",
    "reports/stage4-final/stage5/2057ad0/stage5-wixqa-m2.cases.jsonl": "d30f87c84d53c662cbbe18b338891df13a8d1de4358e7787448d7e5d3168ac2f",
    "reports/stage4-final/stage5/2057ad0/stage5-conditionalqa-m1.json": "2d4d19f0a98adddc55942a024161acf49ada34407fde0e511887b33f3906191a",
    "reports/stage4-final/stage5/2057ad0/stage5-conditionalqa-m1.cases.jsonl": "c51985283b4b1d4cc4a5acec55b4821d679432c0f40e3baaed4b8d28b80550d2",
    "reports/stage4-final/stage5/2057ad0/stage5-conditionalqa-m2.json": "093df6572eb6a1046b83f2fbab5216b852f00d60038127bf9a1daa787fcf2890",
    "reports/stage4-final/stage5/2057ad0/stage5-conditionalqa-m2.cases.jsonl": "c32ad3b9a1d515aba2c11dc8fa714d9d810856860cc180b9acc0adc1f31ddcd9",
    "reports/stage4-final/138f3b3/final-aircargo-m1.json": "b652921bd3a988e0bb9cc3bef4ec52f07043f543194a8c52f6694f2471628c83",
    "reports/stage4-final/138f3b3/final-aircargo-m1.cases.jsonl": "232d605eee10b65320f3a6a52a5dd3ecd3fb297d4c442b639329d1b8383e779a",
}
FROZEN = (
    "agent/prompts.py",
    "scripts/chat_answer_judge.py",
    "scripts/chat_signals.py",
    "scripts/context_judge.py",
    "scripts/p2_astra_reference.py",
    "evaluation/isolated_request.py",
    "evaluation/blinded_judge_clients.py",
    "evaluation/blinded_judge.py",
    "evaluation/external_parts.py",
    "evaluation/semantic_ruler.py",
    "reports/answer-prompt-v4/tools/bridge_plan.py",
    "reports/answer-prompt-v4/tools/v4_record.py",
    "reports/answer-prompt-v5/tools/v5_record.py",
    "reports/answer-prompt-v5/tools/v5_core.py",
    "reports/answer-prompt-v5/tools/replay.py",
    "reports/answer-prompt-v6/tools/v6_common.py",
    "reports/answer-prompt-v6/tools/v6_replay.py",
    "reports/answer-prompt-v6/tools/v6_judge.py",
    "reports/answer-prompt-v6/tools/v6_key.py",
    "reports/answer-prompt-v6/tools/v6_record.py",
    "reports/answer-prompt-v6/tools/shown_text.py",
    "reports/stage2/tools/stage2_common.py",
    "reports/stage2/tools/judge_export.py",
    "reports/stage2/tools/stage2_cases.py",
    "reports/stage4-final/tools/common.py",
    "reports/stage4-final/tools/run.py",
    "reports/stage4-final/tools/stand.py",
    "reports/stage4-final/tools/judge.py",
    "reports/stage4-final/tools/external/protocol.py",
    "tests/test_generator_ceiling.py",
)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def read(path):
    return json.loads(Path(path).read_bytes().decode("utf-8"))


def rows(path):
    return [
        json.loads(line) for line in Path(path).read_bytes().decode("utf-8").splitlines() if line
    ]


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(
        (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    )
    temporary.replace(path)


def public_guard(value):
    if isinstance(value, dict):
        for key, item in value.items():
            require(
                not (
                    key.lower() in {"question", "answer", "text", "content", "prompt", "document"}
                    and isinstance(item, str)
                ),
                "text in public record",
            )
            if key.lower() == "reference":
                require(
                    isinstance(item, str) and item in judge().REFERENCE, "non-enum public reference"
                )
            public_guard(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            public_guard(item)


def public(path, value):
    public_guard(value)
    write(path, value)


def public_rows(path, values):
    public_guard(values)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        "".join(json.dumps(v, ensure_ascii=False, allow_nan=False) + "\n" for v in values).encode(
            "utf-8"
        )
    )


def unique(values):
    result = {v["case_id"]: v for v in values}
    require(len(result) == len(values), "duplicate case ids")
    return result


@functools.lru_cache(maxsize=None)
def load(relative, name):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@functools.lru_cache(maxsize=1)
def instruments():
    # V6's own path loader sets up the frozen dependencies, without any live call.
    require(
        not os.environ.get("V6_PRODUCT_ROOT")
        or Path(os.environ["V6_PRODUCT_ROOT"]).resolve() == ROOT,
        "V6 root override refused",
    )
    sys.path.insert(0, str(ROOT / "reports/answer-prompt-v6/tools"))
    common = load("reports/answer-prompt-v6/tools/v6_common.py", "v6_common")
    found = {"common": common}
    for name in ("replay", "judge", "record", "key"):
        found[name] = load(f"reports/answer-prompt-v6/tools/v6_{name}.py", "v6_" + name)
    found["core"] = load("reports/answer-prompt-v5/tools/v5_core.py", "ceiling_v5_core")
    found["legacy"] = load("reports/stage4-final/tools/judge.py", "ceiling_legacy_judge")
    return SimpleNamespace(**found)


@functools.lru_cache(maxsize=1)
def judge():
    sys.path.insert(0, str(ROOT))
    from scripts import chat_answer_judge

    return chat_answer_judge


def committed(path):
    path = Path(path).resolve()
    relative = path.relative_to(ROOT).as_posix()
    result = subprocess.run(
        ["git", "show", "HEAD:" + relative], cwd=ROOT, capture_output=True, check=False
    )
    require(
        result.returncode == 0 and result.stdout == path.read_bytes(),
        "uncommitted or changed registered file",
    )
    return sha(path)


def tool_paths():
    return sorted(
        set(FROZEN)
        | {
            p.relative_to(ROOT).as_posix()
            for p in HERE.iterdir()
            if p.is_file() and p.suffix in (".py", ".txt")
        }
    )


def tool_hashes():
    return {name: sha(ROOT / name) for name in tool_paths()}


def registration(spec=SPEC):
    raw = Path(spec).read_bytes()
    require(b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf"), "spec must be UTF-8/LF")
    text = raw.decode("utf-8")
    require(
        re.search(r"^Status: \*\*registered before the first request\*\*$", text, re.M),
        "spec is a draft",
    )
    pins = dict(re.findall(r"^- `([^`]+)` `([0-9a-f]{64})`", text, re.M))
    for name, expected in tool_hashes().items():
        require(pins.get(name) == expected, "registration tool hash refused")
        committed(ROOT / name)
    for name, expected in INPUT_PINS.items():
        require(pins.get(name) == expected, "registration input hash missing")
    committed(spec)
    return sha(spec)


def public_inputs():
    for name, expected in INPUT_PINS.items():
        require(sha(ROOT / name) == expected, "package input hash refused")
        committed(ROOT / name)
    return dict(INPUT_PINS)


def old_path(key, metric):
    return ROOT / (
        f"reports/stage4-final/stage5/2057ad0/stage5-{key}-{metric}.json"
        if key in BASES
        else "reports/stage4-final/138f3b3/final-aircargo-m1.json"
    )


def outside(path):
    path = Path(path).resolve()
    require(
        not path.is_relative_to(ROOT) and not ROOT.is_relative_to(path),
        "private path overlaps repository",
    )
    return path


def disjoint(output, sources):
    output = Path(output).resolve()
    for source in sources:
        source = Path(source).resolve()
        require(
            not output.is_relative_to(source) and not source.is_relative_to(output),
            "output overlaps input",
        )


def output_path(path):
    path = Path(path).resolve()
    require(path.is_relative_to(PUBLIC), "public output must be under reports/generator-ceiling")
    return path


def series_path(private, series):
    require(re.fullmatch(r"[A-Za-z0-9_-]+", series), "invalid series name")
    return outside(private) / series


def judge_stops(series):
    return sorted(
        p.relative_to(series).as_posix() for p in Path(series).glob("*/*/NOT_EVIDENCE.json")
    )


def wrap(prompt):
    require(isinstance(prompt, bytes) and b"\r" not in prompt, "prompt must be LF bytes")
    prompt.decode("utf-8")
    wrapper = (HERE / "wrapper.txt").read_bytes()
    require(
        wrapper.count(b"{prompt}") == 1 and b"\r" not in wrapper and wrapper.endswith(b"\n"),
        "wrapper bytes invalid",
    )
    return wrapper.replace(b"{prompt}", prompt)


def metrics(key):
    return ("m1", "bridge", "m2") if key in BASES else ("m1", "bridge")


def plan_name(key, metric):
    return f"ceiling-bridge-{key}" if metric == "bridge" else f"ceiling-{key}-judge-{metric}"


def aircargo_cases(runs):
    require(not list(Path(runs).rglob("._*")), "AppleDouble in package runs")
    common = instruments().common
    result = []
    for n in range(1, 11):
        folder = Path(runs) / f"final-answers-aircargo-b{n:02d}"
        launch = read(folder / "launch.json")
        require(launch.get("status") == "complete", "incomplete package batch")
        require(
            str(launch.get("code_sha", "")).startswith(STANDS["aircargo"]), "package stand differs"
        )
        require(
            launch.get("model") == common.MODEL and launch.get("model_digest") == common.DIGEST,
            "package model differs",
        )
        answers = judge().run_answers(folder)
        require(
            len(answers) == 10 and [a["case_id"] for a in answers] == launch.get("cases"),
            "package order/count differs",
        )
        require(
            len(list((folder / "prompts").glob("*-stream.txt"))) == 10,
            "package stream count differs",
        )
        originals = unique(
            [dict(read(p), file=p.name) for p in sorted((folder / "cases").glob("*.json"))]
        )
        require(set(originals) == {a["case_id"] for a in answers}, "package case files differ")
        for answer in answers:
            raw = (folder / "prompts" / answer["prompt_file"]).read_bytes()
            require(
                b"\r" not in raw
                and answer["prompt_id"] == "QA_PROMPT_V4"
                and sha(folder / "prompts" / answer["prompt_file"]) == answer["prompt_sha256"],
                "package prompt bytes/frame differ",
            )
            result.append(
                {
                    **answer,
                    "saved": raw.decode("utf-8"),
                    "batch": n,
                    "file": originals[answer["case_id"]]["file"],
                }
            )
    unique(result)
    require(len({a["question"] for a in result}) == 100, "duplicate package questions")
    return result


def package_cases(s5, i6):
    public_inputs()
    result = {}
    for key in KEYS:
        runs = Path(s5 if key in BASES else i6) / "runs"
        result[key] = (
            instruments().replay.cases(runs, key) if key in BASES else aircargo_cases(runs)
        )
        old = unique(rows(old_path(key, "m1").with_suffix(".cases.jsonl")))
        require(set(old) == set(unique(result[key])) and len(old) == 100, "package ids differ")
        for case in result[key]:
            require(
                case["prompt_sha256"] == old[case["case_id"]]["prompt_sha256"],
                "package prompt hash differs from export",
            )
        for n in range(1, 11):
            require(
                len(list((runs / f"final-answers-{key}-b{n:02d}" / "prompts").glob("*-stream.txt")))
                == 10,
                "package stream count differs",
            )
    return result


def tree_hashes(root):
    root = Path(root)
    require(root.is_dir(), "private input folder missing")
    paths = sorted(p for p in root.rglob("*") if p.is_file())
    require(
        all(not p.is_symlink() and p.resolve().is_relative_to(root.resolve()) for p in paths),
        "unsafe input path",
    )
    return {p.relative_to(root).as_posix(): sha(p) for p in paths}


@contextlib.contextmanager
def serial_lock(root):
    """OS lock releases after a crash; one companion task across all series."""
    Path(root).mkdir(parents=True, exist_ok=True)
    with (Path(root) / "driver.lock").open("a+b") as handle:
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("hashes",))
    parser.parse_args()
    for path, value in tool_hashes().items():
        print(f"- `{path}` `{value}`")


if __name__ == "__main__":
    main()
