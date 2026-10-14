#!/bin/sh
# Screening of generators below 7B (docs/specs/small-generator-screening.md), order of the plan:
# per model 1 -> 5 -> 100 cases, smallest model first; a step that fails stops everything.
REPO=/Users/julia/genscreen_86df582
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
HERE=/Users/julia/genscreen
OUT=$HERE/results
LOG=$HERE/progress.log
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

step() {  # model label think-flag cases
  id="gs-$2-n$4"
  max=$4
  [ "$4" = 100 ] && max=0
  echo "$(date -u +%FT%TZ) START $id" >> $LOG
  $PY -u $REPO/scripts/generator_benchmark.py --model "$1" --runs 1 --required-runs 1 \
    --no-llm-judge --max-cases $max $3 --run-id $id --results-dir $OUT > $OUT/$id.log 2>&1
  code=$?
  if ! $PY $HERE/check_step.py $OUT/$id-phase-c-generator-benchmark.json "$4" $code >> $LOG 2>&1; then
    echo "$(date -u +%FT%TZ) STOP $id" >> $LOG
    exit 1
  fi
}

step qwen2.5:1.5b qwen25-1p5b "" 5
step qwen2.5:1.5b qwen25-1p5b "" 100
for n in 1 5 100; do step qwen3:1.7b qwen3-1p7b --no-think $n; done
for n in 1 5 100; do step qwen3:4b qwen3-4b --no-think $n; done
echo "$(date -u +%FT%TZ) ALL_DONE" >> $LOG
