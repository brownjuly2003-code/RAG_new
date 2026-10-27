"""The answer prompt V5, the judge's first step: the core of the decision.

docs/specs/answer-prompt-v5.md, «Amendment 1, 2026-10-27: the judge in two steps», registered
before V5's first grade. The core is what can adopt V5 at all: both sides' M1 plans of WixQA and
ConditionalQA and their bridges. It is read by v5_record.py's own checks and numbers, the tool
unchanged, without M2 and aircargo:

  python reports/answer-prompt-v5/tools/v5_core.py STAND_DIR [OUT] [--keys KEY,...]

--keys names the bases judged so far, by default both. Writes OUT, by default
STAND_DIR/v5-core.json: the SHA-256 of each input and of the tools; the primary and, beside it,
the same on the pairs of the same context; each base's numbers as v5_record.corpus reads them;
the plans; and the step, the first that holds:
  stop, not adopted   - harm read on M1 as v5_record.decision reads it: a base's bad share rises,
                        its good share falls while its bad share does not, its declines where
                        the gold says not answerable fall, or the pooled bad share rises;
  stop, NOT_EVIDENCE  - a plan of the core not counted;
  wait                - a base not judged yet;
  go on               - the pooled bad share falls: M2 and aircargo are graded, and
                        v5_record.py decides by the spec's table;
  stop, not adopted   - no gain.
Each stop is where the table can no longer adopt V5: its row 3 needs the pooled bad share to
fall, and what the rest adds is harm or NOT_EVIDENCE, never adoption.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v5_record as vr  # noqa: E402

v4r = vr.v4r
SPEC = "docs/specs/answer-prompt-v5.md"
AMENDMENT = "Amendment 1, 2026-10-27: the judge in two steps"
TOOLS = (*vr.TOOLS, "v5_core.py")
USAGE = "usage: v5_core.py STAND_DIR [OUT] [--keys KEY,...]"


def step(primary, corpora, keys, readable, not_counted):
    """The core's step: stop (with the table's outcome), wait, or go on."""
    harm = vr.decision(primary, None, corpora, list(keys), readable, not_counted)["harm"]
    names = [name for key in keys for name in not_counted.get(key, ())]
    waiting = [key for key in vr.BASES if key not in keys]
    if harm:
        found, outcome, reasons = "stop", "not adopted", harm
    elif names:
        found, outcome, reasons = (
            "stop",
            "NOT_EVIDENCE",
            [f"a plan not counted: {', '.join(names)}"],
        )
    elif waiting:
        found, outcome, reasons = "wait", None, [f"not judged yet: {', '.join(waiting)}"]
    elif primary["direction"] == "falls":
        found, outcome = "go on", None
        reasons = ["fewer bad answers: M2 and aircargo are graded, v5_record.py decides"]
    else:
        found, outcome, reasons = "stop", "not adopted", ["no gain"]
    return {
        "step": found,
        "decision": outcome,
        "v5_replaces_v4": False,
        "reasons": reasons,
        "harm": harm,
        "not_counted": {key: list(names) for key, names in not_counted.items()},
    }


def core(stand, keys=vr.BASES, *, v4_dir=vr.V4_DIR, root=vr.WS):
    """The core of STAND_DIR against V4's on the bases judged: V4's folder and the root the inputs
    are named from can be given (the tests' own)."""
    stand, root, v4_dir = Path(stand).resolve(), Path(root).resolve(), Path(v4_dir).resolve()
    if not keys or len(set(keys)) != len(keys) or not set(keys) <= set(vr.BASES):
        raise SystemExit(f"--keys names some of {','.join(vr.BASES)}, each once")
    keys = [key for key in vr.BASES if key in keys]
    inputs = {}

    def read(path):
        path = Path(path).resolve()
        try:
            name = path.relative_to(root).as_posix()
        except ValueError:
            raise SystemExit(f"{path}: not a record of the repository {root}") from None
        if not path.is_file():
            raise SystemExit(f"{name}: no such record")
        inputs[name] = vr.sha256(path)
        return path

    def record(path):
        return json.loads(read(path).read_text(encoding="utf-8"))

    def load(folder, name):
        rows = vr.load_jsonl(read(folder / f"{name}.cases.jsonl"))
        return name, record(folder / f"{name}.json"), rows

    tools = {name: vr.sha256(HERE / name) for name in TOOLS}
    corpora, plans, not_counted, readable, launches = {}, {}, {}, [], []
    pooled, same = ({}, {}, {}), ({}, {}, {})
    for key in keys:
        folders = {"v4": v4_dir, "v5": stand}
        loaded = {side: {"m1": load(folders[side], vr.names(key)[side]["m1"])} for side in vr.SIDES}
        vr.check_plans(key, loaded)
        bridge = load(stand, f"v5-bridge-{key}")
        vr.check_bridge(key, bridge, loaded["v4"]["m1"])
        summary = record(stand / f"v5-{key}.json")
        answers = vr.load_jsonl(read(stand / f"v5-{key}.cases.jsonl"))
        parity = vr.load_jsonl(read(stand / f"v5-{key}.check.jsonl"))
        vr.check_answers(key, summary, answers, parity, tools)
        launches += summary["launches"]
        questions = v4r.ids(f"v5-{key}", answers)
        # The judges graded the prompts replayed: V4's by the parity rows, V5's by the summary's.
        sent = {
            "v4": {row["case_id"]: row["v4_prompt_sha256"] for row in parity},
            "v5": {row["case_id"]: row["v5_prompt_sha256"] for row in answers},
        }
        for side in vr.SIDES:
            name, _, rows = loaded[side]["m1"]
            if v4r.ids(name, rows) != questions:
                raise SystemExit(f"{key}: {name} holds other questions than v5-{key}")
            if any(row["prompt_sha256"] != sent[side][row["case_id"]] for row in rows):
                raise SystemExit(f"{name}: graded other prompts than the replay's")
        by = {
            side: {"m1": {row["case_id"]: row for row in loaded[side]["m1"][2]}}
            for side in vr.SIDES
        }
        by["v5"]["answers"] = {row["case_id"]: row for row in answers}
        pairs = sorted(
            case
            for case in by["v4"]["m1"]
            if v4r.graded(by["v4"]["m1"][case]) and v4r.graded(by["v5"]["m1"][case])
        )
        families = {
            case: [f"{key}:cluster:{row['cluster']}"] for case, row in by["v4"]["m1"].items()
        }
        corpora[key], context = vr.corpus(key, pairs, by["v4"], by["v5"], families)
        counted = True
        for name, plan, _ in (bridge, loaded["v4"]["m1"], loaded["v5"]["m1"]):
            plans[name] = v4r.plan_summary(plan)
            if plan["status"] != "counted":
                not_counted.setdefault(key, []).append(name)
                counted = False
        if counted:
            readable.append(key)
        for into, cases in ((pooled, pairs), (same, context)):
            into[0].update(v4r.indicator(key, cases, by["v4"]["m1"], v4r.is_bad))
            into[1].update(v4r.indicator(key, cases, by["v5"]["m1"], v4r.is_bad))
            into[2].update({f"{key}:{case}": families[case] for case in cases})
    found = v4r.environment(
        "v5-environment.jsonl", vr.load_jsonl(read(stand / "v5-environment.jsonl")), launches
    )
    if [server["started"] for server in found["servers"]] != [vr.OLLAMA_STARTED]:
        raise SystemExit("v5-environment.jsonl: not stage 2's one Ollama server")
    primary = {"indicator": "bad", "keys": keys, **vr.pair(*pooled)}
    return {
        "spec": SPEC,
        "amendment": AMENDMENT,
        "stand": vr.STAND,
        "keys": keys,
        "tools": tools,
        "disclosure": list(vr.DISCLOSURE),
        "inputs": dict(sorted(inputs.items())),
        "environment": found,
        "primary": primary,
        "same_context": {"indicator": "bad", "keys": keys, **vr.pair(*same)},
        "corpora": corpora,
        "plans": plans,
        "step": step(primary, corpora, keys, readable, not_counted),
    }


def main(argv=None, **folders):
    argv = list(sys.argv[1:] if argv is None else argv)
    keys = vr.BASES
    if "--keys" in argv:
        at = argv.index("--keys")
        if at + 1 == len(argv):
            raise SystemExit(USAGE)
        keys = tuple(argv[at + 1].split(","))
        del argv[at : at + 2]
    if len(argv) not in (1, 2):
        raise SystemExit(USAGE)
    stand = Path(argv[0])
    out = Path(argv[1]) if len(argv) == 2 else stand / "v5-core.json"
    found = core(stand, keys, **folders)
    vr.write(out, found)
    print(out)
    print(json.dumps(found["step"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
