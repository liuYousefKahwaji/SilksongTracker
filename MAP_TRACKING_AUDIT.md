# Map tracking audit — 2026-09-29

This file and the JSON audit contain game-content names; avoid them during a spoiler-free playthrough.

## Current outcome — 2026-09-29

All 1,419 source-map pins are classified: 1,136 have automatic save rules, 163 are reference locations, 115 are route waypoints, and five objectives remain unverified. The machine-readable current result is `data/map_tracking_audit.json`; regenerate it with `py tools/audit_map_tracking.py`. Since the previous 2026-09-20 snapshot (47 unverified), 42 entries received evidence-backed rules or reference classifications. This pass also corrected 115 `Requires …` pins: access/ability flags describe whether a route is available, not whether its destination was visited, so they now remain manual waypoints. A follow-up search of the installed build's scene and collectible data did not establish exact identities for the five remaining pins. They are deliberately left manual rather than assigning a neighboring object's or an aggregate counter's state.

The 1,136 automatic save rules include exact scene/object identities and composite predicates for source pins that combine multiple pickups. `@all` completes only when every listed save record is complete; any known incomplete component keeps the group incomplete, while missing or malformed evidence remains unknown. `@any` completes when any component is complete, remains incomplete only when every component is known incomplete, and otherwise remains unknown. This avoids converting partial aggregate pickups into false completion.

The five remaining unverified pins are three one-way shortcut transitions with no verified persistent route-specific record, one Rosary Necklace whose exact unique reward identity is not established, and one Beast Shard absent from the installed collectible definitions and target-scene object data examined for this build. The community-datamined pickup list checked as a cross-reference did not establish either item's unique map-pin/save identity; that list is useful scene/item evidence, not proof of a save transition ([source](https://gist.github.com/flibber-hk/5e38f9ae7d3ed5d090b25bf6dc67bd7f)). They remain manually markable. The exact cases and reasons are in the audit JSON. Related room visits, reversible platforms, nearby enemies, quest completion, and aggregate inventory counts are not accepted as substitutes for the missing exact identity.

The full room audit scanned all 2,068 installed asset bundles and found 549 bundles with a game `SceneSize` component. All 549 now have entries in both `data/live_room_inventory.json` and the exact `data/live_native_rooms.json` embedded in the bridge: 469 use game-map room geometry, 51 have fixed game-map room anchors but no room outline, 26 use an area/last-known anchor because the scene has no room-specific map root, and three use embedded legacy room-local transforms. All 300 runtime scenes referenced by persistent-object map pins are covered; 270 legacy Sketch transforms also provide additional browser fallback support. Blasted Steps (`coral_*`) and Sands of Karak (`dust_*`) are present in the room table. The separate `Pilgrims Rest` save-key alias is not a runtime room. These counts describe asset coverage, not equal precision: room anchors do not move within the room, area/last-known positions are explicitly approximate, and legacy estimates need visual checks. One supplemental interior pickup in `Organ_01` has a Screenshots placement and exact save predicate but no source Sketch coordinate or native map sprite, so it cannot be positioned on Sketch from verified data. See [TRACKING_VALIDATION.md](TRACKING_VALIDATION.md) for methods and test scope.

## Historical baseline — 2026-09-19

The snapshot recorded through 2026-09-20 had 1,206 save-rule pins, 166 reference pins, and 47 unresolved objectives, with 43 tests. See [TRACKING_VALIDATION.md](TRACKING_VALIDATION.md) for the dated progression of researched mappings and evidence. The sections below retain the historical baseline and are not current counts.

The previous blanket label covered 256 pins. This pass supplies 25 researched rules, classifies 166 pins as reference locations, and leaves 65 objectives explicitly awaiting verified tracking. Together with existing source rules, 1,188 pins now have a tracking rule. Classification does not depend on which save is loaded.

Reference means the **pin's role**, not a claim that the game cannot save visits to that place. Unflagged benches represent rest locations; NPCs and shops represent locations rather than an entire character's progress. Requirement/intersection annotations describe routes, not completion. Requirement pins are waypoints even when the source map attaches an ability or gate flag; those flags can no longer hide destinations the player has not explored.

“Only left” includes confirmed incomplete objectives, unresolved objectives manually marked incomplete, and route waypoints until manually marked visited. Reference, missing-save completion objectives, completed objectives, and unavailable alternatives are excluded. An explicitly focused deep-link pin remains visible. Search results follow the same filter.

## Evidence in the original audit pass

- Original placement and predicate data: archived `source/ssMap.js`; the live [source map](https://scripterswar.com/silksong/map) still serves the same bundle revision.
- [BlueOrcaz gameData](https://github.com/BlueOrcaz/silksong-save-viewer/blob/main/src/lib/gameData.js): quest title/internal-name mappings, equipment, purchase flags, quest rewards and mementos. [ToolPouches](https://github.com/BlueOrcaz/silksong-save-viewer/blob/main/src/lib/components/ToolPouches.svelte) establishes purchase and quest evaluators. The WIP scene rule was not adopted.
- [th3r3dfox wishes](https://github.com/th3r3dfox/silksong-tracker/blob/main/src/data/wishes.json): Runtfeast and Survivor's Camp Supplies internal quest names. [Completion](https://github.com/th3r3dfox/silksong-tracker/blob/main/src/data/completion.json) and [save evaluator](https://github.com/th3r3dfox/silksong-tracker/blob/main/src/save-data.ts): quill alternatives and state values.
- [Architect field documentation](https://starshooter.gitbook.io/architect/architect-silksong/ids/playerdata-bool-ids) and the actual local schema confirm `nuuMementoAwarded`; combined with the source pin's Nuu reward identity this is the mapping used for pin 368. The positive transition is not playthrough-tested.

Supplemental rules are in `silksongtracker/maptracking.py`, bound to stable source IDs. Quest pins are joined by exact title, not quest-list order. The missing mask and spool rewards were checked against their complete inventories (the other 19 mask and 17 spool records account for every other reward/scene), plus their source reward locations. Different datasets' numeric item labels are not treated as matching identifiers.

Quill alternatives use equality, not a greater-than comparison. Owning another variant is displayed as an unavailable alternative, not a missing collectible. Source predicates are never overwritten by these supplements.

## Historical remaining-research snapshot

65 unresolved pins: 36 quest-object locations, 15 shortcuts, and 14 other pickups/events. An overall quest flag does not establish the state of a specific quest object. Matching by proximity, number alone, visited room, or aggregate item count would produce false results, so none is used. One unresolved source pin explicitly has a bad-position note; its coordinates and predicate are not guessed.

The itemized audit is `data/map_tracking_audit.json`. Regenerate with `py tools/audit_map_tracking.py`; it reads source data only, never a user's save. Further exact scene/object mappings or before/after transition fixtures are needed for these unresolved entries. Do not ask an early-game player to visit future locations for testing.

## Historical verification snapshot

25 unit tests cover all 25 supplemental rules (positive, negative, missing data), every quill variant, source-predicate preservation, classification without a save, and no inferred individual-object completion from aggregate quests. Actual-save checks are read-only. Synthetic fixtures do not prove late-game transitions; no game save is altered or committed.
