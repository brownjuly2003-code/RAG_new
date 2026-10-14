#!/bin/sh
# Screening, second part (docs/specs/small-generator-screening.md, amendment of 2026-10-14):
# the tag qwen3:4b is Qwen3-4B-Thinking-2507, which ignores think=false. Wait for its 5-case
# step (PID 65519, left running when run_screen.sh was stopped) and record it, pull
# Qwen3-4B-Instruct-2507, check its digest, then run it 1 -> 5 -> 100 like the others.
REPO=/Users/julia/genscreen_86df582
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
HERE=/Users/julia/genscreen
OUT=$HERE/results
LOG=$HERE/progress.log
API=http://127.0.0.1:11434
MODEL=qwen3:4b-instruct-2507-q4_K_M
DIGEST=0edcdef34593
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

while kill -0 65519 2>/dev/null; do sleep 10; done
$PY $HERE/check_step.py $OUT/gs-qwen3-4b-n5-phase-c-generator-benchmark.json 5 -1 >> $LOG 2>&1
echo "$(date -u +%FT%TZ) END gs-qwen3-4b (thinking tag: no 100-case step)" >> $LOG

echo "$(date -u +%FT%TZ) PULL $MODEL" >> $LOG
curl -s --max-time 3600 $API/api/pull -d "{\"name\":\"$MODEL\",\"stream\":false}" >> $LOG 2>&1
echo >> $LOG
if ! curl -s $API/api/tags | $PY -c "import json,sys; sys.exit(0 if any(m['name'] == '$MODEL' and m['digest'].startswith('$DIGEST') for m in json.load(sys.stdin)['models']) else 1)"; then
  echo "$(date -u +%FT%TZ) STOP pull: $MODEL with digest $DIGEST... is not held" >> $LOG
  exit 1
fi
caps=$(curl -s $API/api/show -d "{\"name\":\"$MODEL\"}" | $PY -c "import json,sys; print(' '.join(json.load(sys.stdin).get('capabilities', [])))")
think=""
case " $caps " in *" thinking "*) think=--no-think ;; esac
echo "$(date -u +%FT%TZ) capabilities: $caps; think flag: ${think:-none}" >> $LOG

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

for n in 1 5 100; do step $MODEL qwen3-4b-instruct "$think" $n; done
echo "$(date -u +%FT%TZ) ALL_DONE" >> $LOG
