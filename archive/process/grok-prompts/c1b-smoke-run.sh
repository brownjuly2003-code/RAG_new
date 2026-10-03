#!/bin/bash
set -euo pipefail

# shellcheck disable=SC1091
. /tmp/c1b-b8ecc8e-smoke.env

cd "$WORKTREE"
export PYTHONUNBUFFERED=1

echo "WORKTREE=$WORKTREE"
echo "HEAD=$(git rev-parse HEAD)"
echo "CLEAN=$(git status --porcelain | wc -l | tr -d ' ')"
echo "RESULTS_DIR=$RESULTS_DIR"

START=$(date +%s)
set +e
"$PY" scripts/generator_benchmark.py \
  --dataset evaluation/curated_cases_aircargo.jsonl \
  --contexts .tmp/ab_candidates_phase2_C.json \
  --results-dir "$RESULTS_DIR" \
  --run-id c1b-qwen3-8b-b8ecc8e-smoke \
  --model qwen3:8b \
  --runs 1 \
  --max-cases 1 \
  --context-chars 6000 \
  --seed-base 42 \
  --temperature 0 \
  --num-ctx 4096 \
  --num-predict 384 \
  --nli-batch-size 4 \
  --no-think
BENCH_EXIT=$?
set -e
END=$(date +%s)
echo "BENCH_EXIT=$BENCH_EXIT"
echo "DURATION_SEC=$((END-START))"
echo DONE

REPORT="$RESULTS_DIR/c1b-qwen3-8b-b8ecc8e-smoke-phase-c-generator-benchmark.json"
"$PY" - "$REPORT" "$BENCH_EXIT" <<'PY'
import json
import sys

path = sys.argv[1]
bench_exit = int(sys.argv[2])
expected_code = "b8ecc8efb780d423a267595584ef0927ebb77cc5"
expected_ds = "3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720"
expected_ctx = "91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10"
expected_model = "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"

with open(path, encoding="utf-8") as fh:
    report = json.load(fh)

prov = report.get("provenance") or {}
cfg = prov.get("config") or {}
runs = report.get("runs") or []
cases = runs[0].get("cases") if runs else []
row = cases[0] if cases else {}
nli = row.get("nli") or {}
errors = []

if report.get("evidence_class") != "not_evidence":
    errors.append("evidence_class=" + str(report.get("evidence_class")))
if str(prov.get("code_sha") or "") != expected_code:
    errors.append("code_sha=" + str(prov.get("code_sha")))
if prov.get("code_tree_clean") is not True:
    errors.append("code_tree_clean=" + str(prov.get("code_tree_clean")))
if str(prov.get("dataset_sha256") or "") != expected_ds:
    errors.append("dataset_sha256=" + str(prov.get("dataset_sha256")))
if str(prov.get("contexts_sha256") or "") != expected_ctx:
    errors.append("contexts_sha256=" + str(prov.get("contexts_sha256")))
digest = str(prov.get("ollama_model_digest") or "").removeprefix("sha256:")
if digest != expected_model:
    errors.append("model_digest=" + digest)
if prov.get("ollama_think") is not False:
    errors.append("ollama_think=" + str(prov.get("ollama_think")))
if cfg.get("think") is not False:
    errors.append("config.think=" + str(cfg.get("think")))
if len(runs) != 1:
    errors.append("run_count=" + str(len(runs)))
if len(cases) != 1:
    errors.append("case_count=" + str(len(cases)))
if row.get("generation_valid") is not True:
    errors.append("generation_valid=" + str(row.get("generation_valid")))
if row.get("llm_judge_valid") is not True:
    errors.append("llm_judge_valid=" + str(row.get("llm_judge_valid")))
if row.get("nli_valid") is not True:
    errors.append("nli_valid=" + str(row.get("nli_valid")))
if row.get("error"):
    errors.append("error=" + str(row.get("error")))
if int(runs[0].get("failed_cases") or 0) != 0:
    errors.append("failed_cases=" + str(runs[0].get("failed_cases")))
if not nli:
    errors.append("missing nli output")
if bench_exit not in (0, 1):
    errors.append("unexpected bench_exit=" + str(bench_exit))
if bench_exit == 0:
    errors.append("bench_exit=0 but smoke must remain not_evidence")

print("EVIDENCE_CLASS", report.get("evidence_class"))
print("CODE_SHA", prov.get("code_sha"))
print("CODE_TREE_CLEAN", prov.get("code_tree_clean"))
print("DATASET_SHA", prov.get("dataset_sha256"))
print("CONTEXTS_SHA", prov.get("contexts_sha256"))
print("MODEL_DIGEST", digest)
print("OLLAMA_THINK", prov.get("ollama_think"))
print("CONFIG_THINK", cfg.get("think"))
print("GENERATION_VALID", row.get("generation_valid"))
print("LLM_JUDGE_VALID", row.get("llm_judge_valid"))
print("NLI_VALID", row.get("nli_valid"))
print("FAILED_CASES", runs[0].get("failed_cases") if runs else None)
print("ERROR", repr(row.get("error")))
print("NLI_KEYS", sorted(nli.keys()) if isinstance(nli, dict) else type(nli).__name__)
if errors:
    print("SMOKE_FAIL")
    for item in errors:
        print("FAIL", item)
    raise SystemExit(1)
print("SMOKE_OK")
PY
