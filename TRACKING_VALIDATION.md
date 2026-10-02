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

## 2026-09-23 follow-up

The current suite has 46 passing unit tests. Data validation finds 100 official points, 1,419 source pins, and all expected locally downloaded map assets. The read-only real-save check still resolves all 193 checklist entries for version 1.0.30000 and confirms the file hash did not change. These results do not close the late-game evidence gap above.

Browser checks covered manual-mark export, clear, and restore; a malformed import retained the prior mark. The acquired-only checklist reduced the tested save's visible entries from 193 to 46 and persisted after reload. The full map remains spoiler-bearing. The six pins without Sketch coordinates are absent from the upstream Sketch placement data; no positions were inferred for them, and one upstream placement is explicitly marked suspect.

## 2026-09-28 completion and full room-inventory pass

**Spoilers below.** This records static-data progress and regression coverage, not a completed playthrough. The player does not currently own the game, so no new live transition or visual alignment test was possible.

The current map-pin audit classifies all 1,419 pins: 1,136 automatic-save, 163 reference-only, 115 route waypoints, and 5 unverified. Exact save rules were added for persistent shortcut states, item rewards and grouped pickups, newly identified core/object locations, and room objects whose persistence records were checked. A legacy pin was corrected to the exact scene/object identity supported by its placement; the old related-scene mapping is no longer treated as the same pickup. Requirement pins are visit waypoints, not completion objectives: an acquired ability or opened gate only describes access, so these remain outstanding until manually marked visited. Aggregate pins that represent several physical pickups now use the explicit `@all` evaluator: all components must be complete, a known incomplete component prevents overall completion, and absent/malformed state cannot be silently upgraded to complete. Positive/negative/missing-data behaviors have regression tests. A further search of installed scene/collectible data and a community-datamined pickup list did not prove exact identities for the five remaining pins, so they remain manually markable rather than being assigned a nearby or aggregate state. The pickup list provides useful scene/item records but is not a per-pin save-transition specification ([source](https://gist.github.com/flibber-hk/5e38f9ae7d3ed5d090b25bf6dc67bd7f)).

The five deliberately unresolved cases are: three one-way shortcut pins without a verified exact route-state record; the Rosary Necklace pin, whose unique persisted reward identity was not established; and Beast Shard, for which no matching installed collectible definition or target-scene persistent object was found. No proximity, quest completion, neighboring event, or aggregate inventory shortcut was used to fabricate these mappings. Those pins remain manually markable. The generated, itemized classification is `data/map_tracking_audit.json`.

A final external cross-check used [a datamined CollectableItemPickup/SavedItemTrackerMarker inventory](https://gist.github.com/flibber-hk/5e38f9ae7d3ed5d090b25bf6dc67bd7f) and [BingoUI's counter documentation](https://thunderstore.io/c/hollow-knight-silksong/p/flibber/BingoUI/). The former records pickup scene/object and saved-item names/types; it did not establish a unique, location-specific save predicate for these pins. The latter describes resource counters based on ever-picked-up inventory totals, which cannot identify which map location supplied an item. This corroborates the decision not to infer per-pin completion from an aggregate count; it does not prove no hidden exact save record exists.

The latest audit scanned all 2,068 installed asset bundles and found 549 with a game `SceneSize` component. All 549 have a positioning mode and none are unmapped: 469 game-map room-geometry records, 51 fixed in-game map anchors, 26 last-known/area anchors, and three scenes that rely on legacy room transforms. All 300 runtime scenes named by persistent-object source-map pins are covered. The 270 legacy Sketch transforms also cover six additional rooms. `Pilgrims Rest` remains excluded because it is a save-key alias for the Toll Door object in `Bone_East_10`, not a room Hornet can occupy. The native-map Sketch fit uses 267 room correspondences (253 inliers); leave-one-room-out errors are RMS 5.130, P90 7.625, maximum 17.563 Sketch units. The 51 fixed anchors do not track within-room movement; 26 scenes with no room-specific map root inherit the last mapped point or use an explicitly approximate area anchor. The three legacy-only scene transforms use screenshot/Sketch landmarks. The regression test requires a documented mode for each of the 549 inventory entries and verifies all map-tagged runtime scenes are covered.

One limitation remains: the supplemental Silk Grub Large Cocoon objective in `Organ_01` has an exact save predicate and a Screenshots placement, but its source marker has no Sketch location and the room has no native in-game map sprite in the extracted map data. It can be tracked as acquired in the checklist and seen on Screenshots, but it cannot be accurately rendered on live Sketch without a legitimate coordinate source. The six pins without upstream Sketch positions (including this item) continue to use their Screenshots placements; no Sketch coordinates are inferred.

Verification on 2026-09-28: all 61 Python unit tests pass; all 13 JavaScript live-position math checks pass; and the BepInEx bridge builds with 0 warnings and 0 errors. The map audit reports 1,136/163/115/5 (automatic-save/reference/waypoint/unverified). The complete installed-bundle scan found 549/549 room-sized scenes covered and 300/300 persistent-object-tagged runtime scenes represented; six more rooms have legacy fallback transforms. These are static or synthetic checks; they do not replace running the mod in Silksong, real save-transition comparisons, or visual testing across rooms. Keep the save reader read-only and ask only for voluntarily shared saves; do not ask an early-game player to visit spoiler locations.

Next verification once the game is available: test the bridge and room fit in a few already-visited rooms, compare known pickups through before/after save snapshots for uncertain rules, and record actual discrepancies rather than broadly retuning coordinate transforms. No spoiler-required test is needed from the current early-game player.

## 2026-09-29 bridge room-resolution correction

The user reported that Blasted Steps and Sands of Karak displayed no calibrated rooms. Inspection of the active API showed the bridge sending scene `DontDestroyOnLoad` with `mapMode: unmapped`. `HeroController` is in Unity's persistent-object scene, so that name cannot match any room entry; this explained why even regions already present in the data appeared empty. Version 0.3.6 now selects the active gameplay scene first, with loaded-room fallback and a once-per-resolution diagnostic log. It also deserializes the embedded room resource with explicit error/count reporting rather than silently accepting a null Unity JSON parse.

The installed asset scan was rerun and the actual bridge resource regenerated: a second scan of all 2,068 bundles found exactly 549 scene-size bundles, all 549 covered. This includes all 31 `coral_*` rooms (29 geometry, two fixed anchors) and 25 `dust_*` rooms (13 geometry, 12 fixed anchors). Three previously browser-only transforms (`Bone_East_LavaChallenge`, `Room_CrowCourt`, `Room_CrowCourt_02`) are embedded and evaluated by the bridge. Regression tests require every inventory scene to exist in that embedded resource. The Silksong in-game map overlay was removed from the active plugin/tracker and its v0.3.5 source/build/adapter were preserved in `archive/map-overlay-v0.3.5/`.

This closes the **coverage and room-key lookup defect** in static data/code; it does not prove 100% geometric accuracy. The game was open during this edit and the new DLL has not yet been installed or observed after a restart. Native geometry, fixed/area anchors, and legacy transforms retain their distinct precision limits; no player can verify all rooms without visiting them. The latest unit suite passes (66 Python tests; 13 JS math checks). A spoiler-free verification can be done in a room the player already knows: restart the mod/tracker, confirm **Live: connected**, and compare the reported scene and marker behavior without traveling anywhere.
