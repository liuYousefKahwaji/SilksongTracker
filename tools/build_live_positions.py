"""Derive room-local world-to-Sketch transforms from game objects and map pins.

Maintainer tool: reads installed game bundles and writes numerical transforms only.
Requires UnityPy (the source/.deps copy is used when present). It never writes to
the game or includes game textures in its output.
"""
from __future__ import annotations

import argparse
import cmath
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source/.deps"))


def world_objects(bundle: Path) -> list[dict]:
    import UnityPy

    UnityPy.config.FALLBACK_UNITY_VERSION = "6000.0.50f1"
    env = UnityPy.load(str(bundle))
    transforms = {o.path_id: o.read_typetree() for o in env.objects if o.type.name == "Transform"}

    def position(tid: int) -> list[float]:
        transform = transforms[tid]
        local = transform["m_LocalPosition"]
        vector = [local["x"], local["y"]]
        parent = transform["m_Father"]["m_PathID"]
        while parent:
            transform = transforms[parent]
            rotation = transform["m_LocalRotation"]
            angle = 2 * math.atan2(rotation["z"], rotation["w"])
            scale = transform["m_LocalScale"]
            local = transform["m_LocalPosition"]
            x, y = vector[0] * scale["x"], vector[1] * scale["y"]
            vector = [local["x"] + x * math.cos(angle) - y * math.sin(angle),
                      local["y"] + x * math.sin(angle) + y * math.cos(angle)]
            parent = transform["m_Father"]["m_PathID"]
        return vector

    result = []
    for obj in env.objects:
        if obj.type.name != "GameObject":
            continue
        game_object = obj.read()
        components = [c.component for c in game_object.m_Component]
        transform = next((c for c in components if c.path_id in transforms), None)
        if transform is None:
            continue
        for component in components:
            if component.deref().type.name != "MonoBehaviour":
                continue
            item = component.read_typetree().get("itemData")
            if isinstance(item, dict) and "ID" in item:
                result.append({"id": item["ID"] or game_object.m_Name, "pos": position(transform.path_id)})
    return result


def fit(pairs: list[tuple[complex, complex]], reflected: bool = False) -> dict | None:
    if len(pairs) < 2:
        return None
    source = [p.conjugate() if reflected else p for p, _ in pairs]
    target = [q for _, q in pairs]
    p0 = sum(source) / len(source)
    q0 = sum(target) / len(target)
    denominator = sum(abs(p - p0) ** 2 for p in source)
    if denominator < 25:
        return None
    multiplier = sum((q - q0) * (p - p0).conjugate() for p, q in zip(source, target)) / denominator
    if not .1 <= abs(multiplier) <= 20:
        return None
    residuals = [abs(q - (q0 + multiplier * (p - p0))) for p, q in zip(source, target)]
    return {"source": [round(p0.real, 4), round(-p0.imag if reflected else p0.imag, 4)],
            "sketch": [round(q0.real, 4), round(q0.imag, 4)],
            "real": round(multiplier.real, 7), "imag": round(multiplier.imag, 7),
            "reflected": reflected, "rms": round(math.sqrt(sum(e * e for e in residuals) / len(residuals)), 3),
            "maxError": round(max(residuals), 3), "anchors": len(pairs)}


def robust_fit(pairs: list[tuple[complex, complex]]) -> dict | None:
    if len(pairs) < 3:
        return None
    best = None
    for i in range(len(pairs)):
        for j in range(i + 1, len(pairs)):
            if abs(pairs[i][0] - pairs[j][0]) < 15 or abs(pairs[i][1] - pairs[j][1]) < 15:
                continue
            for reflected in (False, True):
                trial = fit([pairs[i], pairs[j]], reflected)
                if trial is None:
                    continue
                p0 = complex(*trial["source"])
                q0 = complex(*trial["sketch"])
                multiplier = complex(trial["real"], trial["imag"])
                inliers = [(p, q) for p, q in pairs if abs(q - (q0 + multiplier * ((p - p0).conjugate() if reflected else p - p0))) <= 16]
                if len(inliers) < 3:
                    continue
                result = fit(inliers, reflected)
                if result is None or result["rms"] > 12 or result["maxError"] > 20:
                    continue
                rank = (len(inliers), -result["rms"])
                if best is None or rank > best[0]:
                    best = (rank, result)
    return best[1] if best else None


