import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NativeLiveMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = json.loads((ROOT / "data/live_positions.json").read_text(encoding="utf-8"))
        cls.rooms = json.loads((ROOT / "data/live_native_rooms.json").read_text(encoding="utf-8"))

    def test_room_resource_contains_valid_live_position_mappings(self):
        self.assertEqual(self.rooms["format"], 1)
        self.assertIsInstance(self.rooms["rooms"], list)
        self.assertEqual(len(self.rooms["rooms"]), 549)
        for room in self.rooms["rooms"]:
            self.assertTrue(room["name"])
            self.assertEqual(len(room["sceneSize"]), 2)
            if room.get("legacyOnly"):
                self.assertEqual(len(room["legacySource"]), 2)
                self.assertEqual(len(room["legacySketchLonLat"]), 2)
                self.assertTrue(all(isinstance(room[key], (int, float)) for key in ("real", "imag")))
                continue
            self.assertEqual(len(room["bounds"]), 4)
            if room.get("anchorOnly"):
                self.assertEqual(room["bounds"][0], room["bounds"][2])
                self.assertEqual(room["bounds"][1], room["bounds"][3])
            else:
                self.assertLess(room["bounds"][0], room["bounds"][2])
                self.assertLess(room["bounds"][1], room["bounds"][3])
            self.assertGreater(room["sceneSize"][0], 0)
            self.assertGreater(room["sceneSize"][1], 0)

    def test_native_map_model_has_strong_room_held_out_fit(self):
        model = self.live["nativeMap"]
        self.assertEqual(model["method"], "native-room-sprite-to-sketch-affine-v1")
        self.assertEqual(len(model["x"]), 3)
        self.assertEqual(len(model["y"]), 3)
        quality = model["quality"]
        self.assertGreaterEqual(quality["inliers"], 220)
        self.assertLess(quality["leaveOneRoomOutRms"], 6)
        self.assertLess(quality["leaveOneRoomOutP90"], 8)

    def test_room_geometry_and_legacy_transforms_cover_every_tagged_source_scene(self):
        native = {room["name"].lower() for room in self.rooms["rooms"]}
        fallback = {name.lower() for name in self.live["rooms"]}
        self.assertEqual(len(native), 549)
        self.assertGreaterEqual(len(fallback), 270)

        source = json.loads((ROOT / "data/map/map.json").read_text(encoding="utf-8"))
        tagged = set()
        for marker in source["markers"]:
            parts = marker.get("flag", "").split(",")
            if len(parts) > 1 and parts[0] in ("@bool", "@int", "@geo"):
                tagged.add(parts[1])
        self.assertIn("Pilgrims Rest", tagged)
        # It is the saved scene key on the Bone_East_10 Toll Door, not a
        # runtime scene; live position is reported in Bone_East_10 instead.
        alias_objects = json.loads((ROOT / "source/scene-research/Bone_East_10.json").read_text(encoding="utf-8"))
        self.assertTrue(any(obj.get("item", {}).get("SceneName") == "Pilgrims Rest"
                            and obj.get("item", {}).get("ID") == "Toll Door" for obj in alias_objects))
        tagged.discard("Pilgrims Rest")
        self.assertEqual(len(tagged), 300)
        uncovered = {name for name in tagged if name.lower() not in native}
        self.assertEqual(uncovered, set(), f"Uncovered tracker scenes: {sorted(uncovered)}")
        self.assertEqual(len(fallback - {name.lower() for name in tagged}), 6)

    def test_every_room_size_bundle_has_a_documented_positioning_mode(self):
        inventory = json.loads((ROOT / "data/live_room_inventory.json").read_text(encoding="utf-8"))
        native = {room["name"].lower(): room for room in self.rooms["rooms"]}
        fallback = {name.lower() for name in self.live["rooms"]}
        self.assertEqual(inventory["roomSceneBundles"], len(inventory["rooms"]))
        self.assertEqual(inventory["roomSceneBundles"], 549)
        self.assertEqual(inventory["positioningCounts"], {
            "in-game-room-anchor": 51,
            "in-game-room-geometry": 469,
            "last-known-area-anchor": 26,
            "legacy-room-transform": 3,
        })
        self.assertEqual(len({room["name"].lower() for room in inventory["rooms"]}), len(inventory["rooms"]))
        self.assertEqual({room["name"].lower() for room in inventory["rooms"]}, set(native))
        expected = {"in-game-room-geometry", "in-game-room-anchor", "legacy-room-transform", "last-known-area-anchor"}
        self.assertTrue({room["positioning"] for room in inventory["rooms"]} <= expected)
        self.assertNotIn("unmapped", {room["positioning"] for room in inventory["rooms"]})

    def test_blasted_steps_and_sands_of_karak_have_direct_room_entries(self):
        native = {room["name"].lower(): room for room in self.rooms["rooms"]}
        inventory = json.loads((ROOT / "data/live_room_inventory.json").read_text(encoding="utf-8"))
        expected = {"coral_": (31, 29, 2), "dust_": (25, 13, 12)}
        for prefix, (total, geometry, anchors) in expected.items():
            region = [room for room in inventory["rooms"] if room["name"].lower().startswith(prefix)]
            self.assertEqual(len(region), total, f"Unexpected room inventory for {prefix}")
            self.assertTrue(all(room["name"].lower() in native for room in region),
                            f"Bridge data missing {prefix} scenes")
            self.assertEqual(sum(room["positioning"] == "in-game-room-geometry" for room in region), geometry)
            self.assertEqual(sum(room["positioning"] == "in-game-room-anchor" for room in region), anchors)

    def test_legacy_only_room_transforms_are_embedded_not_browser_only(self):
        native = {room["name"].lower(): room for room in self.rooms["rooms"]}
        self.assertEqual({name for name, room in native.items() if room.get("legacyOnly")}, {
            "bone_east_lavachallenge", "room_crowcourt", "room_crowcourt_02",
        })


if __name__ == "__main__":
    unittest.main()
