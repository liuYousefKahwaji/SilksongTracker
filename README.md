# Silksong Tracker

**v0.3.2 beta** — a local, read-only progress tracker for Hollow Knight: Silksong, inspired by Hollow Tracker.

Reads your save to show a completion checklist and an interactive map, with Sketch/Screenshots views, navigable interiors, item pins, search, filters, multiple save selection, and automatic save refresh. Unverified map locations can be marked manually in this browser. Runs on your computer at `http://127.0.0.1:7397`; saves are not uploaded or modified.

An **optional BepInEx live bridge** can show Hornet's current position on **Sketch only**, using the supplied Hornet-head image with its outside background clipped away. It sends room-scoped world coordinates to the tracker on your own computer; it does not modify saves or send data to the internet. Auto-placement now covers 251 map-tagged rooms found in the installed game data: 59 have three or more matching landmarks, 37 use two matched landmarks, and 155 align one matched landmark with a regional movement estimate. In any room, two manual captures fit that room's scale and direction. Single-landmark estimates are approximate. This feature still needs more live-game checks.

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
2. Install [BepInEx](https://www.nexusmods.com/hollowknightsilksong/mods/26) in your Silksong game folder. Extract it beside `Hollow Knight Silksong.exe`, then launch and quit the game once to generate `BepInEx/config`. Do not copy BepInEx into the tracker folder.
3. With the game closed, from the tracker folder run:

```powershell
py tools/install_live_bridge.py --game-dir "C:\path\to\Hollow Knight Silksong" --dll "C:\path\to\SilksongLiveBridge.dll"
```

The installer copies the DLL to the game's `BepInEx/plugins`, creates a private tracker token, and configures the plugin to send only to `127.0.0.1:7397`. For an existing installation, close the game and add `--upgrade` to replace only this bridge DLL while keeping your token/settings. If the tracker runs on another port, add `--port NUMBER` on first install. Restart the game and tracker, then refresh Sketch. The status should say **Live: connected**. Automatic placement quality is shown in the live status. For manual calibration, stand still, click **Calibrate current room**, and click Hornet's position on Sketch. Move a good distance in that room, click **Capture calibration point 2**, and click the new position on Sketch; the pair fits movement scale and direction. Calibration stays in your browser and never changes a save. Full [spoiler-free mod setup, verification, and troubleshooting](live-bridge/README.md).

The token in `.live-bridge-token` and the matching BepInEx config is private: do not share either file or post its contents. To disable live tracking, set `Enabled = false` in the plugin config or remove the DLL.

Map artwork, icons, and the upstream map dataset are **not bundled in this repository**: setup downloads them from their attributed third-party sources. Upstream availability and terms apply; including a downloader does not grant redistribution permission. The full map needs about 30 MB of downloads.

## Current limits

- **Spoilers:** the checklist has an optional **Acquired only** view that hides unfinished entries and searches only acquired ones. It is not a fully spoiler-safe mode: the map exposes future geography and items, and switching the view off reveals the full checklist. The map link is labeled accordingly.
- Of 1,419 map pins, 1,206 have save rules, 166 are reference locations, and **47 objectives still need verified automatic tracking**. You can mark those 47 manually per save; these marks live in this browser and never change a game save. Use Export/Import backup in the map sidebar to move or safeguard those marks (the import replaces marks for the selected save after confirmation). “Only left” includes confirmed incomplete and manually marked incomplete pins.
- All 193 checklist entries resolve against the tested early-game save, but late-game transitions and every supported game version have **not** been independently validated. Missing fields remain unknown rather than being guessed.
- Sketch groups pins that share an in-game map point into numbered item icons. A group opens its member locations and can switch to their exact placement in Screenshots, including detached interiors. Six pins lack sketch coordinates and use the Screenshots view. Some source locations may be inaccurate.
- Live placement covers 251 of 300 map-tagged scene bundles found in the locally installed game: 59 transforms pass a three-or-more-landmark fit, 37 are exact two-landmark fits, and 155 align one unique landmark using a regional scale and direction estimate. Those 155 are explicitly labeled approximate. The other 49 tagged scenes lack usable unique map-object anchors. Automatic placement and calibration still need broader in-game alignment checks. Manual calibration now uses two room-local world positions to solve scale and direction; its first point is immediate, while the second must be far enough away and consistent with the map. Previous calibration data is intentionally ignored after a coordinate-system bug; manual map marks are unaffected.
- A clean-clone Windows installation and a two-slot selection were tested. Malformed saves, further slot layouts, and cross-platform behavior need broader testing. This is a beta, not a guaranteed 100% completion authority.
- Third-party asset redistribution permission is not established; no artwork redistribution rights are claimed.

Tests (after map setup): `python -m unittest discover -s tests -v` and `node tests/test_live_math.js`. Passing tests do not prove full in-game coverage. `python tools/validate_progress.py` performs a read-only, count-only check of discovered saves without printing game-content names. See [validation evidence and remaining gaps](TRACKING_VALIDATION.md) (contains spoilers).

Please report bugs with the tracker/game version and expected versus observed behavior. **Do not post your save file or personal paths publicly.** Mark game-content reports as spoilers.

## Credits and license

Inspired by Hollow Tracker. Map and placements: [RainingChain & IdoManti](https://scripterswar.com/silksong/map). Save-rule research includes [BlueOrcaz](https://github.com/BlueOrcaz/silksong-save-viewer) and [th3r3dfox](https://github.com/th3r3dfox/silksong-tracker). Game artwork and trademarks belong to Team Cherry; this is an unofficial fan project.

Tracker code: GPL-3.0-or-later ([LICENSE](LICENSE)). Leaflet is BSD-2-Clause; its license is included under `web/vendor/`. These code licenses do not cover third-party game/map artwork or datasets.
