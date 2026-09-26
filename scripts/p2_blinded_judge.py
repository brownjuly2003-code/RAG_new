#!/usr/bin/env python3
"""Offline P2 runner; judge calls are made only by the explicit judge command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.blinded_judge import (  # noqa: E402
    INSTRUCTION_SHA256,
    InvalidControl,
    NotEvidence,
    build_report,
    build_request,
    draw_human_sample,
    import_human_grades,
    load_inputs,
    run_judge,
    write_human_page,
)
from evaluation.blinded_judge_clients import GlmClient, MistralClient, SonnetClient  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="P2 blinded relevance judgment")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("units")
    judge = commands.add_parser("judge")
    judge.add_argument("--judge", choices=("sonnet", "glm", "mistral"), required=True)
    judge.add_argument("--pool", choices=("H", "Hm", "both"), default="both")
    judge.add_argument("--limit", type=int)
    judge.add_argument("--gk-base", default="http://127.0.0.1:8011")
    judge.add_argument("--glm-settings", type=Path)
    judge.add_argument("--mistral-key-file", type=Path)
    sample = commands.add_parser("human-sample")
    sample.add_argument("--out", type=Path, required=True)
    human_import = commands.add_parser("human-import")
    human_import.add_argument("--grades", type=Path, required=True)
    human_import.add_argument("--grader", required=True)
    human_import.add_argument("--date", required=True)
    human_import.add_argument(
        "--out", type=Path, default=PROJECT_ROOT / "reports/p2/human-grades.json"
    )
    report = commands.add_parser("report")
    report.add_argument("--out-dir", type=Path, default=PROJECT_ROOT / "reports/p2")
    report.add_argument("--store", type=Path, action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        inputs = load_inputs()
        if args.command == "units":
            for name, pool in inputs.pools.items():
                print(
                    json.dumps(
                        {
                            "pool": name,
                            "cases": len(pool.cases),
                            "units": len(pool.cases) * 5,
                            "shortened_units": pool.shortened_units,
                            "control_H_top_k_5": inputs.control_precision,
                            "instruction_sha256": INSTRUCTION_SHA256,
                            "requests": {
                                case.case_id: build_request(case).sha256 for case in pool.cases
                            },
                        },
                        ensure_ascii=False,
                    )
                )
        elif args.command == "judge":
            if args.judge == "sonnet":
                client = SonnetClient(args.gk_base)
            elif args.judge == "glm":
                client = GlmClient(args.glm_settings)
            else:
                if args.mistral_key_file is None:
                    raise ValueError("--mistral-key-file is required for mistral")
                client = MistralClient(args.mistral_key_file)
            names = ("H", "Hm") if args.pool == "both" else (args.pool,)
            cases = [case for name in names for case in inputs.pools[name].cases]
            result = run_judge(
                args.judge,
                client,
                cases,
                PROJECT_ROOT / "reports/p2/replies" / f"{args.judge}.jsonl",
                control_precision=inputs.control_precision,
                limit=args.limit,
            )
            print(json.dumps(result, ensure_ascii=False))
        elif args.command == "human-sample":
            pool = inputs.pools["H"]
            sample = draw_human_sample(pool.cases, pool.ruler_per_case)
            write_human_page(sample, args.out)
            print(args.out)
        elif args.command == "human-import":
            pool = inputs.pools["H"]
            sample = draw_human_sample(pool.cases, pool.ruler_per_case)
            result = import_human_grades(args.grades, sample, args.grader, args.date)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            print(args.out)
        elif args.command == "report":
            stores = sorted((PROJECT_ROOT / "reports/p2/replies").glob("*.jsonl")) + args.store
            path, _ = build_report(inputs, stores, out_dir=args.out_dir)
            print(path)
    except (InvalidControl, NotEvidence, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
