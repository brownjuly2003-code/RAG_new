#!/bin/bash
# Export the given runs into chatlive-small/runs.json from a clean environment (no env.json:
# the clean Settings() must hold the code defaults), then scan it for secret-like strings.
# Usage: export.sh LABEL...
set -euo pipefail
CL=/Users/julia/RAG_new_chat_33d4b42/chatlive-small
WS=/Users/julia/RAG_new_chat_33d4b42
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
if pgrep -f "live_(supervisor|retrieval|api|runner)" >/dev/null; then
  echo "a live_ process is running; refuse"; exit 3
fi
SCRATCH=$(mktemp -d /tmp/chatlive-export.XXXXXX)
env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin HOME=/Users/julia CHAT_RUN_DIR="$SCRATCH" \
  PYTHONPATH="$WS:/Users/julia/RAG_new_mf_gate_site" PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -u "$CL/export.py" "$CL/runs.json" "$@"
"$PY" -I "$CL/check_export.py" "$CL/runs.json"
ls -A "$SCRATCH"
rm -rf "${SCRATCH:?}"
shasum -a 256 "$CL/runs.json"
