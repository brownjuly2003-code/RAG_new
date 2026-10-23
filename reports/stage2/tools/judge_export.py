"""The judge's side of stage 2: the references, the handover reading, the committed record.

docs/specs/stage2-four-corpora.md, «The judge». Three commands:

  judge_export.py references KEY ROOT OUT
    On the Mac, in the stand's chatlive folder. The private references file of an external
    base: every registered question of KEY, one a line - case_id, stratum, cluster,
    conditional (ConditionalQA) and reference_answers, the dataset's answers of a question
    with an answer (ConditionalQA's answerable, WixQA's, MultiHop-RAG's but null_query) and
    none for the others, whose M2 is read from answers_question alone. The clusters are those
    of evaluation/external_parts.py: ConditionalQA the primary questions of one document,
    WixQA and MultiHop-RAG the questions joined by a shared gold document; any other question
    is a cluster of its own. OUT holds answer text: it stays on the hosts
    (evaluation/external_bases.json, "redistribution") and goes to the laptop's private folder
    for `chat_answer_judge.py plan --references`.

  judge_export.py reading PLAN_DIR
    On the laptop, part 1's plan only (the handover-signal plan's 1.2): writes into its
    plan.json the key reading - the section «Reading» of docs/specs/handover-signal.md as the
    last commit that changed the file holds it, with that commit. Refused once the plan has a
    reply or a reading, or while the file has uncommitted changes.

  judge_export.py export PLAN_DIR NAME OUT --run LABEL=DIR ... [--references FILE]
    On the laptop: the plan's committed record, OUT/NAME.json and OUT/NAME.cases.jsonl. A
    verdict counts from a request's first six replies only - the adapter's three attempts and
    one more run of the plan - and through the adapter's own checks (the plan as the adapter
    froze it, the plan's model, a clean session, the planned request); the references file
    is the one the plan was frozen with. Per question: its ids, class or level, the verdict's
    enums and integers, never the note, and the basis of the verdict's admission - which of
    its request's replies it is and the CLI's version - each string of a row an identifier
    or a registered value, checked (`plain`); on an external base M2 - the judge's reference
    for a question with one, right or wrong by answers_question for one without - and the
    question's stratum, cluster and condition. The plan's numbers: per run as the adapter
    counts them; each share with its n and Wilson 95 % interval and, on an external base, its
    clusters and cluster-bootstrap interval (evaluation.semantic_ruler.cluster_summary); the
    retest's pairs with their first requests' ids, agreement, pairs two steps apart,
    quadratic kappa and its bootstrap interval, and the stability rule's verdict; the other
    fields' agreement on the pairs (M2's reference on the pairs of a question with one); which
    reply admitted each counted verdict and under which CLI. A plan that withheld its references
    from the requests (`chat_answer_judge.py plan --withhold-references`, part 4's M1, amended
    2026-10-23) takes from the file the strata and clusters only, and its record holds no M2:
    each question's has_reference is false there. The record's status is "counted",
    or "NOT_EVIDENCE" when the retests fail the rule - then the command exits 3. The run
    folders, given as to the plan, supply the questions and the documents' names
    stage2_common.without_text keeps out.
"""

import argparse
import json
import math
import random
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The stand's root above its chatlive folder; the repository's above reports/stage2/tools.
WS = next(p for p in HERE.parents if (p / "scripts" / "chat_answer_judge.py").exists())
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(WS))
from stage2_common import load_jsonl, sha256, without_text, write  # noqa: E402

# The adapter's three attempts in one run of the plan, and one more run: chat_answer_judge's
# REPLIES, held equal by a test (the adapter is not imported where the references are made).
REPLIES = 6
PLAIN = re.compile(r"[A-Za-z0-9_.:~-]{1,120}")
MIN_PAIRS = 12
KAPPA = 0.6
AGREE, OF = 13, 15  # at least 13 in 15 of the pairs agree, and none is two steps apart
HANDOVER = "docs/specs/handover-signal.md"
READING = "## Reading — frozen in stage 1's `plan.json`, before its first verdict"
EXTERNAL = ("conditionalqa", "wixqa", "multihoprag")


