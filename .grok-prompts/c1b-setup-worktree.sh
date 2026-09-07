#!/bin/bash
set -euo pipefail

OLD_WT=/tmp/rag-new-c06bdf5.WLtg39/worktree
BUNDLE=/tmp/c1b-b8ecc8e.bundle
SHA=b8ecc8efb780d423a267595584ef0927ebb77cc5
BASE_SHA=c06bdf5721b434eff32dcf5b9991221d5b2a15f8
CTX_SRC="$OLD_WT/.tmp/ab_candidates_phase2_C.json"
CTX_HASH=91ce1745e13ce24cc1b69d0655412385700f5028b4e6b4ed4bf056cb6188ff10
DS_HASH=3737d694362d1867ca3d5983e3765d02c01110d2409145ba7e0f05c021d9c720
MODEL_DIGEST=500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41
PY=/Users/julia/RAG_Support_Assistant/.venv/bin/python

echo "OLD_HEAD=$(git -C "$OLD_WT" rev-parse HEAD)"
echo "OLD_PORCELAIN=$(git -C "$OLD_WT" status --porcelain | wc -l | tr -d ' ')"
git -C "$OLD_WT" cat-file -t "$BASE_SHA" >/dev/null
git -C "$OLD_WT" bundle verify "$BUNDLE"

BASE=$(mktemp -d /tmp/rag-new-b8ecc8e.XXXXXX)
BARE="$BASE/bare"
WT="$BASE/worktree"
RESULTS="$BASE/results"
mkdir -p "$RESULTS"

git clone --bare -- "$OLD_WT" "$BARE"
git -C "$BARE" fetch -- "$BUNDLE" master:refs/heads/from-bundle
git -C "$BARE" cat-file -t "$SHA" >/dev/null
git -C "$BARE" worktree add --detach "$WT" "$SHA"

cd "$WT"
HEAD_NOW=$(git rev-parse HEAD)
PORCELAIN=$(git status --porcelain)
if [ "$HEAD_NOW" != "$SHA" ]; then
  echo "FAIL new worktree SHA $HEAD_NOW"
  exit 1
fi
if [ -n "$PORCELAIN" ]; then
  echo "FAIL new worktree dirty"
  printf '%s\n' "$PORCELAIN"
  exit 1
fi

DS_ACT=$(shasum -a 256 evaluation/curated_cases_aircargo.jsonl | awk '{print $1}')
echo "DATASET_SHA=$DS_ACT"
if [ "$DS_ACT" != "$DS_HASH" ]; then
  echo "FAIL dataset hash"
  exit 1
fi

CTX_ACT=$(shasum -a 256 "$CTX_SRC" | awk '{print $1}')
echo "CTX_SRC_SHA=$CTX_ACT"
if [ "$CTX_ACT" != "$CTX_HASH" ]; then
  echo "FAIL contexts source hash"
  exit 1
fi
mkdir -p .tmp
cp -p "$CTX_SRC" .tmp/ab_candidates_phase2_C.json
CTX_NEW=$(shasum -a 256 .tmp/ab_candidates_phase2_C.json | awk '{print $1}')
echo "CTX_NEW_SHA=$CTX_NEW"
if [ "$CTX_NEW" != "$CTX_HASH" ]; then
  echo "FAIL contexts copy hash"
  exit 1
fi

"$PY" - <<'PY'
import httpx
import torch
import transformers
print("PYTHON", "3.11.15")
print("IMPORTS_OK")
print("TORCH", torch.__version__)
print("TRANSFORMERS", transformers.__version__)
print("HTTPX", httpx.__version__)
PY

"$PY" - <<'PY'
import json
import urllib.request
expected = "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"
with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=30) as resp:
    data = json.load(resp)
models = data.get("models") or []
match = None
for item in models:
    name = str(item.get("name") or item.get("model") or "")
    if name == "qwen3:8b":
        match = item
        break
if match is None:
    raise SystemExit("FAIL ollama model qwen3:8b not installed")
digest = str(match.get("digest") or "").removeprefix("sha256:")
details = match.get("details") or {}
quant = str(details.get("quantization_level") or "")
print("OLLAMA_NAME", match.get("name"))
print("OLLAMA_DIGEST", digest)
print("OLLAMA_QUANT", quant)
print("OLLAMA_SIZE", match.get("size"))
if digest != expected:
    raise SystemExit("FAIL ollama digest")
if quant != "Q4_K_M":
    raise SystemExit("FAIL ollama quant")
print("OLLAMA_OK")
PY

echo "OLD_HEAD_AFTER=$(git -C "$OLD_WT" rev-parse HEAD)"
echo "OLD_PORCELAIN_AFTER=$(git -C "$OLD_WT" status --porcelain | wc -l | tr -d ' ')"
echo "NEW_WORKTREE=$WT"
echo "NEW_HEAD=$HEAD_NOW"
echo "NEW_CLEAN=1"
echo "RESULTS_DIR=$RESULTS"
echo "BASE=$BASE"

umask 077
cat > /tmp/c1b-b8ecc8e-smoke.env <<EOF
BASE=$BASE
WORKTREE=$WT
RESULTS_DIR=$RESULTS
SHA=$SHA
PY=$PY
EOF

echo SETUP_OK
