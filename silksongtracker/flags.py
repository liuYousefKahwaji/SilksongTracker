"""Source-map predicates, matching the Silksong serialized save collections.

Collection absence is unknown; an absent record in a valid sparse collection
is not completed. Never substitute an object's ID from a different scene.
"""
import json
from .schema import get_path


def flag_status(flag, raw):
    if raw is None or not flag:
        return 'unknown'
    parts = flag.split(',')
    head = parts[0].lower()
    # This single archived source record has a mistyped predicate. Confirmed
    # against the reference viewer's relic list and Relics.svelte evaluator.
    if flag == '@flag,Ancient Egg Abyss Middle': head = '@relic'
    missing = object()
    got, wanted, op = missing, True, '='
    if head == '@' and len(parts) >= 2:
        got = get_path(raw, parts[1], missing)
        try: wanted = json.loads(parts[2]) if len(parts)>2 and parts[2] else True
        except ValueError: wanted = parts[2]
        op = parts[3] if len(parts)>3 else '='
    elif head in ('@tool', '@crest', '@wish', '@relic') and len(parts)>1:
        collection, fields = {
            '@tool':('Tools', ['IsUnlocked']), '@crest':('ToolEquips', ['IsUnlocked']),
            '@wish':('QuestCompletionData', ['IsCompleted', 'WasEverCompleted']),
            '@relic':('Relics', ['IsCollected']),
        }[head]
        records = get_path(raw, 'playerData.'+collection+'.savedData', missing)
        if not isinstance(records, list): return 'unknown'
        matches = [r for r in records if isinstance(r,dict) and r.get('Name') == parts[1]]
        if not matches: return 'left'
        values = [get_path(r,'Data.'+f,missing) for r in matches for f in fields]
        if any(v is True for v in values): return 'complete'
        return 'left' if all(isinstance(v,bool) for v in values) else 'unknown'
    elif head == '@nail' and len(parts)>1:
        got = get_path(raw, 'playerData.nailUpgrades', missing)
        wanted, op = int(parts[1]), '>='
    elif head in ('@bool', '@int', '@geo') and len(parts)>2:
        collection = {'@bool':'persistentBools', '@int':'persistentInts', '@geo':'geoRocks'}[head]
        records = get_path(raw, 'sceneData.'+collection+'.serializedList', missing)
        modern = isinstance(records,list)
        if not modern and head == '@bool':
            records = get_path(raw,'sceneData.persistentBoolItems',missing)
        if not isinstance(records,list): return 'unknown'
        record = next((r for r in records if isinstance(r,dict)
                       and r.get('SceneName' if modern else 'sceneName') == parts[1]
                       and r.get('ID' if modern else 'id') == parts[2]),None)
        if record is None: return 'left' if modern else 'unknown'
        got = record.get('Value' if modern else 'activated',missing)
        try: wanted = (len(parts)<4 or parts[3]!='false') if head=='@bool' else int(parts[3] if len(parts)>3 and parts[3] else '1')
        except ValueError: return 'unknown'
    if got is missing: return 'unknown'
    try:
        if op in ('=', '=='): done = type(got) is type(wanted) and got == wanted
        elif op == '>=': done = got >= wanted
        elif op == '<=': done = got <= wanted
        elif op == '>': done = got > wanted
        elif op == '<': done = got < wanted
        elif op == '!=': done = got != wanted
        else: return 'unknown'
    except TypeError: return 'unknown'
    return 'complete' if done else 'left'
