"""Stage 2's observation-only API, with final-package refusal before its lifespan."""

import os
import sys
from pathlib import Path

from common import ROOT, SETTINGS, frozen, load, require, write
from stand import check


def main():
    held = check()
    run = Path(os.environ["CHAT_RUN_DIR"])
    write(run / "stand.json", held)
    observer = load("reports/stage2/tools/live_api.py", "final_live_api")
    observer.WS = ROOT
    sys.path.insert(0, str(ROOT))
    import vectordb._base_manager as base
    from vectordb.onnx_reranker import OnnxCrossEncoder

    original = base.get_reranker

    def checked(*args, **kwargs):
        live = original(*args, **kwargs)
        require(isinstance(live, OnnxCrossEncoder), "factory did not load ONNX")
        frozen("arms").loaded_environment(live, held["environment"])
        write(
            run / "loaded.json",
            {
                "tokenizer_snapshot": held["environment"]["tokenizer_snapshot"],
                "ort_intra_op_num_threads": live.session.get_session_options().intra_op_num_threads,
            },
        )
        return live

    base.get_reranker = checked
    observer.PUBLIC_SETTINGS = sorted(
        set(observer.PUBLIC_SETTINGS) | set(SETTINGS) | {"reranker_onnx_path"}
    )
    observer.main()


if __name__ == "__main__":
    main()
