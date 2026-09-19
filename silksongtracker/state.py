from __future__ import annotations

from .analyzer import analyze
from .codec import find_saves, read_save
from .mapdata import build_map


class TrackerState:
    def __init__(self, extra_dirs: list[str] | None = None):
        self.extra_dirs = extra_dirs or []
        self.saves: list[dict] = []
        self.selected_slot: int | None = None
        self.raw: dict | None = None
        self.error: str | None = None
        self.refresh()

    def refresh(self) -> None:
        self.saves = find_saves(self.extra_dirs)
        previous = self.selected_slot
        slots = {item["slot"] for item in self.saves}
        self.selected_slot = previous if previous in slots else (self.saves[0]["slot"] if self.saves else None)
        self.raw = None; self.error = None
        if self.selected_slot is not None:
            candidate = next(item for item in self.saves if item["slot"] == self.selected_slot)
            try:
                self.raw = read_save(candidate["path"])
            except Exception as exc:  # surfaced in /api/state; tracker stays usable
                self.error = f"Could not decode slot {self.selected_slot}: {exc}"

    def select(self, slot: int) -> None:
        self.selected_slot = int(slot)
        self.refresh()

    def state(self) -> dict:
        candidate = next((x for x in self.saves if x["slot"] == self.selected_slot), None)
        result = analyze(self.raw, self.selected_slot, candidate["path"] if candidate else None)
        result["saves"] = [{k: item[k] for k in ("slot", "path", "size", "mtime")} for item in self.saves]
        result["error"] = self.error
        return result

    def map(self) -> dict:
        return build_map(self.raw)
