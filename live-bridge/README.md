# Optional live Hornet position (experimental)

This BepInEx plugin samples Hornet's position twice per second and posts it to the tracker on `127.0.0.1`. The browser checks about every 750 ms. The dot appears **only on Sketch**, and only after two-point calibration. The tracker removes it within five seconds of lost updates. Nothing is sent to a remote server, written to a save, or displayed on Screenshots.

## Install (Windows)

1. Install BepInEx for your Silksong game. Close the game before copying files. You need the .NET SDK to build the bridge.
2. From the tracker folder, build with `dotnet build live-bridge/SilksongLiveBridge.csproj -c Release -p:GameDir="C:\path\to\Hollow Knight Silksong"`. If your game is at the default Steam Windows path, omit `-p:GameDir`.
3. Run `python tools/install_live_bridge.py --game-dir "C:\path\to\Hollow Knight Silksong"`. This creates the private `.live-bridge-token`, copies the DLL, and configures BepInEx. It refuses to overwrite an existing installation. If you use a different tracker port, add `--port 7398` (or your port).
4. Start the tracker and game. Keep `.live-bridge-token` private; never post it in a bug report or commit it.

The plugin defaults to disabled if copied manually; the opt-in installer enables it. Disable it again by setting `Enabled = false` in `BepInEx/config/dev.silksongtracker.livebridge.cfg` or removing its DLL. The tracker never opens an inbound internet port; the endpoint accepts only a matching private token. The token is ignored by Git.

## Spoiler-free calibration

Open Sketch in the tracker while your game is running. The status should say **Live: connected**. Stand still somewhere you can identify on the map. Click **Place calibration point 1**, then click your exact location on Sketch. Move to a *different* recognizable location, click **Place calibration point 2**, then click that location on Sketch. The live dot and **Center on Hornet** button should appear. Choose two points reasonably far apart for better accuracy. You can clear the calibration and redo it anytime.

If the game exposes its native map coordinate, the two points calibrate the whole Sketch. Otherwise, the bridge falls back to world coordinates, and calibration applies to the current room only. In a new room, the dot stays hidden until calibrated there—it will not pretend to know your location. Opening the game's map once may make native coordinates available. Calibration is stored in this browser, not the game or tracker server.

To check without story spoilers: stand at point 1, verify the dot is there; walk a short distance and verify it moves in the same direction; change rooms and confirm either the dot stays correctly aligned or disappears with a calibration prompt. Switch to Screenshots and confirm the dot hides. Quit the game and confirm it disappears within five seconds. Please report any mismatch with a screenshot of just the local area and no save file or token.

This is experimental because the game's native map-position internals and the Sketch source's pixel coordinates still need an in-game alignment check. The bridge is built against the local game's DLLs and may need rebuilding after game updates.
