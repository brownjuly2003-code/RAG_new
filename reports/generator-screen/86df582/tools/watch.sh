#!/bin/sh
# Print each new line of the screening's progress log; exit after ALL_DONE or STOP,
# or when the runner is gone. Argument: the number of lines already seen.
LOG=/Users/julia/genscreen/progress.log
seen=${1:-0}
while :; do
  n=$(wc -l < $LOG | tr -d ' ')
  if [ "$n" -gt "$seen" ]; then
    sed -n "$((seen + 1)),${n}p" $LOG
    seen=$n
  fi
  grep -qE "ALL_DONE|STOP" $LOG && exit 0
  pgrep -f /genscreen/run_screen > /dev/null || { echo "RUNNER GONE after line $seen"; exit 1; }
  sleep 30
done
