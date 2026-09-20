# Map tracking audit — 2026-09-19

This file and the JSON audit contain game-content names; avoid them during a spoiler-free playthrough.

## Outcome

Follow-up through 2026-09-20: coverage is now 1,206 save-rule pins, 166 reference pins, and 47 unresolved objectives, with 43 tests. See [TRACKING_VALIDATION.md](TRACKING_VALIDATION.md) for 18 additional mappings, reviewed upstream correction, evidence strength, and remaining accuracy gaps. The sections below retain the original audit baseline.

The previous blanket label covered 256 pins. This pass supplies 25 researched rules, classifies 166 pins as reference locations, and leaves 65 objectives explicitly awaiting verified tracking. Together with existing source rules, 1,188 pins now have a tracking rule. Classification does not depend on which save is loaded.

Reference means the **pin's role**, not a claim that the game cannot save visits to that place. Unflagged benches represent rest locations; NPCs and shops represent locations rather than an entire character's progress. Requirement/intersection annotations describe routes, not completion. Bench unlocks and other locations already carrying source predicates keep those predicates.

“Only left” now means confirmed incomplete: reference, unresolved, missing-save, completed, and unavailable-alternative pins are excluded. An explicitly focused deep-link pin remains visible. Search results follow the same filter.

## Evidence

- Original placement and predicate data: archived `source/ssMap.js`; the live [source map](https://scripterswar.com/silksong/map) still serves the same bundle revision.
- [BlueOrcaz gameData](https://github.com/BlueOrcaz/silksong-save-viewer/blob/main/src/lib/gameData.js): quest title/internal-name mappings, equipment, purchase flags, quest rewards and mementos. [ToolPouches](https://github.com/BlueOrcaz/silksong-save-viewer/blob/main/src/lib/components/ToolPouches.svelte) establishes purchase and quest evaluators. The WIP scene rule was not adopted.
- [th3r3dfox wishes](https://github.com/th3r3dfox/silksong-tracker/blob/main/src/data/wishes.json): Runtfeast and Survivor's Camp Supplies internal quest names. [Completion](https://github.com/th3r3dfox/silksong-tracker/blob/main/src/data/completion.json) and [save evaluator](https://github.com/th3r3dfox/silksong-tracker/blob/main/src/save-data.ts): quill alternatives and state values.
- [Architect field documentation](https://starshooter.gitbook.io/architect/architect-silksong/ids/playerdata-bool-ids) and the actual local schema confirm `nuuMementoAwarded`; combined with the source pin's Nuu reward identity this is the mapping used for pin 368. The positive transition is not playthrough-tested.

Supplemental rules are in `silksongtracker/maptracking.py`, bound to stable source IDs. Quest pins are joined by exact title, not quest-list order. The missing mask and spool rewards were checked against their complete inventories (the other 19 mask and 17 spool records account for every other reward/scene), plus their source reward locations. Different datasets' numeric item labels are not treated as matching identifiers.

Quill alternatives use equality, not a greater-than comparison. Owning another variant is displayed as an unavailable alternative, not a missing collectible. Source predicates are never overwritten by these supplements.

## Remaining research

65 unresolved pins: 36 quest-object locations, 15 shortcuts, and 14 other pickups/events. An overall quest flag does not establish the state of a specific quest object. Matching by proximity, number alone, visited room, or aggregate item count would produce false results, so none is used. One unresolved source pin explicitly has a bad-position note; its coordinates and predicate are not guessed.

The itemized audit is `data/map_tracking_audit.json`. Regenerate with `py tools/audit_map_tracking.py`; it reads source data only, never a user's save. Further exact scene/object mappings or before/after transition fixtures are needed for these unresolved entries. Do not ask an early-game player to visit future locations for testing.

## Verification

25 unit tests cover all 25 supplemental rules (positive, negative, missing data), every quill variant, source-predicate preservation, classification without a save, and no inferred individual-object completion from aggregate quests. Actual-save checks are read-only. Synthetic fixtures do not prove late-game transitions; no game save is altered or committed.
