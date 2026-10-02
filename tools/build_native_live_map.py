"""Build native in-game-map geometry for every loadable Sketch room.

Requires the installed Silksong game and UnityPy from source/.deps. The output
contains only room bounds, scene sizes, and a numerical map-to-Sketch transform;
it does not extract or redistribute game artwork.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source/.deps"))

# Scene bundles with no independent overworld-map geometry. These scenes still
# get a useful map location: retain the last mapped room while inside them and
# use a documented parent/area anchor when the bridge starts there cold.
ROOM_ALIASES = {
    "abyss_cocoon": ("label", "THE ABYSS"),
    "bellshrine_lore_additive": ("room", "Bellshrine_Enclave"),
    "belltown_room_doctor": ("room", "Belltown"),
    "belltown_room_pinsmith": ("room", "Belltown"),
    "belltown_room_relic": ("room", "Belltown"),
    "belltown_room_spare": ("room", "Belltown"),
    "bellway_01": ("markers", [46, 47]),
    "bellway_centipede_arena": ("marker", 46),
    "cradle_destroyed_challenge_bench": ("room", "Cradle_Destroyed_Challenge_01"),
    "demoend": ("label", "The Surface"),
    "last_dive": ("label", "THE ABYSS"),
    "last_dive_return": ("label", "THE ABYSS"),
    "memory_ant_queen": ("room", "Ant_Queen"),
    "memory_coral_tower": ("room", "Coral_Tower_01"),
    "memory_first_sinner": ("marker", 561),
    "memory_needolin": ("label", "MEMORIUM"),
    "memory_red": ("label", "MEMORIUM"),
    "memory_silk_heart_bellbeast": ("label", "MEMORIUM"),
    "memory_silk_heart_lacetower": ("label", "MEMORIUM"),
    "memory_silk_heart_wardboss": ("label", "MEMORIUM"),
    "room_caravan_interior": ("label", "GREYMOOR"),
    "room_caravan_interior_travel": ("label", "GREYMOOR"),
    "room_caravan_spa": ("label", "GREYMOOR"),
    "room_witch": ("marker", 123),
    "shellwood_11b_memory": ("room", "Shellwood_11b"),
    "tut_05": ("room", "Tut_04"),
}


def solve3(rows: list[list[float]], values: list[float]) -> list[float] | None:
    matrix = [row[:] + [value] for row, value in zip(rows, values)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(matrix[row][column]))
        if abs(matrix[pivot][column]) < 1e-10:
            return None
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        divisor = matrix[column][column]
        matrix[column] = [value / divisor for value in matrix[column]]
        for row in range(3):
            if row == column:
                continue
            factor = matrix[row][column]
            matrix[row] = [a - factor * b for a, b in zip(matrix[row], matrix[column])]
    return [matrix[row][3] for row in range(3)]


def affine_fit(pairs: list[tuple[float, float, float, float]]) -> dict | None:
    if len(pairs) < 3:
        return None
    rows = [[x, y, 1.0] for x, y, _, _ in pairs]
    normal = [[sum(row[i] * row[j] for row in rows) for j in range(3)] for i in range(3)]
    xcoef = solve3(normal, [sum(row[0] * pair[2] for row, pair in zip(rows, pairs)),
                            sum(row[1] * pair[2] for row, pair in zip(rows, pairs)),
                            sum(pair[2] for pair in pairs)])
    ycoef = solve3(normal, [sum(row[0] * pair[3] for row, pair in zip(rows, pairs)),
                            sum(row[1] * pair[3] for row, pair in zip(rows, pairs)),
                            sum(pair[3] for pair in pairs)])
    if xcoef is None or ycoef is None:
        return None
    return {"x": [round(v, 9) for v in xcoef], "y": [round(v, 9) for v in ycoef]}


def predict(model: dict, x: float, y: float) -> tuple[float, float]:
    return (model["x"][0] * x + model["x"][1] * y + model["x"][2],
            model["y"][0] * x + model["y"][1] * y + model["y"][2])


def residual(model: dict, pair: tuple[float, float, float, float]) -> float:
    px, py = predict(model, pair[0], pair[1])
    return math.hypot(px - pair[2], py - pair[3])


def robust_affine(pairs: list[tuple[str, float, float, float, float]], threshold: float = 18.0,
                  max_iterations: int | None = None) -> tuple[dict | None, list[int], dict]:
    if len(pairs) < 3:
        return None, [], {}
    rng = random.Random(73491)
    best: tuple[tuple[int, float], dict, list[int]] | None = None
    candidates = min(max_iterations or 12000, max(3000, len(pairs) * 30))
    xy = [(p[1], p[2], p[3], p[4]) for p in pairs]
    for _ in range(candidates):
        indices = rng.sample(range(len(pairs)), 3)
        model = affine_fit([xy[i] for i in indices])
        if model is None:
            continue
        if abs(model["x"][0] * model["y"][1] - model["x"][1] * model["y"][0]) < 1e-8:
            continue
        inliers = [i for i, pair in enumerate(xy) if residual(model, pair) <= threshold]
        if len(inliers) < 3:
            continue
        errors = [residual(model, xy[i]) for i in inliers]
        score = (len(inliers), -sum(error * error for error in errors) / len(errors))
        if best is None or score > best[0]:
            best = (score, model, inliers)
    if best is None:
        return None, [], {}
    inliers = best[2]
    for _ in range(3):
        model = affine_fit([xy[i] for i in inliers])
        if model is None:
            break
        next_inliers = [i for i, pair in enumerate(xy) if residual(model, pair) <= threshold]
        if len(next_inliers) < 3 or next_inliers == inliers:
            break
        inliers = next_inliers
    model = affine_fit([xy[i] for i in inliers])
    if model is None:
        return None, [], {}
    errors = [residual(model, xy[i]) for i in inliers]
    loo_errors = []
    for held in inliers:
        training = [xy[i] for i in inliers if i != held]
        loo = affine_fit(training)
        if loo:
            loo_errors.append(residual(loo, xy[held]))
    stats = {
        "pairs": len(pairs), "inliers": len(inliers), "threshold": threshold,
        "rms": round(math.sqrt(sum(e * e for e in errors) / len(errors)), 3),
        "p90": round(sorted(errors)[int(.9 * (len(errors) - 1))], 3),
        "max": round(max(errors), 3),
        "leaveOneRoomOutRms": round(math.sqrt(sum(e * e for e in loo_errors) / len(loo_errors)), 3),
        "leaveOneRoomOutP90": round(sorted(loo_errors)[int(.9 * (len(loo_errors) - 1))], 3),
        "leaveOneRoomOutMax": round(max(loo_errors), 3),
    }
    return model, inliers, stats


def inverse_affine(model: dict, latitude: float, longitude: float) -> list[float] | None:
    """Convert Sketch lat/lon back into the native map-root coordinate system."""
    a, b, c = model["x"]
    d, e, f = model["y"]
    determinant = a * e - b * d
    if abs(determinant) < 1e-10:
        return None
    target_x, target_y = longitude - c, latitude - f
    return [(target_x * e - b * target_y) / determinant,
            (a * target_y - d * target_x) / determinant]


def transform_point_to_root(tid: int, point: tuple[float, float], root_id: int, transforms: dict[int, dict]) -> tuple[float, float] | None:
    x, y = point
    guard = 0
    while tid != root_id:
        transform = transforms.get(tid)
        if transform is None:
            return None
        rotation = transform["m_LocalRotation"]
        angle = 2 * math.atan2(rotation["z"], rotation["w"])
        scale = transform["m_LocalScale"]
        position = transform["m_LocalPosition"]
        sx, sy = x * scale["x"], y * scale["y"]
        x, y = (position["x"] + sx * math.cos(angle) - sy * math.sin(angle),
                position["y"] + sx * math.sin(angle) + sy * math.cos(angle))
        tid = transform["m_Father"]["m_PathID"]
        guard += 1
        if guard > 64:
            return None
    return x, y


def extract_map_rooms(game_dir: Path, report_failures: bool = False) -> dict[str, dict]:
    import UnityPy

    UnityPy.config.FALLBACK_UNITY_VERSION = "6000.0.50f1"
    warnings.filterwarnings("ignore")
    aa = game_dir / "Hollow Knight Silksong_Data/StreamingAssets/aa/StandaloneWindows64"
    map_bundle = aa / "maps_assets_all.bundle"
    if not map_bundle.is_file():
        raise FileNotFoundError(f"Silksong map bundle not found: {map_bundle}")

    env = UnityPy.Environment()
    env.load_file(str(map_bundle))
    # Unity's map bundle has 19 external CAB references. Load their supplying
    # bundles before dereferencing the map objects; loading only the obvious
    # map atlas leaves many sprites unresolved (and used to silently omit rooms).
    dependencies = (
        "572d76c166f4ec5c67aedff26a920797_unitybuiltinassets.bundle",
        "94696d22b6ed0a74097d1bd58feb4dce_monoscripts.bundle",
        "audioobjects_assets_all.bundle",
        "atlases_assets_assets/sprites/_atlases/hornet_map.spriteatlas.bundle",
        "atlases_assets_assets/sprites/_atlases/hornet_map_patch.spriteatlas.bundle",
        "animations_assets_shared.bundle",
        "dataassets_assets_assets/dataassets/collectables/collectableitems.bundle",
        "dataassets_assets_assets/dataassets/questsystem/quests.bundle",
        "dataassets_assets_assets/dataassets/questsystem/mainquests.bundle",
        "fonts_assets_english.bundle",
        "fonts_assets_japanese.bundle",
        "fonts_assets_russian.bundle",
        "hud_assets_all.bundle",
        "inventory_assets_all.bundle",
        "localpoolprefabs_assets_shared.bundle",
        "materials_assets_shared.bundle",
        "sfxstatic_assets_ui.bundle",
        "textures_assets_shared.bundle",
        "tk2danimations_assets_ui.bundle",
    )
    for relative in map(Path, dependencies):
        dependency = aa / relative
        if dependency.is_file():
            env.load_file(str(dependency))
    files = [file for file in env.files.values() if hasattr(file, "files")]
    map_file = env.files[str(map_bundle)]
    for external in getattr(next(iter(map_file.files.values())), "externals", []):
        key = external.path.rsplit("/", 1)[-1]
        for dependency in files:
            if key in dependency.files:
                map_file.files[key] = dependency.files[key]
                break

    transforms = {obj.path_id: obj.read_typetree() for obj in env.objects if obj.type.name == "Transform"}
    root_id = None
    for obj in env.objects:
        if obj.type.name == "GameObject" and obj.read().m_Name == "Game_Map_Hornet":
            root_id = next(component.component.path_id for component in obj.read().m_Component
                            if component.component.deref().type.name == "Transform")
            break
    if root_id is None:
        raise ValueError("Game_Map_Hornet map root was not found")

    result: dict[str, dict] = {}
    failed_sprite = []
    for obj in env.objects:
        if obj.type.name != "GameObject":
            continue
        game_object = obj.read()
        components = [component.component.deref() for component in game_object.m_Component]
        renderer = next((component for component in components if component.type.name == "SpriteRenderer"), None)
        game_map_scene = None
        for component in components:
            if component.type.name != "MonoBehaviour":
                continue
            try:
                tree = component.read_typetree()
            except Exception:
                continue
            if "fullSprite" in tree and "initialState" in tree:
                game_map_scene = component
                break
        if renderer is None or game_map_scene is None:
            continue
        transform = next((component for component in components if component.path_id in transforms), None)
        if transform is None:
            continue
        renderer_error = ""
        try:
            sprite = renderer.read().m_Sprite.deref().read_typetree()
        except Exception as exc:
            renderer_error = f"{type(exc).__name__}: {exc}"
            try:
                sprite = game_map_scene.read().fullSprite.deref().read_typetree()
            except Exception as fallback_exc:
                details = {}
                try:
                    renderer_tree = renderer.read_typetree()
                    sprite_ref = renderer_tree.get("m_Sprite", {})
                    details["rendererSpritePathId"] = sprite_ref.get("m_PathID") if isinstance(sprite_ref, dict) else None
                except Exception:
                    pass
                try:
                    game_map_tree = game_map_scene.read_typetree()
                    full_sprite_ref = game_map_tree.get("fullSprite", {})
                    details["fullSpritePathId"] = full_sprite_ref.get("m_PathID") if isinstance(full_sprite_ref, dict) else None
                    details["mapComponentFields"] = sorted(game_map_tree)
                    details["initialState"] = game_map_tree.get("initialState")
                    for key in ("mappedParent", "unmappedNoBounds", "excludeBounds", "altFullSprites"):
                        if key in game_map_tree:
                            details[key] = game_map_tree[key]
                except Exception:
                    pass
                try:
                    details["mapRootOrigin"] = transform_point_to_root(transform.path_id, (0.0, 0.0), root_id, transforms)
                except Exception:
                    pass
                if details.get("mapRootOrigin") is not None:
                    x, y = details["mapRootOrigin"]
                    result[game_object.m_Name] = {"anchor": [round(x, 6), round(y, 6)],
                                                   "sprite": None, "quality": "in-game-map-room-anchor"}
                failed_sprite.append((game_object.m_Name, renderer_error,
                                      f"{type(fallback_exc).__name__}: {fallback_exc}",
                                      json.dumps(details, sort_keys=True, default=str)))
                continue
        rect, pivot = sprite.get("m_Rect"), sprite.get("m_Pivot")
        ppu = sprite.get("m_PixelsToUnits")
        if not isinstance(rect, dict) or not isinstance(pivot, dict) or not isinstance(ppu, (int, float)) or ppu <= 0:
            failed_sprite.append((game_object.m_Name, "sprite has no usable rectangle/pivot/PPU", "", ""))
            continue
        x0, x1 = (rect["x"] - pivot["x"] * rect["width"]) / ppu, (rect["x"] + (1-pivot["x"]) * rect["width"]) / ppu
        y0, y1 = (rect["y"] - pivot["y"] * rect["height"]) / ppu, (rect["y"] + (1-pivot["y"]) * rect["height"]) / ppu
        corners = [transform_point_to_root(transform.path_id, point, root_id, transforms)
                   for point in ((x0, y0), (x0, y1), (x1, y0), (x1, y1))]
        if any(point is None for point in corners):
            continue
        min_x, max_x = min(p[0] for p in corners), max(p[0] for p in corners)
        min_y, max_y = min(p[1] for p in corners), max(p[1] for p in corners)
        result[game_object.m_Name] = {"bounds": [round(min_x, 6), round(min_y, 6), round(max_x, 6), round(max_y, 6)],
                                      "sprite": sprite.get("m_Name", game_object.m_Name)}
    if failed_sprite:
        print(f"Warning: no sprite geometry for {len(failed_sprite)} map rooms", file=sys.stderr)
        if report_failures:
            for name, first_error, second_error, object_details in sorted(set(failed_sprite)):
                detail = f" ({first_error}; fallback: {second_error}) {object_details}" if first_error else ""
                print(f"map geometry missing: {name}{detail}", file=sys.stderr)
    return result


def extract_scene_size(bundle: Path) -> list[float] | None:
    import UnityPy

    try:
        env = UnityPy.load(str(bundle))
        for obj in env.objects:
            if obj.type.name != "MonoBehaviour":
                continue
            try:
                tree = obj.read_typetree()
            except Exception:
                continue
            width, height = tree.get("width"), tree.get("height")
            if type(width) is int and type(height) is int and width > 0 and height > 0:
                return [float(width), float(height)]
    except Exception:
        return None
    return None


def inventory_scene_bundles(scenes_root: Path) -> dict[str, dict]:
    """Find every bundle with a positive SceneSize-like width/height component.

    We intentionally scan all bundles instead of relying on filename prefixes:
    room scenes, interiors, challenges, and one-off arenas use inconsistent names.
    """
    import UnityPy

    UnityPy.config.FALLBACK_UNITY_VERSION = "6000.0.50f1"
    warnings.filterwarnings("ignore")
    inventory = {}
    bundles = sorted(scenes_root.rglob("*.bundle"))
    for index, bundle in enumerate(bundles, 1):
        size = extract_scene_size(bundle)
        if size:
            inventory[bundle.stem] = {"sceneSize": size, "bundle": str(bundle.relative_to(scenes_root))}
        if index % 250 == 0:
            print(f"Scanned {index}/{len(bundles)} bundles; found {len(inventory)} scene-size components.", file=sys.stderr)
    return inventory


def locate_map_dependency_bundles(game_dir: Path) -> dict:
    """Locate all Unity bundles containing the serialized files referenced by the map bundle."""
    import UnityPy

    UnityPy.config.FALLBACK_UNITY_VERSION = "6000.0.50f1"
    warnings.filterwarnings("ignore")
    scenes_root = game_dir / "Hollow Knight Silksong_Data/StreamingAssets/aa/StandaloneWindows64"
    map_bundle = scenes_root / "maps_assets_all.bundle"
    env = UnityPy.Environment()
    env.load_file(str(map_bundle))
    map_file = env.files[str(map_bundle)]
    external_ids = {external.path.rsplit("/", 1)[-1]
                    for asset in map_file.files.values()
                    for external in getattr(asset, "externals", [])}
    located: dict[str, list[str]] = {external_id: [] for external_id in external_ids}
    bundles = sorted(scenes_root.rglob("*.bundle"))
    for index, bundle in enumerate(bundles, 1):
        if bundle == map_bundle:
            continue
        try:
            candidate = UnityPy.load(str(bundle))
        except Exception:
            continue
        for asset in candidate.files.values():
            if not hasattr(asset, "files"):
                continue
            for external_id in external_ids.intersection(asset.files):
                located[external_id].append(str(bundle.relative_to(scenes_root)))
        if index % 250 == 0:
            print(f"Searched {index}/{len(bundles)} bundles; resolved {sum(bool(paths) for paths in located.values())}/{len(external_ids)} map dependencies.", file=sys.stderr)
    return {"bundleCount": len(bundles), "dependencies": {
        external_id: sorted(paths) for external_id, paths in sorted(located.items())}}


def build(game_dir: Path, map_path: Path, live_path: Path, report_map_failures: bool = False) -> tuple[dict, dict, dict]:
    map_rooms = extract_map_rooms(game_dir, report_failures=report_map_failures)
    map_data = json.loads(map_path.read_text(encoding="utf-8"))
    markers = map_data["markers"]
    live = json.loads(live_path.read_text(encoding="utf-8"))
    scenes_root = game_dir / "Hollow Knight Silksong_Data/StreamingAssets/aa/StandaloneWindows64"
    bundles = {}
    for path in scenes_root.rglob("*.bundle"):
        key = path.stem.lower()
        if key not in bundles or path.parent.name.lower() == "scenes_scenes_scenes":
            bundles[key] = path
    scene_bundle_dir = scenes_root / "scenes_scenes_scenes"
    scene_bundles = {path.stem.lower(): path for path in sorted(scene_bundle_dir.glob("*.bundle"))}
    scene_sizes = {name: size for name, bundle in scene_bundles.items()
                   if (size := extract_scene_size(bundle)) is not None}
    map_room_lookup = {name.lower(): (name, room) for name, room in map_rooms.items()}
    scene_names = set(live.get("rooms", {}))
    scene_names.update(marker.get("flag", "").split(",")[1]
                       for marker in markers
                       if marker.get("flag", "").split(",", 1)[0] in ("@bool", "@int", "@geo")
                       and len(marker.get("flag", "").split(",")) > 1)
    # The archived tracker only names rooms that already have a marker or a
    # legacy live transform. Include every real game room represented in the
    # native map as well, so rooms whose pins lack save rules still get live
    # positioning instead of silently disappearing from the bridge's index.
    scene_names.update(name for name in map_rooms if name.lower() in bundles)
    scene_names.update(scene_sizes)
    legacy_scene_names = {name.lower() for name in live.get("rooms", {})}
    tagged_scene_names = {marker.get("flag", "").split(",")[1]
                          for marker in markers
                          if marker.get("flag", "").split(",", 1)[0] in ("@bool", "@int", "@geo")
                          and len(marker.get("flag", "").split(",")) > 1}
    native_rooms = {}
    for scene in sorted(scene_names):
        match = map_room_lookup.get(scene.lower())
        bundle = scene_bundles.get(scene.lower()) or bundles.get(scene.lower())
        if not match or not bundle:
            continue
        size = scene_sizes.get(scene.lower()) or extract_scene_size(bundle)
        if not size:
            continue
        is_anchor_only = "bounds" not in match[1]
        bounds = match[1].get("bounds")
        if bounds is None:
            anchor = match[1].get("anchor")
            if not isinstance(anchor, list) or len(anchor) != 2:
                continue
            bounds = [anchor[0], anchor[1], anchor[0], anchor[1]]
        native_rooms[bundle.stem] = {"bounds": bounds, "sceneSize": size, "anchorOnly": is_anchor_only,
                                     "anchorSource": match[1].get("quality") if is_anchor_only else None}

    pairs = []
    native_by_lower = {name.lower(): room for name, room in native_rooms.items()}
    for scene, room in live.get("rooms", {}).items():
        native = native_by_lower.get(scene.lower())
        if not native or not isinstance(room.get("source"), list) or not isinstance(room.get("sketch"), list):
            continue
        x, y = room["source"]
        min_x, min_y, max_x, max_y = native["bounds"]
        width, height = native["sceneSize"]
        nx = min_x + (max_x - min_x) * x / width
        ny = min_y + (max_y - min_y) * y / height
        # Room transforms store Sketch in (longitude, latitude) order.
        pairs.append((scene, nx, ny, room["sketch"][0], room["sketch"][1]))
    model, inliers, stats = robust_affine(pairs)
    if model:
        model.update({"method": "native-room-sprite-to-sketch-affine-v1", "quality": stats})

    # Several shipped scenes are intentionally absent from the overworld-map
    # objects (shop interiors, memory vignettes, and end/challenge variants).
    # Give them an honest parent/area anchor and let the bridge preserve the
    # last mapped location while the player is inside the non-spatial scene.
    image_pairs = [(marker["id"], marker["pos"][1], marker["pos"][0], marker["pos2"][1], marker["pos2"][0])
                   for marker in markers
                   if isinstance(marker.get("pos"), list) and len(marker["pos"]) == 2
                   and isinstance(marker.get("pos2"), list) and len(marker["pos2"]) == 2]
    image_model, _, image_stats = robust_affine(image_pairs, threshold=20.0, max_iterations=3000)
    marker_by_id = {str(marker.get("id")): marker for marker in markers}
    label_by_name = {}
    for label in map_data.get("labels", []):
        label_by_name.setdefault(label.get("name", "").casefold(), label)

    def target_sketch(kind: str, value):
        if kind == "room":
            target = native_rooms.get(str(value).lower())
            if not target or not model:
                return None
            bounds = target["bounds"]
            native_point = ((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)
            longitude, latitude = predict(model, *native_point)
            return [latitude, longitude]
        if kind in ("marker", "markers"):
            ids = [value] if kind == "marker" else value
            points = []
            for marker_id in ids:
                marker = marker_by_id.get(str(marker_id))
                if not marker:
                    continue
                if isinstance(marker.get("pos2"), list) and len(marker["pos2"]) == 2:
                    points.append(marker["pos2"])
                elif image_model and isinstance(marker.get("pos"), list) and len(marker["pos"]) == 2:
                    longitude, latitude = predict(image_model, marker["pos"][1], marker["pos"][0])
                    points.append([latitude, longitude])
            if points:
                return [sum(point[axis] for point in points) / len(points) for axis in (0, 1)]
            return None
        if kind == "label":
            label = label_by_name.get(str(value).casefold())
            if label and image_model and isinstance(label.get("pos"), list) and len(label["pos"]) == 2:
                longitude, latitude = predict(image_model, label["pos"][1], label["pos"][0])
                return [latitude, longitude]
        return None

    legacy_by_lower = {name.lower(): room for name, room in live.get("rooms", {}).items()}
    missing_aliases = []
    for scene, (kind, value) in ROOM_ALIASES.items():
        if scene in native_rooms or scene in legacy_by_lower or scene not in scene_sizes:
            continue
        sketch_point = target_sketch(kind, value)
        native_point = inverse_affine(model, *sketch_point) if model and sketch_point else None
        if native_point is None:
            missing_aliases.append(scene)
            continue
        native_rooms[scene_bundles[scene].stem] = {
            "bounds": [native_point[0], native_point[1], native_point[0], native_point[1]],
            "sceneSize": scene_sizes[scene], "anchorOnly": True,
            "inheritLastPosition": True, "anchorSource": f"{kind}:{value}",
        }

    # Three shipped room-size scenes have no independent overworld map root
    # and were absent from the 546 native geometry/anchor records. Preserve
    # their researched room-local Sketch transforms in the exact resource the
    # BepInEx bridge embeds; a browser-only fallback is not runtime coverage.
    native_by_lower = {name.lower() for name in native_rooms}
    for scene, size in sorted(scene_sizes.items()):
        key = scene.lower()
        if key in native_by_lower:
            continue
        legacy = legacy_by_lower.get(key)
        if not legacy:
            continue
        source, sketch = legacy.get("source"), legacy.get("sketch")
        real, imag = legacy.get("real"), legacy.get("imag")
        if (not isinstance(source, list) or len(source) != 2 or
                not isinstance(sketch, list) or len(sketch) != 2 or
                not isinstance(real, (int, float)) or not isinstance(imag, (int, float))):
            continue
        bundle = scene_bundles.get(key)
        if not bundle:
            continue
        native_rooms[bundle.stem] = {
            "sceneSize": size,
            "legacyOnly": True,
            "legacySource": source,
            # Legacy transforms store Sketch as (longitude, latitude).
            "legacySketchLonLat": sketch,
            "real": real,
            "imag": imag,
            "reflected": bool(legacy.get("reflected")),
            "anchorSource": "legacy-room-transform",
        }

    # A bridge room counts as covered only when its transform is emitted into
    # the embedded native-room resource. The historical browser transform
    # table alone cannot rescue a missing plugin room at runtime.
    covered = {name.lower() for name in native_rooms}
    # This is a PersistentBoolItem save-key alias on the Bone_East_10 Toll
    # Door, not a runtime room/scene that Hornet can occupy or position.
    actual_scenes = {name.lower() for name in tagged_scene_names} - {"pilgrims rest"}
    additional_legacy_scenes = sorted(legacy_scene_names - actual_scenes)
    native_map_scenes = {name.lower() for name in native_rooms}
    room_inventory = []
    for scene, size in sorted(scene_sizes.items()):
        room = native_rooms.get(scene)
        if room and room.get("legacyOnly"):
            positioning = "legacy-room-transform"
        elif room and room.get("inheritLastPosition"):
            positioning = "last-known-area-anchor"
        elif room and room.get("anchorOnly"):
            positioning = "in-game-room-anchor"
        elif room:
            positioning = "in-game-room-geometry"
        elif scene in legacy_by_lower:
            positioning = "legacy-room-transform"
        else:
            positioning = "unmapped"
        room_inventory.append({"name": scene, "sceneSize": size, "positioning": positioning,
                               "anchorSource": room.get("anchorSource") if room else None})
    uncovered_game_scenes = sorted(entry["name"] for entry in room_inventory
                                   if entry["name"] not in covered)
    report = {"mapSprites": len(map_rooms), "loadableRoomSizes": len(native_rooms),
              "mapTaggedRooms": len(actual_scenes), "coveredRooms": len(actual_scenes & covered),
              "uncoveredRooms": sorted(actual_scenes - covered),
              "legacyFallbackTransforms": len(legacy_scene_names),
              "additionalLegacyFallbackRooms": additional_legacy_scenes,
              "nativeMapRooms": len(native_map_scenes),
              "nativeMapAnchorOnlyRooms": sum(1 for room in native_rooms.values() if room.get("anchorOnly")),
              "nativeMapRoomsWithoutLegacyAnchors": len(native_map_scenes - {name.lower() for name in live.get("rooms", {})}),
              "anchorPairs": len(pairs),
              "gameSceneSizeBundles": len(scene_sizes),
              "coveredGameSceneSizeBundles": len(room_inventory) - len(uncovered_game_scenes),
              "uncoveredGameSceneBundles": uncovered_game_scenes,
              "syntheticRoomAliases": sum(1 for room in native_rooms.values() if room.get("anchorSource")),
              "unresolvedRoomAliases": sorted(missing_aliases)}
    return native_rooms, model or {}, {"report": report, "stats": stats,
                                       "outliers": [pairs[i][0] for i in range(len(pairs)) if i not in set(inliers)],
                                       "roomInventory": room_inventory,
                                       "imageToSketchQuality": image_stats}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=Path("C:/Program Files (x86)/Steam/steamapps/common/Hollow Knight Silksong"))
    parser.add_argument("--dry-run", action="store_true", help="Print coverage and cross-validation diagnostics without writing files")
    parser.add_argument("--audit-all-bundles", action="store_true", help="Scan every bundle for a room-size component and report coverage gaps")
    parser.add_argument("--audit-map-failures", action="store_true", help="List map sprites whose geometry could not be decoded")
    parser.add_argument("--audit-map-dependencies", action="store_true", help="Find all bundles supplying the map bundle's referenced serialized assets")
    args = parser.parse_args()
    if args.audit_map_dependencies:
        print(json.dumps(locate_map_dependency_bundles(args.game_dir), indent=2))
        return
    if args.audit_map_failures:
        extract_map_rooms(args.game_dir, report_failures=True)
        return
    if args.audit_all_bundles:
        scenes_root = args.game_dir / "Hollow Knight Silksong_Data/StreamingAssets/aa/StandaloneWindows64"
        inventory = inventory_scene_bundles(scenes_root)
        native_file = json.loads((ROOT / "data/live_native_rooms.json").read_text(encoding="utf-8"))
        native_rooms = {room["name"].lower() for room in native_file.get("rooms", [])}
        live_file = json.loads((ROOT / "data/live_positions.json").read_text(encoding="utf-8"))
        fallback = {name.lower() for name in live_file.get("rooms", {})}
        unmapped = sorted((entry for name, entry in inventory.items() if name.lower() not in native_rooms), key=lambda item: item["bundle"].lower())
        report = {"bundlesScanned": len(list(scenes_root.rglob("*.bundle"))),
                  "sceneSizeBundles": len(inventory), "nativeMapRoomBounds": len(native_rooms),
                  "sceneBundlesWithLegacyFallback": sum(1 for name in inventory if name.lower() in fallback),
                  "unmappedSceneSizeBundles": unmapped,
                  "uncoveredSceneNames": sorted(name for name in inventory if name.lower() not in native_rooms)}
        print(json.dumps(report, indent=2))
        return
    rooms, model, evidence = build(args.game_dir, ROOT / "data/map/map.json", ROOT / "data/live_positions.json")
    print(json.dumps({**evidence["report"], "stats": evidence["stats"], "imageToSketchQuality": evidence["imageToSketchQuality"],
                      "outlierScenes": evidence["outliers"], "nativeMap": model}, indent=2))
    if args.dry_run:
        return
    if not model or evidence["stats"].get("leaveOneRoomOutRms", 1e9) > 20:
        raise SystemExit("Native map model failed its held-out validation; outputs were not changed.")
    if evidence["report"]["uncoveredGameSceneBundles"] or evidence["report"]["unresolvedRoomAliases"]:
        raise SystemExit("One or more game scene bundles lack a map anchor; outputs were not changed.")
    output = ROOT / "data/live_native_rooms.json"
    resource = {"format": 1, "rooms": [{"name": name, **room} for name, room in sorted(rooms.items())]}
    output.write_text(json.dumps(resource, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    inventory_path = ROOT / "data/live_room_inventory.json"
    inventory_resource = {"format": 1, "roomSceneBundles": len(evidence["roomInventory"]),
                          "positioningCounts": {kind: sum(1 for room in evidence["roomInventory"] if room["positioning"] == kind)
                                                for kind in sorted({room["positioning"] for room in evidence["roomInventory"]})},
                          "rooms": evidence["roomInventory"]}
    inventory_path.write_text(json.dumps(inventory_resource, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    live_path = ROOT / "data/live_positions.json"
    live = json.loads(live_path.read_text(encoding="utf-8"))
    live["nativeMap"] = model
    live["nativeMapEvidence"] = evidence["stats"]
    live_path.write_text(json.dumps(live, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(rooms)} native/area positions for {len(evidence['roomInventory'])} game scene bundles and a validated map transform.")


if __name__ == "__main__":
    main()
