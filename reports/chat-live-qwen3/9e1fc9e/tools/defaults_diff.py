"""Every Settings field of a clean environment (code defaults) against a run's snapshot.

Usage (Mac, clean env, workspace on PYTHONPATH, CHAT_RUN_DIR set to any directory):
  defaults_diff.py EFFECTIVE_SETTINGS_JSON
Secret-like fields appear only as <set>/<empty> on both sides (live_api.settings_snapshot).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_api import settings_snapshot  # noqa: E402

from config.settings import Settings  # noqa: E402

defaults = settings_snapshot(Settings())
effective = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["all"]
for name in sorted(set(defaults) | set(effective)):
    if defaults.get(name) != effective.get(name):
        print(f"{name}: default={defaults.get(name)!r} run={effective.get(name)!r}")
