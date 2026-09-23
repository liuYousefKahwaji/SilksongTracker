"""Opt-in installer for the local BepInEx live-position bridge."""
from __future__ import annotations

import argparse
import secrets
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", required=True, type=Path, help="Hollow Knight Silksong install directory")
    parser.add_argument("--dll", type=Path, help="DLL from the separate mod release archive; omit when building from source")
    parser.add_argument("--upgrade", action="store_true", help="replace only this bridge DLL while keeping its existing config/token")
    parser.add_argument("--port", type=int, default=7397, help="local tracker port")
    args = parser.parse_args()
    game = args.game_dir.resolve()
    if not (game / "BepInEx/core/BepInEx.dll").is_file() or not (game / "Hollow Knight Silksong_Data/Managed/Assembly-CSharp.dll").is_file():
        parser.error("Not a Silksong installation with BepInEx. Install BepInEx first.")
    if not 1 <= args.port <= 65535:
        parser.error("Port must be in 1..65535.")
    source = args.dll.resolve() if args.dll else ROOT / "live-bridge/bin/Release/netstandard2.1/SilksongLiveBridge.dll"
    if not source.is_file():
        parser.error("Bridge DLL not found. Pass --dll from the mod archive or build the bridge from source.")
    destination = game / "BepInEx/plugins/SilksongLiveBridge.dll"
    config = game / "BepInEx/config/dev.silksongtracker.livebridge.cfg"
    if destination.exists() or config.exists():
        if not args.upgrade or not destination.is_file() or not config.is_file():
            parser.error("Bridge already installed. Use --upgrade with the game closed to replace only its DLL.")
        token_file = ROOT / ".live-bridge-token"
        if not token_file.is_file():
            parser.error("Tracker token is missing; existing installation was not changed.")
        token = token_file.read_text(encoding="ascii").strip()
        configured = config.read_text(encoding="utf-8")
        if len(token) != 64 or not any(line.strip() == "Token = " + token for line in configured.splitlines()):
            parser.error("Existing plugin token does not match this tracker; nothing was changed.")
        shutil.copy2(source, destination)
        print("Updated only the bridge DLL; existing token and settings were kept. Restart the game.")
        return
    token_file = ROOT / ".live-bridge-token"
    if token_file.exists():
        token = token_file.read_text(encoding="ascii").strip()
        if len(token) != 64:
            parser.error("Existing .live-bridge-token is invalid; no files were changed.")
    else:
        token = secrets.token_hex(32)
        token_file.write_text(token + "\n", encoding="ascii")
    destination.parent.mkdir(parents=True, exist_ok=True)
    config.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    config.write_text(
        "[Bridge]\nEnabled = true\nToken = " + token +
        f"\nEndpoint = http://127.0.0.1:{args.port}/api/live-position\n",
        encoding="utf-8",
    )
    print("Installed and enabled the local-only bridge. The token was not printed. Restart the game and tracker, then calibrate on Sketch.")


if __name__ == "__main__":
    main()
