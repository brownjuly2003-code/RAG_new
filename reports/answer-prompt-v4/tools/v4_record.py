"""The answer prompt V4 against stage 2's V3, question by question: the comparison record.

docs/specs/answer-prompt-v4.md, «How it is read», registered with these tools before V4's
first request. Reads committed records only:

  reports/stage2/5e308fe/                    V3's judge: p1-aircargo-judge,
                                             p4-<base>-judge-m1 (references withheld), -m2
  reports/stage2/retrieval-20261021/         V3's aircargo answers: p1-aircargo
  reports/stage2/external-answers-20261023/  V3's answers of a base: p4-<base>
  STAND_DIR                                  V4's answers v4-<key>; its judge v4-aircargo-judge,
                                             v4-<base>-judge-m1, -m2; the judge's bridge
                                             v4-bridge-<key> (bridge_plan.py); both sides'
                                             marks v3-<key>.marks.jsonl, v4-<key>.marks.jsonl
                                             (answer_marks.py); the stand's environment
                                             v4-environment.jsonl (stand_env.py)

  python reports/answer-prompt-v4/tools/v4_record.py STAND_DIR [OUT] [--keys KEY,...]

STAND_DIR is reports/answer-prompt-v4/<stand7>/; --keys names the keys V4 ran whole, by
default all three. Writes OUT, by default STAND_DIR/v4-record.json: the SHA-256 of each input
and of the tools; on the pairs of a key - the questions both sides' M1 graded, the others
listed by id - paired differences of a yes or no, V4 minus V3: the table, both shares, the
difference, the cluster bootstrap of the per-question difference
(evaluation.semantic_ruler.cluster_summary over stage 2's clusters, each aircargo question its
own) and Newcombe's interval for paired shares (method 10 on Wilson limits). `read95` spans
both, and a difference falls or rises - detected - only when both exclude zero on one side:
  - primary: the bad share on WixQA and ConditionalQA pooled; printed beside it, the same on
    the pairs whose context V4 read unchanged;
  - per key, read by the decision: the bad and the good share, the declines of the questions
    whose gold says not answerable, the placeholder and the referral of every answer;
  - per key, printed: the transitions from V3's class to V4's, the wrong declines, the moves of
    `context_has_answer` and the bad answers turned good by a decline, the supported claims,
    the share routed to a person and the referrals so routed, the times, and the pairing
    (whether V4 read V3's retrieval and, with it, the same context) on every question;
  - per external base, M2, printed: `agrees` among the questions with a reference, paired, and
    the right declines of those without;
  - each plan's status, retest and admitting CLI, the bridges' among them; the environment;
    the decision of the spec's table, read in its order; the disclosure.
"""

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(WS / "reports" / "stage2" / "tools"))
sys.path.insert(1, str(WS))
from stage2_common import load_jsonl, sha256, spread  # noqa: E402

