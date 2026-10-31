"""Stage 5's WixQA, ConditionalQA, MultiHop-RAG series through item 6's unchanged batch."""

import argparse
import signal
import sys
import time
from pathlib import Path

from protocol import (
    BASES,
    ROOT,
    SPEC,
    batch_hashes,
    forecast,
    outside,
    product_diff,
    questions,
    read,
    require,
    sha,
    write,
)
from record import answers
from run import batch, code_check, corpus, wait_idle


def run_series(data, out, baseline, source, item6_sha):
    out, data = outside(out), outside(data)
    require(not out.exists(), "new OUT required; quality runs do not resume")
    code = code_check()
    relative = baseline.resolve().relative_to(ROOT.resolve()).as_posix()
    require(
        read(ROOT / "STAND_FILES.json")["files"].get(relative) == sha(baseline),
        "baseline receipt is not in the stand",
    )
    held = read(baseline)
    require(held["item6_sha"] == item6_sha, "item 6 registration differs from baseline")
    change = product_diff(source, item6_sha, code)
    require(
        held["spec"] == SPEC and held["status"] == "counted" and held["order"] == list(BASES),
        "baseline receipt differs",
    )
    for base in BASES:
        cases, ids = questions(base, data)
        old = held["bases"][base]
        require(
            old["ids"] == ids
            and old["cases_sha256"] == sha(cases)
            and old["corpus"] == corpus(base, data),
            "registered questions or corpus differ",
        )
        require(old["forecast"] == forecast(old["times"]["total_sec"]), "forecast receipt differs")
    seconds = sum(held["bases"][b]["forecast"]["series"] for b in BASES)
    deadline = time.monotonic() + 3 * seconds
    out.mkdir(parents=True)
    launch = {
        "status": "running",
        "code_sha": code,
        "baseline_sha256": sha(baseline),
        "forecast_seconds": seconds,
        "order": list(BASES),
        "completed": [],
        "bases": {},
        "product_diff": change,
    }
    write(out / "series.json", launch)
    print("FORECAST", seconds, "seconds; stop", 3 * seconds, flush=True)
    try:
        for base in BASES:
            cases, ids = questions(base, data)
            f = held["bases"][base]["forecast"]
            base_deadline = min(deadline, time.monotonic() + 3 * f["series"])
            try:
                for n in range(10):
                    require(not (out / "STOP").exists(), "operator stop")
                    require(time.monotonic() < base_deadline, "3x series forecast")
                    before = wait_idle(
                        out / f"{base}-b{n + 1:02d}-idle-wait.json", base_deadline, False
                    )
                    require(not (out / "STOP").exists(), "operator stop")
                    require(time.monotonic() < base_deadline, "3x series forecast")
                    batch(
                        out / f"final-answers-{base}-b{n + 1:02d}",
                        base,
                        cases,
                        ids[n * 10 : n * 10 + 10],
                        data,
                        min(base_deadline, time.monotonic() + 3 * f["batch"]),
                        False,
                        before=before,
                    )
                    launch["completed"].append([base, n + 1])
                    write(out / "series.json", launch)
                measured = answers(out, base, data)
                require(measured["provenance"]["code_sha"] == code, "answer stand differs")
                require(code_check() == code, "stand moved")
                require(time.monotonic() < base_deadline, "3x series forecast")
                marker = {
                    "status": "complete",
                    "base": base,
                    "code_sha": code,
                    "baseline_sha256": sha(baseline),
                    "product_diff": change,
                    "batch_sha256": batch_hashes(out, base),
                }
                # Publish only after the base's gate; a laptop can now copy these immutable runs.
                pending = out / f"{base}.complete.tmp"
                write(pending, marker)
                pending.replace(out / f"{base}.complete")
                launch["bases"][base] = {"status": "complete"}
            except (SystemExit, OSError, ValueError, KeyError) as error:
                launch["bases"][base] = {
                    "status": "NOT_EVIDENCE",
                    "error_type": type(error).__name__,
                }
                if isinstance(error, SystemExit) and str(error) == "NOT_EVIDENCE: terminated":
                    raise
                # Path failures are local to this base. Operator/series stops still stop owned work.
                require(not (out / "STOP").exists(), "operator stop")
                require(time.monotonic() < deadline, "3x series forecast")
                require(code_check() == code, "stand moved")
            finally:
                write(out / "series.json", launch)
        require(
            code_check() == code and time.monotonic() < deadline,
            "stand moved or series deadline reached",
        )
        launch["status"] = (
            "complete"
            if all(launch["bases"][b]["status"] == "complete" for b in BASES)
            else "NOT_EVIDENCE"
        )
    except BaseException as error:
        launch.update(status="NOT_EVIDENCE", error_type=type(error).__name__)
        raise
    finally:
        write(out / "series.json", launch)


def series_gate(runs, baseline, measured, base):
    """A completed base stands independently of later failures or a still-running series."""
    path = runs / f"{base}.complete"
    require(path.is_file(), "base completion marker missing")
    held = read(path)
    require(
        held["status"] == "complete"
        and held["base"] == base
        and held["baseline_sha256"] == sha(baseline)
        and measured["provenance"]["code_sha"] == held["code_sha"]
        and held["batch_sha256"] == batch_hashes(runs, base),
        "incomplete stage5 base or changed batch hashes",
    )
    return held


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--item6-sha", required=True)
    args = parser.parse_args()
    run_series(args.data, args.out, args.baseline, args.source, args.item6_sha)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit("NOT_EVIDENCE: terminated"))
    main()
