"""Log in using service.json, ask one question, and report attribution and delivery."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.windows import _support as support  # noqa: E402

BASE = "http://127.0.0.1:8002"


def parser() -> argparse.ArgumentParser:
    result = support.parser(__doc__ or "")
    result.add_argument("question")
    result.add_argument("--tenant", default="aircargo")
    return result


def post(
    path: str, body: dict[str, str], token: str | None = None, timeout: int = 60
) -> tuple[int, dict[str, Any]]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(BASE + path, json.dumps(body).encode("utf-8"), headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # Error bodies may echo submitted credentials; never print them.
        error.close()
        return error.code, {}


def ask(paths: support.Paths, question: str, tenant: str) -> int:
    service = json.loads(paths.service_store.read_text(encoding="utf-8"))
    status, body = post(
        "/api/auth/login",
        {"username": service["admin_username"], "password": service["admin_password"]},
    )
    if status != 200:
        print(f"login HTTP {status}", file=sys.stderr)
        return 1
    token = body.get("access_token")
    if not isinstance(token, str) or not token:
        raise support.DeploymentError("Login response has no access token")
    started = time.monotonic()
    status, body = post(
        "/api/ask", {"question": question, "tenant_id": tenant}, token, timeout=3600
    )
    print("seconds:", round(time.monotonic() - started, 1))
    if status != 200:
        print(f"ask HTTP {status}", file=sys.stderr)
        return 1
    for key in (
        "answer_provider",
        "answer_model",
        "route",
        "ticket_id",
        "delivery_state",
        "quality_score",
    ):
        print(f"{key}: {body.get(key)}")
    return 0


def main() -> int:
    args = parser().parse_args()
    return ask(support.Paths(args.root), args.question, args.tenant)


if __name__ == "__main__":
    sys.exit(support.cli(main))
