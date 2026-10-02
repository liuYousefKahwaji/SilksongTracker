import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LiveBridgeSourceTests(unittest.TestCase):
    def test_active_scene_is_resolved_before_the_persistent_hero_scene(self):
        source = (ROOT / "live-bridge/LiveBridge.cs").read_text(encoding="utf-8")
        resolver = source.split("private string ResolveRoomScene", 1)[1].split("private bool HasRoom", 1)[0]
        self.assertLess(resolver.index("SceneManager.GetActiveScene()"),
                        resolver.index("hero.gameObject.scene.name"))
        self.assertIn("SceneManager.GetSceneAt(i)", resolver)
        self.assertIn('"DontDestroyOnLoad"', resolver)

    def test_embedded_room_resource_is_loaded_and_counted(self):
        source = (ROOT / "live-bridge/LiveBridge.cs").read_text(encoding="utf-8")
        project = (ROOT / "live-bridge/SilksongLiveBridge.csproj").read_text(encoding="utf-8")
        self.assertIn('SilksongLiveBridge.live_native_rooms.json', project)
        self.assertIn("JsonConvert.DeserializeObject<NativeRoomSet>", source)
        self.assertIn("Loaded live-position mappings for ", source)
        self.assertIn("Expected mappings for 549 room-size scenes", source)
        self.assertIn('"legacy-room-transform"', source)

    def test_overlay_is_not_part_of_the_active_mod_or_tracker(self):
        source = (ROOT / "live-bridge/LiveBridge.cs").read_text(encoding="utf-8")
        project = (ROOT / "live-bridge/SilksongLiveBridge.csproj").read_text(encoding="utf-8")
        server = (ROOT / "silksongtracker/server.py").read_text(encoding="utf-8")
        self.assertNotIn("TrackerMapOverlay", source)
        self.assertNotIn("Map Overlay", source)
        self.assertNotIn("0Harmony", project)
        self.assertNotIn("UnityEngine.IMGUIModule", project)
        self.assertNotIn("game-map-tile", server)
        self.assertFalse((ROOT / "silksongtracker/mapassets.py").exists())


if __name__ == "__main__":
    unittest.main()
