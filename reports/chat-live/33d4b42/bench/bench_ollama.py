"""One-off speed probe of Ollama on deproject-mac with real RAG prompts.

Builds the product's QA prompt (agent/prompts.py copied next to this file) from
five real chunks of the ask100 Chroma index, sends it to /api/chat with
streaming, and records the time to the first token plus Ollama's own counters
(prompt_eval_count/duration, eval_count/duration, load_duration). Stdlib only.

Usage: python bench_ollama.py OUT_DIR MODEL:N_QUESTIONS [MODEL:N_QUESTIONS ...]
"""

import json
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from prompts import PROMPT_REGISTRY, _format_context_block  # noqa: E402


def build_qa_prompt(question, docs):
    return PROMPT_REGISTRY["qa"]["text"].format(context_block=_format_context_block(docs), question=question)

CHROMA = "/Users/julia/RAG_new_ask100_20261012_7cad79f/.ask100-runtime/chroma/chroma.sqlite3"
OLLAMA = "http://127.0.0.1:11434"
QUESTIONS = [
    ("Можно ли уволить беременную сотрудницу по инициативе работодателя?", "%беремен%"),
    ("Когда таможенный кейс нужно отправить на ручную проверку?", "%таможен%"),
    ("Кого нельзя привлекать к сверхурочной работе даже с согласия?", "%сверхурочн%"),
]
OPTIONS = {"num_ctx": 4096, "num_predict": 1024, "temperature": 0.2}


def host_state():
    out = {}
    for key, cmd in (("load", ["sysctl", "-n", "vm.loadavg"]), ("swap", ["sysctl", "-n", "vm.swapusage"])):
        out[key] = subprocess.run(cmd, capture_output=True, text=True, check=False).stdout.strip()
    return out


def chunks(pattern, limit=5):
    con = sqlite3.connect(f"file:{CHROMA}?mode=ro", uri=True)
    rows = con.execute(
        "select id, string_value from embedding_metadata where key='chroma:document' "
        "and string_value like ? order by id limit ?",
        (pattern, limit),
    ).fetchall()
    docs = []
    for row_id, text in rows:
        meta = dict(
            con.execute(
                "select key, string_value from embedding_metadata where id=? and key in ('source','file_name')",
                (row_id,),
            ).fetchall()
        )
        docs.append({"page_content": text, "metadata": meta})
    con.close()
    return docs


def post(path, body, timeout):
    req = urllib.request.Request(
        OLLAMA + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    return urllib.request.urlopen(req, timeout=timeout)


def preload(model):
    t0 = time.monotonic()
    with post("/api/generate", {"model": model, "keep_alive": "10m"}, 300) as resp:
        body = json.load(resp)
    return {"wall_sec": round(time.monotonic() - t0, 2), "done_reason": body.get("done_reason")}


def ask(model, prompt):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "keep_alive": "10m",
        "options": OPTIONS,
    }
    t0 = time.monotonic()
    first = None
    text = []
    final = {}
    with post("/api/chat", body, 900) as resp:
        for line in resp:
            if not line.strip():
                continue
            msg = json.loads(line)
            piece = (msg.get("message") or {}).get("content") or ""
            if piece and first is None:
                first = time.monotonic() - t0
            text.append(piece)
            if msg.get("done"):
                final = msg
    wall = time.monotonic() - t0
    ns = 1e9
    pe_n, pe_d = final.get("prompt_eval_count", 0), final.get("prompt_eval_duration", 0) / ns
    ev_n, ev_d = final.get("eval_count", 0), final.get("eval_duration", 0) / ns
    return {
        "wall_sec": round(wall, 2),
        "first_token_sec": round(first, 2) if first is not None else None,
        "load_sec": round(final.get("load_duration", 0) / ns, 2),
        "prompt_tokens": pe_n,
        "prompt_sec": round(pe_d, 2),
        "prompt_tok_per_sec": round(pe_n / pe_d, 1) if pe_d else None,
        "output_tokens": ev_n,
        "output_sec": round(ev_d, 2),
        "output_tok_per_sec": round(ev_n / ev_d, 2) if ev_d else None,
        "prompt_chars": len(prompt),
        "answer_head": "".join(text)[:160],
    }


def main():
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = [(spec.rsplit(":", 1)[0], int(spec.rsplit(":", 1)[1])) for spec in sys.argv[2:]]
    result = {"options": OPTIONS, "chroma": CHROMA, "host_before": host_state(), "runs": []}
    for model, n in plan:
        entry = {"model": model, "preload": preload(model), "host_after_load": host_state(), "calls": []}
        print(model, "preload", entry["preload"], flush=True)
        for question, pattern in QUESTIONS[:n]:
            docs = chunks(pattern)
            prompt = build_qa_prompt(question, docs)
            row = {"question": question, "n_docs": len(docs), **ask(model, prompt)}
            entry["calls"].append(row)
            print(model, json.dumps({k: v for k, v in row.items() if k != "answer_head"}, ensure_ascii=False), flush=True)
        entry["host_after_calls"] = host_state()
        result["runs"].append(entry)
        with post("/api/generate", {"model": model, "keep_alive": 0}, 60) as resp:
            resp.read()
    result["host_after"] = host_state()
    (out_dir / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DONE", out_dir / "results.json", flush=True)


if __name__ == "__main__":
    main()
