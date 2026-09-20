"""Reviewed supplements to the archived map, kept separate from source data.

Evidence and unresolved cases: MAP_TRACKING_AUDIT.md. These rules attach to
stable source IDs, never to an approximate position or an aggregate count.
"""
from .schema import get_path

# Exact quest-title joins against the reference trackers' quest definitions.
QUESTS = {
    '1335':'Courier Delivery Bonebottom', '1337':'Courier Delivery Fleatopia',
    '1338':'Tormented Trobbio', '1339':'Courier Delivery Pilgrims Rest',
    '1340':'Huntress Quest Runt', '1342':'Courier Delivery Songclave',
    '1343':'Courier Delivery Fixer', '463':'Courier Delivery Dustpens Slave',
    '464':'Courier Delivery Mask Maker', '468':'Belltown House Start',
    '490':'Steel Sentinel Pt2',
}
FLAGS = {
    '695':'@,playerData.UnlockedFastTravelTeleport,true',
    '1038':'@collectable,Plasmium Gland',
    '56':'@,playerData.HasMossGrottoMap,true',
    '58':'@,playerData.HasBoneforestMap,true',
    '174':'@,playerData.PurchasedPilgrimsRestToolPouch,true',
    '175':'@wish,Journal',
    # Full pickup inventories cross-checked: the other 19 mask / 17 spool
    # records already account for every other reference reward and scene.
    '143':'@wish,Beastfly Hunt',
    '1062':'@wish,Save Sherma',
    '1087':'@,playerData.FleaGamesMementoGiven,true',
    '368':'@,playerData.nuuMementoAwarded,true',
    '1183':'@,playerData.QuillState,1',
    '911':'@,playerData.QuillState,2',
    '912':'@,playerData.QuillState,3',
    '1029':'@,playerData.hasPinBench,true',
    '510':'@,playerData.hasJournal,true',
    '535':'@,playerData.CollectedHeartHunter,true',
}
FLAGS.update({key:'@wish,'+value for key,value in QUESTS.items()})

# Scene/object identities cross-checked against installed scene bundles and
# independently authored scene lists. See TRACKING_VALIDATION.md for evidence
# and the distinction between a researched mapping and playthrough validation.
CORE_LOCATIONS = {
    '1395':('Bone_04','Black_Thread_Core'),
    '1396':('Mosstown_02','Black_Thread_Core'),
    '1398':('Bone_07','Black_Thread_Core'),
    '1407':('Shellwood_26','Black_Thread_Core'),
    '1409':('Shellwood_01b','Black_Thread_Core'),
    '1415':('Greymoor_07','Black_Thread_Core'),
    '1418':('Dust_03','Black_Thread_Core'),
    '1419':('Greymoor_02','Black_Thread_Core'),
    '1421':('Shadow_05','Black_Thread_Core'),
    '1423':('Song_01','Black_Thread_Core_Citadel'),
    '1433':('Library_04','Black_Thread_Core_Citadel'),
    '1434':('Library_04','Black_Thread_Core_Citadel (1)'),
}
FLAGS.update({key:f'@bool,{scene},{item},true' for key,(scene,item) in CORE_LOCATIONS.items()})

# Additional room matches: lever components were followed to their connected
# gates, and the currency pickup's persistence component was checked directly.
SCENE_LOCATIONS = {
    '1378':('Bone_East_18','ant_lever_persistent (1)'),
    '1466':('Bone_01','Bone Lever'),
    '760':('Greymoor_15b','Greymoor Stand Lever'),
    '1332':('Hang_06_bank','Geo Small Persistent (1)'),
}
FLAGS.update({key:f'@bool,{scene},{item},true' for key,(scene,item) in SCENE_LOCATIONS.items()})

# Deliberate, reviewed corrections: related story events are not ownership.
CORRECTIONS = {'1039':'@collectable,White Flower'}


def alternative_unavailable(marker, raw):
    variants = {'1183':1, '911':2, '912':3}
    chosen = get_path(raw, 'playerData.QuillState')
    return marker['id'] in variants and type(chosen) is int and chosen in (1,2,3) and chosen != variants[marker['id']]


def supplemental_flag(marker):
    # Never replace a source predicate silently.
    return '' if marker.get('flag') else FLAGS.get(marker['id'],'')


def reference_reason(marker):
    """Describe this pin's role, not whether the game saves visits to it."""
    cat, name = marker['cat'], marker['name']
    if cat == 'benches': return 'Rest location. This pin does not track visits or rest history.'
    if cat in ('npc','vendor') or (cat=='maps' and name.startswith('Map Vendor')):
        return 'Character or shop location. Individual purchases and objectives are tracked by their own pins.'
    if cat == 'info': return 'Reference location, not a one-time completion objective.'
    if cat == 'shortcut' and name.startswith(('Requires ', 'Intersection -', 'Requirement Unknown')):
        return 'Route information. This pin does not establish whether the route has been traversed.'
    return None


def unresolved_reason(marker):
    if marker['name'].startswith('Wish Progress'):
        return 'The exact save record for this individual objective location has not been verified. Completing the overall quest is not proof of this pickup.'
    if marker['cat'] == 'shortcut':
        return 'The save record for opening this particular route has not been verified.'
    return 'This objective may be recorded in the save, but its exact tracking rule still needs verification.'
