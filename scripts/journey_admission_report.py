"""Publish the T-01 shipment-status admission score over the pinned B.1 corpus.

    python scripts/journey_admission_report.py
    python scripts/journey_admission_report.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.journey_admission import (  # noqa: E402
    CorpusDigestMismatchError,
    format_report,
    score_default_corpus,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit one machine-readable report object")
    args = parser.parse_args(argv)
    try:
        report = score_default_corpus()
    except CorpusDigestMismatchError as error:
        print(f"journey admission report refused: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True))
    else:
        print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
