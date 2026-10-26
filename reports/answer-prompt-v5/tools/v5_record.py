"""The answer prompt V5 against V4, question by question, on V4's contexts: the record.

docs/specs/answer-prompt-v5.md, «How it is read», registered with these tools before V5's first
answer. Reads committed records only:

  reports/answer-prompt-v4/4f48fed/   V4's judge: v4-aircargo-judge, v4-<base>-judge-m1
                                      (references withheld), v4-<base>-judge-m2
  STAND_DIR                           V5's judge: v5-aircargo-judge, v5-<base>-judge-m1, -m2;
                                      the bridges v5-bridge-<key>, V4's retested M1 requests
                                      graded again in V5's window; V5's answers v5-<key>
                                      (replay.py summary) and their parity v5-<key>.check.jsonl
                                      (replay.py check); the stand's v5-environment.jsonl

  python reports/answer-prompt-v5/tools/v5_record.py STAND_DIR [OUT] [--keys KEY,...]

--keys names the keys V5 answered whole, by default all three. Writes OUT, by default
STAND_DIR/v5-record.json: the SHA-256 of each input and of the tools; on the pairs of a key - the
questions both sides' M1 graded, the others listed - paired differences of a yes or no, V5 minus
V4, read as V4's record read them (v4_record.paired: Newcombe's interval and the cluster
bootstrap; detected only when both exclude zero on one side):
  - primary: the bad share on WixQA and ConditionalQA pooled; beside it, the same on the pairs
    whose context V5 read unchanged;
  - per key, read by the decision: the bad and the good share, the declines of the questions
    whose gold says not answerable; pooled, M2's `agrees` among the questions with a reference;
  - per key, printed: the transitions from V4's class to V5's, the wrong declines, the moves of
    `context_has_answer`, the supported claims, the defects by kind, the answers that quote
    their context, the ones the deadline cut and the ones at the token cap, the stream's seconds
    and chunks, the same context, M2's right declines of the questions without a reference;
  - each plan's status, retest and admitting CLI; the environment; the decision of the spec's
    table, read in its order; the disclosure.
"""

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(WS / "reports" / "answer-prompt-v4" / "tools"))
sys.path.insert(1, str(WS / "reports" / "stage2" / "tools"))
sys.path.insert(2, str(WS))
import v4_record as v4r  # noqa: E402
from stage2_common import load_jsonl, sha256, spread  # noqa: E402

STAND = "4f48fed5d8d1ed534c47f1eedb7b0fec4c124cb1"
V4_DIR = WS / "reports/answer-prompt-v4/4f48fed"
KEYS = ("wixqa", "conditionalqa", "aircargo")
BASES = ("wixqa", "conditionalqa")
SIDES = ("v4", "v5")
CLASSES = ("good", "partial_ok", "bad")
V4, V5 = "QA_PROMPT_V4", "QA_PROMPT_V5"
USAGE = "usage: v5_record.py STAND_DIR [OUT] [--keys KEY,...]"
REPLAY = ("replay.py", "qa_prompt_v5.txt", "v5_chain.sh")
TOOLS = (*REPLAY, "v5_record.py")
DEFECTS = (
    "empty",
    "citation_only",
    "wrong_language",
    "copied_context",
    "cut_off",
    "repetition",
    "other",
)
# Each key's bridge, as bridge_plan.py froze it from V4's M1 plan before V5's first answer.
BRIDGES = {
    "wixqa": "db88932ee23275e4194081ec831992f93816074f2c5b2299803e6b26bf4de37a",
    "conditionalqa": "582de3638d6b0e3652e80df9a44741c6d385242cce21c0c03cba56a4bc3da421",
    "aircargo": "f4e646b9904b2c6d419dab423155efa0bea52ae2105c416f9d1054c557e366cf",
}
# The judge V5's plans are made and exported by: scripts/chat_answer_judge.py with V5's marker,
# committed with these tools; judge_export.py stays V4's.
JUDGE_SHA256 = "cdb2be82d3341afe0b1aba4e560f56eac4e2dec9cce69d0e038a18da4f2c7788"
# Stage 2's one Ollama server: v4_record.environment reads its version and count, not its start.
OLLAMA_STARTED = "2026-09-13T16:37:06+00:00"
DISCLOSURE = (
    "V5 was written after reading V4's answers, so the comparison is on the same questions "
    "(in-sample).",
    "V5 answered on V4's saved contexts, never more of them: the record compares the prompts, "
    "not two paths; its longer template can leave a shorter context, unless the pair shows "
    "the same context.",
    "One answer a side: the 4B samples without a seed; one draw of the judge, whose frozen "
    "instructions predate V5's quoted evidence; the judge and V5's author are the session's "
    "model (D12).",
    "No self-evaluation, route, widget answer or follow-up turn was replayed: they change with "
    "V5 unmeasured.",
)


