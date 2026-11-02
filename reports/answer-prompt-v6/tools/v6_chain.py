"""Mac-only serial chain on the two original stands; launch no server and retrieve nothing."""

import argparse
import os
import signal
import subprocess
from pathlib import Path

from v6_common import (
    FORECAST,
    HERE,
    KEYS,
    SOURCE_RUNS,
    STANDS,
    final,
    outside,
    require,
    unicode_gate,
    write,
)


def command(key, out, spec, check=False):
    stand = Path("/Users/julia/RAG_new_chat_" + STANDS[key])
    env = {
        "HOME": str(Path.home()),
        "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "V6_PRODUCT_ROOT": str(stand),
        "PYTHONPATH": f"{stand}:{final.SITE}",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "RAG_RERANKER_ONNX": final.ONNX,
    }
    argv = [
        final.PY,
        "-u",
        str(HERE / "v6_replay.py"),
        "check" if check else "run",
        key,
        "--runs",
        SOURCE_RUNS[key],
        "--out",
        str(out / key),
        "--spec",
        str(spec),
    ]
    return stand, env, argv


def interrupted(signum, frame):
    raise SystemExit(128 + signum)


def selected_keys(value):
    keys = value.split(",")
    require(bool(keys) and len(keys) == len(set(keys)) and set(keys) <= set(KEYS), "invalid keys")
    return [key for key in KEYS if key in keys]


def failure_stop(out, key):
    if not (out / "STOP").exists():
        write(out / "STOP", {"key": key, "reason": "key failure or deadline"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument(
        "--check", action="store_true", help="all gates without generation or idle wait"
    )
    parser.add_argument("--keys", default=",".join(KEYS))
    args = parser.parse_args()
    unicode_gate()
    require(os.uname().sysname == "Darwin", "the chain runs on the registered Mac")
    out, spec = outside(args.out), args.spec.resolve()
    require(not out.exists(), "new chain output required; retain previous failures")
    if not args.check:
        out.mkdir(parents=True)
    signal.signal(signal.SIGTERM, interrupted)
    keys = selected_keys(args.keys)
    for key in keys:
        require(not (out / "STOP").exists(), "operator/harm stop")
        stand, env, argv = command(key, out, spec, args.check)
        child = subprocess.Popen(argv, cwd=stand, env=env)
        print("KEY_START", key, "pid", child.pid, "stand", STANDS[key], flush=True)
        try:
            code = child.wait(timeout=3 * FORECAST[key])
            require(code == 0, f"{key} refused; chain stops, retain all files")
        except BaseException:
            if not args.check:
                failure_stop(out, key)
            raise
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=120)  # owned cleanup, not another request
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
        print("KEY_COMPLETE", key, flush=True)
    if not args.check:
        write(out / "CHAIN_COMPLETE", {"keys": keys})


if __name__ == "__main__":
    main()