CODE = "5e308fe48cca0955c3007057a574a425f71e2a6a"
JUDGE = WS / "reports/stage2/5e308fe"
RETRIEVAL = WS / "reports/stage2/retrieval-20261021"
EXTERNAL = WS / "reports/stage2/external-answers-20261023"
KEYS = ("aircargo", "wixqa", "conditionalqa")
BASES = ("wixqa", "conditionalqa")
SIDES = ("v3", "v4")
CLASSES = ("good", "partial_ok", "bad")
V3, V4 = "QA_PROMPT_V3", "QA_PROMPT_V4"
Z = 1.96
USAGE = "usage: v4_record.py STAND_DIR [OUT] [--keys KEY,...]"
TOOLS = ("answer_marks.py", "bridge_plan.py", "raise_stand.sh", "stand_env.py", "v4_record.py")
# Each key's bridge, as bridge_plan.py froze it from stage 2's M1 plan before V4's first request.
BRIDGES = {
    "aircargo": "23e6e13eafd9ebb8aea1562c980bf1309988f9a6d850592cd7801b8f3882d1a3",
    "wixqa": "5697593e39d81ca8cf551b339b1624c0186cca16216ae03c54504fc6e6e107d5",
    "conditionalqa": "ed89a6b6a2b939041e7df23ff8b749d9e4908fc91c89864cb4dc85da9179fc93",
}
# Stage 2's environment: its first answer (p1-aircargo-b01) started at STAGE2_FIRST; the Ollama
# server that served all of stage 2 runs OLLAMA, and the stage's interpreter holds the
# distributions FREEZE names, none changed since 2026-05-30 (stand_env.py, 2026-10-24).
STAGE2_FIRST = "2026-10-19T19:07:50+00:00"
OLLAMA = "0.33.2"
FREEZE = "ed8fe1c2142b1a9ff7f1c80db891a0887860ba939131bf5cd3cbde324b161ada"
# The answers' path: what both sides' answers records hold alike; the settings compare without
# the paths of a run's own.
SAME_PATH = (
    "source_sha256",
    "cases_file_sha256",
    "tools_sha256",
    "overrides",
    "data_root",
    "model",
    "model_digest",
)
PER_RUN = ("tracing_db_path", "vectordb_chroma_dir")
# QA_PROMPT_V3 as stage 2's stand held it (git show 5e308fe:agent/prompts.py), the prompt of
# every V3 answer.
V3_TEMPLATE = """You are a support assistant.

You are given context from a knowledge base and a user's question.
Your task is to answer strictly from this context.

If the context does NOT hold enough information for a confident answer,
say honestly that the available information does not answer the question,
and suggest contacting a support specialist.
Do NOT invent facts that are not in the provided text.

--------------------
CONTEXT:
{context_block}
--------------------

QUESTION:
{question}

When you rely on a specific fact from the context, add [N] right after it,
where N is the number of the document in the context list, starting from 1.
Do not invent citation numbers. If a statement is not supported by the context,
do not add a reference.

Answer in the language of the QUESTION, even when the context is written in another language.
Write a clear, brief and accurate answer for the user:
"""
# QA_PROMPT_V4 as the spec registered it (agent/prompts.py at the stand), the prompt of every
# V4 answer; a later change of agent/prompts.py leaves this record as it was.
V4_TEMPLATE = """You are a support assistant.

You are given context from a knowledge base and a user's question.
Your task is to answer strictly from this context.

If the context answers the question only in part, or in general terms that cover
the user's case, give what the context says and briefly name what it does not cover.
Only when nothing in the context answers the question, say that the available
information does not answer it.
When the answer depends on conditions the context gives, state them
instead of a bare yes or no.
Do NOT invent facts, conditions or advice that are not in the provided text.

--------------------
CONTEXT:
{context_block}
--------------------

QUESTION:
{question}

When you rely on a specific fact from the context, put the number of its document
in square brackets right after it: [1] for the first document in the context list,
[2] for the second, and so on. Do not invent citation numbers. If a statement is not
supported by the context, do not add a reference.

Answer in the language of the QUESTION, even when the context is written in another language.
Write a clear, brief and accurate answer for the user:
"""
# A V4 prompt is this much longer than V3's on the same question and documents.
TEMPLATE_DELTA = len(V4_TEMPLATE) - len(V3_TEMPLATE)
DISCLOSURE = (
    "V4 was written after reading these V3 answers, so the comparison is on the same "
    "questions (in-sample).",
    "The longer template can fit less of the documents: a pair compares the prompt and the "
    "context it leaves together, unless the pairing shows the same context.",
    "One answer a side: the 4B samples without a seed.",
    "The widget's /api/ask answers and the follow-up turns change with V4, unmeasured.",
)


