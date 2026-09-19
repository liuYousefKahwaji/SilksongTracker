from __future__ import annotations

import json
import sys
import unittest
from unittest.mock import Mock, patch
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from silksongtracker.analyzer import analyze  # noqa: E402
from silksongtracker.codec import decode_save  # noqa: E402
from silksongtracker.database import load_content  # noqa: E402
from silksongtracker.rules import evaluate  # noqa: E402
from silksongtracker.schema import SaveView  # noqa: E402
from silksongtracker.mapdata import build_map, flag_status  # noqa: E402
from tools.build_map import live_config  # noqa: E402
from silksongtracker.server import App  # noqa: E402


class CoreTests(unittest.TestCase):
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

    def test_ingame_map_asset_and_overlay_coordinates(self):
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


if __name__ == "__main__": unittest.main()
