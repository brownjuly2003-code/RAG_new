#!/bin/sh
# Stage 2 of PLAN.md on one stand: the chat's answers in batches of ten, or retrieval alone.
# Usage: stage2.sh MODE PART KEY ROOT [FROM [TO]]
#   MODE answers   - each batch of ten is one live_supervisor.py run: a fresh API and
#                    database, the model loaded (timed apart) and unloaded after it, every
#                    question sent as a visitor's first; caps 1020/1200 s - 3x the forecasts
#                    of 340 s for a batch's first question and 400 s for the others;
#        retrieval - one live_supervisor.py run in mode retrieval (live_retrieval.py, the
#                    placement cpu): no model, no API, no database;
#   PART - the label prefix of the part, e.g. p1 (aircargo's answers), p2 (retrieval),
#          p4 (the external bases' answers); a rerun of a batch adds SUFFIX, e.g. SUFFIX=-r2;
#   KEY  - aircargo, aircargo-gr (retrieval only), conditionalqa, wixqa or multihoprag;
#   ROOT - the index generation: the database in ROOT/<base>/index/chroma, an external
#          base's questions in ROOT/<base>/cases.jsonl;
#   FROM, TO - the batches to run (answers) or the questions (retrieval), 1-based, inclusive;
#          default all.
# The questions and their order: stage2_cases.py KEY (the registered order). Each run reads
# a fresh copy of its index, made just before it and removed after it: the API writes into
# the database it opens, and the generation stays as its receipt describes it.
# A batch or a run that does not complete stops the driver (the session reads it first);
# so does a path break that the check after it finds (answers_summary.py check, or
# retrieval_summary.py check: stage 1's path test), the stop file runs/PART-KEY.stop, or the
# cap PART_CAP_SEC of this invocation (default 3x the forecast of the batches it runs), both
# read between batches. The log: runs/PART-KEY.log.
set -u
CL=$(cd "$(dirname "$0")" && pwd)
WS=$(dirname "$CL")
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
MODE=$1
PART=$2
KEY=$3
ROOT=$4
SUFFIX=${SUFFIX:-}
OLLAMA=http://127.0.0.1:11434
case $KEY in
  aircargo) BASE=aircargo; CASES=$WS/evaluation/curated_cases_aircargo.jsonl ;;
  aircargo-gr) BASE=aircargo; CASES=$WS/evaluation/curated_cases_aircargo_gr_multihop.jsonl ;;
  conditionalqa|wixqa|multihoprag) BASE=$KEY; CASES=$ROOT/$KEY/cases.jsonl ;;
  *) echo "unknown key $KEY"; exit 2 ;;
esac
TENANT=aircargo
[ "$BASE" = aircargo ] || TENANT=ext_$BASE
mkdir -p "$CL/runs"
LOG=$CL/runs/$PART-$KEY.log
STOP=$CL/runs/$PART-$KEY.stop
IDS=$($PY "$CL/stage2_cases.py" "$KEY" "$CASES") || { echo "$(date -u +%FT%TZ) STOP no case list" >> "$LOG"; exit 1; }
N=$(echo "$IDS" | wc -l | tr -d ' ')

free() {  # both ports bind and Ollama holds no model, as live_supervisor.py requires
  $PY -c "import socket
for port in (8002, 55433):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))" 2>/dev/null &&
    [ "$(curl -s $OLLAMA/api/ps | $PY -c "import json,sys; print(len(json.load(sys.stdin)['models']))")" = 0 ]
}

copy() {  # a byte-identical copy of the index beside the runs; its path printed
  rm -rf "$CL/runs/$1.chroma" && cp -Rp "$ROOT/$BASE/index/chroma" "$CL/runs/$1.chroma" &&
    diff -rq "$ROOT/$BASE/index/chroma" "$CL/runs/$1.chroma" > /dev/null && echo "$CL/runs/$1.chroma"
}

