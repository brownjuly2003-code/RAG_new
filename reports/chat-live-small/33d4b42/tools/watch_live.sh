#!/bin/sh
# Print each new line of the small-model live log; exit after a LIVE_SMALL_DONE written after
# the lines already seen, or when live_small.sh is gone. Argument: the lines already seen.
LOG=/Users/julia/RAG_new_chat_33d4b42/chatlive-small/runs/live-small.log
start=${1:-0}
seen=$start
while :; do
  n=$(wc -l < $LOG 2>/dev/null | tr -d ' ')
  n=${n:-0}
  if [ "$n" -gt "$seen" ]; then
    sed -n "$((seen + 1)),${n}p" $LOG | grep -E "START|LIVE_DONE|SKIP|STOP|unload|LIVE_SMALL_DONE"
    seen=$n
  fi
  tail -n "+$((start + 1))" $LOG | grep -q "LIVE_SMALL_DONE" && exit 0
  pgrep -f chatlive-small/live_small.sh > /dev/null || { echo "LIVE SCRIPT GONE after line $seen"; exit 1; }
  sleep 30
done
