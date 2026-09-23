# Silksong Tracker

**v0.3.0 beta** — a local, read-only progress tracker for Hollow Knight: Silksong, inspired by Hollow Tracker.

Reads your save to show a completion checklist and an interactive map, with Sketch/Screenshots views, navigable interiors, item pins, search, filters, multiple save selection, and automatic save refresh. Unverified map locations can be marked manually in this browser. Runs on your computer at `http://127.0.0.1:7397`; saves are not uploaded or modified.

An **optional BepInEx live bridge** can show Hornet's current position on **Sketch only**, using a Hornet-head marker. It sends coordinates to the tracker on your own computer; it does not modify saves or send data to the internet. Auto-placement is available in 59 rooms with independently matched map points; optional calibration refines it or covers other rooms. This feature is experimental and has not yet been verified in a live game session.

## Download and run (Windows)

Download the **tracker archive** from [Releases](https://github.com/liuYousefKahwaji/SilksongTracker/releases) and extract it to a normal writable folder. Install [Python 3.10+](https://www.python.org/downloads/) with its Windows `py` launcher. Double-click `Silksong Tracker.bat` in the extracted folder. On first run it installs the map-build dependency and downloads the map data/artwork; this needs internet and can take several minutes. Thereafter normal use works offline. The tracker opens at `http://127.0.0.1:7397`.

From a terminal, the equivalent first-run commands are:

```sh
python -m pip install -r requirements-build.txt
python tools/build_map.py
python -m silksongtracker
```

On Windows, use `py` instead of `python` if needed. Use `--save-dir "path/to/folder"` if automatic save discovery misses your slot. The release archive contains the tracker, launcher, live-position room transforms, and setup code, but not copyrighted map artwork or the BepInEx DLL.

## Optional live-position mod (Windows)

1. Download the **separate mod archive** from the same release and extract `SilksongLiveBridge.dll`. The tracker works without this mod.
2. Install [BepInEx for Unity Mono](https://docs.bepinex.dev/master/articles/user_guide/installation/unity_mono.html) in your Silksong game folder. Choose the Windows x64 Unity Mono build for a 64-bit game, extract it beside `Hollow Knight Silksong.exe`, then launch and quit the game once to generate `BepInEx/config`. Do not copy BepInEx into the tracker folder.
3. With the game closed, from the tracker folder run:

```powershell
py tools/install_live_bridge.py --game-dir "C:\path\to\Hollow Knight Silksong" --dll "C:\path\to\SilksongLiveBridge.dll"
```

The installer copies the DLL to the game's `BepInEx/plugins`, creates a private tracker token, and configures the plugin to send only to `127.0.0.1:7397`. It refuses to overwrite an existing installation. If the tracker runs on another port, add `--port NUMBER`. Restart the game and tracker, then refresh Sketch. The status should say **Live: connected**. The dot appears automatically in supported rooms; otherwise use the two on-map calibration points. Calibration stays in your browser and never changes a save. Full [spoiler-free mod setup, verification, and troubleshooting](live-bridge/README.md).

The token in `.live-bridge-token` and the matching BepInEx config is private: do not share either file or post its contents. To disable live tracking, set `Enabled = false` in the plugin config or remove the DLL.

Map artwork, icons, and the upstream map dataset are **not bundled in this repository**: setup downloads them from their attributed third-party sources. Upstream availability and terms apply; including a downloader does not grant redistribution permission. The full map needs about 30 MB of downloads.

## Current limits

- **Spoilers:** the checklist has an optional **Acquired only** view that hides unfinished entries and searches only acquired ones. It is not a fully spoiler-safe mode: the map exposes future geography and items, and switching the view off reveals the full checklist. The map link is labeled accordingly.
- Of 1,419 map pins, 1,206 have save rules, 166 are reference locations, and **47 objectives still need verified automatic tracking**. You can mark those 47 manually per save; these marks live in this browser and never change a game save. Use Export/Import backup in the map sidebar to move or safeguard those marks (the import replaces marks for the selected save after confirmation). “Only left” includes confirmed incomplete and manually marked incomplete pins.
- All 193 checklist entries resolve against the tested early-game save, but late-game transitions and every supported game version have **not** been independently validated. Missing fields remain unknown rather than being guessed.
- Sketch groups pins that share an in-game map point into numbered item icons. A group opens its member locations and can switch to their exact placement in Screenshots, including detached interiors. Six pins lack sketch coordinates and use the Screenshots view. Some source locations may be inaccurate.
- Live auto-placement currently covers 59 rooms; this was derived from 236 matched in-game objects and map pins, not an in-game runtime check. It may be approximate or unavailable in other rooms. Manual two-point calibration remains optional where auto-placement works and necessary for precise positioning in unrecognized rooms. The mod's game-version compatibility and native-map fallback still need in-game validation.
- A clean-clone Windows installation and a two-slot selection were tested. Malformed saves, further slot layouts, and cross-platform behavior need broader testing. This is a beta, not a guaranteed 100% completion authority.
- Third-party asset redistribution permission is not established; no artwork redistribution rights are claimed.

Tests (after map setup): `python -m unittest discover -s tests -v`. Passing tests do not prove full in-game coverage. `python tools/validate_progress.py` performs a read-only, count-only check of discovered saves without printing game-content names. See [validation evidence and remaining gaps](TRACKING_VALIDATION.md) (contains spoilers).

Please report bugs with the tracker/game version and expected versus observed behavior. **Do not post your save file or personal paths publicly.** Mark game-content reports as spoilers.

## Credits and license

Inspired by Hollow Tracker. Map and placements: [RainingChain & IdoManti](https://scripterswar.com/silksong/map). Save-rule research includes [BlueOrcaz](https://github.com/BlueOrcaz/silksong-save-viewer) and [th3r3dfox](https://github.com/th3r3dfox/silksong-tracker). Game artwork and trademarks belong to Team Cherry; this is an unofficial fan project.

Tracker code: GPL-3.0-or-later ([LICENSE](LICENSE)). Leaflet is BSD-2-Clause; its license is included under `web/vendor/`. These code licenses do not cover third-party game/map artwork or datasets.
