from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    content = json.loads((ROOT / "data/content.json").read_text(encoding="utf-8"))
    areas = json.loads((ROOT / "data/areas.json").read_text(encoding="utf-8"))
    map_data = json.loads((ROOT / "data/map/map.json").read_text(encoding="utf-8"))
    required = {"tools":51,"silk-skills":6,"upgrades":8,"silk-hearts":3,"crests":6,"abilities":7,"mask-upgrades":5,"silk-upgrades":9,"needle-upgrades":4,"items":1}
    actual = {s["id"]: len(s.get("items", s.get("entries", []))) for s in content["sections"] if s["id"] in required}
    errors = []
    for key, expected in required.items():
        if actual.get(key) != expected: errors.append(f"{key}: expected {expected}, got {actual.get(key)}")
    ids = [m.get("id") for m in map_data.get("markers", [])]
    if len(ids) != len(set(ids)): errors.append("map marker ids are not unique")
    if not areas: errors.append("areas.json is empty")
    if not map_data.get("markers"): errors.append("map has no markers")
    for marker in map_data['markers']:
        if not (ROOT / 'data/map/icons' / marker['icon']).is_file(): errors.append('Missing icon: '+marker['icon'])
    for key in map_data['validTiles']:
        if not (ROOT / 'data/map/tiles' / (key+'.webp')).is_file(): errors.append('Missing tile: '+key)
    for key in map_data['sketch']['validTiles']:
        if not (ROOT / 'data/map/sketch' / (key+'.webp')).is_file(): errors.append('Missing sketch tile: '+key)
    if errors:
        print("DATA INVALID"); print("\n".join(f"- {e}" for e in errors)); return 1
    print(f"OK: {sum(actual.values())} official points; {len(ids)} source pins; {len(map_data['categories'])} categories; {len(map_data['validTiles'])} offline tiles and all icons present")
    return 0


if __name__ == "__main__": raise SystemExit(main())
