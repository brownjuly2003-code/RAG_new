"""Contract tests for the separate Opus reference judgment."""

from __future__ import annotations

import json

import pytest

from evaluation.blinded_judge import draw_human_sample, load_inputs
from scripts.p2_opus_reference import CLI_ARGS, parse_cli_envelope, select_sample


def test_opus_grades_exactly_the_preselected_human_sample() -> None:
    inputs = load_inputs()
    sample = select_sample(inputs)
    assert len(sample) == 10
    assert [case.case_id for case in sample] == [
        case.case_id
        for case in draw_human_sample(inputs.pools["H"].cases, inputs.pools["H"].ruler_per_case)
    ]
    assert all(case.pool == "H" for case in sample)


def test_cli_envelope_requires_exact_opus_model_and_success() -> None:
    envelope = {
        "is_error": False,
        "terminal_reason": "completed",
        "result": '{"grades":[]}',
        "modelUsage": {
            "claude-opus-5-5": {
                "canonicalModel": "claude-opus-5-5",
                "provider": "firstParty",
            }
        },
        "usage": {"input_tokens": 12},
        "total_cost_usd": 0.5,
    }
    parsed = parse_cli_envelope(json.dumps(envelope))
    assert parsed["result"] == '{"grades":[]}'
    assert parsed["model"] == "claude-opus-5-5"
    assert parsed["usage"]["total_cost_usd"] == 0.5
    for change in (
        {"is_error": True},
        {"modelUsage": {"claude-sonnet-5": {"canonicalModel": "claude-sonnet-5"}}},
        {"result": ""},
    ):
        with pytest.raises(ValueError):
            parse_cli_envelope(json.dumps({**envelope, **change}))


def test_cli_flags_pin_max_effort_without_model_fallback() -> None:
    assert CLI_ARGS[CLI_ARGS.index("--model") + 1] == "claude-opus-5-5"
    assert CLI_ARGS[CLI_ARGS.index("--effort") + 1] == "max"
    assert "--fallback-model" not in CLI_ARGS
    assert CLI_ARGS[CLI_ARGS.index("--tools") + 1] == ""
