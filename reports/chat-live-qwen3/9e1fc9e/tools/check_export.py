"""Scan an exported record for secret-like strings before it leaves the Mac.

Usage: check_export.py RECORD_JSON
Prints the JSON path, the pattern and the length of every matching string, never the
string itself, so the output can be read anywhere; expected hits are the code, dataset,
model and index digests.
"""

import json
import re
import sys

PATTERNS = {
    "url credentials": r"://[^/<@\s]+@",
    "assignment": r"(?i)(passw\w*|secret\w*|api[_-]?key\w*|token)\s*[=:]\s*(?!<)[^\s,}]{6,}",
    "long hex": r"\b[0-9a-f]{32,}\b",
    "bearer": r"(?i)bearer\s+[a-z0-9._-]{10,}",
    "key prefix": r"\b(sk|pk|ghp|gho|xox[bp])[-_][A-Za-z0-9]{10,}",
    "base64 blob": r"[A-Za-z0-9+/]{40,}={0,2}",
}


def walk(value, path):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk(item, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def main():
    data = json.loads(open(sys.argv[1], encoding="utf-8").read())
    hits = 0
    seen = {}
    for path, text in walk(data, "$"):
        for name, pattern in PATTERNS.items():
            if re.search(pattern, text):
                hits += 1
                key = (name, re.sub(r"\[\d+\]", "[]", path))
                seen[key] = seen.get(key, 0) + 1
    for (name, path), count in sorted(seen.items()):
        print(f"{name}: {path} x{count}")
    masked = {"<set>", "<empty>", None}
    secrets = {}
    for group in ("runs", "retrieval_runs"):
        for item in data.get(group, []):
            for name, pair in item["settings_off_default"].items():
                if re.search(r"(?i)key|secret|token|passw", name):
                    secrets[item["label"] + "." + name] = [
                        value if value in masked else "<UNMASKED>" for value in pair.values()]
    print("secret-like settings:", json.dumps(secrets))
    print("hits:", hits)


if __name__ == "__main__":
    main()
