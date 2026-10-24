"""The placeholder and the referral of each answer: ids and booleans of private answers.

docs/specs/answer-prompt-v4.md, «How it is read»: the two defects whose end the decision's
«kept» reads. On the laptop, over the private run folders of one prompt's answers - stage 2's
of QA_PROMPT_V3 or the V4 runs' - as scripts/chat_answer_judge.run_answers reads them:

  python reports/answer-prompt-v4/tools/answer_marks.py OUT.jsonl --run LABEL=DIR [--run ...]

writes OUT, one line an answer, sorted by run and question:
  {"run", "case_id", "prompt_id", "placeholder", "referral"}
`placeholder`: the answer prints V3's «[N]» as it stands; `referral`: the answer holds the
noun of V3's own instruction «suggest contacting a support specialist», in the two languages
of the questions. All runs hold one answer prompt (chat_answer_judge.one_prompt). Each row
passes stage2_common.without_text with the runs' questions and documents' names: no text of
an answer, a question or a document leaves the laptop.
"""

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
sys.path.insert(0, str(WS / "reports" / "stage2" / "tools"))
sys.path.insert(1, str(WS))
from stage2_common import without_text  # noqa: E402

PLACEHOLDER = re.compile(r"\[N\]")
REFERRAL = re.compile(r"specialist|специалист", re.IGNORECASE)


def mark_rows(runs):
    """runs: label -> run folder. One row per answered case, refused across two prompts."""
    from scripts.chat_answer_judge import one_prompt, run_answers

    rows, names, questions = [], set(), set()
    for label, run in runs.items():
        try:
            answers = run_answers(Path(run))
        except ValueError as exc:
            raise SystemExit(f"{label}: {exc}") from None
        for answer in answers:
            questions.add(answer["question"])
            names.update(source for source, _ in answer["documents"])
            rows.append(
                {
                    "run": label,
                    "case_id": answer["case_id"],
                    "prompt_id": answer["prompt_id"],
                    "placeholder": bool(PLACEHOLDER.search(answer["answer"])),
                    "referral": bool(REFERRAL.search(answer["answer"])),
                }
            )
    try:
        one_prompt(row["prompt_id"] for row in rows)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    if not rows:
        raise SystemExit("the runs hold no answer")
    rows.sort(key=lambda row: (row["run"], row["case_id"]))
    return [without_text(row, names, questions) for row in rows]


def write(out, rows):
    Path(out).write_bytes(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--run", action="append", required=True, metavar="LABEL=DIR")
    args = parser.parse_args(argv)
    runs = {}
    for spec in args.run:
        label, _, path = spec.partition("=")
        if not label or not path or label in runs:
            raise SystemExit(f"--run {spec}: give each run once as LABEL=DIR")
        runs[label] = Path(path)
    rows = mark_rows(runs)
    write(args.out, rows)
    print(
        f"{len(rows)} answers of {rows[0]['prompt_id']}: "
        f"{sum(row['placeholder'] for row in rows)} with the placeholder, "
        f"{sum(row['referral'] for row in rows)} with the referral, in {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
