# Tracking accuracy follow-up — 2026-09-20

**Spoilers below.** This is an evidence record, not a claim of complete late-game playtesting.

## Result

Eighteen previously unresolved pins now have rules (16 scene objects and two permanent unlocks): coverage is 1,206 save-rule pins, 166 reference locations, and 47 unresolved objectives out of 1,419. Missing or malformed authoritative data remains unknown. These changes do not modify game saves.

## Completion corrections

Read-only inspection of the installed game's `PlayerData.CountGameCompletion` confirmed that Sylphsong uses `HasBoundCrestUpgrader`, not `HasSeenEvaHeal`. Everbloom uses the computed `HasWhiteFlower` property, whose serialized source is `Collectables` → `White Flower` → `Data.Amount > 0`, not `CompletedRedMemory`. The property itself is not a serialized boolean.

The encounter checklist now uses the completed Pinstress Battle wish instead of `PinstressPeakBattleAccepted`, which only records acceptance. Missing explicit checklist fields no longer fall back to related source-map story flags. Pin 1039 receives a separate reviewed correction rather than silently changing upstream data.

The inspected completion formula also counts grouped unlocked tools, visible base-version crests minus the starting crest, nail/kit/pouch upgrades, silk regeneration, six ability flags, health above five, and silk above nine. Regression tests exercise the counters and ability flags; every late-game transition remains unvalidated.

The equipment follow-up inspected `ToolItem.IsUnlockedNotHidden`, `ToolItemManager.GetUnlockedTools`/`GetCount`, and the installed tool definitions. Hidden tools must not count. Skill tools unlock from either `Tools.savedData.IsUnlocked` or the corresponding ability flag, and still require visibility. These paths now share a completion evaluator. The five multi-variant tool groups match the definitions' shared count keys; only the six skill tools have alternate unlock tests in the main tool bundle. A synthetic 100-point fixture includes all tool variants simultaneously, verifies no duplicate points, excludes an uncounted tool, and drops to 99 when one counted tool is hidden. This does not prove all assets are reachable in an ordinary playthrough.

## Two permanent unlocks

- Pin 695 (Beastling Call): `playerData.UnlockedFastTravelTeleport`. The field is present in installed PlayerData; the [BasicItemSync author's implementation](https://old.thunderstore.io/c/hollow-knight-silksong/p/BobbyTheCatfish/BasicItemSync/source/) explicitly maps it to this ability. Ordinary Bellway access and encountering the boss do not grant this pin.
- Pin 1038 (Plasmium Gland): `Collectables.savedData`, name `Plasmium Gland`, `Data.Amount > 0`. Installed `PlayerData.HasLifebloodSyringeGland` computes precisely this quantity check; the item definition identifies the gland and has no use responses. A related encounter flag is not used as proof of ownership.

Local inspection provenance: Steam build 22479045; Assembly-CSharp SHA-256 `70713BB2B1F1B0C4C6B7007FA6A8446CF79818CB5E308C48C094C4D1DE7114BB`. The checked real save reports version 1.0.30000. These identifiers scope the evidence; they do not establish compatibility with every release. Decompiled code and extracted assets are not included in this repository.

## Additional map identities

Candidate scene/object identifiers were cross-checked against [the secondary tracker dataset](https://github.com/th3r3dfox/silksong-tracker/blob/main/src/data/mini-bosses.json), installed scene objects, and existing [source-map placements](https://scripterswar.com/silksong/map). Matching used at least two agreeing room anchors and a coordinate transform. Thus pin-to-object identity is a researched coordinate inference, not a witnessed before/after transition. Runtime completion uses only the exact persisted scene/object boolean, never proximity or aggregate quest progress.

| Pin | Scene | Persistent object |
| --- | --- | --- |
| 1395 | Bone_04 | Black_Thread_Core |
| 1396 | Mosstown_02 | Black_Thread_Core |
| 1398 | Bone_07 | Black_Thread_Core |
| 1407 | Shellwood_26 | Black_Thread_Core |
| 1409 | Shellwood_01b | Black_Thread_Core |
| 1415 | Greymoor_07 | Black_Thread_Core |
| 1418 | Dust_03 | Black_Thread_Core |
| 1419 | Greymoor_02 | Black_Thread_Core |
| 1421 | Shadow_05 | Black_Thread_Core |
| 1423 | Song_01 | Black_Thread_Core_Citadel |
| 1433 | Library_04 | Black_Thread_Core_Citadel |
| 1434 | Library_04 | Black_Thread_Core_Citadel (1) |

Installed persistence code confirms scene-plus-object identity and the boolean value. Ambiguous candidates, inconsistent room anchors, and known bad placements were not adopted. The two Library objects have separate keys and tests preventing one from completing the other.

## Verification and limits

Four further room matches use the same anchor method, with component inspection confirming the saved type and event. Pin 1378 maps to `Bone_East_18 / ant_lever_persistent (1)` (two anchors, 3.61 coordinate units residual), whose Lever opens `ant_gate_animated (1)`. Pin 1466 maps to `Bone_01 / Bone Lever` (two anchors, 3.48 residual), connected to `Great Bone Gate`. Pin 760 maps to `Greymoor_15b / Greymoor Stand Lever` (seven anchors, 1.24 residual), connected to `grey_lever_gate`. These components save their activated state through PersistentBoolItem. Pin 1332 maps to `Hang_06_bank / Geo Small Persistent (1)` (eight anchors, 1.13 residual), a GeoControl pickup with PersistentBoolItem. All four use exact scene/object keys; the tests reject adjacent objects and the same object name in another room. Pin 1223 was investigated but remains unresolved: its nearby sliding platform is reversible, so its current node is not sufficient evidence of permanently opening the route.

43 unit tests cover the existing rules plus corrected completion sources, acceptance versus victory, independent scene objects, conflicting scene and named records, malformed fields, strict boolean/numeric types, missing authoritative data, hidden equipment, alternate skill unlocks, and the full-completion boundary. Synthetic progression tests are not real late-game saves.

Browser smoke checks exercised the Sketch/Screenshots switch and Only left filter against the local API: displayed pin counts matched eligible markers in each coordinate set, with no broken images detected. These checks do not establish that every source-map placement is visually exact.

`py tools/validate_progress.py` checks discovered saves without modifying or uploading them. Output contains counts, schema version, and a before/after file-hash comparison, not item names or personal paths. The current real-save check resolves all 193 checklist entries and reports an unchanged file; this is early-game schema evidence, not a full playthrough validation. Explicit save paths can be supplied for privately obtained representative samples.

Still needed: exact identities for the remaining 47 objectives, genuine before/after late-game samples, reachable equipment/crest state checks, and broader version/slot/platform testing. Future samples should be volunteered privately with consent; an early-game player need not visit spoiler locations or publicly share saves.
