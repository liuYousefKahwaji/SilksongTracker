"""Small, explicit rule language for content and map markers."""

from __future__ import annotations

from typing import Any

from .schema import SaveView, truthy


def evaluate(rule: Any, save: SaveView | None) -> str:
    if save is None:
        return "unknown"
    if not rule:
        return "unknown"  # no rule means unverified, never falsely complete
    if isinstance(rule, str):
        return "complete" if truthy(save.value(rule, False)) else "left"
    if isinstance(rule, list):
        results = [evaluate(item, save) for item in rule]
        if any(item == "left" for item in results): return "left"
        if any(item == "unknown" for item in results): return "unknown"
        return "complete"
    if not isinstance(rule, dict):
        return "unknown"
    kind = rule.get("type", "bool")
    if kind == 'source_flag':
        from .flags import flag_status
        return flag_status(rule.get('flag'),save.raw)
    if kind == 'journal':
        records = save.value('playerData.EnemyJournalKillData.list',None)
        if not isinstance(records,list): return 'unknown'
        matched = [r for r in records if isinstance(r,dict) and r.get('Name') == rule['name']]
        if not matched: return 'left'
        kills = matched[0].get('Record',{}).get('Kills')
        if not isinstance(kills,int) or isinstance(kills,bool): return 'unknown'
        return 'complete' if kills > 0 else 'left'
    if kind == "bool":
        value = save.value(rule.get("path", ""), None)
        if value is None: return "unknown"
        return "complete" if truthy(value) == rule.get("equals", True) else "left"
    if kind in {"int", "number"}:
        value = save.value(rule.get("path", ""), None)
        if not isinstance(value, (int, float)): return "unknown"
        op = rule.get("op", ">="); target = rule.get("value", 1)
        ok = {">=": value >= target, ">": value > target, "==": value == target, "<=": value <= target, "<": value < target}.get(op)
        return "complete" if ok else "left"
    if kind == "any":
        outcomes = [evaluate(x, save) for x in rule.get("rules", [])]
        return "complete" if "complete" in outcomes else ("unknown" if "unknown" in outcomes else "left")
    if kind == "all":
        outcomes = [evaluate(x, save) for x in rule.get("rules", [])]
        return "left" if "left" in outcomes else ("unknown" if "unknown" in outcomes else "complete")
    if kind == "list_item_bool":
        collection = save.value(rule.get("path", ""), None)
        if not isinstance(collection, list): return "unknown"
        names = rule.get("matchAny", [rule.get("match")])
        names = {str(x) for x in names if x is not None}
        outcomes = []
        for item in collection:
            if not isinstance(item, dict) or str(item.get("Name", item.get("name", ""))) not in names:
                continue
            value: Any = item
            for part in str(rule.get("valuePath", "Data.IsUnlocked")).split("."):
                value = value.get(part) if isinstance(value, dict) else None
            outcomes.append('unknown' if value is None else ('complete' if truthy(value) == rule.get('equals',True) else 'left'))
        return 'complete' if 'complete' in outcomes else ('unknown' if 'unknown' in outcomes else 'left')
    if kind == "list_contains":
        collection = save.value(rule.get("path", ""), None)
        if not isinstance(collection, list): return "unknown"
        return "complete" if rule.get("value") in collection else "left"
    return "unknown"
