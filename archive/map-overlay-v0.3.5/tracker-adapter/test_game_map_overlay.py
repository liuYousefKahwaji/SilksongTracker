"""Regression checks for the local-only data adapter consumed by the BepInEx overlay."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from threading import RLock
from unittest.mock import patch
from urllib.error import HTTPError

from silksongtracker import mapassets
from silksongtracker.mapdata import build_map
from silksongtracker.server import App, make_handler


class GameMapPayloadTests(unittest.TestCase):
    def test_payload_is_compact_and_uses_flattened_crs_simple_bounds(self):
        app = App.__new__(App)
        app.lock = RLock()
        app.refresh_if_changed = lambda: None
        app.state = type("State", (), {"map": lambda self: {
            "title": "Pharloom", "hasSave": True, "slot": 2,
            "groups": [{"id": "g", "name": "Group", "icon": "g.png", "visible": True}],
            "categories": [{"id": "c", "name": "Cat", "group": "g", "icon": "c.png"}],
            "markers": [{"id": "1", "cat": "c", "name": "Pin", "icon": "i.png",
                         "pos": [-12, 34], "pos2": [-8, 21], "status": "left",
                         "tracking": "save", "trackingNote": None, "flag": "private detail"}],
            "labels": [{"name": "AREA", "pos": [-4, 30]}],
            "image": {"tileSize": 1024, "maxZoom": 4, "bounds": [[-944, 0], [0, 1280]]},
            "validTiles": ["4/1_2"],
            "sketch": {"tileSize": 1024, "maxZoom": 2, "bounds": [[-2048, 0], [0, 2048]],
                       "validTiles": ["2/3_4"]},
        }} )()
        payload = app.payload("game-map")
        self.assertEqual(payload["screenshots"]["minLat"], -944)
        self.assertEqual(payload["screenshots"]["maxLng"], 1280)
        self.assertEqual(payload["screenshots"]["validTiles"], ["4/1_2"])
        self.assertEqual(payload["sketch"]["maxZoom"], 2)
        self.assertNotIn("flag", payload["markers"][0])
        self.assertEqual(payload["markers"][0]["pos2"], [-8, 21])

    def test_real_source_dataset_pins_and_tiles_are_preserved(self):
        source = build_map(None)
        app = App.__new__(App)
        app.lock = RLock()
        app.state = type("State", (), {"map": lambda self: source})()
        payload = app.payload("game-map")
        self.assertEqual(len(payload["markers"]), len(source["markers"]))
        self.assertEqual(len(payload["categories"]), len(source["categories"]))
        self.assertEqual(payload["screenshots"]["validTiles"], source["validTiles"])
        self.assertEqual(payload["sketch"]["validTiles"], source["sketch"]["validTiles"])
        source_by_id = {marker["id"]: marker for marker in source["markers"]}
        for marker in payload["markers"]:
            original = source_by_id[marker["id"]]
            self.assertEqual(marker.get("pos2"), original.get("pos2"))
            self.assertEqual(marker["pos"], original["pos"])

    def test_only_existing_whitelisted_tiles_are_converted(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is only needed for the map build/test extra")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sketch = root / "data" / "map" / "sketch"
            sketch.mkdir(parents=True)
            tile = sketch / "2" / "3_4.webp"
            tile.parent.mkdir()
            Image.new("RGB", (16, 16), "#c07544").save(tile, "WEBP")
            metadata = {"sketch": {"validTiles": ["2/3_4"], "url": "/map/sketch/{z}/{x}_{y}.webp"}}
            with patch.object(mapassets, "ROOT", root), patch.object(mapassets, "_metadata", return_value=metadata):
                with mapassets._LOCK:
                    mapassets._CACHE.clear()
                result = mapassets.tile_jpeg("sketch", "2", "3", "4")
                self.assertTrue(result.startswith(b"\xff\xd8"))
                self.assertIsNone(mapassets.tile_jpeg("sketch", "2", "3", "5"))
                self.assertIsNone(mapassets.tile_jpeg("../data", "2", "3", "4"))
                self.assertIsNone(mapassets.tile_jpeg("screenshots", "2", "3", "4"))

    def test_overlay_api_routes_only_serve_loopback_tracker_data(self):
        app = App.__new__(App)
        app.lock = RLock()
        app.refresh_if_changed = lambda: None
        app.state = type("State", (), {"map": lambda self: {
            "title": "Pharloom", "hasSave": False, "slot": None, "groups": [], "categories": [],
            "markers": [], "labels": [], "image": {"tileSize": 1024, "maxZoom": 0,
                "bounds": [[-944, 0], [0, 1280]]}, "validTiles": [],
            "sketch": {"tileSize": 1024, "maxZoom": 0, "bounds": [[-2048, 0], [0, 2048]],
                       "validTiles": []},
        }})()
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            root = "http://127.0.0.1:" + str(server.server_address[1])
            with urlopen(root + "/api/game-map") as response:
                self.assertEqual(response.headers.get_content_type(), "application/json")
                payload = json.loads(response.read())
                self.assertEqual(payload["screenshots"]["maxLng"], 1280)
            def fake_tile(style, z, x, y):
                return b"\xff\xd8tile" if style == "sketch" and (z, x, y) == ("0", "0", "0") else None
            with patch("silksongtracker.server.tile_jpeg", side_effect=fake_tile):
                with urlopen(root + "/api/game-map-tile?style=sketch&z=0&x=0&y=0") as response:
                    self.assertEqual(response.headers.get_content_type(), "image/jpeg")
                    self.assertTrue(response.read().startswith(b"\xff\xd8"))
            with patch("silksongtracker.server.tile_jpeg",
                       side_effect=mapassets.MapTileDependencyError("Pillow is required")):
                with self.assertRaises(HTTPError) as error:
                    urlopen(root + "/api/game-map-tile?style=sketch&z=0&x=0&y=0")
                self.assertEqual(error.exception.code, 503)
            with self.assertRaises(HTTPError):
                urlopen(root + "/api/game-map-tile?style=../../secret&z=0&x=0&y=0")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
