#!/bin/bash
set -euo pipefail

# shellcheck disable=SC1091
. /tmp/c1b-b8ecc8e-smoke.env

RUN_ID=c1b-qwen3-8b-b8ecc8e
EXPECTED_SHA=b8ecc8efb780d423a267595584ef0927ebb77cc5
EXPECTED_DATASET=3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720
EXPECTED_CONTEXTS=91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10
EXPECTED_MODEL=500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41
REPORT="$RESULTS_DIR/$RUN_ID-phase-c-generator-benchmark.json"
CHECKPOINT="$RESULTS_DIR/$RUN_ID-checkpoint.json"
LOG="$RESULTS_DIR/$RUN_ID.log"

cd "$WORKTREE"
export PYTHONUNBUFFERED=1

HEAD_NOW=$(git rev-parse HEAD)
PORCELAIN=$(git status --porcelain)
DATASET_NOW=$(shasum -a 256 evaluation/curated_cases_aircargo.jsonl | awk '{print $1}')
CONTEXTS_NOW=$(shasum -a 256 .tmp/ab_candidates_phase2_C.json | awk '{print $1}')

echo "WORKTREE=$WORKTREE"
echo "HEAD=$HEAD_NOW"
echo "CLEAN_COUNT=$(git status --porcelain | wc -l | tr -d ' ')"
echo "DATASET_SHA=$DATASET_NOW"
echo "CONTEXTS_SHA=$CONTEXTS_NOW"
echo "RESULTS_DIR=$RESULTS_DIR"

if [ "$HEAD_NOW" != "$EXPECTED_SHA" ]; then
  echo "FAIL unexpected worktree SHA"
  exit 1
fi
if [ -n "$PORCELAIN" ]; then
  echo "FAIL benchmark worktree is dirty"
  printf '%s\n' "$PORCELAIN"
  exit 1
fi
if [ "$DATASET_NOW" != "$EXPECTED_DATASET" ]; then
  echo "FAIL dataset SHA-256"
  exit 1
fi
if [ "$CONTEXTS_NOW" != "$EXPECTED_CONTEXTS" ]; then
  echo "FAIL contexts SHA-256"
  exit 1
fi
if [ -e "$REPORT" ] || [ -e "$CHECKPOINT" ]; then
  echo "FAIL full-run report or checkpoint already exists"
  exit 1
fi

ACTIVE=$(pgrep -af 'python.*generator_benchmark.py.*c1b-qwen3-8b-b8ecc8e([[:space:]]|$)' || true)
if [ -n "$ACTIVE" ]; then
  echo "FAIL full benchmark process already active"
  printf '%s\n' "$ACTIVE"
  exit 1
fi

"$PY" - "$EXPECTED_MODEL" <<'PY'
import json
import sys
import urllib.request

expected = sys.argv[1]
with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=30) as response:
    payload = json.load(response)
matches = [
    item
    for item in payload.get("models") or []
    if str(item.get("name") or item.get("model") or "") == "qwen3:8b"
]
if len(matches) != 1:
    raise SystemExit(f"FAIL expected one qwen3:8b tag, found {len(matches)}")
item = matches[0]
digest = str(item.get("digest") or "").removeprefix("sha256:")
quant = str((item.get("details") or {}).get("quantization_level") or "")
print("MODEL_NAME", item.get("name"))
print("MODEL_DIGEST", digest)
print("MODEL_QUANT", quant)
print("MODEL_SIZE", item.get("size"))
if digest != expected:
    raise SystemExit("FAIL model digest")
if quant != "Q4_K_M":
    raise SystemExit("FAIL model quantization")
print("MODEL_OK")
PY

echo FULL_PREFLIGHT_OK
START=$(date +%s)
set +e
"$PY" scripts/generator_benchmark.py \
  --dataset evaluation/curated_cases_aircargo.jsonl \
  --contexts .tmp/ab_candidates_phase2_C.json \
  --results-dir "$RESULTS_DIR" \
  --run-id "$RUN_ID" \
  --model qwen3:8b \
  --runs 3 \
  --expected-cases 100 \
  --context-chars 6000 \
  --seed-base 42 \
  --temperature 0 \
  --num-ctx 4096 \
  --num-predict 384 \
  --nli-batch-size 4 \
  --no-think 2>&1 | tee "$LOG"
BENCH_EXIT=${PIPESTATUS[0]}
set -e
END=$(date +%s)
echo "BENCH_EXIT=$BENCH_EXIT"
echo "DURATION_SEC=$((END-START))"
if [ "$BENCH_EXIT" -ne 0 ]; then
  echo FULL_BENCHMARK_FAILED
  exit "$BENCH_EXIT"
fi

