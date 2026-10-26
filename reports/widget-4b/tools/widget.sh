#!/bin/sh
# Stage 3, step 4 (docs/specs/widget-4b.md): the production request, then the ten in
# development, each one widget_supervisor.py run on a fresh API and a byte-identical copy of
# the aircargo index, as stage2.sh runs its batches. A run that stops ends the chain.
# On the stand, from the laptop:
#   S=/Users/julia/RAG_new_chat_4f48fed
#   ssh deproject-mac "nohup sh $S/chatlive/widget.sh > $S/chatlive/runs/widget.out 2>&1 </dev/null &"
set -u
CL=$(cd "$(dirname "$0")" && pwd)
WS=$(dirname "$CL")
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
OLLAMA=http://127.0.0.1:11434
INDEX=/Users/julia/RAG_new_external_s1/aircargo/index/chroma
CASES=$WS/evaluation/curated_cases_aircargo.jsonl
LOG=$CL/runs/widget.log
CAP=4200
PRODUCTION=aircargo-matliab-disputed
TEN=aircargo-probation-data,aircargo-probation-extend,aircargo-probation-dismissal,aircargo-dismissal-check,aircargo-dismissal-lawyer,aircargo-dismissal-order,aircargo-leave-sources,aircargo-leave-compensation,aircargo-leave-risk,aircargo-matliab-check
mkdir -p "$CL/runs"

free() {  # both ports bind and Ollama holds no model, as widget_supervisor.py requires
  $PY -c "import socket
for port in (8002, 55433):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))" 2>/dev/null &&
    [ "$(curl -s $OLLAMA/api/ps | $PY -c "import json,sys; print(len(json.load(sys.stdin)['models']))")" = 0 ]
}

copy() {  # a byte-identical copy of the index beside the runs; its path printed
  rm -rf "$CL/runs/$1.chroma" && cp -Rp "$INDEX" "$CL/runs/$1.chroma" &&
    diff -rq "$INDEX" "$CL/runs/$1.chroma" > /dev/null && echo "$CL/runs/$1.chroma"
}

run() {  # label cases extra: one supervisor run on a fresh copy of the index
  i=0
  until free; do i=$((i + 1)); [ $i -gt 36 ] && { echo "$(date -u +%FT%TZ) STOP $1: ports or model not free after 180 s" >> "$LOG"; return 1; }; sleep 5; done
  index=$(copy "$1") || { echo "$(date -u +%FT%TZ) STOP $1: no copy of the index" >> "$LOG"; return 1; }
  echo "$(date -u +%FT%TZ) START $1" >> "$LOG"
  { sysctl -n vm.loadavg vm.swapusage; ps -axo pid,pcpu,rss,comm -r | head -6; } >> "$LOG"
  $PY -u "$CL/widget_supervisor.py" "$1" prod "$2" "$CAP" "TENANT=aircargo,CHROMA=$index,CASES_FILE=$CASES$3" >> "$CL/runs/$1.supervisor.log" 2>&1
  status=$?
  rm -rf "$index"
  echo "$(date -u +%FT%TZ) $(tail -n 1 "$CL/runs/$1.supervisor.log")" >> "$LOG"
  return $status
}

run widget-production "$PRODUCTION" ",ENV=production" || { echo "$(date -u +%FT%TZ) CHAIN_STOPPED" >> "$LOG"; exit 1; }
run widget-development "$TEN" "" || { echo "$(date -u +%FT%TZ) CHAIN_STOPPED" >> "$LOG"; exit 1; }
echo "$(date -u +%FT%TZ) CHAIN_DONE" >> "$LOG"
