"""Load and validate the editable Silksong content database."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_json(name: str):
    with (ROOT / "data" / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_content() -> dict:
    data = load_json("content.json")
    # Keep the source file concise while exposing a stable entry contract.
    for section in data.get("sections", []):
        if "entries" not in section:
            entries = []
            for index, item in enumerate(section.pop("items", []), 1):
                if isinstance(item, str):
                    entry_id = f"{section['id']}-{index:02d}"
                    entries.append({"id": entry_id, "name": item, "points": 1, "counts": section.get("counts", True)})
                else:
                    entries.append({"counts": section.get("counts", True), **item})
            section["entries"] = entries
    return data


def load_areas() -> list[dict]:
    return load_json("areas.json")


def load_map() -> dict:
    return load_json("map/map.json")
