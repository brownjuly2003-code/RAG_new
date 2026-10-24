#!/bin/sh
# Stage 2b's answers after WixQA, unattended (docs/specs/answer-prompt-v4.md, «The stand and the
# run»; Julia, 2026-10-24: «Автозапуск на Mac»): ConditionalQA, then aircargo, on the stand of
# 4f48fed, by stage2.sh as the session would launch them. Not a measurement of its own.
#   - It waits for WixQA's driver to end, and goes on only if WixQA is done whole: each of its
#     ten batches complete and its path check clean.
#   - Each base: batch 1 alone; its ten stream prompts must be V4's (QA_PROMPT_V4's citation
#     sentence, none of V3's); then batches 2-10; then the base done whole.
#   - Before each launch: no stop file, and the Mac idle as stage 2's idle check reads it (the
#     5-minute load below 2; no pytest, llama-server or supervisor; Ollama holding no model),
#     waited for up to IDLE_WAIT seconds.
#   - After each base: a line of the stand's environment (stand_env.py).
# Anything else stops the chain, and the session reads it: a failed batch is rerun only by the
# session, by stage 2's rules. Its log: $C/v4-chain.log.
# Stop the chain before its next launch: touch $C/v4-chain.stop. Stop a running base before its
# next batch: touch $S/chatlive/runs/v4-<key>.stop.
# Usage, on the Mac: nohup sh $C/v4_chain.sh > $C/v4-chain.out 2>&1 </dev/null &
set -u
S=/Users/julia/RAG_new_chat_4f48fed
C=/Users/julia/RAG_new_v4_control_20261024
R=$S/chatlive/runs
ROOT=/Users/julia/RAG_new_external_s1
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
LOG=$C/v4-chain.log
IDLE_WAIT=${IDLE_WAIT:-21600}

say() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }
stop() { say "CHAIN_STOP $*"; exit 1; }

whole() {  # KEY FROM TO: each batch complete, its path check clean
  n=$2
  while [ "$n" -le "$3" ]; do
    b=$(printf "v4-%s-b%02d" "$1" "$n")
    grep -q "LIVE_DONE $b complete exit 0" "$R/v4-$1.log" || return 1
    grep -q "^CHECK $b cases 10 .*path_breaks {}$" "$R/v4-$1.log" || return 1
    n=$((n + 1))
  done
}

v4prompts() {  # LABEL: ten stream prompts, each V4's
  [ "$(ls "$R/$1/prompts/" | grep -c -- '-stream\.txt$')" -eq 10 ] || return 1
  for p in "$R/$1/prompts/"*-stream.txt; do
    grep -q "\[1\] for the first document in the context list" "$p" || return 1
    grep -q "add \[N\] right after it" "$p" && return 1
    grep -q "suggest contacting a support specialist" "$p" && return 1
  done
  return 0
}

idle() {
  t=0
  while :; do
    l5=$(sysctl -n vm.loadavg | awk '{print $3}')
    if awk "BEGIN{exit !($l5 < 2)}" && ! pgrep -f "pytest|llama-server|live_supervisor" > /dev/null &&
      [ "$(curl -s http://127.0.0.1:11434/api/ps)" = '{"models":[]}' ]; then
      say "idle: load5 $l5"
      return 0
    fi
    [ "$t" -ge "$IDLE_WAIT" ] && return 1
    sleep 60
    t=$((t + 60))
  done
}

launch() {  # KEY FROM TO, run to its end
  [ -e "$C/v4-chain.stop" ] && stop "the stop file $C/v4-chain.stop"
  idle || stop "the Mac not idle within $IDLE_WAIT s"
  say "LAUNCH $1 batches $2-$3"
  sh "$S/chatlive/stage2.sh" answers v4 "$1" "$ROOT" "$2" "$3" >> "$R/v4-$1.out" 2>&1
  say "PART_END $1 batches $2-$3 exit $?"
}

environment() {
  "$PY" "$S/reports/answer-prompt-v4/tools/stand_env.py" >> "$S/chatlive/v4-environment.jsonl" ||
    stop "no environment line"
  say "environment line $(wc -l < "$S/chatlive/v4-environment.jsonl" | tr -d ' ')"
}

if [ "${1:-}" = check ]; then  # sh v4_chain.sh check N: the checks on WixQA's batches 1-N
  LOG=/dev/null
  whole wixqa 1 "${2:-1}" && echo "wixqa batches 1-${2:-1} whole" || echo "wixqa batches 1-${2:-1} not whole"
  v4prompts v4-wixqa-b01 && echo "v4-wixqa-b01: ten V4 prompts" || echo "v4-wixqa-b01: not ten V4 prompts"
  IDLE_WAIT=0 idle && echo "idle" || echo "not idle"
  exit 0
fi
mkdir -p "$C"
say "CHAIN_START: waiting for WixQA's driver"
while pgrep -f "stage2.sh answers v4 wixqa" > /dev/null; do sleep 60; done
whole wixqa 1 10 || stop "wixqa not done whole: read $R/v4-wixqa.log"
say "wixqa done whole"
environment
for KEY in conditionalqa aircargo; do
  launch "$KEY" 1 1
  whole "$KEY" 1 1 || stop "$KEY batch 1 not done whole: read $R/v4-$KEY.log"
  v4prompts "v4-$KEY-b01" || stop "$KEY batch 1: a stream prompt not V4's, or not ten"
  say "$KEY batch 1: ten V4 prompts"
  launch "$KEY" 2 10
  whole "$KEY" 1 10 || stop "$KEY not done whole: read $R/v4-$KEY.log"
  say "$KEY done whole"
  environment
done
say "CHAIN_DONE"
