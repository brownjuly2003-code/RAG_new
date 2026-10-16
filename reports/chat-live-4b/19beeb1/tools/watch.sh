#!/bin/bash
# Print progress lines of one live run as they appear; exit when the supervisor is done.
# Usage: watch.sh LABEL
R=/Users/julia/RAG_new_chat_19beeb1/chatlive/runs
S="$R/$1.supervisor.log"
P="$R/$1/progress.log"
n=0
while true; do
  if [ -f "$P" ]; then
    c=$(wc -l < "$P")
    if [ "$c" -gt "$n" ]; then
      sed -n "$((n + 1)),${c}p" "$P" | grep -E "BEGIN|CASE|STOP|VARIANT|Traceback|Error" || true
      n=$c
    fi
  fi
  if grep -q LIVE_DONE "$S" 2>/dev/null; then
    tail -3 "$S"
    exit 0
  fi
  if ! pgrep -f "live_supervisor.py $1 " > /dev/null; then
    echo "SUPERVISOR GONE without LIVE_DONE"
    tail -5 "$S"
    exit 1
  fi
  sleep 5
done
