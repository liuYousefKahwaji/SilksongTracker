# Silksong Tracker

**v0.2.2 beta** — a local, read-only progress tracker for Hollow Knight: Silksong, inspired by Hollow Tracker.

Reads your save to show a completion checklist and an interactive map, with Sketch/Screenshots views, navigable interiors, item pins, search, filters, multiple save selection, and automatic save refresh. Unverified map locations can be marked manually in this browser. Runs on your computer at `http://127.0.0.1:7397`; saves are not uploaded or modified.

An **optional BepInEx live bridge** can show Hornet's current position on **Sketch only**. It sends coordinates to the tracker on your own computer; it does not modify saves or send data to the internet. See [spoiler-free setup and calibration](live-bridge/README.md). This feature is experimental and has not yet been verified in a live game session.

## Run

Requires Python 3.10+ and internet for first-time map setup. From this folder:

```sh
python -m pip install -r requirements-build.txt
python tools/build_map.py
python -m silksongtracker
```

On Windows, use `py` instead of `python`. After setup, you can also double-click `Silksong Tracker.bat`. Normal use works offline and needs only Python. Use `--save-dir "path/to/folder"` if automatic save discovery misses your slot.

Map artwork, icons, and the upstream map dataset are **not bundled in this repository**: setup downloads them from their attributed third-party sources. Upstream availability and terms apply; including a downloader does not grant redistribution permission. The full map needs about 30 MB of downloads.

## Current limits

- **Spoilers:** the checklist has an optional **Acquired only** view that hides unfinished entries and searches only acquired ones. It is not a fully spoiler-safe mode: the map exposes future geography and items, and switching the view off reveals the full checklist. The map link is labeled accordingly.
- Of 1,419 map pins, 1,206 have save rules, 166 are reference locations, and **47 objectives still need verified automatic tracking**. You can mark those 47 manually per save; these marks live in this browser and never change a game save. Use Export/Import backup in the map sidebar to move or safeguard those marks (the import replaces marks for the selected save after confirmation). “Only left” includes confirmed incomplete and manually marked incomplete pins.
- All 193 checklist entries resolve against the tested early-game save, but late-game transitions and every supported game version have **not** been independently validated. Missing fields remain unknown rather than being guessed.
- Sketch groups pins that share an in-game map point into numbered item icons. A group opens its member locations and can switch to their exact placement in Screenshots, including detached interiors. Six pins lack sketch coordinates and use the Screenshots view. Some source locations may be inaccurate.
- A clean-clone Windows installation and a two-slot selection were tested. Malformed saves, further slot layouts, and cross-platform behavior need broader testing. This is a beta, not a guaranteed 100% completion authority.
- Third-party asset redistribution permission is not established; no artwork redistribution rights are claimed.

Tests (after map setup): `python -m unittest discover -s tests -v`. Passing tests do not prove full in-game coverage. `python tools/validate_progress.py` performs a read-only, count-only check of discovered saves without printing game-content names. See [validation evidence and remaining gaps](TRACKING_VALIDATION.md) (contains spoilers).

Please report bugs with the tracker/game version and expected versus observed behavior. **Do not post your save file or personal paths publicly.** Mark game-content reports as spoilers.

## Credits and license

Inspired by Hollow Tracker. Map and placements: [RainingChain & IdoManti](https://scripterswar.com/silksong/map). Save-rule research includes [BlueOrcaz](https://github.com/BlueOrcaz/silksong-save-viewer) and [th3r3dfox](https://github.com/th3r3dfox/silksong-tracker). Game artwork and trademarks belong to Team Cherry; this is an unofficial fan project.

Tracker code: GPL-3.0-or-later ([LICENSE](LICENSE)). Leaflet is BSD-2-Clause; its license is included under `web/vendor/`. These code licenses do not cover third-party game/map artwork or datasets.
