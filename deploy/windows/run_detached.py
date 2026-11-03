"""Start the release launcher without a console window, logging to service.log."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.windows import _support as support  # noqa: E402


def parser() -> argparse.ArgumentParser:
    result = support.parser(__doc__ or "")
    result.add_argument(
        "--env-file", type=Path, help="Override the launcher's default external env file"
    )
    return result


def launch(paths: support.Paths, env_file: Path | None) -> int:
    if not paths.python.is_file() or not paths.launcher.is_file():
        raise support.DeploymentError(
            "Prepare the product venv and app release clone before starting"
        )
    argv = [str(paths.python), "-I", str(paths.launcher)]
    if env_file is not None:
        argv.append(str(env_file))
    with paths.service_log.open("ab") as log:
        process = support.detach(argv, cwd=paths.app, stdout=log)
    return process.pid


def main() -> int:
    args = parser().parse_args()
    support.require_windows()
    print("launcher pid", launch(support.Paths(args.root), args.env_file))
    return 0


if __name__ == "__main__":
    sys.exit(support.cli(main))