def has_answer(key, case):
    """Whether a registered question has an answer the judge can hold the reply to."""
    if key == "conditionalqa":
        return case["stratum"] == "answerable"
    return key == "wixqa" or case["stratum"] != "null_query"


def clusters(key, cases):
    """Each question's cluster, numbered in evaluation.semantic_ruler.family_clusters' order."""
    from evaluation.external_parts import primary
    from evaluation.semantic_ruler import family_clusters

    families = {}
    for case in cases:
        if key == "conditionalqa":
            mine = [f"document:{case['document']}"] if primary(case) else []
        else:
            mine = [f"gold:{name}" for name in case["gold_sources"]]
        families[case["case_id"]] = mine or [f"case:{case['case_id']}"]
    return {
        case_id: number
        for number, group in enumerate(family_clusters(families))
        for case_id in group
    }


def reference_rows(key, cases):
    """The private references file's rows, in the registered order of the cases given."""
    if key not in EXTERNAL:
        raise SystemExit(f"{key}: references are an external base's")
    cluster = clusters(key, cases)
    rows = []
    for case in cases:
        answers = [str(a) for a in case.get("reference_answers") or [] if str(a).strip()]
        if has_answer(key, case) and not answers:
            raise SystemExit(f"{case['case_id']}: a question with an answer has no reference")
        row = {
            "case_id": case["case_id"],
            "stratum": case["stratum"],
            "cluster": cluster[case["case_id"]],
            "reference_answers": answers if has_answer(key, case) else [],
        }
        if key == "conditionalqa":
            row["conditional"] = bool(case.get("conditional"))
        rows.append(row)
    return rows


def references(key, root, out):
    from stage2_cases import registered

    cases_file = Path(root) / key / "cases.jsonl"
    by_id = {case["case_id"]: case for case in load_jsonl(cases_file)}
    rows = reference_rows(key, [by_id[i] for i in registered(key, cases_file)])
    Path(out).write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    with_one = sum(bool(row["reference_answers"]) for row in rows)
    count = len({row["cluster"] for row in rows})
    print(f"{key}: {len(rows)} questions, {with_one} with a reference, {count} clusters")
    return 0


def reading_text(text):
    """The section «Reading» of the handover-signal plan, without its heading."""
    lines = text.splitlines()
    if READING not in lines:
        raise SystemExit(f"{HANDOVER} holds no section «{READING[3:]}»")
    start = lines.index(READING) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).strip()


def add_reading(plan_dir, text, commit):
    from scripts import chat_answer_judge as answer_judge

    plan_path = Path(plan_dir) / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if load_jsonl(Path(plan_dir) / "verdicts.jsonl"):
        raise SystemExit("the plan has replies: its reading is frozen before the first")
    if "reading" in plan:
        raise SystemExit("the plan holds a reading already")
    tenants = {str(record.get("tenant")) for record in plan["runs"].values()}
    if plan.get("salt") != answer_judge.SALT or tenants != {"aircargo"}:
        raise SystemExit("the reading belongs to part 1's plan: the answer judge on aircargo")
    plan["reading"] = {
        "source": HANDOVER,
        "commit": commit,
        "section": READING[3:],
        "text": reading_text(text),
    }
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", "utf-8")
    return plan["reading"]