def pair(first, second, families):
    """v4_record.paired with its sides named: V4's share, V5's, the difference V5 minus V4."""
    out = v4r.paired(first, second, families)
    out["v4"], out["v5"] = out.pop("v3"), out.pop("v4")
    return out


def defects(rows):
    found = Counter(row.get("defect") for row in rows)
    return {name: found[name] for name in DEFECTS}


def agrees(row):
    return row["m2"] == "agrees"


def corpus(key, pairs, v4, v5, families):
    """One key's numbers, and its pairs of the same context. v4, v5: a side's M1 rows by case;
    V5's under "answers" the replay's summary rows too."""

    def both(test, cases=pairs):
        tags = {f"{key}:{case}": families[case] for case in cases}
        return pair(
            v4r.indicator(key, cases, v4["m1"], test),
            v4r.indicator(key, cases, v5["m1"], test),
            tags,
        )

    transitions = {name: dict.fromkeys(CLASSES, 0) for name in CLASSES}
    for case in pairs:
        transitions[v4["m1"][case]["grade"]][v5["m1"][case]["grade"]] += 1
    held = Counter(
        (v4["m1"][case].get("context_has_answer"), v5["m1"][case].get("context_has_answer"))
        for case in pairs
    )
    without = [case for case in pairs if v4["m1"][case].get("stratum") == "not_answerable"]
    answers = v5["answers"].values()
    sides = (("v4", v4), ("v5", v5))
    numbers = {
        "pairs": len(pairs),
        "unpaired": v4r.unpaired(v4["m1"], pairs),
        "bad": both(v4r.is_bad),
        "good": both(v4r.is_good),
        "transitions": transitions,
        "wrong_declines": {
            side: sum(v4r.wrong_decline(data["m1"][case]) for case in pairs) for side, data in sides
        },
        "context_has_answer": {
            "same": held[True, True] + held[False, False],
            "lost": held[True, False],
            "gained": held[False, True],
        },
        "claims_supported": {
            side: v4r.claims([data["m1"][case] for case in pairs]) for side, data in sides
        },
        "defects": {side: defects([data["m1"][case] for case in pairs]) for side, data in sides},
        "answers": len(answers),
        "same_context": sum(bool(row["same_context"]) for row in answers),
        "quoted": {side: sum(bool(row["quoted"][side]) for row in answers) for side in SIDES},
        "truncated": sum(bool(row["truncated"]) for row in answers),
        "at_token_cap": {
            side: sum(bool(row["at_token_cap"][side]) for row in answers) for side in SIDES
        },
        "stream_sec": {
            side: spread([row["stream_sec"][side] for row in answers]) for side in SIDES
        },
        "chunks": {side: spread([row["chunks"][side] for row in answers]) for side in SIDES},
    }
    if without:
        numbers["declines_without_answer"] = both(v4r.declined, without)
    return numbers, [case for case in pairs if v5["answers"][case]["same_context"]]


def m2(base, first, second, families):
    """M2 of an external base: `agrees` among the questions with a reference, paired, and the
    right declines of those without (judge_export.m2). The numbers, and the pairs `agrees` read."""
    if any(first[case]["has_reference"] != second[case]["has_reference"] for case in first):
        raise SystemExit(f"{base}: V4's and V5's m2 plans give other questions a reference")

    def both_read(case):
        return first[case].get("m2") is not None and second[case].get("m2") is not None

    held = sorted(case for case in first if first[case]["has_reference"])
    without = sorted(case for case in first if not first[case]["has_reference"])
    pairs = [case for case in held if both_read(case)]
    apart = [case for case in without if both_read(case)]
    tags = {f"{base}:{case}": families[case] for case in pairs}
    numbers = {
        "with_reference": {
            "questions": len(held),
            "pairs": len(pairs),
            "unpaired": v4r.unpaired(held, pairs),
            "agrees": pair(
                v4r.indicator(base, pairs, first, agrees),
                v4r.indicator(base, pairs, second, agrees),
                tags,
            ),
        },
        "without_reference": {
            "questions": len(without),
            "pairs": len(apart),
            "unpaired": v4r.unpaired(without, apart),
            "right": {
                "v4": sum(first[case]["m2"] == "right" for case in apart),
                "v5": sum(second[case]["m2"] == "right" for case in apart),
            },
        },
    }
    return numbers, pairs


