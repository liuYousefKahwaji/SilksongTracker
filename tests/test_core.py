from __future__ import annotations

import json
import sys
import unittest
from unittest.mock import Mock, patch
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from silksongtracker.analyzer import analyze  # noqa: E402
from silksongtracker.codec import decode_save  # noqa: E402
from silksongtracker.database import load_content  # noqa: E402
from silksongtracker.rules import evaluate  # noqa: E402
from silksongtracker.schema import SaveView  # noqa: E402
from silksongtracker.mapdata import build_map, flag_status  # noqa: E402
from tools.build_map import interior_groups, live_config, map_connections  # noqa: E402
from silksongtracker.server import App, make_handler  # noqa: E402
from silksongtracker.state import TrackerState  # noqa: E402


class CoreTests(unittest.TestCase):
    def test_save_selection_keeps_exact_file_when_slots_repeat(self):
        state = TrackerState.__new__(TrackerState)
        state.extra_dirs = []
        state.saves = []
        state.selected_slot = None
        state.selected_path = None
        files = [
            {'slot': 1, 'path': 'first.dat', 'size': 2, 'mtime': 1},
            {'slot': 1, 'path': 'second.dat', 'size': 2, 'mtime': 1},
        ]
        with patch('silksongtracker.state.find_saves', side_effect=[files, files, list(reversed(files))]), patch('silksongtracker.state.read_save', side_effect=lambda path: {'chosen':path}):
            state.refresh()
            state.select_index(1)
            self.assertEqual(state.raw['chosen'], 'second.dat')
            state.refresh()
        self.assertEqual(state.state()['selectedSaveIndex'], 0)
        with self.assertRaises(ValueError): state.select_index(2)

    def test_save_changes_refresh_live_map_state(self):
        app = App.__new__(App)
        app.lock = threading.RLock()
        slot = {'path':'fixture.dat','mtime':1,'size':100}
        app.state = Mock(extra_dirs=[], saves=[slot])
        with patch('silksongtracker.server.find_saves', return_value=[dict(slot)]):
            app.refresh_if_changed()
        app.state.refresh.assert_not_called()
        with patch('silksongtracker.server.find_saves', return_value=[{**slot,'mtime':2}]):
            app.refresh_if_changed()
        app.state.refresh.assert_called_once()

    def test_refresh_route_returns_a_readable_error_when_rescan_fails(self):
        app = App.__new__(App)
        app.refresh = Mock(side_effect=OSError("save directory unavailable"))
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            request = Request(f"http://127.0.0.1:{server.server_port}/api/refresh", method="POST")
            with self.assertRaises(HTTPError) as raised:
                urlopen(request)
            self.assertEqual(raised.exception.code, 500)
            self.assertEqual(json.loads(raised.exception.read())["error"], "Save refresh failed: save directory unavailable")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_select_route_parses_index_query(self):
        app = App.__new__(App)
        app.lock = threading.RLock()
        app.state = Mock()
        app.state.state.return_value = {"selectedSaveIndex": 1}
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            request = Request(f"http://127.0.0.1:{server.server_port}/api/select?index=1", method="POST")
            with urlopen(request) as response:
                self.assertEqual(json.loads(response.read())["selectedSaveIndex"], 1)
            app.state.select_index.assert_called_once_with(1)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_plain_json_decode(self):
        raw = decode_save(json.dumps({"playerData": {"flag": True}}).encode())
        self.assertTrue(raw["playerData"]["flag"])

    def test_rules_have_unknown_state(self):
        self.assertEqual(evaluate({"type": "bool", "path": "missing"}, SaveView({})), "unknown")
        self.assertEqual(evaluate({"type": "bool", "path": "playerData.flag"}, SaveView({"playerData": {"flag": True}})), "complete")

    def test_official_points_are_exactly_one_hundred(self):
        content = load_content()
        sections = {s["id"]: s for s in content["sections"]}
        self.assertEqual(sum(len(sections[key]["entries"]) for key in ("tools", "silk-skills", "upgrades", "silk-hearts", "crests", "abilities", "mask-upgrades", "silk-upgrades", "needle-upgrades", "items")), 100)

    def test_no_save_is_unknown_safe(self):
        state = analyze(None)
        self.assertFalse(state["hasSave"])
        self.assertEqual(state["summary"]["complete"], 0)
        self.assertEqual(state["summary"]["unknown"], 100)

    def test_supporting_checklist_counts_are_separate_from_official_completion(self):
        complete_ids = {"tools-01", "fleas-01", "fleas-02", "bellways-01", "ventrica-01"}

        def result(entry, _save):
            status = "complete" if entry["id"] in complete_ids else "left"
            return {**entry, "status": status, "known": True, "map": None}

        with patch("silksongtracker.analyzer._entry_result", side_effect=result):
            state = analyze({"playerData": {}})

        groups = {group["id"]: group for group in state["groups"]}
        self.assertEqual((groups["fleas"]["complete"], groups["fleas"]["total"]), (2, 30))
        self.assertEqual((groups["bellways"]["complete"], groups["bellways"]["total"]), (1, 12))
        self.assertEqual((groups["ventrica"]["complete"], groups["ventrica"]["total"]), (1, 7))
        self.assertEqual((state["summary"]["complete"], state["summary"]["total"]), (1, 100))

    def test_ingame_map_has_deep_link_for_checklist(self):
        data = build_map(None)
        ids = {m['id'] for m in data['markers']}
        for section in load_content()['sections']:
            if not section.get('points'): continue
            for entry in section['entries']:
                self.assertIn(entry['id'], data['links'], entry['name'])
                self.assertTrue(set(data['links'][entry['id']]['ids']) <= ids)
        self.assertEqual(data['links']['tools-01']['ids'], ['85'])
        self.assertEqual(data['links']['items-01']['ids'], ['1039'])
        self.assertEqual(data['links']['mask-upgrades-01']['kind'], 'components')
        self.assertEqual(len(data['links']['mask-upgrades-01']['ids']),20)

    def test_tracker_map_asset_coordinates(self):
        source = live_config(ROOT / 'source' / 'ssMap.js')
        source_positions = {str(m['uid']):m['pos'] for c in source['categories'] for m in c['list'] if 'uid' in m}
        data = build_map(None)
        for marker in data['markers']:
            if marker['id'] in source_positions:
                self.assertEqual(marker['pos'],source_positions[marker['id']])
            self.assertNotIn('generated',marker)
            self.assertTrue((ROOT / 'data/map/icons' / marker['icon']).is_file(),marker['icon'])
        for key in data['validTiles']:
            self.assertTrue((ROOT / 'data/map/tiles' / (key+'.webp')).is_file(),key)

    def test_map_flags_do_not_invent_missing_progress(self):
        self.assertEqual(flag_status('@,playerData.hasDash,true',None),'unknown')
        self.assertEqual(flag_status('@,playerData.hasDash,true',{}),'unknown')
        self.assertEqual(flag_status('@,playerData.hasDash,true',{'playerData':{'hasDash':False}}),'left')
        self.assertEqual(flag_status('@,playerData.hasDash,true',{'playerData':{'hasDash':True}}),'complete')
        flag='@bool,RoomA,Pickup,true'
        raw={'sceneData':{'persistentBoolItems':[{'sceneName':'RoomB','id':'Pickup','activated':True}]}}
        self.assertEqual(flag_status(flag,raw),'unknown')
        raw['sceneData']['persistentBoolItems'][0]['sceneName']='RoomA'
        self.assertEqual(flag_status(flag,raw),'complete')

    def test_sketch_coordinates_and_offline_tiles(self):
        source = live_config(ROOT / 'source/ssMap.js')
        positions = {str(m['uid']):m.get('pos2') for c in source['categories'] for m in c['list'] if 'uid' in m}
        data = build_map(None)
        for marker in data['markers']:
            if marker['id'] in positions:
                self.assertEqual(marker.get('pos2'), positions[marker['id']])
        self.assertEqual(sum(isinstance(m.get('pos2'),list) for m in data['markers']),1413)
        self.assertEqual(len(data['sketch']['validTiles']),84)
        for key in data['sketch']['validTiles']:
            self.assertTrue((ROOT / 'data/map/sketch' / (key+'.webp')).is_file(),key)

    def test_collapsed_sketch_locations_become_stable_interiors(self):
        markers = [
            {'id':'one','pos':[10,20],'pos2':[3,4]},
            {'id':'two','pos':[30,40],'pos2':[3,4]},
            {'id':'nearby','pos':[10,21],'pos2':[8,9]},
            {'id':'nearby-too','pos':[10,22],'pos2':[8,9]},
        ]
        labels = [{'name':'Named room','pos':[20,30]}]
        first = interior_groups(markers, labels)
        second = interior_groups(list(reversed(markers)), labels)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]['id'], second[0]['id'])
        self.assertEqual(first[0]['entrance'], [3,4])
        self.assertEqual(set(first[0]['members']), {'one','two'})

    def test_source_room_connections_are_flattened(self):
        raw = {'interactiveMap':{'mapLinks':{
            'smallGaps':[[[1,2],[3,4]]],
            'largeGapsConnectingOverMaps':[[[5,6],[7,8]]],
        }}}
        self.assertEqual(map_connections(raw), [
            {'kind':'smallGaps','from':[1,2],'to':[3,4]},
            {'kind':'largeGapsConnectingOverMaps','from':[5,6],'to':[7,8]},
        ])


if __name__ == "__main__": unittest.main()
