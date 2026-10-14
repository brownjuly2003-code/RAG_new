#!/bin/sh
# Live web-chat measurement of the small generators that run on the chat path without a code
# change (the API sends Ollama no think field; neither model thinks). Waits for the generator
# screening to end, then per model: the code-default limits on the B1 questions, then the
# floor limits on the CPU for 1 question and, only if it is answered, the 5 B2 questions.
# Second launch: live-s1-qwen25-1p5b-prod is done; the runs after it were refused because the
# next supervisor started while the API before it still held port 8002, so each run now
# waits until both ports bind and Ollama holds no model.
CL=/Users/julia/RAG_new_chat_33d4b42/chatlive-small
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
LOG=$CL/runs/live-small.log
API=http://127.0.0.1:11434
B1="warmup:Какие документы нужны для перевозки опасного груза?,aircargo-probation-data"
B2=aircargo-probation-data,aircargo-probation-extend,aircargo-probation-dismissal,aircargo-dismissal-check,aircargo-dismissal-lawyer
mkdir -p $CL/runs

while pgrep -f /genscreen/run_screen > /dev/null; do sleep 30; done
for name in $(curl -s $API/api/ps | $PY -c "import json,sys; print(' '.join(m['name'] for m in json.load(sys.stdin)['models']))"); do
  echo "$(date -u +%FT%TZ) unload $name (left by the screening)" >> $LOG
  curl -s $API/api/generate -d "{\"model\":\"$name\",\"keep_alive\":0}" > /dev/null
done
sleep 5

free() {  # both ports bind and Ollama holds no model, as live_supervisor.py requires
  $PY -c "import socket
for port in (8002, 55433):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))" 2>/dev/null &&
    [ "$(curl -s $API/api/ps | $PY -c "import json,sys; print(len(json.load(sys.stdin)['models']))")" = 0 ]
}

run() {  # label mode cases cap extra
  i=0
  until free; do i=$((i + 1)); [ $i -gt 36 ] && { echo "$(date -u +%FT%TZ) STOP $1: ports or model not free after 180 s" >> $LOG; exit 1; }; sleep 5; done
  echo "$(date -u +%FT%TZ) START $1" >> $LOG
  { sysctl -n vm.loadavg vm.swapusage; ps -axo pid,pcpu,rss,comm -r | head -6; } >> $LOG
  $PY -u $CL/live_supervisor.py "$@" >> $CL/runs/$1.supervisor.log 2>&1
  code=$?
  echo "$(date -u +%FT%TZ) $(tail -n 1 $CL/runs/$1.supervisor.log)" >> $LOG
  return $code
}

for pair in qwen25-1p5b=qwen2.5:1.5b qwen3-4b-instruct=qwen3:4b-instruct-2507-q4_K_M; do
  tag=${pair%%=*}
  model=${pair#*=}
  [ -d $CL/runs/live-s1-$tag-prod ] || run live-s1-$tag-prod prod "$B1" 600 MODEL=$model
  if run live-s2-$tag-floor1 floor aircargo-probation-data 1800 RAG_DEVICE=cpu,MODEL=$model; then
    run live-s3-$tag-floor floor "$B2" 1800 RAG_DEVICE=cpu,MODEL=$model
  else
    echo "$(date -u +%FT%TZ) SKIP live-s3-$tag-floor: the 1-question step gave no answer" >> $LOG
  fi
done
echo "$(date -u +%FT%TZ) LIVE_SMALL_DONE" >> $LOG
