"""The judge's bridge of one key: stage 2's retested requests of its M1 plan, graded again.

docs/specs/answer-prompt-v4.md, «The judge». Before V4's first request, on the laptop, over
stage 2's private M1 plan of a key (p1/judge for aircargo, p4/judge/<base>-m1):

  python reports/answer-prompt-v4/tools/bridge_plan.py STAGE2_PLAN_DIR OUT_DIR

writes OUT_DIR/plan.json - stage 2's plan holding only the requests it retested and their
retest copies, nothing else changed - and OUT_DIR/verdicts.jsonl - stage 2's replies to
those first requests, its lines as they stand - and prints the plan's SHA-256, which the
spec and v4_record.BRIDGES name. `chat_answer_judge.py run` then sends the retests alone, in
V4's judge window; judge_export.py exports the folder as v4-bridge-<key>, and its stability
rule reads each of stage 2's verdicts against the new one: a judge that moved since stage 2
fails it.
"""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(WS))
USAGE = "usage: bridge_plan.py STAGE2_PLAN_DIR OUT_DIR"


def bridge(plan):
    """The plan cut to its retests and the requests they repeat, in the plan's order."""
    again = {item["retest_of"] for item in plan["items"] if "retest_of" in item}
    if not again:
        raise SystemExit("the plan holds no retest: no bridge")
    items = [item for item in plan["items"] if item["item_id"] in again or "retest_of" in item]
    return {**plan, "items": items}


def first_replies(lines, plan):
    """Stage 2's journal lines of the bridge's first requests, as they stand."""
    first = {item["item_id"] for item in plan["items"] if "retest_of" not in item}
    kept = [line for line in lines if line.strip() and json.loads(line).get("item_id") in first]
    if {json.loads(line)["item_id"] for line in kept} != first:
        raise SystemExit("stage 2's journal lacks a reply to a request the bridge repeats")
    return kept


def main(argv=None):
    from scripts.chat_answer_judge import check_plan

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        raise SystemExit(USAGE)
    source, out = Path(args[0]), Path(args[1])
    if out.exists():
        raise SystemExit(f"{out}: a bridge is frozen once")
    plan = json.loads((source / "plan.json").read_text(encoding="utf-8"))
    try:
        check_plan(plan)
        new = bridge(plan)
        check_plan(new)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    lines = (source / "verdicts.jsonl").read_bytes().decode("utf-8").splitlines(keepends=True)
    kept = first_replies(lines, new)
    data = (json.dumps(new, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    out.mkdir(parents=True)
    (out / "plan.json").write_bytes(data)
    (out / "verdicts.jsonl").write_bytes("".join(kept).encode("utf-8"))
    retests = sum("retest_of" in item for item in new["items"])
    print(f"{out}: {retests} retests, {len(kept)} replies of stage 2 kept")
    print(f"PLAN_SHA256 {hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
