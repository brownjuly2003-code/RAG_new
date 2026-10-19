"""The registered questions of one stage-2 run, in order, one case id a line (PLAN.md stage 2).

Usage: stage2_cases.py KEY CASES_FILE
  aircargo      - evaluation/curated_cases_aircargo.jsonl in file order (100);
  aircargo-gr   - evaluation/curated_cases_aircargo_gr_multihop.jsonl in file order (15);
  conditionalqa - the selection stage2, then stage2_not_answerable (80 + 20);
  wixqa, multihoprag - the selection stage2 (100 each).
The selections are read through evaluation.external_parts.read, which refuses a locked part;
each id must stand in CASES_FILE, the questions file the runs will read. The stand reads its
own copies: the files of its commit.
"""

import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS))
AIRCARGO = {
    "aircargo": WS / "evaluation" / "curated_cases_aircargo.jsonl",
    "aircargo-gr": WS / "evaluation" / "curated_cases_aircargo_gr_multihop.jsonl",
}
SELECTIONS = {
    "conditionalqa": ("stage2", "stage2_not_answerable"),
    "wixqa": ("stage2",),
    "multihoprag": ("stage2",),
}


def ids_of(path):
    return [
        json.loads(line)["case_id"]
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def registered(key, cases_file):
    """The ids of KEY in their registered order, each checked against CASES_FILE."""
    if key in AIRCARGO:
        ids = ids_of(AIRCARGO[key])
    else:
        from evaluation import external_parts as parts

        registration = parts.registration()
        ids = [i for name in SELECTIONS[key] for i in parts.read(registration, key, selection=name)]
    known = set(ids_of(cases_file))
    missing = [i for i in ids if i not in known]
    if missing or len(set(ids)) != len(ids):
        raise SystemExit(f"{key}: {len(missing)} ids not in {cases_file} or an id repeats")
    return ids


def main():
    print("\n".join(registered(sys.argv[1], sys.argv[2])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
