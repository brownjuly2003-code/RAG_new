#!/bin/sh
# Stage 3b's V5 answers, unattended (docs/specs/answer-prompt-v5.md, «The replay»): WixQA, then
# ConditionalQA, then aircargo, each by replay.py on V4's saved contexts at the stand of 4f48fed.
#   - Before the first key, and after each: a line of the stand's environment (stand_env.py).
#   - Each key: the Mac idle as V4's chain read it (the 5-minute load below 2; no pytest,
#     llama-server, supervisor or replay; Ollama holding no model), waited for up to IDLE_WAIT
#     seconds; then `replay.py check` (every V4 prompt rebuilt byte for byte); then `replay.py
#     run`; then each saved prompt V5's, none V4's, one for each case.
# Anything else stops the chain, and the session reads it; a stopped key resumes where it
# stopped when the chain runs again. Its log: $V/v5-chain.log.
# Stop the chain before its next key: touch $V/v5-chain.stop. Stop a key before its next answer:
# touch $V/runs/v5-<key>.stop.
# Usage, on the Mac: nohup sh $V/v5_chain.sh > $V/v5-chain.out 2>&1 </dev/null &
set -u
S=/Users/julia/RAG_new_chat_4f48fed
V=$S/v5
R=$S/chatlive/runs
OUT=$V/runs
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
SITE=/Users/julia/RAG_new_mf_gate_site
LOG=$V/v5-chain.log
IDLE_WAIT=${IDLE_WAIT:-21600}
KEYS="wixqa conditionalqa aircargo"
V5_MARK="\[1\] for the context's first document,"
V4_MARK="\[1\] for the first document in the context list,"

say() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }
stop() { say "CHAIN_STOP $*"; exit 1; }

idle() {
  t=0
  while :; do
    l5=$(sysctl -n vm.loadavg | awk '{print $3}')
    if awk "BEGIN{exit !($l5 < 2)}" &&
      ! pgrep -f "pytest|llama-server|_supervisor|replay\.py" > /dev/null &&
      [ "$(curl -s http://127.0.0.1:11434/api/ps)" = '{"models":[]}' ]; then
      say "idle: load5 $l5"
      return 0
    fi
    [ "$t" -ge "$IDLE_WAIT" ] && return 1
    sleep 60
    t=$((t + 60))
  done
}

environment() {
  "$PY" "$V/stand_env.py" >> "$V/v5-environment.jsonl" || stop "no environment line"
  say "environment line $(wc -l < "$V/v5-environment.jsonl" | tr -d ' ')"
}

replay() {  # COMMAND KEY [OUT]
  env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME="$HOME" LC_ALL=C PYTHONPATH="$S:$SITE" \
    PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 \
    REQUEST_TIMEOUT_SEC=3600 OLLAMA_REQUEST_TIMEOUT_SEC=3600 STREAMING_TIMEOUT_SEC=3600 \
    RAG_DEVICE=cpu "$PY" "$V/replay.py" "$@" "$R" ${OUT_ARG:-}
}

v5prompts() {  # KEY: one V5 prompt for each case of its ten batches, none V4's
  cases=0
  prompts=0
  for b in "$OUT/v5-$1-b"*; do
    cases=$((cases + $(ls "$b/cases" | grep -c '\.json$')))
    for p in "$b/prompts/"*-stream.txt; do
      grep -q "$V5_MARK" "$p" || return 1
      grep -q "$V4_MARK" "$p" && return 1
      prompts=$((prompts + 1))
    done
  done
  say "$1: $cases cases, $prompts V5 prompts"
  [ "$cases" -eq "$prompts" ] && [ "$cases" -gt 0 ]
}

mkdir -p "$OUT"
say "CHAIN_START keys $KEYS"
environment
for key in $KEYS; do
  [ -e "$V/v5-chain.stop" ] && stop "the stop file $V/v5-chain.stop"
  idle || stop "the Mac not idle within $IDLE_WAIT s"
  OUT_ARG="" replay check "$key" > "$V/v5-$key.check.jsonl" 2> "$V/v5-$key.check.err"
  code=$?
  say "$(tail -1 "$V/v5-$key.check.err") exit $code"
  [ "$code" -eq 0 ] || stop "$key: a V4 prompt not rebuilt (exit $code)"
  say "LAUNCH $key"
  OUT_ARG="$OUT" replay run "$key" >> "$V/v5-chain.out" 2>&1
  code=$?
  say "KEY_END $key exit $code"
  environment
  [ "$code" -eq 0 ] || stop "$key: replay exit $code"
  v5prompts "$key" || stop "$key: its prompts are not V5's, one a case"
done
say "CHAIN_DONE"
