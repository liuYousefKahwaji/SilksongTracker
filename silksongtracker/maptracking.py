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
    '490':'Steel Sentinel Pt2', '1436':'Pinstress Battle',
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
    # Exact marker-to-save matches reviewed against installed scene bundles.
    '1314':'@,playerData.cog7_gateOpened,true',
    '1464':'@,playerData.song_11_oneway,true',
    '1319':'@,playerData.skullKingShortcut,true',
    '1286':'@,playerData.openedDocksBackEntrance,true',
    '1420':'@,playerData.silkFarmAbyssCoresCleared,true',
    '1110':'@collectable,Pristine Core',
    '296':'@collectable,Shard Pouch',
    '375':'@bool,Organ_01,Silk Grub Large Cocoon,true',
    '525':'@wish,Shiny Bell Goomba',
    '950':'@bool,Cog_07,Battle Scene,true',
    '1469':'@bool,Bone_East_LavaChallenge,Battle Scene,true',
    # These source pins aggregate several physical pickups into one icon.
    # @all intentionally reports complete only when every exact save record is.
    '1468':'@all,@bool,Dock_01,Geo Small Persistent,true|@bool,Dock_01,Geo Small Persistent (1),true|@bool,Dock_01,Geo Med Persistent,true',
    '1309':'@all,@int,Shellwood_11,Shell Shard Fossil Mid,0|@int,Shellwood_11,Shell Shard Fossil Tiny Egg,0|@int,Shellwood_11,Shell Shard Fossil Tiny Bumpy,0|@int,Shellwood_11,Shell Shard Fossil Tiny Bumpy (1),0|@int,Shellwood_11,Shell Shard Fossil Tiny Bumpy (2),0',
    '331':'@all,@int,Greymoor_17,Shell Shard Fossil Tiny Egg (3),0|@int,Greymoor_17,Shell Shard Fossil Tiny Egg (1),0|@int,Greymoor_17,Shell Shard Fossil Tiny Front,0|@int,Greymoor_17,Shell Shard Fossil Tiny Front (1),0|@int,Greymoor_17,Shell Shard Fossil Tiny Front (2),0',
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
    '1403':('Bone_East_17','Black_Thread_Core'),
    '1404':('Bone_East_05','Black_Thread_Core'),
    '1405':('Bone_East_03','Black_Thread_Core'),
    '1406':('Ant_05b','Black_Thread_Core'),
    '1408':('Shellwood_15','Black_Thread_Core'),
    '1410':('Shellwood_02','Black_Thread_Core'),
    '1412':('Coral_32','Black_Thread_Core'),
    '1413':('Ant_04_left','Black_Thread_Core'),
    '1414':('Greymoor_16','Black_Thread_Core'),
    '1416':('Greymoor_11','Black_Thread_Core'),
    '1417':('Greymoor_12','Black_Thread_Core'),
    '1424':('Song_04','Black_Thread_Core'),
    '1425':('Under_05','Black_Thread_Core'),
    '1426':('Under_18','Black_Thread_Core'),
    '1427':('Song_15','Black_Thread_Core_Citadel'),
    '1428':('Song_17','Black_Thread_Core_Citadel'),
    '1429':('Song_27','Black_Thread_Core_Citadel'),
    '1430':('Hang_03','Black_Thread_Core_Citadel'),
    '1431':('Hang_13','Black_Thread_Core'),
    '1432':('Song_05','Black_Thread_Core_Citadel'),
    '1435':('Library_06','Black_Thread_Core_Citadel'),
}
FLAGS.update({key:f'@bool,{scene},{item},true' for key,(scene,item) in CORE_LOCATIONS.items()})

# Additional room matches: lever components were followed to their connected
# gates, and the currency pickup's persistence component was checked directly.
SCENE_LOCATIONS = {
    '1378':('Bone_East_18','ant_lever_persistent (1)'),
    '1466':('Bone_01','Bone Lever'),
    '760':('Greymoor_15b','Greymoor Stand Lever'),
    '1332':('Hang_06_bank','Geo Small Persistent (1)'),
    '1274':('Under_05','Song_lever_side'),
    '790':('Greymoor_08','greymoor_drop_propeller'),
    '1236':('Library_05','attic_ladder'),
}
FLAGS.update({key:f'@bool,{scene},{item},true' for key,(scene,item) in SCENE_LOCATIONS.items()})

# Deliberate, reviewed corrections: related story events are not ownership.
CORRECTIONS = {
    '1039':'@collectable,White Flower',
    # The archived marker points at Bone_East_03, but its pin position matches
    # Bone_East_02b. Bone_East_03's distinct core is pin 1405.
    '1402':'@bool,Bone_East_02b,Black_Thread_Core,true',
}


def alternative_unavailable(marker, raw):
    variants = {'1183':1, '911':2, '912':3}
    chosen = get_path(raw, 'playerData.QuillState')
    return marker['id'] in variants and type(chosen) is int and chosen in (1,2,3) and chosen != variants[marker['id']]


def supplemental_flag(marker):
    # Never replace a source predicate silently.
    return '' if marker.get('flag') else FLAGS.get(marker['id'],'')


def route_waypoint_reason(marker):
    """Access hints are destinations to visit, not evidence of visiting them."""
    if marker['cat'] == 'shortcut' and marker['name'].startswith('Requires '):
        return 'Route waypoint. Having the required ability or opening this gate does not prove the destination was visited; mark it visited after exploring it.'
    return None


def reference_reason(marker):
    """Describe this pin's role, not whether the game saves visits to it."""
    cat, name = marker['cat'], marker['name']
    if cat == 'benches': return 'Rest location. This pin does not track visits or rest history.'
    if cat in ('npc','vendor') or (cat=='maps' and name.startswith('Map Vendor')):
        return 'Character or shop location. Individual purchases and objectives are tracked by their own pins.'
    if cat == 'info': return 'Reference location, not a one-time completion objective.'
    if cat == 'shortcut' and name.startswith('Unlocked during '):
        return 'Availability annotation for a wish reward, not a separately traversed route.'
    if cat == 'shortcut' and name.startswith(('Requires ', 'Intersection -', 'Requirement Unknown')):
        return 'Route information. This pin does not establish whether the route has been traversed.'
    if marker['id'] == '1401' and cat == 'wish':
        return 'Legacy map entry for content removed before the installed game version; it has no current save state.'
    return None


def unresolved_reason(marker):
    if marker['name'].startswith('Wish Progress'):
        return 'The exact save record for this individual objective location has not been verified. Completing the overall quest is not proof of this pickup.'
    if marker['cat'] == 'shortcut':
        return 'The save record for opening this particular route has not been verified.'
    return 'This objective may be recorded in the save, but its exact tracking rule still needs verification.'
