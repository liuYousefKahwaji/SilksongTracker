# Optional live Hornet position (experimental)

This BepInEx plugin samples Hornet's room and world position twice per second and posts it to the tracker on `127.0.0.1`. The browser checks about every 750 ms. The Hornet-head marker appears **only on Sketch**. Automatic placement covers 251 map-tagged rooms from the installed game data: 59 use three or more matched landmarks, 37 use two, and 155 use a single landmark plus an estimated regional movement transform. Single-landmark placement is marked approximate. In other rooms, two manual positions calibrate scale and direction for that room. The tracker removes the marker within five seconds of lost updates. Nothing is sent to a remote server, written to a save, or displayed on Screenshots.

## Install (Windows)

1. Install [BepInEx for Unity Mono](https://docs.bepinex.dev/master/articles/user_guide/installation/unity_mono.html) in the *game* folder, next to `Hollow Knight Silksong.exe`. Use the Windows x64 Unity Mono build for a 64-bit game. Launch and quit Silksong once to generate `BepInEx/config`, then close the game.
2. Download and extract both release archives: the tracker and the **separate** mod archive containing `SilksongLiveBridge.dll`. Python 3.10+ with its `py` launcher is needed for the tracker; the prebuilt DLL does **not** require the .NET SDK.
3. From the tracker folder, run `py tools/install_live_bridge.py --game-dir "C:\path\to\Hollow Knight Silksong" --dll "C:\path\to\SilksongLiveBridge.dll"`. This creates the private `.live-bridge-token`, copies the DLL to the game's `BepInEx/plugins`, and configures BepInEx. If an older bridge is installed, close the game and add `--upgrade`; this replaces only the bridge DLL and keeps the existing token/config. If you use a different tracker port, add `--port 7398` (or your port) on first install.
4. Start the tracker and game, then refresh Sketch. Keep `.live-bridge-token` private; never post it in a bug report or commit it.

Building from source instead of using the mod archive: install the .NET SDK and run `dotnet build live-bridge/SilksongLiveBridge.csproj -c Release -p:GameDir="C:\path\to\Hollow Knight Silksong"` from the tracker folder, then omit `--dll` from the installer. If the game is at the default Steam Windows path, omit `-p:GameDir`.

The plugin defaults to disabled if copied manually; the opt-in installer enables it. Disable it again by setting `Enabled = false` in `BepInEx/config/dev.silksongtracker.livebridge.cfg` or removing its DLL. The tracker never opens an inbound internet port; the endpoint accepts only a matching private token. The token is ignored by Git.

## Spoiler-free verification and optional calibration

Open Sketch in the tracker while your game is running. The status should say **Live: connected**. In rooms with three or more matched landmarks, placement uses a robust multi-point fit. Two-landmark rooms use a direct paired fit. One-landmark rooms use that exact map match as an origin with a regional movement estimate, and are labeled approximate. All static transforms still need broader live-game validation.

For manual calibration, stand still and click **Calibrate current room**, then click Hornet's exact location on Sketch. The first point anchors Hornet immediately. Move a good distance without leaving the room, click **Capture calibration point 2**, and mark the new spot on Sketch. The second point solves both movement scale and direction; nearby or inconsistent points are rejected while keeping point 1. Press Escape to cancel a pending map click. Calibration applies to the current room only and can be replaced or cleared anytime.

Manual calibration uses stable room-local world coordinates only. The previous native-map calibration data is intentionally ignored because it could produce badly misplaced markers; your other manual map marks are unaffected. Calibration is stored in this browser, not the game or tracker server.

To check without story spoilers: stand at point 1, verify the dot is there; walk a short distance and verify it moves in the same direction; change rooms and confirm either the dot stays correctly aligned or disappears with a calibration prompt. Switch to Screenshots and confirm the dot hides. Quit the game and confirm it disappears within five seconds. Please report any mismatch with a screenshot of just the local area and no save file or token.

This is experimental because the automatic transforms and manual calibration still need broader in-game alignment checks. The bridge DLL is built against a specific game version and may need rebuilding after game updates.
