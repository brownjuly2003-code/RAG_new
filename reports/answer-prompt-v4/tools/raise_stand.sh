#!/bin/sh
# Raise V4's stand of commit C on the Mac (docs/specs/answer-prompt-v4.md, «The stand and the
# run»): the stage-1 handoff's command («Next actions» 2), its product-code check made against
# 5e308fe, stage 2's stand, and the first line of the stand's environment (stand_env.py).
# Usage, on the laptop: sh reports/answer-prompt-v4/tools/raise_stand.sh <full commit sha>
set -eu
C=$1
case $C in
  ????????????????????????????????????????) ;;
  *) echo "give the full 40-character sha" >&2; exit 2 ;;
esac
ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
S=/Users/julia/RAG_new_chat_$(printf %s "$C" | cut -c1-7)
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
echo "== product diff against 5e308fe:"
git -C "$ROOT" diff --stat 5e308fe "$C" -- . ':!docs' ':!docs-site' ':!reports' ':!tests' ':!archive' ':!*.md'
OTHER=$(git -C "$ROOT" diff --name-only 5e308fe "$C" -- . ':!docs' ':!docs-site' ':!reports' ':!tests' ':!archive' ':!*.md' \
  | grep -v -x -e agent/prompts.py -e scripts/chat_answer_judge.py -e scripts/context_judge.py \
       -e .github/workflows/ci.yml -e .pre-commit-config.yaml || true)
if [ -n "$OTHER" ]; then
  echo "refused: the product diff holds more than the spec allows: $OTHER" >&2
  exit 3
fi
CODE=$(git -C "$ROOT" diff -U0 5e308fe "$C" -- .github/workflows/ci.yml .pre-commit-config.yaml \
  | grep '^[+-]' | grep -v '^[+-][+-][+-]' | grep -v '^[+-][[:space:]]*#' || true)
if [ -n "$CODE" ]; then
  echo "refused: the CI configuration changed beyond its comments" >&2
  exit 3
fi
git -C "$ROOT" archive "$C" | ssh deproject-mac "test ! -e $S && mkdir $S && tar -x -C $S && echo $C > $S/CODE_SHA && ln -s /Users/julia/RAG_new_ask100_20261012_7cad79f/.ask100-runtime $S/.ask100-runtime && mkdir $S/chatlive && cp $S/reports/stage1/tools/*.py $S/reports/stage1/tools/audit.sh $S/chatlive/ && cp $S/reports/stage2/tools/* $S/chatlive/ && $PY $S/reports/answer-prompt-v4/tools/stand_env.py >> $S/chatlive/v4-environment.jsonl && cat $S/CODE_SHA && ls $S/chatlive && wc -l $S/chatlive/v4-environment.jsonl"