def decision(primary, recall, corpora, keys, readable, not_counted):
    """The spec's table, read in its order; the first row that holds decides.

    corpora: key -> its numbers, for the keys V5 answered whole; readable: those whose M1 plans
    and bridge count, where a key's harm is read; recall: M2's pooled `agrees`, or None unless
    both bases' M2 plans count on both sides; not_counted: key -> its plans not counted.
      1 not adopted - harm: a key's bad share rises; its good share falls while its bad share
        does not; the declines of its questions without an answer fall; the pooled bad share
        rises, both bases readable; M2's pooled agreement with the reference falls;
      2 NOT_EVIDENCE - a plan not counted, or a key not answered whole;
      3 adopted - the pooled bad share falls;
      4 not adopted - no gain.
    V5 replaces V4 only when adopted.
    """
    harm = []
    for key in readable:
        bad, good = corpora[key]["bad"]["direction"], corpora[key]["good"]["direction"]
        if bad == "rises":
            harm.append(f"{key}: the bad share rises")
        if good == "falls" and bad != "falls":
            harm.append(f"{key}: the good share falls, the bad share does not")
        guard = corpora[key].get("declines_without_answer")
        if guard is not None and guard["direction"] == "falls":
            harm.append(f"{key}: fewer declines where the gold says not answerable")
    pooled = primary["keys"]
    if len(pooled) > 1 and set(pooled) <= set(readable) and primary["direction"] == "rises":
        harm.append("pooled: the bad share rises")
    if recall is not None and recall["direction"] == "falls":
        harm.append("pooled: M2's agreement with the reference falls")
    not_run = [key for key in KEYS if key not in keys]
    if harm:
        outcome, reasons = "not adopted", harm
    elif not_counted or not_run:
        outcome, reasons = "NOT_EVIDENCE", []
        if not_counted:
            names = [name for key in keys for name in not_counted.get(key, ())]
            reasons.append(f"a plan not counted: {', '.join(names)}")
        if not_run:
            reasons.append(f"not answered whole, no harm read: {', '.join(not_run)}")
    elif primary["direction"] == "falls":
        outcome, reasons = "adopted", ["fewer bad answers"]
    else:
        outcome, reasons = "not adopted", ["no gain"]
    return {
        "decision": outcome,
        "v5_replaces_v4": outcome == "adopted",
        "reasons": reasons,
        "harm": harm,
        "not_counted": {key: list(names) for key, names in not_counted.items()},
        "not_run": not_run,
    }


def names(key):
    """Each side's judge records of a key: side -> part -> record name."""
    if key not in BASES:
        return {side: {"m1": f"{side}-{key}-judge"} for side in SIDES}
    return {side: {part: f"{side}-{key}-judge-{part}" for part in ("m1", "m2")} for side in SIDES}


def check_plans(key, loaded):
    """Both sides' plans of a key: the right prompt; references withheld from M1 and read by M2;
    V4's salt, instructions, references and route; the answers of V4's model and tenant."""
    for side, prompt in zip(SIDES, (V4, V5), strict=True):
        for part, (name, record, _) in loaded[side].items():
            provenance = record["provenance"]
            if provenance.get("prompt_id") != prompt:
                raise SystemExit(f"{name}: its plan reads {provenance.get('prompt_id')}")
            withheld = provenance.get("references_withheld") is True
            if key in BASES and ((part == "m1") != withheld or (part == "m2") != ("m2" in record)):
                raise SystemExit(
                    f"{name}: the m1 plan withholds the references, the m2 plan reads M2"
                )
            before = loaded["v4"][part][1]["provenance"]
            for field in ("salt", "instructions_sha256", "references_sha256", "route"):
                if provenance.get(field) != before.get(field):
                    raise SystemExit(f"{name}: not V4's judge, its {field} differs")
            if side == "v5":
                registered(name, provenance, before)
            found = v4r.answered_by(provenance)
            if len(found) != 1 or found != v4r.answered_by(before):
                raise SystemExit(f"{name}: answers of another model or tenant than V4's")


def registered(name, provenance, before):
    """A plan of V5's window exported by the registered judge and by V4's export."""
    if provenance.get("adapter_sha256") != JUDGE_SHA256:
        raise SystemExit(f"{name}: read by another judge than the registered")
    if provenance.get("tool_sha256") != before.get("tool_sha256"):
        raise SystemExit(f"{name}: exported by another tool than V4's")


