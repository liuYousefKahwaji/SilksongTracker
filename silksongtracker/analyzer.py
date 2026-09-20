"""Evaluate completion content against a decoded save without mutating it."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .database import load_content, load_map
from functools import lru_cache
from .flags import flag_status
from .rules import evaluate
from .schema import SaveView, first
from .maplinks import links

TOOL_MATCHES = [
    ["Straight Pin"], ["Tri Pin"], ["Sting Shard"], ["Tack"], ["Harpoon"], ["Curve Claws", "Curve Claws Upgraded"],
    ["Shakra Ring"], ["Pimpilo"], ["Conch Drill"], ["WebShot Forge", "WebShot Architect", "WebShot Weaver"],
    ["Screw Attack"], ["Cogwork Saw"], ["Cogwork Flier"], ["Rosary Cannon"], ["Lightning Rod"], ["Flintstone"],
    ["Flea Brew"], ["Lifeblood Syringe"], ["Mosscreep Tool 1", "Mosscreep Tool 2"], ["Lava Charm"], ["Bell Bind"],
    ["Poison Pouch"], ["Fractured Mask"], ["Multibind"], ["White Ring"], ["Brolly Spike"], ["Quickbind"],
    ["Spool Extender"], ["Reserve Bind"], ["Dazzle Bind", "Dazzle Bind Upgraded"], ["Revenge Crystal"], ["Thief Claw"],
    ["Zap Imbuement"], ["Quick Sling"], ["Maggot Charm"], ["Longneedle"], ["Wisp Lantern"], ["Flea Charm"],
    ["Pinstress Tool"], ["Compass"], ["Bone Necklace"], ["Rosary Magnet"], ["Weighted Anklet"], ["Barbed Wire"],
    ["Dead Mans Purse", "Shell Satchel"], ["Magnetite Dice"], ["Scuttlebrace"], ["Wallcling"], ["Musician Charm"],
    ["Sprintmaster"], ["Thief Charm"],
]
SILK_SKILL_FLAGS = ["hasNeedleThrow", "hasThreadSphere", "hasParry", "hasSilkCharge", "hasSilkBomb", "hasSilkBossNeedle"]
SILK_SKILL_TOOLS = ['Silk Spear','Thread Sphere','Parry','Silk Charge','Silk Bomb','Silk Boss Needle']
ABILITY_FLAGS = {"Needolin":"hasNeedolin", "Swift Step":"hasDash", "Cling Grip":"hasWalljump", "Clawline":"hasHarpoonDash", "Silk Soar":"hasSuperJump", "Sylphsong":"HasSeenEvaHeal", "Needle Strike":"hasChargeSlash"}
CREST_FLAGS = {"Reaper Crest":"Reaper", "Wanderer Crest":"Wanderer", "Beast Crest":"Warrior", "Witch Crest":"Witch", "Architect Crest":"Toolmaster", "Shaman Crest":"Spell"}
BOSS_FLAGS = {"Bell Beast":"defeatedBellBeast", "Phantom":"defeatedPhantom", "Lace":"defeatedLaceTower", "Widow":"visitedBellhartSaved", "First Sinner":"defeatedFirstWeaver", "The Unravelled":"wardBossDefeated", "Trobbio":"defeatedTrobbio", "Tormented Trobbio":"defeatedTormentedTrobbio", "Voltvyrm":"defeatedZapCoreEnemy", "Broodmother":"defeatedBroodMother", "Second Sentinel":"defeatedSongChevalierBoss", "Clover Dancers":"defeatedCloverDancers", "Sister Splinter":"defeatedSplinterQueen", "Savage Beastfly":"defeatedBoneFlyerGiant", "Great Conchflies":"defeatedCoralDrillers", "Last Judge":"defeatedLastJudge", "Cogwork Dancers":"defeatedCogworkDancers", "Disgraced Chef Lugoli":"defeatedRoachkeeperChef", "Father of the Flame":"defeatedWispPyreEffigy", "Groal the Great":"DefeatedSwampShaman", "Palestag":"defeatedWhiteCloverstag", "Gurr the Outcast":"defeatedAntTrapper", "Pinstress":"PinstressPeakBattleAccepted", "Shrine Guardian Seth":"defeatedSeth", "Nyleth":"defeatedFlowerQueen", "Skarrsinger Karmelita":"defeatedAntQueen", "Crust King Khann":"defeatedCoralKing", "Lost Garmond":"garmondBlackThreadDefeated", "Plasmified Zango":"BlueScientistDead"}
BELLWAY_FLAGS = {"Marrow":"UnlockedFastTravel", "Bone Bottom":"UnlockedFastTravel", "Deep Docks":"UnlockedDocksStation", "Far Fields":"UnlockedBoneforestEastStation", "Greymoor":"UnlockedGreymoorStation", "Bellhart":"UnlockedBelltownStation", "Shellwood":"UnlockedShellwoodStation", "Blasted Steps":"UnlockedCoralTowerStation", "The Slab":"UnlockedPeakStation", "Grand Bellway":"UnlockedCityStation", "Bilewater":"UnlockedShadowStation", "Putrified Ducts":"UnlockedAqueductStation"}
VENTRICA_FLAGS = {"Terminus":["UnlockedArboriumTube", "UnlockedHangTube", "UnlockedSongTube", "UnlockedCityBellwayTube", "UnlockedUnderTube", "UnlockedEnclaveTube"], "Memorium":"UnlockedArboriumTube", "High Halls":"UnlockedHangTube", "First Shrine":"UnlockedEnclaveTube", "Choral Chambers":"UnlockedSongTube", "Grand Bellway":"UnlockedCityBellwayTube", "Underworks":"UnlockedUnderTube"}


def known_rule(entry: dict) -> dict | None:
    entry_id = entry.get("id", "")
    name = entry.get("name", "")
    # Checked against PlayerData.CountGameCompletion in the installed game.
    if name == 'Sylphsong': return {'type':'bool','path':'playerData.HasBoundCrestUpgrader'}
    if entry_id == 'items-01': return {'type':'source_flag','flag':'@collectable,White Flower'}
    if entry_id.startswith('bosses-') and name == 'Pinstress':
        return {'type':'source_flag','flag':'@wish,Pinstress Battle'}
    number = int(entry_id.rsplit('-',1)[-1]) if entry_id.rsplit('-',1)[-1].isdigit() else 0
    if entry_id.startswith('upgrades-'):
        field = 'ToolKitUpgrades' if number <= 4 else 'ToolPouchUpgrades'
        return {'type':'int','path':'playerData.'+field,'value':number if number <= 4 else number-4}
    for prefix, field, baseline in [('mask-upgrades-', 'maxHealthBase', 5), ('silk-upgrades-', 'silkMax', 9), ('silk-hearts-', 'silkRegenMax', 0)]:
        if entry_id.startswith(prefix): return {'type':'int','path':'playerData.'+field,'value':baseline+number}
    if entry_id == 'fleas-21': return {'type':'source_flag','flag':'@bool,GLOBAL_SHARED,Caravan Troupe Hunter,true'}
    extra_bosses = {'Moss Mother':'defeatedMossMother', 'Lace':'defeatedLace1', 'Fourth Chorus':'defeatedSongGolem', 'Forebrothers Signis & Gron':'defeatedDockForemen', 'Moorwing':'defeatedVampireGnatBoss', 'Crawfather':'defeatedCrowCourt', 'Savage Beastfly II':'defeatedBoneFlyerGiantGolemScene', 'Skull Tyrant':'skullKingDefeated', 'Watcher at the Edge':'defeatedGreyWarrior', 'Raging Vonchfly':'defeatedCoralDrillerSolo'}
    if entry_id.startswith('bosses-') and name in extra_bosses: return {'type':'bool','path':'playerData.'+extra_bosses[name]}
    journal = {'Bell Eater':'Giant Centipede', 'Shakra':'Shakra', 'Grand Mother Silk':'Silk Boss', 'Lost Lace':'Lost Lace', 'Summoned Saviour':'Abyss Mass', 'Garmond & Zaza':'Garmond_Zaza'}
    if entry_id.startswith('bosses-') and name in journal: return {'type':'journal','name':journal[name]}
    if entry_id.startswith("tools-"):
        index = int(entry_id.rsplit("-", 1)[-1]) - 1
        if 0 <= index < len(TOOL_MATCHES): return {'type':'tool_completion','names':TOOL_MATCHES[index]}
    if entry_id.startswith("silk-skills-"):
        index = int(entry_id.rsplit("-", 1)[-1]) - 1
        if 0 <= index < len(SILK_SKILL_FLAGS): return {'type':'tool_completion','names':[SILK_SKILL_TOOLS[index]],'alternate':SILK_SKILL_FLAGS[index]}
    if name in ABILITY_FLAGS: return {"type":"bool", "path":f"playerData.{ABILITY_FLAGS[name]}"}
    if name in CREST_FLAGS: return {"type":"list_item_bool", "path":"playerData.ToolEquips.savedData", "match":CREST_FLAGS[name], "valuePath":"Data.IsUnlocked"}
    if entry_id.startswith("needle-upgrades-"):
        return {"type":"int", "path":"playerData.nailUpgrades", "op":">=", "value":int(entry_id.rsplit("-", 1)[-1])}
    if name in BOSS_FLAGS: return {"type":"bool", "path":f"playerData.{BOSS_FLAGS[name]}"}
    if entry_id.startswith("bellways-") and name in BELLWAY_FLAGS: return {"type":"bool", "path":f"playerData.{BELLWAY_FLAGS[name]}"}
    if entry_id.startswith("ventrica-") and name in VENTRICA_FLAGS:
        flags = VENTRICA_FLAGS[name]
        return {"type":"all", "rules":[{"type":"bool", "path":f"playerData.{x}"} for x in (flags if isinstance(flags,list) else [flags])]}
    return None


@lru_cache(maxsize=1)
def source_flags():
    return {m['id']:m.get('flag','') for m in load_map()['markers']}


def _entry_result(entry: dict, save: SaveView | None) -> dict:
    rule = entry.get("rule") or known_rule(entry)
    if rule is None and entry.get("probe"):
        # Probes are deliberately conservative aliases.  They let a future
        # schema adapter light up entries without changing the content file.
        rule = {"type": "any", "rules": [{"type": "bool", "path": path} for path in entry["probe"]]}
    result = evaluate(rule, save)
    link = links().get(entry.get('id'))
    if rule is None and save is not None and link and link['kind'] != 'components':
        outcomes = [flag_status(source_flags().get(marker_id),save.raw) for marker_id in link['ids']]
        if 'complete' in outcomes: result = 'complete'
        elif outcomes and all(x == 'left' for x in outcomes): result = 'left'
    return {**entry, "status": result, "known": result != "unknown", "map": links().get(entry.get('id'))}


def analyze(raw: dict | None, slot: int | None = None, path: str | None = None) -> dict:
    content = load_content()
    save = SaveView(raw) if raw is not None else None
    groups: list[dict] = []
    total = complete = left = unknown = 0
    for section in content.get("sections", []):
        entries = [_entry_result(item, save) for item in section.get("entries", [])]
        counted = [x for x in entries if x.get("counts", True)]
        total += len(counted)
        complete += sum(x["status"] == "complete" for x in counted)
        left += sum(x["status"] == "left" for x in counted)
        unknown += sum(x["status"] == "unknown" for x in counted)
        groups.append({**section, "entries": entries, "complete": sum(x["status"] == "complete" for x in counted), "total": len(counted), "entryTotal": len(entries)})
    player = save.player if save else {}
    return {
        "game": "Hollow Knight: Silksong",
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "slot": slot,
        "path": path,
        "hasSave": raw is not None,
        "saveStatus": "loaded" if raw is not None else "waiting",
        "saveVersion": first(raw or {}, ("playerData.version", "version", "gameVersion", "buildVersion", "playerData.gameVersion"), None),
        "playerName": first(raw or {}, ("playerName", "playerData.playerName", "name"), None),
        "summary": {"complete": complete, "total": total, "left": left, "unknown": unknown, "percent": round(complete / total * 100, 1) if total else 0},
        "completion": {"officialCap": content.get("officialCap", 100), "trackedPoints": content.get("trackedPoints", 100), "notes": content.get("completionNotes", [])},
        "groups": groups,
    }