run() {  # label mode cases cap: one supervisor run on a fresh copy of the index
  i=0
  until free; do i=$((i + 1)); [ $i -gt 36 ] && { echo "$(date -u +%FT%TZ) STOP $1: ports or model not free after 180 s" >> "$LOG"; return 1; }; sleep 5; done
  index=$(copy "$1") || { echo "$(date -u +%FT%TZ) STOP $1: no copy of the index" >> "$LOG"; return 1; }
  echo "$(date -u +%FT%TZ) START $1" >> "$LOG"
  { sysctl -n vm.loadavg vm.swapusage; ps -axo pid,pcpu,rss,comm -r | head -6; } >> "$LOG"
  LIVE_VARIANTS=cpu $PY -u "$CL/live_supervisor.py" "$1" "$2" "$3" "$4" "TENANT=$TENANT,CHROMA=$index,CASES_FILE=$CASES" >> "$CL/runs/$1.supervisor.log" 2>&1
  status=$?
  rm -rf "$index"
  echo "$(date -u +%FT%TZ) $(tail -n 1 "$CL/runs/$1.supervisor.log")" >> "$LOG"
  return $status
}

STARTED=$(date +%s)
if [ "$MODE" = retrieval ]; then
  FROM=${5:-1}
  TO=${6:-$N}
  ASKED=$(echo "$IDS" | sed -n "${FROM},${TO}p")
  M=$(echo "$ASKED" | wc -l | tr -d ' ')
  # 3x the forecast: 60 s to build the retriever, 120 s the first question, 40 s each other
  CAP=$((3 * (140 + 40 * M)))
  echo "$(date -u +%FT%TZ) PART $PART-$KEY retrieval questions $FROM-$TO of $N, cap $CAP s" >> "$LOG"
  run "$PART-$KEY$SUFFIX" retrieval "$(echo "$ASKED" | paste -sd, -)" "$CAP" || { echo "$(date -u +%FT%TZ) PART_STOPPED" >> "$LOG"; exit 1; }
  $PY "$CL/retrieval_summary.py" check "$PART-$KEY$SUFFIX" >> "$LOG" 2>&1 || { echo "$(date -u +%FT%TZ) STOP path break" >> "$LOG"; echo "$(date -u +%FT%TZ) PART_STOPPED" >> "$LOG"; exit 1; }
  echo "$(date -u +%FT%TZ) PART_DONE" >> "$LOG"
  exit 0
fi
[ "$MODE" = answers ] || { echo "unknown mode $MODE"; exit 2; }
LAST=$(( (N + 9) / 10 ))
FROM=${5:-1}
TO=${6:-$LAST}
PART_CAP_SEC=${PART_CAP_SEC:-$((3 * (TO - FROM + 1) * 4060))}
echo "$(date -u +%FT%TZ) PART $PART-$KEY answers batches $FROM-$TO of $LAST, cap $PART_CAP_SEC s" >> "$LOG"
b=$FROM
while [ "$b" -le "$TO" ]; do
  [ -e "$STOP" ] && { echo "$(date -u +%FT%TZ) STOP file before batch $b" >> "$LOG"; exit 1; }
  [ $(( $(date +%s) - STARTED )) -gt "$PART_CAP_SEC" ] && { echo "$(date -u +%FT%TZ) STOP part cap before batch $b" >> "$LOG"; exit 1; }
  batch=$(echo "$IDS" | sed -n "$(( (b - 1) * 10 + 1 )),$(( b * 10 ))p" | paste -sd, -)
  label=$(printf "%s-%s-b%02d%s" "$PART" "$KEY" "$b" "$SUFFIX")
  run "$label" prod "$batch" 1020/1200 || { echo "$(date -u +%FT%TZ) PART_STOPPED at batch $b" >> "$LOG"; exit 1; }
  $PY "$CL/answers_summary.py" check "$label" >> "$LOG" 2>&1 || { echo "$(date -u +%FT%TZ) STOP path break in $label" >> "$LOG"; echo "$(date -u +%FT%TZ) PART_STOPPED at batch $b" >> "$LOG"; exit 1; }
  b=$((b + 1))
done
echo "$(date -u +%FT%TZ) PART_DONE" >> "$LOG"
