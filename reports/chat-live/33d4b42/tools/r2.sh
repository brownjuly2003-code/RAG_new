#!/bin/bash
# Launch run R2 (retrieval alone; the reranker on the GPU with its error recorded, and with
# smaller cross-encoder batches) with the cases of R1. Refuses when anything of ours runs.
set -euo pipefail
CL=/Users/julia/RAG_new_chat_33d4b42/chatlive
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python
if pgrep -f "live_(supervisor|retrieval|api|runner)" >/dev/null; then
  echo "a live_ process is running; refuse"; exit 3
fi
CASES=$("$PY" -I -c 'import json,sys; print(",".join(json.load(open(sys.argv[1]))["cases"]))' \
  "$CL/runs/live-r1-retrieval/launch.json")
LIVE_VARIANTS=rerank-mps,rerank-mps-b4,rerank-mps-b1,auto-b4,auto \
  "$PY" -u "$CL/launch.py" live-r2-rerank-gpu retrieval "$CASES" 900
