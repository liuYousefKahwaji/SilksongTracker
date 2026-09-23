from __future__ import annotations

import hashlib

from .analyzer import analyze
from .codec import find_saves, read_save
from .mapdata import build_map


class TrackerState:
    def __init__(self, extra_dirs: list[str] | None = None):
        self.extra_dirs = extra_dirs or []
        self.saves: list[dict] = []
        self.selected_slot: int | None = None
        self.selected_path: str | None = None
        self.raw: dict | None = None
        self.error: str | None = None
        self.refresh()

    def refresh(self) -> None:
        self.saves = find_saves(self.extra_dirs)
        candidate = next((item for item in self.saves if item["path"] == self.selected_path), None)
        if candidate is None: candidate = self.saves[0] if self.saves else None
        self.selected_path = candidate["path"] if candidate else None
        self.selected_slot = candidate["slot"] if candidate else None
        self.raw = None; self.error = None
        if candidate is not None:
            try:
                self.raw = read_save(candidate["path"])
            except Exception as exc:  # surfaced in /api/state; tracker stays usable
                self.error = f"Could not decode slot {self.selected_slot}: {exc}"

    def select(self, slot: int) -> None:
        candidate = next((item for item in self.saves if item["slot"] == int(slot)), None)
        if candidate is None: raise ValueError("Save slot not found")
        self.selected_path = candidate["path"]
        self.refresh()

    def select_index(self, index: int) -> None:
        if not 0 <= index < len(self.saves): raise ValueError("Save index out of range")
        self.selected_path = self.saves[index]["path"]
        self.refresh()

    def state(self) -> dict:
        candidate = next((x for x in self.saves if x["path"] == self.selected_path), None)
        result = analyze(self.raw, self.selected_slot, candidate["path"] if candidate else None)
        result["saves"] = [{k: item[k] for k in ("slot", "path", "size", "mtime")} for item in self.saves]
        result["selectedSaveIndex"] = self.saves.index(candidate) if candidate else None
        result["error"] = self.error
        return result

    def map(self) -> dict:
        save_key = hashlib.sha256(self.selected_path.encode()).hexdigest()[:16] if self.selected_path else "no-save"
        return {**build_map(self.raw), "slot": self.selected_slot, "saveKey": save_key, "saveError": self.error}
