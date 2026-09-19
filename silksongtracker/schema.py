"""Tolerant accessors around the evolving Silksong save schema."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def get_path(root: Any, path: str, default: Any = None) -> Any:
    value = root
    for part in path.split(".") if path else []:
        if isinstance(value, dict):
            value = value.get(part, default)
        else:
            return default
        if value is default:
            return default
    return value


def first(root: dict, paths: Iterable[str], default: Any = None) -> Any:
    for path in paths:
        value = get_path(root, path, None)
        if value is not None:
            return value
    return default


def truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return bool(value)


class SaveView:
    """Flatten common player/persistent collections while preserving raw data."""

    def __init__(self, raw: dict):
        self.raw = raw
        self.player = first(raw, ("playerData", "PlayerData", "player", "data.playerData"), {}) or {}
        self.persistent = first(raw, ("persistentData", "PersistentData", "persistent", "data.persistentData"), {}) or {}
        self.bools: dict[str, Any] = {}
        self.ints: dict[str, Any] = {}
        self.strings: dict[str, Any] = {}
        self._collect(self.player); self._collect(self.persistent)
        for container_name in ("persistentBoolItems", "persistentBools", "bools", "persistentBoolData"):
            self._collect_collection(first(raw, (container_name, f"playerData.{container_name}"), None), self.bools)
        for container_name in ("persistentIntItems", "persistentInts", "ints", "persistentIntData"):
            self._collect_collection(first(raw, (container_name, f"playerData.{container_name}"), None), self.ints)

    def _collect(self, value: Any, prefix: str = "") -> None:
        if not isinstance(value, dict):
            return
        for key, item in value.items():
            name = f"{prefix}.{key}" if prefix else key
            if isinstance(item, bool): self.bools[name] = item
            elif isinstance(item, int) and not isinstance(item, bool): self.ints[name] = item
            elif isinstance(item, str): self.strings[name] = item
            elif isinstance(item, dict): self._collect(item, name)

    @staticmethod
    def _collect_collection(value: Any, target: dict[str, Any]) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, dict) and "value" in item: target[str(key)] = item["value"]
                else: target[str(key)] = item
        elif isinstance(value, list):
            for item in value:
                if not isinstance(item, dict): continue
                key = item.get("key", item.get("name", item.get("id")))
                if key is not None: target[str(key)] = item.get("value", item.get("Value", item.get("state", True)))

    def value(self, path: str, default: Any = None) -> Any:
        direct = get_path(self.raw, path, None)
        if direct is not None: return direct
        direct = get_path(self.player, path, None)
        if direct is not None: return direct
        if path in self.bools: return self.bools[path]
        if path in self.ints: return self.ints[path]
        if path in self.strings: return self.strings[path]
        return default

    def has(self, path: str) -> bool:
        return self.value(path, None) is not None