def git(*args):
    return subprocess.run(
        ["git", "-C", str(WS), *args], capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout


def counted(rows):
    """A request's first six replies, and how many came past them (`past_the_limit`).

    A refused route's row is no reply. The adapter applies the same limit itself.
    """
    seen = Counter()
    kept = []
    for row in rows:
        if row.get("status") in ("valid", "invalid"):
            seen[row.get("item_id")] += 1
            if seen[row.get("item_id")] > REPLIES:
                continue
        kept.append(row)
    return kept, sum(max(0, n - REPLIES) for n in seen.values())


def admission(rows, valid):
    """Each counted verdict's basis: which of its request's replies it is, and the CLI's version.

    The adapter's own rule, mirrored: a request's first valid reply among its first six.
    """
    seen, admitted = Counter(), {}
    for row in rows:
        if row.get("status") not in ("valid", "invalid"):
            continue
        item_id = str(row["item_id"])
        seen[item_id] += 1
        if row["status"] == "valid" and item_id in valid and item_id not in admitted:
            if seen[item_id] <= REPLIES:
                session = row.get("session") or {}
                admitted[item_id] = (seen[item_id], session.get("cli_version"))
    if set(admitted) != set(valid):
        raise SystemExit("a counted verdict has no reply the adapter's rule admits")
    return admitted


def plain(row):
    """Refuse a question row with a string that is not an identifier or a registered value.

    Ids, labels, enums and hashes only - letters, digits and _.:~- - so no text of a question,
    a document or an answer can ride in a row; the error names the field, never the value.
    """
    for key, value in row.items():
        for one in value if isinstance(value, list) else [value]:
            if isinstance(one, str) and not PLAIN.fullmatch(one):
                raise SystemExit(f"{row.get('item_id')}: {key} holds more than an identifier")
    return row


def judge_of(plan):
    """A plan's adapter: its scale (lowest first), the fields a row keeps, those paired."""
    from scripts import chat_answer_judge as answer_judge
    from scripts import context_judge

    if plan.get("salt") == answer_judge.SALT:
        return {
            "answers": True,
            "module": answer_judge,
            "scale": tuple(reversed(answer_judge.CLASSES)),
            "keep": tuple(key for key in answer_judge.KEYS if key != "note"),
            "paired": ("reference", "answers_question", "context_has_answer", "defect"),
        }
    if plan.get("salt") == context_judge.SALT:
        return {
            "answers": False,
            "module": context_judge,
            "scale": context_judge.LEVELS,
            "keep": tuple(key for key in context_judge.KEYS if key != "note"),
            "paired": ("documents_with_answer",),
        }
    raise SystemExit("the plan is neither chat_answer_judge.py's nor context_judge.py's")


def grade(judge, item, valid):
    """An answer's class or a context's level; None when its request has no counted verdict."""
    if item.get("empty_answer"):
        return "bad"
    if item.get("empty_context"):
        return "none"
    verdict = valid.get(item["item_id"])
    if verdict is None:
        return None
    return judge["module"].classify(verdict) if judge["answers"] else verdict["context_answer"]


def m2(item, verdict):
    """M2 on an external base: the judge's reference, or right or wrong by a decline.

    An empty answer has no verdict: beside a reference it is counted apart; to a question
    without one it is wrong, for it does not decline (the spec, «What each number is»).
    """
    if item.get("empty_answer"):
        return "empty_answer" if item["has_reference"] else "wrong"
    if verdict is None:
        return None
    if item["has_reference"]:
        return verdict["reference"]
    return "right" if verdict["answers_question"] == "declined" else "wrong"


def share(values, families):
    """values: case -> 0 or 1. Its n, hits and Wilson interval; with families the clusters'."""
    from evaluation.semantic_ruler import cluster_summary
    from scripts.chat_signals import wilson

    n, hits = len(values), sum(values.values())
    out = {"n": n, "hits": hits, "share": round(hits / n, 4) if n else None}
    out["wilson95"] = wilson(hits, n)
    if families and n:
        summary = cluster_summary(values, {case: families[case] for case in values})
        out["clusters"] = summary["clusters"]
        out["cluster95"] = [round(value, 4) for value in summary["ci95"]]
    return out


def shares(grades, names, families):
    """The share of each name among the graded questions of grades (case -> name or None)."""
    graded = {case: name for case, name in grades.items() if name is not None}
    return {
        name: share({case: int(value == name) for case, value in graded.items()}, families)
        for name in names
    }


def kappa_interval(pairs, levels):
    """The quadratic kappa's bootstrap 95 % interval: pairs drawn with replacement."""
    from evaluation.semantic_ruler import RESAMPLES, SEED
    from scripts.chat_answer_judge import quadratic_kappa

    if not pairs:
        return {"ci95": None, "resamples_undefined": None}
    rng = random.Random(SEED)
    draws = []
    for _ in range(RESAMPLES):
        drawn = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        value = quadratic_kappa(drawn, levels)
        if value is not None:
            draws.append(value)
    draws.sort()

    def at(p):
        position = (len(draws) - 1) * p
        low, high = math.floor(position), math.ceil(position)
        return round(draws[low] + (draws[high] - draws[low]) * (position - low), 4)

    return {
        "ci95": [at(0.025), at(0.975)] if draws else None,
        "resamples_undefined": RESAMPLES - len(draws),
    }


def stability(judge, plan, valid):
    """The retest pairs and the stability rule of the spec; the other fields' agreement."""
    from scripts.chat_answer_judge import quadratic_kappa

    scale = judge["scale"]
    index = {name: number for number, name in enumerate(scale)}
    first = {item["item_id"]: item for item in plan["items"] if "retest_of" not in item}
    pairs, ids, fields, of = [], [], Counter(), Counter()
    for item in plan["items"]:
        if "retest_of" not in item:
            continue
        before = grade(judge, first[item["retest_of"]], valid)
        after = grade(judge, item, valid)
        if before is None or after is None:
            continue
        pairs.append((index[before], index[after]))
        ids.append(item["retest_of"])
        a, b = valid[item["retest_of"]], valid[item["item_id"]]
        for name in judge["paired"]:
            # M2's reference is read on the pairs of a question with one; elsewhere both say none.
            if name == "reference" and not item.get("has_reference"):
                continue
            of[name] += 1
            fields[name] += a[name] == b[name]
    n = len(pairs)
    agree = sum(a == b for a, b in pairs)
    apart = sum(abs(a - b) >= 2 for a, b in pairs)
    kappa = quadratic_kappa(pairs, len(scale))
    by_kappa = kappa is not None and kappa >= KAPPA
    by_agreement = n > 0 and agree * OF >= AGREE * n and apart == 0
    return {
        "planned": sum("retest_of" in item for item in plan["items"]),
        "scale": list(scale),
        "pairs": n,
        "pairs_list": [list(pair) for pair in pairs],
        # The item id of each pair's first request, in the order of pairs_list.
        "pairs_ids": ids,
        "agree": agree,
        "two_steps_apart": apart,
        "quadratic_kappa": kappa,
        **kappa_interval(pairs, len(scale)),
        "passes_by_kappa": by_kappa,
        "passes_by_agreement": by_agreement,
        "enough_pairs": n >= MIN_PAIRS,
        "passed": n >= MIN_PAIRS and (by_kappa or by_agreement),
        "field_agreement": {
            name: {"agree": fields[name], "of": of[name]} for name in judge["paired"]
        },
    }


def export(plan_dir, name, out, runs, references_file=None):
    plan_dir = Path(plan_dir)
    plan = json.loads((plan_dir / "plan.json").read_text(encoding="utf-8"))
    judge = judge_of(plan)
    module, scale, answers = judge["module"], judge["scale"], judge["answers"]
    if sorted(runs) != sorted(plan["runs"]):
        raise SystemExit(f"--run gives {sorted(runs)}, the plan holds {sorted(plan['runs'])}")
    tenants = {str(record.get("tenant")) for record in plan["runs"].values()}
    if len(tenants) != 1:
        raise SystemExit(f"one plan, one base: the plan holds {sorted(tenants)}")
    base = tenants.pop().removeprefix("ext_")
    if answers and base == "aircargo" and "reading" not in plan:
        raise SystemExit("part 1's plan holds no reading: judge_export.py reading comes first")
    names, questions = set(), set()
    for label, run in runs.items():
        launch = json.loads((Path(run) / "launch.json").read_text(encoding="utf-8"))
        if any(launch.get(key) != value for key, value in plan["runs"][label].items()):
            raise SystemExit(f"{run}: its launch.json is not the run the plan names {label}")
        read = module.run_answers if answers else module.run_contexts
        for entry in read(Path(run)):
            questions.add(entry["question"])
            names.update(source for source, _ in entry["documents"])
    refs = {}
    for row in load_jsonl(references_file) if references_file else []:
        if row["case_id"] in refs:
            raise SystemExit(f"the references file holds {row['case_id']} twice")
        refs[row["case_id"]] = row
    if base in EXTERNAL and not refs:
        raise SystemExit("an external base's record needs its references file: the clusters")
    if (sha256(references_file) if references_file else None) != plan.get("references_sha256"):
        raise SystemExit("the references file is not the one the plan was frozen with")
    withheld = plan.get("references_withheld", False) is True
    rows_in = load_jsonl(plan_dir / "verdicts.jsonl")
    # The adapter reads the whole journal, the rows past a request's sixth reply included: it
    # refuses a row of a request the plan does not hold, and counts the first six itself.
    _, past = counted(rows_in)
    valid = module._vouched(plan, rows_in)
    admitted = admission(rows_in, valid)
    first = [item for item in plan["items"] if "retest_of" not in item]
    if len({item["case_id"] for item in first}) != len(first):
        raise SystemExit("a question stands twice in the plan: one counted run per batch")
    rows, grades, by_m2 = [], {}, {}
    for item in sorted(first, key=lambda item: (item["run"], item["case_id"])):
        verdict = valid.get(item["item_id"])
        row = {
            key: item.get(key)
            for key in (
                "run",
                "case_id",
                "item_id",
                "prompt_sha256",
                "documents",
                "route",
                "marks_listed",
                "marks_unlisted",
                "has_reference",
                "empty_answer",
                "empty_context",
            )
            if key in item
        }
        row["grade"] = grades[item["case_id"]] = grade(judge, item, valid)
        row["missing"] = row["grade"] is None
        if verdict is not None:
            row.update({key: verdict[key] for key in judge["keep"]})
            row["admitted_reply"], row["admitted_cli"] = admitted[item["item_id"]]
        if item["case_id"] in refs:
            ref = refs[item["case_id"]]
            carried = bool(ref["reference_answers"]) and not withheld
            if answers and item["has_reference"] != carried:
                raise SystemExit(f"{item['case_id']}: the plan and the references disagree")
            row.update(stratum=ref["stratum"], cluster=ref["cluster"])
            if "conditional" in ref:
                row["conditional"] = ref["conditional"]
        if answers and base in EXTERNAL and not withheld:
            row["m2"] = by_m2[item["case_id"]] = m2(item, verdict)
        rows.append(plain(row))
    if refs and any(case not in refs for case in grades):
        raise SystemExit("the references file lacks a question of the plan")
    families = {case: [f"cluster:{refs[case]['cluster']}"] for case in grades} if refs else None
    retest = stability(judge, plan, valid)
    record = {
        "plan": name,
        # The spec, «What is NOT_EVIDENCE»: a plan's numbers when its retests fail the rule.
        "status": "counted" if retest["passed"] else "NOT_EVIDENCE",
        "judge": "answers" if answers else "contexts",
        "base": base,
        "provenance": {
            "plan_sha256": sha256(plan_dir / "plan.json"),
            "verdicts_sha256": sha256(plan_dir / "verdicts.jsonl"),
            "references_sha256": sha256(references_file) if references_file else None,
            "references_withheld": withheld,
            "salt": plan["salt"],
            "prompt_id": plan.get("prompt_id"),
            "instructions_sha256": plan.get("instructions_sha256"),
            "route": plan.get("route"),
            "runs": plan["runs"],
            "adapter_sha256": sha256(module.__file__),
            "tool_sha256": sha256(__file__),
            "replies_counted_per_request": REPLIES,
            "reading": plan.get("reading"),
        },
        "replies": {
            "rows": len(rows_in),
            "statuses": dict(Counter(str(row.get("status")) for row in rows_in)),
            "past_the_limit": past,
            "models": dict(Counter(str(row.get("model")) for row in rows_in if "model" in row)),
            # Every counted verdict, retests included: which reply admitted it, and the CLI.
            "admitted_at_reply": dict(Counter(str(reply) for reply, _ in admitted.values())),
            "admitted_cli": dict(Counter(str(cli) for _, cli in admitted.values())),
            "cost_usd": round(
                sum(float((row.get("usage") or {}).get("total_cost_usd") or 0) for row in rows_in),
                4,
            ),
        },
        "questions": len(first),
        "requests_valid": len(valid),
        "missing": sorted(case for case, value in grades.items() if value is None),
        "per_run": module.summarize(plan, rows_in)["per_run"],
        "shares": shares(grades, scale, families),
        "retest": retest,
    }
    if not answers:
        held = {
            case: (None if v is None else v in ("full", "partial")) for case, v in grades.items()
        }
        record["holds_the_answer"] = share(
            {case: int(v) for case, v in held.items() if v is not None}, families
        )
    if by_m2:
        with_ref = {r["case_id"]: r["m2"] for r in rows if r["has_reference"]}
        without = {r["case_id"]: r["m2"] for r in rows if not r["has_reference"]}
        record["m2"] = {
            "with_reference": shares(
                with_ref, ("agrees", "partial", "disagrees", "declined", "empty_answer"), families
            ),
            "without_reference": shares(without, ("right", "wrong"), families),
        }
        if any(r.get("conditional") for r in rows):
            for group, wanted in (("conditional", True), ("not_conditional", False)):
                apart = {r["case_id"] for r in rows if r["has_reference"]}
                apart = {c for c in apart if bool(refs[c].get("conditional")) is wanted}
                record[group] = {
                    "questions": len(apart),
                    "shares": shares({c: grades[c] for c in apart}, scale, families),
                    "m2": shares(
                        {c: by_m2[c] for c in apart},
                        ("agrees", "partial", "disagrees", "declined", "empty_answer"),
                        families,
                    ),
                }
    without_text(record, names, questions)
    for row in rows:
        without_text(row, names, questions)
    write(out, name, record, rows)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    refs = commands.add_parser("references")
    refs.add_argument("key", choices=EXTERNAL)
    refs.add_argument("root", type=Path)
    refs.add_argument("out", type=Path)
    reading = commands.add_parser("reading")
    reading.add_argument("plan_dir", type=Path)
    exported = commands.add_parser("export")
    exported.add_argument("plan_dir", type=Path)
    exported.add_argument("name")
    exported.add_argument("out", type=Path)
    exported.add_argument("--run", action="append", required=True, metavar="LABEL=DIR")
    exported.add_argument("--references", type=Path)
    args = parser.parse_args(argv)
    if args.command == "references":
        return references(args.key, args.root, args.out)
    if args.command == "reading":
        if git("status", "--porcelain", "--", HANDOVER).strip():
            raise SystemExit(f"{HANDOVER} has uncommitted changes")
        commit = git("log", "-1", "--format=%H", "--", HANDOVER).strip()
        frozen = add_reading(args.plan_dir, git("show", f"{commit}:{HANDOVER}"), commit)
        print(f"reading of {frozen['source']} at {commit[:7]} written into {args.plan_dir}")
        return 0
    runs = {}
    for spec in args.run:
        label, _, path = spec.partition("=")
        if not label or not path or label in runs:
            raise SystemExit(f"--run {spec}: give each run once as LABEL=DIR")
        runs[label] = Path(path)
    record = export(args.plan_dir, args.name, args.out, runs, args.references)
    shown = ("status", "questions", "missing", "retest")
    print(json.dumps({key: record[key] for key in shown}, indent=1))
    return 0 if record["status"] == "counted" else 3


if __name__ == "__main__":
    raise SystemExit(main())
