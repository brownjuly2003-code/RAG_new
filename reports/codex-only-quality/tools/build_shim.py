"""Build the native capture shim; the receipt binds this exact, non-reproducible exe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import NoReturn

SOURCE = Path(__file__).resolve().parent / "shim/CaptureShim.cs"
CSC = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build(out: Path, csc: Path = CSC) -> dict[str, str]:
    if sys.platform != "win32":
        raise ValueError("building the capture shim requires Windows")
    if out.suffix.lower() != ".exe":
        raise ValueError("--out must name an .exe")
    if not csc.is_file():
        raise ValueError("the .NET Framework C# compiler is missing")
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    source_hash = sha256(SOURCE)
    # An exclusive sibling file keeps compiler output on the destination volume.
    # Avoid a second directory ACL boundary inside a restricted Windows workspace.
    built = out.with_name("." + out.stem + "." + uuid.uuid4().hex + ".exe")
    with built.open("xb"):
        pass
    try:
        result = subprocess.run(
            [
                str(csc),
                "/nologo",
                "/noconfig",
                "/nostdlib+",
                "/langversion:5",
                "/target:exe",
                "/optimize+",
                "/warnaserror+",
                *(
                    f"/reference:{CSC.parent / assembly}"
                    for assembly in (
                        "mscorlib.dll",
                        "System.dll",
                        "System.Core.dll",
                        "System.Web.Extensions.dll",
                    )
                ),
                f"/out:{built}",
                str(SOURCE),
            ],
            capture_output=True,
            check=False,
            timeout=60,
        )
        if result.returncode or not built.is_file():
            raise ValueError(
                "C# compilation failed: " + result.stdout.decode(errors="replace").strip()
            )
        if sha256(SOURCE) != source_hash:
            raise ValueError("source changed during compilation")
        os.replace(built, out)
    finally:
        built.unlink(missing_ok=True)
    return {"source_sha256": source_hash, "exe_sha256": sha256(out)}


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError(message)


def main(argv: list[str] | None = None) -> int:
    try:
        parser = Parser(description=__doc__)
        parser.add_argument("--out", type=Path, required=True)
        parser.add_argument("--csc", type=Path, default=CSC)
        args = parser.parse_args(argv)
        print(json.dumps(build(args.out, args.csc), sort_keys=True))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(" ".join(str(error).splitlines()), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
