# Optional live Hornet position (experimental)

## In-game tracker-map overlay (local build v0.3.5-beta)

With the tracker running and its map data installed, open the **full menu map** and press **F8** or **Menu Extra**. The overlay reads the tracker's local `/api/game-map` endpoint and downloaded tiles over loopback; it does not fetch map assets itself. It is scoped to `InventoryMapManager`, so Quick Map is left alone.

It includes the tracker's **Sketch** and **Screenshots** tile styles; source map pins and icons; save-derived completion state and tracking notes; text search; only-left filtering; zoom, pan and whole-map framing; a Hornet-centering action on Sketch; group/category visibility; and shortcut subfilters (ability requirements, one-way arrows, intersections, and other route notes). Parent layer controls show checked/unchecked/partial state and apply to their children. Manual browser-only marks from the tracker website are not synced into the game overlay.

Controls:

- **Keyboard:** F8 opens the overlay; Esc closes it; Tab or F8 cycles focus through map, layers, and controls; M changes map style; Home fits the whole map; `+`/`-` zoom; arrows pan when map-focused; search + Enter selects the first result.
- **Controller:** Menu Extra opens the overlay and cycles focus through map, layers, and controls; Menu Cancel closes it; left stick pans while the right stick moves a visible cursor over map pins. Submit inspects the pin under the cursor, activates a focused control/layer, or retries loading the map; retry also happens automatically. D-pad pans on the map or navigates layer rows/toolbar controls according to focus. Toolbar focus exposes style, zoom, whole-map, Hornet-center, and only-left controls. Menu Super zooms in; pane shoulder actions zoom in/out.
- **Sound:** the mod tries to play the existing map-marker cursor clip on panel/focus actions. It is silent if the full-map prefab does not expose that clip.

While open, Harmony prefixes skip the game's global `InputHandler.Update` pause/game-input routing and `InventoryPaneInput.Update`, `GameMap.Update`, and `MapMarkerMenu.Update`; controller actions are therefore consumed by the overlay and cannot operate the pause tabs/map underneath it. Menu Cancel closes the overlay, with a brief release guard so the close press itself does not reach the game. The feature is read-only: it does not write save data, tracker state, or manual marks. Set `[Map Overlay] Enabled = false` or change `Toggle Key` in `BepInEx/config/dev.silksongtracker.livebridge.cfg` to disable/rebind it.

**Verification:** this local build adds a controller cursor and modal input suppression; the earlier screenshot also exposed that runtime Pillow was missing, preventing the server from converting local WebP tiles for Unity. The tracker launcher now checks for this runtime dependency and the endpoint reports it explicitly if absent. The new DLL and cursor/modal behavior still need a game relaunch check. Live Hornet position still requires `[Bridge] Enabled = true`; only Sketch renders it.

This BepInEx plugin samples Hornet's room and world position twice per second and posts it to the tracker on `127.0.0.1`. The browser checks about every 750 ms. The Hornet-head marker appears **only on Sketch**. An audit of all 2,068 installed game bundles found 549 room-sized scenes; every scene has a documented positioning mode and none are unmapped. The bridge has game-map geometry for 469 scenes, fixed game-map anchors for 51, approximate area/last-known anchors for 26, and three scenes that rely on legacy room transforms. All 300 runtime scenes referenced by persistent-object map pins are covered; the 270 legacy Sketch transforms also cover six additional rooms. A fixed anchor does not follow movement within its room, and area/last-known anchors are approximate; the UI identifies these modes. Manual two-point calibration is optional for correcting an observed mismatch. The tracker removes the marker within five seconds of lost updates. Nothing is sent to a remote server, written to a save, or displayed on Screenshots.

## Install (Windows)

1. Install [BepInEx for Unity Mono](https://docs.bepinex.dev/master/articles/user_guide/installation/unity_mono.html) in the *game* folder, next to `Hollow Knight Silksong.exe`. Use the Windows x64 Unity Mono build for a 64-bit game. Launch and quit Silksong once to generate `BepInEx/config`, then close the game.
2. Download and extract both release archives: the tracker and the **separate** mod archive containing `SilksongLiveBridge.dll`. Python 3.10+ with its `py` launcher is needed for the tracker; the prebuilt DLL does **not** require the .NET SDK.
3. From the tracker folder, run `py tools/install_live_bridge.py --game-dir "C:\path\to\Hollow Knight Silksong" --dll "C:\path\to\SilksongLiveBridge.dll"`. This creates the private `.live-bridge-token`, copies the DLL to the game's `BepInEx/plugins`, and configures BepInEx. If an older bridge is installed, close the game and add `--upgrade`; this replaces only the bridge DLL and keeps the existing token/config. If you use a different tracker port, add `--port 7398` (or your port) on first install.
4. Start the tracker and game, then refresh Sketch. Keep `.live-bridge-token` private; never post it in a bug report or commit it.

Building from source instead of using the mod archive: install the .NET SDK and run `dotnet build live-bridge/SilksongLiveBridge.csproj -c Release -p:GameDir="C:\path\to\Hollow Knight Silksong"` from the tracker folder, then omit `--dll` from the installer. If the game is at the default Steam Windows path, omit `-p:GameDir`.

The plugin defaults to disabled if copied manually; the opt-in installer enables it. Disable it again by setting `Enabled = false` in `BepInEx/config/dev.silksongtracker.livebridge.cfg` or removing its DLL. The tracker never opens an inbound internet port; the endpoint accepts only a matching private token. The token is ignored by Git.

## Spoiler-free verification and optional calibration

Open Sketch in the tracker while your game is running. The status should say **Live: connected**. For geometry-backed rooms, the marker follows Hornet through the game's own map-room geometry. The status distinguishes fixed room anchors, approximate area/last-known fallbacks, and legacy transforms; these do not provide the same within-room precision. Static placement still needs broader live-game validation; the installed game assets cannot prove every position against an active playthrough.

Manual calibration is optional. To correct a visible mismatch, stand still and click **Calibrate current room**, then click Hornet's location on Sketch. The first point anchors Hornet immediately. Move a good distance without leaving the room, click **Capture calibration point 2**, and mark the new spot on Sketch. The second point solves both movement scale and direction; nearby or inconsistent points are rejected while keeping point 1. Press Escape to cancel a pending map click. Calibration applies to the current room only and can be replaced or cleared anytime.

Manual calibration uses stable room-local world coordinates only. The previous native-map calibration data is intentionally ignored because it could produce badly misplaced markers; your other manual map marks are unaffected. Calibration is stored in this browser, not the game or tracker server.

To check without story spoilers: stand at point 1, verify the dot is there; walk a short distance and verify it moves in the same direction; change rooms and confirm either the dot stays correctly aligned or disappears with a calibration prompt. Switch to Screenshots and confirm the dot hides. Quit the game and confirm it disappears within five seconds. Please report any mismatch with a screenshot of just the local area and no save file or token.

This is experimental because the automatic transforms and manual calibration still need broader in-game alignment checks. The bridge DLL is built against a specific game version and may need rebuilding after game updates.
