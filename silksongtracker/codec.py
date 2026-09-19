"""Silksong save decoding and discovery.

Silksong currently uses the same Unity/C# BinaryFormatter wrapper family seen
in Hollow Knight: a 22-byte header, a 7-bit length prefix, base64 text and an
AES-ECB payload.  The decoder deliberately accepts plain JSON and fails with
actionable diagnostics because game builds and storefronts can change this
format.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
from pathlib import Path

from .aes import decrypt_ecb

AES_KEY = b"UKu52ePUBwetZ9wNX88o54dnfKRu0T1l"
CSHARP_HEADER = bytes([0, 1, 0, 0, 0, 255, 255, 255, 255, 1, 0, 0, 0, 0, 0, 0, 0, 6, 1, 0, 0, 0])
SLOT_RE = re.compile(r"^user(\d+)\.dat$", re.I)


def _decrypt(payload: bytes) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        dec = Cipher(algorithms.AES(AES_KEY), modes.ECB()).decryptor()
        return dec.update(payload) + dec.finalize()
    except ImportError:
        pass
    try:
        from Crypto.Cipher import AES
        return AES.new(AES_KEY, AES.MODE_ECB).decrypt(payload)
    except ImportError:
        return decrypt_ecb(AES_KEY, payload)


def _strip_wrapper(raw: bytes) -> bytes:
    if not raw.startswith(CSHARP_HEADER) or len(raw) <= len(CSHARP_HEADER) + 1:
        raise ValueError("missing or truncated Unity save header")
    body = raw[len(CSHARP_HEADER):-1]
    length_bytes = 0
    for i, value in enumerate(body[:5]):
        length_bytes = i + 1
        if not value & 0x80:
            break
    else:
        raise ValueError("invalid 7-bit payload length")
    payload = body[length_bytes:]
    if not payload:
        raise ValueError("empty encrypted payload")
    return payload


def decode_save(raw: bytes) -> dict:
    stripped = raw.lstrip()
    if stripped[:1] in (b"{", b"["):
        obj = json.loads(stripped.decode("utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("save JSON root is not an object")
        return obj
    if not raw.startswith(CSHARP_HEADER):
        raise ValueError("not a recognised Silksong save (JSON or Unity header expected)")
    try:
        payload = base64.b64decode(_strip_wrapper(raw), validate=False)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"invalid base64 payload: {exc}") from exc
    if len(payload) % 16:
        raise ValueError("encrypted payload is not AES block aligned")
    plain = _decrypt(payload)
    if not plain:
        raise ValueError("decrypted payload is empty")
    pad = plain[-1]
    if not 1 <= pad <= 16 or plain[-pad:] != bytes([pad]) * pad:
        raise ValueError("invalid PKCS#7 padding; the key or save version may differ")
    try:
        obj = json.loads(plain[:-pad].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"decrypted payload is not JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError("save JSON root is not an object")
    return obj


def read_save(path: str | os.PathLike) -> dict:
    return decode_save(Path(path).read_bytes())


def default_save_dirs() -> list[Path]:
    """Known Windows, macOS, Linux and Proton locations, without creating any."""
    home = Path.home()
    userprofile = os.environ.get("USERPROFILE")
    out: list[Path] = []
    if userprofile:
        root = Path(userprofile) / "AppData/LocalLow/Team Cherry/Hollow Knight Silksong"
        out += [root, root / "Saves"]
        # Microsoft Store/WGS data is intentionally searched only for *.dat.
        out.append(Path(userprofile) / "AppData/Local/Packages/TeamCherry.HollowKnightSilksong_y4jvztpgccj42/SystemAppData/wgs")
    out += [
        home / "Library/Application Support/unity.Team-Cherry.Silksong",
        home / ".config/unity3d/Team Cherry/Hollow Knight Silksong",
        home / ".local/share/Steam/steamapps/compatdata/1030300/pfx/drive_c/users/steamuser/AppData/LocalLow/Team Cherry/Hollow Knight Silksong",
    ]
    seen: set[str] = set(); result: list[Path] = []
    for item in out:
        try:
            key = str(item.resolve()).lower()
            if item.is_dir() and key not in seen:
                seen.add(key); result.append(item)
        except OSError:
            continue
    return result


def find_saves(extra_dirs: list[str] | None = None) -> list[dict]:
    dirs = [Path(x) for x in (extra_dirs or [])] + default_save_dirs()
    found: dict[str, dict] = {}
    for directory in dirs:
        if not directory.is_dir():
            continue
        try:
            files = list(directory.rglob("user*.dat"))
        except OSError:
            files = []
        for path in files:
            match = SLOT_RE.match(path.name)
            if not match:
                continue
            try:
                key = str(path.resolve()).lower(); stat = path.stat()
            except OSError:
                continue
            if key in found:
                continue
            found[key] = {"slot": int(match.group(1)), "path": str(path), "dir": str(path.parent), "mtime": stat.st_mtime, "size": stat.st_size}
    return sorted(found.values(), key=lambda x: (x["slot"], x["path"]))