def check_bridge(key, bridge, v4_m1):
    """A key's bridge: the plan the spec registered, cut from V4's M1 plan, its first verdicts
    V4's own."""
    (name, record, rows), (_, before, first) = bridge, v4_m1
    provenance = record["provenance"]
    if provenance.get("plan_sha256") != BRIDGES[key]:
        raise SystemExit(f"{name}: not the bridge the spec registered")
    registered(name, provenance, before["provenance"])
    for field in ("prompt_id", "salt", "instructions_sha256", "references_sha256", "route", "runs"):
        if provenance.get(field) != before["provenance"].get(field):
            raise SystemExit(f"{name}: not V4's plan, its {field} differs")
    verdicts = {row["case_id"]: (row["item_id"], row["grade"]) for row in first}
    if not rows or any(
        verdicts.get(row["case_id"]) != (row["item_id"], row["grade"]) for row in rows
    ):
        raise SystemExit(f"{name}: its first verdicts are not V4's")


def check_answers(key, summary, rows, parity, tools):
    """V5's answers of a key: whole, at the stand, by the registered tools, after every V4 prompt
    of the same questions was rebuilt byte for byte."""
    name = f"v5-{key}"
    if not rows or not summary["whole"] or summary["answers"] != len(rows):
        raise SystemExit(f"{name}: not answered whole")
    for launch in summary["launches"]:
        if launch["code_sha"] != STAND or launch["status"] != "complete":
            raise SystemExit(f"{name}: {launch['label']} is not a whole batch of the stand {STAND}")
        if launch["prompt_id"] != V5 or launch["tools_sha256"] != {
            tool: tools[tool] for tool in REPLAY
        }:
            raise SystemExit(f"{name}: {launch['label']} ran other tools than the registered")
    if not parity or not all(row["parity"] for row in parity):
        raise SystemExit(f"{name}: a V4 prompt was not rebuilt byte for byte")
    if sorted(row["case_id"] for row in parity) != sorted(row["case_id"] for row in rows):
        raise SystemExit(f"{name}: its parity check read other questions")


