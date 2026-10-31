"""Laptop: archive one clean registering commit to a NEW Mac stand, without shell byte pipes."""

import argparse
import hashlib
import json
import re
import subprocess
import tarfile
import tempfile

from common import ROOT, require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("commit")
    args = parser.parse_args()
    require(re.fullmatch("[0-9a-f]{40}", args.commit), "give a full commit SHA")
    require(
        not subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT
        ),
        "dirty checkout",
    )
    require(
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        == args.commit,
        "registering commit must be HEAD",
    )
    stand = "/Users/julia/RAG_new_chat_" + args.commit[:7]
    # All shell interpolations are fixed literals or the validated hexadecimal commit.
    remote = (
        f"test ! -e {stand} && mkdir {stand} && tar -xf - -C {stand} && "
        f"printf '%s\\n' {args.commit} > {stand}/CODE_SHA && "
        f"ln -s /Users/julia/RAG_new_ask100_20261012_7cad79f/.ask100-runtime {stand}/.ask100-runtime"
    )
    with tempfile.TemporaryFile() as archive:
        subprocess.run(["git", "archive", args.commit], cwd=ROOT, stdout=archive, check=True)
        archive.seek(0)
        # Hash the archive's bytes, not Windows checkout bytes subject to autocrlf.
        with tarfile.open(fileobj=archive) as contents:
            files = {
                m.name: hashlib.sha256(contents.extractfile(m).read()).hexdigest()
                for m in contents.getmembers()
                if m.isfile()
            }
        archive.seek(0)
        subprocess.run(["ssh", "deproject-mac", remote], stdin=archive, check=True)
    manifest = {"code_sha": args.commit, "files": files}
    subprocess.run(
        ["ssh", "deproject-mac", f"cat > {stand}/STAND_FILES.json"],
        input=(json.dumps(manifest) + "\n").encode("utf-8"),
        check=True,
    )
    print(stand)


if __name__ == "__main__":
    main()
