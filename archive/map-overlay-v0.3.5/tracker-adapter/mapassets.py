"""Safe local map-tile access for the in-game overlay.

The source map is downloaded by the user during tracker setup and stays on
their machine. This adapter only serves whitelisted tiles to the loopback game
mod, converting WebP to JPEG because Unity's built-in image loader does not
decode WebP.
"""
from __future__ import annotations

import io
import json
import threading
from collections import OrderedDict
from pathlib import Path

from .database import ROOT

_LOCK = threading.RLock()
_CACHE: OrderedDict[tuple[str, str], bytes] = OrderedDict()
_CACHE_LIMIT = 32


class MapTileDependencyError(RuntimeError):
    """Raised when the tracker runtime lacks its required WebP converter."""


def _metadata() -> dict:
    path = ROOT / "data" / "map" / "map.json"
    return json.loads(path.read_text(encoding="utf-8"))


def tile_jpeg(style: str, z: str, x: str, y: str) -> bytes | None:
    """Return an existing, explicitly listed local tile as JPEG, or None."""
    if style not in ("sketch", "screenshots"):
        return None
    try:
        zoom, tile_x, tile_y = (int(part) for part in (z, x, y))
    except (TypeError, ValueError):
        return None
    if min(zoom, tile_x, tile_y) < 0:
        return None
    key = f"{zoom}/{tile_x}_{tile_y}"
    cache_key = (style, key)
    with _LOCK:
        cached = _CACHE.get(cache_key)
        if cached is not None:
            _CACHE.move_to_end(cache_key)
            return cached

    metadata = _metadata()
    spec = metadata.get("sketch") if style == "sketch" else metadata.get("image")
    if not isinstance(spec, dict) or key not in set(spec.get("validTiles", metadata.get("validTiles", []))):
        return None
    suffix = ".webp" if style == "sketch" else Path(spec.get("url", "")).suffix or ".webp"
    path = ROOT / "data" / "map" / ("sketch" if style == "sketch" else "tiles") / key
    path = path.with_suffix(suffix)
    root = (ROOT / "data" / "map" / ("sketch" if style == "sketch" else "tiles")).resolve()
    if root not in path.resolve().parents or not path.is_file():
        return None
    try:
        from PIL import Image
    except ImportError as exc:
        raise MapTileDependencyError(
            "Pillow is required to display local WebP map tiles. Install requirements.txt and restart the tracker."
        ) from exc
    try:
        with Image.open(path) as image:
            converted = io.BytesIO()
            image.convert("RGB").save(converted, format="JPEG", quality=92, subsampling=0, optimize=True)
            body = converted.getvalue()
    except (OSError, ValueError):
        return None

    with _LOCK:
        _CACHE[cache_key] = body
        _CACHE.move_to_end(cache_key)
        while len(_CACHE) > _CACHE_LIMIT:
            _CACHE.popitem(last=False)
    return body