def transform_prior(rooms: dict, scene: str) -> dict | None:
    """Use only multi-landmark transforms as priors; estimates must not compound."""
    trusted = {name: room for name, room in rooms.items() if room.get("anchors", 0) >= 3}
    prefix = scene.split("_")[0]
    area = [room for name, room in trusted.items() if name.split("_")[0] == prefix]
    candidates = area or list(trusted.values())
    if not candidates:
        return None
    scales = [math.hypot(room["real"], room["imag"]) for room in candidates]
    angles = [math.atan2(room["imag"], room["real"]) for room in candidates]
    scale = sorted(scales)[len(scales) // 2]
    angle = sorted(angles)[len(angles) // 2]
    reflected = sum(bool(room.get("reflected")) for room in candidates) > len(candidates) / 2
    return {"real": scale * math.cos(angle), "imag": scale * math.sin(angle), "reflected": reflected}


def paired_fit(pairs: list[tuple[complex, complex]], prior: dict | None) -> dict | None:
    """Fit an exact two-landmark room transform when no redundant third point exists."""
    if len(pairs) != 2:
        return None
    source_distance = abs(pairs[1][0] - pairs[0][0])
    target_distance = abs(pairs[1][1] - pairs[0][1])
    if source_distance < 25 or target_distance < 12:
        return None
    if prior is None:
        prior = {"real": 0.65, "imag": 0.0, "reflected": False}
    prior_angle = math.atan2(prior["imag"], prior["real"])
    candidates = []
    for reflected in (prior["reflected"], not prior["reflected"]):
        result = fit(pairs, reflected)
        if result is None:
            continue
        scale = math.hypot(result["real"], result["imag"])
        if not 0.15 <= scale <= 1.0:
            continue
        angle = math.atan2(result["imag"], result["real"])
        angle_delta = abs((angle - prior_angle + math.pi) % (2 * math.pi) - math.pi)
        if angle_delta > math.radians(20):
            continue
        scale_delta = abs(math.log(scale / math.hypot(prior["real"], prior["imag"])))
        candidates.append(((angle_delta, scale_delta), result))
    if not candidates:
        return None
    _, result = min(candidates, key=lambda candidate: candidate[0])
    result.pop("rms", None)
    result.pop("maxError", None)
    result["quality"] = "paired-landmarks"
    return result


def single_landmark_estimate(pairs: list[tuple[complex, complex]], prior: dict | None) -> dict | None:
    """Anchor one exact map match and estimate room movement from a trusted area scale."""
    if len(pairs) != 1:
        return None
    if prior is None:
        prior = {"real": 0.65, "imag": 0.0, "reflected": False}
    source, sketch = pairs[0]
    return {
        "source": [round(source.real, 4), round(source.imag, 4)],
        "sketch": [round(sketch.real, 4), round(sketch.imag, 4)],
        "real": round(prior["real"], 7), "imag": round(prior["imag"], 7),
        "reflected": prior["reflected"], "anchors": 1,
        "quality": "single-landmark-estimate",
    }


def build(map_path: Path, cache_dir: Path, bundles_dir: Path, trusted_rooms: dict | None = None) -> dict:
    markers = json.loads(map_path.read_text(encoding="utf-8"))["markers"]
    by_scene = defaultdict(lambda: defaultdict(set))
    for marker in markers:
        parts = marker.get("flag", "").split(",")
        sketch = marker.get("pos2")
        if len(parts) >= 3 and parts[0].startswith("@") and parts[1] and parts[2] and isinstance(sketch, list) and len(sketch) == 2:
            by_scene[parts[1]][parts[2]].add((sketch[1], sketch[0]))
    bundle_index = {p.stem.lower(): p for p in bundles_dir.rglob("*.bundle")}
    result = {}
    for scene, pins in sorted(by_scene.items()):
        if not pins:
            continue
        cache = cache_dir / (scene + ".json")
        if cache.is_file():
            objects = json.loads(cache.read_text(encoding="utf-8"))
        elif scene.lower() in bundle_index:
            try:
                objects = world_objects(bundle_index[scene.lower()])
            except Exception as exc:
                print(f"Skipped {scene}: {type(exc).__name__}", file=sys.stderr)
                continue
        else:
            continue
        by_id = defaultdict(list)
        for obj in objects:
            by_id[obj["id"]].append(obj["pos"])
        pairs = []
        for name, sketches in pins.items():
            if len(sketches) != 1 or len(by_id[name]) != 1:
                continue
            x, y = by_id[name][0]
            qx, qy = next(iter(sketches))
            pairs.append((complex(x, y), complex(qx, qy)))
        transform = robust_fit(pairs)
        if transform is None and len(pairs) == 2:
            transform = paired_fit(pairs, transform_prior(trusted_rooms or {}, scene))
        if transform is None and len(pairs) == 1:
            transform = single_landmark_estimate(pairs, transform_prior(trusted_rooms or {}, scene))
        if transform:
            result[scene] = transform
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=Path("C:/Program Files (x86)/Steam/steamapps/common/Hollow Knight Silksong"))
    args = parser.parse_args()
    root = args.game_dir / "Hollow Knight Silksong_Data/StreamingAssets/aa"
    output_path = ROOT / "data/live_positions.json"
    previous = json.loads(output_path.read_text(encoding="utf-8")) if output_path.is_file() else {}
    trusted_rooms = previous.get("rooms", {})
    result = build(ROOT / "data/map/map.json", ROOT / "source/scene-research", root, trusted_rooms)
    output_path.write_text(json.dumps({"format": 2, "method": "scene-object-matches+regional-prior", "maxResidualPixelsForMultiLandmarkFit": 20,
                                "rooms": result}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    quality = {"multi-landmark": 0, "paired-landmarks": 0, "single-landmark-estimate": 0}
    for room in result.values():
        label = room.get("quality", "multi-landmark")
        quality[label] += 1
    print(f"Wrote {len(result)} room transforms to {output_path}: " + ", ".join(f"{count} {label}" for label, count in quality.items()))


if __name__ == "__main__":
    main()
