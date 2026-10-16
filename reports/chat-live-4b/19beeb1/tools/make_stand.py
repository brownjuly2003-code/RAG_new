"""Build the tools of the second Qwen3-4B-Instruct live chat stand (ROADMAP, thread M, step 4).

Source: the tools of the first 4B stand (reports/chat-live-4b/7a99c45/tools, da134d4).
Its series (2026-10-16, 20:12-21:12 UTC) did not measure the 4B alone: the stand's env.json,
the ask100 runtime's deployment environment, pins OLLAMA_MODEL_NAME=qwen2.5:7b; series.sh
passed no MODEL=, so the supervisor left it, and the stream's suggested questions, which read
that setting until 19beeb1, loaded the 7B beside the 4B at the end of every answer. Its
thirty-question step then stopped at question 2 on a 503 the web chat would not have met:
the runner sent every question a new session id of its own, and a 2-s database timeout under
swap had put the tenant's session store in its 60-s cooldown, in which the API refuses an
unverified caller-supplied id.
Changes:
- live_supervisor.py: with the default model, the model choice env.json makes is dropped
  (OLLAMA_MODEL_NAME, OLLAMA_FAST_MODEL_NAME, MODEL_ROUTING_ENABLED, LLM_PROVIDER_PROFILE,
  PROVIDER_REGISTRY_PATH), so the code defaults choose it, as the docstring always said;
- live_runner.py: each question goes as the web chat sends a new conversation's first
  question (static/chat.inline.js), with no session_id - the server makes one;
- export.sh, watch.sh, series.sh: the new stand's paths; series_plan.json names every
  question and its forecast before the first launch, from the first 4B stand's times.
Output: the record's tools folder (argv[1]); argv[2] the code SHA.
"""

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("D:/RAG_new")
BASE = REPO / "reports/chat-live-4b/7a99c45/tools"
OUT = Path(sys.argv[1])
CODE_SHA = sys.argv[2]
OLD_STAND = "/Users/julia/RAG_new_chat_7a99c45"
STAND = f"/Users/julia/RAG_new_chat_{CODE_SHA[:7]}"
FORECAST = {"first_question_of_a_fresh_api": 340, "other_questions": 400}


def patch(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, old
    return text.replace(old, new)


def write(name: str, text: str) -> None:
    (OUT / name).write_text(text, encoding="utf-8", newline="\n")


OUT.mkdir(parents=True, exist_ok=False)
for name in ("analyze.py", "check_export.py", "defaults_diff.py", "export.py",
             "index_digest.py", "launch.py", "live_api.py", "launch_series.py"):
    shutil.copyfile(BASE / name, OUT / name)
shutil.copyfile(Path(__file__), OUT / "make_stand.py")

sup = (BASE / "live_supervisor.py").read_text(encoding="utf-8")
sup = patch(
    sup,
    "               code defaults since step 4: without MODEL= nothing is overridden.\n",
    "               code defaults since step 4: without MODEL= the model choice env.json\n"
    "               makes (MODEL_CHOICE) is dropped and the code defaults choose it.\n",
)
sup = patch(
    sup,
    'DEFAULT_MODEL = "qwen3:4b-instruct-2507-q4_K_M"\n',
    'DEFAULT_MODEL = "qwen3:4b-instruct-2507-q4_K_M"\n'
    "# What chooses the model; env.json (the ask100 deployment) pins qwen2.5:7b.\n"
    'MODEL_CHOICE = ("OLLAMA_MODEL_NAME", "OLLAMA_FAST_MODEL_NAME", "MODEL_ROUTING_ENABLED",\n'
    '                "LLM_PROVIDER_PROFILE", "PROVIDER_REGISTRY_PATH")\n',
)
sup = patch(
    sup,
    "        if model != DEFAULT_MODEL:\n"
    '            env.update({"OLLAMA_MODEL_NAME": model,\n',
    "        for name in MODEL_CHOICE:\n"
    "            env.pop(name, None)\n"
    "        if model != DEFAULT_MODEL:\n"
    '            env.update({"OLLAMA_MODEL_NAME": model,\n',
)
write("live_supervisor.py", sup)

runner = (BASE / "live_runner.py").read_text(encoding="utf-8")
runner = patch(runner, "import uuid\n", "")
runner = patch(
    runner,
    '    payload = {"question": question, "session_id": str(uuid.uuid4()), "tenant_id": "aircargo"}\n',
    "    # A new conversation's first question, as the web chat sends it: no session_id.\n"
    '    payload = {"question": question, "tenant_id": "aircargo"}\n',
)
assert "uuid" not in runner
write("live_runner.py", runner)

for name in ("export.sh", "watch.sh"):
    text = (BASE / name).read_text(encoding="utf-8").replace(OLD_STAND, STAND)
    assert "7a99c45" not in text, name
    write(name, text)

old_plan = json.loads((BASE / "series_plan.json").read_text(encoding="utf-8"))
first, rest = FORECAST["first_question_of_a_fresh_api"], FORECAST["other_questions"]
plan = {
    "named": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "model": old_plan["model"],
    "code_sha": CODE_SHA,
    "mode": "prod",
    "served_by": "the code defaults: series.sh passes no MODEL=, and the supervisor drops the "
                 "model choice of env.json (OLLAMA_MODEL_NAME, OLLAMA_FAST_MODEL_NAME, "
                 "MODEL_ROUTING_ENABLED, LLM_PROVIDER_PROFILE, PROVIDER_REGISTRY_PATH)",
    "client": "each question as a new conversation's first question of the web chat: "
              "question and tenant, no session_id",
    "forecast_sec": FORECAST,
    "forecast_basis": (
        "the first 4B stand on 2026-10-16 (code 7a99c45; its series is not published: the 7B "
        "wrote every answer's suggested questions). The 4B's own part of each question, to "
        "the end of the self-evaluation: the first question of a fresh API 314, 347 and "
        "268 s, median 314; the four others 440, 368, 356 and 389 s, median 379 s. Plus "
        "about 25 s for the suggested questions written by the 4B (a short prompt, about 60 "
        "tokens at the 4.8 tokens/s the 4B wrote its answers): 340 s for the first question "
        "of each step, 400 s for every other, questions 6-30 included"
    ),
    "stop_rule": old_plan["stop_rule"],
    "client_cap_sec": f"{3 * first}/{3 * rest}",
    "cases_source": old_plan["cases_source"],
    "recorded_per_question": old_plan["recorded_per_question"],
    "steps": old_plan["steps"],
}
write("series_plan.json", json.dumps(plan, indent=2, ensure_ascii=False) + "\n")

series = (BASE / "series.sh").read_text(encoding="utf-8").replace(OLD_STAND, STAND)
series = patch(series, f"CAP={old_plan['client_cap_sec']}\n", f"CAP={plan['client_cap_sec']}\n")
assert "7a99c45" not in series and "MODEL=" not in series
write("series.sh", series)
print("built", OUT, "cap", plan["client_cap_sec"])
