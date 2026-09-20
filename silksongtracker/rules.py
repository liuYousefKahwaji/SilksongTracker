"""Small, explicit rule language for content and map markers."""

from __future__ import annotations

from typing import Any
import math

from .schema import SaveView, truthy


def evaluate(rule: Any, save: SaveView | None) -> str:
    if save is None:
        return "unknown"
    if not rule:
        return "unknown"  # no rule means unverified, never falsely complete
    if isinstance(rule, str):
        return evaluate({'type':'bool','path':rule},save)
    if isinstance(rule, list):
        if not rule:return 'unknown'
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
        if not matched: return 'left' if all(isinstance(r,dict) and isinstance(r.get('Name'),str) for r in records) else 'unknown'
        if any(r.get('Record') != matched[0].get('Record') for r in matched):return 'unknown'
        record=matched[0].get('Record')
        if not isinstance(record,dict): return 'unknown'
        kills = record.get('Kills')
        if not isinstance(kills,int) or isinstance(kills,bool): return 'unknown'
        return 'complete' if kills > 0 else 'left'
    if kind == "bool":
        value = save.value(rule.get("path", ""), None)
        if not isinstance(value,bool): return "unknown"
        return "complete" if truthy(value) == rule.get("equals", True) else "left"
    if kind in {"int", "number"}:
        value = save.value(rule.get("path", ""), None)
        if type(value) not in (int,float) or not math.isfinite(value): return "unknown"
        op = rule.get("op", ">="); target = rule.get("value", 1)
        if type(target) not in (int,float) or not math.isfinite(target) or op not in ('>=','>','==','<=','<'): return 'unknown'
        ok = {">=": value >= target, ">": value > target, "==": value == target, "<=": value <= target, "<": value < target}.get(op)
        return "complete" if ok else "left"
    if kind == "any":
        if not rule.get('rules'):return 'unknown'
        outcomes = [evaluate(x, save) for x in rule.get("rules", [])]
        return "complete" if "complete" in outcomes else ("unknown" if "unknown" in outcomes else "left")
    if kind == "all":
        if not rule.get('rules'):return 'unknown'
        outcomes = [evaluate(x, save) for x in rule.get("rules", [])]
        return "left" if "left" in outcomes else ("unknown" if "unknown" in outcomes else "complete")
    if kind == "list_item_bool":
        collection = save.value(rule.get("path", ""), None)
        if not isinstance(collection, list): return "unknown"
        names = rule.get("matchAny", [rule.get("match")])
        names = {str(x) for x in names if x is not None}
        outcomes = []
        seen = {}
        for item in collection:
            if not isinstance(item, dict) or str(item.get("Name", item.get("name", ""))) not in names:
                continue
            name = item.get('Name',item.get('name'))
            if name in seen and seen[name] != item:return 'unknown'
            seen[name] = item
            value: Any = item
            for part in str(rule.get("valuePath", "Data.IsUnlocked")).split("."):
                value = value.get(part) if isinstance(value, dict) else None
            outcomes.append('unknown' if not isinstance(value,bool) else ('complete' if value == rule.get('equals',True) else 'left'))
        if not outcomes and any(not isinstance(r,dict) or not isinstance(r.get('Name',r.get('name')),str) for r in collection):return 'unknown'
        return 'complete' if 'complete' in outcomes else ('unknown' if 'unknown' in outcomes else 'left')
    if kind == 'tool_completion':
        # CountGameCompletion uses IsUnlockedNotHidden. A skill's player flag
        # is an alternate unlock test, ORed with the serialized tool unlock.
        records = save.value('playerData.Tools.savedData',None)
        if not isinstance(records,list):return 'unknown'
        names = rule['names']
        outcomes = []
        for name in names:
            matched = [r for r in records if isinstance(r,dict) and r.get('Name')==name]
            if matched and any(r.get('Data') != matched[0].get('Data') for r in matched):
                outcomes.append('unknown')
                continue
            owned = evaluate({'type':'list_item_bool','path':'playerData.Tools.savedData','match':name},save)
            alternate = rule.get('alternate')
            if alternate:
                alt = evaluate({'path':'playerData.'+alternate},save)
                owned = 'complete' if 'complete' in (owned,alt) else ('unknown' if 'unknown' in (owned,alt) else 'left')
            # Missing record uses the game's default struct (IsHidden=false).
            hidden = [r.get('Data',{}).get('IsHidden',False) if isinstance(r.get('Data'),dict) else None for r in matched]
            if any(v is True for v in hidden):owned='left'
            elif any(not isinstance(v,bool) for v in hidden):owned='unknown'
            outcomes.append(owned)
        return 'complete' if 'complete' in outcomes else ('unknown' if 'unknown' in outcomes else 'left')
    if kind == "list_contains":
        collection = save.value(rule.get("path", ""), None)
        if not isinstance(collection, list): return "unknown"
        return "complete" if rule.get("value") in collection else "left"
    return "unknown"
