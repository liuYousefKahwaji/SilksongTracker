"""Local-only live bridge endpoint contract, without launching the game."""
import json
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from silksongtracker.server import App, make_handler, LIVE_TTL


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.app = App.__new__(App)
        self.app.lock = threading.RLock()
        self.app.live = None
        self.app.live_time = 0
        self.app.live_token = "test-secret"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/api/live-position"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def post(self, value, token="test-secret"):
        data = json.dumps(value).encode()
        request = Request(self.url, data=data, headers={"X-Silksong-Live-Token": token}, method="POST")
        return urlopen(request)

    def test_authorized_position_and_expiry(self):
        with self.post({"scene": "sample", "x": 1.5, "y": -2, "map": [5, 9]}) as response:
            self.assertEqual(response.status, 200)
        with urlopen(self.url) as response:
            value = json.load(response)
        self.assertTrue(value["connected"])
        self.assertEqual(value["position"]["map"], [5, 9])
        self.app.live_time = time.monotonic() - LIVE_TTL - 1
        with urlopen(self.url) as response:
            value = json.load(response)
        self.assertFalse(value["connected"])
        self.assertIsNone(value["position"])

    def test_rejects_unauthorized_and_bad_coordinates(self):
        with self.assertRaises(HTTPError) as error:
            self.post({"scene": "sample", "x": 1, "y": 2}, "wrong")
        self.assertEqual(error.exception.code, 403)
        with self.assertRaises(HTTPError) as error:
            self.post({"scene": "sample", "x": True, "y": 2})
        self.assertEqual(error.exception.code, 400)
        self.assertIsNone(self.app.live)

    def test_empty_native_map_uses_room_fallback(self):
        with self.post({"scene": "sample", "x": 1, "y": 2, "map": []}) as response:
            self.assertEqual(response.status, 200)
        self.assertIsNone(self.app.live["map"])


if __name__ == "__main__":
    unittest.main()
