#!/bin/sh
# The stage-1 live audit (PLAN.md stage 1, items 1 and 3): one question per tenant through
# /api/ask/stream, each tenant on a fresh supervisor (API, database, model load timed apart),
# so an external tenant's index is read from disk by an API that never ingested it.
# Usage: audit.sh PREFIX ROOT [AIRCARGO_CHROMA [ONLY]]
#   PREFIX - the run labels' prefix, e.g. before or after;
#   ROOT   - the directory of the external bases' generation: the database in
#            <ROOT>/<base>/index/chroma (scripts/production_index.py --output <base>/index),
#            the questions in <ROOT>/<base>/cases.jsonl;
#   AIRCARGO_CHROMA - aircargo's index directory; empty: env.json's (the ask100 runtime);
#   ONLY   - the bases to run, space-separated (default all four).
# The questions: the first of each base's open selection in the registered order
# (evaluation/external_parts.json): aircargo the first case of the live series,
# ConditionalQA and WixQA the first of the pilot selection, MultiHop-RAG the first of the
# advisory part. Forecast 340 s each, the first question of a fresh API; cap 3x (Julia's
# stop rule, 2026-10-15). A step that fails does not stop the others: each tenant is a
# finding of its own.
# Each tenant reads a copy of its index directory, made just before its step: the API
# writes into the database it opens (the default tenant's collection at startup), and the
# generations stay as their receipts describe them. The copy is byte-identical at the start.
set -u
CL=$(cd "$(dirname "$0")" && pwd)
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
PREFIX=$1
ROOT=$2
AIRCARGO_CHROMA=${3:-}
ONLY=" ${4:-aircargo conditionalqa wixqa multihoprag} "
LOG=$CL/runs/$PREFIX-audit.log
API=http://127.0.0.1:11434
CAP=1020
mkdir -p "$CL/runs"

free() {  # both ports bind and Ollama holds no model, as live_supervisor.py requires
  $PY -c "import socket
for port in (8002, 55433):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))" 2>/dev/null &&
    [ "$(curl -s $API/api/ps | $PY -c "import json,sys; print(len(json.load(sys.stdin)['models']))")" = 0 ]
}

run() {  # label case extra
  i=0
  until free; do i=$((i + 1)); [ $i -gt 36 ] && { echo "$(date -u +%FT%TZ) STOP $1: ports or model not free after 180 s" >> "$LOG"; exit 1; }; sleep 5; done
  echo "$(date -u +%FT%TZ) START $1" >> "$LOG"
  { sysctl -n vm.loadavg vm.swapusage; ps -axo pid,pcpu,rss,comm -r | head -6; } >> "$LOG"
  $PY -u "$CL/live_supervisor.py" "$1" prod "$2" "$CAP" "$3" >> "$CL/runs/$1.supervisor.log" 2>&1
  echo "$(date -u +%FT%TZ) $(tail -n 1 "$CL/runs/$1.supervisor.log")" >> "$LOG"
}

copy() {  # source label: a copy of an index directory beside the runs, its path printed
  rm -rf "$CL/runs/$2.chroma" && cp -Rp "$1" "$CL/runs/$2.chroma" &&
    diff -rq "$1" "$CL/runs/$2.chroma" > /dev/null && echo "$CL/runs/$2.chroma"
}

if [ "${ONLY#* aircargo }" = "$ONLY" ]; then
  :
elif [ -n "$AIRCARGO_CHROMA" ]; then
  run "$PREFIX-aircargo" aircargo-probation-data "TENANT=aircargo,CHROMA=$(copy "$AIRCARGO_CHROMA" "$PREFIX-aircargo")"
else
  run "$PREFIX-aircargo" aircargo-probation-data "TENANT=aircargo"
fi
for pair in conditionalqa:conditionalqa-train-1484 wixqa:wixqa-simulated-074 multihoprag:multihoprag-0448; do
  base=${pair%%:*}
  [ "${ONLY#* $base }" = "$ONLY" ] && continue
  index=$(copy "$ROOT/$base/index/chroma" "$PREFIX-$base") || { echo "$(date -u +%FT%TZ) STOP $base: no copy of its index" >> "$LOG"; continue; }
  run "$PREFIX-$base" "${pair#*:}" "TENANT=ext_$base,CHROMA=$index,CASES_FILE=$ROOT/$base/cases.jsonl"
done
echo "$(date -u +%FT%TZ) AUDIT_DONE" >> "$LOG"
