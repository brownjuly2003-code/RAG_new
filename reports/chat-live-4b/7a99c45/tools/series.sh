#!/bin/sh
# The live series of qwen3:4b-instruct-2507-q4_K_M at the code defaults, 1 -> 5 -> 30 questions (series_plan.json):
# each step a fresh supervisor (API, database, model load timed apart); the next step only
# when the runner delivered every answer within its cap (exit 0). Started by launch_series.py.
CL=/Users/julia/RAG_new_chat_7a99c45/chatlive
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
LOG=$CL/runs/series.log
API=http://127.0.0.1:11434
CAP=1029/900
mkdir -p $CL/runs

free() {  # both ports bind and Ollama holds no model, as live_supervisor.py requires
  $PY -c "import socket
for port in (8002, 55433):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))" 2>/dev/null &&
    [ "$(curl -s $API/api/ps | $PY -c "import json,sys; print(len(json.load(sys.stdin)['models']))")" = 0 ]
}

run() {  # label cases
  i=0
  until free; do i=$((i + 1)); [ $i -gt 36 ] && { echo "$(date -u +%FT%TZ) STOP $1: ports or model not free after 180 s" >> $LOG; exit 1; }; sleep 5; done
  echo "$(date -u +%FT%TZ) START $1" >> $LOG
  { sysctl -n vm.loadavg vm.swapusage; ps -axo pid,pcpu,rss,comm -r | head -6; } >> $LOG
  $PY -u $CL/live_supervisor.py "$1" prod "$2" "$CAP" >> $CL/runs/$1.supervisor.log 2>&1
  code=$?
  echo "$(date -u +%FT%TZ) $(tail -n 1 $CL/runs/$1.supervisor.log)" >> $LOG
  return $code
}

run qwen3-4b-instruct-q1 "aircargo-probation-data" || { echo "$(date -u +%FT%TZ) SERIES_STOP after qwen3-4b-instruct-q1" >> $LOG; exit 1; }
run qwen3-4b-instruct-q5 "aircargo-probation-data,aircargo-probation-extend,aircargo-probation-dismissal,aircargo-dismissal-check,aircargo-dismissal-lawyer" || { echo "$(date -u +%FT%TZ) SERIES_STOP after qwen3-4b-instruct-q5" >> $LOG; exit 1; }
run qwen3-4b-instruct-q30 "aircargo-probation-data,aircargo-probation-extend,aircargo-probation-dismissal,aircargo-dismissal-check,aircargo-dismissal-lawyer,aircargo-dismissal-order,aircargo-leave-sources,aircargo-leave-compensation,aircargo-leave-risk,aircargo-matliab-check,aircargo-matliab-disputed,aircargo-templates-choose,aircargo-templates-checklist,aircargo-templates-insufficient,aircargo-secret-check,aircargo-secret-not-auto,aircargo-secret-disclosure,aircargo-pdp-scope,aircargo-pdp-data,aircargo-pdp-uncertain,aircargo-claims-delay,aircargo-claims-damage,aircargo-claims-lawyer,aircargo-claims-forbidden,aircargo-expedition-vs-carrier,aircargo-expedition-mawb-hawb,aircargo-expedition-risks,aircargo-road-cutoff,aircargo-road-penalty,aircargo-road-seal" || { echo "$(date -u +%FT%TZ) SERIES_STOP after qwen3-4b-instruct-q30" >> $LOG; exit 1; }
echo "$(date -u +%FT%TZ) SERIES_DONE" >> $LOG
