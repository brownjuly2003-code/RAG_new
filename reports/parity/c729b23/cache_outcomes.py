"""Count the cache records of a finished parity run by kind and by llm outcome.

Read-only. The digest is the one scripts/production_parity.py uses; the manifest
digest it prints must equal manifest_sha256 in comparison.json.
"""

import hashlib
import json
import sys
from pathlib import Path


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def main(run):
    identity = digest(json.loads((run / "manifest.json").read_text(encoding="utf-8")))
    kinds, outcomes, mismatches = {}, {}, 0
    for path in sorted((run / "cache").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        kind = path.name.split("-", 1)[0]
        kinds[kind] = kinds.get(kind, 0) + 1
        key = digest({"run": identity, "request": record["request"]})
        if (
            record["key"] != key
            or record["value_sha256"] != digest(record["value"])
            or path.name != f"{kind}-{key}.json"
        ):
            mismatches += 1
        if kind == "llm":
            value = record["value"]
            outcome = value.get("outcome") if isinstance(value, dict) else None
            outcomes[str(outcome)] = outcomes.get(str(outcome), 0) + 1
    print(
        json.dumps(
            {
                "manifest_sha256": identity,
                "cache_records": sum(kinds.values()),
                "records_by_kind": dict(sorted(kinds.items())),
                "llm_outcomes": dict(sorted(outcomes.items())),
                "integrity_mismatches": mismatches,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
