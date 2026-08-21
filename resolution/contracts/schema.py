from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from resolution.contracts.models import ResolutionContract

DEFAULT_JSON_SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schemas" / "resolution-contract-v0.1.schema.json"
)


def resolution_contract_json_schema() -> dict[str, Any]:
    return cast(dict[str, Any], ResolutionContract.model_json_schema(mode="validation"))


def resolution_contract_schema_json() -> str:
    return (
        json.dumps(
            resolution_contract_json_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def check_schema_snapshot(path: Path = DEFAULT_JSON_SCHEMA_PATH) -> bool:
    return path.is_file() and path.read_text(encoding="utf-8") == resolution_contract_schema_json()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export or verify ResolutionContract v0.1 schema")
    parser.add_argument("--check", action="store_true", help="fail when the snapshot is stale")
    parser.add_argument("--stdout", action="store_true", help="print the generated schema")
    parser.add_argument("--output", type=Path, default=DEFAULT_JSON_SCHEMA_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    generated = resolution_contract_schema_json()
    if args.stdout:
        print(generated, end="")
        return 0
    if args.check:
        return 0 if check_schema_snapshot(args.output) else 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generated, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_JSON_SCHEMA_PATH",
    "check_schema_snapshot",
    "resolution_contract_json_schema",
    "resolution_contract_schema_json",
]
