"""Extract paired times from the published idle rerun or item 5's private raw run.

No historical timings are inferred from a printed median. Input hashes accompany the
numeric subset; absent or incomplete archives refuse, not a fabricated comparison.
"""

import argparse
from pathlib import Path

from common import MODEL_DIGEST, positive, questions, read, require, sha, write


def times(data, ids, field):
    require(
        [r[field] for r in data] == ids and len(ids) == 30, "baseline order or completeness differs"
    )
    result = []
    for row in data:
        require(
            not row.get("client_error") and not row.get("error_sec"), "baseline question failed"
        )
        require(
            all(positive(row.get(k)) for k in ("first_token_sec", "result_sec", "total_sec")),
            "baseline timing missing",
        )
        require(
            row["first_token_sec"] <= row["result_sec"] <= row["total_sec"], "baseline timing order"
        )
        result.append(
            {
                "case_id": row[field],
                **{k: row[k] for k in ("first_token_sec", "result_sec", "total_sec")},
            }
        )
    return result


def extract(source, path, ids, cases_sha):
    if source == "19beeb1":
        held = read(path)
        require(
            held["schema"] == "chat-live/v1" and held["code_sha"].startswith("19beeb1"),
            "wrong idle record",
        )
        require(held["dataset"]["sha256"] == cases_sha, "baseline question file differs")
        selected = [r for r in held["runs"] if r["label"] == "qwen3-4b-instruct-q30-r2"]
        require(len(selected) == 1, "one idle rerun required")
        run = selected[0]
        require(
            run["status"] == "complete"
            and run["runner_exit"] == 0
            and run["model_digest"] == MODEL_DIGEST,
            "baseline run failed or model differs",
        )
        require(all(r["http"] == 200 for r in run["cases"]), "baseline HTTP failure")
        cases = times(run["cases"], ids, "case")
        hashes = {path.name: sha(path)}
    else:
        require(source == "item5", "unknown baseline")
        launch = read(path / "launch.json")
        require(
            path.name == "s5-30" and launch["code_sha"].startswith("4f48fed"), "wrong item 5 run"
        )
        require(
            launch["status"] == "complete"
            and launch["runner_exit"] == 0
            and launch["model_digest"] == MODEL_DIGEST,
            "item 5 run failed",
        )
        files = sorted((path / "cases").glob("*.json"))
        data = [read(p) for p in files]
        require(
            all(r["http_status"] == 200 and not r.get("drain_error") for r in data),
            "item 5 question failed",
        )
        cases = times(data, ids, "case_id")
        hashes = {str(p.relative_to(path)): sha(p) for p in [path / "launch.json", *files]}
    return {
        "source": source,
        "status": "counted",
        "input_sha256": hashes,
        "cases_sha256": cases_sha,
        "cases": cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=("19beeb1", "item5"))
    parser.add_argument("path", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    require(not args.out.exists(), "baseline export exists")
    path, ids = questions("aircargo", None)
    write(args.out, extract(args.source, args.path, ids[:30], sha(path)))


if __name__ == "__main__":
    main()