def wilson(hits, n):
    """Wilson's 95 % limits, unrounded: scripts.chat_signals.wilson's before its rounding."""
    share = hits / n
    denominator = 1 + Z * Z / n
    centre = (share + Z * Z / (2 * n)) / denominator
    half = Z * math.sqrt(share * (1 - share) / n + Z * Z / (4 * n * n)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def phi(a, b, c, d):
    """The table's correlation as method 10 takes it: 0 on a zero margin; a·d - b·c less n/2,
    not below 0, where it is positive."""
    margins = (a + b) * (c + d) * (a + c) * (b + d)
    if not margins:
        return 0.0
    cross = a * d - b * c
    if cross > 0:
        cross = max(cross - (a + b + c + d) / 2, 0)
    return cross / math.sqrt(margins)


def newcombe(a, b, c, d):
    """V4's share minus V3's with Newcombe's interval for paired shares, unrounded.

    Method 10 of Statistics in Medicine 1998, 17:2635, the first share V4's and the second
    V3's: a both yes, b V3's yes alone, c V4's yes alone, d neither.
    """
    n = a + b + c + d
    p4, p3 = (a + c) / n, (a + b) / n
    (l4, u4), (l3, u3) = wilson(a + c, n), wilson(a + b, n)
    f = phi(a, b, c, d)
    difference = p4 - p3
    low = (p4 - l4) ** 2 - 2 * f * (p4 - l4) * (u3 - p3) + (u3 - p3) ** 2
    high = (u4 - p4) ** 2 - 2 * f * (u4 - p4) * (p3 - l3) + (p3 - l3) ** 2
    return difference - math.sqrt(max(low, 0.0)), difference + math.sqrt(max(high, 0.0))


def paired(v3, v4, families):
    """A yes or no on each pair, V4 minus V3: the table, the shares, both intervals, the read.

    v3, v4: tag ("key:case_id") -> 0 or 1 on the same pairs; families: tag -> its cluster.
    """
    if set(v3) != set(v4) or any(value not in (0, 1) for value in [*v3.values(), *v4.values()]):
        raise SystemExit("a paired difference reads a yes or no on both sides of each pair")
    table = Counter((v3[tag], v4[tag]) for tag in v3)
    a, b, c, d = table[1, 1], table[1, 0], table[0, 1], table[0, 0]
    n = len(v3)
    out = {"n": n, "table": {"a": a, "b": b, "c": c, "d": d}}
    if not n:
        return {
            **out,
            **dict.fromkeys(("v3", "v4", "difference", "cluster95", "newcombe95", "read95")),
            "clusters": 0,
            "detected": False,
            "direction": "not detected",
        }
    from evaluation.semantic_ruler import cluster_summary

    summary = cluster_summary(
        {tag: v4[tag] - v3[tag] for tag in v3}, {tag: families[tag] for tag in v3}
    )
    cluster95 = [round(value, 4) for value in summary["ci95"]]
    newcombe95 = [round(value, 4) for value in newcombe(a, b, c, d)]
    read95 = [min(newcombe95[0], cluster95[0]), max(newcombe95[1], cluster95[1])]
    return {
        **out,
        "v3": round((a + b) / n, 4),
        "v4": round((a + c) / n, 4),
        "difference": round((c - b) / n, 4),
        "clusters": summary["clusters"],
        "cluster95": cluster95,
        "newcombe95": newcombe95,
        "read95": read95,
        "detected": read95[0] > 0 or read95[1] < 0,
        "direction": "falls" if read95[1] < 0 else "rises" if read95[0] > 0 else "not detected",
    }


def indicator(key, cases, rows, test):
    """tag -> 1 where test holds of the case's row, else 0."""
    return {f"{key}:{case}": int(bool(test(rows[case]))) for case in cases}


def is_bad(row):
    return row["grade"] == "bad"


def is_good(row):
    return row["grade"] == "good"


def declined(row):
    return row.get("answers_question") == "declined"


def graded(row):
    return row.get("grade") is not None and not row.get("missing")


def wrong_decline(row):
    """Declined where the judge found the answer in the documents."""
    return declined(row) and row.get("context_has_answer") is True


def claims(rows):
    supported = sum(row.get("claims_supported", 0) for row in rows)
    total = sum(row.get("claims_total", 0) for row in rows)
    return {
        "supported": supported,
        "total": total,
        "share": round(supported / total, 4) if total else None,
    }


def marks(data):
    """A side's marks; the referrals of answers routed to a person stand apart too, for the
    product's own fail-closed text names a specialist."""
    rows = data["marks"]
    return {
        "answers": len(rows),
        "placeholder": sum(bool(row["placeholder"]) for row in rows.values()),
        "referral": sum(bool(row["referral"]) for row in rows.values()),
        "referral_routed": sum(
            bool(row["referral"]) and data["answers"][case]["route"] == "human"
            for case, row in rows.items()
        ),
    }


def retrieved(row):
    """The retrieval an answer read: its reranked scores and expanded characters."""
    scores, chars = row.get("ranked_scores"), row.get("expanded_chars")
    return None if scores is None or chars is None else (scores, chars)


def prompt_chars(row):
    prompts = row.get("prompts") or []
    return prompts[0].get("chars") if prompts else None


def pairing(first, second):
    """V4 on V3's retrieval, and of those the same context - a prompt grown by the template's
    difference exactly - or a shorter fitted tail (_fit_stream_prompt cut the last document
    more), grown by less; a prompt grown by more has no cause the spec knows, and is counted.
    Returns the counts and the questions of the same context."""
    same = [
        case
        for case in sorted(first)
        if retrieved(first[case]) is not None and retrieved(first[case]) == retrieved(second[case])
    ]
    grew = {
        case: prompt_chars(second[case]) - prompt_chars(first[case])
        for case in same
        if prompt_chars(first[case]) is not None and prompt_chars(second[case]) is not None
    }
    context = sorted(case for case, growth in grew.items() if growth == TEMPLATE_DELTA)
    counts = {
        "questions": len(first),
        "same_retrieval": len(same),
        "same_context": len(context),
        "shorter_tail": sum(growth < TEMPLATE_DELTA for growth in grew.values()),
        "longer": sum(growth > TEMPLATE_DELTA for growth in grew.values()),
    }
    return counts, context


def unpaired(cases, pairs):
    left = sorted(set(cases) - set(pairs))
    return {"count": len(left), "case_ids": left}


def corpus(key, pairs, v3, v4, families):
    """One key's numbers, and the pairs of the same context. v3, v4: a side's M1 rows, answers
    and marks by case."""

    def both(part, test, cases=pairs):
        tags = {f"{key}:{case}": families[case] for case in cases}
        return paired(
            indicator(key, cases, v3[part], test), indicator(key, cases, v4[part], test), tags
        )

    transitions = {name: dict.fromkeys(CLASSES, 0) for name in CLASSES}
    for case in pairs:
        transitions[v3["m1"][case]["grade"]][v4["m1"][case]["grade"]] += 1
    held = Counter(
        (v3["m1"][case].get("context_has_answer"), v4["m1"][case].get("context_has_answer"))
        for case in pairs
    )
    without = [case for case in pairs if v3["m1"][case].get("stratum") == "not_answerable"]
    sides = (("v3", v3), ("v4", v4))
    counts, context = pairing(v3["answers"], v4["answers"])
    numbers = {
        "pairs": len(pairs),
        "unpaired": unpaired(v3["m1"], pairs),
        "bad": both("m1", is_bad),
        "good": both("m1", is_good),
        "marks": {side: marks(data) for side, data in sides},
        "referral": both("marks", lambda row: row["referral"], sorted(v3["marks"])),
        "transitions": transitions,
        "wrong_declines": {
            side: sum(wrong_decline(data["m1"][case]) for case in pairs) for side, data in sides
        },
        "context_has_answer": {
            "same": held[True, True] + held[False, False],
            "lost": held[True, False],
            "gained": held[False, True],
        },
        "bad_to_good_declining": sum(
            is_bad(v3["m1"][case]) and is_good(v4["m1"][case]) and declined(v4["m1"][case])
            for case in pairs
        ),
        "claims_supported": {
            side: claims([data["m1"][case] for case in pairs]) for side, data in sides
        },
        "human": both("answers", lambda row: row["route"] == "human"),
        "times": {
            side: spread([row.get("total_sec") for row in data["answers"].values()])
            for side, data in sides
        },
        "pairing": counts,
    }
    if without:
        numbers["declines_without_answer"] = both("m1", declined, without)
    return numbers, [case for case in context if case in set(pairs)]


def reference(base, first, second, families):
    """M2 of an external base: `agrees` among the questions with a reference, paired, and the
    right declines of those without (judge_export.m2: right or wrong by the decline)."""
    if any(first[case]["has_reference"] != second[case]["has_reference"] for case in first):
        raise SystemExit(f"{base}: V3's and V4's m2 plans give other questions a reference")

    def both_read(case):
        return first[case].get("m2") is not None and second[case].get("m2") is not None

    held = sorted(case for case in first if first[case]["has_reference"])
    without = sorted(case for case in first if not first[case]["has_reference"])
    pairs = [case for case in held if both_read(case)]
    apart = [case for case in without if both_read(case)]
    tags = {f"{base}:{case}": families[case] for case in pairs}

    def agrees(row):
        return row["m2"] == "agrees"

    return {
        "with_reference": {
            "questions": len(held),
            "pairs": len(pairs),
            "unpaired": unpaired(held, pairs),
            "agrees": paired(
                indicator(base, pairs, first, agrees), indicator(base, pairs, second, agrees), tags
            ),
        },
        "without_reference": {
            "questions": len(without),
            "pairs": len(apart),
            "unpaired": unpaired(without, apart),
            "right": {
                "v3": sum(first[case]["m2"] == "right" for case in apart),
                "v4": sum(second[case]["m2"] == "right" for case in apart),
            },
        },
    }


def defects(corpora, keys):
    """What is left of the two defects: the placeholder in more than one V4 answer of a key,
    the referral's share not falling on an external base."""
    left = [
        f"{key}: the placeholder in {corpora[key]['marks']['v4']['placeholder']} answers"
        for key in keys
        if corpora[key]["marks"]["v4"]["placeholder"] > 1
    ]
    left += [
        f"{base}: the referral's share does not fall"
        for base in BASES
        if base in keys and corpora[base]["referral"]["direction"] != "falls"
    ]
    return left


def decision(primary, corpora, keys, not_counted):
    """The spec's table, read in its order; the first row that holds decides.

    corpora: key -> its numbers, for the keys V4 ran whole; not_counted: key -> its plans not
    counted, an M1 plan of either side or its bridge. Harm is read on the counted keys.
      1 not adopted - harm: a base's bad share rises; its good share falls and its bad share
        does not; the declines of its questions without an answer fall; the pooled bad share
        rises, both bases counted;
      2 NOT_EVIDENCE - a plan not counted, or a key not run whole;
      3 adopted - the pooled bad share falls;
      4 kept - the two defects gone: the placeholder in at most one V4 answer of each key, and
        the referral's share falls on both external bases;
      5 not adopted - no gain.
    V4 stays when adopted or kept; otherwise V3 comes back.
    """
    counted = [key for key in keys if key not in not_counted]
    harm = []
    for key in counted:
        bad, good = corpora[key]["bad"]["direction"], corpora[key]["good"]["direction"]
        if bad == "rises":
            harm.append(f"{key}: the bad share rises")
        if good == "falls" and bad != "falls":
            harm.append(f"{key}: the good share falls, the bad share does not")
        guard = corpora[key].get("declines_without_answer")
        if guard is not None and guard["direction"] == "falls":
            harm.append(f"{key}: fewer declines where the gold says not answerable")
    pooled = primary["keys"]
    if len(pooled) > 1 and set(pooled) <= set(counted) and primary["direction"] == "rises":
        harm.append("pooled: the bad share rises")
    not_run = [key for key in KEYS if key not in keys]
    left = defects(corpora, keys)
    if harm:
        outcome, reasons = "not adopted", harm
    elif not_counted or not_run:
        outcome, reasons = "NOT_EVIDENCE", []
        if not_counted:
            names = [name for key in keys for name in not_counted.get(key, ())]
            reasons.append(f"a plan not counted: {', '.join(names)}")
        if not_run:
            reasons.append(f"not run whole, no harm read: {', '.join(not_run)}")
    elif primary["direction"] == "falls":
        outcome, reasons = "adopted", ["fewer bad answers"]
    elif not left:
        outcome, reasons = "kept", ["the two defects gone"]
    else:
        outcome, reasons = "not adopted", ["no gain", *left]
    return {
        "decision": outcome,
        "v4_stays": outcome in ("adopted", "kept"),
        "reasons": reasons,
        "harm": harm,
        "defects_left": left,
        "not_counted": {key: list(names) for key, names in not_counted.items()},
        "not_run": not_run,
    }


def sources(stand, judge, retrieval, external):
    """Each side's records by key and part: (folder, name)."""
    v3 = {"aircargo": {"m1": (judge, "p1-aircargo-judge"), "answers": (retrieval, "p1-aircargo")}}
    v4 = {"aircargo": {"m1": (stand, "v4-aircargo-judge"), "answers": (stand, "v4-aircargo")}}
    for base in BASES:
        v3[base] = {
            "m1": (judge, f"p4-{base}-judge-m1"),
            "m2": (judge, f"p4-{base}-judge-m2"),
            "answers": (external, f"p4-{base}"),
        }
        v4[base] = {
            "m1": (stand, f"v4-{base}-judge-m1"),
            "m2": (stand, f"v4-{base}-judge-m2"),
            "answers": (stand, f"v4-{base}"),
        }
    return {"v3": v3, "v4": v4}


def ids(name, rows):
    found = [row["case_id"] for row in rows]
    if len(set(found)) != len(found):
        raise SystemExit(f"{name}: a question stands twice")
    return set(found)


def answered_by(provenance):
    """The answers' model, its digest and the tenant of a judge record's runs."""
    return {
        (run.get("model"), run.get("model_digest"), run.get("tenant"))
        for run in (provenance.get("runs") or {}).values()
    }


def same_path(v3, v4):
    """V4's answers on stage 2's path: the index sources, the questions' file, the driver's
    tools, the overrides, the data, the model; every run's settings but its own paths."""
    (_, before, _), (name, after, _) = v3, v4
    for field in SAME_PATH:
        if after["provenance"].get(field) != before["provenance"].get(field):
            raise SystemExit(f"{name}: not stage 2's path, its {field} differs")
    settings = {
        json.dumps({k: v for k, v in run["settings"].items() if k not in PER_RUN}, sort_keys=True)
        for record in (before, after)
        for run in record["runs"]
    }
    if len(settings) != 1:
        raise SystemExit(f"{name}: not stage 2's path, its settings differ")


def check_bridge(key, bridge, stage2):
    """A key's bridge: the plan the spec registered, cut from stage 2's M1 plan, its first
    verdicts stage 2's own."""
    (name, record, rows), (_, before, first) = bridge, stage2
    provenance = record["provenance"]
    if provenance.get("plan_sha256") != BRIDGES[key]:
        raise SystemExit(f"{name}: not the bridge the spec registered")
    if provenance.get("prompt_id") != V3:
        raise SystemExit(f"{name}: its plan reads {provenance.get('prompt_id')}")
    for field in ("salt", "instructions_sha256", "references_sha256", "route", "runs"):
        if provenance.get(field) != before["provenance"].get(field):
            raise SystemExit(f"{name}: not stage 2's plan, its {field} differs")
    verdicts = {row["case_id"]: (row["item_id"], row["grade"]) for row in first}
    if not rows or any(
        verdicts.get(row["case_id"]) != (row["item_id"], row["grade"]) for row in rows
    ):
        raise SystemExit(f"{name}: its first verdicts are not stage 2's")


def check(loaded, keys):
    """The refusals: another prompt, judge, bridge, answer model, path or references; another
    stand; a path break; other questions. loaded: side -> key -> part -> (name, record, rows),
    the bridges under "bridge". The V4 stand's commit."""
    for side, prompt in zip(SIDES, (V3, V4), strict=True):
        for key in keys:
            parts = loaded[side][key]
            for part in ("m1", "m2"):
                if part not in parts:
                    continue
                name, record, _ = parts[part]
                provenance = record["provenance"]
                if provenance.get("prompt_id") != prompt:
                    raise SystemExit(f"{name}: its plan reads {provenance.get('prompt_id')}")
                withheld = provenance.get("references_withheld") is True
                if key in BASES and (
                    (part == "m1") != withheld or (part == "m2") != ("m2" in record)
                ):
                    raise SystemExit(
                        f"{name}: the m1 plan withholds the references, the m2 plan reads M2"
                    )
                before = loaded["v3"][key][part][1]["provenance"]
                for field in ("salt", "instructions_sha256", "references_sha256", "route"):
                    if provenance.get(field) != before.get(field):
                        raise SystemExit(f"{name}: not stage 2's judge, its {field} differs")
                if len(answered_by(provenance)) != 1 or answered_by(provenance) != answered_by(
                    before
                ):
                    raise SystemExit(f"{name}: answers of another model or tenant than stage 2's")
            name, _, rows = parts["marks"]
            if any(row["prompt_id"] != prompt for row in rows):
                raise SystemExit(f"{name}: marks of another prompt than {prompt}")
    commits = set()
    for side in SIDES:
        for key in keys:
            name, record, rows = loaded[side][key]["answers"]
            if record["aggregate"]["path_breaks"] or any(row["path_breaks"] for row in rows):
                raise SystemExit(f"{name}: a counted answer has a path break")
            if side == "v3" and record["provenance"]["code_sha"] != [CODE]:
                raise SystemExit(f"{name}: not the stand {CODE}")
            if side == "v4":
                commits.update(record["provenance"]["code_sha"])
    if len(commits) != 1 or CODE in commits:
        raise SystemExit(f"V4's answers name {sorted(commits)}: one stand, not stage 2's")
    for key in keys:
        same_path(loaded["v3"][key]["answers"], loaded["v4"][key]["answers"])
        check_bridge(key, loaded["bridge"][key], loaded["v3"][key]["m1"])
        name, _, rows = loaded["v3"][key]["answers"]
        questions = ids(name, rows)
        for side in SIDES:
            for other, _, others in loaded[side][key].values():
                if ids(other, others) != questions:
                    raise SystemExit(f"{key}: {other} holds other questions than {name}")
    return commits.pop()


def moment(text):
    return datetime.fromisoformat(text)


def environment(name, snapshots, launches):
    """The stand's environment, read before V4's first answer and after its last: stage 2's
    Ollama and interpreter. launches: the launch of each V4 answers run."""
    for snapshot in snapshots:
        ollama, found = snapshot["ollama"], snapshot["distributions"]
        if ollama.get("server_version") != OLLAMA or len(ollama.get("servers") or ()) != 1:
            raise SystemExit(f"{name}: not one Ollama server of stage 2's {OLLAMA}")
        newest = found.get("newest") or {}
        if found.get("freeze_sha256") != FREEZE or not (
            newest.get("changed") and moment(newest["changed"]) < moment(STAGE2_FIRST)
        ):
            raise SystemExit(f"{name}: the interpreter's distributions are not stage 2's")
    taken = sorted(moment(snapshot["taken"]) for snapshot in snapshots)
    started = min(moment(launch["started"]) for launch in launches)
    finished = max(moment(launch["finished"]) for launch in launches)
    if len(taken) < 2 or taken[0] > started or taken[-1] < finished:
        raise SystemExit(f"{name}: not read before V4's first answer and after its last")
    servers = {
        (server["pid"], server["started"], server["binary"])
        for snapshot in snapshots
        for server in snapshot["ollama"]["servers"]
    }
    return {
        "snapshots": len(taken),
        "taken": [taken[0].isoformat(), taken[-1].isoformat()],
        "ollama": OLLAMA,
        "servers": [
            {"pid": pid, "started": started, "binary": binary}
            for pid, started, binary in sorted(servers)
        ],
        "freeze_sha256": FREEZE,
        "newest": snapshots[-1]["distributions"]["newest"],
        "versions": snapshots[-1]["distributions"].get("versions"),
    }


def plan_summary(record):
    return {
        "status": record["status"],
        "retest_passed": record["retest"]["passed"],
        "admitted_cli": (record.get("replies") or {}).get("admitted_cli"),
    }


def build(stand, keys=KEYS, *, judge=JUDGE, retrieval=RETRIEVAL, external=EXTERNAL, root=WS):
    """The record of STAND_DIR against stage 2's on the keys V4 ran whole: the V3 folders and
    the root the inputs are named from can be given (the tests' own)."""
    stand, root = Path(stand).resolve(), Path(root).resolve()
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

    def load(folder, name):
        record = json.loads(read(folder / f"{name}.json").read_text(encoding="utf-8"))
        return name, record, load_jsonl(read(folder / f"{name}.cases.jsonl"))

    loaded = {side: {} for side in (*SIDES, "bridge")}
    folders = sources(stand, Path(judge), Path(retrieval), Path(external))
    for side in SIDES:
        for key in keys:
            loaded[side][key] = {part: load(*where) for part, where in folders[side][key].items()}
            name = f"{side}-{key}.marks"
            loaded[side][key]["marks"] = (name, None, load_jsonl(read(stand / f"{name}.jsonl")))
    for key in keys:
        loaded["bridge"][key] = load(stand, f"v4-bridge-{key}")
    commit = check(loaded, keys)
    if stand.name != commit[:7]:
        raise SystemExit(f"{stand.name}: the folder of the stand {commit} is {commit[:7]}")
    found = environment(
        "v4-environment.jsonl",
        load_jsonl(read(stand / "v4-environment.jsonl")),
        [run["launch"] for key in keys for run in loaded["v4"][key]["answers"][1]["runs"]],
    )

    def by_case(side, key):
        return {
            part: {row["case_id"]: row for row in rows}
            for part, (_, _, rows) in loaded[side][key].items()
        }

    corpora, pooled, same = {}, ({}, {}, {}), ({}, {}, {})
    for key in keys:
        v3, v4 = by_case("v3", key), by_case("v4", key)
        pairs = sorted(
            case for case in v3["m1"] if graded(v3["m1"][case]) and graded(v4["m1"][case])
        )
        families = {
            case: [f"{key}:cluster:{row['cluster']}"] if key in BASES else [f"{key}:answer:{case}"]
            for case, row in v3["m1"].items()
        }
        corpora[key], context = corpus(key, pairs, v3, v4, families)
        if key in BASES:
            for into, cases in ((pooled, pairs), (same, context)):
                into[0].update(indicator(key, cases, v3["m1"], is_bad))
                into[1].update(indicator(key, cases, v4["m1"], is_bad))
                into[2].update({f"{key}:{case}": families[case] for case in cases})
            statuses = {loaded[side][key]["m2"][1]["status"] for side in SIDES}
            corpora[key]["m2"] = {
                "status": "counted" if statuses == {"counted"} else "NOT_EVIDENCE",
                **reference(key, v3["m2"], v4["m2"], families),
            }
    primary = {"indicator": "bad", "keys": [key for key in BASES if key in keys]}
    primary.update(paired(*pooled))
    same_context = {"indicator": "bad", "keys": primary["keys"], **paired(*same)}
    plans = {
        side: {
            name: plan_summary(record)
            for key in keys
            for part, (name, record, _) in loaded[side][key].items()
            if part in ("m1", "m2")
        }
        for side in SIDES
    }
    plans["bridge"] = {
        loaded["bridge"][key][0]: plan_summary(loaded["bridge"][key][1]) for key in keys
    }
    not_counted = {}
    for key in keys:
        for name, record, _ in (
            loaded["v3"][key]["m1"],
            loaded["v4"][key]["m1"],
            loaded["bridge"][key],
        ):
            if record["status"] != "counted":
                not_counted.setdefault(key, []).append(name)
    return {
        "stand": commit,
        "stage2": CODE,
        "keys": keys,
        "prompts": {
            "v3": V3,
            "v4": V4,
            "v3_sha256": hashlib.sha256(V3_TEMPLATE.encode("utf-8")).hexdigest(),
            "v4_sha256": hashlib.sha256(V4_TEMPLATE.encode("utf-8")).hexdigest(),
            "template_delta": TEMPLATE_DELTA,
        },
        "tools": {name: sha256(HERE / name) for name in TOOLS},
        "disclosure": list(DISCLOSURE),
        "inputs": dict(sorted(inputs.items())),
        "environment": found,
        "primary": primary,
        "same_context": same_context,
        "corpora": corpora,
        "plans": plans,
        "decision": decision(primary, corpora, keys, not_counted),
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
    out = Path(argv[1]) if len(argv) == 2 else stand / "v4-record.json"
    record = build(stand, keys, **folders)
    write(out, record)
    print(out)
    print(json.dumps(record["decision"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
