#!/bin/sh
# Raise the stand of item 5a's short live series at commit C on the Mac
# (docs/specs/stage4-step5a-live.md, «The stand»): V4's raise_stand.sh
# (reports/answer-prompt-v4/tools) without its check of the product's diff against 5e308fe,
# since both runtimes run the one commit, and with the series' folder $S/live5a for its tools.
# Usage, on the laptop: sh reports/stage4-step5a-live/tools/raise_stand.sh <full commit sha>
set -eu
C=$1
case $C in
  ????????????????????????????????????????) ;;
  *) echo "give the full 40-character sha" >&2; exit 2 ;;
esac
ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
S=/Users/julia/RAG_new_chat_$(printf %s "$C" | cut -c1-7)
git -C "$ROOT" archive "$C" | ssh deproject-mac "test ! -e $S && mkdir $S && tar -x -C $S && echo $C > $S/CODE_SHA && ln -s /Users/julia/RAG_new_ask100_20261012_7cad79f/.ask100-runtime $S/.ask100-runtime && mkdir -p $S/live5a/runs && cat $S/CODE_SHA && ls -la $S/.ask100-runtime/ | head -5"