def build(stand, keys=KEYS, *, v4_dir=V4_DIR, root=WS):
    """The record of STAND_DIR against V4's on the keys V5 answered whole: V4's folder and the
    root the inputs are named from can be given (the tests' own)."""
    stand, root, v4_dir = Path(stand).resolve(), Path(root).resolve(), Path(v4_dir).resolve()
    if not keys or len(set(keys)) != len(keys) or not set(keys) <= set(KEYS):
        raise SystemExit(f"--keys names some of {','.join(KEYS)}, each once")
    keys = [key for key in KEYS if key in keys]
    inputs = {}

    def read(path):
        path = Path(path).resolve()
        try:
            name = path.relative_to(root).as_posix()
        except ValueError:
            raise SystemExit(f"{path}: not a record of the repository {root}") from None
        if not path.is_file():
            raise SystemExit(f"{name}: no such record")
        inputs[name] = sha256(path)
        return path

    def record(path):
        return json.loads(read(path).read_text(encoding="utf-8"))

    def load(folder, name):
        rows = load_jsonl(read(folder / f"{name}.cases.jsonl"))
        return name, record(folder / f"{name}.json"), rows

    tools = {name: sha256(HERE / name) for name in TOOLS}
    corpora, plans, not_counted, readable, launches = {}, {}, {}, [], []
    pooled, same, recall = ({}, {}, {}), ({}, {}, {}), ({}, {}, {})
    m2_counted = True
    for key in keys:
        folders = {"v4": v4_dir, "v5": stand}
        loaded = {
            side: {part: load(folders[side], name) for part, name in parts.items()}
            for side, parts in names(key).items()
        }
        check_plans(key, loaded)
        bridge = load(stand, f"v5-bridge-{key}")
        check_bridge(key, bridge, loaded["v4"]["m1"])
        summary = record(stand / f"v5-{key}.json")
        answers = load_jsonl(read(stand / f"v5-{key}.cases.jsonl"))
        parity = load_jsonl(read(stand / f"v5-{key}.check.jsonl"))
        check_answers(key, summary, answers, parity, tools)
        launches += summary["launches"]
        questions = v4r.ids(f"v5-{key}", answers)
        # The judges graded the prompts replayed: V4's by the parity rows, V5's by the summary's.
        sent = {
            "v4": {row["case_id"]: row["v4_prompt_sha256"] for row in parity},
            "v5": {row["case_id"]: row["v5_prompt_sha256"] for row in answers},
        }
        for side in SIDES:
            for name, _, rows in loaded[side].values():
                if v4r.ids(name, rows) != questions:
                    raise SystemExit(f"{key}: {name} holds other questions than v5-{key}")
                if any(row["prompt_sha256"] != sent[side][row["case_id"]] for row in rows):
                    raise SystemExit(f"{name}: graded other prompts than the replay's")
        by = {
            side: {
                part: {row["case_id"]: row for row in rows} for part, (_, _, rows) in parts.items()
            }
            for side, parts in loaded.items()
        }
        by["v5"]["answers"] = {row["case_id"]: row for row in answers}
        pairs = sorted(
            case
            for case in by["v4"]["m1"]
            if v4r.graded(by["v4"]["m1"][case]) and v4r.graded(by["v5"]["m1"][case])
        )
        families = {
            case: [f"{key}:cluster:{row['cluster']}"] if key in BASES else [f"{key}:answer:{case}"]
            for case, row in by["v4"]["m1"].items()
        }
        corpora[key], context = corpus(key, pairs, by["v4"], by["v5"], families)
        m1_counted = bridge[1]["status"] == "counted"
        plans[bridge[0]] = v4r.plan_summary(bridge[1])
        if not m1_counted:
            not_counted.setdefault(key, []).append(bridge[0])
        for side in SIDES:
            for part, (name, plan, _) in loaded[side].items():
                plans[name] = v4r.plan_summary(plan)
                if plan["status"] != "counted":
                    not_counted.setdefault(key, []).append(name)
                    m1_counted = m1_counted and part != "m1"
                    m2_counted = m2_counted and part != "m2"
        if m1_counted:
            readable.append(key)
        if key not in BASES:
            continue
        for into, cases in ((pooled, pairs), (same, context)):
            into[0].update(v4r.indicator(key, cases, by["v4"]["m1"], v4r.is_bad))
            into[1].update(v4r.indicator(key, cases, by["v5"]["m1"], v4r.is_bad))
            into[2].update({f"{key}:{case}": families[case] for case in cases})
        corpora[key]["m2"], held = m2(key, by["v4"]["m2"], by["v5"]["m2"], families)
        recall[0].update(v4r.indicator(key, held, by["v4"]["m2"], agrees))
        recall[1].update(v4r.indicator(key, held, by["v5"]["m2"], agrees))
        recall[2].update({f"{key}:{case}": families[case] for case in held})
    found = v4r.environment(
        "v5-environment.jsonl", load_jsonl(read(stand / "v5-environment.jsonl")), launches
    )
    if [server["started"] for server in found["servers"]] != [OLLAMA_STARTED]:
        raise SystemExit("v5-environment.jsonl: not stage 2's one Ollama server")
    bases = [key for key in BASES if key in keys]
    primary = {"indicator": "bad", "keys": bases, **pair(*pooled)}
    same_context = {"indicator": "bad", "keys": bases, **pair(*same)}
    agreement = {"indicator": "agrees", "keys": bases, **pair(*recall)}
    template = (HERE / "qa_prompt_v5.txt").read_text(encoding="utf-8")
    return {
        "stand": STAND,
        "keys": keys,
        "prompts": {
            "v4": V4,
            "v5": V5,
            "v4_sha256": hashlib.sha256(v4r.V4_TEMPLATE.encode("utf-8")).hexdigest(),
            "v5_sha256": hashlib.sha256(template.encode("utf-8")).hexdigest(),
            "template_delta": len(template) - len(v4r.V4_TEMPLATE),
        },
        "tools": tools,
        "disclosure": list(DISCLOSURE),
        "inputs": dict(sorted(inputs.items())),
        "environment": found,
        "primary": primary,
        "same_context": same_context,
        "recall": agreement,
        "corpora": corpora,
        "plans": plans,
        "decision": decision(
            primary,
            agreement if bases == list(BASES) and m2_counted else None,
            corpora,
            keys,
            readable,
            not_counted,
        ),
    }


def write(out, record):
    Path(out).write_bytes((json.dumps(record, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def main(argv=None, **folders):
    argv = list(sys.argv[1:] if argv is None else argv)
    keys = KEYS
    if "--keys" in argv:
        at = argv.index("--keys")
        if at + 1 == len(argv):
            raise SystemExit(USAGE)
        keys = tuple(argv[at + 1].split(","))
        del argv[at : at + 2]
    if len(argv) not in (1, 2):
        raise SystemExit(USAGE)
    stand = Path(argv[0])
    out = Path(argv[1]) if len(argv) == 2 else stand / "v5-record.json"
    record = build(stand, keys, **folders)
    write(out, record)
    print(out)
    print(json.dumps(record["decision"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
