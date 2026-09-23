"""Create separate, checked tracker and prebuilt-mod release archives."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def tracked_paths() -> list[Path]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True)
    paths = [Path(raw.decode("utf-8")) for raw in result.stdout.split(b"\0") if raw]
    forbidden = ("data/map/", "source/", "web/assets/", ".live-bridge-token")
    for path in paths:
        name = path.as_posix()
        if name.startswith(forbidden) or name.endswith((".dat", ".save.json")):
            raise RuntimeError(f"Refusing to package private or third-party file: {name}")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="version string, e.g. v0.3.0-beta")
    parser.add_argument("--out", type=Path, default=ROOT / "output/releases")
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    tracker = output / f"SilksongTracker-{args.version}-Windows.zip"
    mod = output / f"SilksongLiveBridge-{args.version}-Windows.zip"
    dll = ROOT / "live-bridge/bin/Release/netstandard2.1/SilksongLiveBridge.dll"
    if not dll.is_file():
        parser.error("Build the mod in Release configuration first.")
    with ZipFile(tracker, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in tracked_paths():
            archive.write(ROOT / path, path.as_posix())
    with ZipFile(mod, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(dll, "SilksongLiveBridge.dll")
        archive.write(ROOT / "live-bridge/README.md", "README.md")
        archive.write(ROOT / "LICENSE", "LICENSE")
    print(f"Tracker: {tracker.name} ({tracker.stat().st_size:,} bytes)")
    print(f"Mod: {mod.name} ({mod.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
