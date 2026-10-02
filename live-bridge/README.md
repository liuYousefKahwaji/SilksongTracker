# Optional live Hornet position

The BepInEx bridge sends Hornet's current room and world position to the Silksong Tracker running on the same computer. The Hornet-head marker is shown on the browser tracker’s **Sketch** map only. This mod does not add anything to the game's map, write saves, or contact the internet.

## Install or update (Windows)

1. Install BepInEx for Unity Mono in the game folder beside `Hollow Knight Silksong.exe`. Launch and quit Silksong once to create `BepInEx/config`, then make sure the game is closed.
2. Start the Silksong Tracker once so its private `.live-bridge-token` exists.
3. From the tracker folder, run:

   ```powershell
   py tools/install_live_bridge.py --game-dir "C:\path\to\Hollow Knight Silksong" --dll "C:\path\to\SilksongLiveBridge.dll"
   ```

   Omit `--dll` when building from source. For an existing bridge, add `--upgrade`; the installer replaces only its DLL and retains the token and settings. Use `--port NUMBER` only if the tracker is not on port 7397.
4. Start the tracker, then Silksong. Open `/map`, choose **Sketch**, and look for **Live: connected**. Keep `.live-bridge-token` and the matching BepInEx config private.

## Build from source

With the game and BepInEx installed, build from the repository root:

```powershell
dotnet build live-bridge/SilksongLiveBridge.csproj -c Release -p:GameDir="C:\path\to\Hollow Knight Silksong"
```

The output is `live-bridge/bin/Release/netstandard2.1/SilksongLiveBridge.dll`.

## Room coverage and placement quality

Version 0.3.6 embeds mappings for every one of the 549 installed scene bundles with room-size data. The mappings comprise 469 rooms with in-game map geometry, 51 fixed in-game map anchors, 26 last-known/area anchors for special scenes without independent overworld geometry, and three legacy room transforms. The generated table is `data/live_native_rooms.json`; the full audit is `data/live_room_inventory.json`.

The bridge resolves the active gameplay scene first. `HeroController` is placed in Unity's `DontDestroyOnLoad` scene, which is a persistent object container and not the room; using it as the room ID made every such position unmapped. If the active scene is not in the room table, the bridge checks Hornet's scene and then loaded room scenes. A one-time log entry reports the active, hero, and selected scene names plus the mapping mode.

Placement modes are intentionally distinct:

- **Room geometry** uses the game's own per-room map sprite bounds and follows movement within that room.
- **Room anchor** marks the exact fixed map location supplied by the game, but cannot follow movement inside a room that has no map outline.
- **Area / last-known anchor** places a special scene at its parent area or retains Hornet's last mapped point; this is not interior navigation.
- **Legacy room transform** applies the research-era room-local Sketch transform for three scenes without a native room-map sprite. These are estimates and may need visual correction.

This is full data coverage, not a claim that every room has been verified against a live playthrough. The game scene/map assets provide automatic placements, but only in-game observation can confirm every transform aligns perfectly. Manual calibration is optional: use **Calibrate current room**, mark Hornet's location, move a good distance without changing rooms, capture the second point, and mark the new location. Calibration is stored only in this browser. You should not need to calibrate every room.

## Spoiler-free checks and troubleshooting

You can verify live tracking without visiting a new area: start the tracker and game, open Sketch, and check that the status connects and that the displayed scene name matches the room you are already in. For geometry-backed rooms the marker should follow movement; an anchor/last-known mode will state its limitation. To check a problem area, report the scene name and mode shown by the tracker, plus whether the marker is absent, static, or visibly offset. Do not include a save file or token.

If the status says **Live: waiting**, make sure the tracker is running, the mod's `[Bridge] Enabled` option is `true`, and the bridge token matches the tracker's `.live-bridge-token`. If it reports `unmapped`, check `BepInEx/LogOutput.log` for the resolver line. If a room has a scene name missing from `data/live_room_inventory.json`, it is a coverage defect; if it has a mapping but the marker is offset, it is an alignment defect and may be corrected by optional calibration.

The bridge defaults to disabled if installed manually. The installer enables it. Set `Enabled = false` or remove `BepInEx/plugins/SilksongLiveBridge.dll` to disable live tracking. Any old `[Map Overlay]` configuration values are unused. The former in-game overlay source, adapter, docs, and v0.3.5 DLL are retained in `archive/map-overlay-v0.3.5/` for recovery; they are not part of the active plugin.
