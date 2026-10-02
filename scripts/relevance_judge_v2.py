"""Run the addressed v2 relevance judge; archived P2 v1 runners stay unchanged.

Input JSONL rows contain case_id, question and 1–10 addressed documents in
the evaluation.judge_contract format. Only this explicit CLI makes requests.
Replies and validated grade records share an append-only JSONL store.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluation.blinded_judge import JudgeClient, _append_store, read_store
from evaluation.blinded_judge_clients import (
    GlmClient,
    JudgeUnavailable,
    MistralClient,
    RateLimited,
    SonnetClient,
    TransportError,
)
from evaluation.judge_contract import (
    build_request_v2,
    make_grade_records,
    parse_grades_v2,
    validate_grade_record,
)


def run_judge_v2(
    client: JudgeClient,
    cases: Sequence[Mapping[str, Any]],
    store_path: Path,
    *,
    judge_version: str,
    rubric_version: str = "p2-0-3-v1",
    limit: int | None = None,
) -> dict[str, Any]:
    """Persist each attempt, reuse exact valid replies, and never retry implicitly."""
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    requests = [
        build_request_v2(
            case_id=case["case_id"],
            question=case["question"],
            documents=case["documents"],
            judge_version=judge_version,
            rubric_version=rubric_version,
        )
        for case in cases
    ]
    if len({request.case_id for request in requests}) != len(requests):
        raise ValueError("case ids must be unique")
    cache: dict[str, dict[str, Any]] = {}
    for row in read_store(store_path):
        if row.get("request_version") != 2:
            continue
        for grade in row["records"]:
            validate_grade_record(grade)
        if row.get("status") == "valid":
            cache[row["request_key"]] = row
    result: dict[str, Any] = dict(valid=0, invalid=0, absent=0, reused=0, pending=0)
    started = 0
    for position, request in enumerate(requests):
        labels = [f"D{i}" for i in range(1, len(request.documents) + 1)]
        cached = cache.get(request.request_key)
        if cached and cached.get("request_sha256") == request.request_sha256:
            outcome = parse_grades_v2(cached.get("raw_text"), labels)
            if outcome.status == "valid":
                records = make_grade_records(request, outcome)
                if cached.get("records") != records:
                    rebound = {
                        **cached,
                        "case_id": request.case_id,
                        "records": records,
                        "reused": True,
                    }
                    _append_store(store_path, rebound)
                    cache[request.request_key] = rebound
                result["reused"] += 1
                continue
        if limit is not None and started >= limit:
            result["pending"] += 1
            continue
        started += 1
        record: dict[str, Any] = {
            "case_id": request.case_id,
            "request_version": request.request_version,
            "request_key": request.request_key,
            "request_sha256": request.request_sha256,
            "question_hash": request.question_hash,
            "rubric_version": request.rubric_version,
            "judge_version": request.judge_version,
            "raw_text": None,
        }
        failure = ""
        unavailable = ""
        try:
            reply = client.grade(request.text)
        except JudgeUnavailable as exc:
            failure, unavailable = "judge_unavailable", exc.code
        except RateLimited as exc:
            failure, unavailable = "rate_limit", "rate_limit"
            record["reset_at"] = exc.reset_at
        except TransportError:
            failure = "transport_error"
        else:
            record.update(
                raw_text=reply.text, model=reply.model, usage=reply.usage, elapsed_s=reply.elapsed_s
            )
        outcome = parse_grades_v2(record["raw_text"], labels)
        record.update(
            status=outcome.status,
            reason=failure or outcome.reason,
            records=make_grade_records(request, outcome),
        )
        if unavailable:
            record["unavailable"] = unavailable
        _append_store(store_path, record)
        result[outcome.status] += 1
        if outcome.status == "valid":
            cache[request.request_key] = record
        if unavailable:
            result["unavailable"] = unavailable
            result["pending"] += len(requests) - position - 1
            break
    return result


def _client(args: argparse.Namespace) -> Any:
    if args.judge == "sonnet":
        return SonnetClient(args.gk_base)
    if args.judge == "glm":
        return GlmClient(args.glm_settings)
    return MistralClient(args.mistral_key_file)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--judge", choices=("sonnet", "glm", "mistral"), required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--gk-base", default="http://127.0.0.1:8011")
    parser.add_argument("--glm-settings", type=Path)
    parser.add_argument("--mistral-key-file", type=Path)
    args = parser.parse_args(argv)
    if args.judge == "mistral" and args.mistral_key_file is None:
        parser.error("--mistral-key-file is required for --judge mistral")
    cases = read_store(args.cases)
    if not cases:
        parser.error("cases must be a nonempty JSONL file")
    client = _client(args)
    version_fields = {"judge": args.judge, "route": client.route, "parameters": client.parameters}
    if args.judge == "sonnet":
        version_fields["endpoint_sha256"] = hashlib.sha256(
            args.gk_base.rstrip("/").encode("utf-8")
        ).hexdigest()
    version = json.dumps(
        version_fields,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    result = run_judge_v2(client, cases, args.store, judge_version=version, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False))
    return int(bool(result["invalid"] or result["absent"] or result["pending"]))


if __name__ == "__main__":
    raise SystemExit(main())
