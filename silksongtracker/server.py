"""Threaded local HTTP/SSE server for the tracker UI."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .database import ROOT, load_areas, load_content
from .state import TrackerState
from .codec import find_saves

WEB = ROOT / "web"


class App:
    def __init__(self, extra_dirs: list[str] | None = None):
        self.state = TrackerState(extra_dirs)
        self.lock = threading.RLock()
        self.stop = False

    def refresh(self):
        with self.lock: self.state.refresh()

    def refresh_if_changed(self):
        with self.lock:
            latest = find_saves(self.state.extra_dirs)
            fingerprint = lambda slots: sorted((s['path'], s['mtime'], s['size']) for s in slots)
            if fingerprint(latest) != fingerprint(self.state.saves):
                self.state.refresh()

    def payload(self, kind: str):
        with self.lock:
            if kind == "state": return self.state.state()
            if kind == "map": return self.state.map()
            if kind == "meta":
                content = load_content()
                return {"game": "Hollow Knight: Silksong", "version": content.get("version"), "areas": load_areas(), "sections": [{"id": x["id"], "name": x["name"], "total": len(x.get("entries", []))} for x in content.get("sections", [])]}
            return {"ok": True, "time": time.time()}


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SilksongTracker/0.2.1"

        def log_message(self, fmt, *args):
            if os.environ.get("SILKSONG_TRACKER_LOG"):
                super().log_message(fmt, *args)

        def send_json(self, value, status=200):
            body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path); route = parsed.path
            if route == "/api/state": return self.send_json(app.payload("state"))
            if route == "/api/map": return self.send_json(app.payload("map"))
            if route == "/api/meta": return self.send_json(app.payload("meta"))
            if route == "/health": return self.send_json({"ok": True, "game": "silksong"})
            if route == "/events":
                self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-cache"); self.send_header("Connection", "keep-alive"); self.end_headers()
                try:
                    last = ""
                    for _ in range(60):
                        app.refresh_if_changed()
                        value = app.payload("state")
                        comparison = dict(value); comparison.pop("generatedAt", None)
                        fingerprint = json.dumps(comparison, separators=(",", ":"), sort_keys=True)
                        payload = json.dumps(value, separators=(",", ":"))
                        if fingerprint != last:
                            self.wfile.write(f"event: state\ndata: {payload}\n\n".encode()); self.wfile.flush(); last = fingerprint
                        time.sleep(1)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass
                return
            if route in ("/", "/index.html"): return self.serve(WEB / "index.html")
            if route == "/map": return self.serve(WEB / "map.html")
            if route.startswith('/map/'):
                map_root = (ROOT / 'data' / 'map').resolve()
                path = (map_root / route[5:]).resolve()
                if map_root in path.parents and path.is_file(): return self.serve(path)
                return self.send_json({'error':'map asset not found'}, 404)
            if route.startswith("/"):
                path = (WEB / route.lstrip("/")).resolve()
                if WEB.resolve() in path.parents and path.is_file(): return self.serve(path)
            self.send_json({"error": "not found"}, 404)

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/select":
                query = parse_qs(parsed.query)
                try:
                    with app.lock:
                        if "index" in query: app.state.select_index(int(query["index"][0]))
                        elif "slot" in query: app.state.select(int(query["slot"][0]))
                        else: raise ValueError("Save index is required")
                        result = app.state.state()
                except (TypeError, ValueError) as exc: return self.send_json({"error":str(exc)},400)
                return self.send_json(result)
            if parsed.path == "/api/refresh": app.refresh(); return self.send_json(app.payload("state"))
            self.send_json({"error": "not found"}, 404)

        def serve(self, path: Path):
            try: body = path.read_bytes()
            except OSError: return self.send_json({"error": "not found"}, 404)
            content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            cache = 'public, max-age=86400' if path.suffix in ('.png','.webp') else 'no-store'
            self.send_response(200); self.send_header("Content-Type", content_type); self.send_header("Cache-Control", cache); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the local Silksong Tracker")
    parser.add_argument("--port", type=int, default=7397)
    parser.add_argument("--save-dir", action="append", default=[], help="additional directory to scan (repeatable)")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if not (ROOT / 'data/map/map.json').is_file():
        parser.exit(1, 'Map data is not installed. Run: python -m pip install -r requirements-build.txt\nThen: python tools/build_map.py\n')
    app = App(args.save_dir)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(app))
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Silksong Tracker listening at {url}")
    print("No save found: serving unknown-safe UI until Silksong creates userN.dat." if not app.state.saves else f"Found {len(app.state.saves)} save slot(s).")
    if not args.no_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == "__main__": main()