"$PY" - "$REPORT" "$EXPECTED_SHA" "$EXPECTED_DATASET" "$EXPECTED_CONTEXTS" "$EXPECTED_MODEL" <<'PY'
import hashlib
import json
import sys

path, expected_code, expected_dataset, expected_contexts, expected_model = sys.argv[1:]
with open(path, encoding="utf-8") as handle:
    report = json.load(handle)

provenance = report.get("provenance") or {}
config = provenance.get("config") or {}
runs = report.get("runs") or []
errors = []

def require(condition, message):
    if not condition:
        errors.append(message)

require(report.get("evidence_class") == "measured", f"evidence_class={report.get('evidence_class')}")
require(not (report.get("evidence_reasons") or []), f"evidence_reasons={report.get('evidence_reasons')}")
require(str(provenance.get("code_sha") or "") == expected_code, f"code_sha={provenance.get('code_sha')}")
require(provenance.get("code_tree_clean") is True, f"code_tree_clean={provenance.get('code_tree_clean')}")
require(str(provenance.get("dataset_sha256") or "") == expected_dataset, "dataset_sha256 mismatch")
require(str(provenance.get("contexts_sha256") or "") == expected_contexts, "contexts_sha256 mismatch")
model_digest = str(provenance.get("ollama_model_digest") or "").removeprefix("sha256:")
require(model_digest == expected_model, f"model_digest={model_digest}")
require(provenance.get("ollama_think") is False, f"ollama_think={provenance.get('ollama_think')}")
require(config.get("think") is False, f"config.think={config.get('think')}")
require(config.get("runs") == 3, f"config.runs={config.get('runs')}")
require(config.get("expected_cases") == 100, f"config.expected_cases={config.get('expected_cases')}")
require(config.get("selected_cases") == 100, f"config.selected_cases={config.get('selected_cases')}")
require(config.get("context_chars") == 6000, f"config.context_chars={config.get('context_chars')}")
require(config.get("seed_base") == 42, f"config.seed_base={config.get('seed_base')}")
require(config.get("temperature") == 0, f"config.temperature={config.get('temperature')}")
require(config.get("num_ctx") == 4096, f"config.num_ctx={config.get('num_ctx')}")
require(config.get("num_predict") == 384, f"config.num_predict={config.get('num_predict')}")
require(config.get("nli_batch_size") == 4, f"config.nli_batch_size={config.get('nli_batch_size')}")
require(len(runs) == 3, f"run_count={len(runs)}")

reference_ids = None
total_cases = 0
for expected_index, run in enumerate(runs, 1):
    rows = run.get("cases") or []
    case_ids = [str(row.get("case_id") or "") for row in rows]
    total_cases += len(rows)
    require(run.get("run_index") == expected_index, f"run_index={run.get('run_index')}")
    require(run.get("seed") == 41 + expected_index, f"run {expected_index} seed={run.get('seed')}")
    require(run.get("num_cases") == 100, f"run {expected_index} num_cases={run.get('num_cases')}")
    require(run.get("failed_cases") == 0, f"run {expected_index} failed_cases={run.get('failed_cases')}")
    require(len(rows) == 100, f"run {expected_index} row_count={len(rows)}")
    require(len(case_ids) == len(set(case_ids)), f"run {expected_index} duplicate case ids")
    if reference_ids is None:
        reference_ids = case_ids
    else:
        require(case_ids == reference_ids, f"run {expected_index} case ordering differs")
    for row in rows:
        case_id = row.get("case_id")
        require(row.get("generation_valid") is True, f"{case_id} generation_valid={row.get('generation_valid')}")
        require(row.get("llm_judge_valid") is True, f"{case_id} llm_judge_valid={row.get('llm_judge_valid')}")
        require(row.get("nli_valid") is True, f"{case_id} nli_valid={row.get('nli_valid')}")
        require(not str(row.get("error") or ""), f"{case_id} error={row.get('error')}")

require(total_cases == 300, f"total_cases={total_cases}")
print("EVIDENCE_CLASS", report.get("evidence_class"))
print("RUN_COUNT", len(runs))
print("TOTAL_CASES", total_cases)
print("MODEL_DIGEST", model_digest)
print("OLLAMA_THINK", provenance.get("ollama_think"))
print("CONFIG_THINK", config.get("think"))
print("AGGREGATE", json.dumps(report.get("aggregate") or {}, sort_keys=True))
with open(path, "rb") as handle:
    print("REPORT_SHA256", hashlib.sha256(handle.read()).hexdigest())
if errors:
    print("FULL_VALIDATION_FAIL")
    for item in errors[:40]:
        print("FAIL", item)
    if len(errors) > 40:
        print("FAIL", len(errors) - 40, "additional validation errors")
    raise SystemExit(1)
print("FULL_VALIDATION_OK")
PY

echo DONE
