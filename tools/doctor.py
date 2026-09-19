from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from silksongtracker.codec import default_save_dirs, find_saves  # noqa: E402


def main() -> int:
    required = ["README.md", "data/content.json", "data/areas.json", "data/map/map.json", "web/index.html", "web/map.html", "web/app.js", "web/map.js", "silksongtracker/server.py"]
    missing = [x for x in required if not (ROOT / x).is_file()]
    print(f"Root: {ROOT}")
    print(f"Files: {len(list(ROOT.rglob('*')))}")
    if missing: print("Missing: " + ", ".join(missing)); return 1
    print("Save directories checked:")
    for directory in default_save_dirs(): print(f"  {directory}")
    saves = find_saves(); print(f"Detected save slots: {len(saves)}")
    print("No save is expected before the game has been launched." if not saves else "Save files found; use tools/inspect_save.py before updating adapters.")
    return 0


if __name__ == "__main__": raise SystemExit(main())
